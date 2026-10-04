"""Headless UI boundary tests: no GUI, microphone, provider, or credential writes."""
import threading

import pytest

from windows_client.controller import WINDOWS_DEFAULTS
from windows_client.hotkeys import Hotkey
from windows_client.ui import LABELS, WindowsApp, result_message, settings_snapshot


class Value:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Widget:
    def __init__(self):
        self.options = {}
        self.text = ""

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def get(self, *_):
        return self.text

    def delete(self, *_):
        self.text = ""

    def insert(self, _index, text):
        self.text = text


class Root:
    def __init__(self):
        self.calls = []

    def title(self, title):
        self.calls.append(("title", title))

    def protocol(self, *_):
        pass

    def after(self, *_):
        self.calls.append(("after", threading.get_ident()))
        return "tick"

    def after_cancel(self, *_):
        self.calls.append(("after_cancel",))

    def destroy(self):
        self.calls.append(("destroy",))


class Controller:
    def __init__(self, config, on_event, native):
        self.config = config
        self.on_event = on_event
        self.state = "idle"
        self.last_text = ""
        self.toggles = []
        self.cancelled = False
        self.closed = False

    def toggle(self, target=None):
        self.toggles.append(target)
        self.state = "recording" if self.state == "idle" else "processing"
        self.last_text = ""
        return True

    def cancel(self):
        self.cancelled = True
        self.last_text = ""
        self.state = "idle"

    def close(self):
        self.closed = True
        self.state = "closed"

    def apply_config(self, config):
        self.config = config


class Native:
    def __init__(self):
        self.copied = []
        self.capture_threads = []
        self.target = object()

    def capture_target(self):
        self.capture_threads.append(threading.get_ident())
        return self.target

    def copy_text(self, text):
        self.copied.append(text)


class Hotkeys:
    def __init__(self, on_toggle, on_cancel, on_error):
        self.on_toggle, self.on_cancel, self.on_error = on_toggle, on_cancel, on_error
        self.stopped = False
        self.pair = None

    def start(self, toggle, cancel):
        self.pair = (toggle, cancel)

    def stop(self):
        self.stopped = True


class HeadlessApp(WindowsApp):
    def _build(self):
        self._labels = []
        self._setting_widgets = []
        self.vars = {
            field: Value(self.config[field]) for field in
            (*WINDOWS_DEFAULTS.keys(), "language", "ui_language")
        }
        self.key_var = Value(self._key_drafts[self._key_provider])
        self.status, self.notice, self.hotkey_notice = Value(), Value(), Value()
        self.record_button, self.cancel_button, self.save_button = Widget(), Widget(), Widget()
        self.meter, self.result, self.copy_button = Widget(), Widget(), Widget()


@pytest.fixture
def app():
    saved = []
    instance = HeadlessApp(
        Root(), {**WINDOWS_DEFAULTS, "language": "auto", "ui_language": "en"},
        controller_factory=Controller, native=Native(), hotkeys_factory=Hotkeys,
        save_config=saved.append, validate_hotkey=Hotkey.parse,
    )
    instance.saved = saved
    return instance


def test_all_languages_have_same_messages():
    assert set(LABELS["en"]) == set(LABELS["zh-TW"]) == set(LABELS["ja"])


def test_worker_events_touch_no_ui_until_pumped(app):
    app.controller.state = "recording"
    calls = list(app.root.calls)
    worker = threading.Thread(target=lambda: app.enqueue("level", 0.4))
    worker.start()
    worker.join()
    assert app.root.calls == calls
    assert "value" not in app.meter.options or app.meter.options["value"] == 0
    app._pump()
    assert app.meter.options["value"] == 0.4


def test_global_shortcut_captures_target_on_worker_before_queue(app):
    main_thread = threading.get_ident()
    calls = list(app.root.calls)
    worker = threading.Thread(target=app.hotkeys.on_toggle)
    worker.start()
    worker.join()
    assert app.native.capture_threads and app.native.capture_threads[0] != main_thread
    assert app.controller.toggles == []
    assert app.root.calls == calls
    app._pump()
    assert app.controller.toggles == [app.native.target]


def test_preview_button_never_captures_foreground(app):
    app._toggle_preview()
    assert app.controller.toggles == [None]
    assert app.native.capture_threads == []


def test_provider_change_revokes_consent_and_preserves_key_drafts(app):
    app.vars["windows_cloud_consent"].set(True)
    app.key_var.set("synthetic-groq-key")
    app.vars["windows_provider"].set("openai")
    app._provider_changed()
    assert app.vars["windows_cloud_consent"].get() is False
    assert app.key_var.get() == ""
    app.key_var.set("synthetic-openai-key")
    app.vars["windows_provider"].set("groq")
    app._provider_changed()
    assert app.key_var.get() == "synthetic-groq-key"
    assert app._key_drafts["openai"] == "synthetic-openai-key"


def test_save_failure_does_not_apply_or_echo_secret(app):
    original = dict(app.controller.config)
    def fail(_config):
        raise RuntimeError("do-not-display-this-secret")
    app.save_config = fail
    app.vars["windows_cloud_consent"].set(True)
    app._save()
    assert app.controller.config == original
    assert app.notice.get() == LABELS["en"]["save_failed"]
    assert "do-not-display" not in app.notice.get()


def test_settings_only_save_when_idle(app):
    app.controller.state = "processing"
    app._save()
    assert app.saved == []
    assert app.notice.get() == LABELS["en"]["busy"]


def test_duplicate_normalized_shortcuts_rejected_before_save(app):
    app.vars["windows_toggle_hotkey"].set("Ctrl+Alt+F9")
    app.vars["windows_cancel_hotkey"].set("Alt+Control+F09")
    app._save()
    assert app.saved == []
    assert app.notice.get() == LABELS["en"]["invalid_settings"]


def test_successful_save_updates_language_and_hotkeys(app):
    previous = app.hotkeys
    app.vars["ui_language"].set("ja")
    app.vars["windows_toggle_hotkey"].set("Ctrl+Alt+F8")
    app._save()
    assert app.saved[0]["ui_language"] == "ja"
    assert app.lang == "ja"
    assert previous.stopped
    assert app.hotkeys.pair == ("Ctrl+Alt+F8", "Ctrl+Alt+F10")
    assert app.notice.get() == LABELS["ja"]["saved"]


def test_registration_failure_visible_and_preview_still_works(app):
    def fail(**kwargs):
        raise RuntimeError("hotkey in use")
    app.hotkeys_factory = fail
    app._start_hotkeys()
    assert app.hotkey_notice.get() == LABELS["en"]["hotkeys_failed"]
    app._toggle_preview()
    assert app.controller.toggles == [None]


def test_changed_target_result_remains_for_explicit_copy(app):
    app.controller.last_text = "Synthetic test text"
    app.enqueue("result", {"text": "Synthetic test text", "insertion": {"success": False, "reason": "target_changed"}})
    app._pump()
    assert app.result.text == "Synthetic test text"
    assert app.notice.get() == LABELS["en"]["paste_fallback"]
    assert app.native.copied == []
    app._copy()
    assert app.native.copied == ["Synthetic test text"]


def test_sent_command_never_claims_verified_delivery():
    assert result_message({"insertion": {"success": True}}) == "paste_sent"
    assert "Confirm" in LABELS["en"]["paste_sent"]


def test_cancel_clears_current_and_queued_result(app):
    app.result.text = app.controller.last_text = "Synthetic result"
    app.enqueue("result", {"text": "Synthetic result", "insertion": {"success": False}})
    app._cancel()
    app._pump()
    assert app.controller.cancelled
    assert app.result.text == ""


def test_new_recording_clears_previous_and_stale_queued_result(app):
    app.result.text = app.controller.last_text = "Old result"
    app.enqueue("result", {"text": "Old result"})
    app._toggle_preview()
    app._pump()
    assert app.result.text == ""


def test_unsaved_settings_block_new_recording(app):
    app._mark_dirty()
    app._toggle_preview()
    assert app.controller.toggles == []


def test_invalid_meter_data_ignored_and_values_clamped(app):
    app.controller.state = "recording"
    for level in ("invalid", float("nan"), float("inf"), 3):
        app.enqueue("level", level)
    app._pump()
    assert app.meter.options["value"] == 1


def test_close_stops_controller_hotkeys_and_timer(app):
    app.close()
    assert app.closed and app.controller.closed and app.hotkeys.stopped
    assert ("after_cancel",) in app.root.calls
    assert app.root.calls[-1] == ("destroy",)
    calls = list(app.root.calls)
    app.enqueue("result", {"text": "too late"})
    app._pump()
    assert app.root.calls == calls


def test_close_keeps_tk_alive_until_worker_audio_cleanup_finishes(app):
    def delayed_close():
        app.controller.closed = True
        app.controller.state = "processing"
    app.controller.close = delayed_close
    app.close()
    assert app.controller.closed and app.hotkeys.stopped
    assert app.status.get() == LABELS["en"]["closed"]
    assert app.copy_button.options["state"] == "disabled"
    assert ("destroy",) not in app.root.calls
    assert app._close_after_id == "tick"
    app.close()  # The title-bar close button remains idempotent while waiting.
    assert ("destroy",) not in app.root.calls
    app.controller.state = "closed"
    app._wait_for_close()
    assert app.root.calls[-1] == ("destroy",)


def test_settings_snapshot_preserves_existing_key_and_unrelated_config():
    current = {"groq_api_key": "synthetic", "monthly_budget_jpy": 100}
    values = {**WINDOWS_DEFAULTS, "language": "auto", "ui_language": "en"}
    updated = settings_snapshot(current, values, {"groq": ""})
    assert updated["groq_api_key"] == "synthetic"
    assert updated["monthly_budget_jpy"] == 100
    assert "windows_provider" not in current
