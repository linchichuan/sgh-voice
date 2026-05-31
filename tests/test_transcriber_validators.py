"""Tests for transcriber.py validator helpers: _should_skip_llm, _sanitize_repetition,
_is_llm_hallucination."""
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
