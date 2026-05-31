"""Tests for transcriber._detect_voice_command — v2.4.0 新版 pause-marker 要求。

關鍵 regression：v2.3 之前 "請問怎麼把『早安』翻成英文" 會被誤判為 translate_en command，
把使用者真正想說的內容當指令切掉。v2.4 加上 pause marker 強制要求。"""
import pytest


def test_voice_command_no_marker_does_not_trigger(mock_transcriber):
    """無明確停頓標記（無「以上/這段」也無 punctuation）→ 不該觸發 translate。"""
    text = "請問怎麼把早安翻成英文"
    stripped, style = mock_transcriber._detect_voice_command(text)
    assert style is None
    assert stripped == text  # 整段保留


def test_voice_command_with_marker_triggers_translate_en(mock_transcriber):
    """有「，以上翻成英文」→ 觸發 translate_en，stripped 是 marker 之前的全文。"""
    text = "請幫我打一封 email 給土方告訴他明天會議改時間，以上翻成英文"
    stripped, style = mock_transcriber._detect_voice_command(text)
    assert style == "translate_en"
    # stripped 應該包含使用者的實質內容，但不含 "以上翻成英文"
    assert "土方" in stripped
    assert "翻成英文" not in stripped


def test_voice_command_formal_style(mock_transcriber):
    """「，前面這段改成正式」→ 觸發 formal style。"""
    text = "我覺得這份提案還可以再調整一下細節，前面這段改成正式"
    stripped, style = mock_transcriber._detect_voice_command(text)
    assert style == "formal"
    assert "提案" in stripped


def test_voice_command_threshold_12_chars_enforced(mock_transcriber):
    """前段文字 < 12 字 → 不觸發（指令誤判保護）。"""
    text = "早安，翻成英文"  # 前段「早安」只有 2 字 < 12
    stripped, style = mock_transcriber._detect_voice_command(text)
    assert style is None


def test_voice_command_disabled_via_config(mock_transcriber):
    """config.enable_voice_commands=False → 永不觸發。"""
    mock_transcriber.config["enable_voice_commands"] = False
    text = "我覺得這份提案還可以再調整一下細節，前面這段改成正式"
    stripped, style = mock_transcriber._detect_voice_command(text)
    assert style is None
    assert stripped == text
