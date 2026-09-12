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
    @Test
    fun `single letter correction beside Chinese learns only the complete English term`() {
        val original = "使用Orbyt進行部署"
        val diff = CorrectionDiff.analyze(original, "使用Orbit進行部署")
            as CorrectionDiffResult.Accepted
        val replacement = requireNotNull(VoiceCorrectionLearning.prepare(original, diff.replacement))
        val repository = PersonalizationRepository(CorrectionLearningStorage())
        repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, highConfidence = true)
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
        val recorded = repository.recordVoiceCorrection(
            LearningLanguage.MIXED,
            replacement,
            highConfidence = true
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
    fun `complete 64 character word reaches hints but oversized word is never truncated`() {
        val original = "a".repeat(64)
        val edited = "A" + "a".repeat(63)
        val diff = CorrectionDiff.analyze(original, edited) as CorrectionDiffResult.Accepted
        val replacement = requireNotNull(VoiceCorrectionLearning.prepare(original, diff.replacement))
        val repository = PersonalizationRepository(CorrectionLearningStorage())
        repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, highConfidence = true)
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

        val pending = repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, highConfidence = false)
        assertEquals(CorrectionRecordStatus.EVIDENCE_RECORDED, pending.status)
        assertTrue(repository.getPromptWords().isEmpty())
        assertEquals(original, dictionary.applyCorrections(original, includePersonalization = true))

        val confirmed = repository.recordVoiceCorrection(LearningLanguage.MIXED, replacement, highConfidence = false)
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
