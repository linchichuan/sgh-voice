package com.shingihou.sghvoice.learning

/**
 * Turns a minimal editor diff into a bounded, reusable dictionary term.
 * Only the edge tokens are completed; surrounding sentences are never added.
 */
object VoiceCorrectionLearning {
    fun prepare(
        originalText: String,
        replacement: CorrectionReplacement
    ): CorrectionReplacement? {
        val wrongLength = replacement.wrongText.codePointCount(0, replacement.wrongText.length)
        val correctedLength = replacement.correctedText.codePointCount(0, replacement.correctedText.length)
        if (originalText.isBlank() || wrongLength == 0 || correctedLength == 0) return null

        val original = originalText.codePoints().toArray()
        val start = replacement.unchangedPrefixCodePoints
        val end = start + wrongLength
        if (start !in 0..original.size || end !in 0..original.size || end < start ||
            original.size - end != replacement.unchangedSuffixCodePoints ||
            original.copyOfRange(start, end).toUnicodeString() != replacement.wrongText
        ) return null

        var expandedStart = start
        var expandedEnd = end
        val corrected = replacement.correctedText.codePoints().toArray()
        if (isAlphabeticTokenCodePoint(original[start]) || isAlphabeticTokenCodePoint(corrected.first())) {
            while (expandedStart > 0 && isAlphabeticTokenCodePoint(original[expandedStart - 1])) {
                expandedStart -= 1
            }
        }
        if (isAlphabeticTokenCodePoint(original[end - 1]) || isAlphabeticTokenCodePoint(corrected.last())) {
            while (expandedEnd < original.size && isAlphabeticTokenCodePoint(original[expandedEnd])) {
                expandedEnd += 1
            }
        }

        // A standalone Han/kana replacement is too broad. Retain the existing
        // short-context safeguard without pulling in half of an adjacent English word.
        val completedWrongLength = expandedEnd - expandedStart
        val completedCorrectedLength = correctedLength + start - expandedStart + expandedEnd - end
        val hasCjkChange = (start until end).any { isCjkCodePoint(original[it]) } ||
            corrected.any(::isCjkCodePoint)
        if ((completedWrongLength < 2 || completedCorrectedLength < 2) && hasCjkChange) {
            repeat(2) {
                if (expandedStart > 0 && isCjkCodePoint(original[expandedStart - 1])) expandedStart -= 1
                if (expandedEnd < original.size && isCjkCodePoint(original[expandedEnd])) expandedEnd += 1
            }
        }

        val left = original.copyOfRange(expandedStart, start).toUnicodeString()
        val right = original.copyOfRange(end, expandedEnd).toUnicodeString()
        val wrongText = left + replacement.wrongText + right
        val correctedText = left + replacement.correctedText + right
        val maxLength = CorrectionDiff.DEFAULT_MAX_REPLACEMENT_CODE_POINTS
        if (wrongText.codePointCount(0, wrongText.length) !in 2..maxLength ||
            correctedText.codePointCount(0, correctedText.length) !in 2..maxLength
        ) return null

        return replacement.copy(
            wrongText = wrongText,
            correctedText = correctedText,
            // Spec 6: the hint is the corrected word itself, never its sentence context.
            suggestedPromptText = LearnedTerms.promptTerm(wrongText, correctedText),
            unchangedPrefixCodePoints = expandedStart,
            unchangedSuffixCodePoints = original.size - expandedEnd
        )
    }

    private fun isAlphabeticTokenCodePoint(codePoint: Int): Boolean =
        !isCjkCodePoint(codePoint) && (
            Character.isLetterOrDigit(codePoint) ||
                Character.getType(codePoint) == Character.NON_SPACING_MARK.toInt() ||
                Character.getType(codePoint) == Character.COMBINING_SPACING_MARK.toInt() ||
                codePoint == '\''.code || codePoint == '-'.code || codePoint == '_'.code
            )

    private fun isCjkCodePoint(codePoint: Int): Boolean =
        when (Character.UnicodeScript.of(codePoint)) {
            Character.UnicodeScript.HAN,
            Character.UnicodeScript.HIRAGANA,
            Character.UnicodeScript.KATAKANA -> true
            else -> codePoint == 0x30FC || codePoint == 0xFF70
        }

    private fun IntArray.toUnicodeString(): String = buildString(size) {
        this@toUnicodeString.forEach(::appendCodePoint)
    }
}

/** Shared rules for what a learned correction may contain and what it may send as a hint. */
object LearnedTerms {
    /** New learning is limited to short word fixes; stored (migrated) rules may be up to 64. */
    const val MAX_LEARNED_CODE_POINTS = 24
    private const val MAX_CJK_ONLY_CODE_POINTS = 6
    private const val MAX_LATIN_WORDS = 4

    /** Connectives and function words: swapping them is a style edit, not a misrecognition. */
    private val STYLE_WORDS = setOf(
        "接著", "接着", "然後", "然后", "所以", "但是", "可是", "不過", "因為", "因为", "而且", "還有", "还有",
        "就是", "那個", "那个", "這個", "这个", "首先", "最後", "最后", "另外", "其實", "其实", "如果", "雖然",
        "或者", "還是", "还是", "之後", "之后", "接下來", "再來", "然後再", "並且", "并且", "以及", "和", "跟", "與",
        "そして", "それから", "でも", "しかし", "だから", "ですから", "つまり", "まず", "次に", "最後に", "また",
        "and", "then", "but", "so", "also", "next", "finally", "however", "because", "or", "the", "a", "an"
    )

    /**
     * Why a correction pair must never be learned, or null when it looks like a spelling fix.
     * Facts (numbers, units, dates, signs, currency, negation) reuse the dictation guard rules.
     */
    fun rejectionReason(wrong: String, corrected: String): String? {
        if (!com.shingihou.sghvoice.processing.FactPreservation.correctionPreservesFacts(wrong, corrected)) {
            return "changes a fact"
        }
        if (wrong.trim().lowercase() in STYLE_WORDS && corrected.trim().lowercase() in STYLE_WORDS) {
            return "style word swap"
        }
        val hasLatinOrDigit = (wrong + corrected).any { it.code < 128 && it.isLetterOrDigit() }
        if (!hasLatinOrDigit &&
            maxOf(wrong.codePointCount(0, wrong.length), corrected.codePointCount(0, corrected.length)) >
            MAX_CJK_ONLY_CODE_POINTS
        ) return "long rewrite"
        if (latinWords(wrong) > MAX_LATIN_WORDS || latinWords(corrected) > MAX_LATIN_WORDS) return "long rewrite"
        return null
    }

    /**
     * The STT hint for a rule: the changed part of [corrected], completed to whole Latin
     * words, without sentence context. If a short CJK term differs by one character,
     * retain its bounded whole spelling rather than silently dropping the useful hint.
     */
    fun promptTerm(wrong: String, corrected: String): String {
        val w = wrong.codePoints().toArray()
        val c = corrected.codePoints().toArray()
        var prefix = 0
        while (prefix < w.size && prefix < c.size && w[prefix] == c[prefix]) prefix++
        var suffix = 0
        while (suffix < w.size - prefix && suffix < c.size - prefix &&
            w[w.size - 1 - suffix] == c[c.size - 1 - suffix]
        ) suffix++
        var start = prefix
        var end = c.size - suffix
        if (start >= end) return ""
        while (start > 0 && isLatinPoint(c[start - 1]) && isLatinPoint(c[start])) start--
        while (end < c.size && isLatinPoint(c[end]) && isLatinPoint(c[end - 1])) end++
        val term = buildString { for (index in start until end) appendCodePoint(c[index]) }.trim()
        if (term.isEmpty() || !term.any(Char::isLetterOrDigit)) return ""
        val hasCjk = term.codePoints().anyMatch(::isCjk)
        if (hasCjk && term.codePointCount(0, term.length) < 2) {
            // CJK has no dependable whitespace word boundary. Only retain the already
            // bounded, all-CJK short term; never grow a fragment back into a sentence.
            return if (w.size in 2..MAX_CJK_ONLY_CODE_POINTS && c.size in 2..MAX_CJK_ONLY_CODE_POINTS &&
                w.all(::isCjk) && c.all(::isCjk) && rejectionReason(wrong, corrected) == null
            ) corrected else ""
        }
        return term
    }

    /** Where a rule learned without explicit context may apply. */
    fun scopeOf(wrong: String, corrected: String, language: LearningLanguage? = null): CorrectionScope {
        val text = wrong + corrected
        return when {
            !text.codePoints().anyMatch(::isCjk) -> CorrectionScope.LATIN
            language == LearningLanguage.JAPANESE || text.codePoints().anyMatch(::isKana) -> CorrectionScope.JAPANESE
            else -> CorrectionScope.CHINESE
        }
    }

    /** Context of a text a rule is applied to: kana means Japanese, other CJK means Chinese. */
    fun textScope(text: String): CorrectionScope =
        if (text.codePoints().anyMatch(::isKana)) CorrectionScope.JAPANESE else CorrectionScope.CHINESE

    private fun latinWords(text: String): Int =
        text.split(Regex("[^A-Za-z0-9]+")).count { it.isNotEmpty() }

    private fun isLatinPoint(point: Int): Boolean =
        !isCjk(point) && (Character.isLetterOrDigit(point) || point == '\''.code || point == '-'.code || point == '_'.code)

    private fun isKana(point: Int): Boolean = when (Character.UnicodeScript.of(point)) {
        Character.UnicodeScript.HIRAGANA, Character.UnicodeScript.KATAKANA -> true
        else -> point == 0x30FC || point == 0xFF70
    }

    private fun isCjk(point: Int): Boolean =
        Character.UnicodeScript.of(point) == Character.UnicodeScript.HAN || isKana(point)
}
