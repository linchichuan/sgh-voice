"""Message-loop lifecycle tests with a fake Win32 queue; no global hooks."""

import ctypes
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from windows_client.hotkeys import (
    CANCEL_ID, GlobalHotkeys, Hotkey, HotkeyError, MOD_NOREPEAT, MSG,
    TOGGLE_ID, WM_COMMAND_QUEUE, WM_HOTKEY, Win32HotkeyBackend,
)
from tests.test_windows_native import FakeFunction


class FakeHotkeyBackend:
    def __init__(self):
        self.messages = queue.Queue()
        self.registered = {}
        self.operations = []
        self.conflicts = set()
        self.thread_id = None
        self.wake_success = True
        self.stopped = threading.Event()

    def initialize_queue(self):
        self.thread_id = threading.get_ident()
        return self.thread_id

    def register(self, identifier, hotkey):
        self.operations.append(("register", identifier, threading.get_ident()))
        if hotkey in self.conflicts:
            return False
        self.registered[identifier] = hotkey
        return True

    def unregister(self, identifier):
        self.operations.append(("unregister", identifier, threading.get_ident()))
        self.registered.pop(identifier, None)
        return True

    def get_message(self):
        message = self.messages.get(timeout=5)
        if isinstance(message, Exception):
            self.stopped.set()
            raise message
        return message

    def wake(self, thread_id):
        assert thread_id == self.thread_id
        if self.wake_success:
            self.messages.put((WM_COMMAND_QUEUE, 0))
        return self.wake_success


class TestHotkeyParsing(unittest.TestCase):
    def test_normalizes_and_compares_shortcuts_semantically(self):
        key = Hotkey.parse(" Alt + control + f9 ")
        self.assertEqual((key.modifiers, key.key, key.label), (3, 0x78, "Ctrl+Alt+F9"))
        self.assertEqual(key, Hotkey.parse("Ctrl+Alt+F9"))
        self.assertEqual(Hotkey.parse("Ctrl+Shift+Space").key, 0x20)
        self.assertEqual(Hotkey.parse("Alt+F24").key, 0x87)

    def test_rejects_reserved_missing_duplicate_and_unsafe_keys(self):
        for value in ("", "F9", "Shift+A", "Win+A", "Ctrl+F12", "Ctrl+Alt+Delete",
                      "Ctrl+Ctrl+A", "Ctrl+", "Ctrl+F25", "Ctrl+Mouse1", None):
            with self.subTest(value=value), self.assertRaises(HotkeyError):
                Hotkey.parse(value)

    def test_msg_structure_layout(self):
        self.assertEqual(ctypes.sizeof(MSG), 48 if ctypes.sizeof(ctypes.c_void_p) == 8 else 32)

    def test_backend_registers_norepeat_and_signed_message_status(self):
        user32 = SimpleNamespace(**{name: FakeFunction() for name in (
            "RegisterHotKey", "UnregisterHotKey", "PeekMessageW", "GetMessageW", "PostThreadMessageW")})
        kernel32 = SimpleNamespace(GetCurrentThreadId=FakeFunction(lambda: 123))
        backend = Win32HotkeyBackend(user32, kernel32)
        self.assertEqual(backend.initialize_queue(), 123)
        self.assertTrue(backend.register(TOGGLE_ID, Hotkey.parse("Ctrl+Alt+F9")))
        self.assertEqual(user32.RegisterHotKey.calls, [(None, TOGGLE_ID, MOD_NOREPEAT | 3, 0x78)])
        user32.GetMessageW.implementation = lambda *args: -1
        with self.assertRaises(HotkeyError):
            backend.get_message()
        self.assertEqual(user32.GetMessageW.restype, ctypes.c_int32)


class TestGlobalHotkeys(unittest.TestCase):
    def setUp(self):
        self.backend = FakeHotkeyBackend()
        self.callbacks = queue.Queue()
        self.errors = queue.Queue()
        self.hotkeys = GlobalHotkeys(
            lambda: self.callbacks.put(("toggle", threading.get_ident())),
            lambda: self.callbacks.put(("cancel", threading.get_ident())),
            self.errors.put, backend=self.backend,
        )

    def tearDown(self):
        self.backend.wake_success = True
        self.hotkeys.stop()

    def test_callbacks_and_all_registration_cleanup_use_one_message_thread(self):
        self.hotkeys.start()
        self.assertTrue(self.hotkeys.running)
        for identifier, expected in ((TOGGLE_ID, "toggle"), (CANCEL_ID, "cancel")):
            self.backend.messages.put((WM_HOTKEY, identifier))
            self.assertEqual(self.callbacks.get(timeout=1), (expected, self.backend.thread_id))
        self.hotkeys.stop()
        self.assertFalse(self.hotkeys.running)
        self.assertEqual(self.backend.registered, {})
        self.assertTrue(all(operation[2] == self.backend.thread_id for operation in self.backend.operations))
        self.assertNotEqual(self.backend.thread_id, threading.get_ident())

    def test_update_releases_old_pair_and_registers_new_pair(self):
        self.hotkeys.start()
        self.hotkeys.update("Ctrl+Shift+F8", "Ctrl+Shift+F10")
        self.assertEqual(self.backend.registered, {
            TOGGLE_ID: Hotkey.parse("Ctrl+Shift+F8"), CANCEL_ID: Hotkey.parse("Ctrl+Shift+F10")})
        self.assertEqual([item[:2] for item in self.backend.operations], [
            ("register", 1), ("register", 2), ("unregister", 1), ("unregister", 2),
            ("register", 1), ("register", 2),
        ])

    def test_unchanged_update_does_not_unregister(self):
        self.hotkeys.start()
        self.hotkeys.update("Alt+Ctrl+F9", "Ctrl+Alt+F10")
        self.assertEqual(len(self.backend.operations), 2)

    def test_conflicting_new_pair_rolls_back_both_old_shortcuts(self):
        self.hotkeys.start()
        old = self.backend.registered.copy()
        self.backend.conflicts.add(Hotkey.parse("Ctrl+Shift+F10"))
        with self.assertRaisesRegex(HotkeyError, "already in use"):
            self.hotkeys.update("Ctrl+Shift+F8", "Ctrl+Shift+F10")
        self.assertEqual(self.backend.registered, old)
        self.assertTrue(self.hotkeys.running)

    def test_startup_conflict_cleans_successful_first_registration(self):
        self.backend.conflicts.add(Hotkey.parse("Ctrl+Alt+F10"))
        with self.assertRaisesRegex(HotkeyError, "already in use"):
            self.hotkeys.start()
        self.assertEqual(self.backend.registered, {})
        self.assertFalse(self.hotkeys.running)

    def test_duplicate_keys_rejected_before_mutating_registrations(self):
        with self.assertRaisesRegex(HotkeyError, "different"):
            self.hotkeys.start("Ctrl+Alt+F9", "Alt+Control+F9")
        self.assertEqual(self.backend.operations, [])
        self.hotkeys.start()
        with self.assertRaisesRegex(HotkeyError, "different"):
            self.hotkeys.update("Alt+A", "Alt+A")
        self.assertEqual(len(self.backend.operations), 2)

    def test_wake_failure_cancels_command_and_does_not_apply_later(self):
        self.hotkeys.start()
        old = self.backend.registered.copy()
        self.backend.wake_success = False
        with self.assertRaisesRegex(HotkeyError, "not applied"):
            self.hotkeys.update("Alt+A", "Alt+B")
        self.backend.wake_success = True
        # A later update wakes the thread; the failed queued update is skipped.
        self.hotkeys.update("Ctrl+Alt+F9", "Ctrl+Alt+F10")
        self.assertEqual(self.backend.registered, old)
        self.assertEqual(len(self.backend.operations), 2)

    def test_message_loop_failure_surfaces_and_releases_hotkeys(self):
        self.hotkeys.start()
        self.backend.messages.put(HotkeyError("Windows message failure"))
        self.assertEqual(self.errors.get(timeout=1), "Windows message failure")
        self.hotkeys._thread.join(timeout=1)
        self.assertEqual(self.backend.registered, {})
        self.assertFalse(self.hotkeys.running)

    def test_callback_exception_is_content_free_and_thread_keeps_running(self):
        def failure():
            raise RuntimeError("secret content")
        self.hotkeys._callbacks[TOGGLE_ID] = failure
        self.hotkeys.start()
        self.backend.messages.put((WM_HOTKEY, TOGGLE_ID))
        message = self.errors.get(timeout=1)
        self.assertNotIn("secret", message)
        self.assertTrue(self.hotkeys.running)

    def test_restart_after_clean_stop(self):
        self.hotkeys.start()
        self.hotkeys.stop()
        self.hotkeys.start("Alt+F8", "Alt+F9")
        self.assertTrue(self.hotkeys.running)
        self.assertEqual(self.backend.registered[TOGGLE_ID], Hotkey.parse("Alt+F8"))

    def test_non_windows_backend_rejects_without_loading_dlls(self):
        with patch("windows_client.hotkeys.sys.platform", "darwin"):
            with patch.object(ctypes, "WinDLL", create=True, side_effect=AssertionError("DLL load")):
                with self.assertRaises(HotkeyError):
                    Win32HotkeyBackend()


if __name__ == "__main__":
    unittest.main()
