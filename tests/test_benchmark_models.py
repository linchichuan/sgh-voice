"""benchmark_models.py 的語言 profile 單元測試。"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import benchmark_models


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("zh_01.wav", "zh"),
        ("JA_customer.m4a", "ja"),
        ("en_meeting.mp3", "en"),
        ("mixed_zhen_01.wav", "auto"),
        ("mix_jaen_01.wav", "auto"),
        ("medical_01.wav", "auto"),
    ],
)
def test_language_for_audio_infers_from_filename(filename, expected):
    assert benchmark_models.language_for_audio(filename) == expected


@pytest.mark.parametrize("override", ["zh", "ja", "en"])
def test_language_for_audio_explicit_override_wins(override):
    assert benchmark_models.language_for_audio("mixed_01.wav", override) == override


def test_code_switch_quality_metrics_detect_script_and_term_loss():
    reference = "來週 SEO と API v2.5.4 を確認，費用 ¥1,200"
    perfect = "來週 SEO と API v2.5.4 を確認，費用 ¥1,200。"
    damaged = "來週搜尋最佳化確認，費用 1,300。"

    assert benchmark_models.script_preservation_rate(reference, perfect) == 1.0
    assert benchmark_models.protected_term_recall(reference, perfect) == 1.0
    assert benchmark_models.script_preservation_rate(reference, damaged) < 1.0
    assert benchmark_models.protected_term_recall(reference, damaged) < 0.5


def test_transcribe_auto_omits_language_argument(monkeypatch):
    captured = {}

    def fake_transcribe(audio_path, **kwargs):
        captured.update({"audio_path": audio_path, **kwargs})
        return {"text": "test"}

    monkeypatch.setitem(
        sys.modules,
        "mlx_whisper",
        SimpleNamespace(transcribe=fake_transcribe),
    )

    text, _ = benchmark_models.transcribe_with_model(
        "mixed_01.wav",
        "mlx-community/whisper-turbo",
        language="auto",
    )

    assert text == "test"
    assert "language" not in captured


def test_transcribe_explicit_language_is_forwarded(monkeypatch):
    captured = {}

    def fake_transcribe(audio_path, **kwargs):
        captured.update(kwargs)
        return {"text": "テスト"}

    monkeypatch.setitem(
        sys.modules,
        "mlx_whisper",
        SimpleNamespace(transcribe=fake_transcribe),
    )

    benchmark_models.transcribe_with_model(
        "ja_01.wav",
        "mlx-community/whisper-turbo",
        language="ja",
    )

    assert captured["language"] == "ja"


def test_run_benchmark_uses_per_file_language_and_reports_it(tmp_path, monkeypatch):
    audio_dir = tmp_path / "audio"
    ground_truth_dir = tmp_path / "ground_truth"
    results_dir = tmp_path / "results"
    audio_dir.mkdir()
    ground_truth_dir.mkdir()

    for stem in ("zh_01", "ja_01", "en_01", "mixed_01", "unknown_01"):
        (audio_dir / f"{stem}.wav").touch()
        (ground_truth_dir / f"{stem}.txt").write_text(stem, encoding="utf-8")

    calls = []

    def fake_transcribe(audio_path, model_name, language="auto"):
        calls.append((Path(audio_path).name, model_name, language))
        return Path(audio_path).stem, 0.01

    monkeypatch.setattr(benchmark_models, "AUDIO_DIR", audio_dir)
    monkeypatch.setattr(benchmark_models, "GROUND_TRUTH_DIR", ground_truth_dir)
    monkeypatch.setattr(benchmark_models, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(benchmark_models, "transcribe_with_model", fake_transcribe)

    report = benchmark_models.run_benchmark(["fake-model"])

    profiles = {filename: language for filename, _, language in calls}
    assert profiles == {
        "en_01.wav": "en",
        "ja_01.wav": "ja",
        "mixed_01.wav": "auto",
        "unknown_01.wav": "auto",
        "zh_01.wav": "zh",
    }
    assert "| 語言 profile |" in report
    assert "Script 保留率" in report
    assert "術語保留率" in report
    assert "| ja_01.wav | ja | fake-model |" in report
    assert "| mixed_01.wav | auto | fake-model |" in report


def test_main_passes_cli_language_override(monkeypatch):
    captured = {}

    def fake_run_benchmark(models, language="auto"):
        captured["models"] = models
        captured["language"] = language
        return ""

    monkeypatch.setattr(benchmark_models, "run_benchmark", fake_run_benchmark)
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark_models.py", "--models", "model-a,model-b", "--language", "en"],
    )

    benchmark_models.main()

    assert captured == {"models": ["model-a", "model-b"], "language": "en"}
