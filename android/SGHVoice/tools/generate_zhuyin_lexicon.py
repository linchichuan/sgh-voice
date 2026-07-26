#!/usr/bin/env python3
"""Generate a compact Traditional Chinese Zhuyin candidate asset.

Source data:
  Unicode Unihan `kHanyuPinlu` and `kTraditionalVariant`
  https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip

The generated TSV is intentionally limited to common single-character
candidates with published corpus counts. Multi-character phrase prediction and
user learning remain separate concerns for a future full input engine.
"""

from __future__ import annotations

import argparse
import collections
import io
import re
import tempfile
import unicodedata
import urllib.request
import zipfile
from pathlib import Path


UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
TOKEN_RE = re.compile(r"(.+?)\((\d+)\)")

INITIALS = {
    "b": "ㄅ",
    "p": "ㄆ",
    "m": "ㄇ",
    "f": "ㄈ",
    "d": "ㄉ",
    "t": "ㄊ",
    "n": "ㄋ",
    "l": "ㄌ",
    "g": "ㄍ",
    "k": "ㄎ",
    "h": "ㄏ",
    "j": "ㄐ",
    "q": "ㄑ",
    "x": "ㄒ",
    "zh": "ㄓ",
    "ch": "ㄔ",
    "sh": "ㄕ",
    "r": "ㄖ",
    "z": "ㄗ",
    "c": "ㄘ",
    "s": "ㄙ",
}

FINALS = {
    "": "",
    "a": "ㄚ",
    "o": "ㄛ",
    "e": "ㄜ",
    "ê": "ㄝ",
    "ai": "ㄞ",
    "ei": "ㄟ",
    "ao": "ㄠ",
    "ou": "ㄡ",
    "an": "ㄢ",
    "en": "ㄣ",
    "ang": "ㄤ",
    "eng": "ㄥ",
    "er": "ㄦ",
    "i": "ㄧ",
    "ia": "ㄧㄚ",
    "io": "ㄧㄛ",
    "ie": "ㄧㄝ",
    "iai": "ㄧㄞ",
    "iao": "ㄧㄠ",
    "iou": "ㄧㄡ",
    "ian": "ㄧㄢ",
    "in": "ㄧㄣ",
    "iang": "ㄧㄤ",
    "ing": "ㄧㄥ",
    "iong": "ㄩㄥ",
    "u": "ㄨ",
    "ua": "ㄨㄚ",
    "uo": "ㄨㄛ",
    "uai": "ㄨㄞ",
    "uei": "ㄨㄟ",
    "uan": "ㄨㄢ",
    "uen": "ㄨㄣ",
    "uang": "ㄨㄤ",
    "ueng": "ㄨㄥ",
    "ong": "ㄨㄥ",
    "v": "ㄩ",
    "ve": "ㄩㄝ",
    "van": "ㄩㄢ",
    "vn": "ㄩㄣ",
}

TONE_MARKS = {1: "", 2: "ˊ", 3: "ˇ", 4: "ˋ", 5: "˙"}
COMBINING_TONES = {"\u0304": 1, "\u0301": 2, "\u030c": 3, "\u0300": 4}
APICAL_INITIALS = {"zh", "ch", "sh", "r", "z", "c", "s"}


def strip_tone(pinyin: str) -> tuple[str, int]:
    tone = 5
    output: list[str] = []
    for char in unicodedata.normalize("NFD", pinyin.lower()):
        if char in COMBINING_TONES:
            tone = COMBINING_TONES[char]
        elif char == "\u0308":
            if output and output[-1] == "u":
                output[-1] = "v"
        elif unicodedata.combining(char):
            continue
        elif char not in {"'", "’", "-"}:
            output.append(char)
    return "".join(output), tone


def pinyin_to_zhuyin(pinyin: str) -> str | None:
    base, tone = strip_tone(pinyin)
    if not base:
        return None

    initial = ""
    final = base

    if base.startswith("y"):
        rest = base[1:]
        if rest.startswith("i"):
            final = rest
        elif rest.startswith("u"):
            final = "v" + rest[1:]
        else:
            final = "i" + rest
    elif base.startswith("w"):
        rest = base[1:]
        final = rest if rest.startswith("u") else "u" + rest
    else:
        for candidate in ("zh", "ch", "sh"):
            if base.startswith(candidate):
                initial = candidate
                final = base[len(candidate) :]
                break
        else:
            if base[0] in INITIALS:
                initial = base[0]
                final = base[1:]

    if initial in {"j", "q", "x"} and final.startswith("u"):
        final = "v" + final[1:]

    if initial in APICAL_INITIALS and final == "i":
        final = ""
    elif final == "iu":
        final = "iou"
    elif final == "ui":
        final = "uei"
    elif final == "un":
        final = "uen"

    final_symbols = FINALS.get(final)
    if final_symbols is None:
        return None
    initial_symbol = INITIALS.get(initial, "")
    return initial_symbol + final_symbols + TONE_MARKS[tone]


def parse_unihan(zip_bytes: bytes, max_candidates: int) -> dict[str, list[tuple[str, int]]]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        readings = archive.read("Unihan_Readings.txt").decode("utf-8")
        variants = archive.read("Unihan_Variants.txt").decode("utf-8")

    traditional_variants: dict[int, int] = {}
    for line in variants.splitlines():
        if "\tkTraditionalVariant\t" not in line:
            continue
        codepoint, _, values = line.split("\t", 2)
        source_cp = int(codepoint[2:], 16)
        variant_codepoints = [
            int(value, 16) for value in re.findall(r"U\+([0-9A-F]+)", values)
        ]
        # Some Unihan rows list the simplified code point itself first, for
        # example 勢 as "U+52BF U+52E2". Prefer the first genuinely different
        # Traditional variant so the Android candidate strip stays 繁體中文.
        preferred_variant = next(
            (candidate for candidate in variant_codepoints if candidate != source_cp),
            source_cp,
        )
        traditional_variants[source_cp] = preferred_variant

    ranked: dict[str, dict[str, int]] = collections.defaultdict(dict)
    skipped = 0
    for line in readings.splitlines():
        if "\tkHanyuPinlu\t" not in line:
            continue
        codepoint, _, values = line.split("\t", 2)
        source_cp = int(codepoint[2:], 16)
        output_cp = traditional_variants.get(source_cp, source_cp)
        output_char = chr(output_cp)

        for pinyin, count_text in TOKEN_RE.findall(values):
            reading = pinyin_to_zhuyin(pinyin)
            if reading is None:
                skipped += 1
                continue
            count = int(count_text)
            ranked[reading][output_char] = max(count, ranked[reading].get(output_char, 0))

    if skipped:
        print(f"Skipped {skipped} unsupported pinyin readings.")

    return {
        reading: sorted(characters.items(), key=lambda item: (-item[1], item[0]))[
            :max_candidates
        ]
        for reading, characters in ranked.items()
    }


def render_tsv(entries: dict[str, list[tuple[str, int]]]) -> str:
    lines = [
        "# SGH Voice compact Zhuyin candidates",
        "# Source: Unicode Unihan 17.0.0 kHanyuPinlu + kTraditionalVariant",
        f"# Download: {UNIHAN_URL}",
        "# License: Unicode-3.0 (see UNICODE_LICENSE.txt)",
        "# Format: reading<TAB>candidate:corpus_count|...",
    ]
    for reading in sorted(entries):
        candidates = "|".join(f"{text}:{score}" for text, score in entries[reading])
        lines.append(f"{reading}\t{candidates}")
    return "\n".join(lines) + "\n"


def self_check() -> None:
    cases = {
        "nǐ": "ㄋㄧˇ",
        "hǎo": "ㄏㄠˇ",
        "shì": "ㄕˋ",
        "zhōng": "ㄓㄨㄥ",
        "guó": "ㄍㄨㄛˊ",
        "wǒ": "ㄨㄛˇ",
        "yuè": "ㄩㄝˋ",
        "xióng": "ㄒㄩㄥˊ",
        "lüè": "ㄌㄩㄝˋ",
        "ér": "ㄦˊ",
        "de": "ㄉㄜ˙",
    }
    for pinyin, expected in cases.items():
        actual = pinyin_to_zhuyin(pinyin)
        if actual != expected:
            raise AssertionError(f"{pinyin}: expected {expected}, got {actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unihan-zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-candidates", type=int, default=24)
    args = parser.parse_args()

    self_check()
    if args.unihan_zip:
        zip_bytes = args.unihan_zip.read_bytes()
    else:
        with urllib.request.urlopen(UNIHAN_URL, timeout=30) as response:
            zip_bytes = response.read()

    entries = parse_unihan(zip_bytes, args.max_candidates)
    output = render_tsv(entries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8")

    candidate_count = sum(len(values) for values in entries.values())
    print(
        f"Wrote {len(entries)} readings / {candidate_count} candidates "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()
