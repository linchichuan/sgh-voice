package com.shingihou.sghvoice.processing

import android.content.SharedPreferences
import com.shingihou.sghvoice.learning.LearningLanguage
import com.shingihou.sghvoice.learning.LearningStorage
import com.shingihou.sghvoice.learning.PersonalizationRepository
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/** Real learning repository and dictionary, with only persistent storage replaced. */
class LearnedCjkSafetyTest {
    @Test fun `activated single Han correction contributes its complete short term to STT`() {
        val repository = PersonalizationRepository(CjkSafetyStorage())
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }
        for (turn in 1L..2L) {
            repository.recordVoiceCorrection(LearningLanguage.MIXED, "診聊所", "診療所", true, turnId = turn)
            if (turn == 1L) {
                assertFalse(dictionary.buildWhisperPrompt(true).split('、').contains("診療所"))
            }
        }
        assertEquals(1, repository.getActiveVoiceCorrections().size)

        assertTrue(dictionary.buildWhisperPrompt(includePersonalization = true).split('、').contains("診療所"))
        assertFalse(dictionary.buildWhisperPrompt(false).split('、').contains("診療所"))
        assertEquals("去診聊所", dictionary.applyCorrections("去診聊所", true))
        assertNull(dictionary.getSpellingAliases(true)["診聊所"])
        repository.setEnabled(false)
        assertFalse(dictionary.buildWhisperPrompt(true).split('、').contains("診療所"))
    }

    @Test fun `reloaded active rule with legacy empty prompt still supplies its short term`() {
        // Persisted schema-v2 rules from the previous release stored an empty hint.
        val storage = CjkSafetyStorage().apply {
            update(mapOf("schema_version" to 2, "voice_corrections_v2" to JSONArray().put(JSONObject()
                .put("language", "MIXED").put("wrongText", "診聊所").put("correctedText", "診療所")
                .put("promptText", "").put("evidenceCount", 2).put("highConfidenceSeen", true)
                .put("active", true).put("lastSeenAtMillis", 5L).put("scope", "CHINESE")
            ).toString()))
        }
        val reloaded = PersonalizationRepository(storage)
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { reloaded }

        assertEquals(1, reloaded.getActiveVoiceCorrections().size)
        assertTrue(dictionary.buildWhisperPrompt(includePersonalization = true).split('、').contains("診療所"))
    }

    @Test fun `learned kana never replaces part of a longer word`() {
        val repository = PersonalizationRepository(CjkSafetyStorage())
        for (turn in 1L..2L) {
            repository.recordVoiceCorrection(LearningLanguage.JAPANESE, "バス", "パス", true, turnId = turn)
        }
        assertEquals(1, repository.getActiveVoiceCorrections().size)
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }

        assertEquals("バスケットをする", dictionary.applyCorrections("バスケットをする", true))
        assertEquals("バス", dictionary.applyCorrections("バス", true))
        assertTrue(dictionary.buildWhisperPrompt(true).split('、').contains("パス"))
        assertFalse(dictionary.buildLlmVocabularyHint("バスケットをする", true).contains("パス"))
        assertNull(dictionary.getSpellingAliases(true)["バス"])
    }

    @Test fun `explicit manual kana rule keeps its existing behavior`() {
        val prefs = mock<SharedPreferences>()
        whenever(prefs.getString("corrections", null)).thenReturn(JSONObject().put("バス", "パス").toString())
        val dictionary = DictionaryManager(prefs) { PersonalizationRepository(CjkSafetyStorage()) }

        assertEquals("パス", dictionary.applyCorrections("バス", true))
    }

    @Test fun `v1 migration never promotes pending or unspecified rules into cloud hints`() {
        fun legacy(wrong: String, corrected: String, active: Boolean?) = JSONObject()
            .put("language", "MIXED").put("wrongText", wrong).put("correctedText", corrected)
            .put("promptText", corrected).put("evidenceCount", 1).put("highConfidenceSeen", true)
            .put("lastSeenAtMillis", 5L).apply { if (active != null) put("active", active) }
        val storage = CjkSafetyStorage().apply {
            update(mapOf("schema_version" to 1, "voice_corrections_v1" to JSONArray()
                .put(legacy("Kotlun", "Kotlin", true))
                .put(legacy("Orbyt", "Orbit", false))
                .put(legacy("Nybulax", "Nebulax", null)).toString()))
        }

        // Exercise both the migration and its persisted reload through public interfaces.
        repeat(2) {
            val repository = PersonalizationRepository(storage)
            val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }
            assertEquals(setOf("Kotlun", "Orbyt", "Nybulax"), repository.getVoiceCorrections().map { it.wrongText }.toSet())
            assertEquals(listOf("Kotlun"), repository.getActiveVoiceCorrections().map { it.wrongText })
            val prompt = dictionary.buildWhisperPrompt(true).split('、')
            assertTrue(prompt.contains("Kotlin"))
            assertFalse(prompt.contains("Orbit"))
            assertFalse(prompt.contains("Nebulax"))
            val llm = dictionary.buildLlmVocabularyHint("Orbyt Nybulax", true)
            assertFalse(llm.contains("Orbit"))
            assertFalse(llm.contains("Nebulax"))
            assertNull(dictionary.getSpellingAliases(true)["Orbyt"])
            assertNull(dictionary.getSpellingAliases(true)["Nybulax"])
            assertEquals("Orbyt Nybulax", dictionary.applyCorrections("Orbyt Nybulax", true))
        }
    }
}

private class CjkSafetyStorage : LearningStorage {
    private val values = mutableMapOf<String, Any?>()
    override fun getString(key: String, defaultValue: String?) = values[key] as? String ?: defaultValue
    override fun getInt(key: String, defaultValue: Int) = values[key] as? Int ?: defaultValue
    override fun getBoolean(key: String, defaultValue: Boolean) = values[key] as? Boolean ?: defaultValue
    override fun update(values: Map<String, Any?>) { this.values.putAll(values) }
}
