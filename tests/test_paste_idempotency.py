"""Paste idempotency: 每個 recording_token（一段語音的轉錄結果）最多只准
消費一次 paste_text()。

設計原則（見 app.py:_consume_paste_token 的 docstring）：
- utterance/segment token 只消費一次 —— 重用既有的 recording_token（PTT cancel
  token 同一條流，見 app.py:765 / app.py:1151）。
- 嚴禁 content-based 時間窗 dedup：同樣文字、不同 recording_token 的兩次呼叫
  必須都成功貼上（使用者合法的重複口述不可被吃掉）。
"""
import threading
import types

import pytest


def _build_engine(monkeypatch, paste_calls, final_text="hello world"):
    """建立一個最小可跑 _transcribe_and_paste 的 VoiceEngine stub。

    audio_array/filepath 都是 None，跳過 recorder/backup 相關 IO；
    transcriber.transcribe 固定回傳 final_text，聚焦在 paste idempotency 本身。
    """
    import app

    def fake_paste_text(text):
        paste_calls.append(text)
        return True

    monkeypatch.setattr(app, "paste_text", fake_paste_text)
    monkeypatch.setattr(app, "update_stats", lambda *a, **k: None)

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = threading.RLock()
    engine._paste_lock = threading.Lock()
    engine._active_recording_tokens = set()
    engine._cancelled_recording_tokens = set()
    engine._pasted_recording_tokens = set()
    engine._recording_context_by_token = {}
    engine._stopping_recording_token = None
    engine._processing_recording_tokens = []
    engine._inflight_transcriptions = 0
    engine.is_processing = False
    engine.is_recording = False
    engine._processing_start_ts = None
    engine._data_wipe_in_progress = False
    engine._cancel_inflight = False
    engine._on_status_change = None
    engine.config = {"auto_paste": True, "enable_transcript_overlay": False}
    engine.overlay = types.SimpleNamespace(
        show=lambda *a, **k: None,
        update_stage=lambda *a, **k: None,
        show_transcript=lambda *a, **k: None,
    )
    engine.transcriber = types.SimpleNamespace(
        transcribe=lambda *a, **k: {"final": final_text, "process_time": 0.01}
    )
    return engine


def test_consume_paste_token_blocks_second_call_same_token():
    """單元層級：同一 recording_token 第二次 consume 必須被擋。"""
    import app

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = threading.RLock()
    engine._pasted_recording_tokens = set()

    assert engine._consume_paste_token(123.0) is True
    assert engine._consume_paste_token(123.0) is False
    # 不同 token 不受影響
    assert engine._consume_paste_token(124.0) is True


def test_consume_paste_token_none_always_allowed():
    """None token（Retry / Quick-Rewrite 等非錄音分段路徑）不受保護，永遠放行。"""
    import app

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = threading.RLock()
    engine._pasted_recording_tokens = set()

    assert engine._consume_paste_token(None) is True
    assert engine._consume_paste_token(None) is True


def test_same_token_second_paste_is_skipped(monkeypatch, isolated_data_dir):
    """同一 recording_token 呼叫 _transcribe_and_paste 兩次（模擬重試/重複事件），
    第二次必須被擋下，paste_text 只執行一次。"""
    paste_calls = []
    engine = _build_engine(monkeypatch, paste_calls, final_text="早安，今天天氣很好")
    token = 1000.0

    engine._transcribe_and_paste(None, None, 1.5, "dictate", "", token, None)
    engine._transcribe_and_paste(None, None, 1.5, "dictate", "", token, None)

    assert paste_calls == ["早安，今天天氣很好"]
    assert engine._pasted_recording_tokens == {token}


def test_different_tokens_same_text_both_paste(monkeypatch, isolated_data_dir):
    """不同 recording_token、完全相同的文字（使用者合法重複口述）——
    兩次都必須成功貼上，證明沒有 content-based 時間窗 dedup。"""
    paste_calls = []
    engine = _build_engine(monkeypatch, paste_calls, final_text="收到，謝謝")

    engine._transcribe_and_paste(None, None, 1.0, "dictate", "", 2000.0, None)
    engine._transcribe_and_paste(None, None, 1.0, "dictate", "", 2001.0, None)

    assert paste_calls == ["收到，謝謝", "收到，謝謝"]
    assert engine._pasted_recording_tokens == {2000.0, 2001.0}
