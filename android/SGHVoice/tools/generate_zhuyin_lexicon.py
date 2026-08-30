#!/usr/bin/env python3
"""Build SGH Voice's indexed Traditional Chinese Zhuyin lexicon.

The source is a pinned, locally built McBopomofo checkout. McBopomofo's data
pipeline already resolves Taiwan Zhuyin readings, heterophones and corpus
scores; this tool only filters the generated language model into compact SGH
Voice assets and creates sparse byte-offset indexes for low-heap Android reads.

Upstream: https://github.com/openvanilla/McBopomofo
Pinned commit: 557733124aa3192b3366f7655c5b6c93c28b4ea6
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path


FORMAT_VERSION = 2
PINNED_SOURCE_COMMIT = "557733124aa3192b3366f7655c5b6c93c28b4ea6"
PINNED_SOURCE_DATE = "2026-08-28"
SOURCE_PROJECT_URL = "https://github.com/openvanilla/McBopomofo"
SCORE_SCALE = 10_000
MIN_PHRASE_SCORE = -8.0
DEFAULT_MAX_CANDIDATES = 24
DEFAULT_INDEX_STRIDE = 64
TONE_MARKS = frozenset("ˊˇˋ˙")

EXACT_FILENAME = "traditional_zhuyin_exact.zlex"
FOLDED_FILENAME = "traditional_zhuyin_folded.zlex"
CONTEXT_FILENAME = "traditional_zhuyin_context.zlex"
SNAPSHOT_FILENAME = "snapshot.json"
ATTRIBUTION_FILENAME = "ATTRIBUTION.txt"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_han_character(char: str) -> bool:
    codepoint = ord(char)
    return (
        codepoint == 0x3007
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x323AF
    )


def is_han_text(text: str) -> bool:
    return bool(text) and all(is_han_character(char) for char in text)


def is_zhuyin_syllable(value: str) -> bool:
    if not value:
        return False
    return all("ㄅ" <= char <= "ㄩ" or char in TONE_MARKS for char in value)


def fold_zhuyin_tones(reading: str) -> str:
    return "".join(char for char in reading if char not in TONE_MARKS)


def parse_occurrences(text: str) -> dict[str, int]:
    frequencies: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.rsplit(maxsplit=1)
        if len(parts) != 2:
            continue
        try:
            frequency = int(parts[1])
        except ValueError:
            continue
        frequencies[parts[0]] = max(frequency, frequencies.get(parts[0], 0))
    return frequencies


def parse_base_encodings(text: str) -> dict[str, set[str]]:
    encodings: dict[str, set[str]] = collections.defaultdict(set)
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 5:
            encodings[parts[0]].add(parts[-1])
    return dict(encodings)


def scaled_score(value: str) -> int:
    return round(float(value) * SCORE_SCALE)


def rank_and_limit(
    candidates: dict[str, dict[str, int]],
    max_candidates: int,
) -> dict[str, list[tuple[str, int]]]:
    if max_candidates <= 0:
        raise ValueError("max_candidates must be positive")
    result: dict[str, list[tuple[str, int]]] = {}
    for key, values in candidates.items():
        ranked = sorted(
            values.items(),
            key=lambda item: (-item[1], len(item[0]), item[0]),
        )[:max_candidates]
        if ranked:
            result[key] = ranked
    return result


def build_mcbopomofo_lexicon(
    data_text: str,
    base_text: str,
    frequency_text: str,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> tuple[dict[str, list[tuple[str, int]]], dict[str, int]]:
    """Convert generated McBopomofo data into exact Zhuyin candidates.

    Single characters that only occur in the upstream ``utf8`` compatibility
    bucket and have no corpus occurrence are omitted. This removes Simplified
    compatibility characters from the visible Traditional Chinese candidates
    without performing the unsafe one-codepoint variant substitution used by
    the old Unihan generator.
    """

    frequencies = parse_occurrences(frequency_text)
    encodings = parse_base_encodings(base_text)
    collected: dict[str, dict[str, int]] = collections.defaultdict(dict)
    stats: collections.Counter[str] = collections.Counter()

    for line in data_text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(" ")
        if len(parts) != 3:
            stats["skippedMalformedRowCount"] += 1
            continue
        source_reading, text, score_text = parts
        syllables = source_reading.split("-")
        if (
            source_reading.startswith("_")
            or not is_han_text(text)
            or len(syllables) != len(text)
            or not all(is_zhuyin_syllable(syllable) for syllable in syllables)
        ):
            stats["skippedNonLexicalRowCount"] += 1
            continue
        try:
            source_score = float(score_text)
        except ValueError:
            stats["skippedMalformedRowCount"] += 1
            continue

        if len(text) > 1 and source_score <= MIN_PHRASE_SCORE:
            stats["skippedLowScorePhraseCount"] += 1
            continue
        if len(text) == 1:
            source_encodings = encodings.get(text, set())
            only_utf8_compatibility = source_encodings == {"utf8"}
            if only_utf8_compatibility and frequencies.get(text, 0) <= 0:
                stats["skippedUtf8CompatibilityCharacterCount"] += 1
                continue

        reading = " ".join(syllables)
        score = scaled_score(score_text)
        old_score = collected[reading].get(text)
        if old_score is None or score > old_score:
            collected[reading][text] = score

    ranked = rank_and_limit(dict(collected), max_candidates)
    stats["includedReadingCount"] = len(ranked)
    stats["includedCandidateCount"] = sum(len(values) for values in ranked.values())
    stats["includedPhraseCandidateCount"] = sum(
        len(text) > 1 for values in ranked.values() for text, _ in values
    )
    stats["includedSingleCharacterCount"] = sum(
        len(text) == 1 for values in ranked.values() for text, _ in values
    )
    return ranked, dict(stats)


def build_folded_lexicon(
    exact_entries: dict[str, list[tuple[str, int]]],
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> dict[str, list[tuple[str, int]]]:
    collected: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for reading, entries in exact_entries.items():
        folded = fold_zhuyin_tones(reading)
        for text, score in entries:
            old_score = collected[folded].get(text)
            if old_score is None or score > old_score:
                collected[folded][text] = score
    return rank_and_limit(dict(collected), max_candidates)


def build_mcbopomofo_context_lexicon(
    associated_text: str,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> tuple[dict[str, list[tuple[str, int]]], dict[str, int]]:
    """Convert McBopomofo associated phrases into prefix -> commit suffix."""

    collected: dict[str, dict[str, int]] = collections.defaultdict(dict)
    stats: collections.Counter[str] = collections.Counter()
    for line in associated_text.splitlines():
        if not line or line.startswith("#"):
            continue
        try:
            encoded, score_text = line.rsplit(" ", 1)
            score = scaled_score(score_text)
        except (ValueError, TypeError):
            stats["skippedMalformedContextRowCount"] += 1
            continue

        parts = encoded.split("-")
        if len(parts) < 4 or len(parts) % 2 != 0:
            stats["skippedMalformedContextRowCount"] += 1
            continue
        characters = parts[0::2]
        readings = parts[1::2]
        if (
            not all(len(char) == 1 and is_han_character(char) for char in characters)
            or not all(is_zhuyin_syllable(reading) for reading in readings)
        ):
            stats["skippedNonLexicalContextRowCount"] += 1
            continue

        prefix = characters[0]
        suffix = "".join(characters[1:])
        old_score = collected[prefix].get(suffix)
        if old_score is None or score > old_score:
            collected[prefix][suffix] = score

    ranked = rank_and_limit(dict(collected), max_candidates)
    stats["includedContextPrefixCount"] = len(ranked)
    stats["includedContextCandidateCount"] = sum(
        len(values) for values in ranked.values()
    )
    return ranked, dict(stats)


def render_indexed_lexicon(
    entries: dict[str, list[tuple[str, int]]],
    index_stride: int = DEFAULT_INDEX_STRIDE,
) -> tuple[bytes, bytes]:
    if index_stride <= 0:
        raise ValueError("index_stride must be positive")

    data = bytearray()
    index_lines = [f"# format-version={FORMAT_VERSION}", f"# stride={index_stride}"]
    for line_number, key in enumerate(sorted(entries)):
        if line_number % index_stride == 0:
            index_lines.append(f"{key}\t{len(data)}")
        encoded_candidates = "|".join(
            f"{text}:{score}" for text, score in entries[key]
        )
        data.extend(f"{key}\t{encoded_candidates}\n".encode("utf-8"))
    return bytes(data), ("\n".join(index_lines) + "\n").encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def render_attribution(
    source_commit: str,
    source_date: str,
    exact_stats: dict[str, int],
    context_stats: dict[str, int],
) -> str:
    return f"""SGH Voice Traditional Chinese Zhuyin Lexicon Attribution

This package includes a filtered and re-indexed adaptation of dictionary data
from McBopomofo (小麥注音輸入法).

Project: {SOURCE_PROJECT_URL}
Pinned source: {SOURCE_PROJECT_URL}/tree/{source_commit}
Source snapshot date: {source_date}
Data licence: MIT License
Full licence file: MCBOPOMOFO_LICENSE.txt
Upstream acknowledgements: MCBOPOMOFO_ACKNOWLEDGEMENTS.md
libtabe source-data notice: LIBTABE_NOTICE.txt

Included exact lexicon: {exact_stats['includedReadingCount']} readings /
{exact_stats['includedCandidateCount']} candidates, including
{exact_stats['includedPhraseCandidateCount']} multi-character phrases.
Included associated phrases: {context_stats['includedContextPrefixCount']} prefixes /
{context_stats['includedContextCandidateCount']} commit suffixes.

McBopomofo's Source/Data/README.md states that BPMFMappings.txt was originally
simplified from libtabe's BSD-licensed tsi.src and then modified. This package
preserves that provenance. McBopomofo, OpenVanilla and libtabe do not endorse
SGH Voice. The data is supplied without warranty.

The generated *.zlex files are sorted UTF-8 text with sparse *.zidx byte-offset
indexes. SGH Voice's application code is separately licensed.

Update procedure:
1. Check out the pinned McBopomofo commit.
2. Run `make all` in Source/Data using the upstream build pipeline.
3. Run tools/generate_zhuyin_lexicon.py with --mcbopomofo-data-dir pointing to
   Source/Data and review snapshot.json plus the generator contract tests.
"""


def source_file_metadata(path: Path) -> dict[str, object]:
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcbopomofo-data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", default=PINNED_SOURCE_COMMIT)
    parser.add_argument("--source-date", default=PINNED_SOURCE_DATE)
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_MAX_CANDIDATES)
    parser.add_argument("--index-stride", type=int, default=DEFAULT_INDEX_STRIDE)
    args = parser.parse_args()

    source_dir = args.mcbopomofo_data_dir
    source_paths = {
        "data.txt": source_dir / "data.txt",
        "associated-phrases-v2.txt": source_dir / "associated-phrases-v2.txt",
        "BPMFBase.txt": source_dir / "BPMFBase.txt",
        "phrase.occ": source_dir / "phrase.occ",
    }
    missing = [name for name, path in source_paths.items() if not path.is_file()]
    if missing:
        raise SystemExit("Missing McBopomofo source files: " + ", ".join(missing))

    exact_entries, exact_stats = build_mcbopomofo_lexicon(
        source_paths["data.txt"].read_text(encoding="utf-8"),
        source_paths["BPMFBase.txt"].read_text(encoding="utf-8"),
        source_paths["phrase.occ"].read_text(encoding="utf-8"),
        max_candidates=args.max_candidates,
    )
    folded_entries = build_folded_lexicon(exact_entries, args.max_candidates)
    context_entries, context_stats = build_mcbopomofo_context_lexicon(
        source_paths["associated-phrases-v2.txt"].read_text(encoding="utf-8"),
        max_candidates=args.max_candidates,
    )

    rendered_assets: dict[str, bytes] = {}
    for filename, entries in (
        (EXACT_FILENAME, exact_entries),
        (FOLDED_FILENAME, folded_entries),
        (CONTEXT_FILENAME, context_entries),
    ):
        data, index = render_indexed_lexicon(entries, args.index_stride)
        rendered_assets[filename] = data
        rendered_assets[str(Path(filename).with_suffix(".zidx"))] = index

    for filename, data in rendered_assets.items():
        write_atomic(args.output_dir / filename, data)

    snapshot = {
        "formatVersion": FORMAT_VERSION,
        "generatedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dataLicence": "MIT",
        "sourceAncestryLicence": "BSD-3-Clause (libtabe tsi.src)",
        "sourceProjectUrl": SOURCE_PROJECT_URL,
        "sourceCommit": args.source_commit,
        "sourceCommitUrl": f"{SOURCE_PROJECT_URL}/tree/{args.source_commit}",
        "sourceSnapshotDate": args.source_date,
        "sourceFiles": {
            name: source_file_metadata(path) for name, path in source_paths.items()
        },
        "maxCandidatesPerKey": args.max_candidates,
        "sparseIndexStride": args.index_stride,
        **exact_stats,
        "foldedReadingCount": len(folded_entries),
        "foldedCandidateCount": sum(len(values) for values in folded_entries.values()),
        **context_stats,
        "exactLexiconFile": EXACT_FILENAME,
        "exactLexiconBytes": len(rendered_assets[EXACT_FILENAME]),
        "exactLexiconSha256": sha256_bytes(rendered_assets[EXACT_FILENAME]),
        "foldedLexiconFile": FOLDED_FILENAME,
        "foldedLexiconBytes": len(rendered_assets[FOLDED_FILENAME]),
        "foldedLexiconSha256": sha256_bytes(rendered_assets[FOLDED_FILENAME]),
        "contextLexiconFile": CONTEXT_FILENAME,
        "contextLexiconBytes": len(rendered_assets[CONTEXT_FILENAME]),
        "contextLexiconSha256": sha256_bytes(rendered_assets[CONTEXT_FILENAME]),
        "updateProcedure": (
            "Build the pinned McBopomofo Source/Data target, regenerate the indexed "
            "assets, review snapshot hashes and run the generator contract tests."
        ),
    }
    write_atomic(
        args.output_dir / SNAPSHOT_FILENAME,
        (json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    write_atomic(
        args.output_dir / ATTRIBUTION_FILENAME,
        render_attribution(
            args.source_commit,
            args.source_date,
            exact_stats,
            context_stats,
        ).encode("utf-8"),
    )

    print(
        "Wrote "
        f"{exact_stats['includedReadingCount']} readings / "
        f"{exact_stats['includedCandidateCount']} exact candidates / "
        f"{context_stats['includedContextCandidateCount']} context candidates "
        f"to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
