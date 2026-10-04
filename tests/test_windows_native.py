"""Win32 contract tests runnable on non-Windows; not Windows acceptance tests."""

import ctypes
import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from windows_client.native import (
    GUITHREADINFO, INPUT, KEYBDINPUT, MOUSEINPUT, NativeInputError,
    TargetWindow, Win32Backend, WindowsNative,
)


class FakeBackend:
    def __init__(self):
        self.hwnd = 0x123456780
        self.pid = 42
        self.focus_hwnd = 0x223456780
        self.password = False
        self.modifiers = False
        self.sent = []
        self.copied = []
        self.return_count = None

    def foreground(self):
        return self.hwnd

    def process_id(self, hwnd):
        return self.pid

    def focus(self, hwnd):
        return self.focus_hwnd

    def password_control(self, hwnd):
        return self.password

    def modifiers_down(self):
        return self.modifiers

    def send_inputs(self, events):
        self.sent.append([(event.type, event.ki.wVk, event.ki.wScan, event.ki.dwFlags)
                          for event in events])
        return len(events) if self.return_count is None else self.return_count

    def copy_text(self, text):
        self.copied.append(text)


class FakeFunction:
    def __init__(self, implementation=lambda *args: 1):
        self.implementation = implementation
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.implementation(*args)


class FakeDLLs:
    """Real ctypes buffers exercise allocation/ownership without user32."""
    def __init__(self):
        self.buffers = {}
        self.published = []
        self.freed = []
        self.next_handle = 0x100000001
        self.format_ids = {}
        self.fail_format = None
        self.fail_register = False
        self.fail_alloc = False
        self.fail_lock = False
        self.fail_open = False
        self.user32 = SimpleNamespace()
        names = ("GetForegroundWindow", "IsWindow", "GetWindowThreadProcessId",
                 "GetGUIThreadInfo", "GetClassNameW", "GetWindowLongPtrW", "GetWindowLongW",
                 "GetAsyncKeyState", "SendInput", "RegisterClipboardFormatW", "CreateWindowExW",
                 "DestroyWindow", "OpenClipboard", "CloseClipboard", "EmptyClipboard", "SetClipboardData")
        for name in names:
            setattr(self.user32, name, FakeFunction())
        self.user32.RegisterClipboardFormatW.implementation = self.register
        self.user32.CreateWindowExW.implementation = lambda *args: 0x200000001
        self.user32.OpenClipboard.implementation = lambda owner: not self.fail_open
        self.user32.SetClipboardData.implementation = self.publish
        self.kernel32 = SimpleNamespace(
            GlobalAlloc=FakeFunction(self.allocate), GlobalLock=FakeFunction(self.lock),
            GlobalUnlock=FakeFunction(), GlobalFree=FakeFunction(self.free),
        )

    def register(self, name):
        if self.fail_register:
            return 0
        self.format_ids.setdefault(name, 0xC000 + len(self.format_ids))
        return self.format_ids[name]

    def allocate(self, flags, size):
        if self.fail_alloc:
            return 0
        assert flags == 2
        handle = self.next_handle
        self.next_handle += 1
        self.buffers[handle] = ctypes.create_string_buffer(size)
        return handle

    def lock(self, handle):
        return 0 if self.fail_lock else ctypes.addressof(self.buffers[handle])

    def free(self, handle):
        self.freed.append(handle)
        del self.buffers[handle]
        return 0

    def publish(self, format_id, handle):
        if format_id == self.fail_format:
            return 0
        self.published.append((format_id, handle, self.buffers[handle].raw))
        return handle


class TestNativeInput(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.native = WindowsNative(self.backend, own_pid=100)
        self.target = self.native.capture_target()

    def test_windows_abi_sizes_do_not_use_host_long(self):
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self.assertEqual((ctypes.sizeof(KEYBDINPUT), ctypes.sizeof(MOUSEINPUT),
                              ctypes.sizeof(INPUT), ctypes.sizeof(GUITHREADINFO)), (24, 32, 40, 72))
        else:
            self.assertEqual((ctypes.sizeof(KEYBDINPUT), ctypes.sizeof(MOUSEINPUT),
                              ctypes.sizeof(INPUT), ctypes.sizeof(GUITHREADINFO)), (16, 24, 28, 48))

    def test_utf16_supplementary_characters_use_surrogates_and_key_up(self):
        result = self.native.send_text(self.target, "中😀")
        self.assertTrue(result.success)
        self.assertEqual((result.sent_events, result.total_events), (6, 6))
        self.assertEqual(self.backend.sent[0], [
            (1, 0, 0x4E2D, 4), (1, 0, 0x4E2D, 6),
            (1, 0, 0xD83D, 4), (1, 0, 0xD83D, 6),
            (1, 0, 0xDE00, 4), (1, 0, 0xDE00, 6),
        ])
        self.assertEqual(self.backend.copied, [])

    def test_changed_window_pid_focus_password_unknown_and_modifiers_do_not_inject(self):
        for attribute, value in [("hwnd", 888), ("pid", 99), ("focus_hwnd", 333),
                                 ("password", True), ("password", None), ("modifiers", True)]:
            with self.subTest(attribute=attribute, value=value):
                previous = getattr(self.backend, attribute)
                setattr(self.backend, attribute, value)
                self.assertFalse(self.native.send_text(self.target, "sensitive").success)
                self.assertEqual(self.backend.sent, [])
                self.assertEqual(self.backend.copied, [])
                setattr(self.backend, attribute, previous)

    def test_last_moment_focus_change_rejected(self):
        calls = iter([self.target.focus_hwnd, 444])
        self.backend.focus = lambda hwnd: next(calls)
        self.assertFalse(self.native.send_text(self.target, "hello").success)
        self.assertEqual(self.backend.sent, [])

    def test_no_target_and_own_app_rejected(self):
        for target in (None, TargetWindow(55, 100, 56)):
            self.assertFalse(self.native.send_text(target, "hello").success)
        self.backend.pid = 100
        with self.assertRaises(NativeInputError):
            self.native.capture_target()
        self.assertEqual(self.backend.sent, [])

    def test_no_focus_cannot_be_captured(self):
        self.backend.focus_hwnd = 0
        with self.assertRaises(NativeInputError):
            self.native.capture_target()

    def test_partial_and_blocked_inputs_are_never_retried_or_copied(self):
        for count in (0, 1, 3):
            self.backend.return_count = count
            before = len(self.backend.sent)
            result = self.native.send_text(self.target, "ab")
            self.assertFalse(result.success)
            self.assertEqual(result.sent_events, count)
            self.assertEqual(len(self.backend.sent), before + 1)
            self.assertEqual(self.backend.copied, [])

    def test_unsafe_control_invalid_unicode_and_large_output_stay_in_ui(self):
        for text in ("", "a\nb", "a\rb", "a\tb", "a\x00b", "\x7f", "\x85", "\ud800", "a" * 32769):
            with self.subTest(length=len(text)):
                result = self.native.send_text(self.target, text)
                self.assertFalse(result.success)
                self.assertNotIn(text if len(text) > 5 else "NEVER", result.reason)
        self.assertEqual(self.backend.sent, [])
        self.assertEqual(self.backend.copied, [])

    def test_backend_exception_never_exposes_content(self):
        def fail(events):
            raise RuntimeError("private patient text")
        self.backend.send_inputs = fail
        result = self.native.send_text(self.target, "private patient text")
        self.assertFalse(result.success)
        self.assertNotIn("patient", result.reason)

    def test_copy_is_explicit_and_allows_multiline(self):
        self.native.copy_text("hello\nworld😀")
        self.assertEqual(self.backend.copied, ["hello\nworld😀"])
        self.assertEqual(self.backend.sent, [])
        for invalid in ("", "a\0b", "\ud800"):
            with self.assertRaises(NativeInputError):
                self.native.copy_text(invalid)

    def test_module_import_does_not_load_win32_dlls(self):
        import windows_client.native as native_module
        # Import in a fresh module namespace avoids altering objects used by
        # these tests while still exercising every import-time statement.
        with patch.object(ctypes, "WinDLL", create=True, side_effect=AssertionError("DLL load")):
            spec = importlib.util.spec_from_file_location("_sgh_native_import_test", native_module.__file__)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            try:
                spec.loader.exec_module(module)
            finally:
                del sys.modules[spec.name]


class TestWin32Clipboard(unittest.TestCase):
    def setUp(self):
        self.dll = FakeDLLs()
        self.backend = Win32Backend(self.dll.user32, self.dll.kernel32)

    def test_64bit_safe_function_prototypes(self):
        self.assertIs(self.dll.user32.SetClipboardData.restype, ctypes.c_void_p)
        self.assertIs(self.dll.kernel32.GlobalAlloc.restype, ctypes.c_void_p)
        self.assertIs(self.dll.kernel32.GlobalLock.restype, ctypes.c_void_p)
        self.assertIs(self.dll.user32.GetForegroundWindow.restype, ctypes.c_void_p)
        self.assertEqual(self.dll.user32.SendInput.argtypes[-1], ctypes.c_int)

    def test_privacy_formats_precede_unicode_and_ownership_transfers_once(self):
        self.backend.copy_text("中\n😀")
        self.assertEqual(len(self.dll.published), 4)
        self.assertEqual([item[2] for item in self.dll.published[:3]], [b"\0" * 4] * 3)
        self.assertEqual(self.dll.published[-1][0], 13)
        self.assertEqual(self.dll.published[-1][2], "中\r\n😀\0".encode("utf-16-le"))
        self.assertEqual(self.dll.freed, [])
        self.assertEqual(self.dll.user32.OpenClipboard.calls, [(0x200000001,)])
        self.assertEqual(len(self.dll.user32.CloseClipboard.calls), 1)
        self.assertEqual(len(self.dll.user32.DestroyWindow.calls), 1)

    def test_privacy_registration_failure_preserves_existing_clipboard(self):
        self.dll.fail_register = True
        with self.assertRaises(NativeInputError):
            self.backend.copy_text("private")
        self.assertEqual(self.dll.user32.EmptyClipboard.calls, [])
        self.assertEqual(self.dll.buffers, {})

    def test_busy_clipboard_frees_all_allocations_without_clearing_it(self):
        self.dll.fail_open = True
        with self.assertRaises(NativeInputError):
            self.backend.copy_text("private")
        self.assertEqual(self.dll.buffers, {})
        self.assertEqual(self.dll.user32.EmptyClipboard.calls, [])
        self.assertEqual(self.dll.user32.CloseClipboard.calls, [])
        self.assertEqual(len(self.dll.user32.DestroyWindow.calls), 1)

    def test_privacy_publication_failure_does_not_publish_plaintext(self):
        self.dll.fail_format = 0xC001
        with self.assertRaises(NativeInputError):
            self.backend.copy_text("private")
        self.assertEqual(len(self.dll.published), 1)
        self.assertNotIn(13, [entry[0] for entry in self.dll.published])
        self.assertEqual(len(self.dll.freed), 3)
        self.assertEqual(len(self.dll.user32.CloseClipboard.calls), 1)

    def test_text_publication_failure_releases_untransferred_handle_only(self):
        self.dll.fail_format = 13
        with self.assertRaises(NativeInputError):
            self.backend.copy_text("private")
        self.assertEqual(len(self.dll.freed), 1)
        self.assertEqual(len(self.dll.published), 3)
        self.assertNotIn(self.dll.freed[0], [entry[1] for entry in self.dll.published])

    def test_allocation_and_lock_failure_do_not_clear_clipboard(self):
        for attribute in ("fail_alloc", "fail_lock"):
            with self.subTest(failure=attribute):
                setattr(self.dll, attribute, True)
                with self.assertRaises(NativeInputError):
                    self.backend.copy_text("private")
                self.assertEqual(self.dll.buffers, {})
                self.assertEqual(self.dll.user32.EmptyClipboard.calls, [])
                setattr(self.dll, attribute, False)


if __name__ == "__main__":
    unittest.main()
