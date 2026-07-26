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
    CORRECTION_FOUND
}

data class VoiceCorrectionTrackingResult(
    val status: VoiceCorrectionTrackingStatus,
    val replacement: CorrectionReplacement? = null,
    val highConfidence: Boolean = false,
    val rejection: CorrectionDiffRejection? = null
)

/**
 * Tracks one recently committed voice result for at most 60 seconds.
 *
 * It identifies the committed range again using short anchors immediately
 * before and after the result. A correction is high-confidence only when both
 * sides are anchored, or when a missing anchor is a verified window boundary.
 * The tracker consumes the session after the first accepted or rejected edit,
 * because Phase 1 intentionally learns at most one replacement per voice turn.
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
        const val DEFAULT_MAX_TRACKED_TEXT_CODE_POINTS = 512
        const val DEFAULT_MAX_WINDOW_CODE_POINTS = 1_200
    }

    private data class Session(
        val sessionId: Long,
        val committedText: String,
        val beforeAnchor: String,
        val afterAnchor: String,
        val targetStartedAtWindowBoundary: Boolean,
        val targetEndedAtWindowBoundary: Boolean,
        val targetStartedAtDocumentBoundary: Boolean,
        val targetEndedAtDocumentBoundary: Boolean,
        val initialWindowStartOffset: Int?,
        val startedAtMillis: Long
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
     */
    @Synchronized
    fun begin(
        sessionId: Long,
        committedText: String,
        afterCommitSnapshot: BoundedTextSnapshot,
        learningAllowed: Boolean = true
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

        session = Session(
            sessionId = sessionId,
            committedText = committedText,
            beforeAnchor = beforeText.takeLastCodePoints(anchorCodePoints),
            afterAnchor = afterText.takeFirstCodePoints(anchorCodePoints),
            targetStartedAtWindowBoundary = targetStart == 0,
            targetEndedAtWindowBoundary = targetEnd == fullText.length,
            targetStartedAtDocumentBoundary =
                targetStart == 0 && afterCommitSnapshot.startsAtDocumentBoundary,
            targetEndedAtDocumentBoundary =
                targetEnd == fullText.length && afterCommitSnapshot.endsAtDocumentBoundary,
            initialWindowStartOffset = afterCommitSnapshot.windowStartOffset,
            startedAtMillis = clockElapsedMillis()
        )
        return true
    }

    @Synchronized
    fun inspect(
        sessionId: Long,
        currentSnapshot: BoundedTextSnapshot
    ): VoiceCorrectionTrackingResult {
        val active = session ?: return result(VoiceCorrectionTrackingStatus.NO_ACTIVE_SESSION)
        if (active.sessionId != sessionId) {
            return result(VoiceCorrectionTrackingStatus.SESSION_MISMATCH)
        }

        val elapsed = clockElapsedMillis() - active.startedAtMillis
        if (elapsed < 0L || elapsed > sessionDurationMillis) {
            session = null
            return result(VoiceCorrectionTrackingStatus.EXPIRED)
        }
        if (currentSnapshot.fullText.codePointLength() > maxWindowCodePoints) {
            return result(VoiceCorrectionTrackingStatus.INSUFFICIENT_CONTEXT)
        }

        val located = locateTrackedText(active, currentSnapshot)
            ?: return result(VoiceCorrectionTrackingStatus.INSUFFICIENT_CONTEXT)
        val (editedText, strongAnchors) = located
        if (editedText == active.committedText) {
            return result(VoiceCorrectionTrackingStatus.NO_CHANGE)
        }

        return when (
            val diff = CorrectionDiff.analyze(
                original = active.committedText,
                edited = editedText,
                maxReplacementCodePoints = maxReplacementCodePoints
            )
        ) {
            is CorrectionDiffResult.Accepted -> {
                session = null
                VoiceCorrectionTrackingResult(
                    status = VoiceCorrectionTrackingStatus.CORRECTION_FOUND,
                    replacement = diff.replacement,
                    highConfidence = strongAnchors
                )
            }

            is CorrectionDiffResult.Rejected -> {
                session = null
                VoiceCorrectionTrackingResult(
                    status = VoiceCorrectionTrackingStatus.REJECTED_EDIT,
                    rejection = diff.reason
                )
            }
        }
    }

    @Synchronized
    fun cancel() {
        session = null
    }

    @Synchronized
    fun isTracking(sessionId: Long? = null): Boolean {
        val active = session ?: return false
        val elapsed = clockElapsedMillis() - active.startedAtMillis
        if (elapsed < 0L || elapsed > sessionDurationMillis) {
            session = null
            return false
        }
        return sessionId == null || sessionId == active.sessionId
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
