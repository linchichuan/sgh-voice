"""Shared hotkey parsing, normalization and collision validation.

The Dashboard, native NSEvent listeners and pynput fallback must agree on the
same grammar.  Keeping the map here avoids the previous behavior where the UI
accepted a value but individual listeners silently ignored unknown tokens or
fell back to ``right_cmd``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping


HOTKEY_FIELDS = (
    "hotkey",
    "rewrite_hotkey",
    "retry_hotkey",
    "cancel_hotkey",
    "continuous_hotkey",
)

RECOMMENDED_RECORD_HOTKEY = "right_option+right_shift"
FN_RECORD_HOTKEY = "fn+right_shift"
RECOMMENDED_ACTION_HOTKEYS = {
    # Use only keys present on Apple's compact keyboards.  Keeping the action
    # chords on the left side also makes them disjoint from the right-side PTT
    # chord, so Cancel can be pressed while recording without waking Rewrite.
    "rewrite_hotkey": "ctrl+option",
    "retry_hotkey": "ctrl+shift",
    # Cancel must remain distinguishable while right Option/Shift are held for
    # PTT, including KVMs that expose only generic (not left/right) flags.
    "cancel_hotkey": "ctrl+cmd",
    "continuous_hotkey": "",
}
PREVIOUS_V2_ACTION_HOTKEYS = {
    "rewrite_hotkey": "ctrl+option",
    "retry_hotkey": "ctrl+shift",
    "cancel_hotkey": "option+shift",
}
# v2.5.3 release-candidate defaults.  They are migration candidates rather
# than permanent aliases: right Control is absent from Apple compact keyboards
# and same-family left+right chords are ambiguous on generic-only KVM events.
PREVIOUS_V1_ACTION_HOTKEYS = {
    "rewrite_hotkey": "right_ctrl+right_shift",
    "retry_hotkey": "option+right_option",
    "cancel_hotkey": "ctrl+right_ctrl",
}
INTERIM_V4_ACTION_HOTKEYS = {
    "rewrite_hotkey": "right_ctrl+f9",
    "retry_hotkey": "right_ctrl+f10",
    "cancel_hotkey": "right_ctrl+f11",
}
LEGACY_DEFAULT_HOTKEYS = {
    "hotkey": "right_cmd",
    "rewrite_hotkey": "right_option+r",
    "retry_hotkey": "right_option+y",
    "cancel_hotkey": "right_option+x",
    "continuous_hotkey": "",
}
HOTKEY_MODES = frozenset({"push_to_talk", "toggle"})

# macOS exposes Fn/Globe as one system modifier (kVK_Function / the
# SecondaryFn flag).  It does not expose a left/right identity, even when an
# external keyboard physically places the key on the right.  ``right_fn`` is
# therefore accepted as a user-facing alias and normalized to ``fn``.
FN_KEYCODE = 63
FN_MODIFIER_MASK = 0x800000


KEY_CODES = {
    "cmd": 55,
    "right_cmd": 54,
    "option": 58,
    "right_option": 61,
    "ctrl": 59,
    "right_ctrl": 62,
    "shift": 56,
    "right_shift": 60,
    "fn": FN_KEYCODE,
    "space": 49,
    "escape": 53,
    "f1": 122,
    "f2": 120,
    "f3": 99,
    "f4": 118,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f8": 100,
    "f9": 101,
    "f10": 109,
    "f11": 103,
    "f12": 111,
    "0": 29,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "5": 23,
    "6": 22,
    "7": 26,
    "8": 28,
    "9": 25,
    "a": 0,
    "b": 11,
    "c": 8,
    "d": 2,
    "e": 14,
    "f": 3,
    "g": 5,
    "h": 4,
    "i": 34,
    "j": 38,
    "k": 40,
    "l": 37,
    "m": 46,
    "n": 45,
    "o": 31,
    "p": 35,
    "q": 12,
    "r": 15,
    "s": 1,
    "t": 17,
    "u": 32,
    "v": 9,
    "w": 13,
    "x": 7,
    "y": 16,
    "z": 6,
}

ALIASES = {
    "command": "cmd",
    "left_cmd": "cmd",
    "cmd_l": "cmd",
    "left_command": "cmd",
    "right_command": "right_cmd",
    "alt": "option",
    "left_alt": "option",
    "alt_l": "option",
    "left_option": "option",
    "right_alt": "right_option",
    "alt_r": "right_option",
    "control": "ctrl",
    "left_ctrl": "ctrl",
    "left_control": "ctrl",
    "right_control": "right_ctrl",
    "left_shift": "shift",
    "function": "fn",
    "function_key": "fn",
    "globe": "fn",
    "globe_key": "fn",
    "left_fn": "fn",
    "right_fn": "fn",
    "esc": "escape",
}

MODIFIER_TOKENS = frozenset(
    {
        "cmd",
        "right_cmd",
        "option",
        "right_option",
        "ctrl",
        "right_ctrl",
        "shift",
        "right_shift",
        "fn",
    }
)
MODIFIER_KEYCODES = frozenset(KEY_CODES[token] for token in MODIFIER_TOKENS)
FUNCTION_TOKENS = frozenset(f"f{number}" for number in range(1, 13))

_TOKEN_ORDER = {
    token: index
    for index, token in enumerate(
        (
            "ctrl",
            "right_ctrl",
            "option",
            "right_option",
            "fn",
            "shift",
            "right_shift",
            "cmd",
            "right_cmd",
        )
    )
}

_RESERVED_SHORTCUTS = {
    "cmd+space": "macOS Spotlight",
    "ctrl+space": "macOS input-source switching",
    "cmd+q": "Quit",
    "cmd+w": "Close Window",
    "cmd+a": "Select All",
    "cmd+c": "Copy",
    "cmd+v": "Paste",
    "cmd+x": "Cut",
    "cmd+z": "Undo",
}
_RESERVED_MODIFIER_FAMILY = {
    "right_cmd": "cmd",
    "right_ctrl": "ctrl",
    "right_option": "option",
    "right_shift": "shift",
    "fn": "fn",
}
_MODIFIER_FAMILY = {
    "cmd": "cmd",
    "right_cmd": "cmd",
    "ctrl": "ctrl",
    "right_ctrl": "ctrl",
    "option": "option",
    "right_option": "option",
    "shift": "shift",
    "right_shift": "shift",
    "fn": "fn",
}
_RESERVED_BY_SET = {
    frozenset(item.split("+")): reason
    for item, reason in _RESERVED_SHORTCUTS.items()
}

# NSEvent device-dependent flags keep left/right modifiers distinct.
_DEVICE_MASK_BY_KEYCODE = {
    55: 0x8,
    54: 0x10,
    58: 0x20,
    61: 0x40,
    59: 0x1,
    62: 0x2000,
    56: 0x2,
    60: 0x4,
}
_GENERIC_MASK_BY_KEYCODE = {
    55: 0x100000,
    54: 0x100000,
    58: 0x80000,
    61: 0x80000,
    59: 0x40000,
    62: 0x40000,
    56: 0x20000,
    60: 0x20000,
}
_OPPOSITE_KEYCODE = {
    55: 54,
    54: 55,
    58: 61,
    61: 58,
    59: 62,
    62: 59,
    56: 60,
    60: 56,
}


class HotkeyValidationError(ValueError):
    """Validation error that identifies the affected config field."""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class HotkeySpec:
    field: str
    raw: str
    normalized: str
    tokens: tuple[str, ...]
    keycodes: frozenset[int]


def _canonical_token(token: str) -> str:
    lowered = token.strip().lower()
    return ALIASES.get(lowered, lowered)


def parse_hotkey(
    value,
    *,
    field: str = "hotkey",
    allow_legacy_single_modifier: bool = False,
) -> HotkeySpec:
    """Parse and validate one user-facing hotkey string.

    ``hotkey`` (recording) is required.  Auxiliary actions may be blank to
    disable them.  A printable key must be combined with at least one modifier;
    function keys may be used alone.  Two or more modifiers are also valid,
    which makes the recommended right-side recording chord possible without
    emitting a character into the focused field.  Runtime listeners may opt
    into loading one legacy single-modifier recording shortcut, but newly
    saved settings must never create one.
    """

    if not isinstance(value, str):
        raise HotkeyValidationError("hotkey must be a string", field=field)

    raw = value.strip()
    if not raw:
        if field == "hotkey":
            raise HotkeyValidationError("recording hotkey cannot be empty", field=field)
        return HotkeySpec(field, raw, "", (), frozenset())

    # With an explicit ``+``, allow human-readable labels such as
    # ``Right Fn + Right Shift`` in addition to config-style underscores.
    # Without ``+`` keep the original whitespace-separated grammar so
    # existing inputs like ``ctrl option`` remain valid.
    if "+" in raw:
        source_tokens = [
            re.sub(r"[\s-]+", "_", part.strip())
            for part in raw.split("+")
            if part.strip()
        ]
    else:
        source_tokens = [part for part in re.split(r"\s+", raw) if part]
    tokens = [_canonical_token(part) for part in source_tokens]
    unknown = [token for token in tokens if token not in KEY_CODES]
    if unknown:
        raise HotkeyValidationError(
            f"unsupported hotkey token: {unknown[0]}", field=field
        )
    if len(set(tokens)) != len(tokens):
        raise HotkeyValidationError("hotkey contains a duplicate key", field=field)
    if len(tokens) > 4:
        raise HotkeyValidationError("hotkey may contain at most four keys", field=field)

    modifiers = [token for token in tokens if token in MODIFIER_TOKENS]
    non_modifiers = [token for token in tokens if token not in MODIFIER_TOKENS]
    modifier_families = [_MODIFIER_FAMILY[token] for token in modifiers]
    if len(set(modifier_families)) != len(modifier_families):
        raise HotkeyValidationError(
            "a hotkey cannot combine both sides of the same modifier",
            field=field,
        )
    if len(non_modifiers) > 1:
        raise HotkeyValidationError(
            "hotkey may contain only one non-modifier key", field=field
        )

    if len(tokens) == 1:
        token = tokens[0]
        if token in MODIFIER_TOKENS:
            if field != "hotkey" or not allow_legacy_single_modifier:
                raise HotkeyValidationError(
                    "a hotkey cannot be a single modifier", field=field
                )
        elif token not in FUNCTION_TOKENS:
            raise HotkeyValidationError(
                "a letter, number or Space must include a modifier", field=field
            )
    elif non_modifiers and not modifiers:
        raise HotkeyValidationError(
            "a multi-key hotkey must include a modifier", field=field
        )

    ordered_tokens = tuple(
        sorted(tokens, key=lambda token: (_TOKEN_ORDER.get(token, 100), token))
    )
    normalized = "+".join(ordered_tokens)
    reserved_tokens = frozenset(
        _RESERVED_MODIFIER_FAMILY.get(token, token)
        for token in ordered_tokens
    )
    reason = _RESERVED_BY_SET.get(reserved_tokens)
    if reason:
        raise HotkeyValidationError(
            f"hotkey conflicts with {reason}: {normalized}", field=field
        )

    return HotkeySpec(
        field=field,
        raw=raw,
        normalized=normalized,
        tokens=ordered_tokens,
        keycodes=frozenset(KEY_CODES[token] for token in ordered_tokens),
    )


def validate_hotkey_config(
    config: Mapping[str, object],
    *,
    allow_legacy_recording: str | None = None,
) -> dict[str, str]:
    """Normalize every hotkey and reject ambiguous combinations.

    Action chords may share one key with another action.  Runtime listeners
    require an exact match within the action-key set, so a third modifier does
    not wake a second action.  Recording is stricter: it must be fully disjoint
    from every action because PTT remains held while Cancel is pressed.
    """

    specs = {}
    for field in HOTKEY_FIELDS:
        value = config.get(field, "")
        legacy_allowed = (
            field == "hotkey"
            and allow_legacy_recording is not None
            and isinstance(value, str)
            and value.strip().lower()
            == str(allow_legacy_recording).strip().lower()
        )
        specs[field] = parse_hotkey(
            value,
            field=field,
            allow_legacy_single_modifier=legacy_allowed,
        )
    active = [spec for spec in specs.values() if spec.keycodes]
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if "hotkey" in {left.field, right.field} and (
                left.keycodes & right.keycodes
            ):
                raise HotkeyValidationError(
                    f"{left.field} ({left.normalized}) shares a recording key with "
                    f"{right.field} ({right.normalized})",
                    field=left.field,
                )
            if {left.field, right.field} == {"hotkey", "cancel_hotkey"}:
                left_families = {
                    _MODIFIER_FAMILY[token]
                    for token in left.tokens
                    if token in MODIFIER_TOKENS
                }
                right_families = {
                    _MODIFIER_FAMILY[token]
                    for token in right.tokens
                    if token in MODIFIER_TOKENS
                }
                if left_families & right_families:
                    raise HotkeyValidationError(
                        f"cancel_hotkey ({specs['cancel_hotkey'].normalized}) "
                        "shares a modifier family with the recording hotkey",
                        field="cancel_hotkey",
                    )
            if left.keycodes.issubset(right.keycodes) or right.keycodes.issubset(
                left.keycodes
            ):
                raise HotkeyValidationError(
                    f"{left.field} ({left.normalized}) conflicts with "
                    f"{right.field} ({right.normalized})",
                    field=left.field,
                )
    return {field: spec.normalized for field, spec in specs.items()}


def validate_hotkey_mode(value) -> str:
    """Validate the behavior applied when the recording chord becomes active."""

    if not isinstance(value, str) or value not in HOTKEY_MODES:
        raise HotkeyValidationError(
            "hotkey_mode must be push_to_talk or toggle",
            field="hotkey_mode",
        )
    return value


def modifier_is_pressed(keycode: int, flags: int) -> bool:
    """Interpret an NSEvent modifier flag while preserving left/right sides."""

    if int(keycode) == FN_KEYCODE:
        return bool(int(flags) & FN_MODIFIER_MASK)

    device_mask = _DEVICE_MASK_BY_KEYCODE.get(int(keycode), 0)
    generic_mask = _GENERIC_MASK_BY_KEYCODE.get(int(keycode), 0)
    if not device_mask or not generic_mask:
        return False
    if int(flags) & device_mask:
        return True
    if not (int(flags) & generic_mask):
        return False

    opposite = _OPPOSITE_KEYCODE.get(int(keycode))
    opposite_mask = _DEVICE_MASK_BY_KEYCODE.get(opposite, 0)
    if opposite_mask and int(flags) & opposite_mask:
        return False
    # Some software keyboards/KVMs expose only the generic modifier flag.
    return True
