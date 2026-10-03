"""Conservative, offline support for dictation cleanup and its validators.

Semantic edits (including discourse markers such as 然後, like and あの) belong
to the LLM. These helpers never infer missing words or sentence boundaries.
"""
import re


# Ambiguous words intentionally absent: 然後/就是/對/like/あの can carry meaning.
_HESITATIONS = frozenset({"呃", "um", "uh", "えーと", "えっと"})
_BOUNDARY = r"[\s，、。！？；：,.!?;:…⋯]"
_ELLIPSIS = re.compile(r"\.{3,}|…+|⋯+")


def _mask_literals(text):
    """Hide quoted/code literals from cleanup, including unmatched open quotes.

    Sentinels are not word characters or cleanup boundaries. This also prevents
    punctuation repair outside a literal from modifying its exact contents.
    """
    pairs = {"「": "」", "『": "』", "“": "”", "‘": "’", '"': '"', "'": "'", "`": "`"}
    prefix = "\ue000"
    while prefix in text:
        prefix += "\ue000"
    masked = []
    literals = []
    start = 0
    index = 0
    while index < len(text):
        opener = text[index]
        if opener not in pairs or (opener == "'" and index and text[index - 1].isascii() and text[index - 1].isalnum()):
            index += 1
            continue
        delimiter = opener
        if opener == "`":
            while index + len(delimiter) < len(text) and text[index + len(delimiter)] == "`":
                delimiter += "`"
        closer = delimiter if opener == "`" else pairs[opener]
        end = index + len(delimiter)
        while end < len(text):
            if text[end] == "\\":
                end += 2
                continue
            if text.startswith(closer, end):
                # Apostrophes within contractions are not closing quote marks.
                if opener == "'" and end and end + 1 < len(text) and all(
                    char.isascii() and char.isalnum() for char in (text[end - 1], text[end + 1])
                ):
                    end += 1
                    continue
                end += len(closer)
                break
            end += 1
        end = min(end, len(text))
        masked.append(text[start:index])
        token = prefix + chr(0xE100 + len(literals)) + "\ue001"
        masked.append(token)
        literals.append((token, text[index:end]))
        start = index = end
    masked.append(text[start:])
    return "".join(masked), literals


def _restore_literals(text, literals):
    for token, literal in literals:
        text = text.replace(token, literal)
    return text


def remove_hesitations(text, filler_words):
    text, literals = _mask_literals(text)
    configured = {
        word.casefold()
        for words in (filler_words or {}).values()
        for word in (words or [])
        if isinstance(word, str) and word
    }
    lines = []
    for original_line in text.split("\n"):
        line = original_line
        for filler in sorted(configured & _HESITATIONS, key=len, reverse=True):
            # Keep standalone utterances and quoted words. A hesitation must be
            # a separate token with substantive speech following on this line.
            # Uppercase UM/UH can be identifiers; do not erase them as speech.
            token = f"(?:{filler}|{filler.capitalize()})" if filler in {"um", "uh"} else re.escape(filler)
            pattern = rf"(^|{_BOUNDARY}){token}(?={_BOUNDARY})(?=[^\n]*[^\W\d_]{{2,}})"
            def remove(match):
                # ASCII 'um' is also a micrometre unit after a numeric value.
                if filler == "um" and re.search(r"\d\s*$", line[:match.start()]):
                    return match.group(0)
                return match.group(1)
            line = re.sub(pattern, remove, line)
        if line == original_line:
            lines.append(line)
            continue
        # Only repair punctuation where a deletion actually occurred.
        line = re.sub(r"[\t ]+", " ", line).strip()
        line = re.sub(r"^[，、,;；:： ]+", "", line)
        line = re.sub(
            r"([，、,])[ \t]*[，、,]+[ \t]*",
            lambda match: match.group(1) + (" " if match.group(1) == "," and " " in match.group(0) else ""),
            line,
        )
        line = re.sub(r"[，、,]+(?=[。！？.!?])", "", line)
        lines.append(line)
    return _restore_literals("\n".join(lines), literals)


def stutter_reference(text):
    """Only normalize unmistakable pronoun restarts for content comparison.

    Never deduplicate arbitrary words: 'very very', 'no no', and 日日 carry
    emphasis or lexical meaning. Delivery still uses the validated LLM output.
    """
    text, literals = _mask_literals(text)
    for pronoun in ("I", "[Ww]e", "[Yy]ou"):
        text = re.sub(rf"\b({pronoun})(?:[ \t,-]+{pronoun})+(?=[ \t]+[A-Za-z])", r"\1", text)
    text = re.sub(r"(^|[\s，。！？,.!?])([我你])(?:[ \t，,]*\2)+", r"\1\2", text)
    # Collapse only adjacent repeated connectors, keeping one chronological link.
    text = re.sub(r"然後(?:[ \t，,]*然後)+", "然後", text)
    return _restore_literals(text, literals)


def hesitation_reference(text, filler_words):
    """Reference for validating an LLM edit, never delivered as local output.

    Japanese ASR often joins an unambiguous hesitation to the following word.
    Allow the model to remove that prefix, without allowing global deletion of
    meaningful あの, その, like, 然後 or substrings inside names.
    """
    text, literals = _mask_literals(text)
    # A leading chain of hesitation sounds is clearly a false start. Do not
    # remove an isolated affirmative 嗯 or expressive 啊, or an ordinary 然後.
    text = re.sub(r"^(?:[嗯啊呃欸][，、 \t]*){2,}(?=[\w])", "", text)
    # The locked model contract includes these hesitations even in persisted
    # configs created before 呃/えっと were added to the default vocabulary.
    comparison_fillers = {**(filler_words or {}), "_contract_core": list(_HESITATIONS)}
    text = remove_hesitations(text, comparison_fillers)
    configured = {word for words in comparison_fillers.values() for word in (words or [])}
    for word in ("えーと", "えっと"):
        if word in configured:
            text = re.sub(rf"(^|[\s，、。！？,.!?]){word}(?=[\u3040-\u30ff\u3400-\u9fff])", r"\1", text)
    return _restore_literals(stutter_reference(text), literals)


def ellipses_preserved(original, output):
    # An existing intentional pause can change typographic form, but cleanup may
    # neither invent omission markers nor erase the speaker's existing pauses.
    def anchors(text):
        result = []
        for match in _ELLIPSIS.finditer(text or ""):
            before = re.sub(r"\W", "", text[:match.start()])
            after = re.sub(r"\W", "", text[match.end():])
            result.append((before[-1:], after[:1]))
        return result
    return anchors(original) == anchors(output)


def ordered_content_preserved(original, output):
    """Punctuation/paragraphing may change; ordered substantive content may not.

    Callers normalize approved dictionary fixes and bounded disfluencies first.
    Unlike overlap or counting negative words, this catches a shifted negation,
    lost name characters, altered uncertainty and a changed dose/unit.
    """
    original, original_literals = _mask_literals(original or "")
    output, output_literals = _mask_literals(output or "")
    if [literal for _, literal in original_literals] != [literal for _, literal in output_literals]:
        return False
    # Retain the private-use literal sentinels so an unchanged quote cannot be
    # moved to a different place among the speaker's other words.
    return re.sub(r"[^\w\ue000-\uf8ff]|_", "", original).casefold() == re.sub(
        r"[^\w\ue000-\uf8ff]|_", "", output
    ).casefold()
