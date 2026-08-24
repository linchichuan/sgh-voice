import plistlib
import json
import stat
import subprocess
from pathlib import Path

from scripts import pipeline_health


def test_pipeline_health_json_write_is_atomic_and_private(tmp_path):
    output = tmp_path / "private" / "health.json"

    pipeline_health.save_json(output, {"status": "ok"})

    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "ok"}
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    assert list(output.parent.glob(".*.tmp")) == []


def test_speed_rtf_uses_only_records_with_audio_duration():
    result = pipeline_health.detect_speed_anomalies(
        [
            {
                "process_time": 2.0,
                "audio_duration": 0,
                "stt_source": "local",
                "llm_source": "regex",
                "timestamp": "2026-08-24T10:00:00",
            },
            {
                "process_time": 4.0,
                "audio_duration": 2.0,
                "stt_source": "local",
                "llm_source": "regex",
                "timestamp": "2026-08-24T10:01:00",
            },
        ]
    )

    stats = result["combo_summary"]["local+regex"]
    assert stats["realtime_factor"] == 2.0
    assert stats["rtf_sample_count"] == 1
    assert stats["rtf_coverage_pct"] == 50.0


def test_speed_rtf_is_unavailable_without_audio_duration():
    result = pipeline_health.detect_speed_anomalies(
        [
            {
                "process_time": 12.0,
                "stt_source": "local",
                "llm_source": "regex",
                "timestamp": "2026-08-24T10:00:00",
            }
        ]
    )

    stats = result["combo_summary"]["local+regex"]
    assert stats["realtime_factor"] is None
    assert stats["rtf_sample_count"] == 0
    assert stats["rtf_coverage_pct"] == 0.0

    report = pipeline_health.generate_report({"speed": result})
    assert "N/A (0/1)" in report
    assert "120.0x" not in report


def test_health_report_never_persists_transcript_previews():
    raw_secret = "synthetic raw patient transcript marker"
    final_secret = raw_secret * 3
    result = pipeline_health.monitor_llm_quality(
        [
            {
                "whisper_raw": raw_secret,
                "final_text": final_secret,
                "llm_source": "synthetic",
                "timestamp": "2026-08-24T10:00:00",
            }
        ]
    )

    serialized = json.dumps(result, ensure_ascii=False)
    report = pipeline_health.generate_report({"llm_quality": result})
    assert raw_secret not in serialized
    assert raw_secret not in report
    assert "raw_preview" not in serialized
    assert "final_preview" not in serialized


def test_pipeline_health_notification_passes_text_as_argv(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs

    monkeypatch.setattr(pipeline_health.subprocess, "run", fake_run)
    title = 'health "title"'
    body = 'bad\\" & do shell script "touch /tmp/should-not-run" & "'

    pipeline_health.notify(title, body)

    argv = captured["argv"]
    assert argv[:2] == ["osascript", "-e"]
    assert argv[-3:] == ["--", title, body]
    assert body not in argv[2]
    assert title not in argv[2]


def test_scheduled_pipeline_health_is_read_only_and_uses_project_venv():
    plist_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launchd"
        / "com.shingihou.pipeline-health.plist"
    )
    with plist_path.open("rb") as handle:
        config = plistlib.load(handle)

    args = config["ProgramArguments"]
    assert args == [
        "/bin/bash",
        "/Users/lin/Library/Application Support/SGHVoice/run_pipeline_health.sh",
        "--quiet",
    ]
    assert "--auto-fix" not in args
    assert "--quiet" in args
    assert "WorkingDirectory" not in config
    assert config["StandardOutPath"].startswith(
        "/Users/lin/Library/Logs/SGHVoice/"
    )
    assert config["StandardErrorPath"].startswith(
        "/Users/lin/Library/Logs/SGHVoice/"
    )
    assert config["Umask"] == 0o77


def test_pipeline_health_launch_wrapper_can_start_the_cli():
    wrapper = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_pipeline_health.sh"
    )

    result = subprocess.run(
        ["/bin/bash", str(wrapper), "--help"],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "SGH Voice" in result.stdout
    assert "umask 077" in wrapper.read_text(encoding="utf-8")
