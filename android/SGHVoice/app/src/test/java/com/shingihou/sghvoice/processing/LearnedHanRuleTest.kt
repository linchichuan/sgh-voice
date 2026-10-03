package com.shingihou.sghvoice.processing

import android.content.SharedPreferences
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.learning.LearningLanguage
import com.shingihou.sghvoice.learning.LearningStorage
import com.shingihou.sghvoice.learning.PersonalizationRepository
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * Learned rules containing Han (no word segmentation) never replace text literally: they are
 * STT hints only for CJK->CJK, or guard aliases for CJK->Latin. Only Latin and manual rules
 * keep replacing literally; pure kana must not rewrite pieces of longer Japanese words.
 */
class LearnedHanRuleTest {
    private fun repository(vararg rules: Pair<String, String>) =
        PersonalizationRepository(HanStorage()).also { repo ->
            rules.forEach { (wrong, corrected) ->
                for (turn in 1L..2L) repo.recordVoiceCorrection(LearningLanguage.MIXED, wrong, corrected, true, turnId = turn)
            }
        }

    private fun config() = mock<ApiConfig>().also {
        whenever(it.llmEngine).thenReturn("groq")
        whenever(it.groqApiKey).thenReturn("synthetic-test-key")
        whenever(it.groqLlmModel).thenReturn("test-model")
        whenever(it.outputStyle).thenReturn("normal")
        whenever(it.hasCloudProcessingConsent).thenReturn(true)
    }

    private fun refine(dictionary: DictionaryManager, source: String, reply: String, includeLearned: Boolean) = runBlocking {
        LlmClient(config(), OkHttpClient.Builder().addInterceptor { chain ->
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200).message("OK")
                .body(JSONObject().put("choices", JSONArray().put(JSONObject().put("finish_reason", "stop")
                    .put("message", JSONObject().put("content", reply)))).toString()
                    .toResponseBody("application/json".toMediaType())).build()
        }.build()) { dictionary.getSpellingAliases(includeLearned) }
            .refineDictation(source, vocabularyHint = dictionary.buildLlmVocabularyHint(source, true))
    }

    @Test fun `active Han rule never rewrites a longer word literally`() {
        val repo = repository("在家" to "再加")
        assertEquals(1, repo.getActiveVoiceCorrections().size)
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repo }
        assertEquals("我在家裡", dictionary.applyCorrections("我在家裡", includePersonalization = true))
        assertEquals("我們在家開會", dictionary.applyCorrections("我們在家開會", includePersonalization = true))
        // STT hint only (2026-10-03 gap 3): never a guard alias.
        assertTrue(dictionary.buildWhisperPrompt(includePersonalization = true).split('、').contains("再加"))
        assertNull(dictionary.getSpellingAliases(includeLearned = true)["在家"])
    }

    @Test fun `Latin and manual rules still replace while learned kana stays unchanged`() {
        val prefs = mock<SharedPreferences>()
        whenever(prefs.getString("corrections", null)).thenReturn(JSONObject().put("清涼", "診療").toString())
        val dictionary = DictionaryManager(prefs) { repository("Kotlun" to "Kotlin", "ことりむ" to "ことりん") }
        assertEquals("用Kotlin、ことりむ、診療所", dictionary.applyCorrections("用Kotlun、ことりむ、清涼所", includePersonalization = true))
    }

    // Revised 2026-10-03 (gap 3): the previous expectation endorsed the LLM applying the learned
    // 在家→再加 in a new sentence. A learned Han->Han pair is now not handed to the LLM vocabulary
    // and is not a guard alias, so a learned rule cannot induce a cross-context replacement.
    @Test fun `learned Han word is not handed to the LLM and an unchanged reply keeps the source`() {
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository("在家" to "再加") }
        val source = dictionary.applyCorrections("我們在家開會", includePersonalization = true)
        assertEquals("我們在家開會", source)
        assertFalse(dictionary.buildLlmVocabularyHint(source, includePersonalization = true).contains("再加"))
        assertNull(dictionary.getSpellingAliases(includeLearned = true)["在家"])
        val unchanged = refine(dictionary, source, "我們在家開會。", includeLearned = true)
        assertEquals(LlmClient.RefinementStatus.APPLIED, unchanged.status)
        assertEquals("我們在家開會。", unchanged.text)
    }
}

private class HanStorage : LearningStorage {
    private val values = mutableMapOf<String, Any>()
    override fun getString(key: String, defaultValue: String?) = values[key] as? String ?: defaultValue
    override fun getInt(key: String, defaultValue: Int) = values[key] as? Int ?: defaultValue
    override fun getBoolean(key: String, defaultValue: Boolean) = values[key] as? Boolean ?: defaultValue
    override fun update(values: Map<String, Any?>) {
        values.forEach { (key, value) -> if (value == null) this.values.remove(key) else this.values[key] = value }
    }
}
