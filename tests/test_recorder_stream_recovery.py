"""
PortAudio stream 死亡自癒與錯誤回報的回歸測試（2026-06-13 災情）。

實際案例：app 長跑 + 凌晨切換音訊裝置後，PortAudio 裝置清單過期，
之後每段錄音 InputStream 開啟都失敗 → 收到 0 個 chunk → stop 時
app.py 靜默回 idle。使用者只看到「🔴錄音中…」之後毫無下文。

修法：
1. _open_input_stream 開啟失敗 → 重新初始化 PortAudio 後重試一次（自癒）
2. 重試仍失敗 → 設 last_error + 回呼 on_error，engine 立刻重置狀態並顯示錯誤
3. stream 半路死亡 → 設 last_error + 刷新 PortAudio，讓下一段能重開
"""
import pytest
import numpy as np

import recorder as rec_mod

pytestmark = pytest.mark.skipif(rec_mod.sd is None, reason="sounddevice not installed")


def _make_recorder():
    return rec_mod.Recorder({"sample_rate": 16000})


def test_open_input_stream_reinit_and_retry(monkeypatch):
    """第一次開 stream 失敗 → 刷新 PortAudio → 重試成功。"""
    r = _make_recorder()
    attempts = []
    sentinel = object()

    def fake_input_stream(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise rec_mod.sd.PortAudioError("stale device list")
        return sentinel

    reinits = []
    monkeypatch.setattr(rec_mod.sd, "InputStream", fake_input_stream)
    monkeypatch.setattr(r, "_reinit_portaudio", lambda: reinits.append(1))

    out = r._open_input_stream(16000, 1600)
    assert out is sentinel
    assert len(attempts) == 2
    assert reinits == [1]


def test_open_input_stream_retry_still_fails_raises(monkeypatch):
    """重試後仍失敗 → 例外往外拋（由 _record_loop 接手回報）。"""
    r = _make_recorder()

    def always_fail(**kwargs):
        raise rec_mod.sd.PortAudioError("device gone")

    monkeypatch.setattr(rec_mod.sd, "InputStream", always_fail)
    monkeypatch.setattr(r, "_reinit_portaudio", lambda: None)

    with pytest.raises(rec_mod.sd.PortAudioError):
        r._open_input_stream(16000, 1600)


def test_record_loop_open_failure_reports_error(monkeypatch):
    """stream 開不起來 → last_error 設定 + on_error 回呼 + is_recording 重置。"""
    r = _make_recorder()

    def fail_open(sr, chunk):
        raise rec_mod.sd.PortAudioError("boom")

    monkeypatch.setattr(r, "_open_input_stream", fail_open)
    errors = []
    r._on_error = errors.append
    r.is_recording = True

    r._record_loop()

    assert r.is_recording is False
    assert r.last_error and "boom" in r.last_error
    assert errors and "boom" in errors[0]
    assert r.audio_data == []  # 沒收到任何 chunk


def test_record_loop_read_death_sets_last_error_and_reinits(monkeypatch):
    """stream 半路 read 失敗 → last_error 設定 + 刷新 PortAudio（下一段能重開）。"""
    r = _make_recorder()

    class DyingStream:
        def __init__(self):
            self.reads = 0

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, chunk):
            self.reads += 1
            if self.reads == 1:
                return np.zeros((chunk, 1), dtype=np.float32), False
            raise rec_mod.sd.PortAudioError("device unplugged")

    monkeypatch.setattr(r, "_open_input_stream", lambda sr, chunk: DyingStream())
    reinits = []
    monkeypatch.setattr(r, "_reinit_portaudio", lambda: reinits.append(1))
    r.is_recording = True

    r._record_loop()

    assert r.is_recording is False
    assert r.last_error and "device unplugged" in r.last_error
    assert reinits == [1]
    assert len(r.audio_data) == 1  # 死前收到的 chunk 仍保留


def test_start_resets_last_error(monkeypatch):
    """新一段錄音開始時要清掉上一段的 last_error，避免 stop 時報舊錯。"""
    r = _make_recorder()
    r.last_error = "舊錯誤"
    monkeypatch.setattr(
        rec_mod.threading, "Thread",
        lambda *a, **k: type("T", (), {"start": lambda self: None, "is_alive": lambda self: False})(),
    )
    r.start()
    assert r.last_error is None
