"""Conservative Win32 text delivery; importing this module never loads a DLL.

SendInput targets the foreground input queue, not an HWND. We verify the captured
window and native focus immediately before sending, but Windows offers no atomic
"check HWND then send" operation. Native password styles can be detected; custom
or browser password fields are not reliably exposed by this adapter. Callers must
keep automatic insertion opt-in and provide an explicit Copy action.
"""

from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass

# Fixed-width Windows types also keep the ABI tests meaningful on Unix hosts.
WORD = ctypes.c_uint16
DWORD = UINT = ctypes.c_uint32
LONG = BOOL = ctypes.c_int32
HANDLE = HWND = ctypes.c_void_p
ULONG_PTR = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t


class POINT(ctypes.Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", LONG), ("top", LONG), ("right", LONG), ("bottom", LONG)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", LONG), ("dy", LONG), ("mouseData", DWORD),
                ("dwFlags", DWORD), ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", WORD), ("wScan", WORD), ("dwFlags", DWORD),
                ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD)]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [("type", DWORD), ("data", INPUTUNION)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", DWORD), ("flags", DWORD), ("hwndActive", HWND),
                ("hwndFocus", HWND), ("hwndCapture", HWND), ("hwndMenuOwner", HWND),
                ("hwndMoveSize", HWND), ("hwndCaret", HWND), ("rcCaret", RECT)]


class NativeInputError(RuntimeError):
    """A content-free, user-displayable native operation failure."""


@dataclass(frozen=True)
class TargetWindow:
    hwnd: int
    process_id: int
    focus_hwnd: int


@dataclass(frozen=True)
class InputResult:
    success: bool
    sent_events: int = 0
    total_events: int = 0
    reason: str = ""


def _bind(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes = args
    function.restype = result
    return function


def _unicode_inputs(text: str):
    encoded = text.encode("utf-16-le")
    units = [int.from_bytes(encoded[i:i + 2], "little") for i in range(0, len(encoded), 2)]
    events = (INPUT * (len(units) * 2))()
    for index, unit in enumerate(units):
        for release in (0, 1):
            event = events[index * 2 + release]
            event.type = 1  # INPUT_KEYBOARD
            event.ki = KEYBDINPUT(0, unit, 0x0004 | (0x0002 if release else 0), 0, 0)
    return events


class Win32Backend:
    """Thin ctypes boundary, injectable for tests. Construct only on Windows."""

    def __init__(self, user32=None, kernel32=None):
        if user32 is None or kernel32 is None:
            if sys.platform != "win32":
                raise NativeInputError("Windows native input is available only on Windows.")
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user32, self.kernel32 = user32, kernel32
        _bind(user32, "GetForegroundWindow", [], HWND)
        _bind(user32, "IsWindow", [HWND], BOOL)
        _bind(user32, "GetWindowThreadProcessId", [HWND, ctypes.POINTER(DWORD)], DWORD)
        _bind(user32, "GetGUIThreadInfo", [DWORD, ctypes.POINTER(GUITHREADINFO)], BOOL)
        _bind(user32, "GetClassNameW", [HWND, ctypes.c_wchar_p, ctypes.c_int], ctypes.c_int)
        # GetWindowLongPtrW is a macro alias for GetWindowLongW on 32-bit Windows.
        long_name = "GetWindowLongPtrW" if ctypes.sizeof(HWND) == 8 else "GetWindowLongW"
        self._window_style = _bind(user32, long_name, [HWND, ctypes.c_int], LPARAM)
        _bind(user32, "GetAsyncKeyState", [ctypes.c_int], ctypes.c_int16)
        _bind(user32, "SendInput", [UINT, ctypes.POINTER(INPUT), ctypes.c_int], UINT)
        _bind(user32, "RegisterClipboardFormatW", [ctypes.c_wchar_p], UINT)
        _bind(user32, "CreateWindowExW", [DWORD, ctypes.c_wchar_p, ctypes.c_wchar_p,
              DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
              HWND, HANDLE, HANDLE, ctypes.c_void_p], HWND)
        _bind(user32, "DestroyWindow", [HWND], BOOL)
        _bind(user32, "OpenClipboard", [HWND], BOOL)
        _bind(user32, "CloseClipboard", [], BOOL)
        _bind(user32, "EmptyClipboard", [], BOOL)
        _bind(user32, "SetClipboardData", [UINT, HANDLE], HANDLE)
        _bind(kernel32, "GlobalAlloc", [UINT, ctypes.c_size_t], HANDLE)
        _bind(kernel32, "GlobalLock", [HANDLE], ctypes.c_void_p)
        _bind(kernel32, "GlobalUnlock", [HANDLE], BOOL)
        _bind(kernel32, "GlobalFree", [HANDLE], HANDLE)

    def foreground(self) -> int:
        return int(self.user32.GetForegroundWindow() or 0)

    def process_id(self, hwnd: int) -> int:
        pid = DWORD()
        if not self.user32.IsWindow(hwnd):
            return 0
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def focus(self, hwnd: int) -> int:
        thread_id = self.user32.GetWindowThreadProcessId(hwnd, None)
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(info)
        if not thread_id or not self.user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            return 0
        if int(info.hwndActive or 0) != hwnd:
            return 0
        return int(info.hwndFocus or 0)

    def password_control(self, hwnd: int) -> bool | None:
        name = ctypes.create_unicode_buffer(256)
        if not self.user32.GetClassNameW(hwnd, name, len(name)):
            return None
        # ES_PASSWORD is shared by standard Edit and RichEdit controls. Other
        # widget classes may use this style bit for an unrelated purpose.
        if "edit" in name.value.lower():
            return bool(self._window_style(hwnd, -16) & 0x0020)
        return False

    def modifiers_down(self) -> bool:
        return any(self.user32.GetAsyncKeyState(key) & 0x8000
                   for key in (0x10, 0x11, 0x12, 0x5B, 0x5C))

    def send_inputs(self, events) -> int:
        return int(self.user32.SendInput(len(events), events, ctypes.sizeof(INPUT)))

    def _allocate(self, data: bytes) -> int:
        handle = self.kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        if not handle:
            raise NativeInputError("Could not allocate clipboard memory.")
        pointer = self.kernel32.GlobalLock(handle)
        if not pointer:
            self.kernel32.GlobalFree(handle)
            raise NativeInputError("Could not access clipboard memory.")
        try:
            ctypes.memmove(pointer, data, len(data))
        finally:
            self.kernel32.GlobalUnlock(handle)
        return handle

    def copy_text(self, text: str) -> None:
        """Copy after explicit user action; never called by send_text.

        Windows history/cloud exclusion flags do not prevent other local programs
        or third-party clipboard managers from reading the current clipboard.
        """
        # Prepare everything before clearing the user's existing clipboard.
        formats = []
        for name in ("CanIncludeInClipboardHistory", "CanUploadToCloudClipboard",
                     "ExcludeClipboardContentFromMonitorProcessing"):
            format_id = self.user32.RegisterClipboardFormatW(name)
            if not format_id:
                raise NativeInputError("Could not apply clipboard privacy settings; nothing was copied.")
            formats.append((format_id, b"\x00" * 4))
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        formats.append((13, normalized.encode("utf-16-le") + b"\x00\x00"))
        allocations = []
        owner = None
        opened = False
        try:
            for format_id, data in formats:
                allocations.append([format_id, self._allocate(data)])
            # A real, non-visible owner is required after EmptyClipboard. Using
            # NULL ownership would make SetClipboardData fail on Windows.
            owner = self.user32.CreateWindowExW(
                0, "STATIC", "SGHVoice Clipboard", 0, 0, 0, 0, 0,
                HWND(-3), None, None, None,  # HWND_MESSAGE
            )
            if not owner:
                raise NativeInputError("Could not create the clipboard owner; nothing was copied.")
            if not self.user32.OpenClipboard(owner):
                raise NativeInputError("Clipboard is busy; nothing was copied. Try Copy again.")
            opened = True
            if not self.user32.EmptyClipboard():
                raise NativeInputError("Could not clear the clipboard; nothing was copied.")
            for allocation in allocations:
                if not self.user32.SetClipboardData(*allocation):
                    raise NativeInputError("Clipboard copy failed; use Copy again when ready.")
                allocation[1] = None  # Windows now owns this HGLOBAL.
        finally:
            if opened:
                self.user32.CloseClipboard()
            if owner:
                self.user32.DestroyWindow(owner)
            for _, handle in allocations:
                if handle:
                    self.kernel32.GlobalFree(handle)


class WindowsNative:
    def __init__(self, backend=None, own_pid: int | None = None):
        self._backend = backend if backend is not None else Win32Backend()
        self._own_pid = os.getpid() if own_pid is None else own_pid

    def capture_target(self) -> TargetWindow:
        hwnd = self._backend.foreground()
        pid = self._backend.process_id(hwnd) if hwnd else 0
        focus = self._backend.focus(hwnd) if pid else 0
        if not hwnd or not pid or pid == self._own_pid or not focus:
            raise NativeInputError("Choose a text field in another application before recording.")
        if self._backend.foreground() != hwnd:
            raise NativeInputError("The active window changed; choose the target text field again.")
        return TargetWindow(hwnd, pid, focus)

    def send_text(self, target: TargetWindow | None, text: str) -> InputResult:
        """Submit one batch once; success means queued, not target acknowledgement."""
        if not isinstance(text, str) or not text:
            return InputResult(False, reason="There is no text to insert.")
        # Enter/Tab can submit forms or move focus. Multiline output stays in the
        # UI for explicit Copy instead of being converted into keyboard actions.
        if any(ord(character) < 32 or 0x7F <= ord(character) < 0xA0 for character in text):
            return InputResult(False, reason="Text contains line breaks or controls; use Copy explicitly.")
        if len(text) > 32768:
            return InputResult(False, reason="Text is too long for automatic input; use Copy explicitly.")
        try:
            events = _unicode_inputs(text)
        except UnicodeEncodeError:
            return InputResult(False, reason="Text contains invalid Unicode.")
        total = len(events)
        if target is None or target.process_id == self._own_pid:
            return InputResult(False, total_events=total, reason="No external target was captured; use Copy explicitly.")
        try:
            backend = self._backend
            if (backend.foreground() != target.hwnd
                    or backend.process_id(target.hwnd) != target.process_id):
                return InputResult(False, total_events=total, reason="The target window changed; nothing was inserted.")
            if backend.focus(target.hwnd) != target.focus_hwnd or not target.focus_hwnd:
                return InputResult(False, total_events=total, reason="The target text field changed; nothing was inserted.")
            password = backend.password_control(target.focus_hwnd)
            if password is not False:
                return InputResult(False, total_events=total, reason="The field is protected or could not be checked; nothing was inserted.")
            if backend.modifiers_down():
                return InputResult(False, total_events=total, reason="A modifier key is held; nothing was inserted. Use Copy when ready.")
            # Last possible check: do not move focus, activate windows, retry,
            # elevate, or fall back to the clipboard after a failed submission.
            if (backend.foreground() != target.hwnd
                    or backend.focus(target.hwnd) != target.focus_hwnd):
                return InputResult(False, total_events=total, reason="The target changed before input; nothing was inserted.")
            sent = backend.send_inputs(events)
        except Exception:
            # Backend exceptions could contain application data: never forward
            # their text into logs or the UI.
            return InputResult(False, total_events=total, reason="Native input failed; check the target before using Copy.")
        if sent != total:
            reason = ("Windows blocked input, or the target has higher privileges; nothing was queued."
                      if sent == 0 else "Windows accepted only part of the input. Check the target before using Copy to avoid duplicates.")
            return InputResult(False, sent_events=sent, total_events=total, reason=reason)
        return InputResult(True, sent_events=sent, total_events=total,
                           reason="Text was submitted to the target; verify it in the receiving application.")

    def copy_text(self, text: str) -> None:
        if not isinstance(text, str) or not text:
            raise NativeInputError("There is no text to copy.")
        if "\x00" in text:
            raise NativeInputError("Text contains an unsupported null character; nothing was copied.")
        try:
            text.encode("utf-16-le")
        except UnicodeEncodeError:
            raise NativeInputError("Text contains invalid Unicode; nothing was copied.") from None
        self._backend.copy_text(text)
