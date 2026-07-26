package com.shingihou.sghvoice.learning

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PersonalizationRepositoryTest {

    @Test
    fun `selected candidate is promoted and survives repository recreation`() {
        val storage = InMemoryLearningStorage()
        var now = 100L
        val repository = repository(storage) { now }

        repository.recordCandidateSelection(
            LearningLanguage.ENGLISH,
            inputKey = "HE",
            candidate = "hello"
        )
        now += 1

        assertEquals(
            listOf("hello", "help", "hero"),
            repository.rankCandidates(
                LearningLanguage.ENGLISH,
                inputKey = "he",
                candidates = listOf("help", "hero", "hello")
            )
        )

        val reloaded = repository(storage) { now }
        assertEquals(
            1,
            reloaded.getCandidateUsage(
                LearningLanguage.ENGLISH,
                "he",
                "hello"
            )?.selectedCount
        )
    }

    @Test
    fun `disabled repository neither learns nor changes ranking`() {
        val repository = repository()
        repository.setEnabled(false)

        assertNull(
            repository.recordCandidateSelection(
                LearningLanguage.ZHUYIN,
                "ㄋㄧˇ",
                "你"
            )
        )
        assertEquals(
            listOf("擬", "你"),
            repository.rankCandidates(
                LearningLanguage.ZHUYIN,
                "ㄋㄧˇ",
                listOf("擬", "你")
            )
        )
        assertFalse(repository.getStats().enabled)
    }

    @Test
    fun `high confidence correction activates immediately and yields prompt word`() {
        val repository = repository()

        val result = repository.recordVoiceCorrection(
            language = LearningLanguage.MIXED,
            replacement = CorrectionReplacement(
                wrongText = "cloud c",
                correctedText = "Claude C",
                suggestedPromptText = "Claude Code",
                unchangedPrefixCodePoints = 0,
                unchangedSuffixCodePoints = 3
            ),
            highConfidence = true
        )

        assertEquals(CorrectionRecordStatus.ACTIVATED, result.status)
        assertTrue(result.rule?.active == true)
        assertEquals(listOf("Claude Code"), repository.getPromptWords())
    }

    @Test
    fun `low confidence correction requires two identical observations`() {
        val repository = repository()

        val first = repository.recordVoiceCorrection(
            LearningLanguage.ZHUYIN,
            "林紀泉",
            "林紀全",
            highConfidence = false
        )
        val second = repository.recordVoiceCorrection(
            LearningLanguage.ZHUYIN,
            "林紀泉",
            "林紀全",
            highConfidence = false
        )

        assertEquals(CorrectionRecordStatus.EVIDENCE_RECORDED, first.status)
        assertFalse(first.rule?.active == true)
        assertEquals(CorrectionRecordStatus.ACTIVATED, second.status)
        assertEquals(2, second.rule?.evidenceCount)
    }

    @Test
    fun `undo restores previous record and an entry evicted by the bound`() {
        val storage = InMemoryLearningStorage()
        var now = 1L
        val repository = repository(
            storage = storage,
            limits = PersonalizationLimits(
                maxCandidateRecords = 2,
                maxCorrectionRules = 2
            ),
            clock = { now }
        )

        repository.recordCandidateSelection(LearningLanguage.ENGLISH, "a", "alpha")
        now += 1
        repository.recordCandidateSelection(LearningLanguage.ENGLISH, "b", "beta")
        now += 1
        repository.recordCandidateSelection(LearningLanguage.ENGLISH, "a", "alpha")
        now += 1
        repository.recordCandidateSelection(LearningLanguage.ENGLISH, "c", "charlie")

        assertNull(
            repository.getCandidateUsage(LearningLanguage.ENGLISH, "b", "beta")
        )
        assertTrue(repository.undoLast())
        assertNull(
            repository.getCandidateUsage(LearningLanguage.ENGLISH, "c", "charlie")
        )
        assertEquals(
            1,
            repository.getCandidateUsage(
                LearningLanguage.ENGLISH,
                "b",
                "beta"
            )?.selectedCount
        )
    }

    @Test
    fun `undo correction removes its activation`() {
        val repository = repository()
        repository.recordVoiceCorrection(
            LearningLanguage.JAPANESE,
            "清涼",
            "診療",
            highConfidence = true
        )

        assertEquals(1, repository.getActiveVoiceCorrections().size)
        assertTrue(repository.undoLast())
        assertTrue(repository.getActiveVoiceCorrections().isEmpty())
        assertFalse(repository.undoLast())
    }

    @Test
    fun `clear all resets learned stats while preserving enabled state`() {
        val repository = repository()
        repository.recordCandidateSelection(
            LearningLanguage.ZHUYIN,
            "ㄋㄧˇ",
            "你"
        )
        repository.recordVoiceCorrection(
            LearningLanguage.MIXED,
            "新義豐",
            "新義豊",
            highConfidence = true
        )

        repository.clearAll()

        assertTrue(repository.isEnabled())
        assertEquals(
            PersonalizationStats(
                enabled = true,
                candidateRecordCount = 0,
                totalCandidateSelections = 0,
                correctionRuleCount = 0,
                activeCorrectionRuleCount = 0,
                totalCorrectionEvidence = 0
            ),
            repository.getStats()
        )
    }

    private fun repository(
        storage: InMemoryLearningStorage = InMemoryLearningStorage(),
        limits: PersonalizationLimits = PersonalizationLimits(),
        clock: () -> Long = { 1L }
    ) = PersonalizationRepository(storage, clock, limits)
}

private class InMemoryLearningStorage : LearningStorage {
    private val values = mutableMapOf<String, Any>()

    override fun getString(key: String, defaultValue: String?): String? =
        values[key] as? String ?: defaultValue

    override fun getInt(key: String, defaultValue: Int): Int =
        values[key] as? Int ?: defaultValue

    override fun getBoolean(key: String, defaultValue: Boolean): Boolean =
        values[key] as? Boolean ?: defaultValue

    override fun update(values: Map<String, Any?>) {
        values.forEach { (key, value) ->
            if (value == null) {
                this.values.remove(key)
            } else {
                this.values[key] = value
            }
        }
    }
}
