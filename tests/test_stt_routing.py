"""STT primary/fallback routing tests; all providers are mocked."""

from types import SimpleNamespace

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


# ─── Qwen3-ASR (mlx-audio) engine routing — v2.7.0 ──────────────────────────

def test_local_stt_dispatches_to_qwen3_when_selected(mock_transcriber, monkeypatch):
    """local_whisper_model == 'qwen3-asr' must route to the mlx-audio call path,
    not the mlx_whisper one."""
    mock_transcriber.config["local_whisper_model"] = "qwen3-asr"
    calls = []
    monkeypatch.setattr(
        mock_transcriber, "_local_stt_qwen3",
        lambda source: calls.append("qwen3") or {"text": "qwen3 結果", "language": "zh"},
    )
    monkeypatch.setattr(
        mock_transcriber, "_local_stt_whisper",
        lambda source, **kw: calls.append("whisper") or {"text": "不應使用", "language": "zh"},
    )

    result = mock_transcriber._local_stt(np.ones(1600, dtype=np.float32))

    assert calls == ["qwen3"]
    assert result == {"text": "qwen3 結果", "language": "zh"}


def test_local_stt_still_uses_whisper_path_for_non_qwen3_models(mock_transcriber, monkeypatch):
    """Sanity check the dispatcher doesn't regress the existing whisper-turbo /
    Breeze routes — same behavior as before this feature landed."""
    mock_transcriber.config["local_whisper_model"] = "whisper-turbo"
    calls = []
    monkeypatch.setattr(
        mock_transcriber, "_local_stt_qwen3",
        lambda source: calls.append("qwen3") or {"text": "不應使用", "language": "zh"},
    )
    monkeypatch.setattr(
        mock_transcriber, "_local_stt_whisper",
        lambda source, **kw: calls.append("whisper") or {"text": "whisper 結果", "language": "zh"},
    )

    result = mock_transcriber._local_stt(np.ones(1600, dtype=np.float32))

    assert calls == ["whisper"]
    assert result == {"text": "whisper 結果", "language": "zh"}


def test_qwen3_asr_falls_back_to_whisper_turbo_when_model_not_downloaded(mock_transcriber, monkeypatch):
    """Fail-safe: model selected but never downloaded via Dashboard -> must fall
    back to whisper-turbo specifically (not silently trigger a multi-GB blocking
    download, not just return None and let dictation fail)."""
    monkeypatch.setattr(mock_transcriber, "_qwen3_asr_downloaded", lambda repo: False)
    fallback_calls = []
    monkeypatch.setattr(
        mock_transcriber, "_local_stt_whisper",
        lambda source, **kw: fallback_calls.append(kw) or {"text": "turbo 備援", "language": "zh"},
    )

    result = mock_transcriber._local_stt_qwen3(np.ones(1600, dtype=np.float32))

    assert result == {"text": "turbo 備援", "language": "zh"}
    assert fallback_calls == [{"model_name_override": "whisper-turbo"}]


def test_qwen3_asr_falls_back_to_whisper_turbo_when_mlx_audio_load_fails(mock_transcriber, monkeypatch):
    """Fail-safe: mlx-audio not installed / weight load raises -> same
    whisper-turbo fallback, never a hard pipeline failure."""
    monkeypatch.setattr(mock_transcriber, "_qwen3_asr_downloaded", lambda repo: True)

    def _boom(repo_id):
        raise ImportError("mlx_audio not installed")
    monkeypatch.setattr(mock_transcriber, "_load_qwen3_asr_model", _boom)

    fallback_calls = []
    monkeypatch.setattr(
        mock_transcriber, "_local_stt_whisper",
        lambda source, **kw: fallback_calls.append(kw) or {"text": "turbo 備援", "language": "zh"},
    )

    result = mock_transcriber._local_stt_qwen3(np.ones(1600, dtype=np.float32))

    assert result == {"text": "turbo 備援", "language": "zh"}
    assert fallback_calls == [{"model_name_override": "whisper-turbo"}]


def test_qwen3_asr_falls_back_to_whisper_turbo_when_generate_raises(mock_transcriber, monkeypatch):
    """Fail-safe: model loads fine but generate() throws mid-inference -> still
    degrade to whisper-turbo instead of losing the dictation entirely."""
    monkeypatch.setattr(mock_transcriber, "_qwen3_asr_downloaded", lambda repo: True)
    broken_model = SimpleNamespace(generate=lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("oom")))
    monkeypatch.setattr(mock_transcriber, "_load_qwen3_asr_model", lambda repo_id: broken_model)

    fallback_calls = []
    monkeypatch.setattr(
        mock_transcriber, "_local_stt_whisper",
        lambda source, **kw: fallback_calls.append(kw) or {"text": "turbo 備援", "language": "zh"},
    )

    result = mock_transcriber._local_stt_qwen3(np.ones(1600, dtype=np.float32))

    assert result == {"text": "turbo 備援", "language": "zh"}
    assert fallback_calls == [{"model_name_override": "whisper-turbo"}]


def test_qwen3_asr_happy_path_passes_system_prompt_and_mapped_language(mock_transcriber, monkeypatch):
    """When the model is downloaded and inference succeeds: generate() gets the
    same _build_stt_prompt() vocabulary/scene string Whisper's initial_prompt
    uses (real equivalent, not a dropped feature), and language is mapped from
    the config's ISO code to Qwen3-ASR's full language name."""
    monkeypatch.setattr(mock_transcriber, "_qwen3_asr_downloaded", lambda repo: True)
    monkeypatch.setattr(mock_transcriber, "_build_stt_prompt", lambda: "相關詞彙：Shingihou、Twilio")
    mock_transcriber.config["language"] = "zh"

    seen = {}
    def _fake_generate(audio_source, **kwargs):
        seen["audio_source"] = audio_source
        seen["kwargs"] = kwargs
        return SimpleNamespace(text="你好，這是測試", language="zh")
    fake_model = SimpleNamespace(generate=_fake_generate)
    monkeypatch.setattr(mock_transcriber, "_load_qwen3_asr_model", lambda repo_id: fake_model)

    audio = np.ones(1600, dtype=np.float32)
    result = mock_transcriber._local_stt_qwen3(audio)

    assert result["text"] == "你好，這是測試"  # < 20 字，_sanitize_repetition 直接放行
    assert result["language"] == "zh"
    assert seen["audio_source"] is audio
    assert seen["kwargs"]["system_prompt"] == "相關詞彙：Shingihou、Twilio"
    assert seen["kwargs"]["language"] == "chinese"


def test_qwen3_asr_normalizes_list_shaped_language_from_real_mlx_audio_output(mock_transcriber, monkeypatch):
    """Regression test for a real bug caught by the product-code smoke test (see
    mlx_audio's Qwen3-ASR
    STTOutput.language came back as ['Chinese'] (a list of a full language name),
    not the plain 'zh' mlx_whisper returns. Without normalization this leaked a
    Python list repr ("['chinese']") into _get_system_prompt()'s language hint."""
    monkeypatch.setattr(mock_transcriber, "_qwen3_asr_downloaded", lambda repo: True)
    monkeypatch.setattr(mock_transcriber, "_build_stt_prompt", lambda: "")
    fake_model = SimpleNamespace(
        generate=lambda audio_source, **kw: SimpleNamespace(text="你好", language=["Chinese"]),
    )
    monkeypatch.setattr(mock_transcriber, "_load_qwen3_asr_model", lambda repo_id: fake_model)

    result = mock_transcriber._local_stt_qwen3(np.ones(1600, dtype=np.float32))

    assert result["language"] == "zh"  # mapped back to the same ISO code mlx_whisper uses
    # Downstream _get_system_prompt() does str(language_hint or "").strip().lower() —
    # must never see the raw list.
    assert not isinstance(result["language"], (list, tuple))


def test_normalize_qwen3_language_handles_unknown_and_empty_values(mock_transcriber):
    assert mock_transcriber._normalize_qwen3_language(["Japanese"]) == "ja"
    assert mock_transcriber._normalize_qwen3_language("English") == "en"
    assert mock_transcriber._normalize_qwen3_language(None) is None
    assert mock_transcriber._normalize_qwen3_language([]) is None
    assert mock_transcriber._normalize_qwen3_language("Klingon") == "klingon"  # unknown: lowercased, not dropped
