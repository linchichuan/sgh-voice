"""Continuous-dictation VAD loop: segmentation, backpressure, and thread
lifecycle regression tests (recorder.py:259-373).

Continuous mode keeps the microphone open indefinitely and fires
`on_segment(audio_array, duration)` on its own background thread every time
the VAD detects a voice->silence boundary. Two properties matter for a
long-running dictation session and were previously untested anywhere in the
repo (grep for "continuous"/"_pending_segments"/"_flush_segment" under
tests/ before this file only turns up app.py-level hotkey/orchestration
tests, never recorder.py's own loop):

1. Segments are assembled from the right chunk boundaries, in order.
2. `continuous_max_pending_segments` actually bounds pending work (by
   dropping the overflow segment, not by blocking the VAD loop), and a
   slow/cancelled/raising downstream consumer can never leak a pending slot
   forever.

No real microphone or PortAudio stream is used anywhere in this file:
`Recorder._open_input_stream` is monkeypatched to a fake stream fed
synthetic numpy chunks.
"""
import threading
import time

import numpy as np
import pytest

import recorder as rec_mod

pytestmark = pytest.mark.skipif(rec_mod.sd is None, reason="sounddevice not installed")

CHUNK = 1600  # 100ms @ 16kHz, matches recorder.py's `int(sr * 0.1)`


def _make_recorder(max_pending=2, silence_s=0.3, min_s=0.2, max_s=1.0):
    return rec_mod.Recorder({
        "sample_rate": 16000,
        "silence_threshold": 0.001,
        "continuous_silence_duration": silence_s,
        "continuous_min_segment_duration": min_s,
        "continuous_max_segment_duration": max_s,
        "continuous_max_pending_segments": max_pending,
    })


def _voice(n, amplitude):
    return [np.full((CHUNK, 1), amplitude, dtype=np.float32) for _ in range(n)]


def _silence(n):
    return [np.zeros((CHUNK, 1), dtype=np.float32) for _ in range(n)]


class _ScriptedStream:
    """Fake InputStream: replays a scripted chunk list, flips the recorder's
    _stop_event the moment the last chunk is delivered so `_continuous_loop`
    exits (and runs its natural end-of-stream flush) deterministically --
    no real audio I/O or wall-clock waiting involved."""

    def __init__(self, chunks, stop_event):
        self._chunks = list(chunks)
        self._stop_event = stop_event

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, chunk):
        data = self._chunks.pop(0)
        if not self._chunks:
            self._stop_event.set()
        return data, False


class _SyncThread:
    """Drop-in for threading.Thread that runs `target` synchronously on
    .start(). Used only for the ordering test below: production genuinely
    dispatches each segment on its own OS thread (exercised for real by the
    backpressure/cancel/lifecycle tests further down), but OS thread
    scheduling gives no ordering guarantee between two started threads, so
    asserting *delivery* order would be flaky by construction. Running the
    dispatch synchronously isolates the property that IS deterministic and
    under test here: _continuous_loop assembles the right chunks into the
    right segment, in the right order, before ever handing off to a thread.
    """

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **_):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)

    def is_alive(self):
        return False

    def join(self, timeout=None):
        return None


def _wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# ── 1. Segment boundaries + flush ordering ──────────────────────────────

def test_segments_are_flushed_in_chronological_order(monkeypatch):
    """3 consecutive voice/silence cycles -> 3 segments, correct content and
    order, correct trailing-silence trim math, correct no-trim tail flush.

    ⚠️ silence_s/min_s/max_s below are picked from values where
    `seconds / 0.1` lands on the "obvious" integer even without rounding
    (e.g. `0.5 / 0.1 == 5.0` exactly), so this test isolates segmentation
    logic from the float-rounding concern covered separately below.
    recorder.py now computes silence_chunks/min_seg_chunks/max_seg_chunks
    via `int(round(x / 0.1))` (previously plain `int(x / 0.1)`, which
    truncated *down* by one chunk for inputs like `0.3` or production's own
    default `continuous_min_segment_duration=0.6` -- see
    test_min_segment_duration_rounds_instead_of_truncating and
    test_record_loop_toggle_silence_duration_rounds_instead_of_truncating
    further below for the dedicated regression coverage of that fix).
    """
    r = _make_recorder(silence_s=0.5, min_s=0.2, max_s=1.0)  # silence_chunks=5, min=2
    monkeypatch.setattr(rec_mod.threading, "Thread", _SyncThread)

    chunks = (
        _voice(4, 0.05) + _silence(5)   # segment A: silence-triggered flush
        + _voice(4, 0.07) + _silence(5)  # segment B: silence-triggered flush
        + _voice(2, 0.09)                # segment C: flushed by natural stream end
    )
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    results = []
    r._continuous_loop(
        lambda audio, dur: results.append((round(float(audio[0]), 3), dur)),
        None, None,
    )

    assert [marker for marker, _ in results] == [0.05, 0.07, 0.09]
    # A/B: 4 voice + 5 silence chunks (9*0.1s=0.9s) minus the trimmed tail
    # (tail_cut = 5*1600 - 0.2*16000 = 4800 samples = 3 chunks) => 0.6s.
    assert results[0][1] == pytest.approx(0.6, abs=1e-6)
    assert results[1][1] == pytest.approx(0.6, abs=1e-6)
    # C: stream ends mid-utterance, no trailing silence to trim => 2*0.1s.
    assert results[2][1] == pytest.approx(0.2, abs=1e-6)
    assert r._pending_segments == 0  # synchronous dispatch always drains back to 0


def test_segment_callbacks_cannot_overtake_an_earlier_slow_segment():
    """實際 OS threads 下，第二段不得在第一段 STT／貼上完成前先交付。"""
    r = _make_recorder(max_pending=2, silence_s=0.2, min_s=0.1, max_s=1.0)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    delivered = []

    def on_segment(audio, dur):
        marker = round(float(audio[0]), 3)
        delivered.append(marker)
        if marker == 0.05:
            first_entered.set()
            release_first.wait(timeout=2)
        elif marker == 0.07:
            second_entered.set()

    chunks = _voice(2, 0.05) + _silence(2) + _voice(2, 0.07) + _silence(2)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    r._continuous_loop(on_segment, None, None)

    assert first_entered.wait(timeout=1)
    assert not second_entered.wait(timeout=0.1), "第二段越過仍在處理的第一段"
    release_first.set()
    assert _wait_until(lambda: delivered == [0.05, 0.07])
    assert _wait_until(lambda: r._pending_segments == 0)


def test_segment_shorter_than_min_duration_is_discarded_not_flushed(monkeypatch):
    """A blip below continuous_min_segment_duration must not reach on_segment
    at all (neither as a false-positive segment nor a zero-length one)."""
    r = _make_recorder(silence_s=0.2, min_s=0.5, max_s=1.0)  # min_seg_chunks=5
    monkeypatch.setattr(rec_mod.threading, "Thread", _SyncThread)

    # Only 2 voice chunks + 2 silence chunks (well below the 5-chunk min) then
    # a real segment so the loop has something to end on.
    chunks = _voice(2, 0.05) + _silence(2) + _voice(6, 0.09) + _silence(2)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    results = []
    r._continuous_loop(lambda audio, dur: results.append(round(float(audio[0]), 3)), None, None)

    assert results == [0.09]  # the too-short blip never produced a callback


# ── 2. Backpressure: continuous_max_pending_segments is enforced by DROP ──

def test_pending_cap_drops_overflow_segment_instead_of_blocking():
    """With max_pending=2 and two segments already in flight (blocked in a
    slow on_segment, simulating STT still processing), a 3rd completed
    segment must be dropped -- not queued, not waited on -- so the VAD loop
    itself never stalls behind a slow consumer."""
    r = _make_recorder(max_pending=2, silence_s=0.2, min_s=0.1, max_s=1.0)  # silence_chunks=2

    hold = threading.Event()  # left unset: on_segment blocks until the test releases it
    received = []
    lock = threading.Lock()

    def on_segment(audio, dur):
        with lock:
            received.append(round(float(audio[0]), 3))
        hold.wait(timeout=5)

    chunks = (
        _voice(2, 0.05) + _silence(2)   # segment 1 -> dispatched, blocks on `hold`
        + _voice(2, 0.07) + _silence(2)  # segment 2 -> dispatched, blocks on `hold`
        + _voice(2, 0.09) + _silence(2)  # segment 3 -> must be dropped (pending==2)
    )
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    r._continuous_loop(on_segment, None, None)

    # The pending counter is incremented synchronously in _flush_segment (the
    # calling/VAD thread), before the background thread is even started -- so
    # this is true immediately, with no race, the instant _continuous_loop
    # returns (it already processed all 3 flush points in-line).
    assert r._pending_segments == 2

    # Chronological delivery means segment 2 is pending behind the blocked
    # segment 1; it is counted for backpressure but cannot overtake it.
    assert _wait_until(lambda: received == [0.05])
    assert 0.09 not in received

    hold.set()  # release segment 1, then segment 2 may run
    assert _wait_until(lambda: received == [0.05, 0.07])
    assert _wait_until(lambda: r._pending_segments == 0)


# ── 3. Cancel-marker interception of an in-flight segment ─────────────────

def test_cancel_marker_intercepted_segment_still_releases_pending_slot():
    """recorder.py itself has no "cancel session" concept -- that lives in
    app.py's VoiceEngine._on_segment, which checks a shared `cancel_event`
    at the top of the callback and returns early without pasting/further
    processing (see app.py:1719-1758, `if duration < 0.4 or
    cancel_event.is_set(): return`). This models that exact shape: a
    callback that gets cancelled *while a segment is already in flight* on
    its own background thread, and must still let `_run_segment`'s
    `finally` release the pending slot -- otherwise a single cancelled
    session permanently jams continuous_max_pending_segments for whatever
    starts next."""
    r = _make_recorder(max_pending=1, silence_s=0.2, min_s=0.1, max_s=1.0)
    cancel_event = threading.Event()
    intercepted = []

    def on_segment(audio, dur):
        # Mirrors app.py's real cancel check: early-return, no exception.
        if cancel_event.is_set():
            intercepted.append(round(float(audio[0]), 3))
            return
        raise AssertionError("should have been intercepted by cancel_event")

    cancel_event.set()  # session already cancelled before this segment flushes
    chunks = _voice(2, 0.05) + _silence(2)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    r._continuous_loop(on_segment, None, None)

    assert _wait_until(lambda: intercepted == [0.05])
    assert _wait_until(lambda: r._pending_segments == 0), (
        "pending slot leaked after the cancel marker intercepted an "
        "in-flight segment -- would permanently block future segments"
    )

    # The freed slot must actually be usable by the next (un-cancelled) segment.
    cancel_event.clear()
    received = []
    chunks2 = _voice(2, 0.07) + _silence(2)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks2, r._stop_event)
    r._stop_event.clear()
    r._continuous_loop(lambda audio, dur: received.append(round(float(audio[0]), 3)), None, None)
    assert _wait_until(lambda: received == [0.07])


def test_pending_slot_is_released_even_if_on_segment_raises():
    """Defense in depth beyond the cancel-marker path above: recorder.py's
    own `finally: self._pending_segments -= 1` (recorder.py:309-311) must
    hold even if a caller's callback is outright broken and raises, not
    just when it cooperatively early-returns. A misbehaving/buggy caller
    must never be able to permanently exhaust continuous_max_pending_segments."""
    r = _make_recorder(max_pending=1, silence_s=0.2, min_s=0.1, max_s=1.0)

    def broken_on_segment(audio, dur):
        raise RuntimeError("simulated: caller callback blew up")

    chunks = _voice(2, 0.05) + _silence(2)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    r._continuous_loop(broken_on_segment, None, None)

    assert _wait_until(lambda: r._pending_segments == 0), (
        "pending slot leaked after on_segment raised -- would permanently "
        "block all future segments once max_pending is reached"
    )


# ── 4. Fast stop/start does not leave a residual thread ───────────────────

def test_stop_then_restart_leaves_no_residual_thread():
    """After _stop_event triggers a clean exit, the recorder thread must
    actually terminate (join succeeds) and on_stopped must fire -- and a
    fresh start_continuous() right after must spin up a genuinely new
    thread, not silently reuse/hang on the old one."""
    r = _make_recorder()

    class _QuietStream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, chunk):
            return np.zeros((chunk, 1), dtype=np.float32), False

    r._open_input_stream = lambda sr, chunk: _QuietStream()

    stopped_1 = []
    assert r.start_continuous(on_segment=lambda *a: None, on_stopped=lambda: stopped_1.append(1)) is True
    thread_1 = r._thread
    assert thread_1 is not None and thread_1.is_alive()

    r._stop_event.set()
    thread_1.join(timeout=3)
    assert thread_1.is_alive() is False
    assert r.is_recording is False
    assert stopped_1 == [1]

    # Mirror app.py's stop_continuous_mode discipline (join before allowing a
    # restart). recorder.start_continuous() now also has its own is_alive()
    # guard (same as start(), see tests further below) as a second line of
    # defense, but this test still joins explicitly first to isolate "clean
    # stop -> clean restart" from the guard's own wait/reject behavior.
    r._stop_event.clear()
    stopped_2 = []
    assert r.start_continuous(on_segment=lambda *a: None, on_stopped=lambda: stopped_2.append(1)) is True
    thread_2 = r._thread
    assert thread_2 is not thread_1

    r._stop_event.set()
    thread_2.join(timeout=3)
    assert thread_2.is_alive() is False
    assert r.is_recording is False
    assert stopped_2 == [1]


# ── 5. Float-rounding regression (recorder.py chunk-count math) ───────────
#
# recorder.py computes silence/min/max segment lengths in "chunks" (100ms
# units) from seconds via division by 0.1. IEEE-754 float division makes
# plain `int(x / 0.1)` truncate *down* by one chunk for inputs such as 0.3,
# 0.6, or 0.7 (`0.6 / 0.1 == 5.999999999999999`, `0.7 / 0.1 ==
# 6.999999999999999`) -- silently shrinking a documented N-second threshold
# to (N-0.1) seconds. Fixed by rounding first: `int(round(x / 0.1))`. Two
# call sites needed this fix: _continuous_loop's silence/min/max segment
# chunk counts, and _record_loop's toggle-mode silence auto-stop threshold.

def test_min_segment_duration_rounds_instead_of_truncating(monkeypatch):
    """Production's own default `continuous_min_segment_duration=0.6` hit
    this bug: pre-fix `min_seg_chunks = int(0.6 / 0.1) == 5`, silently
    lowering the documented 0.6s floor to 0.5s. With min_s=0.6 and
    silence_s=0.2 (silence_chunks=2, no rounding ambiguity there), a segment
    of exactly 5 voice chunks (0.5s) + 2 trailing silence chunks has
    len(seg_buffer)==7. Required threshold is min_seg_chunks + silence_chunks:
    pre-fix that's 5+2=7 (7>=7 -> WOULD wrongly flush a sub-floor segment);
    post-fix it's 6+2=8 (7<8 -> correctly discarded). This test asserts the
    post-fix (correct) behavior and would fail under the old truncating code."""
    r = _make_recorder(silence_s=0.2, min_s=0.6, max_s=1.0)
    monkeypatch.setattr(rec_mod.threading, "Thread", _SyncThread)

    chunks = _voice(5, 0.05) + _silence(2)  # 0.5s voice: below the 0.6s min floor
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    results = []
    r._continuous_loop(lambda audio, dur: results.append(round(float(audio[0]), 3)), None, None)

    assert results == []  # must be discarded -- 0.5s is below the configured 0.6s floor
    assert r._pending_segments == 0


def test_record_loop_toggle_silence_duration_rounds_instead_of_truncating(monkeypatch):
    """Sibling bug fixed at the same time, in the Push-to-Talk toggle-mode
    auto-stop path (recorder.py's `_record_loop`, not `_continuous_loop`).
    With `silence_duration=0.7`, pre-fix `silence_chunks = int(0.7 / 0.1) ==
    6` (should be 7), so toggle mode would auto-stop after only 0.6s of
    trailing silence instead of the configured 0.7s. 3 voice chunks followed
    by 10 silence chunks (ample margin past the 6-vs-7 boundary) must
    accumulate exactly 3+7=10 chunks in audio_data before auto-stop breaks
    the loop -- not 3+6=9."""
    r = rec_mod.Recorder({
        "sample_rate": 16000,
        "silence_threshold": 0.001,
        "silence_duration": 0.7,
        "hotkey_mode": "toggle",
        "max_recording_duration": 1800,
    })
    chunks = _voice(3, 0.05) + _silence(10)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    r._record_loop()

    assert len(r.audio_data) == 10  # 3 voice + 7 silence chunks (0.7s), not 6


# ── 5a. Push-to-talk silence auto-stop safety net (config.ptt_silence_
#         autostop_seconds) ──────────────────────────────────────────────
#
# Motivation: toggle mode already auto-stops on trailing silence (test
# above); push_to_talk relied only on key-release or the 30-minute
# max_recording_duration watchdog. If the key-release NSEvent is lost
# (app switch, KVM, etc.) the mic stays open for up to 30 minutes. This
# threshold reuses the exact same rms/consecutive_silence counting done
# for the toggle branch (no second energy computation) and breaks the
# loop through the identical code path -- see recorder.py:_record_loop.

def test_ptt_silence_autostop_triggers_after_threshold(monkeypatch):
    """2 voice chunks + threshold-worth of silence must break the loop
    early -- before the remaining scripted silence chunks are ever read."""
    r = rec_mod.Recorder({
        "sample_rate": 16000,
        "silence_threshold": 0.001,
        "hotkey_mode": "push_to_talk",
        "ptt_silence_autostop_seconds": 0.5,  # -> 5 chunks
        "max_recording_duration": 1800,
    })
    # 2 voice + 8 silence chunks scripted, but autostop must fire after the
    # 5th consecutive silence chunk (2+5=7), leaving 3 chunks unread.
    chunks = _voice(2, 0.05) + _silence(8)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    r._record_loop()

    assert len(r.audio_data) == 7  # 2 voice + 5 silence chunks (0.5s), not all 10
    assert r.is_recording is False


def test_ptt_silence_autostop_does_not_trigger_while_speaking(monkeypatch):
    """Silence never accumulates past the (short) threshold because voice
    keeps resetting consecutive_silence -> loop must run to natural
    end-of-stream, not break early. Threshold generous enough in production
    (default 120s) to never cut off a real pause; this test just proves the
    reset logic, using a short threshold so the test stays fast."""
    r = rec_mod.Recorder({
        "sample_rate": 16000,
        "silence_threshold": 0.001,
        "hotkey_mode": "push_to_talk",
        "ptt_silence_autostop_seconds": 0.3,  # -> 3 chunks
        "max_recording_duration": 1800,
    })
    # Alternating voice/silence(1): consecutive_silence never exceeds 1,
    # always below the 3-chunk threshold.
    chunks = (_voice(1, 0.05) + _silence(1)) * 5  # 10 chunks total
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    r._record_loop()

    assert len(r.audio_data) == 10  # all chunks consumed, no early break
    assert r.is_recording is False  # normal end-of-stream still resets the flag


def test_ptt_silence_autostop_disabled_when_zero(monkeypatch):
    """ptt_silence_autostop_seconds=0 must fully disable the safety net --
    20 consecutive silence chunks (far past any sane threshold) must not
    break the loop; it only ends via natural end-of-stream."""
    r = rec_mod.Recorder({
        "sample_rate": 16000,
        "silence_threshold": 0.001,
        "hotkey_mode": "push_to_talk",
        "ptt_silence_autostop_seconds": 0,
        "max_recording_duration": 1800,
    })
    chunks = _silence(20)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)
    r.is_recording = True

    r._record_loop()

    assert len(r.audio_data) == 20  # disabled -> never breaks early


def test_ptt_silence_autostop_then_immediate_stop_is_not_double_finished():
    """Compatibility with app.py's PTT key-release handler
    (app.py:2183-2189 calls engine.stop_and_process() -> recorder.stop()
    exactly once per token when the physical key transitions to released).

    Simulates the auto-stop firing and the key-release arriving almost
    simultaneously: run _record_loop on a real thread (like start() does)
    so it can actually finish and die on its own, then call stop() right
    after -- mirroring what stop_and_process() does on key-release.

    Must prove two things recorder.stop()'s own logic already guarantees
    but which a silence-triggered early break could plausibly break:
    1. No dead-wait: the recorder thread already exited by itself, so
       stop()'s `self._thread.join(timeout=5)` must return near-instantly,
       not block for the full 5s meant for a genuinely stuck stream.
    2. No double-finish: a second stop() call (e.g. a watchdog firing in
       the same window) must be a no-op, not reprocess/re-save audio_data.
    """
    r = rec_mod.Recorder({
        "sample_rate": 16000,
        "silence_threshold": 0.001,
        "hotkey_mode": "push_to_talk",
        "ptt_silence_autostop_seconds": 0.5,  # -> 5 chunks
        "max_recording_duration": 1800,
    })
    chunks = _voice(2, 0.05) + _silence(8)
    r._open_input_stream = lambda sr, chunk: _ScriptedStream(chunks, r._stop_event)

    # Mirror what Recorder.start() sets up, since we're driving
    # _record_loop directly on our own thread instead of via start().
    r.is_recording = True
    r._stop_event.clear()
    r._start_time = time.time()
    r._thread = threading.Thread(target=r._record_loop, daemon=True)
    r._thread.start()

    assert r._thread.join(timeout=2.0) is None
    assert not r._thread.is_alive()  # autostop already ended the thread

    t0 = time.time()
    audio_array, filepath, duration = r.stop()
    elapsed = time.time() - t0
    try:
        assert elapsed < 2.0  # must not dead-wait the full 5s join timeout
        assert audio_array is not None
        assert len(audio_array) == 7 * 1600  # 2 voice + 5 silence chunks

        # "almost simultaneous" second stop trigger (e.g. watchdog racing
        # the key-release) must be inert, not reprocess audio_data.
        audio_array2, filepath2, duration2 = r.stop()
        assert audio_array2 is None
        assert filepath2 is None
        assert duration2 == 0
    finally:
        if filepath:
            rec_mod.os.unlink(filepath)


# ── 6. start_continuous() PortAudio-deadlock guard (mirrors start()) ──────


class _NoOpThread:
    """Drop-in threading.Thread replacement whose .start() does nothing --
    used to test start_continuous()'s own gate logic in isolation, without
    actually running _continuous_loop (which would need a real/fake audio
    stream unrelated to what these tests check)."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **_):
        self._target = target

    def start(self):
        pass

    def is_alive(self):
        return False

    def join(self, timeout=None):
        return None


def test_start_continuous_waits_for_dying_thread_then_succeeds(monkeypatch):
    """New guard added to start_continuous(), mirroring start()'s at
    recorder.py:47-54: if a caller invokes start_continuous() again while
    the previous recorder thread is still alive (bypassing app.py's own
    external join discipline in start_continuous_mode/stop_continuous_mode),
    it must wait up to 2s for that thread to finish -- not race it with a
    second concurrent InputStream, which deadlocks inside PortAudio's
    Pa_OpenStream. If the old thread finishes within the wait, the new
    recording must start normally."""
    r = _make_recorder()

    class _DyingOldThread:
        def __init__(self):
            self.join_calls = []
            self._alive_calls = 0

        def is_alive(self):
            self._alive_calls += 1
            # Alive on the first check (before join); "finished" by the
            # second check (right after join() -- simulates the old thread
            # completing its InputStream teardown during the wait).
            return self._alive_calls == 1

        def join(self, timeout=None):
            self.join_calls.append(timeout)

    old = _DyingOldThread()
    r._thread = old
    monkeypatch.setattr(rec_mod.threading, "Thread", _NoOpThread)

    assert r.start_continuous(on_segment=lambda *a: None) is True
    assert old.join_calls == [2.0]
    assert r._thread is not old  # a genuinely new thread was started
    assert r.is_recording is True


def test_start_continuous_raises_when_previous_thread_wont_die():
    """If the previous thread is still alive even after the 2s join, the
    guard must reject the new recording outright (raise) rather than
    silently opening a second InputStream on top of a stuck one -- and must
    not mutate recorder state on the way out, so the caller can inspect/retry
    cleanly (mirrors start()'s same rejection contract, already covered for
    start() by test_thread_start_failure_rolls_back_recorder_state in
    tests/test_recorder_stream_recovery.py)."""
    r = _make_recorder()

    class _StuckOldThread:
        def __init__(self):
            self.joined_timeout = None

        def is_alive(self):
            return True

        def join(self, timeout=None):
            self.joined_timeout = timeout

    old = _StuckOldThread()
    r._thread = old

    with pytest.raises(RuntimeError, match="PortAudio deadlock"):
        r.start_continuous(on_segment=lambda *a: None)

    assert old.joined_timeout == 2.0
    assert r.is_recording is False  # rejected start must not flip state
    assert r._thread is old  # stuck thread reference preserved, not clobbered
