"""Thread-owned RegisterHotKey shortcuts with explicit conflict reporting.

Callbacks execute on the message thread. A UI must post them to its own queue;
it may capture the foreground target in on_toggle before posting that event.
No keyboard hook, pynput, elevation, or third-party package is required.
"""

from __future__ import annotations

import ctypes
import queue
import sys
import threading
from dataclasses import dataclass, field

from .native import BOOL, DWORD, HWND, LPARAM, POINT, UINT, ULONG_PTR, _bind

WM_HOTKEY = 0x0312
WM_COMMAND_QUEUE = 0x8001
MOD_NOREPEAT = 0x4000
TOGGLE_ID = 1
CANCEL_ID = 2


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", HWND), ("message", UINT), ("wParam", ULONG_PTR),
                ("lParam", LPARAM), ("time", DWORD), ("pt", POINT), ("lPrivate", DWORD)]


class HotkeyError(RuntimeError):
    """A registration or lifecycle failure safe to display to the user."""


@dataclass(frozen=True)
class Hotkey:
    modifiers: int
    key: int
    label: str = field(compare=False)

    @classmethod
    def parse(cls, text: str) -> "Hotkey":
        if not isinstance(text, str):
            raise HotkeyError("A shortcut must be text, such as Ctrl+Alt+F9.")
        parts = [part.strip().upper() for part in text.split("+")]
        modifiers = 0
        modifier_names = {"CTRL": (2, "Ctrl"), "CONTROL": (2, "Ctrl"),
                          "ALT": (1, "Alt"), "SHIFT": (4, "Shift")}
        for part in parts[:-1]:
            if part not in modifier_names:
                raise HotkeyError("Use Ctrl, Alt, or Shift modifiers; Windows-key shortcuts are reserved.")
            value = modifier_names[part][0]
            if modifiers & value:
                raise HotkeyError("A shortcut cannot repeat a modifier.")
            modifiers |= value
        if not modifiers & 3:
            raise HotkeyError("A global shortcut must include Ctrl or Alt.")
        key_name = parts[-1]
        if key_name.startswith("F") and key_name[1:].isdigit() and 1 <= int(key_name[1:]) <= 24:
            if int(key_name[1:]) == 12:
                raise HotkeyError("F12 is reserved by Windows; choose another key.")
            key = 0x70 + int(key_name[1:]) - 1
            key_name = "F" + str(int(key_name[1:]))
        elif len(key_name) == 1 and ("A" <= key_name <= "Z" or "0" <= key_name <= "9"):
            key = ord(key_name)
        elif key_name == "SPACE":
            key, key_name = 0x20, "Space"
        else:
            raise HotkeyError("Use a letter, number, Space, or F1–F24 (except F12).")
        labels = [label for bit, label in ((2, "Ctrl"), (1, "Alt"), (4, "Shift")) if modifiers & bit]
        return cls(modifiers, key, "+".join([*labels, key_name]))


def _pair(toggle, cancel):
    pair = (Hotkey.parse(toggle), Hotkey.parse(cancel))
    if pair[0] == pair[1]:
        raise HotkeyError("Record and cancel shortcuts must be different.")
    return pair


class Win32HotkeyBackend:
    def __init__(self, user32=None, kernel32=None):
        if user32 is None or kernel32 is None:
            if sys.platform != "win32":
                raise HotkeyError("Global Windows shortcuts are available only on Windows.")
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user32, self.kernel32 = user32, kernel32
        _bind(user32, "RegisterHotKey", [HWND, ctypes.c_int, UINT, UINT], BOOL)
        _bind(user32, "UnregisterHotKey", [HWND, ctypes.c_int], BOOL)
        _bind(user32, "PeekMessageW", [ctypes.POINTER(MSG), HWND, UINT, UINT, UINT], BOOL)
        _bind(user32, "GetMessageW", [ctypes.POINTER(MSG), HWND, UINT, UINT], BOOL)
        _bind(user32, "PostThreadMessageW", [DWORD, UINT, ULONG_PTR, LPARAM], BOOL)
        _bind(kernel32, "GetCurrentThreadId", [], DWORD)

    def initialize_queue(self):
        message = MSG()
        self.user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
        return int(self.kernel32.GetCurrentThreadId())

    def register(self, identifier, hotkey):
        return bool(self.user32.RegisterHotKey(None, identifier, hotkey.modifiers | MOD_NOREPEAT, hotkey.key))

    def unregister(self, identifier):
        return bool(self.user32.UnregisterHotKey(None, identifier))

    def get_message(self):
        message = MSG()
        status = int(self.user32.GetMessageW(ctypes.byref(message), None, 0, 0))
        if status < 0:
            raise HotkeyError("Windows stopped delivering shortcuts; restart the application.")
        return None if status == 0 else (message.message, message.wParam)

    def wake(self, thread_id):
        return bool(self.user32.PostThreadMessageW(thread_id, WM_COMMAND_QUEUE, 0, 0))


@dataclass
class _Command:
    action: str
    pair: tuple | None = None
    complete: threading.Event = field(default_factory=threading.Event)
    error: HotkeyError | None = None
    cancelled: bool = False


class GlobalHotkeys:
    """Use start/update/stop from the UI thread; callbacks must return promptly."""

    def __init__(self, on_toggle, on_cancel, on_error, *, backend=None):
        self._callbacks = {TOGGLE_ID: on_toggle, CANCEL_ID: on_cancel}
        self._on_error = on_error
        self._backend = backend
        self._commands = queue.Queue()
        self._thread = None
        self._thread_id = None
        self._ready = threading.Event()
        self._startup_cancelled = threading.Event()
        self._startup_error = None
        self._active = {}
        self._lifecycle = threading.RLock()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive() and bool(self._active)

    def start(self, toggle="Ctrl+Alt+F9", cancel="Ctrl+Alt+F10"):
        pair = _pair(toggle, cancel)
        with self._lifecycle:
            if self._thread is not None and self._thread.is_alive():
                raise HotkeyError("Global shortcuts are already running.")
            if self._backend is None:
                self._backend = Win32HotkeyBackend()
            self._ready.clear()
            self._startup_cancelled.clear()
            self._startup_error = None
            self._thread_id = None
            self._commands = queue.Queue()
            self._thread = threading.Thread(target=self._run, args=(pair,),
                                            name="SGHVoiceHotkeys", daemon=True)
            self._thread.start()
            if not self._ready.wait(3):
                self._startup_cancelled.set()
                if self._thread_id:
                    self._commands.put(_Command("stop"))
                    self._backend.wake(self._thread_id)
                raise HotkeyError("Windows shortcut initialization timed out; restart the application.")
            if self._startup_error:
                self._thread.join(timeout=3)
                raise self._startup_error

    def update(self, toggle, cancel):
        pair = _pair(toggle, cancel)
        with self._lifecycle:
            self._request(_Command("update", pair))

    def stop(self):
        with self._lifecycle:
            if self._thread is None or not self._thread.is_alive():
                return
            if threading.current_thread() is self._thread:
                raise HotkeyError("Stop shortcuts from the UI thread, not the shortcut callback.")
            self._request(_Command("stop"))
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                raise HotkeyError("Shortcut shutdown timed out; close the application before restarting it.")

    def _request(self, command):
        if self._thread is None or not self._thread.is_alive() or not self._thread_id:
            raise HotkeyError("Global shortcuts are not running.")
        if threading.current_thread() is self._thread:
            raise HotkeyError("Change shortcuts from the UI thread, not the shortcut callback.")
        self._commands.put(command)
        if not self._backend.wake(self._thread_id):
            command.cancelled = True
            raise HotkeyError("Could not contact the shortcut thread; settings were not applied.")
        if not command.complete.wait(3):
            command.cancelled = True
            raise HotkeyError("Shortcut update timed out; restart the application to confirm its settings.")
        if command.error:
            raise command.error

    def _register_pair(self, pair):
        for identifier, hotkey in zip((TOGGLE_ID, CANCEL_ID), pair):
            if not self._backend.register(identifier, hotkey):
                raise HotkeyError(f"Shortcut {hotkey.label} is unavailable or already in use. Choose another shortcut.")
            self._active[identifier] = hotkey

    def _clear(self):
        failed = False
        for identifier in list(self._active):
            if self._backend.unregister(identifier):
                del self._active[identifier]
            else:
                failed = True
        if failed:
            raise HotkeyError("Windows could not release a shortcut; restart the application before changing it.")

    def _replace(self, pair):
        if set(self._active) != {TOGGLE_ID, CANCEL_ID}:
            raise HotkeyError("The shortcut registration is incomplete; restart the application.")
        previous = tuple(self._active[identifier] for identifier in (TOGGLE_ID, CANCEL_ID))
        if previous == pair:
            return
        self._clear()
        try:
            self._register_pair(pair)
        except HotkeyError as failure:
            self._clear()
            try:
                self._register_pair(previous)
            except HotkeyError:
                self._clear()
                raise HotkeyError("New shortcuts failed and old shortcuts could not be restored; restart the application.") from None
            raise failure

    def _report(self, message):
        try:
            self._on_error(message)
        except Exception:
            pass  # Never log callback arguments or let a UI error leak native resources.

    def _run(self, pair):
        try:
            self._thread_id = self._backend.initialize_queue()
            if self._startup_cancelled.is_set():
                return
            self._register_pair(pair)
            if self._startup_cancelled.is_set():
                return
            self._ready.set()
            while True:
                message = self._backend.get_message()
                if message is None:
                    break
                kind, identifier = message
                if kind == WM_COMMAND_QUEUE:
                    while True:
                        try:
                            command = self._commands.get_nowait()
                        except queue.Empty:
                            break
                        if command.cancelled:
                            command.complete.set()
                            continue
                        stop = command.action == "stop"
                        try:
                            self._clear() if stop else self._replace(command.pair)
                        except HotkeyError as error:
                            command.error = error
                        finally:
                            command.complete.set()
                        if stop:
                            return
                elif kind == WM_HOTKEY and identifier in self._active:
                    try:
                        self._callbacks[identifier]()
                    except Exception:
                        self._report("The shortcut action failed; try the application controls.")
        except Exception as error:
            safe_error = error if isinstance(error, HotkeyError) else HotkeyError("Windows shortcuts failed; restart the application.")
            if not self._ready.is_set():
                self._startup_error = safe_error
            else:
                self._report(str(safe_error))
        finally:
            try:
                self._clear()
            except HotkeyError as error:
                self._report(str(error))
            self._thread_id = None
            self._ready.set()
            while True:
                try:
                    command = self._commands.get_nowait()
                except queue.Empty:
                    break
                command.error = HotkeyError("The shortcut thread has stopped; settings were not applied.")
                command.complete.set()
