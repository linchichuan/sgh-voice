"""PTT 靜音自停後的「及時 finalize」測試。

背景：recorder.py 的 `_record_loop` 在 push_to_talk 模式下偵測到連續靜音達
``ptt_silence_autostop_seconds``（預設 120s）門檻時會自己 break 迴圈、存檔，
並（如果 app.py 有註冊 on_done）透過 `self._on_done(filepath, duration)` 同步
回呼（recorder.py:203-207）。這組測試涵蓋 app.py 這一端接住 on_done 之後的
`VoiceEngine._on_recorder_autostop`：

1. 自停後立刻 finalize（不必等 30 分鐘的 max_recording_duration watchdog）
2. 「自停後使用者才放鍵」與「watchdog 同時到期」兩種競態下都只 finalize 一次
3. 已取消（Cancel hotkey）的錄音不會被安全網誤送

單一 finalizer 的核心防線是 `is_recording` / `_record_start_ts` 在 `_state_lock`
下的原子判定（誰先宣稱擁有這個 token，另一方就直接 return）；`_consume_paste_token`
／`_pasted_recording_tokens`（app.py:1055-1069）與 `_cancelled_recording_tokens`
則是第二層防禦縱深，就算第一層被繞過，使用者也不會看到第二次自動貼上。
"""
import os
import threading
import types

import pytest


class _ImmediateThread:
    """threading.Thread 的同步替身：.start() 直接原地執行 target，讓測試不用
    等待/join 背景 thread 就能斷言最終狀態。沿用 tests/test_hotkey_config.py
    / tests/test_continuous_mode.py 既有的同款 fake pattern。"""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **_):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)

    def is_alive(self):
        return False

    def join(self, timeout=None):
        return None


def _build_engine(
    monkeypatch,
    paste_calls,
    final_text="hello world",
    notify_calls=None,
    ledger_calls=None,
):
    """最小可跑 _on_recorder_autostop / stop_and_process / _transcribe_and_paste
    的 VoiceEngine stub。沿用 tests/test_paste_idempotency.py 的建構風格。"""
    import app

    monkeypatch.setattr(app, "paste_text", lambda text: paste_calls.append(text) or True)
    monkeypatch.setattr(app, "update_stats", lambda *a, **k: None)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)
    if notify_calls is not None:
        monkeypatch.setattr(
            app, "notify", lambda title, message: notify_calls.append((title, message))
        )
    if ledger_calls is not None:
        monkeypatch.setattr(
            app.event_ledger,
            "user_action",
            lambda action, phase, **extra: ledger_calls.append((action, phase, extra)),
        )

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = threading.RLock()
    engine._recorder_transition_lock = threading.RLock()
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
    engine._record_start_ts = None
    engine._processing_start_ts = None
    engine._data_wipe_in_progress = False
    engine._cancel_inflight = False
    engine._continuous_active = False
    engine._watchdog_timer = None
    engine._on_hotkey_reset = None
    engine._on_status_change = None
    engine._backup_threads = set()
    engine.config = {
        "auto_paste": True,
        "enable_transcript_overlay": False,
        "backup_audio_dir": "",
    }
    engine.overlay = types.SimpleNamespace(
        show=lambda *a, **k: None,
        update_stage=lambda *a, **k: None,
        show_transcript=lambda *a, **k: None,
    )
    engine.transcriber = types.SimpleNamespace(
        transcribe=lambda *a, **k: {"final": final_text, "process_time": 0.01}
    )
    return engine


def _touch(tmp_path, name):
    fp = tmp_path / name
    fp.write_bytes(b"RIFF")
    return str(fp)


# ── 1. 連線：start_recording() 有幫 PTT 錄音註冊 on_done ───────────────


def test_start_recording_wires_on_done_for_autostop(monkeypatch):
    """start_recording() 呼叫 recorder.start() 時必須帶上 on_done——沒有這條
    連線，recorder 自己 break 迴圈時就沒有人接手 finalize（回到修復前的
    「等 30 分鐘 watchdog」狀態），這是本次任務要補的最後一段線。"""
    import app

    paste_calls = []
    engine = _build_engine(monkeypatch, paste_calls)
    engine._arm_watchdog = lambda **_kwargs: None
    engine._cancel_watchdog = lambda: None

    captured = {}

    class FakeRecorder:
        def start(self, on_done=None, on_error=None):
            captured["on_done"] = on_done
            captured["on_error"] = on_error
            return True

    engine.recorder = FakeRecorder()

    assert engine.start_recording(from_hotkey=True) is True
    assert callable(captured.get("on_done"))
    assert callable(captured.get("on_error"))
    assert captured["on_done"] is not captured["on_error"]


# ── 2. 自停後立刻 finalize，不必等 watchdog ─────────────────────────────


def test_autostop_triggers_immediate_finalize(monkeypatch, tmp_path):
    import app

    paste_calls = []
    notify_calls = []
    ledger_calls = []
    engine = _build_engine(
        monkeypatch,
        paste_calls,
        final_text="安全網立刻送出",
        notify_calls=notify_calls,
        ledger_calls=ledger_calls,
    )

    token = 5000.0
    engine.is_recording = True
    engine._record_start_ts = token
    engine._active_recording_tokens = {token}
    engine._recording_context_by_token = {
        token: {"mode": "dictate", "translation_targets": []}
    }
    # recorder 自己已經在背景 thread 內存好檔並回呼；此路徑絕對不能再呼叫
    # recorder.stop()（那會 join 正在執行本 callback 的 thread 本身 = 死結）。
    engine.recorder = types.SimpleNamespace(
        stop=lambda: (_ for _ in ()).throw(
            AssertionError("autostop 路徑不該呼叫 recorder.stop()")
        )
    )

    filepath = _touch(tmp_path, "autostop_immediate.wav")
    engine._on_recorder_autostop(filepath, 122.0, token)

    assert paste_calls == ["安全網立刻送出"]
    assert engine.is_recording is False
    assert engine._record_start_ts is None
    assert token not in engine._active_recording_tokens
    assert len(notify_calls) == 1
    assert notify_calls[0][0] == "SGH Voice"
    assert "靜音" in notify_calls[0][1]
    assert ledger_calls == [("ptt_autostop", "recording", {})]
    # backup_audio_dir 為空 → 處理完直接刪除暫存音檔，不留孤兒檔
    assert not os.path.exists(filepath)


def test_autostop_respects_cancelled_token(monkeypatch, tmp_path):
    """Cancel hotkey 標記過的 token：安全網不該再送去轉寫/貼上，也不該再跳
    「已自動停止」通知去誤導使用者（使用者是主動取消，不是安全網救援）。"""
    import app

    paste_calls = []
    notify_calls = []
    ledger_calls = []
    engine = _build_engine(
        monkeypatch, paste_calls, notify_calls=notify_calls, ledger_calls=ledger_calls
    )

    token = 5100.0
    engine.is_recording = True
    engine._record_start_ts = token
    engine._active_recording_tokens = {token}
    engine._cancelled_recording_tokens = {token}
    engine._recording_context_by_token = {
        token: {"mode": "dictate", "translation_targets": []}
    }

    filepath = _touch(tmp_path, "autostop_cancelled.wav")
    engine._on_recorder_autostop(filepath, 5.0, token)

    assert paste_calls == []
    assert notify_calls == []
    assert ledger_calls == []
    assert not os.path.exists(filepath)
    assert engine.is_recording is False


# ── 3. 競態一：自停已經 finalize 完，使用者「稍後」才放開按鍵 ────────────


def test_late_key_release_after_autostop_does_not_double_finalize(monkeypatch, tmp_path):
    import app

    paste_calls = []
    engine = _build_engine(monkeypatch, paste_calls, final_text="不該被貼兩次")

    token = 5200.0
    engine.is_recording = True
    engine._record_start_ts = token
    engine._active_recording_tokens = {token}
    engine._recording_context_by_token = {
        token: {"mode": "dictate", "translation_targets": []}
    }

    recorder_stop_calls = []
    engine.recorder = types.SimpleNamespace(
        stop=lambda: recorder_stop_calls.append(True) or (None, None, 0.0)
    )

    filepath = _touch(tmp_path, "autostop_then_release.wav")
    # Step 1：recorder 自己偵測到 PTT 靜音、finalize 完成（安全網先手）。
    engine._on_recorder_autostop(filepath, 130.0, token)
    assert paste_calls == ["不該被貼兩次"]

    # Step 2：使用者這時才真的放開按鍵。app.py:2183-2189 的 key-release 分支
    # 呼叫 stop_and_process 前會先檢查 `if engine.is_recording:`；就算忽略那層
    # 外部檢查直接呼叫，stop_and_process 自己的第一行守門
    # （`if not self.is_recording: return None`）也會讓它變成完全的 no-op。
    result = engine.stop_and_process()

    assert result is None
    assert recorder_stop_calls == []  # 根本不會再去碰 recorder
    assert paste_calls == ["不該被貼兩次"]  # 沒有第二次貼上


# ── 4. 競態二：watchdog 與自停幾乎同時到期 ──────────────────────────────


def test_watchdog_wins_race_then_late_autostop_callback_is_discarded(
    monkeypatch, tmp_path
):
    """watchdog 比 recorder 的自停 callback 早一步呼叫 stop_and_process 拿到
    音訊；recorder 那條背景 thread 幾乎同時也跨過 ptt_silence 門檻、自己另外
    存了一份檔，事後才呼叫 on_done——這時 armed_for_ts 已經不再屬於 engine，
    late callback 必須丟棄重複檔，不能進 pipeline。"""
    import app

    paste_calls = []
    engine = _build_engine(monkeypatch, paste_calls, final_text="watchdog 先贏")

    token = 5300.0
    engine.is_recording = True
    engine._record_start_ts = token
    engine._active_recording_tokens = {token}
    engine._recording_context_by_token = {
        token: {"mode": "dictate", "translation_targets": []}
    }

    watchdog_wav = _touch(tmp_path, "watchdog_stop.wav")
    engine.recorder = types.SimpleNamespace(
        stop=lambda: ([0.1, 0.2], watchdog_wav, 30.0)
    )

    # _arm_watchdog._fire()（app.py:977-989）到期後就是呼叫 stop_and_process。
    result = engine.stop_and_process()
    assert result is None
    assert paste_calls == ["watchdog 先贏"]

    late_fp = _touch(tmp_path, "late_autostop.wav")
    engine._on_recorder_autostop(late_fp, 30.1, token)

    assert paste_calls == ["watchdog 先贏"]  # 沒有第二次貼上
    assert not os.path.exists(late_fp)  # 遲到的重複檔被丟棄


def test_autostop_wins_race_then_watchdog_precheck_blocks_it(monkeypatch, tmp_path):
    """反過來：recorder 自停先贏。之後 watchdog timer 才到期，其 `_fire()`
    在呼叫 stop_and_process 之前會先在 `_state_lock` 下讀
    `current_ts = self._record_start_ts` / `is_recording = self.is_recording`
    並比對 `current_ts == armed_for_ts`（app.py:981-983）——這裡直接重現那段
    前置判斷，證明它會在碰到 stop_and_process 之前就先擋下來。"""
    import app

    paste_calls = []
    engine = _build_engine(monkeypatch, paste_calls, final_text="自停先贏")

    token = 5400.0
    engine.is_recording = True
    engine._record_start_ts = token
    engine._active_recording_tokens = {token}
    engine._recording_context_by_token = {
        token: {"mode": "dictate", "translation_targets": []}
    }
    engine.recorder = types.SimpleNamespace(
        stop=lambda: (_ for _ in ()).throw(
            AssertionError("watchdog 前置檢查沒擋住，不該碰到 recorder.stop()")
        )
    )

    filepath = _touch(tmp_path, "autostop_wins.wav")
    engine._on_recorder_autostop(filepath, 121.0, token)
    assert paste_calls == ["自停先贏"]

    with engine._state_lock:
        current_ts = engine._record_start_ts
        is_recording = engine.is_recording
    watchdog_would_fire = is_recording and current_ts == token
    assert watchdog_would_fire is False

    assert paste_calls == ["自停先贏"]


# ── 5. 防禦縱深：就算兩條路徑都真的跑到 _transcribe_and_paste ───────────


def test_paste_idempotency_token_backstops_autostop_even_if_double_invoked(
    monkeypatch,
):
    """就算未來改動不小心讓 still_owned 判定失守、同一個 recording_token 真
    的被兩條路徑都送進 _transcribe_and_paste，既有的
    `_consume_paste_token`／`_pasted_recording_tokens`（app.py:1055-1069，
    tests/test_paste_idempotency.py 已覆蓋其單元行為）仍然只放行一次
    paste——這是安全網 finalize 的第二層防線，不只依賴第一層的
    is_recording/_record_start_ts 判定。"""
    import app

    paste_calls = []
    engine = _build_engine(monkeypatch, paste_calls, final_text="雙重呼叫仍只貼一次")

    token = 5500.0
    engine._recording_context_by_token = {
        token: {"mode": "dictate", "translation_targets": []}
    }

    engine._transcribe_and_paste(None, None, 10.0, "dictate", "", token, [])
    engine._transcribe_and_paste(None, None, 10.0, "dictate", "", token, [])

    assert paste_calls == ["雙重呼叫仍只貼一次"]
    assert engine._pasted_recording_tokens == {token}
