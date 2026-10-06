"""Headless UI boundary tests: no GUI, microphone, network, or credential writes."""
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
        self.model_ready = True
        self.imports = []
        self.soap_ready = True
        self.last_soap = ""
        self.soap_requests = []

    def draft_soap(self, transcript):
        self.soap_requests.append(transcript)
        self.state = "drafting_soap"
        return True

    def import_file(self, path):
        self.imports.append(path)
        self.state = "importing"
        return True

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
            "ui_language": "en",
            "windows_lexicon_enabled": False, "windows_auto_insert": False,
            "windows_save_history": False, "windows_toggle_hotkey": "Ctrl+Alt+F9",
            "windows_cancel_hotkey": "Ctrl+Alt+F10", "windows_soap_auto": True, "windows_soap_copy": True,
        }
        self.vars = {field: Value(self.config.get(field, default)) for field, default in defaults.items()}
        self.status, self.notice, self.hotkey_notice = Value(), Value(), Value()
        self.model_notice, self.model_details, self.candidates = Value(), Value(), Value()
        self.record_button, self.cancel_button, self.save_button = Widget(), Widget(), Widget()
        self.meter, self.result, self.copy_button = Widget(), Widget(), Widget()
        self.import_button, self.save_text_button = Widget(), Widget()
        self.soap_button = Widget()


@pytest.fixture
def app():
    saved = []
    instance = HeadlessApp(
        Root(), {**WINDOWS_DEFAULTS, "windows_lexicon_enabled": False, "ui_language": "en"},
        controller_factory=Controller, native=Native(), hotkeys_factory=Hotkeys,
        save_config=saved.append, validate_hotkey=Hotkey.parse,
        model_info={"name": "Synthetic local model", "size_label": "0.01 GB (test fixture)"},
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


def test_settings_snapshot_preserves_unrelated_config_and_forces_japanese():
    current = {"keep": "me", "windows_model_dir": "C:\\Models\\old-download"}
    values = {**WINDOWS_DEFAULTS, "windows_language": "en", "ui_language": "en"}
    updated = settings_snapshot(current, values)
    assert updated["keep"] == "me"
    assert updated["windows_language"] == "ja"
    assert "windows_model_dir" not in updated
    assert current["windows_model_dir"] == "C:\\Models\\old-download"


def test_builtin_model_is_shown_and_cannot_be_chosen_or_downloaded(app):
    assert app.model_details.get() == LABELS["en"]["model_builtin"].format(
        name="Synthetic local model", size="0.01 GB (test fixture)")
    for removed in ("_browse_model", "_prepare_model", "_open_model_source", "prepare_button", "source_button"):
        assert not hasattr(app, removed)
    assert "windows_model_dir" not in app.vars and "windows_language" not in app.vars


def test_status_waits_for_model_verification(app):
    app.controller.state = "verifying_model"
    app.controller.model_ready = False
    app._render_state()
    assert app.status.get() == LABELS["en"]["verifying_model"]
    assert app.model_notice.get() == LABELS["en"]["verifying_model"]
    app.controller.state = "idle"
    app._render_state()
    assert app.status.get() == LABELS["en"]["needs_model"]
    app.enqueue("error", "model_invalid")
    app._pump()
    assert app.notice.get() == LABELS["en"]["model_invalid"]


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
    for code in ("model_required", "model_invalid", "model_load_failed", "model_missing",
                 "invalid_model_path", "model_not_ready", "invalid_language", "invalid_cpu_threads",
                 "local_runtime_missing", "local_model_load_failed", "local_transcription_failed",
                 "audio_unavailable", "invalid_mode", "invalid_decode_options"):
        app.enqueue("error", code)
        app._pump()
        assert app.notice.get() == LABELS["en"][code]


def test_offline_controls_have_no_cloud_or_key_fields(app):
    assert "windows_provider" not in app.vars
    assert "windows_cloud_consent" not in app.vars
    assert "windows_polish" not in app.vars
    assert not hasattr(app, "key_var")
    assert app.config["windows_language"] == "ja"
    assert app.vars["windows_lexicon_enabled"].get() is False


def test_audio_import_uses_chosen_file_and_shows_privacy_notice(app):
    chosen = []
    app.choose_audio_file = lambda **kwargs: chosen.append(kwargs["filetypes"]) or "C:\\rec\\visit.mp3"
    app._import_file()
    assert app.controller.imports == ["C:\\rec\\visit.mp3"]
    assert "*.wav *.mp3" in chosen[0][0][1]
    assert app.notice.get() == LABELS["en"]["import_notice"]
    assert app.import_button.options["state"] == "disabled"
    assert app.cancel_button.options["state"] == "normal"


def test_audio_import_cancelled_dialog_does_nothing(app):
    app.choose_audio_file = lambda **kwargs: ""
    app._import_file()
    assert app.controller.imports == []


def test_file_progress_and_result_are_preview_only(app):
    app.controller.state = "processing"
    app.enqueue("file_progress", {"percent": 42, "message": "private"})
    app._pump()
    assert "42%" in app.notice.get() and "private" not in app.notice.get()
    app.controller.last_text = "一行目\n二行目"
    app.enqueue("result", {"text": "一行目\n二行目", "source": "file",
                           "insertion": {"success": False, "reason": "preview_only"}})
    app._pump()
    assert app.result.get() == "一行目\n二行目"
    assert app.notice.get() == LABELS["en"]["file_done"]


def test_save_text_writes_utf8_with_bom_for_notepad(app, tmp_path):
    target = tmp_path / "visit.txt"
    app.result.insert("1.0", "診察メモ\n二行目")
    app.choose_save_path = lambda **kwargs: str(target)
    app._save_text()
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert target.read_text(encoding="utf-8-sig").splitlines() == ["診察メモ", "二行目"]
    assert app.notice.get() == LABELS["en"]["text_saved"]


def test_audio_import_errors_are_localized(app):
    for code in ("audio_format_unsupported", "audio_file_unreadable", "audio_file_empty", "audio_file_too_long"):
        app.enqueue("error", code)
        app._pump()
        assert app.notice.get() == LABELS["en"][code]


def test_long_recording_messages_and_elapsed_clock(app, monkeypatch):
    assert result_message({"long": True, "insertion": {"success": False, "reason": "preview_only"}}) == "long_done"
    assert result_message({"long": True, "limit_reached": True, "insertion": {}}) == "recording_limit"
    assert result_message({"long": True, "insertion": {"success": True}}) == "paste_sent"
    for lang in LABELS:
        assert "{" not in LABELS[lang]["recording_limit"] and "{elapsed}" in LABELS[lang]["recording_elapsed"]
    import windows_client.ui as ui
    now = [1000.0]
    monkeypatch.setattr(ui.time, "monotonic", lambda: now[0])
    app.controller.state = "recording"
    app._render_state()
    now[0] += 25 * 60 + 7
    app._pump()
    assert app.status.get() == LABELS["en"]["recording_elapsed"].format(elapsed="25:07", limit="60:00")
    app.controller.state = "idle"
    app._render_state()
    assert app._recording_since is None


def test_soap_result_shows_draft_unverified_terms_and_transcript(app):
    app.controller.last_text = "血圧は148の92です。"
    app.enqueue("result", {"text": app.controller.last_text, "insertion": {"success": False},
                           "long": True, "soap_follows": True})
    app._pump()
    assert app.notice.get() == LABELS["en"]["soap_pending"]
    app.controller.state = "drafting_soap"
    app._render_state()
    assert app.cancel_button.options["state"] == "normal"
    assert app.soap_button.options["state"] == "disabled"
    app.enqueue("soap_progress", {"seconds": 75})
    app._pump()
    assert app.status.get() == LABELS["en"]["soap_elapsed"].format(elapsed="01:15")
    soap = {"text": "S（主観的情報）:\n- 記載なし\nO（客観的情報）:\n- 血圧 148/92\nA（評価）:\n- 記載なし\nP（計画）:\n- インスリン",
            "unverified": ["インスリン"], "seconds": 80}
    app.enqueue("soap_result", {"soap": soap, "transcript": app.controller.last_text, "insertion": {}})
    app._pump()  # stale: controller.last_soap differs
    assert "SOAP" not in app.result.get("1.0", "end-1c")
    app.controller.last_soap = soap["text"]
    app.controller.state = "idle"
    app.enqueue("soap_result", {"soap": soap, "transcript": app.controller.last_text, "insertion": {}})
    app._pump()
    text = app.result.get("1.0", "end-1c")
    assert text.startswith(LABELS["en"]["soap_heading"])
    assert LABELS["en"]["soap_unverified"] + "インスリン" in text
    assert text.rstrip().endswith(LABELS["en"]["transcript_heading"] + "\n血圧は148の92です。")
    assert app.notice.get() == LABELS["en"]["soap_done"]
    assert app.soap_button.options["state"] == "normal"
    # Re-drafting sends only the transcript part of the result box.
    app._draft_soap()
    assert app.controller.soap_requests == ["\n血圧は148の92です。"]


def test_soap_button_disabled_without_model(app):
    app.controller.soap_ready = False
    app._render_state()
    assert app.soap_button.options["state"] == "disabled"


def test_copied_soap_draft_tells_clinician_to_paste(app):
    soap = {"text": "S:\nO:\nA:\nP:", "unverified": []}
    app.controller.last_soap = soap["text"]
    app.enqueue("soap_result", {"soap": soap, "transcript": "t", "insertion": {"success": False, "reason": "copied"}})
    app._pump()
    assert app.notice.get() == LABELS["en"]["soap_copied"]
