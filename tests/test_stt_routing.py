"""STT primary/fallback routing tests; all providers are mocked."""

import numpy as np


def _prepare(monkeypatch, transcriber, **overrides):
    import transcriber as tr_mod

    transcriber.config.update({
        "enable_audio_gate": False,
        "enable_claude_polish": False,
        "groq_api_key": "",
        "openai_api_key": "",
        "hybrid_audio_threshold": 15,
        **overrides,
    })
    monkeypatch.setattr(tr_mod, "detect_app_style", lambda config: {
        "bundle_id": "", "app_name": "", "style": "default", "prompt": "",
    })


def test_local_primary_stays_local_when_hybrid_is_off(mock_transcriber, monkeypatch):
    _prepare(
        monkeypatch,
        mock_transcriber,
        stt_engine="mlx-whisper",
        enable_hybrid_mode=False,
        groq_api_key="test-only",
    )
    calls = []
    monkeypatch.setattr(
        mock_transcriber, "_local_stt",
        lambda source: calls.append("local") or {"text": "這是本地辨識結果", "language": "zh"},
    )
    monkeypatch.setattr(
        mock_transcriber, "_groq_stt",
        lambda *args, **kwargs: calls.append("groq") or {"text": "不應使用", "language": "zh"},
    )

    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 45.0, "dictate", "", None,
    )

    assert result["final"] == "這是本地辨識結果"
    assert calls == ["local"]
    assert mock_transcriber.memory.history[-1]["stt_source"] == "local"


def test_hybrid_threshold_routes_long_local_profile_to_cloud_first(mock_transcriber, monkeypatch):
    _prepare(
        monkeypatch,
        mock_transcriber,
        stt_engine="mlx-whisper",
        enable_hybrid_mode=True,
        groq_api_key="test-only",
    )
    calls = []
    monkeypatch.setattr(
        mock_transcriber, "_groq_stt",
        lambda *args, **kwargs: calls.append("groq") or {"text": "長音訊雲端結果", "language": "zh"},
    )
    monkeypatch.setattr(
        mock_transcriber, "_local_stt",
        lambda source: calls.append("local") or {"text": "不應使用", "language": "zh"},
    )

    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 20.0, "dictate", "", None,
    )

    assert result["final"] == "長音訊雲端結果"
    assert calls == ["groq"]
    assert mock_transcriber.memory.history[-1]["stt_source"] == "groq"


def test_hybrid_long_clip_falls_back_to_local_without_cloud(mock_transcriber, monkeypatch):
    _prepare(
        monkeypatch,
        mock_transcriber,
        stt_engine="mlx-whisper",
        enable_hybrid_mode=True,
    )
    calls = []
    monkeypatch.setattr(
        mock_transcriber, "_local_stt",
        lambda source: calls.append("local") or {"text": "離線備援結果", "language": "zh"},
    )

    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 20.0, "dictate", "", None,
    )

    assert result["final"] == "離線備援結果"
    assert calls == ["local"]


def test_groq_primary_does_not_get_overridden_by_local(mock_transcriber, monkeypatch):
    _prepare(
        monkeypatch,
        mock_transcriber,
        stt_engine="groq",
        enable_hybrid_mode=True,
        groq_api_key="test-only",
    )
    calls = []
    monkeypatch.setattr(
        mock_transcriber, "_groq_stt",
        lambda *args, **kwargs: calls.append("groq") or {"text": "Groq 多語辨識結果", "language": "ja"},
    )
    monkeypatch.setattr(
        mock_transcriber, "_local_stt",
        lambda source: calls.append("local") or {"text": "不應使用", "language": "zh"},
    )

    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 5.0, "dictate", "", None,
    )

    assert result["final"] == "Groq 多語辨識結果"
    assert calls == ["groq"]


def test_cloud_only_uses_openai_before_groq_fallback(mock_transcriber, monkeypatch):
    _prepare(
        monkeypatch,
        mock_transcriber,
        stt_engine="cloud-only",
        enable_hybrid_mode=True,
        openai_api_key="test-only",
        groq_api_key="test-only",
    )
    calls = []
    monkeypatch.setattr(
        mock_transcriber, "_whisper_api_fallback",
        lambda *args, **kwargs: calls.append("openai") or {"text": "OpenAI 結果", "language": "zh"},
    )
    monkeypatch.setattr(
        mock_transcriber, "_groq_stt",
        lambda *args, **kwargs: calls.append("groq") or {"text": "不應使用", "language": "zh"},
    )

    result = mock_transcriber._transcribe_impl(
        np.ones(16000, dtype=np.float32), 5.0, "dictate", "", None,
    )

    assert result["final"] == "OpenAI 結果"
    assert calls == ["openai"]
    assert mock_transcriber.memory.history[-1]["stt_source"] == "cloud"
