import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_style_profile_generation_is_local_and_never_echoes_samples():
    module = importlib.import_module("scripts.update_style_profile")
    secret = "SyntheticPatientNameZXQ 的 API integration 要在明天完成。"

    profile = module.generate_local_style_profile([secret] * 10)

    assert profile
    assert secret not in profile
    assert "SyntheticPatientNameZXQ" not in profile


def test_style_profile_script_has_no_cloud_provider_clients():
    script = (ROOT / "scripts" / "update_style_profile.py").read_text(
        encoding="utf-8"
    ).lower()

    for forbidden in (
        "import openai",
        "import anthropic",
        "api.groq.com",
        "openrouter.ai",
        "_call_llm",
    ):
        assert forbidden not in script


def test_runtime_logs_do_not_emit_transcript_content_slices():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    for forbidden in (
        "final[:80]",
        "cache['raw'][:30]",
        "final[:60]",
        "selected[:40]",
    ):
        assert forbidden not in app_source
