"""macOS text insertion helpers.

Preferred path uses the Accessibility API's ``AXSelectedText`` attribute, so
normal editable controls receive text at the caret without touching the user's
clipboard.  Apps that do not expose that attribute fall back to a short,
transactional pasteboard swap; the complete pasteboard payload is restored
after the paste event instead of preserving only plain text.
"""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Callable


@dataclass(frozen=True)
class PasteboardSnapshot:
    """An immutable copy of every item/type currently on the pasteboard."""

    items: tuple[tuple[tuple[str, bytes], ...], ...]


def accessibility_is_trusted() -> bool:
    try:
        from ApplicationServices import AXIsProcessTrusted

        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def request_accessibility_prompt() -> bool:
    """Ask macOS to show its native one-time Accessibility permission prompt."""

    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )

        return bool(
            AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        )
    except Exception:
        return accessibility_is_trusted()


def insert_text_via_accessibility(text: str, target_pid: int | None) -> bool:
    """Insert at the active selection/caret without using the pasteboard.

    ``AXSelectedText`` is deliberately the only writable attribute used here.
    Falling back to ``AXValue`` would replace the entire control and could erase
    an existing document.
    """

    if not text or not target_pid or not accessibility_is_trusted():
        return False

    try:
        from ApplicationServices import (
            AXUIElementCopyAttributeValue,
            AXUIElementCreateApplication,
            AXUIElementIsAttributeSettable,
            AXUIElementSetAttributeValue,
            kAXFocusedUIElementAttribute,
            kAXSelectedTextAttribute,
        )

        application = AXUIElementCreateApplication(int(target_pid))
        err, focused = AXUIElementCopyAttributeValue(
            application, kAXFocusedUIElementAttribute, None
        )
        if err != 0 or focused is None:
            return False

        err, settable = AXUIElementIsAttributeSettable(
            focused, kAXSelectedTextAttribute, None
        )
        if err != 0 or not settable:
            return False

        return (
            AXUIElementSetAttributeValue(
                focused, kAXSelectedTextAttribute, str(text)
            )
            == 0
        )
    except Exception:
        return False


def capture_pasteboard(pasteboard=None) -> PasteboardSnapshot:
    """Copy all pasteboard items, including images, files, HTML and rich text."""

    if pasteboard is None:
        from AppKit import NSPasteboard

        pasteboard = NSPasteboard.generalPasteboard()

    captured: list[tuple[tuple[str, bytes], ...]] = []
    for item in pasteboard.pasteboardItems() or []:
        representations: list[tuple[str, bytes]] = []
        for type_name in item.types() or []:
            data = item.dataForType_(type_name)
            if data is not None:
                representations.append((str(type_name), bytes(data)))
        captured.append(tuple(representations))
    return PasteboardSnapshot(tuple(captured))


def stage_text_on_pasteboard(text: str, pasteboard=None) -> int:
    """Temporarily put plain text on the pasteboard and return its changeCount."""

    try:
        from AppKit import NSPasteboardTypeString
    except ImportError:  # test doubles can expose their own type constant
        NSPasteboardTypeString = "public.utf8-plain-text"

    if pasteboard is None:
        from AppKit import NSPasteboard

        pasteboard = NSPasteboard.generalPasteboard()

    pasteboard.clearContents()
    if not pasteboard.setString_forType_(str(text), NSPasteboardTypeString):
        raise RuntimeError("failed to stage text on pasteboard")
    return int(pasteboard.changeCount())


def pasteboard_change_count_matches(
    expected_change_count: int,
    pasteboard=None,
) -> bool:
    """Return whether the staged pasteboard transaction still owns the board.

    This check is intentionally performed immediately before posting Cmd+V.
    If the user copied or cut something while modifier keys were being released,
    the synthetic paste must be cancelled instead of pasting that new content.
    """

    if pasteboard is None:
        from AppKit import NSPasteboard

        pasteboard = NSPasteboard.generalPasteboard()
    try:
        return int(pasteboard.changeCount()) == int(expected_change_count)
    except Exception:
        return False


def restore_pasteboard(
    snapshot: PasteboardSnapshot,
    expected_change_count: int,
    pasteboard=None,
) -> bool:
    """Restore a snapshot unless the user copied/cut something in the meantime."""

    if pasteboard is None:
        from AppKit import NSPasteboard

        pasteboard = NSPasteboard.generalPasteboard()
    if int(pasteboard.changeCount()) != int(expected_change_count):
        return False

    from AppKit import NSPasteboardItem
    from Foundation import NSData

    restored_items = []
    for representations in snapshot.items:
        item = NSPasteboardItem.alloc().init()
        for type_name, payload in representations:
            data = NSData.dataWithBytes_length_(payload, len(payload))
            item.setData_forType_(data, type_name)
        restored_items.append(item)

    pasteboard.clearContents()
    if restored_items:
        pasteboard.writeObjects_(restored_items)
    return True


def schedule_pasteboard_restore(
    snapshot: PasteboardSnapshot,
    expected_change_count: int,
    *,
    delay: float = 0.25,
    restore: Callable[[PasteboardSnapshot, int], bool] = restore_pasteboard,
) -> threading.Thread:
    """Restore after the target app has consumed the synthetic Cmd+V event."""

    def _restore_later() -> None:
        time.sleep(delay)
        try:
            restore(snapshot, expected_change_count)
        except Exception:
            pass

    thread = threading.Thread(target=_restore_later, daemon=True)
    thread.start()
    return thread
