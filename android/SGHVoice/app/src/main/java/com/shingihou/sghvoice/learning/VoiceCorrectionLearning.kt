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
            suggestedPromptText = correctedText,
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
