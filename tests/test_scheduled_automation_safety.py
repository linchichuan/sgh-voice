import importlib.util
import json
import plistlib
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHD_DIR = ROOT / "scripts" / "launchd"
INSTALLED_RUNNER = (
    "/Users/lin/Library/Application Support/SGHVoice/run_scheduled_task.sh"
)


def _load_script_module(filename: str):
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_dictionary_update_notification_passes_text_as_argv(monkeypatch):
    module = _load_script_module("dict-update.py")
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    title = 'dictionary "title"'
    body = 'bad\\" & do shell script "touch /tmp/should-not-run" & "'

    module.notify(title, body)

    argv = captured["argv"]
    assert argv[:2] == ["osascript", "-e"]
    assert argv[-3:] == ["--", title, body]
    assert body not in argv[2]
    assert title not in argv[2]


def test_dictionary_update_write_is_atomic_and_private(tmp_path, monkeypatch):
    module = _load_script_module("dict-update.py")
    dictionary_path = tmp_path / "private" / "dictionary.json"
    monkeypatch.setattr(module, "DATA_DIR", dictionary_path.parent)
    monkeypatch.setattr(module, "DICT_FILE", dictionary_path)

    module.save_dictionary({"auto_added": ["合成測試詞"]})

    assert json.loads(dictionary_path.read_text(encoding="utf-8")) == {
        "auto_added": ["合成測試詞"]
    }
    assert stat.S_IMODE(dictionary_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(dictionary_path.parent.stat().st_mode) == 0o700
    assert list(dictionary_path.parent.glob(".*.tmp")) == []


def test_scheduled_dictionary_jobs_are_review_only():
    expectations = {
        "com.shingihou.dict-update.plist": "dict-update",
        "com.shingihou.promote-corrections.plist": "promote-corrections",
    }

    for filename, task in expectations.items():
        with (LAUNCHD_DIR / filename).open("rb") as handle:
            config = plistlib.load(handle)
        args = config["ProgramArguments"]
        assert args == ["/bin/bash", INSTALLED_RUNNER, task]
        assert "--apply" not in args
        assert config["Umask"] == 0o077
        assert config["StandardOutPath"].startswith(
            "/Users/lin/Library/Logs/SGHVoice/"
        )
        assert config["StandardErrorPath"].startswith(
            "/Users/lin/Library/Logs/SGHVoice/"
        )


def test_all_scheduled_task_runner_targets_exist():
    runner = ROOT / "scripts" / "run_scheduled_task.sh"
    for task in [
        "dict-update",
        "promote-corrections",
        "maintenance-loop",
        "hf-watch",
    ]:
        result = subprocess.run(
            ["/bin/bash", str(runner), task, "--self-test"],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"{task}: {result.stderr}"


def test_hf_watcher_does_not_interpolate_external_text_into_applescript():
    script = (ROOT / "scripts" / "hf-model-watch.sh").read_text(encoding="utf-8")

    assert 'osascript -e "display notification' not in script
    assert 'osascript -e "$NOTIFY_SCRIPT" -- "$TITLE" "$BODY"' in script
