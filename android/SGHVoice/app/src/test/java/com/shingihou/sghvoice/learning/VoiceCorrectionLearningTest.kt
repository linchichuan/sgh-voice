package com.shingihou.sghvoice.learning

import android.content.SharedPreferences
import com.shingihou.sghvoice.processing.DictionaryManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock

/** Real diff, learning adapter, repository and dictionary; only storage is synthetic. */
class VoiceCorrectionLearningTest {
    @Test fun `two corrections in one voice paragraph both reach the next dictation`() {
        fun snapshot(text: String) = BoundedTextSnapshot(text, afterCursor = "",
            windowStartOffset = 0, startsAtDocumentBoundary = true, endsAtDocumentBoundary = true)
        val original = "請用Orbyt檢查Kotlun。"
        val first = "請用Orbit檢查Kotlun。"
        val second = "請用Orbit檢查Kotlin。"
        val repository = PersonalizationRepository(CorrectionLearningStorage())
        // The same two fixes in two voice turns make both rules 已生效.
        for (turn in 1L..2L) {
            val tracker = VoiceCorrectionTracker(clockElapsedMillis = { 0L })
            assertTrue(tracker.begin(turn, original, snapshot(original)))
            for ((before, after) in listOf(original to first, first to second)) {
                val found = tracker.inspect(turn, snapshot(after))
                assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, found.status)
                assertEquals(before, found.originalText)
            }
            val learned = tracker.finish(turn)
            assertEquals(listOf("Orbit", "Kotlin"), learned.map { it.replacement.correctedText })
            learned.forEach {
                repository.recordVoiceCorrection(LearningLanguage.MIXED, it.replacement, it.highConfidence, turn, it.scope)
            }
        }
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }
        assertEquals(second, dictionary.applyCorrections(original, includePersonalization = true))
    }

    @Test fun `bounded long voice paragraph can learn a short correction without persisting the paragraph`() {
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { 0L })
        val prefix = "這是一段測試文字。".repeat(80)
        val source = prefix + "Orbyt"
        fun snapshot(text: String) = BoundedTextSnapshot(text, afterCursor = "",
            startsAtDocumentBoundary = true, endsAtDocumentBoundary = true)
        assertTrue(tracker.begin(1L, source, snapshot(source)))
        tracker.inspect(1L, snapshot(prefix + "Orbit"))
        val prepared = tracker.finish(1L).single().replacement
        assertEquals("Orbyt", prepared.wrongText)
        assertEquals("Orbit", prepared.correctedText)
        assertFalse(tracker.begin(2L, "字".repeat(2049), snapshot("字".repeat(2049))))
    }

    @Test fun `repeated toggles do not count as independent confirmation and edits do not extend expiry`() {
        var now = 0L
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { now })
        fun snapshot(text: String) = BoundedTextSnapshot(text, afterCursor = "")
        assertTrue(tracker.begin(1L, "Orbyt", snapshot("Orbyt")))
        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, tracker.inspect(1L, snapshot("Orbit")).status)
        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, tracker.inspect(1L, snapshot("Orbyt")).status)
        assertEquals(VoiceCorrectionTrackingStatus.EDIT_OBSERVED, tracker.inspect(1L, snapshot("Orbit")).status)
        now = 60_001L
        assertEquals(VoiceCorrectionTrackingStatus.EXPIRED, tracker.inspect(1L, snapshot("OrbitX")).status)
        // Only the final text counts, once per voice turn.
        val learned = tracker.finish(1L)
        assertEquals(listOf("Orbyt" to "Orbit"), learned.map { it.replacement.wrongText to it.replacement.correctedText })
        val repository = PersonalizationRepository(CorrectionLearningStorage())
        repeat(3) {
            assertEquals(CorrectionRecordStatus.EVIDENCE_RECORDED,
                repository.recordVoiceCorrection(LearningLanguage.MIXED, learned.single().replacement, true, 1L).status)
        }
    }

    @Test fun `same letter correction in two different terms is not deduplicated`() {
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { 0L })
        fun snapshot(text: String) = BoundedTextSnapshot(text, afterCursor = "")
        // Separated by Han so the two words are two fixes (adjacent words form one phrase rule).
        tracker.begin(1L, "Orbyt和Kyt", snapshot("Orbyt和Kyt"))
        tracker.inspect(1L, snapshot("Orbit和Kyt"))
        tracker.inspect(1L, snapshot("Orbit和Kit"))
        assertEquals(listOf("Orbyt" to "Orbit", "Kyt" to "Kit"),
            tracker.finish(1L).map { it.replacement.wrongText to it.replacement.correctedText })
    }

    @Test
    fun `single letter correction beside Chinese learns only the complete English term`() {
        val original = "使用Orbyt進行部署"
        val diff = CorrectionDiff.analyze(original, "使用Orbit進行部署")
            as CorrectionDiffResult.Accepted
        val replacement = requireNotNull(VoiceCorrectionLearning.prepare(original, diff.replacement))
        val repository = PersonalizationRepository(CorrectionLearningStorage())
        repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, highConfidence = true, turnId = 1L)
        repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, highConfidence = true, turnId = 2L)
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }

        assertEquals(listOf("Orbit"), repository.getPromptWords())
        assertEquals("再次Orbit測試", dictionary.applyCorrections("再次Orbyt測試", includePersonalization = true))
        assertEquals("再次Orbyte測試", dictionary.applyCorrections("再次Orbyte測試", includePersonalization = true))
    }

    @Test
    fun `manual correction teaches complete terms for hints and the next dictation`() {
        val original = "Please open orbit code today."
        val diff = CorrectionDiff.analyze(original, "Please open Orbit Code today.")
            as CorrectionDiffResult.Accepted
        val replacement = requireNotNull(VoiceCorrectionLearning.prepare(original, diff.replacement))
        val repository = PersonalizationRepository(CorrectionLearningStorage())
        val pending = repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, true, turnId = 1L)
        assertEquals(CorrectionRecordStatus.EVIDENCE_RECORDED, pending.status)
        val recorded = repository.recordVoiceCorrection(
            LearningLanguage.MIXED,
            replacement,
            highConfidence = true,
            turnId = 2L
        )
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }

        assertEquals(CorrectionRecordStatus.ACTIVATED, recorded.status)
        assertEquals(listOf("Orbit Code"), repository.getPromptWords())
        assertTrue(dictionary.buildWhisperPrompt(includePersonalization = true).contains("Orbit Code"))
        assertTrue(dictionary.buildLlmVocabularyHint("使用orbit code", includePersonalization = true).contains("\"Orbit Code\""))
        assertEquals("使用Orbit Code開發。", dictionary.applyCorrections("使用orbit code開發。", includePersonalization = true))
        assertEquals("orbit codec", dictionary.applyCorrections("orbit codec", includePersonalization = true))
    }

    @Test
    fun `minimal cloud code diff is completed without absorbing surrounding emoji`() {
        val original = "🙂cloud code🙂"
        val diff = CorrectionDiff.analyze(original, "🙂Claude Code🙂") as CorrectionDiffResult.Accepted
        assertEquals("cloud c", diff.replacement.wrongText)

        val replacement = requireNotNull(VoiceCorrectionLearning.prepare(original, diff.replacement))

        assertEquals("cloud code", replacement.wrongText)
        assertEquals("Claude Code", replacement.correctedText)
        assertEquals("Claude Code", replacement.suggestedPromptText)
        assertEquals(1, replacement.unchangedPrefixCodePoints)
        assertEquals(1, replacement.unchangedSuffixCodePoints)
    }

    @Test
    fun `single Han correction remains a short phrase and preserves supplementary Unicode`() {
        val original = "我代表新義豐公司出席"
        val diff = CorrectionDiff.analyze(original, "我代表新義豊公司出席") as CorrectionDiffResult.Accepted
        val replacement = requireNotNull(VoiceCorrectionLearning.prepare(original, diff.replacement))

        assertEquals("新義豐公司", replacement.wrongText)
        // A bounded complete term is useful even when its changed fragment is one Han.
        // It remains STT-only, not permission for literal or LLM replacement.
        assertEquals("新義豊公司", replacement.suggestedPromptText)

        val unicodeOriginal = "🙂𠮷野泉🙂"
        val unicodeDiff = CorrectionDiff.analyze(unicodeOriginal, "🙂𠮷野全🙂") as CorrectionDiffResult.Accepted
        val unicodeReplacement = requireNotNull(VoiceCorrectionLearning.prepare(unicodeOriginal, unicodeDiff.replacement))
        assertEquals("𠮷野泉", unicodeReplacement.wrongText)
        assertEquals("𠮷野全", unicodeReplacement.suggestedPromptText)
        assertEquals(1, unicodeReplacement.unchangedPrefixCodePoints)
        assertEquals(1, unicodeReplacement.unchangedSuffixCodePoints)

        val loneHan = CorrectionDiff.analyze("泉", "全") as CorrectionDiffResult.Accepted
        assertNull(VoiceCorrectionLearning.prepare("泉", loneHan.replacement))
    }

    @Test
    fun `complete 24 character word reaches hints but longer or oversized words are never learned`() {
        val longDiff = CorrectionDiff.analyze("a".repeat(64), "A" + "a".repeat(63)) as CorrectionDiffResult.Accepted
        val longReplacement = requireNotNull(VoiceCorrectionLearning.prepare("a".repeat(64), longDiff.replacement))
        val repository = PersonalizationRepository(CorrectionLearningStorage())
        assertEquals("Learning is limited to short word fixes", CorrectionRecordStatus.REJECTED,
            repository.recordVoiceCorrection(LearningLanguage.MIXED, longReplacement, true, turnId = 1L).status)

        val original = "a".repeat(24)
        val edited = "A" + "a".repeat(23)
        val diff = CorrectionDiff.analyze(original, edited) as CorrectionDiffResult.Accepted
        val replacement = requireNotNull(VoiceCorrectionLearning.prepare(original, diff.replacement))
        repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, highConfidence = true, turnId = 1L)
        repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, highConfidence = true, turnId = 2L)
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }

        assertEquals(edited, replacement.suggestedPromptText)
        assertEquals(listOf(edited), repository.getPromptWords())
        assertTrue(dictionary.buildWhisperPrompt(includePersonalization = true).contains(edited))
        assertTrue(dictionary.buildLlmVocabularyHint(original, includePersonalization = true).contains("\"$edited\""))
        assertEquals(edited, dictionary.applyCorrections(original, includePersonalization = true))

        val tooLong = "a".repeat(65)
        val oversizedDiff = CorrectionDiff.analyze(tooLong, "A" + "a".repeat(64)) as CorrectionDiffResult.Accepted
        assertNull(VoiceCorrectionLearning.prepare(tooLong, oversizedDiff.replacement))
    }

    @Test
    fun `complete learned term still needs repeated low confidence evidence and field consent`() {
        val original = "請開啟orbit code"
        val diff = CorrectionDiff.analyze(original, "請開啟Orbit Code") as CorrectionDiffResult.Accepted
        val replacement = requireNotNull(VoiceCorrectionLearning.prepare(original, diff.replacement))
        val repository = PersonalizationRepository(CorrectionLearningStorage())
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }

        for (turn in 1L..2L) {
            val pending = repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, false, turn)
            assertEquals(CorrectionRecordStatus.EVIDENCE_RECORDED, pending.status)
            assertTrue(repository.getPromptWords().isEmpty())
            assertEquals(original, dictionary.applyCorrections(original, includePersonalization = true))
        }

        val confirmed = repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, false, 3L)
        assertEquals(CorrectionRecordStatus.ACTIVATED, confirmed.status)
        assertEquals("請開啟Orbit Code", dictionary.applyCorrections(original, includePersonalization = true))
        assertEquals(original, dictionary.applyCorrections(original, includePersonalization = false))
        assertFalse(dictionary.buildWhisperPrompt(includePersonalization = false).contains("Orbit Code"))
        assertFalse(dictionary.buildLlmVocabularyHint(original, includePersonalization = false).contains("Orbit Code"))

        repository.setEnabled(false)
        assertEquals(original, dictionary.applyCorrections(original, includePersonalization = true))
        assertFalse(dictionary.buildWhisperPrompt(includePersonalization = true).contains("Orbit Code"))
        assertFalse(dictionary.buildLlmVocabularyHint(original, includePersonalization = true).contains("Orbit Code"))
    }

    @Test
    fun `a correction cannot be prepared against a different committed voice text`() {
        val diff = CorrectionDiff.analyze("orbit code", "Orbit Code") as CorrectionDiffResult.Accepted
        assertNull(VoiceCorrectionLearning.prepare("other text", diff.replacement))
    }
}

private class CorrectionLearningStorage : LearningStorage {
    private val values = mutableMapOf<String, Any?>()
    override fun getString(key: String, defaultValue: String?) = values[key] as? String ?: defaultValue
    override fun getInt(key: String, defaultValue: Int) = values[key] as? Int ?: defaultValue
    override fun getBoolean(key: String, defaultValue: Boolean) = values[key] as? Boolean ?: defaultValue
    override fun update(values: Map<String, Any?>) { this.values.putAll(values) }
}
