package com.shingihou.sghvoice.learning

/**
 * A deliberately bounded view of the current editor.
 *
 * The IME can construct this from InputConnection.getSurroundingText() on API
 * 31+, or from getTextBeforeCursor/getSelectedText/getTextAfterCursor on older
 * devices. Full document text is neither required nor retained.
 */
data class BoundedTextSnapshot(
    val beforeCursor: String,
    val selectedText: String = "",
    val afterCursor: String,
    val windowStartOffset: Int? = null,
    val startsAtDocumentBoundary: Boolean = false,
    val endsAtDocumentBoundary: Boolean = false
) {
    val fullText: String
        get() = beforeCursor + selectedText + afterCursor
}

enum class CorrectionDiffRejection {
    NO_CHANGE,
    PURE_INSERTION,
    PURE_DELETION,
    TOO_LARGE,
    PUNCTUATION_OR_WHITESPACE_ONLY,
    CONTROL_CHARACTER
}

data class CorrectionReplacement(
    val wrongText: String,
    val correctedText: String,
    val suggestedPromptText: String,
    val unchangedPrefixCodePoints: Int,
    val unchangedSuffixCodePoints: Int
)

sealed interface CorrectionDiffResult {
    data class Accepted(val replacement: CorrectionReplacement) : CorrectionDiffResult
    data class Rejected(val reason: CorrectionDiffRejection) : CorrectionDiffResult
}

/**
 * Extracts one contiguous replacement by removing the longest unchanged Unicode
 * code-point prefix and suffix.
 *
 * A pure insertion/deletion is intentionally not learned: normal continued
 * typing and backspacing are too easy to mistake for a voice correction.
 */
object CorrectionDiff {

    const val DEFAULT_MAX_REPLACEMENT_CODE_POINTS = 64

    fun analyze(
        original: String,
        edited: String,
        maxReplacementCodePoints: Int = DEFAULT_MAX_REPLACEMENT_CODE_POINTS
    ): CorrectionDiffResult {
        require(maxReplacementCodePoints > 0)
        if (original == edited) {
            return CorrectionDiffResult.Rejected(CorrectionDiffRejection.NO_CHANGE)
        }

        val originalCodePoints = original.toCodePointArray()
        val editedCodePoints = edited.toCodePointArray()
        var prefix = 0
        val sharedPrefixLimit = minOf(originalCodePoints.size, editedCodePoints.size)
        while (prefix < sharedPrefixLimit &&
            originalCodePoints[prefix] == editedCodePoints[prefix]
        ) {
            prefix += 1
        }

        var suffix = 0
        val originalRemaining = originalCodePoints.size - prefix
        val editedRemaining = editedCodePoints.size - prefix
        val sharedSuffixLimit = minOf(originalRemaining, editedRemaining)
        while (suffix < sharedSuffixLimit &&
            originalCodePoints[originalCodePoints.lastIndex - suffix] ==
            editedCodePoints[editedCodePoints.lastIndex - suffix]
        ) {
            suffix += 1
        }

        val wrongCodePoints = originalCodePoints.copyOfRange(
            prefix,
            originalCodePoints.size - suffix
        )
        val correctedCodePoints = editedCodePoints.copyOfRange(
            prefix,
            editedCodePoints.size - suffix
        )

        if (wrongCodePoints.isEmpty()) {
            return CorrectionDiffResult.Rejected(CorrectionDiffRejection.PURE_INSERTION)
        }
        if (correctedCodePoints.isEmpty()) {
            return CorrectionDiffResult.Rejected(CorrectionDiffRejection.PURE_DELETION)
        }
        if (wrongCodePoints.size > maxReplacementCodePoints ||
            correctedCodePoints.size > maxReplacementCodePoints
        ) {
            return CorrectionDiffResult.Rejected(CorrectionDiffRejection.TOO_LARGE)
        }
        if (wrongCodePoints.any(::isControlCodePoint) ||
            correctedCodePoints.any(::isControlCodePoint)
        ) {
            return CorrectionDiffResult.Rejected(CorrectionDiffRejection.CONTROL_CHARACTER)
        }
        if (!wrongCodePoints.any(Character::isLetterOrDigit) ||
            !correctedCodePoints.any(Character::isLetterOrDigit)
        ) {
            return CorrectionDiffResult.Rejected(
                CorrectionDiffRejection.PUNCTUATION_OR_WHITESPACE_ONLY
            )
        }

        return CorrectionDiffResult.Accepted(
            CorrectionReplacement(
                wrongText = wrongCodePoints.toUnicodeString(),
                correctedText = correctedCodePoints.toUnicodeString(),
                suggestedPromptText = buildSuggestedPromptText(
                    editedCodePoints = editedCodePoints,
                    changedStart = prefix,
                    changedEnd = editedCodePoints.size - suffix
                ),
                unchangedPrefixCodePoints = prefix,
                unchangedSuffixCodePoints = suffix
            )
        )
    }

    private fun isControlCodePoint(codePoint: Int): Boolean {
        return when (Character.getType(codePoint)) {
            Character.CONTROL.toInt(),
            Character.FORMAT.toInt(),
            Character.LINE_SEPARATOR.toInt(),
            Character.PARAGRAPH_SEPARATOR.toInt() -> true

            else -> false
        }
    }

    /**
     * Keeps replacement rules minimal while returning a more useful prompt
     * term. Han corrections get up to two context characters on either side;
     * alphabetic/kana corrections expand to their surrounding token.
     */
    private fun buildSuggestedPromptText(
        editedCodePoints: IntArray,
        changedStart: Int,
        changedEnd: Int
    ): String {
        val changed = editedCodePoints.copyOfRange(changedStart, changedEnd)
        val hasHan = changed.any {
            Character.UnicodeScript.of(it) == Character.UnicodeScript.HAN
        }
        var start = changedStart
        var end = changedEnd

        if (hasHan) {
            start = (start - 2).coerceAtLeast(0)
            end = (end + 2).coerceAtMost(editedCodePoints.size)
        } else {
            val allowInternalSpaces = changed.any(Character::isWhitespace)
            while (start > 0 &&
                isPromptTokenCodePoint(
                    editedCodePoints[start - 1],
                    allowInternalSpaces
                )
            ) {
                start -= 1
            }
            while (end < editedCodePoints.size &&
                isPromptTokenCodePoint(editedCodePoints[end], allowInternalSpaces)
            ) {
                end += 1
            }
        }

        val maxPromptCodePoints = 32
        if (end - start > maxPromptCodePoints) {
            val desiredLeft = minOf(8, changedStart - start)
            start = changedStart - desiredLeft
            end = minOf(
                editedCodePoints.size,
                start + maxPromptCodePoints
            )
            if (end < changedEnd) {
                end = changedEnd
                start = (end - maxPromptCodePoints).coerceAtLeast(0)
            }
        }
        return editedCodePoints
            .copyOfRange(start, end)
            .toUnicodeString()
            .trim()
    }

    private fun isPromptTokenCodePoint(
        codePoint: Int,
        allowWhitespace: Boolean
    ): Boolean {
        return Character.isLetterOrDigit(codePoint) ||
            codePoint == '\''.code ||
            codePoint == '-'.code ||
            codePoint == '_'.code ||
            (allowWhitespace && Character.isWhitespace(codePoint))
    }
}

enum class VoiceCorrectionTrackingStatus {
    NO_ACTIVE_SESSION,
    SESSION_MISMATCH,
    EXPIRED,
    INSUFFICIENT_CONTEXT,
    NO_CHANGE,
    REJECTED_EDIT,
    CORRECTION_FOUND,
    /** The tracked text changed; learning waits for [VoiceCorrectionTracker.finish]. */
    EDIT_OBSERVED
}

/** One correction extracted from the final, stable edit of a voice turn. */
data class LearnedCorrection(
    val replacement: CorrectionReplacement,
    val highConfidence: Boolean,
    val scope: CorrectionScope
)

data class VoiceCorrectionTrackingResult(
    val status: VoiceCorrectionTrackingStatus,
    val replacement: CorrectionReplacement? = null,
    val highConfidence: Boolean = false,
    val rejection: CorrectionDiffRejection? = null,
    val originalText: String? = null,
    val editedText: String? = null
)

/**
 * Tracks one recently committed voice result for at most 60 seconds.
 *
 * [inspect] only observes: it re-locates the committed range with short anchors and keeps the
 * latest version in memory. Nothing is learned from intermediate editor states (a word deleted
 * and retyped in pieces, a pure insertion, a half-typed replacement). [finish] compares the
 * final stable text with the text as inserted and extracts every short replacement at once.
 *
 * Only spans that came verbatim from speech recognition may be learned: [begin] receives the
 * STT-derived baseline and a replacement of AI-generated wording is ignored.
 */
class VoiceCorrectionTracker(
    private val clockElapsedMillis: () -> Long = {
        System.nanoTime() / 1_000_000L
    },
    private val sessionDurationMillis: Long = DEFAULT_SESSION_DURATION_MILLIS,
    private val anchorCodePoints: Int = DEFAULT_ANCHOR_CODE_POINTS,
    private val maxTrackedTextCodePoints: Int = DEFAULT_MAX_TRACKED_TEXT_CODE_POINTS,
    private val maxWindowCodePoints: Int = DEFAULT_MAX_WINDOW_CODE_POINTS,
    private val maxReplacementCodePoints: Int =
        CorrectionDiff.DEFAULT_MAX_REPLACEMENT_CODE_POINTS
) {

    companion object {
        const val DEFAULT_SESSION_DURATION_MILLIS = 60_000L
        const val DEFAULT_ANCHOR_CODE_POINTS = 24
        const val DEFAULT_MAX_TRACKED_TEXT_CODE_POINTS = 2_048
        const val DEFAULT_MAX_WINDOW_CODE_POINTS = 4_400

        /** An edit this close to the deadline may be unfinished; it is not learned. */
        const val SETTLE_MILLIS = 2_000L
        const val MAX_CORRECTIONS_PER_TURN = 8
    }

    private data class Session(
        val sessionId: Long,
        val originalText: String,
        val latestText: String,
        val beforeAnchor: String,
        val afterAnchor: String,
        val targetStartedAtWindowBoundary: Boolean,
        val targetEndedAtWindowBoundary: Boolean,
        val targetStartedAtDocumentBoundary: Boolean,
        val targetEndedAtDocumentBoundary: Boolean,
        val initialWindowStartOffset: Int?,
        val startedAtMillis: Long,
        val lastChangeAtMillis: Long,
        val strongAnchors: Boolean,
        /** Per code point of [originalText]: true when it came verbatim from STT. */
        val sttVerbatim: BooleanArray,
        val discarded: Boolean = false
    )

    private var session: Session? = null

    init {
        require(sessionDurationMillis > 0)
        require(anchorCodePoints > 0)
        require(maxTrackedTextCodePoints > 0)
        require(maxWindowCodePoints > 0)
        require(maxReplacementCodePoints > 0)
    }

    /**
     * Starts tracking from a snapshot taken after commitText(..., 1), where the
     * cursor is expected to be directly after [committedText].
     *
     * @param sttText the text the user would have seen without AI cleanup. Null means the
     * committed text itself came from STT. Spans that differ from it are never learned.
     */
    @Synchronized
    fun begin(
        sessionId: Long,
        committedText: String,
        afterCommitSnapshot: BoundedTextSnapshot,
        learningAllowed: Boolean = true,
        sttText: String? = null
    ): Boolean {
        session = null
        if (!learningAllowed || committedText.isBlank()) return false
        if (afterCommitSnapshot.selectedText.isNotEmpty()) return false
        if (!afterCommitSnapshot.beforeCursor.endsWith(committedText)) return false
        if (committedText.codePointLength() > maxTrackedTextCodePoints) return false
        if (afterCommitSnapshot.fullText.codePointLength() > maxWindowCodePoints) return false

        val targetStart = afterCommitSnapshot.beforeCursor.length - committedText.length
        val targetEnd = afterCommitSnapshot.beforeCursor.length
        val fullText = afterCommitSnapshot.fullText
        val beforeText = fullText.substring(0, targetStart)
        val afterText = fullText.substring(targetEnd)
        val started = clockElapsedMillis()

        session = Session(
            sessionId = sessionId,
            originalText = committedText,
            latestText = committedText,
            beforeAnchor = beforeText.takeLastCodePoints(anchorCodePoints),
            afterAnchor = afterText.takeFirstCodePoints(anchorCodePoints),
            targetStartedAtWindowBoundary = targetStart == 0,
            targetEndedAtWindowBoundary = targetEnd == fullText.length,
            targetStartedAtDocumentBoundary =
                targetStart == 0 && afterCommitSnapshot.startsAtDocumentBoundary,
            targetEndedAtDocumentBoundary =
                targetEnd == fullText.length && afterCommitSnapshot.endsAtDocumentBoundary,
            initialWindowStartOffset = afterCommitSnapshot.windowStartOffset,
            startedAtMillis = started,
            lastChangeAtMillis = started,
            strongAnchors = false,
            sttVerbatim = if (sttText == null || sttText == committedText) {
                BooleanArray(committedText.codePointLength()) { true }
            } else {
                EditHunks.verbatimMask(committedText, sttText)
                    ?: BooleanArray(committedText.codePointLength())
            }
        )
        return true
    }

    /** Observes the editor. Never learns; see [finish]. */
    @Synchronized
    fun inspect(
        sessionId: Long,
        currentSnapshot: BoundedTextSnapshot
    ): VoiceCorrectionTrackingResult {
        val active = session ?: return result(VoiceCorrectionTrackingStatus.NO_ACTIVE_SESSION)
        if (active.sessionId != sessionId) {
            return result(VoiceCorrectionTrackingStatus.SESSION_MISMATCH)
        }

        val now = clockElapsedMillis()
        val elapsed = now - active.startedAtMillis
        if (elapsed < 0L || elapsed > sessionDurationMillis) {
            // Kept (without new observations) only until finish()/cancel() at the deadline.
            return result(VoiceCorrectionTrackingStatus.EXPIRED)
        }
        if (active.discarded) return result(VoiceCorrectionTrackingStatus.REJECTED_EDIT)
        if (currentSnapshot.fullText.codePointLength() > maxWindowCodePoints) {
            return result(VoiceCorrectionTrackingStatus.INSUFFICIENT_CONTEXT)
        }

        val located = locateTrackedText(active, currentSnapshot)
            ?: return result(VoiceCorrectionTrackingStatus.INSUFFICIENT_CONTEXT)
        val (editedText, strongAnchors) = located
        if (editedText == active.latestText) {
            return result(VoiceCorrectionTrackingStatus.NO_CHANGE)
        }
        if (editedText.isBlank() || editedText.codePointLength() > maxTrackedTextCodePoints) {
            // The whole voice result was removed (or replaced by something much longer):
            // whatever is typed next is new writing, not a correction of this turn.
            session = active.copy(discarded = true)
            return VoiceCorrectionTrackingResult(
                status = VoiceCorrectionTrackingStatus.REJECTED_EDIT,
                rejection = if (editedText.isBlank()) CorrectionDiffRejection.PURE_DELETION
                    else CorrectionDiffRejection.TOO_LARGE
            )
        }
        session = active.copy(
            latestText = editedText,
            lastChangeAtMillis = now,
            strongAnchors = strongAnchors
        )
        return VoiceCorrectionTrackingResult(
            status = VoiceCorrectionTrackingStatus.EDIT_OBSERVED,
            highConfidence = strongAnchors,
            originalText = active.latestText,
            editedText = editedText
        )
    }

    /**
     * Ends the turn and returns the corrections between the inserted text and its final
     * version. Nothing is returned when the result was cleared, when the final edit may be
     * unfinished at the deadline, or when the change looks like a rewrite rather than fixes.
     *
     * @param requireSettledMillis when > 0, the last observed change must be at least this old.
     */
    @Synchronized
    fun finish(sessionId: Long? = null, requireSettledMillis: Long = 0L): List<LearnedCorrection> {
        val active = session ?: return emptyList()
        session = null
        if (sessionId != null && sessionId != active.sessionId) return emptyList()
        if (active.discarded || active.latestText == active.originalText) return emptyList()
        val now = clockElapsedMillis()
        val deadline = active.startedAtMillis + sessionDurationMillis
        if (now < active.startedAtMillis) return emptyList()
        // Never keep a turn's text beyond its retention window plus a short grace period.
        if (now > deadline + SETTLE_MILLIS * 3) return emptyList()
        if (now > deadline && active.lastChangeAtMillis > deadline - SETTLE_MILLIS) return emptyList()
        if (requireSettledMillis > 0 && now - active.lastChangeAtMillis < requireSettledMillis) {
            return emptyList()
        }
        return extract(active)
    }

    @Synchronized
    fun cancel() {
        session = null
    }

    @Synchronized
    fun isTracking(sessionId: Long? = null): Boolean {
        val active = session ?: return false
        val elapsed = clockElapsedMillis() - active.startedAtMillis
        if (elapsed < 0L || elapsed > sessionDurationMillis) return false
        return sessionId == null || sessionId == active.sessionId
    }

    private fun extract(active: Session): List<LearnedCorrection> {
        val original = active.originalText
        val hunks = EditHunks.hunks(original, active.latestText) ?: return emptyList()
        val replacements = hunks.filter { it.wrong.isNotEmpty() && it.corrected.isNotEmpty() }
        if (replacements.isEmpty() || replacements.size > MAX_CORRECTIONS_PER_TURN) return emptyList()
        val originalLength = original.codePointLength()
        // Latin fixes count their edit distance (Orbyt -> Orbit = 1); other spans count their length.
        val changed = replacements.sumOf(EditHunks::changeCost)
        // Replacing most of the utterance is rewriting, not fixing misrecognized words.
        if (originalLength >= 8 && changed * 10 > originalLength * 6) return emptyList()

        val japaneseContext = original.codePoints().anyMatch(::isKana)
        val learned = mutableListOf<LearnedCorrection>()
        val seen = mutableSetOf<Pair<String, String>>()
        for (hunk in replacements) {
            if (!isLearnableHunk(hunk)) continue
            // Spec: only text that came verbatim from speech recognition can be a mishearing.
            val fromStt = (hunk.start until hunk.end).all { index ->
                active.sttVerbatim.getOrElse(index) { false } ||
                    !Character.isLetterOrDigit(original.codePointAtIndex(index))
            }
            if (!fromStt) continue
            val prepared = VoiceCorrectionLearning.prepare(
                original,
                CorrectionReplacement(
                    wrongText = hunk.wrong,
                    correctedText = hunk.corrected,
                    suggestedPromptText = hunk.corrected,
                    unchangedPrefixCodePoints = hunk.start,
                    unchangedSuffixCodePoints = originalLength - hunk.end
                )
            ) ?: continue
            if (!seen.add(prepared.wrongText to prepared.correctedText)) continue
            val latin = !prepared.wrongText.codePoints().anyMatch(::isCjk) &&
                !prepared.correctedText.codePoints().anyMatch(::isCjk)
            learned += LearnedCorrection(
                replacement = prepared,
                highConfidence = active.strongAnchors,
                scope = when {
                    latin -> CorrectionScope.LATIN
                    japaneseContext -> CorrectionScope.JAPANESE
                    else -> CorrectionScope.CHINESE
                }
            )
        }
        return learned
    }

    private fun isLearnableHunk(hunk: EditHunk): Boolean {
        val wrong = hunk.wrong.codePointLength()
        val corrected = hunk.corrected.codePointLength()
        if (wrong > maxReplacementCodePoints || corrected > maxReplacementCodePoints) return false
        if (!hunk.wrong.any(Char::isLetterOrDigit) || !hunk.corrected.any(Char::isLetterOrDigit)) return false
        if ((hunk.wrong + hunk.corrected).any { Character.getType(it) == Character.CONTROL.toInt() }) return false
        // A long CJK-only replacement is a rewrite of the sentence, not a misheard word.
        val hasLatinOrDigit = (hunk.wrong + hunk.corrected).any { it.code < 128 && it.isLetterOrDigit() }
        return hasLatinOrDigit || maxOf(wrong, corrected) <= MAX_CJK_REPLACEMENT_CODE_POINTS
    }

    /**
     * Returns the current target and whether the boundary evidence is strong.
     */
    private fun locateTrackedText(
        active: Session,
        snapshot: BoundedTextSnapshot
    ): Pair<String, Boolean>? {
        val fullText = snapshot.fullText

        val targetStart = if (active.beforeAnchor.isNotEmpty()) {
            val anchorStart = fullText.uniqueIndexOf(active.beforeAnchor) ?: return null
            anchorStart + active.beforeAnchor.length
        } else {
            if (!active.targetStartedAtWindowBoundary) return null
            if (active.initialWindowStartOffset != null &&
                snapshot.windowStartOffset != active.initialWindowStartOffset
            ) {
                return null
            }
            0
        }

        val targetEnd = if (active.afterAnchor.isNotEmpty()) {
            fullText.uniqueIndexOf(active.afterAnchor, startIndex = targetStart) ?: return null
        } else {
            if (!active.targetEndedAtWindowBoundary) return null
            fullText.length
        }
        if (targetEnd < targetStart) return null

        val strongBefore = active.beforeAnchor.isNotEmpty() ||
            (active.targetStartedAtDocumentBoundary &&
                snapshot.startsAtDocumentBoundary &&
                (active.initialWindowStartOffset == null ||
                    active.initialWindowStartOffset == snapshot.windowStartOffset))
        val strongAfter = active.afterAnchor.isNotEmpty() ||
            (active.targetEndedAtDocumentBoundary && snapshot.endsAtDocumentBoundary)

        return fullText.substring(targetStart, targetEnd) to (strongBefore && strongAfter)
    }

    private fun result(status: VoiceCorrectionTrackingStatus) =
        VoiceCorrectionTrackingResult(status = status)
}

private const val MAX_CJK_REPLACEMENT_CODE_POINTS = 6

private fun String.codePointAtIndex(index: Int): Int = codePointAt(offsetByCodePoints(0, index))

private fun isKana(codePoint: Int): Boolean = when (Character.UnicodeScript.of(codePoint)) {
    Character.UnicodeScript.HIRAGANA, Character.UnicodeScript.KATAKANA -> true
    else -> codePoint == 0x30FC || codePoint == 0xFF70
}

private fun isCjk(codePoint: Int): Boolean =
    Character.UnicodeScript.of(codePoint) == Character.UnicodeScript.HAN || isKana(codePoint)

private fun String.uniqueIndexOf(needle: String, startIndex: Int = 0): Int? {
    val first = indexOf(needle, startIndex)
    if (first < 0) return null
    val second = indexOf(needle, first + 1)
    return first.takeIf { second < 0 }
}

private fun String.toCodePointArray(): IntArray {
    val result = IntArray(codePointLength())
    var sourceIndex = 0
    var targetIndex = 0
    while (sourceIndex < length) {
        val codePoint = codePointAt(sourceIndex)
        result[targetIndex++] = codePoint
        sourceIndex += Character.charCount(codePoint)
    }
    return result
}

private fun IntArray.toUnicodeString(): String {
    val builder = StringBuilder(size)
    forEach(builder::appendCodePoint)
    return builder.toString()
}

private fun String.codePointLength(): Int = codePointCount(0, length)

private fun String.takeFirstCodePoints(count: Int): String {
    if (isEmpty() || count <= 0) return ""
    val end = offsetByCodePoints(0, minOf(count, codePointLength()))
    return substring(0, end)
}

private fun String.takeLastCodePoints(count: Int): String {
    if (isEmpty() || count <= 0) return ""
    val start = offsetByCodePoints(length, -minOf(count, codePointLength()))
    return substring(start)
}
