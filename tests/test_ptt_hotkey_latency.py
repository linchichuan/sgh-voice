"""PTT 熱鍵「按下→第一個 audio frame」啟動延遲最佳化的回歸測試（2026-09）。

涵蓋 recorder.py 新增的三個獨立機制（見 docs/recorder-ptt-latency.md）：

1. `Recorder.warm_up()` / `warm_up_async()`：只 open+close，絕不 start()，
   不構成「idle 時持續開啟 input stream」；可由 config 關閉；任何失敗都
   only-warn，不拋例外。`_reinit_portaudio()` 成功後會補一次背景預熱。
2. `_open_input_stream()` 明確傳 `latency`（預設 'low'，可被 config 覆寫，
   非法值安全退回 'low'）。
3. `_record_loop()` 第一個 0.1s chunk 的可選 probe-read 分段
   （`recorder_first_frame_probe_ms`）：預設（裸 dict config，無此 key）
   必須完全不改變既有的單次 100ms read 行為 —— 這是本檔最重要的一組
   斷言，因為 tests/test_recorder_stream_recovery.py 與
   tests/test_audio_level_meter.py 的既有假設（stream.read() 的呼叫次數/
   次序）依賴這一點沒有被打破。
"""
import threading

import numpy as np
import pytest

import recorder as rec_mod

pytestmark = pytest.mark.skipif(rec_mod.sd is None, reason="sounddevice not installed")

CHUNK = 1600  # 100ms @ 16kHz


def _make_recorder(**extra):
    config = {"sample_rate": 16000, "hotkey_mode": "push_to_talk"}
    config.update(extra)
    return rec_mod.Recorder(config)


# ─── _resolve_input_latency / _open_input_stream latency plumbing ───────


def test_open_input_stream_passes_low_latency_by_default(monkeypatch):
    r = _make_recorder()
    captured = {}

    def fake_input_stream(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(rec_mod.sd, "InputStream", fake_input_stream)
    r._open_input_stream(16000, 1600)
    assert captured.get("latency") == "low"


def test_open_input_stream_honors_config_override(monkeypatch):
    r = _make_recorder(recorder_input_latency="high")
    captured = {}

    def fake_input_stream(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(rec_mod.sd, "InputStream", fake_input_stream)
    r._open_input_stream(16000, 1600)
    assert captured.get("latency") == "high"


def test_resolve_input_latency_falls_back_to_low_on_invalid_value():
    r = _make_recorder(recorder_input_latency="ultra-fast")
    assert r._resolve_input_latency() == "low"


def test_resolve_input_latency_falls_back_to_low_on_non_string():
    r = _make_recorder(recorder_input_latency=42)
    assert r._resolve_input_latency() == "low"


# ─── warm_up() / warm_up_async() ─────────────────────────────────────────


class _FakeStream:
    def __init__(self):
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def close(self):
        self.closed = True


def test_warm_up_opens_and_closes_without_ever_starting(monkeypatch):
    """核心隱私斷言：warm_up() 絕不可呼叫 .start()（那才是 PortAudio 真正
    啟動 IO、macOS 麥克風使用指示會點亮的動作）。"""
    r = _make_recorder()
    created = []

    def fake_input_stream(**kwargs):
        s = _FakeStream()
        created.append(s)
        return s

    monkeypatch.setattr(rec_mod.sd, "InputStream", fake_input_stream)
    assert r.warm_up() is True
    assert len(created) == 1
    assert created[0].started is False
    assert created[0].closed is True


def test_warm_up_disabled_via_config(monkeypatch):
    r = _make_recorder(enable_recorder_prewarm=False)
    calls = []
    monkeypatch.setattr(rec_mod.sd, "InputStream", lambda **kw: calls.append(kw))
    assert r.warm_up() is False
    assert calls == []


def test_warm_up_swallows_open_failure(monkeypatch):
    r = _make_recorder()

    def always_fail(**kwargs):
        raise rec_mod.sd.PortAudioError("no device")

    monkeypatch.setattr(rec_mod.sd, "InputStream", always_fail)
    assert r.warm_up() is False  # 不拋例外


class _CloseFailsStream:
    """open() 成功但 close() 本身會拋例外——驗證 close() 一定會被嘗試
    （放在 finally），且 close() 失敗不會讓 warm_up() 整體回報失敗或把例外
    傳出去（priming 的效果在 open() 成功當下就已經達成）。"""

    def __init__(self):
        self.started = False
        self.close_attempted = False

    def start(self):
        self.started = True

    def close(self):
        self.close_attempted = True
        raise RuntimeError("close failed")


def test_warm_up_attempts_close_even_when_close_itself_raises(monkeypatch):
    r = _make_recorder()
    stream = _CloseFailsStream()
    monkeypatch.setattr(rec_mod.sd, "InputStream", lambda **kw: stream)
    assert r.warm_up() is True  # close() 失敗不代表預熱失敗，priming 已達成
    assert stream.close_attempted is True


def test_warm_up_async_runs_in_background_thread(monkeypatch):
    r = _make_recorder()
    done = threading.Event()
    calls = []

    def fake_warm_up():
        calls.append(1)
        done.set()
        return True

    monkeypatch.setattr(r, "warm_up", fake_warm_up)
    r.warm_up_async()
    assert done.wait(timeout=2)
    assert calls == [1]


def test_reinit_portaudio_triggers_background_warmup(monkeypatch):
    r = _make_recorder()
    monkeypatch.setattr(rec_mod.sd, "_terminate", lambda: None)
    monkeypatch.setattr(rec_mod.sd, "_initialize", lambda: None)
    spy = []
    monkeypatch.setattr(r, "warm_up_async", lambda: spy.append(1))
    r._reinit_portaudio()
    assert spy == [1]


def test_reinit_portaudio_does_not_trigger_warmup_on_failure(monkeypatch):
    """terminate/initialize 失敗時不該再補一次背景 warm-up——沒有理由相信
    刷新失敗後緊接著 open+close 會成功，而且會白白製造一次跟下一次真正
    開流的 stream 競爭。"""
    r = _make_recorder()

    def boom():
        raise RuntimeError("Pa_Terminate failed")

    monkeypatch.setattr(rec_mod.sd, "_terminate", boom)
    spy = []
    monkeypatch.setattr(r, "warm_up_async", lambda: spy.append(1))
    r._reinit_portaudio()
    assert spy == []


# ─── PortAudio 全域狀態併發安全（warm_up / _reinit_portaudio / 真正錄音）──


def test_warm_up_skips_when_recording_already_in_progress(monkeypatch):
    """錄音已經開始（is_recording=True）時 warm_up() 必須直接跳過，不再
    另外開一個 Pa_OpenStream()——這是本來就沒有意義的重複工作，也是跟
    真正錄音併發開流的來源之一。"""
    r = _make_recorder()
    r.is_recording = True
    calls = []
    monkeypatch.setattr(rec_mod.sd, "InputStream", lambda **kw: calls.append(kw))
    assert r.warm_up() is False
    assert calls == []


def test_warm_up_skips_when_it_cannot_acquire_pa_lock(monkeypatch):
    """warm_up() 是 best-effort：搶不到 self._pa_lock（代表 _reinit_portaudio()
    或另一個 warm-up 正在動 PortAudio）就直接放棄，不阻塞、不排隊等待。
    self._pa_lock 是 RLock，同一個 thread 重入永遠會成功，所以必須用真正
    的另一個 thread 持有鎖才能驗證這條「搶不到」路徑。"""
    r = _make_recorder()
    calls = []
    monkeypatch.setattr(rec_mod.sd, "InputStream", lambda **kw: calls.append(kw))

    lock_held = threading.Event()
    release_lock = threading.Event()

    def hold_lock():
        r._pa_lock.acquire()
        lock_held.set()
        release_lock.wait(timeout=2)
        r._pa_lock.release()

    holder = threading.Thread(target=hold_lock, daemon=True)
    holder.start()
    try:
        assert lock_held.wait(timeout=2), "holder thread never acquired the lock"
        assert r.warm_up() is False
        assert calls == []
    finally:
        release_lock.set()
        holder.join(timeout=2)


def test_reinit_portaudio_waits_for_in_flight_warm_up_before_terminating(monkeypatch):
    """核心競態修復：_reinit_portaudio() 的 sd._terminate() 絕不能跟另一個
    thread 正在執行中的 warm_up() open/close 同時發生（Pa_Terminate 會強制
    關閉所有 stream，跟另一個 thread 手上還沒 close() 的 stream 打架是未
    定義行為）。用一個真的會佔住鎖一小段時間的背景 warm_up() thread 驗證
    _reinit_portaudio() 確實會等它讓出鎖，而不是搶進去。"""
    r = _make_recorder()
    order = []
    warmup_started = threading.Event()
    release_warmup = threading.Event()

    def fake_input_stream(**kwargs):
        warmup_started.set()
        assert release_warmup.wait(timeout=2), "warm_up thread never got to proceed"
        order.append("warm_up_open")
        return _FakeStream()

    monkeypatch.setattr(rec_mod.sd, "InputStream", fake_input_stream)

    def run_warm_up():
        r.warm_up()

    t = threading.Thread(target=run_warm_up, daemon=True)
    t.start()
    assert warmup_started.wait(timeout=2), "warm_up thread never started"

    def fake_terminate():
        order.append("terminate")

    monkeypatch.setattr(rec_mod.sd, "_terminate", fake_terminate)
    monkeypatch.setattr(rec_mod.sd, "_initialize", lambda: None)
    monkeypatch.setattr(r, "warm_up_async", lambda: None)  # 不需要再觸發下一輪

    # 讓 warm_up 的 InputStream() 呼叫先卡著，主 thread 呼叫 _reinit_portaudio()
    # 必須被 self._pa_lock 擋住，直到我們放行 warm_up。
    release_warmup.set()
    r._reinit_portaudio()
    t.join(timeout=2)

    assert order == ["warm_up_open", "terminate"], (
        "_reinit_portaudio() 的 terminate() 必須等 warm_up() 的 open/close 結束才執行"
    )


def test_open_input_stream_proceeds_even_when_pa_lock_is_held_by_another_thread(monkeypatch):
    """熱鍵路徑不可被 warm-up 卡住：即使 self._pa_lock 被『另一個 thread』
    持有（模擬 warm-up 正在進行——RLock 對同一 thread 是可重入的，必須用
    真正的另一個 thread 才能驗證這條路徑），_open_input_stream() 仍必須在
    有界的短時間內直接開自己的 stream，不能無限期等待或放棄開錄音。"""
    r = _make_recorder()
    calls = []
    monkeypatch.setattr(rec_mod.sd, "InputStream", lambda **kw: calls.append(kw) or _FakeStream())

    lock_held = threading.Event()
    release_lock = threading.Event()

    def hold_lock():
        r._pa_lock.acquire()
        lock_held.set()
        release_lock.wait(timeout=2)
        r._pa_lock.release()

    holder = threading.Thread(target=hold_lock, daemon=True)
    holder.start()
    assert lock_held.wait(timeout=2), "holder thread never acquired the lock"

    t0 = rec_mod.time.perf_counter()
    stream = r._open_input_stream(16000, 1600)
    elapsed = rec_mod.time.perf_counter() - t0

    release_lock.set()
    holder.join(timeout=2)

    assert isinstance(stream, _FakeStream)
    assert len(calls) == 1
    # 有界等待（_open_input_stream 用 timeout=0.05），不是無限期卡住。
    assert elapsed < 0.5


# ─── _record_loop: hotkey→first-frame 量測 + probe-read 相容性 ──────────


class _SlicingScriptedStream:
    """用一個扁平化的樣本緩衝服務任意大小的 read(n) 請求 —— 讓測試能斷言
    probe/remainder 的精確切分大小，同時保證拼回去的音訊內容跟單次整讀
    逐 byte 相同。全部樣本被讀完時設定 stop_event（比照
    tests/test_continuous_mode.py 的 _ScriptedStream 慣例）。"""

    def __init__(self, chunks, stop_event):
        self._buf = np.concatenate(chunks, axis=0)
        self._pos = 0
        self._stop_event = stop_event
        self.read_sizes = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n):
        self.read_sizes.append(n)
        out = self._buf[self._pos:self._pos + n]
        self._pos += n
        if self._pos >= len(self._buf):
            self._stop_event.set()
        return out, False


def _two_chunks():
    return [
        np.full((CHUNK, 1), 0.05, dtype=np.float32),
        np.full((CHUNK, 1), 0.06, dtype=np.float32),
    ]


def test_record_loop_default_config_does_single_read_per_chunk(monkeypatch):
    """裸 dict config（無 recorder_first_frame_probe_ms key）必須完全沿用
    改動前的行為：每個 0.1s chunk 剛好一次 stream.read(1600)。這是
    tests/test_recorder_stream_recovery.py 與 tests/test_audio_level_meter.py
    的既有假設，不能被打破。"""
    r = _make_recorder(max_recording_duration=0.2)
    stream = _SlicingScriptedStream(_two_chunks(), r._stop_event)
    r._open_input_stream = lambda sr, chunk: stream
    r.is_recording = True

    r._record_loop()

    assert stream.read_sizes == [1600, 1600]
    assert len(r.audio_data) == 2


def test_record_loop_probe_enabled_splits_first_chunk_only(monkeypatch):
    """明確 opt-in（config.recorder_first_frame_probe_ms=20）才會分段讀第
    一個 chunk；之後的 chunk 照舊單次整讀。拼回去的音訊內容必須跟不分段
    時逐 byte 相同（VAD/RMS 用的是同一份資料，不可能因為多讀一次而失真）。"""
    r = _make_recorder(max_recording_duration=0.2, recorder_first_frame_probe_ms=20)
    chunks = _two_chunks()
    stream = _SlicingScriptedStream(chunks, r._stop_event)
    r._open_input_stream = lambda sr, chunk: stream
    r.is_recording = True

    r._record_loop()

    assert stream.read_sizes == [320, 1280, 1600]  # 20ms probe + 80ms remainder, 之後照舊
    assert len(r.audio_data) == 2
    np.testing.assert_array_equal(r.audio_data[0], chunks[0])
    np.testing.assert_array_equal(r.audio_data[1], chunks[1])


def test_record_loop_preserves_probe_data_when_remainder_read_fails(monkeypatch):
    """probe read 成功、緊接著的 remainder read 失敗時，已經到手的 probe
    音訊（往往就是使用者開口的第一個字）不能被默默丟棄。"""
    r = _make_recorder(max_recording_duration=0.2, recorder_first_frame_probe_ms=20)
    probe_frames = 320  # 20ms @ 16kHz
    probe_chunk = np.full((probe_frames, 1), 0.05, dtype=np.float32)

    class _ProbeThenFailStream:
        def __init__(self):
            self.read_sizes = []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n):
            self.read_sizes.append(n)
            if len(self.read_sizes) == 1:
                return probe_chunk, False
            raise rec_mod.sd.PortAudioError("remainder read failed")

    stream = _ProbeThenFailStream()
    r._open_input_stream = lambda sr, chunk: stream
    monkeypatch.setattr(r, "_reinit_portaudio", lambda: None)  # 不必真的動 PortAudio
    r.is_recording = True

    r._record_loop()

    assert stream.read_sizes == [320, 1280]
    assert len(r.audio_data) == 1  # probe 資料被保留，不是空的
    np.testing.assert_array_equal(r.audio_data[0], probe_chunk)
    assert r.last_error is not None and "remainder read failed" in r.last_error
    assert r.is_recording is False


def test_record_loop_reports_hotkey_to_first_frame_latency(monkeypatch):
    r = _make_recorder(max_recording_duration=0.1)
    stream = _SlicingScriptedStream([np.full((CHUNK, 1), 0.05, dtype=np.float32)], r._stop_event)
    r._open_input_stream = lambda sr, chunk: stream

    reported = []
    r.set_first_frame_listener(reported.append)
    r.set_hotkey_press_ts(rec_mod.time.perf_counter() - 0.05)  # 模擬 50ms 前按下熱鍵
    r.is_recording = True

    r._record_loop()

    assert len(reported) == 1
    assert reported[0] >= 40  # 至少涵蓋我們模擬的 50ms（容忍排程誤差抓 40ms 下限）
    # 消費後必須清空，避免下一段非熱鍵觸發的錄音誤用舊值
    assert r._pending_hotkey_ts is None


def test_record_loop_skips_metric_when_hotkey_ts_not_set(monkeypatch):
    """CLI/Dashboard 等非熱鍵路徑從不呼叫 set_hotkey_press_ts()，
    _pending_hotkey_ts 預設 None → 完全不觸發 first-frame 回呼，
    避免顯示誤導性的延遲數字。"""
    r = _make_recorder(max_recording_duration=0.1)
    stream = _SlicingScriptedStream([np.full((CHUNK, 1), 0.05, dtype=np.float32)], r._stop_event)
    r._open_input_stream = lambda sr, chunk: stream

    reported = []
    r.set_first_frame_listener(reported.append)
    r.is_recording = True

    r._record_loop()

    assert reported == []


def test_first_frame_listener_exception_does_not_break_recording(monkeypatch):
    """觀測用途的 callback 壞掉絕不能打斷錄音本身。"""
    r = _make_recorder(max_recording_duration=0.1)
    stream = _SlicingScriptedStream([np.full((CHUNK, 1), 0.05, dtype=np.float32)], r._stop_event)
    r._open_input_stream = lambda sr, chunk: stream

    def _boom(_ms):
        raise RuntimeError("boom")

    r.set_first_frame_listener(_boom)
    r.set_hotkey_press_ts(rec_mod.time.perf_counter())
    r.is_recording = True

    r._record_loop()  # 不應該拋出例外

    assert len(r.audio_data) == 1
    assert r.is_recording is False
