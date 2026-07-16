"""Regression coverage for editable, live-reloaded macOS hotkeys."""

from __future__ import annotations

import sys
import types

import pytest

from hotkey_config import (
    FN_KEYCODE,
    FN_MODIFIER_MASK,
    FN_RECORD_HOTKEY,
    HotkeyValidationError,
    MODIFIER_TOKENS,
    RECOMMENDED_ACTION_HOTKEYS,
    RECOMMENDED_RECORD_HOTKEY,
    modifier_is_pressed,
    parse_hotkey,
    validate_hotkey_config,
)


def test_recommended_hotkey_is_modifier_only_and_normalized():
    spec = parse_hotkey("right_alt + right_shift")

    assert spec.normalized == RECOMMENDED_RECORD_HOTKEY
    assert spec.tokens == ("right_option", "right_shift")
    assert spec.keycodes == frozenset({61, 60})


@pytest.mark.parametrize(
    "value",
    [
        "right_fn+right_shift",
        "Right Fn + Right Shift",
        "globe+right_shift",
        "function_key+right_shift",
    ],
)
def test_fn_aliases_are_accepted_and_normalized(value):
    spec = parse_hotkey(value)

    assert spec.normalized == FN_RECORD_HOTKEY
    assert spec.tokens == ("fn", "right_shift")
    assert spec.keycodes == frozenset({FN_KEYCODE, 60})


def test_auxiliary_hotkey_can_be_disabled():
    spec = parse_hotkey("  ", field="continuous_hotkey")

    assert spec.normalized == ""
    assert spec.keycodes == frozenset()


@pytest.mark.parametrize(
    ("value", "field"),
    [
        ("right_option+banana", "hotkey"),
        ("cmd+space", "hotkey"),
        ("right_cmd+space", "hotkey"),
        ("right_cmd+q", "hotkey"),
        ("right_ctrl+space", "hotkey"),
        ("r", "hotkey"),
        ("right_shift", "hotkey"),
        ("right_option", "retry_hotkey"),
        ("right_shift+right_shift", "hotkey"),
    ],
)
def test_invalid_or_dangerous_shortcuts_are_rejected(value, field):
    with pytest.raises(HotkeyValidationError):
        parse_hotkey(value, field=field)


def test_prefix_collision_is_rejected():
    with pytest.raises(HotkeyValidationError, match="shares|conflicts"):
        validate_hotkey_config(
            {
                "hotkey": RECOMMENDED_RECORD_HOTKEY,
                **RECOMMENDED_ACTION_HOTKEYS,
                "continuous_hotkey": "right_option+right_shift+f8",
            }
        )


def test_recommended_shortcut_does_not_collide_with_action_shortcuts():
    normalized = validate_hotkey_config(
        {
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            **RECOMMENDED_ACTION_HOTKEYS,
        }
    )

    assert normalized["hotkey"] == RECOMMENDED_RECORD_HOTKEY
    recording_keys = parse_hotkey(normalized["hotkey"]).keycodes
    for field in ("rewrite_hotkey", "retry_hotkey", "cancel_hotkey"):
        spec = parse_hotkey(normalized[field], field=field)
        assert len(spec.tokens) == 2
        assert all(token in MODIFIER_TOKENS for token in spec.tokens)
        assert not recording_keys.intersection(spec.keycodes)
        assert "right_cmd" not in spec.tokens
        assert "right_ctrl" not in spec.tokens


@pytest.mark.parametrize(
    "value",
    [
        "cmd+right_cmd",
        "ctrl+right_ctrl",
        "option+right_option",
        "shift+right_shift",
    ],
)
def test_same_modifier_family_chords_are_rejected(value):
    with pytest.raises(HotkeyValidationError, match="both sides"):
        parse_hotkey(value, field="retry_hotkey")


def test_recording_and_action_hotkeys_must_be_disjoint():
    with pytest.raises(HotkeyValidationError, match="shares a recording key"):
        validate_hotkey_config(
            {
                "hotkey": RECOMMENDED_RECORD_HOTKEY,
                **RECOMMENDED_ACTION_HOTKEYS,
                "rewrite_hotkey": "ctrl+right_shift",
            }
        )

    with pytest.raises(HotkeyValidationError, match="modifier family"):
        validate_hotkey_config(
            {
                "hotkey": RECOMMENDED_RECORD_HOTKEY,
                **RECOMMENDED_ACTION_HOTKEYS,
                "cancel_hotkey": "option+shift",
            }
        )


def test_legacy_single_modifier_load_is_runtime_only():
    with pytest.raises(HotkeyValidationError, match="single modifier"):
        parse_hotkey("right_cmd", field="hotkey")

    legacy = parse_hotkey(
        "right_cmd",
        field="hotkey",
        allow_legacy_single_modifier=True,
    )
    assert legacy.normalized == "right_cmd"


def test_modifier_side_detection_keeps_right_and_left_distinct():
    generic_option = 0x80000
    left_option = 0x20
    right_option = 0x40

    assert modifier_is_pressed(61, generic_option | right_option)
    assert not modifier_is_pressed(61, generic_option | left_option)
    assert modifier_is_pressed(61, generic_option)  # KVM/generic fallback


def test_fn_modifier_uses_the_macos_secondary_fn_flag():
    assert modifier_is_pressed(FN_KEYCODE, FN_MODIFIER_MASK)
    assert not modifier_is_pressed(FN_KEYCODE, 0)


class _FakeEvent:
    def __init__(self, event_type, keycode, flags=0, repeat=False):
        self._event_type = event_type
        self._keycode = keycode
        self._flags = flags
        self._repeat = repeat

    def type(self):
        return self._event_type

    def keyCode(self):
        return self._keycode

    def modifierFlags(self):
        return self._flags

    def isARepeat(self):
        return self._repeat


class _ImmediateThread:
    def __init__(self, target, daemon=True):
        self.target = target
        self.daemon = daemon

    def start(self):
        self.target()


def _install_fake_appkit(monkeypatch):
    handlers = {}

    class FakeNSEvent:
        @staticmethod
        def addGlobalMonitorForEventsMatchingMask_handler_(mask, handler):
            handlers["global"] = handler
            return "global-monitor"

        @staticmethod
        def addLocalMonitorForEventsMatchingMask_handler_(mask, handler):
            handlers["local"] = handler
            return "local-monitor"

    fake_appkit = types.SimpleNamespace(
        NSEvent=FakeNSEvent,
        NSKeyDown=10,
        NSKeyUp=11,
        NSFlagsChanged=12,
    )
    monkeypatch.setitem(sys.modules, "AppKit", fake_appkit)
    return handlers


def test_native_recording_listener_ignores_right_cmd_and_reloads_live(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)

    class Engine:
        config = {
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            "hotkey_mode": "push_to_talk",
        }
        is_recording = False
        starts = 0
        stops = 0
        _on_hotkey_reset = None

        def start_recording(self, from_hotkey=False):
            assert from_hotkey is True
            self.is_recording = True
            self.starts += 1

        def stop_and_process(self):
            self.is_recording = False
            self.stops += 1

    engine = Engine()
    app.setup_hotkey(engine)
    handle = handlers["global"]

    # Codex's Right Command must not start SGH Voice anymore.
    handle(_FakeEvent(12, 54, 0x100000 | 0x10))
    assert engine.starts == 0

    # Right Option + Right Shift starts on the second modifier and stops on release.
    option_flags = 0x80000 | 0x40
    both_flags = option_flags | 0x20000 | 0x4
    handle(_FakeEvent(12, 61, option_flags))
    handle(_FakeEvent(12, 60, both_flags))
    assert engine.starts == 1
    assert engine.is_recording is True

    handle(_FakeEvent(12, 60, option_flags))
    assert engine.stops == 1
    assert engine.is_recording is False

    # A Dashboard change is picked up by the already-registered monitor.
    engine.config = {
        "hotkey": "right_ctrl+right_shift",
        "hotkey_mode": "push_to_talk",
    }
    ctrl_flags = 0x40000 | 0x2000
    ctrl_shift_flags = ctrl_flags | 0x20000 | 0x4
    handle(_FakeEvent(12, 62, ctrl_flags))
    handle(_FakeEvent(12, 60, ctrl_shift_flags))
    assert engine.starts == 2


def test_native_recording_listener_supports_fn_and_right_shift(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)

    class Engine:
        config = {
            "hotkey": "right_fn+right_shift",
            "hotkey_mode": "push_to_talk",
        }
        is_recording = False
        starts = 0
        stops = 0
        _on_hotkey_reset = None

        def start_recording(self, from_hotkey=False):
            assert from_hotkey is True
            self.is_recording = True
            self.starts += 1

        def stop_and_process(self):
            self.is_recording = False
            self.stops += 1

    engine = Engine()
    app.setup_hotkey(engine)
    handle = handlers["global"]

    handle(_FakeEvent(12, FN_KEYCODE, FN_MODIFIER_MASK))
    both_flags = FN_MODIFIER_MASK | 0x20000 | 0x4
    handle(_FakeEvent(12, 60, both_flags))
    assert engine.starts == 1
    assert engine.is_recording is True

    handle(_FakeEvent(12, 60, FN_MODIFIER_MASK))
    assert engine.stops == 1
    assert engine.is_recording is False


def test_native_recording_listener_ignores_ptt_while_continuous(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)

    class Engine:
        config = {
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            "hotkey_mode": "push_to_talk",
        }
        is_recording = True
        _continuous_active = True
        _on_hotkey_reset = None
        starts = 0
        stops = 0

        def start_recording(self, from_hotkey=False):
            self.starts += 1

        def stop_and_process(self):
            self.stops += 1

    engine = Engine()
    app.setup_hotkey(engine)
    handle = handlers["global"]
    option = 0x80000 | 0x40
    shift = 0x20000 | 0x4

    handle(_FakeEvent(12, 61, option))
    handle(_FakeEvent(12, 60, option | shift))
    handle(_FakeEvent(12, 60, option))
    handle(_FakeEvent(12, 61, 0))

    assert engine.starts == 0
    assert engine.stops == 0
    assert engine.is_recording is True
    assert engine._continuous_active is True


def test_pynput_fallback_reset_clears_stale_pressed_state(monkeypatch):
    import app

    keys = types.SimpleNamespace(
        cmd_l=object(),
        cmd_r=object(),
        alt_l=object(),
        alt_r=object(),
        ctrl_l=object(),
        ctrl_r=object(),
        shift_l=object(),
        shift_r=object(),
        space=object(),
        esc=object(),
    )

    class Listener:
        def __init__(self, on_press, on_release):
            self.on_press = on_press
            self.on_release = on_release
            self.started = False

        def start(self):
            self.started = True

    keyboard = types.SimpleNamespace(Key=keys, Listener=Listener)
    monkeypatch.setitem(sys.modules, "pynput", types.SimpleNamespace(keyboard=keyboard))

    class Engine:
        config = {
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            "hotkey_mode": "push_to_talk",
        }
        is_recording = False
        starts = 0
        _on_hotkey_reset = None

        def start_recording(self, from_hotkey=False):
            assert from_hotkey is True
            self.is_recording = True
            self.starts += 1

        def stop_and_process(self):
            self.is_recording = False

    engine = Engine()
    listener = app._setup_hotkey_pynput(engine)
    assert listener.started is True

    listener.on_press(keys.alt_r)
    listener.on_press(keys.shift_r)
    assert engine.starts == 1

    # Simulate watchdog recovery after a swallowed key-up.
    engine.is_recording = False
    engine._on_hotkey_reset()
    listener.on_press(keys.alt_r)
    listener.on_press(keys.shift_r)
    assert engine.starts == 2


def test_action_arbiter_releases_once_blocks_prefixes_and_gates_ptt(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)
    calls = []
    engine = types.SimpleNamespace(
        config={
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            **RECOMMENDED_ACTION_HOTKEYS,
        },
        is_recording=False,
        _continuous_active=False,
    )

    monitors = app._setup_dynamic_action_hotkey(
        engine,
        "rewrite_hotkey",
        lambda: calls.append("rewrite"),
        "Quick-Rewrite",
    )
    app._setup_dynamic_action_hotkey(
        engine,
        "retry_hotkey",
        lambda: calls.append("retry"),
        "Retry",
    )
    app._setup_dynamic_action_hotkey(
        engine,
        "cancel_hotkey",
        lambda: calls.append("cancel"),
        "Cancel",
    )
    assert monitors == ("global-monitor", "local-monitor")
    handle = handlers["global"]

    ctrl = 0x40000 | 0x1
    option = 0x80000 | 0x20
    shift = 0x20000 | 0x2

    # Modifier-only actions arm on press and run exactly once on release.
    handle(_FakeEvent(12, 59, ctrl))
    handle(_FakeEvent(12, 58, ctrl | option))
    assert calls == []
    handle(_FakeEvent(12, 58, ctrl))
    assert calls == ["rewrite"]
    handle(_FakeEvent(12, 59, 0))

    # A third key turns the chord into a normal app/VoiceOver shortcut prefix.
    handle(_FakeEvent(12, 59, ctrl))
    handle(_FakeEvent(12, 58, ctrl | option))
    handle(_FakeEvent(10, 40, ctrl | option))  # K down
    handle(_FakeEvent(11, 40, ctrl | option))
    handle(_FakeEvent(12, 58, ctrl))
    handle(_FakeEvent(12, 59, 0))
    assert calls == ["rewrite"]

    # Modifier rollover must not change Rewrite into Retry in one gesture.
    handle(_FakeEvent(12, 59, ctrl))
    handle(_FakeEvent(12, 58, ctrl | option))
    handle(_FakeEvent(12, 56, ctrl | option | shift))
    handle(_FakeEvent(12, 58, ctrl | shift))
    handle(_FakeEvent(12, 56, ctrl))
    handle(_FakeEvent(12, 59, 0))
    assert calls == ["rewrite"]

    # During PTT, non-cancel actions are rejected at event time; Cancel remains.
    engine.is_recording = True
    handle(_FakeEvent(12, 59, ctrl))
    handle(_FakeEvent(12, 58, ctrl | option))
    handle(_FakeEvent(12, 58, ctrl))
    handle(_FakeEvent(12, 59, 0))
    assert calls == ["rewrite"]

    cmd = 0x100000 | 0x8
    handle(_FakeEvent(12, 59, ctrl))
    handle(_FakeEvent(12, 55, ctrl | cmd))
    handle(_FakeEvent(12, 55, ctrl))
    handle(_FakeEvent(12, 59, 0))
    assert calls == ["rewrite", "cancel"]


def test_continuous_action_can_turn_off_while_recording(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)
    calls = []
    engine = types.SimpleNamespace(
        config={
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            **RECOMMENDED_ACTION_HOTKEYS,
            "continuous_hotkey": "cmd+option",
        },
        is_recording=True,
        _continuous_active=True,
    )
    app._setup_dynamic_action_hotkey(
        engine,
        "continuous_hotkey",
        lambda: calls.append("continuous"),
        "Continuous-mode",
    )
    handle = handlers["global"]
    cmd = 0x100000 | 0x8
    option = 0x80000 | 0x20

    handle(_FakeEvent(12, 55, cmd))
    handle(_FakeEvent(12, 58, cmd | option))
    handle(_FakeEvent(12, 58, cmd))
    handle(_FakeEvent(12, 55, 0))

    assert calls == ["continuous"]


def test_cancel_marks_recording_before_queued_callback_on_generic_kvm(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    queued = []

    class QueuedThread:
        def __init__(self, target, daemon=True):
            self.target = target

        def start(self):
            queued.append(self.target)

    monkeypatch.setattr(app.threading, "Thread", QueuedThread)
    token = 123.0
    marks = []
    calls = []

    class Engine:
        config = {
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            **RECOMMENDED_ACTION_HOTKEYS,
        }
        is_recording = True
        _continuous_active = False
        _record_start_ts = token

        def mark_cancel_intent(self, value):
            marks.append(value)
            return value == token

        def cancel_current(self, recording_token=None):
            calls.append(recording_token)

    engine = Engine()
    app._setup_dynamic_action_hotkey(
        engine,
        "cancel_hotkey",
        engine.cancel_current,
        "Cancel",
    )
    handle = handlers["global"]

    # Generic-only flags deliberately omit all left/right device bits.
    option = 0x80000
    shift = 0x20000
    ctrl = 0x40000
    cmd = 0x100000
    ptt = option | shift
    handle(_FakeEvent(12, 61, option))
    handle(_FakeEvent(12, 60, ptt))
    handle(_FakeEvent(12, 59, ptt | ctrl))
    handle(_FakeEvent(12, 55, ptt | ctrl | cmd))
    handle(_FakeEvent(12, 55, ptt | ctrl))

    # Intent is synchronous even though the user-facing callback is queued.
    assert marks == [token]
    assert calls == []
    assert len(queued) == 1

    engine.is_recording = False  # PTT stop wins the scheduling race.
    queued.pop()()
    assert calls == [token]


def test_generic_kvm_ptt_release_clears_blocked_action_state(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)
    calls = []
    engine = types.SimpleNamespace(
        config={
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            **RECOMMENDED_ACTION_HOTKEYS,
        },
        is_recording=True,
        _continuous_active=False,
        _record_start_ts=1.0,
    )
    app._setup_dynamic_action_hotkey(
        engine,
        "rewrite_hotkey",
        lambda: calls.append("rewrite"),
        "Quick-Rewrite",
    )
    handle = handlers["global"]
    option = 0x80000
    shift = 0x20000
    ctrl = 0x40000
    ptt = option | shift

    handle(_FakeEvent(12, 61, option))
    handle(_FakeEvent(12, 60, ptt))
    handle(_FakeEvent(12, 59, ptt | ctrl))
    handle(_FakeEvent(12, 58, ptt | ctrl))
    # Left Option release is ambiguous while Right Option remains held.
    handle(_FakeEvent(12, 58, ptt | ctrl))
    handle(_FakeEvent(12, 59, ptt))
    assert calls == []

    # Releasing the recording family removes only stale action state.
    handle(_FakeEvent(12, 60, option))
    handle(_FakeEvent(12, 61, 0))
    engine.is_recording = False

    handle(_FakeEvent(12, 59, ctrl))
    handle(_FakeEvent(12, 58, ctrl | option))
    handle(_FakeEvent(12, 58, ctrl))
    handle(_FakeEvent(12, 59, 0))
    assert calls == ["rewrite"]


def test_cancel_arbiter_captures_stopping_token_after_ptt_release(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)
    token = 321.0
    calls = []

    class Engine:
        config = {
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            **RECOMMENDED_ACTION_HOTKEYS,
        }
        is_recording = False
        _continuous_active = False
        _record_start_ts = None
        _stopping_recording_token = token

        def mark_cancel_intent(self, value):
            return value == token

        def cancel_current(self, recording_token=None):
            calls.append(recording_token)

    engine = Engine()
    app._setup_dynamic_action_hotkey(
        engine,
        "cancel_hotkey",
        engine.cancel_current,
        "Cancel",
    )
    handle = handlers["global"]
    ctrl = 0x40000 | 0x1
    cmd = 0x100000 | 0x8

    handle(_FakeEvent(12, 59, ctrl))
    handle(_FakeEvent(12, 55, ctrl | cmd))
    handle(_FakeEvent(12, 55, ctrl))
    handle(_FakeEvent(12, 59, 0))

    assert calls == [token]


def test_cancel_arbiter_captures_latest_processing_token(monkeypatch):
    import app

    handlers = _install_fake_appkit(monkeypatch)
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)
    older_token = 320.0
    latest_token = 321.0
    calls = []

    class Engine:
        config = {
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            **RECOMMENDED_ACTION_HOTKEYS,
        }
        is_recording = False
        _continuous_active = False

        def latest_cancellable_recording_token(self):
            return latest_token

        def mark_cancel_intent(self, value):
            return value in {older_token, latest_token}

        def cancel_current(self, recording_token=None):
            calls.append(recording_token)

    engine = Engine()
    app._setup_dynamic_action_hotkey(
        engine,
        "cancel_hotkey",
        engine.cancel_current,
        "Cancel",
    )
    handle = handlers["global"]
    ctrl = 0x40000 | 0x1
    cmd = 0x100000 | 0x8

    handle(_FakeEvent(12, 59, ctrl))
    handle(_FakeEvent(12, 55, ctrl | cmd))
    handle(_FakeEvent(12, 55, ctrl))
    handle(_FakeEvent(12, 59, 0))

    assert calls == [latest_token]


def test_cancel_token_drops_audio_during_ptt_stop_gap():
    import app

    entered_stop = app.threading.Event()
    release_stop = app.threading.Event()
    transcribed = []
    token = 456.0

    class Recorder:
        def stop(self):
            entered_stop.set()
            assert release_stop.wait(timeout=2)
            return [0.1, 0.2], None, 1.0

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine.is_recording = True
    engine.is_processing = False
    engine._record_start_ts = token
    engine._active_recording_tokens = {token}
    engine._cancelled_recording_tokens = set()
    engine._stopping_recording_token = None
    engine._processing_recording_tokens = []
    engine._inflight_transcriptions = 0
    engine._cancel_watchdog = lambda: None
    engine._on_status_change = None
    engine.recorder = Recorder()
    engine.overlay = types.SimpleNamespace(show=lambda _state: None)
    engine.transcriber = types.SimpleNamespace(
        transcribe=lambda *args, **kwargs: transcribed.append(True)
    )
    engine.config = {}

    worker = app.threading.Thread(target=engine.stop_and_process)
    worker.start()
    assert entered_stop.wait(timeout=2)
    assert engine.is_recording is False

    assert engine.mark_cancel_intent(token) is True
    release_stop.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert transcribed == []
    assert token not in engine._active_recording_tokens
    assert token not in engine._cancelled_recording_tokens


def test_old_stop_cannot_clear_a_new_recording_token():
    import app

    entered_watchdog_cancel = app.threading.Event()
    release_watchdog_cancel = app.threading.Event()
    old_token = 654.0
    new_token = 655.0

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine.is_recording = True
    engine.is_processing = False
    engine._record_start_ts = old_token
    engine._stopping_recording_token = None
    engine._active_recording_tokens = {old_token}
    engine._cancelled_recording_tokens = set()
    engine._processing_recording_tokens = []
    engine._inflight_transcriptions = 0
    engine._on_status_change = None
    engine.overlay = types.SimpleNamespace(show=lambda _state: None)
    engine.recorder = types.SimpleNamespace(
        stop=lambda: (None, None, 0.0),
        last_error=None,
    )

    def cancel_watchdog():
        entered_watchdog_cancel.set()
        assert release_watchdog_cancel.wait(timeout=2)

    engine._cancel_watchdog = cancel_watchdog
    worker = app.threading.Thread(target=engine.stop_and_process)
    worker.start()
    assert entered_watchdog_cancel.wait(timeout=2)

    with engine._state_lock:
        engine.is_recording = True
        engine._record_start_ts = new_token
        engine._active_recording_tokens.add(new_token)
    release_watchdog_cancel.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert engine.is_recording is True
    assert engine._record_start_ts == new_token
    assert new_token in engine._active_recording_tokens


def test_cancel_token_prevents_paste_after_transcription_started(monkeypatch):
    import app

    entered_transcribe = app.threading.Event()
    release_transcribe = app.threading.Event()
    pasted = []
    token = 789.0

    def transcribe(*_args, **_kwargs):
        entered_transcribe.set()
        assert release_transcribe.wait(timeout=2)
        return {"final": "must not paste", "process_time": 0.01}

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._paste_lock = app.threading.Lock()
    engine.is_recording = False
    engine.is_processing = False
    engine._processing_start_ts = None
    engine._record_start_ts = None
    engine._stopping_recording_token = token
    engine._processing_recording_tokens = []
    engine._active_recording_tokens = {token}
    engine._cancelled_recording_tokens = set()
    engine._cancel_inflight = False
    engine._inflight_transcriptions = 0
    engine._on_status_change = None
    engine.overlay = types.SimpleNamespace(
        show=lambda _state: None,
        update_stage=lambda _stage: None,
        show_transcript=lambda *_args, **_kwargs: None,
    )
    engine.transcriber = types.SimpleNamespace(transcribe=transcribe)
    engine.config = {
        "auto_paste": True,
        "enable_transcript_overlay": False,
    }
    monkeypatch.setattr(app, "paste_text", lambda value: pasted.append(value))
    monkeypatch.setattr(app, "update_stats", lambda *_args, **_kwargs: None)

    worker = app.threading.Thread(
        target=engine._transcribe_and_paste,
        args=([0.1], None, 1.0, "dictate", "", token),
    )
    worker.start()
    assert entered_transcribe.wait(timeout=2)
    assert engine.mark_cancel_intent(token) is True
    release_transcribe.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert pasted == []
    assert token not in engine._active_recording_tokens
    assert token not in engine._cancelled_recording_tokens


def test_rapid_restart_waits_for_recorder_stop_and_starts_cleanly():
    import app

    entered_stop = app.threading.Event()
    release_stop = app.threading.Event()
    start_calls = []
    start_results = []
    old_token = 901.0

    class Recorder:
        last_error = None

        def stop(self):
            entered_stop.set()
            assert release_stop.wait(timeout=2)
            return None, None, 0.0

        def start(self, on_done=None, on_error=None):
            start_calls.append((on_done, on_error))
            return True

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine._paste_lock = app.threading.Lock()
    engine.is_recording = True
    engine.is_processing = False
    engine._processing_start_ts = None
    engine._record_start_ts = old_token
    engine._stopping_recording_token = None
    engine._processing_recording_tokens = []
    engine._active_recording_tokens = {old_token}
    engine._cancelled_recording_tokens = set()
    engine._cancel_inflight = False
    engine._inflight_transcriptions = 0
    engine._on_status_change = None
    engine._watchdog_timer = None
    engine._cancel_watchdog = lambda: None
    engine._arm_watchdog = lambda from_hotkey=False: None
    engine.overlay = types.SimpleNamespace(show=lambda _state: None)
    engine.recorder = Recorder()
    engine.config = {}

    stopping = app.threading.Thread(target=engine.stop_and_process)
    stopping.start()
    assert entered_stop.wait(timeout=2)
    assert engine.is_recording is False

    restarting = app.threading.Thread(
        target=lambda: start_results.append(
            engine.start_recording(from_hotkey=True)
        )
    )
    restarting.start()
    assert restarting.is_alive()
    assert start_calls == []

    release_stop.set()
    stopping.join(timeout=2)
    restarting.join(timeout=2)

    assert not stopping.is_alive()
    assert not restarting.is_alive()
    assert start_results == [True]
    assert len(start_calls) == 1
    assert engine.is_recording is True
    assert engine._record_start_ts != old_token
    assert old_token not in engine._active_recording_tokens
    assert engine._record_start_ts in engine._active_recording_tokens


def test_recorder_start_refusal_rolls_back_engine_state():
    import app

    class Recorder:
        def start(self, on_done=None, on_error=None):
            return False

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine.is_recording = False
    engine.is_processing = False
    engine._record_start_ts = None
    engine._active_recording_tokens = set()
    engine._cancelled_recording_tokens = set()
    engine._processing_recording_tokens = []
    engine._on_status_change = None
    engine.recorder = Recorder()
    engine.overlay = types.SimpleNamespace(show=lambda _state: None)

    assert engine.start_recording(from_hotkey=True) is False
    assert engine.is_recording is False
    assert engine._record_start_ts is None
    assert engine._active_recording_tokens == set()


def test_start_watchdog_failure_stops_started_recorder():
    import app

    class Recorder:
        is_recording = False
        stops = 0

        def start(self, on_done=None, on_error=None):
            self.is_recording = True
            return True

        def stop(self):
            self.stops += 1
            self.is_recording = False
            return None, None, 0.0

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine.is_recording = False
    engine._record_start_ts = None
    engine._active_recording_tokens = set()
    engine._cancelled_recording_tokens = set()
    engine._processing_recording_tokens = []
    engine._on_status_change = None
    engine._watchdog_timer = None
    engine._cancel_watchdog = lambda: None
    engine._arm_watchdog = lambda **_kwargs: (_ for _ in ()).throw(
        RuntimeError("watchdog failed")
    )
    engine.recorder = Recorder()
    engine.overlay = types.SimpleNamespace(show=lambda _state: None)

    with pytest.raises(RuntimeError, match="watchdog failed"):
        engine.start_recording(from_hotkey=True)

    assert engine.recorder.stops == 1
    assert engine.recorder.is_recording is False
    assert engine.is_recording is False
    assert engine._record_start_ts is None
    assert engine._active_recording_tokens == set()


def test_recording_overlay_failure_is_non_fatal():
    import app

    class Recorder:
        is_recording = False
        stops = 0

        def start(self, on_done=None, on_error=None):
            self.is_recording = True
            return True

        def stop(self):
            self.stops += 1
            return None, None, 0.0

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine.is_recording = False
    engine._record_start_ts = None
    engine._active_recording_tokens = set()
    engine._cancelled_recording_tokens = set()
    engine._processing_recording_tokens = []
    engine._on_status_change = None
    engine._arm_watchdog = lambda **_kwargs: None
    engine.recorder = Recorder()
    engine.overlay = types.SimpleNamespace(
        show=lambda _state: (_ for _ in ()).throw(RuntimeError("overlay failed"))
    )

    assert engine.start_recording(from_hotkey=True) is True
    assert engine.is_recording is True
    assert engine.recorder.is_recording is True
    assert engine.recorder.stops == 0


def test_recorder_error_during_start_ui_setup_returns_false():
    import app

    overlay_states = []

    class Recorder:
        is_recording = False

        def start(self, on_done=None, on_error=None):
            self.is_recording = True
            return True

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine.is_recording = False
    engine._record_start_ts = None
    engine._active_recording_tokens = set()
    engine._cancelled_recording_tokens = set()
    engine._processing_recording_tokens = []
    engine._on_status_change = None
    engine._on_hotkey_reset = None
    engine._watchdog_timer = None
    engine.recorder = Recorder()
    engine.overlay = types.SimpleNamespace(show=overlay_states.append)

    def fail_during_watchdog_setup(**_kwargs):
        token = engine._record_start_ts
        engine.recorder.is_recording = False
        engine._on_recorder_error("stream failed", token)

    engine._arm_watchdog = fail_during_watchdog_setup

    assert engine.start_recording(from_hotkey=True) is False
    assert engine.is_recording is False
    assert engine._record_start_ts is None
    assert engine._active_recording_tokens == set()
    assert overlay_states[-1] == "idle"


def test_stop_and_process_ignores_continuous_stream():
    import app

    stop_calls = []
    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine.is_recording = True
    engine._continuous_active = True
    engine._record_start_ts = None
    engine.recorder = types.SimpleNamespace(
        stop=lambda: stop_calls.append(True),
    )

    assert engine.stop_and_process() is None
    assert stop_calls == []
    assert engine.is_recording is True
    assert engine._continuous_active is True


def test_continuous_cancel_blocks_final_and_inflight_segment_paste(monkeypatch):
    import app

    entered_transcribe = app.threading.Event()
    release_transcribe = app.threading.Event()
    pasted = []
    transcribe_calls = []

    class FinishedThread:
        def join(self, timeout=None):
            return None

        def is_alive(self):
            return False

    class Recorder:
        def __init__(self):
            self._thread = FinishedThread()
            self._stop_event = app.threading.Event()
            self.on_segment = None

        def start_continuous(
            self, on_segment, on_voice_change=None, on_stopped=None
        ):
            self.on_segment = on_segment
            return True

    def transcribe(*_args, **_kwargs):
        transcribe_calls.append(True)
        entered_transcribe.set()
        assert release_transcribe.wait(timeout=2)
        return {"final": "must not paste"}

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine._paste_lock = app.threading.Lock()
    engine.is_recording = False
    engine.is_processing = False
    engine._record_start_ts = None
    engine._stopping_recording_token = None
    engine._processing_recording_tokens = []
    engine._active_recording_tokens = set()
    engine._cancelled_recording_tokens = set()
    engine._continuous_active = False
    engine._continuous_cancel_event = None
    engine._on_status_change = None
    engine.recorder = Recorder()
    engine.transcriber = types.SimpleNamespace(transcribe=transcribe)
    engine.overlay = types.SimpleNamespace(
        show=lambda _state: None,
        show_transcript=lambda *_args, **_kwargs: None,
    )
    engine.config = {"auto_paste": True}
    monkeypatch.setattr(app, "paste_text", lambda value: pasted.append(value))
    monkeypatch.setattr(
        app,
        "event_ledger",
        types.SimpleNamespace(user_action=lambda *_args, **_kwargs: None),
    )

    assert engine.start_continuous_mode() is True
    segment_worker = app.threading.Thread(
        target=engine.recorder.on_segment,
        args=([0.1], 1.0),
    )
    segment_worker.start()
    assert entered_transcribe.wait(timeout=2)

    engine.cancel_current()
    release_transcribe.set()
    segment_worker.join(timeout=2)

    assert not segment_worker.is_alive()
    assert pasted == []
    assert engine.is_recording is False
    assert engine._continuous_active is False

    # Simulate Recorder's stop-time final-buffer flush.  The captured session
    # event remains cancelled even after Engine has cleared its current slot.
    engine.recorder.on_segment([0.2], 1.0)
    assert len(transcribe_calls) == 1
    assert pasted == []


def test_cancel_latest_pipeline_does_not_cancel_older_inflight(monkeypatch):
    import app

    entered = {"older": app.threading.Event(), "latest": app.threading.Event()}
    release = app.threading.Event()
    pasted = []
    older_token = 1001.0
    latest_token = 1002.0

    def transcribe(audio_input, *_args, **_kwargs):
        label = str(audio_input)
        entered[label].set()
        assert release.wait(timeout=2)
        return {"final": label, "process_time": 0.01}

    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = app.threading.RLock()
    engine._recorder_transition_lock = app.threading.RLock()
    engine._paste_lock = app.threading.Lock()
    engine.is_recording = False
    engine.is_processing = False
    engine._processing_start_ts = None
    engine._record_start_ts = None
    engine._stopping_recording_token = None
    engine._processing_recording_tokens = []
    engine._active_recording_tokens = {older_token, latest_token}
    engine._cancelled_recording_tokens = set()
    engine._cancel_inflight = False
    engine._inflight_transcriptions = 0
    engine._on_status_change = None
    engine.overlay = types.SimpleNamespace(
        show=lambda _state: None,
        update_stage=lambda _stage: None,
        show_transcript=lambda *_args, **_kwargs: None,
    )
    engine.transcriber = types.SimpleNamespace(transcribe=transcribe)
    engine.recorder = types.SimpleNamespace()
    engine.config = {
        "auto_paste": True,
        "enable_transcript_overlay": False,
    }
    monkeypatch.setattr(app, "paste_text", lambda value: pasted.append(value))
    monkeypatch.setattr(app, "update_stats", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        app,
        "event_ledger",
        types.SimpleNamespace(user_action=lambda *_args, **_kwargs: None),
    )

    older = app.threading.Thread(
        target=engine._transcribe_and_paste,
        args=("older", None, 1.0, "dictate", "", older_token),
    )
    latest = app.threading.Thread(
        target=engine._transcribe_and_paste,
        args=("latest", None, 1.0, "dictate", "", latest_token),
    )
    older.start()
    assert entered["older"].wait(timeout=2)
    latest.start()
    assert entered["latest"].wait(timeout=2)

    assert engine.latest_cancellable_recording_token() == latest_token
    engine.cancel_current()
    assert latest_token in engine._cancelled_recording_tokens
    assert older_token not in engine._cancelled_recording_tokens

    release.set()
    older.join(timeout=2)
    latest.join(timeout=2)

    assert not older.is_alive()
    assert not latest.is_alive()
    assert pasted == ["older"]
    assert engine._processing_recording_tokens == []


def test_reload_ends_active_push_to_talk_before_switching_hotkey(monkeypatch):
    import app

    engine = object.__new__(app.VoiceEngine)
    engine.config = {
        "hotkey": RECOMMENDED_RECORD_HOTKEY,
        "hotkey_mode": "push_to_talk",
    }
    engine.transcriber = types.SimpleNamespace(
        config=None,
        reset_clients=lambda: None,
    )
    engine.recorder = types.SimpleNamespace(config=None)
    engine._on_hotkey_reset = lambda: None
    engine.is_recording = True
    stops = []
    engine.stop_and_process = lambda: stops.append("stopped")

    monkeypatch.setattr(
        app,
        "load_config",
        lambda: {
            "hotkey": "right_ctrl+right_shift",
            "hotkey_mode": "push_to_talk",
        },
    )
    monkeypatch.setattr(app.threading, "Thread", _ImmediateThread)

    app.VoiceEngine.reload_config(engine)

    assert stops == ["stopped"]


def test_config_api_validates_normalizes_and_live_reloads(monkeypatch):
    import config
    import dashboard

    stored = dict(config.DEFAULT_CONFIG)
    saves = []

    class Engine:
        reloads = 0

        def reload_config(self):
            self.reloads += 1

    engine = Engine()
    monkeypatch.setattr(dashboard, "_engine", engine)
    monkeypatch.setattr(dashboard, "load_config", lambda: dict(stored))

    def fake_save(value):
        stored.clear()
        stored.update(value)
        saves.append(dict(value))

    monkeypatch.setattr(dashboard, "save_config", fake_save)
    client = dashboard.app.test_client()

    response = client.post(
        "/api/config", json={"hotkey": "right_alt + right_shift"}
    )
    assert response.status_code == 200
    assert response.get_json()["hotkeys_applied"] is True
    assert stored["hotkey"] == RECOMMENDED_RECORD_HOTKEY
    assert engine.reloads == 1
    assert len(saves) == 1

    response = client.post(
        "/api/config", json={"hotkey": "right_option+banana"}
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_hotkey"
    assert engine.reloads == 1
    assert len(saves) == 1

    response = client.post("/api/config", json={"hotkey": "right_option"})
    assert response.status_code == 400
    assert "single modifier" in response.get_json()["error"]
    assert engine.reloads == 1
    assert len(saves) == 1

    response = client.post(
        "/api/config",
        json={
            "hotkey": RECOMMENDED_RECORD_HOTKEY,
            "continuous_hotkey": "right_option+right_shift+f8",
        },
    )
    assert response.status_code == 400
    assert "shares" in response.get_json()["error"]
    assert engine.reloads == 1
    assert len(saves) == 1

    response = client.post(
        "/api/config", json={"retry_hotkey": "option+right_option"}
    )
    assert response.status_code == 400
    assert "both sides" in response.get_json()["error"]
    assert engine.reloads == 1
    assert len(saves) == 1

    response = client.post("/api/config", json={"hotkey_mode": "sometimes"})
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_hotkey_mode"
    assert engine.reloads == 1
    assert len(saves) == 1


def test_config_api_accepts_human_readable_right_fn_alias(monkeypatch):
    import config
    import dashboard

    stored = dict(config.DEFAULT_CONFIG)

    class Engine:
        reloads = 0

        def reload_config(self):
            self.reloads += 1

    engine = Engine()
    monkeypatch.setattr(dashboard, "_engine", engine)
    monkeypatch.setattr(dashboard, "load_config", lambda: dict(stored))
    monkeypatch.setattr(dashboard, "save_config", lambda value: stored.update(value))

    response = dashboard.app.test_client().post(
        "/api/config", json={"hotkey": "Right Fn + Right Shift"}
    )

    assert response.status_code == 200
    assert response.get_json()["hotkeys_applied"] is True
    assert response.get_json()["normalized_hotkeys"] == {
        "hotkey": FN_RECORD_HOTKEY
    }
    assert stored["hotkey"] == FN_RECORD_HOTKEY
    assert engine.reloads == 1


def test_config_api_requires_legacy_main_to_move_off_conflicting_family(monkeypatch):
    import config
    import dashboard

    stored = {
        **config.DEFAULT_CONFIG,
        "hotkey": "right_cmd",
    }
    monkeypatch.setattr(dashboard, "load_config", lambda: dict(stored))
    monkeypatch.setattr(dashboard, "save_config", lambda value: stored.update(value))
    monkeypatch.setattr(dashboard, "_engine", None)

    response = dashboard.app.test_client().post(
        "/api/config",
        json={"rewrite_hotkey": RECOMMENDED_ACTION_HOTKEYS["rewrite_hotkey"]},
    )

    assert response.status_code == 400
    assert "modifier family" in response.get_json()["error"]
    assert stored["hotkey"] == "right_cmd"


def test_config_api_reports_keychain_persistence_failure(monkeypatch):
    import config
    import dashboard

    stored = dict(config.DEFAULT_CONFIG)

    class Engine:
        reloads = 0

        def reload_config(self):
            self.reloads += 1

    engine = Engine()
    monkeypatch.setattr(dashboard, "_engine", engine)
    monkeypatch.setattr(dashboard, "load_config", lambda: dict(stored))

    def fail_save(_value):
        raise config.ConfigSaveError("failed to update key in macOS Keychain")

    monkeypatch.setattr(dashboard, "save_config", fail_save)
    response = dashboard.app.test_client().post(
        "/api/config", json={"hotkey_mode": "toggle"}
    )

    assert response.status_code == 503
    assert response.get_json()["code"] == "config_save_failed"
    assert engine.reloads == 0


def test_hotkey_settings_render_editable_fields_and_conflict_guidance():
    from pathlib import Path

    source = (
        Path(__file__).parents[1]
        / "static/js/pages/settings/hotkeys.js"
    ).read_text(encoding="utf-8")

    assert "type: 'text'" in source
    assert "dirty.set(row.key" in source
    assert RECOMMENDED_RECORD_HOTKEY in source
    assert FN_RECORD_HOTKEY in source
    assert "settings.hotkeys.apply.fn" in source
    assert "settings.hotkeys.conflict.right_cmd" in source
