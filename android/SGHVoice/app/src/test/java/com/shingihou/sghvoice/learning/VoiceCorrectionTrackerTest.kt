package com.shingihou.sghvoice.learning

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceCorrectionTrackerTest {

    @Test
    fun `diff finds one short unicode replacement`() {
        val result = CorrectionDiff.analyze(
            original = "我叫林紀泉",
            edited = "我叫林紀全"
        ) as CorrectionDiffResult.Accepted

        assertEquals("泉", result.replacement.wrongText)
        assertEquals("全", result.replacement.correctedText)
        assertEquals("林紀全", result.replacement.suggestedPromptText)
        assertEquals(4, result.replacement.unchangedPrefixCodePoints)
        assertEquals(0, result.replacement.unchangedSuffixCodePoints)
    }

    @Test
    fun `diff preserves supplementary unicode around replacement`() {
        val result = CorrectionDiff.analyze(
            original = "🙂cloud code🙂",
            edited = "🙂Claude Code🙂"
        ) as CorrectionDiffResult.Accepted

        assertEquals("cloud c", result.replacement.wrongText)
        assertEquals("Claude C", result.replacement.correctedText)
        assertEquals("Claude Code", result.replacement.suggestedPromptText)
        assertEquals(1, result.replacement.unchangedPrefixCodePoints)
        assertEquals(4, result.replacement.unchangedSuffixCodePoints)
    }

    @Test
    fun `diff rejects insertion deletion punctuation and oversized edits`() {
        assertRejected(
            CorrectionDiffRejection.PURE_INSERTION,
            CorrectionDiff.analyze("hello", "hello!")
        )
        assertRejected(
            CorrectionDiffRejection.PURE_DELETION,
            CorrectionDiff.analyze("hello!", "hello")
        )
        assertRejected(
            CorrectionDiffRejection.PUNCTUATION_OR_WHITESPACE_ONLY,
            CorrectionDiff.analyze("hello!", "hello?")
        )
        assertRejected(
            CorrectionDiffRejection.TOO_LARGE,
            CorrectionDiff.analyze(
                original = "a".repeat(70),
                edited = "b".repeat(70)
            )
        )
    }

    @Test
    fun `tracker finds anchored correction and consumes session`() {
        var elapsed = 1_000L
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { elapsed })
        val started = tracker.begin(
            sessionId = 9L,
            committedText = "cloud code",
            afterCommitSnapshot = BoundedTextSnapshot(
                beforeCursor = "say cloud code",
                afterCursor = " please",
                windowStartOffset = 10
            )
        )
        assertTrue(started)

        elapsed += 500
        val result = tracker.inspect(
            sessionId = 9L,
            currentSnapshot = BoundedTextSnapshot(
                beforeCursor = "say Claude Code",
                afterCursor = " please",
                windowStartOffset = 10
            )
        )

        assertEquals(
            VoiceCorrectionTrackingStatus.CORRECTION_FOUND,
            result.status
        )
        assertEquals("cloud c", result.replacement?.wrongText)
        assertEquals("Claude C", result.replacement?.correctedText)
        assertTrue(result.highConfidence)
        assertFalse(tracker.isTracking())
    }

    @Test
    fun `tracker accepts verified whole-field boundary correction`() {
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { 10L })
        assertTrue(
            tracker.begin(
                sessionId = 2L,
                committedText = "新義豐",
                afterCommitSnapshot = BoundedTextSnapshot(
                    beforeCursor = "新義豐",
                    afterCursor = "",
                    windowStartOffset = 0,
                    startsAtDocumentBoundary = true,
                    endsAtDocumentBoundary = true
                )
            )
        )

        val result = tracker.inspect(
            sessionId = 2L,
            currentSnapshot = BoundedTextSnapshot(
                beforeCursor = "新義豊",
                afterCursor = "",
                windowStartOffset = 0,
                startsAtDocumentBoundary = true,
                endsAtDocumentBoundary = true
            )
        )

        assertEquals(
            VoiceCorrectionTrackingStatus.CORRECTION_FOUND,
            result.status
        )
        assertTrue(result.highConfidence)
    }

    @Test
    fun `normal continued typing is rejected as a pure insertion`() {
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { 10L })
        tracker.begin(
            sessionId = 3L,
            committedText = "hello",
            afterCommitSnapshot = BoundedTextSnapshot(
                beforeCursor = "hello",
                afterCursor = ""
            )
        )

        val result = tracker.inspect(
            sessionId = 3L,
            currentSnapshot = BoundedTextSnapshot(
                beforeCursor = "hello world",
                afterCursor = ""
            )
        )

        assertEquals(
            VoiceCorrectionTrackingStatus.REJECTED_EDIT,
            result.status
        )
        assertEquals(CorrectionDiffRejection.PURE_INSERTION, result.rejection)
    }

    @Test
    fun `tracker expires after sixty seconds`() {
        var elapsed = 0L
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { elapsed })
        tracker.begin(
            sessionId = 4L,
            committedText = "before",
            afterCommitSnapshot = BoundedTextSnapshot(
                beforeCursor = "context before",
                afterCursor = " end"
            )
        )
        elapsed = 60_001L

        assertEquals(
            VoiceCorrectionTrackingStatus.EXPIRED,
            tracker.inspect(
                sessionId = 4L,
                currentSnapshot = BoundedTextSnapshot(
                    beforeCursor = "context after",
                    afterCursor = " end"
                )
            ).status
        )
        assertFalse(tracker.isTracking())
    }

    @Test
    fun `ambiguous repeated anchor does not guess`() {
        val tracker = VoiceCorrectionTracker(
            clockElapsedMillis = { 0L },
            anchorCodePoints = 3
        )
        tracker.begin(
            sessionId = 5L,
            committedText = "wrong",
            afterCommitSnapshot = BoundedTextSnapshot(
                beforeCursor = "abc wrong",
                afterCursor = " xyz"
            )
        )

        val result = tracker.inspect(
            sessionId = 5L,
            currentSnapshot = BoundedTextSnapshot(
                beforeCursor = "abc abc right",
                afterCursor = " xyz"
            )
        )
        assertEquals(
            VoiceCorrectionTrackingStatus.INSUFFICIENT_CONTEXT,
            result.status
        )
        assertTrue(tracker.isTracking(5L))
    }

    private fun assertRejected(
        expected: CorrectionDiffRejection,
        actual: CorrectionDiffResult
    ) {
        actual as CorrectionDiffResult.Rejected
        assertEquals(expected, actual.reason)
    }
}
