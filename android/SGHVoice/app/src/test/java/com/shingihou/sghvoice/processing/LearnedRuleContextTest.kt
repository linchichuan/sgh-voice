package com.shingihou.sghvoice.processing

import android.content.SharedPreferences
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.learning.LearningLanguage
import com.shingihou.sghvoice.learning.LearningStorage
import com.shingihou.sghvoice.learning.PersonalizationRepository
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
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
 * Gap 3 (05 acceptance probe): an active learned Han->Han pair (在家→再加) must not be handed to
 * the LLM, where it could be applied in an unrelated context (我今天在家裡休息 → 再加裡). It stays an
 * STT hint only. Han->ASCII pairs (吉他哈布→GitHub) remain guard aliases. Also: learned rules
 * cannot change a name next to a title.
 */
class LearnedRuleContextTest {
    private fun repository(vararg rules: Pair<String, String>) =
        PersonalizationRepository(ContextStorage()).also { repo ->
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
        whenever(it.sttEngine).thenReturn("openai")
        whenever(it.openAiApiKey).thenReturn("synthetic-test-key")
        whenever(it.whisperModel).thenReturn("gpt-transcribe")
        whenever(it.recognitionLanguage).thenReturn(RecognitionLanguage.AUTO)
    }

    private fun ok(request: Request, body: JSONObject) =
        Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(200).message("OK")
            .body(body.toString().toResponseBody("application/json".toMediaType())).build()

    private fun Request.values(name: String): List<String> = (body as MultipartBody).parts
        .filter { it.headers?.get("Content-Disposition") == "form-data; name=\"$name\"" }
        .map { part -> Buffer().also { part.body.writeTo(it) }.readUtf8() }

    @Test fun `learned Han to Han word reaches STT only, never the LLM vocabulary or guard aliases`() = runBlocking {
        val repo = repository("在家" to "再加", "吉他哈布" to "GitHub")
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repo }
        val config = config()
        var keywords: List<String> = emptyList()
        var vocabulary: List<String> = emptyList()
        val whisper = WhisperClient(config, OkHttpClient.Builder().addInterceptor { chain ->
            keywords = chain.request().values("keywords[]")
            ok(chain.request(), JSONObject().put("text", "我今天在家裡休息"))
        }.build())
        val llm = LlmClient(config, OkHttpClient.Builder().addInterceptor { chain ->
            val body = JSONObject(Buffer().also { chain.request().body!!.writeTo(it) }.readUtf8())
            val user = JSONObject(body.getJSONArray("messages").getJSONObject(1).getString("content"))
            vocabulary = user.getJSONArray("vocabulary").let { array -> List(array.length()) { array.getString(it) } }
            ok(chain.request(), JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop").put("message", JSONObject().put("content", "我今天在家裡休息。")))))
        }.build()) { dictionary.getSpellingAliases(includeLearned = true) }
        val result = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }
            .process(ByteArray(44), includePersonalization = true)
        whisper.shutdown()

        assertTrue("STT hint keeps the learned Han word", keywords.contains("再加"))
        assertFalse("LLM vocabulary must not carry a learned Han->Han word", vocabulary.contains("再加"))
        assertTrue("Han->ASCII learned term is still LLM vocabulary", vocabulary.contains("GitHub"))
        assertEquals("我今天在家裡休息。", result.text)

        val aliases = dictionary.getSpellingAliases(includeLearned = true)
        assertNull("Han->Han learned pair is not a guard alias", aliases["在家"])
        assertEquals("GitHub", aliases["吉他哈布"])
    }

    @Test fun `learned rule cannot change a name next to a title`() {
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository("Lin" to "Lynn") }
        assertEquals("Send to Mr. Lin and Lynn.", dictionary.applyCorrections("Send to Mr. Lin and Lin.", includePersonalization = true))
    }
}

private class ContextStorage : LearningStorage {
    private val values = mutableMapOf<String, Any>()
    override fun getString(key: String, defaultValue: String?) = values[key] as? String ?: defaultValue
    override fun getInt(key: String, defaultValue: Int) = values[key] as? Int ?: defaultValue
    override fun getBoolean(key: String, defaultValue: Boolean) = values[key] as? Boolean ?: defaultValue
    override fun update(values: Map<String, Any?>) {
        values.forEach { (key, value) -> if (value == null) this.values.remove(key) else this.values[key] = value }
    }
}
