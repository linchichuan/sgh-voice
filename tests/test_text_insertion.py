import sys
import types

import text_insertion


class FakePasteboardItem:
    def __init__(self, representations=None):
        self.representations = dict(representations or {})

    @classmethod
    def alloc(cls):
        return cls()

    def init(self):
        return self

    def types(self):
        return list(self.representations)

    def dataForType_(self, type_name):
        return self.representations.get(str(type_name))

    def setData_forType_(self, data, type_name):
        self.representations[str(type_name)] = bytes(data)
        return True


class FakePasteboard:
    def __init__(self, items):
        self.items = list(items)
        self.change_count = 7

    def pasteboardItems(self):
        return self.items

    def clearContents(self):
        self.items = []
        self.change_count += 1

    def setString_forType_(self, text, type_name):
        self.items = [FakePasteboardItem({str(type_name): text.encode("utf-8")})]
        return True

    def changeCount(self):
        return self.change_count

    def writeObjects_(self, items):
        self.items = list(items)
        return True


def install_fake_pasteboard_modules(monkeypatch):
    appkit = types.ModuleType("AppKit")
    appkit.NSPasteboardTypeString = "public.utf8-plain-text"
    appkit.NSPasteboardItem = FakePasteboardItem
    foundation = types.ModuleType("Foundation")

    class FakeNSData:
        @staticmethod
        def dataWithBytes_length_(payload, length):
            return bytes(payload[:length])

    foundation.NSData = FakeNSData
    monkeypatch.setitem(sys.modules, "AppKit", appkit)
    monkeypatch.setitem(sys.modules, "Foundation", foundation)


def test_transactional_pasteboard_restores_every_representation(monkeypatch):
    install_fake_pasteboard_modules(monkeypatch)
    pasteboard = FakePasteboard(
        [
            FakePasteboardItem(
                {
                    "public.utf8-plain-text": b"original",
                    "public.html": b"<b>original</b>",
                    "public.png": b"not-a-real-png-but-binary-safe",
                }
            )
        ]
    )

    snapshot = text_insertion.capture_pasteboard(pasteboard)
    staged_count = text_insertion.stage_text_on_pasteboard("transcript", pasteboard)

    assert text_insertion.restore_pasteboard(
        snapshot, staged_count, pasteboard
    ) is True
    assert pasteboard.items[0].representations == {
        "public.utf8-plain-text": b"original",
        "public.html": b"<b>original</b>",
        "public.png": b"not-a-real-png-but-binary-safe",
    }


def test_restore_does_not_overwrite_a_new_user_clipboard(monkeypatch):
    install_fake_pasteboard_modules(monkeypatch)
    pasteboard = FakePasteboard(
        [FakePasteboardItem({"public.utf8-plain-text": b"original"})]
    )
    snapshot = text_insertion.capture_pasteboard(pasteboard)
    staged_count = text_insertion.stage_text_on_pasteboard("transcript", pasteboard)

    pasteboard.change_count += 1
    pasteboard.items = [
        FakePasteboardItem({"public.utf8-plain-text": b"new user copy"})
    ]

    assert text_insertion.restore_pasteboard(
        snapshot, staged_count, pasteboard
    ) is False
    assert pasteboard.items[0].representations["public.utf8-plain-text"] == (
        b"new user copy"
    )


def test_change_count_detects_user_copy_before_synthetic_paste():
    pasteboard = FakePasteboard(
        [FakePasteboardItem({"public.utf8-plain-text": b"original"})]
    )
    staged_count = text_insertion.stage_text_on_pasteboard("transcript", pasteboard)

    assert text_insertion.pasteboard_change_count_matches(
        staged_count, pasteboard
    ) is True
    pasteboard.change_count += 1
    assert text_insertion.pasteboard_change_count_matches(
        staged_count, pasteboard
    ) is False


def test_accessibility_inserts_selected_text_without_clipboard(monkeypatch):
    application_services = types.ModuleType("ApplicationServices")
    application_services.kAXFocusedUIElementAttribute = "focused"
    application_services.kAXSelectedTextAttribute = "selected"
    application_services.AXIsProcessTrusted = lambda: True
    application_services.AXUIElementCreateApplication = lambda pid: ("app", pid)
    application_services.AXUIElementCopyAttributeValue = (
        lambda app, attribute, output: (0, "focused-element")
    )
    application_services.AXUIElementIsAttributeSettable = (
        lambda element, attribute, output: (0, True)
    )
    writes = []
    application_services.AXUIElementSetAttributeValue = (
        lambda element, attribute, value: writes.append(value) or 0
    )
    monkeypatch.setitem(sys.modules, "ApplicationServices", application_services)

    assert text_insertion.insert_text_via_accessibility("三語 text", 123) is True
    assert writes == ["三語 text"]


def test_paste_text_prefers_clipboard_free_accessibility(monkeypatch):
    import app

    monkeypatch.setattr(app, "accessibility_is_trusted", lambda: True)
    monkeypatch.setattr(
        app, "insert_text_via_accessibility", lambda text, target_pid: True
    )
    monkeypatch.setattr(
        app,
        "capture_pasteboard",
        lambda: (_ for _ in ()).throw(AssertionError("clipboard should not be read")),
    )
    monkeypatch.setattr(app.event_ledger, "paste_method", lambda **kwargs: None)

    assert app.paste_text("直接輸入") is True


def test_failed_paste_restores_clipboard_and_requests_permission(monkeypatch):
    import app

    snapshot = text_insertion.PasteboardSnapshot(())
    restored = []
    prompted = []
    notified = []

    monkeypatch.setattr(app, "accessibility_is_trusted", lambda: False)
    monkeypatch.setattr(app, "capture_pasteboard", lambda: snapshot)
    monkeypatch.setattr(app, "stage_text_on_pasteboard", lambda text: 44)
    monkeypatch.setattr(
        app, "pasteboard_change_count_matches", lambda count: True
    )
    monkeypatch.setattr(app, "_wait_modifiers_released", lambda **kwargs: None)
    monkeypatch.setattr(
        app.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(returncode=1),
    )
    monkeypatch.setattr(
        app,
        "restore_pasteboard",
        lambda value, count: restored.append((value, count)) or True,
    )
    monkeypatch.setattr(
        app, "request_accessibility_prompt", lambda: prompted.append(True) or False
    )
    monkeypatch.setattr(
        app, "notify", lambda title, message: notified.append((title, message))
    )
    monkeypatch.setattr(app.event_ledger, "paste_method", lambda **kwargs: None)

    assert app.paste_text("不能留在 clipboard") is False
    assert restored == [(snapshot, 44)]
    assert prompted == [True]
    assert "原剪貼簿已保留" in notified[0][1]


def test_successful_quartz_fallback_schedules_full_restore(monkeypatch):
    import app

    snapshot = text_insertion.PasteboardSnapshot(())
    posted_events = []
    scheduled = []
    quartz = types.ModuleType("Quartz")
    quartz.kCGSessionEventTap = "session"
    quartz.kCGEventFlagMaskCommand = "command"
    quartz.CGEventCreateKeyboardEvent = (
        lambda source, keycode, is_down: {
            "keycode": keycode,
            "is_down": is_down,
        }
    )
    quartz.CGEventSetFlags = lambda event, flags: event.update(flags=flags)
    quartz.CGEventPost = lambda tap, event: posted_events.append((tap, event.copy()))
    monkeypatch.setitem(sys.modules, "Quartz", quartz)

    monkeypatch.setattr(app, "accessibility_is_trusted", lambda: True)
    monkeypatch.setattr(
        app, "insert_text_via_accessibility", lambda text, target_pid: False
    )
    monkeypatch.setattr(app, "capture_pasteboard", lambda: snapshot)
    monkeypatch.setattr(app, "stage_text_on_pasteboard", lambda text: 44)
    monkeypatch.setattr(
        app, "pasteboard_change_count_matches", lambda count: True
    )
    monkeypatch.setattr(app, "_wait_modifiers_released", lambda **kwargs: None)
    monkeypatch.setattr(app.time, "sleep", lambda delay: None)
    monkeypatch.setattr(
        app,
        "schedule_pasteboard_restore",
        lambda value, count, delay: scheduled.append((value, count, delay)),
    )
    monkeypatch.setattr(
        app.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("osascript must not run after Quartz succeeds")
        ),
    )
    monkeypatch.setattr(app.event_ledger, "paste_method", lambda **kwargs: None)

    assert app.paste_text("交易式 clipboard fallback") is True
    assert [event[1]["is_down"] for event in posted_events] == [True, False]
    assert scheduled == [(snapshot, 44, 0.25)]


def test_user_copy_during_modifier_wait_cancels_cmd_v(monkeypatch):
    import app

    snapshot = text_insertion.PasteboardSnapshot(())
    notified = []
    subprocess_calls = []

    monkeypatch.setattr(app, "accessibility_is_trusted", lambda: True)
    monkeypatch.setattr(
        app, "insert_text_via_accessibility", lambda text, target_pid: False
    )
    monkeypatch.setattr(app, "capture_pasteboard", lambda: snapshot)
    monkeypatch.setattr(app, "stage_text_on_pasteboard", lambda text: 44)
    monkeypatch.setattr(app, "_wait_modifiers_released", lambda **kwargs: None)
    monkeypatch.setattr(
        app, "pasteboard_change_count_matches", lambda count: False
    )
    monkeypatch.setattr(
        app.subprocess,
        "run",
        lambda *args, **kwargs: subprocess_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(app, "restore_pasteboard", lambda *args: False)
    monkeypatch.setattr(
        app, "notify", lambda title, message: notified.append((title, message))
    )
    monkeypatch.setattr(app.event_ledger, "paste_method", lambda **kwargs: None)

    assert app.paste_text("不能貼出新 clipboard") is False
    assert subprocess_calls == []
    assert "剛複製的內容" in notified[0][1]
