"""Crash-safe persistence and concurrent local-data mutation tests."""

import json
import stat
import threading
import time

import pytest


def test_config_save_replace_failure_preserves_last_good_file(
    isolated_data_dir, monkeypatch
):
    import config

    config.save_config({"language": "en"})
    original = json.loads((isolated_data_dir / "config.json").read_text())
    monkeypatch.setattr(
        config.os,
        "replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("synthetic")),
    )

    with pytest.raises(config.ConfigSaveError):
        config.save_config({"language": "ja"})

    assert json.loads(
        (isolated_data_dir / "config.json").read_text()
    ) == original


def test_corrupt_config_is_quarantined_and_defaults_still_load(
    isolated_data_dir,
):
    import config

    config_path = isolated_data_dir / "config.json"
    config_path.write_text('{"language":', encoding="utf-8")

    loaded = config.load_config()

    assert loaded["language"] == config.DEFAULT_CONFIG["language"]
    assert not config_path.exists()
    quarantined = list(isolated_data_dir.glob("config.json.bad.*"))
    assert len(quarantined) == 1


def test_dashboard_rejects_known_config_field_with_wrong_type(monkeypatch):
    import config
    import dashboard

    saved = []
    monkeypatch.setattr(
        dashboard, "load_config", lambda: dict(config.DEFAULT_CONFIG)
    )
    monkeypatch.setattr(
        dashboard, "save_config", lambda value: saved.append(value)
    )

    response = dashboard.app.test_client().post(
        "/api/config", json={"sample_rate": "16000"}
    )

    assert response.status_code == 400
    assert response.get_json()["field"] == "sample_rate"
    assert saved == []


def test_load_config_drops_invalid_saved_field_but_keeps_valid_field(
    isolated_data_dir,
):
    import config

    (isolated_data_dir / "config.json").write_text(
        json.dumps({"sample_rate": "16000", "language": "en"}),
        encoding="utf-8",
    )

    loaded = config.load_config()

    assert loaded["sample_rate"] == config.DEFAULT_CONFIG["sample_rate"]
    assert loaded["language"] == "en"


def test_config_migration_replaces_file_atomically(isolated_data_dir, monkeypatch):
    import config

    config_path = isolated_data_dir / "config.json"
    config_path.write_text(
        json.dumps({"config_version": 1, "language": "ja"}),
        encoding="utf-8",
    )
    real_replace = config.os.replace
    replacements = []

    def recording_replace(source, destination):
        replacements.append((source, destination))
        return real_replace(source, destination)

    monkeypatch.setattr(config, "_keychain_available", lambda: False)
    monkeypatch.setattr(config.os, "replace", recording_replace)

    config.load_config()

    assert any(destination == config.CONFIG_FILE for _, destination in replacements)


def test_dictionary_file_writes_are_serialized(isolated_data_dir, monkeypatch):
    import config

    real_replace = config.os.replace
    first_replace_entered = threading.Event()
    release_first_replace = threading.Event()
    counter_lock = threading.Lock()
    active = 0
    max_active = 0
    errors = []

    def slow_replace(source, destination):
        nonlocal active, max_active
        with counter_lock:
            active += 1
            max_active = max(max_active, active)
            is_first = active == 1 and not first_replace_entered.is_set()
        if is_first:
            first_replace_entered.set()
            release_first_replace.wait(timeout=1)
        try:
            return real_replace(source, destination)
        finally:
            with counter_lock:
                active -= 1

    def writer(value):
        try:
            config.save_dictionary({"manual_added": [value]})
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    monkeypatch.setattr(config.os, "replace", slow_replace)
    first = threading.Thread(target=writer, args=("first",))
    second = threading.Thread(target=writer, args=("second",))
    first.start()
    assert first_replace_entered.wait(timeout=1)
    second.start()
    time.sleep(0.05)
    release_first_replace.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert errors == []
    assert max_active == 1


def test_memory_dictionary_mutations_are_serialized(empty_memory, monkeypatch):
    import memory as memory_module

    first_check_entered = threading.Event()
    release_first_check = threading.Event()
    call_lock = threading.Lock()
    check_count = 0

    class DelayedFirstContainsList(list):
        def __contains__(self, value):
            nonlocal check_count
            result = super().__contains__(value)
            with call_lock:
                check_count += 1
                is_first = check_count == 1
            if is_first:
                first_check_entered.set()
                release_first_check.wait(timeout=1)
            return result

    empty_memory.dictionary["manual_added"] = DelayedFirstContainsList()
    monkeypatch.setattr(memory_module, "save_dictionary", lambda _value: True)

    first = threading.Thread(target=empty_memory.add_custom_word, args=("term",))
    second = threading.Thread(target=empty_memory.add_custom_word, args=("term",))
    first.start()
    assert first_check_entered.wait(timeout=1)
    second.start()
    second.join(timeout=0.2)
    release_first_check.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert empty_memory.dictionary["manual_added"] == ["term"]


def test_all_runtime_json_writers_create_owner_only_files(
    isolated_data_dir, tmp_path, monkeypatch
):
    import config

    manifest = isolated_data_dir / "audio_backup_manifest.json"
    monkeypatch.setattr(config, "AUDIO_BACKUP_MANIFEST_FILE", str(manifest))
    audio = tmp_path / "owned.wav"
    audio.write_bytes(b"synthetic")

    config.save_dictionary({"manual_added": ["term"]})
    config.save_history([{"final_text": "synthetic"}])
    config.save_stats({"total_dictations": 1})
    config.save_smart_replace({"@test": "synthetic"})
    config.register_audio_backup(str(audio))

    for path in (
        isolated_data_dir / "dictionary.json",
        isolated_data_dir / "history.json",
        isolated_data_dir / "stats.json",
        isolated_data_dir / "smart_replace.json",
        manifest,
    ):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600, path


def test_history_replace_failure_preserves_last_good_file(
    isolated_data_dir, monkeypatch
):
    import config

    config.save_history([{"final_text": "first"}])
    history_path = isolated_data_dir / "history.json"
    original = history_path.read_bytes()
    monkeypatch.setattr(
        config.os,
        "replace",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("synthetic")),
    )

    with pytest.raises(OSError, match="synthetic"):
        config.save_history([{"final_text": "second"}])

    assert history_path.read_bytes() == original


def test_first_launch_uses_private_atomic_runtime_writers(isolated_data_dir):
    import launcher

    launcher.init_user_data()

    for filename in ("config.json", "dictionary.json", "history.json", "stats.json"):
        path = isolated_data_dir / filename
        assert path.exists()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
