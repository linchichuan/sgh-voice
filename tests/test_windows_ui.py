"""Headless UI boundary tests: no GUI, microphone, model downloads, or credential writes."""
import threading

import pytest

from windows_client.controller import WINDOWS_DEFAULTS
from windows_client.hotkeys import Hotkey
from windows_client.ui import LABELS, WindowsApp, candidate_lines, result_message, settings_snapshot


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
        self.undo_resets = 0
        self.visible = True

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def get(self, *_):
        return self.text

    def delete(self, *_):
        self.text = ""

    def insert(self, _index, text):
        self.text = text

    def edit_reset(self):
        self.undo_resets += 1

    def grid(self, **_kwargs):
        self.visible = True

    def grid_remove(self):
        self.visible = False


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
        self.prepare_calls = 0

    def prepare_model(self):
        self.prepare_calls += 1
        self.state = "preparing_model"

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
        defaults = {
            "windows_recognition_mode": "local", "windows_cloud_consent": False,
            "openai_api_key": "",
            "windows_model_dir": "", "windows_language": "ja", "ui_language": "en",
            "windows_lexicon_enabled": False, "windows_auto_insert": False,
            "windows_save_history": False, "windows_toggle_hotkey": "Ctrl+Alt+F9",
            "windows_cancel_hotkey": "Ctrl+Alt+F10",
        }
        self.vars = {field: Value(self.config.get(field, default)) for field, default in defaults.items()}
        self.status, self.notice, self.hotkey_notice = Value(), Value(), Value()
        self.model_notice, self.model_details, self.candidates = Value(), Value(), Value()
        self.record_button, self.cancel_button, self.save_button = Widget(), Widget(), Widget()
        self.meter, self.result, self.copy_button = Widget(), Widget(), Widget()
        self.prepare_button, self.source_button = Widget(), Widget()
        self.cloud_frame, self.local_model_frame, self.mode_notice = Widget(), Widget(), Value()


@pytest.fixture
def app():
    saved = []
    instance = HeadlessApp(
        Root(), {**WINDOWS_DEFAULTS, "windows_model_dir": "", "windows_language": "ja",
                 "windows_lexicon_enabled": False, "ui_language": "en"},
        controller_factory=Controller, native=Native(), hotkeys_factory=Hotkeys,
        save_config=saved.append, validate_hotkey=Hotkey.parse,
        model_info={"name": "Synthetic local model", "source_url": "https://example.invalid/model",
                    "size_label": "10 MiB (test fixture)"},
    )
    instance.saved = saved
    return instance


def test_all_languages_have_same_messages():
    assert set(LABELS["en"]) == set(LABELS["zh-TW"]) == set(LABELS["ja"])


def test_worker_events_touch_no_ui_until_pumped(app):
    app.controller.state = "recording"
    calls = list(app.root.calls)
    worker = threading.Thread(target=lambda: app.enqueue("level", 0.4), daemon=True)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive(), "UI event producer did not finish"
    assert app.root.calls == calls
    assert "value" not in app.meter.options or app.meter.options["value"] == 0
    app._pump()
    assert app.meter.options["value"] == 0.4


def test_global_shortcut_captures_target_on_worker_before_queue(app):
    main_thread = threading.get_ident()
    calls = list(app.root.calls)
    worker = threading.Thread(target=app.hotkeys.on_toggle, daemon=True)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive(), "Shortcut target capture did not finish"
    assert app.native.capture_threads and app.native.capture_threads[0] != main_thread
    assert app.controller.toggles == []
    assert app.root.calls == calls
    app._pump()
    assert app.controller.toggles == [app.native.target]


def test_preview_button_never_captures_foreground(app):
    app._toggle_preview()
    assert app.controller.toggles == [None]
    assert app.native.capture_threads == []


def test_save_failure_does_not_apply_or_echo_secret(app):
    original = dict(app.controller.config)
    def fail(_config):
        raise RuntimeError("do-not-display-this-secret")
    app.save_config = fail
    app.vars["windows_lexicon_enabled"].set(True)
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
    assert app.result.undo_resets == 1


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


def test_settings_snapshot_preserves_unrelated_config():
    current = {"monthly_budget_jpy": 100}
    values = {**WINDOWS_DEFAULTS, "windows_model_dir": "C:\\Models\\whisper-base",
              "windows_language": "ja", "ui_language": "en"}
    updated = settings_snapshot(current, values)
    assert updated["windows_model_dir"] == "C:\\Models\\whisper-base"
    assert updated["monthly_budget_jpy"] == 100
    assert "windows_model_dir" not in current


def test_relative_model_path_is_not_accepted_as_model_identifier(app):
    app.vars["windows_model_dir"].set("base")
    app._save()
    assert app.saved == []
    assert app.notice.get() == LABELS["en"]["invalid_settings"]


def test_no_model_download_or_source_open_on_launch_or_save(app):
    opened = []
    app.open_url = opened.append
    assert app.controller.prepare_calls == 0
    assert app.model_notice.get() == LABELS["en"]["model_required"]
    app._save()
    assert app.controller.prepare_calls == 0
    assert opened == []


def test_model_download_requires_explicit_confirmation_with_source_and_size(app):
    confirmations = []
    def decline(title, message, **kwargs):
        confirmations.append((title, message))
        return False
    app.confirm_download = decline
    app._prepare_model()
    assert app.controller.prepare_calls == 0
    assert "https://example.invalid/model" in confirmations[0][1]
    assert "10 MiB" in confirmations[0][1]
    assert "No recording or transcript is uploaded" in confirmations[0][1]
    app.confirm_download = lambda *_args, **_kwargs: True
    app._prepare_model()
    assert app.controller.prepare_calls == 1
    assert app.prepare_button.options["state"] == "disabled"
    assert app.cancel_button.options["state"] == "normal"


def test_missing_metadata_prevents_download(app):
    app.model_info = {}
    app.confirm_download = lambda *_args, **_kwargs: pytest.fail("No valid disclosure")
    app._prepare_model()
    assert app.controller.prepare_calls == 0
    assert app.notice.get() == LABELS["en"]["model_metadata_unavailable"]


def test_source_link_opens_only_on_click(app):
    opened = []
    app.open_url = opened.append
    assert opened == []
    app._open_model_source()
    assert opened == ["https://example.invalid/model"]


def test_model_directory_picker_uses_existing_directory_and_never_downloads(app):
    calls = []
    def choose(**kwargs):
        calls.append(kwargs)
        return "C:\\Models\\whisper-base"
    app.choose_directory = choose
    app._browse_model()
    assert calls[0]["mustexist"] is True
    assert app.vars["windows_model_dir"].get() == "C:\\Models\\whisper-base"
    assert app.controller.prepare_calls == 0


def test_model_ready_waits_for_idle_before_saving_path(app):
    app.controller.state = "preparing_model"
    app.enqueue("model_ready", {"path": "C:\\Models\\whisper-base"})
    app._pump()
    assert app.saved == []
    assert app._pending_model_save
    app.controller.state = "idle"
    app.enqueue("status", "idle")
    app._pump()
    assert app.saved[0]["windows_model_dir"] == "C:\\Models\\whisper-base"
    assert not app._pending_model_save
    assert app.notice.get() == LABELS["en"]["model_ready"]


def test_model_preparation_progress_never_exposes_raw_messages(app):
    app.enqueue("model_progress", {"percent": 45, "message": "private-path-or-secret"})
    app._pump()
    assert "45%" in app.model_notice.get()
    assert "private" not in app.model_notice.get()


def test_lexicon_candidates_are_opt_in_and_never_replace_transcript(app):
    text = "Synthetic wording"
    candidates = [{"preferred": "synthetic preferred", "matched_alias": "wording", "category": "term"}]
    app.controller.last_text = text
    app.enqueue("result", {"text": text, "lexicon_candidates": candidates})
    app._pump()
    assert app.result.text == text
    assert app.candidates.get() == ""
    app.config["windows_lexicon_enabled"] = True
    app.enqueue("result", {"text": text, "lexicon_candidates": candidates})
    app._pump()
    assert app.result.text == text
    assert "synthetic preferred" in app.candidates.get()
    assert app.native.copied == []
    app._copy()
    assert app.native.copied == [text]


def test_candidate_rendering_is_bounded_and_handles_bad_payloads():
    assert candidate_lines(None) == ""
    assert candidate_lines([None, {"preferred": "term"}]) == "• term"
    assert len(candidate_lines([{"preferred": "term"}] * 30).splitlines()) == 8


def test_local_model_errors_are_localized(app):
    for code in ("model_required", "model_invalid", "model_load_failed", "model_download_failed",
                 "invalid_model_path", "model_not_ready", "invalid_language", "invalid_cpu_threads",
                 "local_runtime_missing", "local_model_load_failed", "local_transcription_failed",
                 "audio_unavailable", "invalid_mode", "model_disk_space"):
        app.enqueue("error", code)
        app._pump()
        assert app.notice.get() == LABELS["en"][code]


def test_local_remains_default_with_only_explicit_openai_option(app):
    assert "windows_provider" not in app.vars
    assert "windows_polish" not in app.vars
    assert app.vars["windows_recognition_mode"].get() == "local"
    assert app.vars["windows_cloud_consent"].get() is False
    assert app.vars["windows_language"].get() == "ja"
    assert app.vars["windows_lexicon_enabled"].get() is False
    assert not app.cloud_frame.visible
    assert app.local_model_frame.visible


def select_cloud(app, *, consent=True, key="synthetic-key"):
    app.vars["windows_recognition_mode"].set("openai-cloud")
    app._mode_changed()
    app.vars["openai_api_key"].set(key)
    app.vars["windows_cloud_consent"].set(consent)


def test_cloud_startup_retains_mode_but_never_reuses_consent():
    original = {**WINDOWS_DEFAULTS, "windows_recognition_mode": "openai-cloud",
                "windows_cloud_consent": True, "openai_api_key": "synthetic-key", "ui_language": "en"}
    saved = []
    app = HeadlessApp(Root(), original, controller_factory=Controller, native=Native(),
                      hotkeys_factory=Hotkeys, save_config=saved.append)
    assert original["windows_cloud_consent"] is True
    assert app.config["windows_recognition_mode"] == "openai-cloud"
    assert app.config["windows_cloud_consent"] is False
    assert app.controller.config["windows_cloud_consent"] is False
    assert app.vars["windows_cloud_consent"].get() is False
    assert "OpenAI" in app.status.get()
    assert app._status_key == "needs_cloud_consent"
    assert saved == []
    app._toggle_preview()
    assert app.controller.toggles == []
    assert app.notice.get() == LABELS["en"]["cloud_consent_required"]


def test_cloud_requires_save_even_after_checkbox_checked(app):
    select_cloud(app)
    app._toggle_preview()
    assert app.controller.toggles == []
    assert app.notice.get() == LABELS["en"]["dirty"]


@pytest.mark.parametrize("consent,key,error", [(False, "synthetic", "cloud_consent_required"),
                                               (True, "", "cloud_key_required")])
def test_cloud_missing_requirements_never_toggle_controller(app, consent, key, error):
    select_cloud(app, consent=consent, key=key)
    app._save()
    app._toggle_preview()
    assert app.controller.toggles == []
    assert app.notice.get() == LABELS["en"][error]


def test_consent_is_session_only_and_cloud_does_not_need_local_model(app):
    select_cloud(app)
    assert app._save() is True
    assert app.saved[-1]["windows_cloud_consent"] is False
    assert app.saved[-1]["openai_api_key"] == "synthetic-key"
    assert app.controller.config["windows_cloud_consent"] is True
    assert app.controller.config["windows_model_dir"] == ""
    assert app.cloud_frame.visible
    assert not app.local_model_frame.visible
    assert app.model_notice.get() == ""
    assert app._status_key == "idle"
    app._toggle_preview()
    assert app.controller.toggles == [None]


def test_mode_switch_revokes_consent_and_cannot_silently_fallback(app):
    select_cloud(app)
    app._save()
    app.vars["windows_recognition_mode"].set("local")
    app._mode_changed()
    assert app.vars["windows_cloud_consent"].get() is False
    app._save()
    assert app.controller.config["windows_recognition_mode"] == "local"
    assert app.controller.config["windows_cloud_consent"] is False
    app.vars["windows_recognition_mode"].set("openai-cloud")
    app._mode_changed()
    assert app.vars["windows_cloud_consent"].get() is False
    app._save()
    app._toggle_preview()
    assert app.controller.toggles == []


def test_key_persistence_failure_leaves_cloud_unavailable_and_masks_error(app):
    select_cloud(app)
    def fail(_config):
        raise RuntimeError("synthetic-key in credential failure")
    app.save_config = fail
    app._save()
    assert app.controller.config["windows_recognition_mode"] == "local"
    assert app.controller.config["windows_cloud_consent"] is False
    assert "synthetic-key" not in app.notice.get()
    assert app.notice.get() == LABELS["en"]["save_failed"]
    app._toggle_preview()
    assert app.controller.toggles == []


def test_blank_key_preserves_existing_credential_as_disclosed(app):
    app.config["openai_api_key"] = "previous-synthetic-key"
    select_cloud(app, key="")
    app._save()
    assert app.controller.config["openai_api_key"] == "previous-synthetic-key"
    assert app.saved[-1]["openai_api_key"] == "previous-synthetic-key"


def test_cloud_processing_and_cancel_disclosure_are_mode_aware(app):
    select_cloud(app)
    app._save()
    app.controller.state = "processing"
    app._render_state()
    assert app._status_key == "processing_cloud"
    assert "OpenAI" in app.status.get()
    assert LABELS["en"]["processing"] not in app.status.get()
    app._cancel()
    assert app.controller.cancelled
    assert app.notice.get() == LABELS["en"]["cloud_cancelled"]


def test_cloud_recording_cancel_does_not_claim_audio_was_sent(app):
    select_cloud(app)
    app._save()
    app.controller.state = "recording"
    app._cancel()
    assert app.notice.get() == ""


def test_cloud_errors_do_not_switch_recognition_mode(app):
    select_cloud(app)
    app._save()
    for code in ("cloud_key_required", "cloud_audio_invalid", "cloud_request_failed",
                 "cloud_auth_failed", "cloud_rate_limited", "cloud_timeout", "cloud_invalid_response"):
        app.enqueue("error", code)
        app._pump()
        assert app.notice.get() == LABELS["en"][code]
        assert app.config["windows_recognition_mode"] == "openai-cloud"
        assert app.controller.prepare_calls == 0


def test_cloud_model_controls_cannot_trigger_download_or_folder_picker(app):
    select_cloud(app)
    app._save()
    app.confirm_download = lambda *_args, **_kwargs: pytest.fail("Unexpected model prompt")
    app.choose_directory = lambda **_kwargs: pytest.fail("Unexpected folder picker")
    app.open_url = lambda _url: pytest.fail("Unexpected model source navigation")
    app._prepare_model()
    app._browse_model()
    app._open_model_source()
    assert app.controller.prepare_calls == 0
    assert app.prepare_button.options["state"] == "disabled"


def test_generic_cloud_failure_never_claims_local_processing(app):
    select_cloud(app)
    app._save()
    app.enqueue("error", "transcription_failed")
    app._pump()
    assert app.notice.get() == LABELS["en"]["cloud_request_failed"]


def test_cloud_can_save_when_unused_model_path_is_invalid(app):
    app.vars["windows_model_dir"].set("obsolete-relative-model")
    select_cloud(app)
    assert app._save() is True
    assert app._status_key == "idle"


def test_invalid_recognition_mode_cannot_be_saved(app):
    app.vars["windows_recognition_mode"].set("automatic-cloud-fallback")
    app._save()
    assert app.saved == []
    assert app.notice.get() == LABELS["en"]["invalid_settings"]


def test_real_widget_builder_masks_key_and_keeps_mode_controls_visible(monkeypatch):
    """Exercise _build itself with fake Tk surfaces, without an OS GUI."""
    import sys
    from types import ModuleType

    widgets = []
    class TkWidget(Widget):
        def __init__(self, parent=None, **options):
            super().__init__()
            self.parent = parent
            self.options.update(options)
            widgets.append(self)
        def pack(self, **_kwargs):
            pass
        def bind(self, *_args):
            pass
        def rowconfigure(self, *_args, **_kwargs):
            pass
        columnconfigure = rowconfigure
        def create_window(self, *_args, **_kwargs):
            return 1
        def yview(self, *_args):
            pass
        def set(self, *_args):
            pass
    class TkValue(Value):
        def trace_add(self, *_args):
            pass
    tk = ModuleType("tkinter")
    ttk = ModuleType("tkinter.ttk")
    tk.StringVar = tk.BooleanVar = TkValue
    tk.Canvas = tk.Text = TkWidget
    for name in ("Frame", "Label", "LabelFrame", "Button", "Radiobutton", "Checkbutton",
                 "Entry", "Combobox", "Progressbar", "Scrollbar"):
        setattr(ttk, name, TkWidget)
    tk.ttk = ttk
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", ttk)
    root = Root()
    root.geometry = root.minsize = lambda *_args: None
    config = {**WINDOWS_DEFAULTS, "windows_recognition_mode": "openai-cloud",
              "windows_cloud_consent": True, "openai_api_key": "synthetic-secret", "ui_language": "en"}
    actual = WindowsApp(root, config, controller_factory=Controller, native=Native(),
                        hotkeys_factory=Hotkeys, save_config=lambda _config: None)
    assert actual.key_entry.options["show"] == "•"
    assert actual.key_entry.options["textvariable"].get() == "synthetic-secret"
    assert not any("synthetic-secret" in str(widget.options.get("text", "")) for widget in widgets)
    assert actual.cloud_frame.visible and not actual.local_model_frame.visible
    assert actual.vars["windows_cloud_consent"].get() is False
    assert {widget.options.get("value") for widget in widgets if "value" in widget.options} >= {"local", "openai-cloud"}
