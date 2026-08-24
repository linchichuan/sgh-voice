import json
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "auto_triage.py"


def test_scheduled_triage_has_no_cloud_provider_path():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "api_key" not in source
    assert "openai" not in source.lower()
    assert "anthropic" not in source.lower()
    assert "requests.post" not in source
    assert "deterministic" in source.lower()


def test_local_triage_reports_only_changed_spans_and_uses_private_file(
    tmp_path, monkeypatch
):
    from scripts import auto_triage

    history_path = tmp_path / "history.json"
    report_path = tmp_path / "auto_triage_report.md"
    history_path.write_text(
        json.dumps(
            [
                {
                    "edited": True,
                    "whisper_raw": "今天要用 cloud code 完成部署",
                    "final_text": "今天要用 Claude Code 完成部署",
                },
                {
                    "edited": False,
                    "whisper_raw": "private unchanged context",
                    "final_text": "private unchanged context",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(auto_triage, "HISTORY_FILE", str(history_path))
    monkeypatch.setattr(auto_triage, "REPORT_FILE", str(report_path))

    result = auto_triage.analyze_history()

    assert result["edited_records"] == 1
    report = report_path.read_text(encoding="utf-8")
    assert "Claude" in report
    assert "private unchanged context" not in report
    assert "今天要用" not in report
    assert stat.S_IMODE(report_path.stat().st_mode) == 0o600


def test_maintenance_does_not_copy_triage_contents_into_project_status():
    source = (ROOT / "scripts" / "maintenance_loop.sh").read_text(
        encoding="utf-8"
    )

    assert 'cat ~/.voice-input/auto_triage_report.md' not in source
    assert "umask 077" in source


def test_triage_cli_runs_from_outside_the_repository(tmp_path):
    history_path = tmp_path / "history.json"
    report_path = tmp_path / "report.md"
    history_path.write_text("[]", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--history",
            str(history_path),
            "--report",
            str(report_path),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert report_path.exists()
