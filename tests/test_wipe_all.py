"""User-visible guarantees for the local data wipe endpoint."""

import threading
import time
import types

import pytest


@pytest.fixture(autouse=True)
def _fresh_runtime_write_lifecycle():
    import config

    config.resume_runtime_data_writes()
    yield
    config.resume_runtime_data_writes()


class _WipeReadyEngine:
    def __init__(self, ready=True):
        self.ready = ready
        self.calls = 0

    def prepare_for_data_wipe(self, timeout=0):
        self.calls += 1
        return self.ready


class _ClearableMemory:
    def __init__(self):
        self.cleared = False

    def clear_all_in_memory(self):
        self.cleared = True


def _wipe(client):
    token_response = client.post("/api/wipe_all/token")
    assert token_response.status_code == 200
    token = token_response.get_json()["token"]
    return client.post(
        "/api/wipe_all",
        json={"token": token, "confirm": "DELETE_ALL_MY_DATA"},
    )


def test_wipe_deletes_only_manifest_owned_audio_in_mixed_backup_directory(
    isolated_data_dir, tmp_path, monkeypatch
):
    import config
    import dashboard

    manifest_file = isolated_data_dir / "audio_backup_manifest.json"
    monkeypatch.setattr(
        config,
        "AUDIO_BACKUP_MANIFEST_FILE",
        str(manifest_file),
        raising=False,
    )
    backup_dir = tmp_path / "mixed-audio"
    backup_dir.mkdir()
    owned = backup_dir / "sgh-owned.wav"
    unrelated = backup_dir / "family-recording.wav"
    owned.write_bytes(b"owned")
    unrelated.write_bytes(b"unrelated")

    config.register_audio_backup(str(owned))
    monkeypatch.setattr(
        dashboard, "load_config", lambda: {"backup_audio_dir": str(backup_dir)}
    )
    engine = _WipeReadyEngine()
    runtime_memory = _ClearableMemory()
    dashboard.set_engine(engine)
    dashboard.set_memory(runtime_memory)
    dashboard._WIPE_TOKEN_STORE.clear()

    response = _wipe(dashboard.app.test_client())

    assert response.status_code == 200
    assert engine.calls == 1
    assert runtime_memory.cleared is True
    assert not owned.exists()
    assert unrelated.exists()
    assert not manifest_file.exists()


def test_voice_engine_blocks_new_recordings_until_active_pipeline_is_quiescent():
    import app

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = threading.RLock()
    engine._data_wipe_in_progress = False
    engine._inflight_transcriptions = 1
    engine._backup_threads = set()
    engine.is_recording = False

    assert engine.prepare_for_data_wipe(timeout=0) is False
    assert engine._data_wipe_in_progress is True
    assert engine.start_recording() is False

    engine._inflight_transcriptions = 0
    assert engine.prepare_for_data_wipe(timeout=0) is True


def test_wipe_removes_corrupt_history_recovery_files(
    isolated_data_dir, monkeypatch
):
    import config
    import dashboard

    manifest_file = isolated_data_dir / "audio_backup_manifest.json"
    monkeypatch.setattr(
        config,
        "AUDIO_BACKUP_MANIFEST_FILE",
        str(manifest_file),
        raising=False,
    )
    corrupt_backup = isolated_data_dir / "history.json.bad.20260824_120000"
    corrupt_backup.write_text("synthetic-corrupt-history", encoding="utf-8")
    dashboard.set_engine(_WipeReadyEngine())
    dashboard.set_memory(_ClearableMemory())
    dashboard._WIPE_TOKEN_STORE.clear()

    response = _wipe(dashboard.app.test_client())

    assert response.status_code == 200
    assert not corrupt_backup.exists()


def test_wipe_removes_app_owned_derived_reports_but_preserves_unrelated_files(
    isolated_data_dir, monkeypatch
):
    import config
    import dashboard

    manifest_file = isolated_data_dir / "audio_backup_manifest.json"
    monkeypatch.setattr(
        config,
        "AUDIO_BACKUP_MANIFEST_FILE",
        str(manifest_file),
        raising=False,
    )
    reports_dir = isolated_data_dir / "reports"
    reports_dir.mkdir()
    health_report = reports_dir / "health_latest.md"
    health_report.write_text("synthetic derived transcript", encoding="utf-8")
    triage_report = isolated_data_dir / "auto_triage_report.md"
    triage_report.write_text("synthetic correction span", encoding="utf-8")
    config_recovery = isolated_data_dir / "config.json.bad.1234"
    config_recovery.write_text("synthetic stale config", encoding="utf-8")
    unrelated_file = isolated_data_dir / "user-notes.txt"
    unrelated_file.write_text("preserve me", encoding="utf-8")
    unrelated_dir = isolated_data_dir / "user-reports"
    unrelated_dir.mkdir()
    (unrelated_dir / "notes.md").write_text("preserve me", encoding="utf-8")

    dashboard.set_engine(_WipeReadyEngine())
    dashboard.set_memory(_ClearableMemory())
    dashboard._WIPE_TOKEN_STORE.clear()

    response = _wipe(dashboard.app.test_client())

    assert response.status_code == 200
    assert not reports_dir.exists()
    assert not triage_report.exists()
    assert not config_recovery.exists()
    assert unrelated_file.exists()
    assert unrelated_dir.exists()


def test_successful_wipe_blocks_late_runtime_writers(
    isolated_data_dir, monkeypatch
):
    import config
    import dashboard
    import event_ledger

    manifest_file = isolated_data_dir / "audio_backup_manifest.json"
    monkeypatch.setattr(
        config,
        "AUDIO_BACKUP_MANIFEST_FILE",
        str(manifest_file),
        raising=False,
    )
    dashboard.set_engine(_WipeReadyEngine())
    dashboard.set_memory(_ClearableMemory())
    dashboard._WIPE_TOKEN_STORE.clear()

    response = _wipe(dashboard.app.test_client())
    try:
        assert response.status_code == 200
        config.save_history([{"final_text": "synthetic late result"}])
        event_ledger.log("late_pipeline_complete", chars_out=21)
        late_audio = isolated_data_dir / "late.wav"
        late_audio.write_bytes(b"synthetic")
        assert config.register_audio_backup(str(late_audio)) is None
        assert not (isolated_data_dir / "history.json").exists()
        assert not (isolated_data_dir / "events.jsonl").exists()
        assert not manifest_file.exists()
    finally:
        config.resume_runtime_data_writes()


def test_voice_engine_registers_each_created_audio_backup(
    isolated_data_dir, tmp_path, monkeypatch
):
    import app
    import config

    manifest_file = isolated_data_dir / "audio_backup_manifest.json"
    monkeypatch.setattr(config, "AUDIO_BACKUP_MANIFEST_FILE", str(manifest_file))
    backup_dir = tmp_path / "mixed-audio"
    backup_dir.mkdir()
    source = tmp_path / "source.wav"
    source.write_bytes(b"synthetic-audio")

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = threading.RLock()
    engine._paste_lock = threading.Lock()
    engine._backup_threads = set()
    engine._data_wipe_in_progress = False
    engine.is_recording = False
    engine.is_processing = False
    engine._processing_start_ts = None
    engine._stopping_recording_token = None
    engine._processing_recording_tokens = []
    engine._active_recording_tokens = set()
    engine._cancelled_recording_tokens = set()
    engine._cancel_inflight = False
    engine._inflight_transcriptions = 0
    engine._on_status_change = None
    engine.overlay = types.SimpleNamespace(
        show=lambda _state: None,
        update_stage=lambda _stage: None,
        show_transcript=lambda *_args, **_kwargs: None,
    )
    engine.transcriber = types.SimpleNamespace(
        transcribe=lambda *_args, **_kwargs: {
            "final": "synthetic result",
            "process_time": 0.01,
        }
    )
    engine.config = {
        "auto_paste": False,
        "enable_transcript_overlay": False,
        "backup_audio_dir": str(backup_dir),
    }
    monkeypatch.setattr(app, "update_stats", lambda *_args, **_kwargs: None)

    engine._transcribe_and_paste(
        None, str(source), 1.0, "dictate", "", recording_token=None
    )
    deadline = time.monotonic() + 2
    while not list(backup_dir.glob("*.wav")) and time.monotonic() < deadline:
        time.sleep(0.01)
    backups = list(backup_dir.glob("*.wav"))
    assert len(backups) == 1

    deleted, failed = config.delete_registered_audio_backups()
    assert failed == []
    assert deleted == [str(backups[0].resolve())]
    assert not backups[0].exists()
