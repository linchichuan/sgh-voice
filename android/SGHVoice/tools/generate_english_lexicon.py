#!/usr/bin/env python3
"""Build offline English completions from a pinned AOSP LatinIME dictionary.

Only this build tool reads network resources. The APK ships the generated TSV,
attribution, snapshot and the complete upstream Apache-2.0/Lexiteria notice.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_COMMIT = "127336e9f29d69607eab55982324b210279ae8c5"
SOURCE_SHA256 = "07682388185c285d307e341d1733331af8699f735b4137e9f22571017fab69d2"
NOTICE_SHA256 = "d04394c729fc9fda050d5733d8ee11663fb54fe54d94532de968cf85c1cc42fb"
SOURCE_ROOT = "https://android.googlesource.com/platform/packages/inputmethods/LatinIME"
SOURCE_URL = f"{SOURCE_ROOT}/+/{SOURCE_COMMIT}/dictionaries/en_wordlist.combined.gz"
NOTICE_URL = f"{SOURCE_ROOT}/+/{SOURCE_COMMIT}/NOTICE"
WORD = re.compile(r"^[a-z]{2,32}(?:'[a-z]+)?$")


def extract_words(text: str, min_frequency: int = 60, max_words: int = 50_000):
    words: dict[str, int] = {}
    scanned = flagged = 0
    for line in text.splitlines():
        if not line.startswith(" word="):
            continue
        scanned += 1
        fields = dict(field.split("=", 1) for field in line.strip().split(",") if "=" in field)
        if fields.get("flags"):
            flagged += 1
            continue
        surface = fields.get("word", "")
        # Reject capitalized proper nouns, URLs, numbers, phrases and punctuation.
        if len(surface) > 32 or not WORD.fullmatch(surface):
            continue
        try:
            frequency = int(fields.get("f", "0"))
        except ValueError:
            continue
        if frequency < min_frequency:
            continue
        words[surface] = max(frequency, words.get(surface, 0))
    ranked = sorted(words.items(), key=lambda item: (-item[1], item[0]))[:max_words]
    return dict(ranked), {"scannedWordCount": scanned, "excludedFlaggedWordCount": flagged}


def write_atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    temporary.replace(path)


def fetch_gitiles(url: str) -> bytes:
    with urllib.request.urlopen(url + "?format=TEXT", timeout=60) as response:
        return base64.b64decode(response.read())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Local gzip or Gitiles base64 snapshot")
    parser.add_argument("--notice-file", type=Path, help="Local notice or Gitiles base64 notice")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "app/src/main/assets/english")
    parser.add_argument("--max-words", type=int, default=50_000)
    parser.add_argument("--min-frequency", type=int, default=60)
    args = parser.parse_args()
    if args.max_words <= 0 or args.min_frequency <= 0:
        parser.error("limits must be positive")
    source = args.input.read_bytes() if args.input else fetch_gitiles(SOURCE_URL)
    if not source.startswith(b"\x1f\x8b"):
        source = base64.b64decode(source, validate=True)
    notice = args.notice_file.read_bytes() if args.notice_file else fetch_gitiles(NOTICE_URL)
    if b"Apache License" not in notice:
        notice = base64.b64decode(notice, validate=True)
    if b"Apache License" not in notice or b"Lexiteria" not in notice:
        raise SystemExit("Expected complete AOSP/Lexiteria notice")
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise SystemExit("Source does not match the pinned AOSP gzip SHA-256")
    if hashlib.sha256(notice).hexdigest() != NOTICE_SHA256:
        raise SystemExit("Notice does not match the pinned AOSP SHA-256")
    text = gzip.decompress(source).decode("utf-8")
    words, stats = extract_words(text, args.min_frequency, args.max_words)
    if not words:
        raise SystemExit("Refusing an empty lexicon")
    header = [
        "# SGH Voice English offline completions; adapted from AOSP LatinIME",
        f"# source={SOURCE_URL}",
        "# licence=Apache-2.0; see AOSP_NOTICE.txt and ATTRIBUTION.txt",
        "# format=word<TAB>frequency; original frequencies are ranking weights",
    ]
    data = ("\n".join(header + [f"{word}\t{words[word]}" for word in sorted(words)]) + "\n").encode()
    source_hash = hashlib.sha256(source).hexdigest()
    snapshot = {
        "formatVersion": 1,
        "sourceProjectUrl": SOURCE_ROOT,
        "sourceUrl": SOURCE_URL,
        "sourceCommit": SOURCE_COMMIT,
        "sourceSha256": source_hash,
        "sourceBytes": len(source),
        "sourceDictionaryHeader": text.splitlines()[0],
        "generatedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataLicence": "Apache-2.0",
        "licenceUrl": NOTICE_URL,
        "licenceSha256": hashlib.sha256(notice).hexdigest(),
        "lexiconFile": "aosp_english.tsv",
        "lexiconBytes": len(data),
        "lexiconSha256": hashlib.sha256(data).hexdigest(),
        "wordCount": len(words),
        "maxWords": args.max_words,
        "minFrequency": args.min_frequency,
        "filters": "Unflagged lowercase ASCII words and contractions; 2-32 characters; no proper-name expansion",
        "updateProcedure": "Review a new official AOSP commit, update SOURCE_COMMIT, regenerate and verify tests before shipping with the APK.",
        **stats,
    }
    attribution = f"""SGH Voice English Lexicon Attribution

Derived from the Android Open Source Project LatinIME English dictionary.
Copyright (c) 2008, The Android Open Source Project.
Includes Dictionaries © Lexiteria LLC. Used by permission.

Source: {SOURCE_URL}
Pinned commit: {SOURCE_COMMIT}
Source gzip SHA-256: {source_hash}
Licence: Apache License 2.0. The complete upstream notice is AOSP_NOTICE.txt.
Upstream licence declaration: {SOURCE_ROOT}/+/{SOURCE_COMMIT}/Android.bp

SGH Voice adaptation: filtered flagged/non-word/uppercase entries, retained
{len(words)} common words by upstream frequency, and changed the format to a
sorted UTF-8 TSV. This is prefix completion only, not an autocorrect engine.
The app's separately curated everyday seed words have higher priority.
No dictionary queries, typed input or learning data are sent to the source.
No endorsement by AOSP, Google or Lexiteria is implied.
"""
    for name, content in {
        "aosp_english.tsv": data,
        "snapshot.json": (json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
        "ATTRIBUTION.txt": attribution.encode(),
        "AOSP_NOTICE.txt": notice,
    }.items():
        write_atomic(args.output_dir / name, content)
    print(f"Wrote {len(words)} English words / {len(data)} bytes")


if __name__ == "__main__":
    main()
