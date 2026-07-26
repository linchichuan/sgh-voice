#!/usr/bin/env python3
"""Generate SGH Voice's compact Japanese IME lexicon from JMdict.

The generator intentionally keeps only exact reading-to-surface mappings for
entries carrying one of JMdict's first-tier priority markers. It does not turn
JMdict into a full morphological or statistical conversion engine.

Official sources:
  JMdict project: https://www.edrdg.org/jmdict/j_jmdict.html
  JMdict_b data:  https://www.edrdg.org/pub/Nihongo/JMdict_b.gz
  EDRDG licence:  https://www.edrdg.org/edrdg/licence.html

The default output directory is app/src/main/assets/japanese. Pass --input to
regenerate from an already-downloaded snapshot without fetching JMdict again.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import tempfile
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SOURCE_NAME = "JMdict_b"
SOURCE_URL = "https://www.edrdg.org/pub/Nihongo/JMdict_b.gz"
PROJECT_URL = "https://www.edrdg.org/jmdict/j_jmdict.html"
EDRDG_URL = "https://www.edrdg.org/"
EDRDG_LICENCE_URL = "https://www.edrdg.org/edrdg/licence.html"
CC_BY_SA_LEGAL_CODE_URL = (
    "https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt"
)
USER_AGENT = "SGH-Voice-JMdict-Generator/1.0"

FORMAT_VERSION = 1
DEFAULT_PRIORITY_TAGS = ("ichi1", "news1", "spec1", "gai1")
PRIORITY_SCORES = {
    "spec1": 4_000,
    "ichi1": 3_000,
    "news1": 2_000,
    "gai1": 2_000,
}
NF_RE = re.compile(r"^nf(\d{2})$")
CREATED_RE = re.compile(rb"JMdict created:\s*(\d{4}-\d{2}-\d{2})")


def download(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def read_source(input_path: Path | None) -> tuple[bytes, str]:
    if input_path is None:
        return download(SOURCE_URL), SOURCE_URL
    return input_path.read_bytes(), "local-file"


def decompress_source(source_bytes: bytes) -> bytes:
    if source_bytes.startswith(b"\x1f\x8b"):
        return gzip.decompress(source_bytes)
    return source_bytes


def katakana_to_hiragana(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    output: list[str] = []
    for char in normalized:
        codepoint = ord(char)
        if 0x30A1 <= codepoint <= 0x30F6 or 0x30FD <= codepoint <= 0x30FE:
            output.append(chr(codepoint - 0x60))
        else:
            output.append(char)
    return "".join(output)


def element_texts(element: ET.Element, tag: str) -> list[str]:
    return [
        child.text.strip()
        for child in element.findall(tag)
        if child.text and child.text.strip()
    ]


def score_priority(tags: Iterable[str]) -> int:
    unique_tags = set(tags)
    primary_score = sum(PRIORITY_SCORES.get(tag, 0) for tag in unique_tags)
    nf_values = [
        int(match.group(1))
        for tag in unique_tags
        if (match := NF_RE.fullmatch(tag)) is not None
    ]
    # nf01 is the highest-frequency 500-word band. It is a tie-breaker;
    # first-tier priority markers remain the main ranking signal.
    nf_score = 100 - min(nf_values) if nf_values else 0
    return primary_score + nf_score


def is_safe_field(value: str) -> bool:
    return bool(value) and "\t" not in value and "\n" not in value and "\r" not in value


def extract_candidates(
    xml_bytes: bytes,
    priority_tags: set[str],
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    candidates: dict[str, dict[str, int]] = defaultdict(dict)
    stats = {
        "scannedEntryCount": 0,
        "priorityEntryCount": 0,
        "candidatePairCountBeforeDeduplication": 0,
    }

    parser = ET.iterparse(io.BytesIO(xml_bytes), events=("end",))
    for _, entry in parser:
        if entry.tag != "entry":
            continue
        stats["scannedEntryCount"] += 1

        written_forms: list[tuple[str, set[str]]] = []
        for kanji_element in entry.findall("k_ele"):
            surface = (kanji_element.findtext("keb") or "").strip()
            if not is_safe_field(surface):
                continue
            written_forms.append(
                (surface, set(element_texts(kanji_element, "ke_pri")))
            )

        entry_produced_candidate = False
        for reading_element in entry.findall("r_ele"):
            raw_reading = (reading_element.findtext("reb") or "").strip()
            if not is_safe_field(raw_reading):
                continue
            reading = katakana_to_hiragana(raw_reading)
            if not is_safe_field(reading):
                continue

            reading_tags = set(element_texts(reading_element, "re_pri"))
            restrictions = set(element_texts(reading_element, "re_restr"))
            no_kanji = reading_element.find("re_nokanji") is not None

            if no_kanji or not written_forms:
                applicable_forms = [(raw_reading, reading_tags)]
            elif restrictions:
                applicable_forms = [
                    (surface, tags)
                    for surface, tags in written_forms
                    if surface in restrictions
                ]
            else:
                applicable_forms = written_forms

            prioritized_forms = [
                (surface, tags)
                for surface, tags in applicable_forms
                if tags.intersection(priority_tags)
            ]
            if prioritized_forms:
                selected_forms = prioritized_forms
            elif reading_tags.intersection(priority_tags) and applicable_forms:
                # A common reading can be attached to several rare spelling
                # variants. JMdict orders the normal/default orthography first;
                # retaining only that form avoids suggestions such as obsolete
                # kanji spellings outranking the ordinary kana fallback.
                selected_forms = applicable_forms[:1]
            else:
                selected_forms = []

            for surface, surface_tags in selected_forms:
                pair_tags = reading_tags | surface_tags
                # Plain hiragana is always supplied by JapaneseComposer. Keep
                # katakana spellings and written forms, but omit duplicate raw
                # hiragana to reduce the packaged asset.
                if surface == reading:
                    entry_produced_candidate = True
                    continue
                if not is_safe_field(surface):
                    continue

                score = score_priority(pair_tags)
                candidates_for_reading = candidates[reading]
                candidates_for_reading[surface] = max(
                    score,
                    candidates_for_reading.get(surface, 0),
                )
                stats["candidatePairCountBeforeDeduplication"] += 1
                entry_produced_candidate = True

        if entry_produced_candidate:
            stats["priorityEntryCount"] += 1
        entry.clear()

    return dict(candidates), stats


def rank_and_limit(
    candidates: dict[str, dict[str, int]],
    max_candidates: int,
) -> dict[str, list[tuple[str, int]]]:
    result: dict[str, list[tuple[str, int]]] = {}
    for reading, surfaces in candidates.items():
        ranked = sorted(
            surfaces.items(),
            key=lambda item: (-item[1], len(item[0]), item[0]),
        )[:max_candidates]
        if ranked:
            result[reading] = ranked
    return result


def render_lexicon(
    entries: dict[str, list[tuple[str, int]]],
    snapshot_date: str,
    priority_tags: set[str],
) -> bytes:
    lines = [
        "# SGH Voice compact JMdict common-word candidates",
        f"# format-version={FORMAT_VERSION}",
        f"# source={SOURCE_NAME}",
        f"# source-created={snapshot_date}",
        f"# source-url={SOURCE_URL}",
        f"# priority-tags={','.join(sorted(priority_tags))}",
        "# format=reading<TAB>score<TAB>candidate",
    ]
    for reading in sorted(entries):
        for surface, score in entries[reading]:
            lines.append(f"{reading}\t{score}\t{surface}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def render_attribution(
    snapshot_date: str,
    source_sha256: str,
    reading_count: int,
    candidate_count: int,
    priority_tags: set[str],
) -> str:
    return f"""SGH Voice Japanese Lexicon Attribution

This package uses a filtered subset of the JMdict/EDICT dictionary files.
These files are the property of the Electronic Dictionary Research and
Development Group (EDRDG), and are used in conformance with the Group's
licence.

Project: {PROJECT_URL}
EDRDG: {EDRDG_URL}
Licence statement: {EDRDG_LICENCE_URL}
Data licence: Creative Commons Attribution-ShareAlike 4.0 International
Full licence file: CC-BY-SA-4.0.txt

Source distribution: {SOURCE_URL}
Source snapshot date: {snapshot_date}
Source SHA-256: {source_sha256}
Included subset: {reading_count} exact readings / {candidate_count} candidates
Priority filters: {", ".join(sorted(priority_tags))}

The generated jmdict_common.tsv and adaptations of that data are distributed
under CC BY-SA 4.0. The SGH Voice application code is separately licensed.
JMdict does not endorse SGH Voice. The data is supplied without warranty.

Update procedure:
Run tools/generate_japanese_lexicon.py against the current official JMdict_b
distribution, review the generated snapshot metadata and tests, then include
the refreshed assets in the next APK release.
"""


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary_path = Path(handle.name)
        handle.write(data)
    temporary_path.replace(path)


def parse_args() -> argparse.Namespace:
    default_output = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "src"
        / "main"
        / "assets"
        / "japanese"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="Local JMdict_b.gz or uncompressed JMdict XML snapshot.",
    )
    parser.add_argument("--output-dir", type=Path, default=default_output)
    parser.add_argument("--max-candidates", type=int, default=24)
    parser.add_argument(
        "--priority-tag",
        action="append",
        dest="priority_tags",
        help=(
            "JMdict priority tag to retain. Repeat for multiple tags. "
            f"Default: {', '.join(DEFAULT_PRIORITY_TAGS)}"
        ),
    )
    parser.add_argument(
        "--license-file",
        type=Path,
        help="Use a local CC BY-SA 4.0 legal-code text instead of downloading it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_candidates <= 0:
        raise SystemExit("--max-candidates must be greater than zero")

    priority_tags = set(args.priority_tags or DEFAULT_PRIORITY_TAGS)
    source_bytes, fetched_from = read_source(args.input)
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    xml_bytes = decompress_source(source_bytes)
    if not xml_bytes.lstrip().startswith(b"<?xml"):
        raise SystemExit("Input is not a JMdict XML document or gzip archive")

    created_match = CREATED_RE.search(xml_bytes[:500_000])
    snapshot_date = (
        created_match.group(1).decode("ascii")
        if created_match
        else "unknown"
    )

    extracted, stats = extract_candidates(xml_bytes, priority_tags)
    entries = rank_and_limit(extracted, args.max_candidates)
    candidate_count = sum(len(values) for values in entries.values())
    if not entries or candidate_count == 0:
        raise SystemExit("No priority candidates were generated; refusing empty output")

    lexicon_bytes = render_lexicon(entries, snapshot_date, priority_tags)
    lexicon_sha256 = hashlib.sha256(lexicon_bytes).hexdigest()

    if args.license_file:
        licence_bytes = args.license_file.read_bytes()
    else:
        licence_bytes = download(CC_BY_SA_LEGAL_CODE_URL)
    licence_sha256 = hashlib.sha256(licence_bytes).hexdigest()

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata = {
        "formatVersion": FORMAT_VERSION,
        "source": SOURCE_NAME,
        "sourceProjectUrl": PROJECT_URL,
        "sourceUrl": SOURCE_URL,
        "sourceFetchedFrom": fetched_from,
        "sourceCreated": snapshot_date,
        "sourceSha256": source_sha256,
        "sourceBytes": len(source_bytes),
        "generatedAtUtc": generated_at,
        "priorityTags": sorted(priority_tags),
        "maxCandidatesPerReading": args.max_candidates,
        "scannedEntryCount": stats["scannedEntryCount"],
        "priorityEntryCount": stats["priorityEntryCount"],
        "candidatePairCountBeforeDeduplication": stats[
            "candidatePairCountBeforeDeduplication"
        ],
        "readingCount": len(entries),
        "candidateCount": candidate_count,
        "lexiconFile": "jmdict_common.tsv",
        "lexiconBytes": len(lexicon_bytes),
        "lexiconSha256": lexicon_sha256,
        "dataLicence": "CC BY-SA 4.0",
        "licenceStatementUrl": EDRDG_LICENCE_URL,
        "legalCodeUrl": CC_BY_SA_LEGAL_CODE_URL,
        "legalCodeSha256": licence_sha256,
        "updateProcedure": (
            "Regenerate from the current official JMdict_b distribution and "
            "ship the refreshed assets with an APK release."
        ),
    }
    metadata_bytes = (
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    attribution_bytes = render_attribution(
        snapshot_date,
        source_sha256,
        len(entries),
        candidate_count,
        priority_tags,
    ).encode("utf-8")

    output_dir = args.output_dir.resolve()
    write_atomic(output_dir / "jmdict_common.tsv", lexicon_bytes)
    write_atomic(output_dir / "snapshot.json", metadata_bytes)
    write_atomic(output_dir / "ATTRIBUTION.txt", attribution_bytes)
    write_atomic(output_dir / "CC-BY-SA-4.0.txt", licence_bytes)

    print(
        f"Wrote {len(entries)} readings / {candidate_count} candidates "
        f"({len(lexicon_bytes)} bytes) from JMdict {snapshot_date} "
        f"to {output_dir}"
    )


if __name__ == "__main__":
    main()
