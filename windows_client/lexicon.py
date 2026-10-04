"""Versioned local terminology candidates, never transcript correction.

The small bundled lexicon verifies spelling against named public sources. It is
neither a diagnostic dictionary nor a clinically validated speech benchmark.
Only full, curated kana readings produce candidates; there is no fuzzy matching,
automatic replacement, network access, patient-text persistence, or logging.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

_FILENAME = "psychiatry-ja-v1.json"
_MAX_FILE_BYTES = 1_000_000
_MAX_TEXT_CHARS = 100_000
_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_TERM = re.compile(r"[一-龯々〆ヵヶぁ-ゖァ-ヺーA-Za-z]{2,64}\Z")
_READING = re.compile(r"[ぁ-ゖァ-ヺー]{5,64}\Z")
_CATEGORIES = frozenset({"diagnosis", "symptom", "therapy", "medication_generic"})
_POLARITY_OR_INSTRUCTION = ("なし", "あり", "否定", "疑い", "可能性", "認めず", "ない",
                            "かもしれない", "増量", "減量", "中止", "服用", "投与")
_PARTICLES = ("は", "が", "を", "に", "で", "と", "も", "の")
_ENDINGS = ("はない", "がない", "ではない", "はなし", "なし", "はある", "がある",
            "あり", "です", "でした", "かもしれない", "とはいえない", "らしい", "など")


class LexiconError(ValueError):
    """Content-free validation failure safe to surface in the UI."""


@dataclass(frozen=True)
class Source:
    source_id: str
    title: str
    publisher: str
    url: str
    checked_on: str


@dataclass(frozen=True)
class Term:
    term_id: str
    preferred: str
    category: str
    aliases: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class Suggestion:
    term_id: str
    preferred: str
    matched_alias: str
    category: str
    source_ids: tuple[str, ...]


def _delimiter(character: str) -> bool:
    return character.isspace() or unicodedata.category(character).startswith(("P", "S"))


def _kanji(character: str) -> bool:
    return "一" <= character <= "龯" or character in "々〆"


def _right_edge(text: str, position: int) -> bool:
    return position == len(text) or _delimiter(text[position]) or _kanji(text[position])


def _phrase_boundaries(text: str, start: int, end: int) -> bool:
    # Conservative Japanese boundaries without introducing a tokenizer/model.
    # Adjacent kana words are deliberately missed rather than guessed. A kana
    # reading can follow a particle after kanji, e.g. 記録はとうごう... .
    left = start == 0 or _delimiter(text[start - 1]) or _kanji(text[start - 1])
    if not left and start >= 2 and text[start - 1] in _PARTICLES:
        left = _kanji(text[start - 2]) or _delimiter(text[start - 2])
    if not left:
        return False
    if _right_edge(text, end):
        return True
    for suffix in (*_ENDINGS, *_PARTICLES):
        if text.startswith(suffix, end) and _right_edge(text, end + len(suffix)):
            return True
    return False


@dataclass(frozen=True)
class Lexicon:
    version: str
    locale: str
    sources: tuple[Source, ...]
    terms: tuple[Term, ...]

    def suggestions(self, text: str, *, limit: int = 8) -> tuple[Suggestion, ...]:
        """Return independent word candidates; the input text is never rewritten.

        No candidate asserts that a condition is present, absent, or diagnosed.
        Preserve the original context and all quantities when manually editing.
        Limits, source provenance, and ordering are deterministic and local.
        """
        if not isinstance(text, str):
            raise TypeError("Terminology matching requires text.")
        if len(text) > _MAX_TEXT_CHARS:
            raise LexiconError("Text is too long for the local terminology matcher.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 32:
            raise LexiconError("Candidate limit must be an integer from 0 to 32.")
        if not text or limit == 0:
            return ()
        matches = []
        for term in self.terms:
            first = None
            for alias in term.aliases:
                # This is literal phrase matching: no normalization, edit
                # distance, homophone guessing, or dose/unit interpretation.
                for match in re.finditer(re.escape(alias), text):
                    if _phrase_boundaries(text, match.start(), match.end()):
                        candidate = (match.start(), alias)
                        if first is None or candidate < first:
                            first = candidate
                        break
            if first is not None:
                matches.append((first[0], term.term_id, Suggestion(
                    term.term_id, term.preferred, first[1], term.category, term.source_ids,
                )))
        matches.sort(key=lambda item: (item[0], item[1]))
        return tuple(item[2] for item in matches[:limit])

    def glossary_prompt(self, *, max_chars: int = 800) -> str:
        """Opt-in spelling list only; callers must not inject it by default.

        Speech models may be biased by a vocabulary prompt. This helper does
        not claim improved accuracy and contains no patient text or instructions.
        """
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or not 0 <= max_chars <= 4000:
            raise LexiconError("Glossary size must be an integer from 0 to 4000.")
        result = ""
        for term in self.terms:
            proposed = (result + "、" if result else "") + term.preferred
            if len(proposed) > max_chars:
                break
            result = proposed
        return result


def _bundled_path() -> Path:
    # PyInstaller onedir/onefile: resources/windows is explicitly bundled by
    # the Windows spec. Normal source checkout: resources is beside the package.
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        bundled = Path(bundle_root) / "resources" / "windows" / _FILENAME
        if bundled.is_file():
            return bundled
    return Path(__file__).resolve().parent.parent / "resources" / "windows" / _FILENAME


def _text(value, *, maximum=200) -> str:
    if (not isinstance(value, str) or not value or len(value) > maximum
            or any(unicodedata.category(character).startswith("C") for character in value)):
        raise LexiconError("The local lexicon contains invalid text metadata.")
    return value


def _identifier(value) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise LexiconError("The local lexicon contains an invalid identifier.")
    return value


def load_terms(path: str | Path | None = None) -> Lexicon:
    """Read a versioned local file only; missing/invalid files fail explicitly."""
    try:
        chosen = _bundled_path() if path is None else Path(path)
        # Bounded read even if another process changes the file after stat().
        with chosen.open("rb") as stream:
            raw = stream.read(_MAX_FILE_BYTES + 1)
        if len(raw) > _MAX_FILE_BYTES:
            raise LexiconError("The local lexicon exceeds the permitted size.")
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        if isinstance(error, LexiconError):
            raise
        raise LexiconError("The local terminology file could not be read.") from None
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("locale") != "ja-JP":
        raise LexiconError("The local lexicon schema or locale is unsupported.")
    version = data.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise LexiconError("The local lexicon version is invalid.")
    if data.get("automatic_replacement") is not False or data.get("clinically_validated") is not False:
        raise LexiconError("The local lexicon must remain an unvalidated suggestion-only resource.")
    source_rows, term_rows = data.get("sources"), data.get("terms")
    if not isinstance(source_rows, list) or not 1 <= len(source_rows) <= 100:
        raise LexiconError("The local lexicon source list is invalid.")
    if not isinstance(term_rows, list) or not 1 <= len(term_rows) <= 500:
        raise LexiconError("The local lexicon term list is invalid.")
    sources = []
    source_ids = set()
    for row in source_rows:
        if not isinstance(row, dict):
            raise LexiconError("The local lexicon source entry is invalid.")
        source_id = _identifier(row.get("id"))
        url = _text(row.get("url"), maximum=2000)
        try:
            parsed = urlsplit(url)
            allowed_host = parsed.hostname in {"kokoro.ncnp.go.jp", "www.ncnp.go.jp", "www.mhlw.go.jp", "www.pmda.go.jp"}
        except ValueError:
            allowed_host = False
        if (not allowed_host or parsed.scheme != "https" or parsed.username or parsed.password
                or source_id in source_ids):
            raise LexiconError("The local lexicon requires unique, official HTTPS sources.")
        checked_on = _text(row.get("checked_on"), maximum=10)
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", checked_on):
            raise LexiconError("The local lexicon source check date is invalid.")
        sources.append(Source(source_id, _text(row.get("title")), _text(row.get("publisher")), url, checked_on))
        source_ids.add(source_id)
    terms = []
    term_ids = set()
    all_aliases = set()
    for row in term_rows:
        if not isinstance(row, dict):
            raise LexiconError("The local lexicon term entry is invalid.")
        term_id = _identifier(row.get("id"))
        preferred = _text(row.get("preferred"), maximum=64)
        category = row.get("category")
        aliases, references = row.get("aliases"), row.get("source_ids")
        if (term_id in term_ids or not isinstance(category, str) or category not in _CATEGORIES
                or not _TERM.fullmatch(preferred)
                or any(fragment in preferred for fragment in _POLARITY_OR_INSTRUCTION)):
            raise LexiconError("The local lexicon contains an unsafe or duplicate term.")
        if (not isinstance(aliases, list) or not 1 <= len(aliases) <= 4
                or not all(isinstance(alias, str) and _READING.fullmatch(alias)
                           and alias != preferred and alias not in all_aliases
                           and not any(fragment in alias for fragment in _POLARITY_OR_INSTRUCTION)
                           for alias in aliases)
                or len(set(aliases)) != len(aliases)):
            raise LexiconError("The local lexicon requires unambiguous full kana aliases without clinical qualifiers.")
        if (not isinstance(references, list) or not references
                or not all(isinstance(reference, str) and reference in source_ids for reference in references)):
            raise LexiconError("A local lexicon term is missing verified source references.")
        terms.append(Term(term_id, preferred, category, tuple(aliases), tuple(references)))
        term_ids.add(term_id)
        all_aliases.update(aliases)
    return Lexicon(version, data["locale"], tuple(sources), tuple(terms))


def suggestions(text: str, *, lexicon: Lexicon | None = None, limit: int = 8) -> tuple[Suggestion, ...]:
    """Convenience wrapper; only metadata candidates are returned."""
    return (lexicon if lexicon is not None else load_terms()).suggestions(text, limit=limit)
