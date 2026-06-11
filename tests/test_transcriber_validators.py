"""Tests for transcriber.py validator helpers: _should_skip_llm, _sanitize_repetition,
_is_llm_hallucination."""
import numpy as np
import pytest


# ───── _should_skip_llm ─────────────────────────────────────

def test_should_skip_llm_empty_string(mock_transcriber):
    assert mock_transcriber._should_skip_llm("") is True


def test_should_skip_llm_whitespace_only(mock_transcriber):
    assert mock_transcriber._should_skip_llm("   \n  ") is True


def test_should_skip_llm_short_clean_text(mock_transcriber):
    """≤ 20 字 + 沒填充詞 → skip。"""
    assert mock_transcriber._should_skip_llm("Hello world.") is True


def test_should_skip_llm_typical_dictation(mock_transcriber):
    """40 字一般敘述 + 有填充詞 → 應該跑 LLM (不 skip)。"""
    txt = "嗯，今天我去了會議室開會然後跟客戶討論了很多細節對。"
    assert mock_transcriber._should_skip_llm(txt) is False


def test_should_skip_llm_long_text_with_fillers(mock_transcriber):
    """長文字 + 有填充詞 → 不 skip。"""
    txt = "那個我覺得這個專案應該要 um 重新評估一下整體的方向" * 2
    assert mock_transcriber._should_skip_llm(txt) is False


# ───── _sanitize_repetition ─────────────────────────────────

def test_sanitize_repetition_truncates_5x_repeat(mock_transcriber):
    """Whisper 幻覺常見：同字重複 ≥5 次該被截斷。"""
    bad = "今天天氣很好" + "啊啊啊" * 10  # "啊啊啊啊啊啊..." 重複多次
    cleaned = mock_transcriber._sanitize_repetition(bad)
    # 結果應該明顯短於輸入
    assert len(cleaned) < len(bad)


def test_sanitize_repetition_preserves_normal_text(mock_transcriber):
    """正常無重複文字應原樣返回。"""
    normal = "今天去開會討論了很多事情，明天還要繼續處理後續細節。"
    cleaned = mock_transcriber._sanitize_repetition(normal)
    assert cleaned == normal


def test_sanitize_repetition_short_text_passthrough(mock_transcriber):
    """< 20 字一律不處理（保護正常短句）。"""
    short = "好好好好好"
    assert mock_transcriber._sanitize_repetition(short) == short


# ───── _is_llm_hallucination ────────────────────────────────

def test_is_llm_hallucination_flags_cannot_prefix(mock_transcriber):
    """"I cannot..." / "I don't..." 起手 → 視為幻覺。"""
    raw = "幫我把這段話翻成英文"
    bad = "I cannot help with that request because of policy."
    assert mock_transcriber._is_llm_hallucination(bad, raw) is True


def test_is_llm_hallucination_flags_excessive_expansion(mock_transcriber):
    """LLM 把短輸入擴寫 >2.5 倍 → 幻覺。"""
    raw = "今天天氣不錯我去散步了"  # ~12 字
    bad = "您好，根據您今天提供的資訊，我為您整理了一篇完整的散步心得日記，內容包含天氣狀況、路線規劃、心情感受等多個層面的詳盡描述。"
    assert mock_transcriber._is_llm_hallucination(bad, raw) is True


def test_is_llm_hallucination_passes_clean_output(mock_transcriber):
    """LLM 輸出 = raw + 標點 → 不是幻覺。"""
    raw = "今天去開會討論了很多事情明天還要繼續處理"
    good = "今天去開會，討論了很多事情，明天還要繼續處理。"
    assert mock_transcriber._is_llm_hallucination(good, raw) is False


def test_transcribe_prefers_wav_path_and_releases_audio_array(mock_transcriber, monkeypatch, tmp_path):
    """一般錄音同時有 ndarray + wav 時，STT 應讀 wav，並在品質檢查後釋放 ndarray 參考。"""
    import transcriber as tr_mod

    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"fake wav")
    audio = np.ones(16000, dtype=np.float32)
    source = {"array": audio, "path": str(wav_path)}
    seen = {}

    mock_transcriber.config.update({
        "enable_audio_gate": False,
        "enable_hybrid_mode": True,
        "stt_engine": "mlx-whisper",
        "enable_claude_polish": False,
    })
    monkeypatch.setattr(tr_mod, "detect_app_style", lambda config: {
        "bundle_id": "",
        "app_name": "",
        "style": "default",
        "prompt": "",
    })

    def fake_local_stt(audio_input):
        seen["audio_input"] = audio_input
        return "測試內容"

    monkeypatch.setattr(mock_transcriber, "_local_stt", fake_local_stt)
    result = mock_transcriber._transcribe_impl(source, 1.0, "dictate", "", None)

    assert seen["audio_input"] == str(wav_path)
    assert source["array"] is None
    assert result["final"] == "測試內容"
