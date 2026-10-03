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
    fun `tracker observes an anchored correction and learns it when the turn ends`() {
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

        // Observation only: nothing is learned from an intermediate state.
        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, result.status)
        assertEquals("cloud code", result.originalText)
        assertEquals("Claude Code", result.editedText)
        assertTrue(result.highConfidence)
        assertTrue(tracker.isTracking())

        val learned = tracker.finish(9L).single()
        assertEquals("cloud code", learned.replacement.wrongText)
        assertEquals("Claude Code", learned.replacement.correctedText)
        assertTrue(learned.highConfidence)
        assertEquals(CorrectionScope.LATIN, learned.scope)
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

        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, result.status)
        assertTrue(result.highConfidence)
        val learned = tracker.finish(2L).single()
        assertEquals("新義豐" to "新義豊", learned.replacement.wrongText to learned.replacement.correctedText)
        assertTrue(learned.highConfidence)
    }

    @Test
    fun `normal continued typing is observed but never learned and does not end tracking`() {
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

        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, result.status)
        assertTrue(tracker.isTracking())
        assertTrue(tracker.finish(3L).isEmpty())
    }

    @Test
    fun `backspace followed by a replacement still learns the final correction`() {
        var elapsed = 0L
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { elapsed })
        fun snapshot(text: String) = BoundedTextSnapshot(
            beforeCursor = "前文：$text",
            afterCursor = "：後文",
            windowStartOffset = 0
        )
        tracker.begin(12L, "我使用 Fyrebase 進行部署", snapshot("我使用 Fyrebase 進行部署"))

        // A real phone edit arrives in separate selection callbacks: delete,
        // pause beyond the IME debounce, then type the replacement.
        elapsed = 1_000L
        val deleting = tracker.inspect(12L, snapshot("我使用  進行部署"))
        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, deleting.status)
        assertTrue("An unfinished bounded deletion must not consume the voice turn", tracker.isTracking(12L))

        elapsed = 2_000L
        val corrected = tracker.inspect(12L, snapshot("我使用 Firebase 進行部署"))
        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, corrected.status)
        val learned = tracker.finish(12L).single()
        assertEquals("Fyrebase" to "Firebase", learned.replacement.wrongText to learned.replacement.correctedText)
        assertEquals("Firebase", learned.replacement.suggestedPromptText)
        assertTrue(learned.highConfidence)
    }

    @Test
    fun `pending deletion never extends the original deadline`() {
        var elapsed = 0L
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { elapsed })
        fun snapshot(text: String) = BoundedTextSnapshot(
            beforeCursor = "前：$text", afterCursor = "：後"
        )
        tracker.begin(13L, "我使用 Fyrebase", snapshot("我使用 Fyrebase"))
        elapsed = 59_000L
        assertEquals(
            VoiceCorrectionTrackingStatus.EDIT_OBSERVED,
            tracker.inspect(13L, snapshot("我使用 ")).status
        )
        assertTrue(tracker.isTracking())
        elapsed = 60_001L
        assertEquals(
            VoiceCorrectionTrackingStatus.EXPIRED,
            tracker.inspect(13L, snapshot("我使用 Firebase")).status
        )
        assertFalse(tracker.isTracking())
        assertTrue("The replacement typed after the deadline is never learned", tracker.finish(13L).isEmpty())
    }

    @Test
    fun `clearing the whole result or deleting a large range cancels learning`() {
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { 0L })
        fun snapshot(text: String) = BoundedTextSnapshot(
            beforeCursor = "前：$text", afterCursor = "：後"
        )
        tracker.begin(14L, "這一段不需要了", snapshot("這一段不需要了"))
        val cleared = tracker.inspect(14L, snapshot(""))
        assertEquals(VoiceCorrectionTrackingStatus.REJECTED_EDIT, cleared.status)
        assertEquals(CorrectionDiffRejection.PURE_DELETION, cleared.rejection)
        tracker.inspect(14L, snapshot("另外寫的話"))
        assertTrue(tracker.finish(14L).isEmpty())

        val original = "a".repeat(65) + "保留"
        tracker.begin(15L, original, snapshot(original))
        tracker.inspect(15L, snapshot("保留"))
        assertTrue(tracker.finish(15L).isEmpty())
    }

    @Test
    fun `delete then type in a boundary-limited editor never upgrades confidence`() {
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { 0L })
        tracker.begin(16L, "我使用 Fyrebase", BoundedTextSnapshot("我使用 Fyrebase", afterCursor = ""))
        val result = tracker.inspect(16L, BoundedTextSnapshot("我使用 ", afterCursor = ""))
        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, result.status)
        assertTrue(tracker.isTracking())
        tracker.inspect(16L, BoundedTextSnapshot("我使用 Firebase", afterCursor = ""))
        val learned = tracker.finish(16L).single()
        assertEquals("Firebase", learned.replacement.correctedText)
        assertFalse(learned.highConfidence)
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
