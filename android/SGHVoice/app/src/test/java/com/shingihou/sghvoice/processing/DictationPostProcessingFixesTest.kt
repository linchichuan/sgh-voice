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
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * Problems 4-6 and the E17 request-assembly proof. Real dictionary, repository, OpenCC,
 * WhisperClient, LlmClient and pipeline; only storage and HTTP transports are synthetic.
 */
class DictationPostProcessingFixesTest {

    private fun repository(vararg rules: Pair<String, String>) =
        PersonalizationRepository(FixesLearningStorage()).also { repo ->
            // A learned rule is 已生效 only after two voice turns (learning package spec 2).
            rules.forEach { (wrong, corrected) ->
                repo.recordVoiceCorrection(LearningLanguage.MIXED, wrong, corrected, highConfidence = true, turnId = 1L)
                repo.recordVoiceCorrection(LearningLanguage.MIXED, wrong, corrected, highConfidence = true, turnId = 2L)
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

    private fun jsonResponse(request: Request, body: JSONObject) =
        Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(200).message("OK")
            .body(body.toString().toResponseBody("application/json".toMediaType())).build()

    private fun llmClient(config: ApiConfig, reply: String, onRequest: (JSONObject) -> Unit = {}) =
        LlmClient(config, OkHttpClient.Builder().addInterceptor { chain ->
            val buffer = Buffer().also { chain.request().body!!.writeTo(it) }
            onRequest(JSONObject(buffer.readUtf8()))
            jsonResponse(chain.request(), JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop")
                .put("message", JSONObject().put("content", reply)))))
        }.build())

    private fun Request.values(name: String): List<String> = (body as MultipartBody).parts
        .filter { it.headers?.get("Content-Disposition") == "form-data; name=\"$name\"" }
        .map { part -> Buffer().also { part.body.writeTo(it) }.readUtf8() }

    // ---- Problem 4: OpenCC must not rewrite Japanese kanji ----

    @Test fun `OpenCC keeps Japanese clauses and still converts Chinese clauses`() {
        val converter = OpenCCConverter()
        assertEquals("テストを実行して、画像を確認します。", converter.convert("テストを実行して、画像を確認します。"))
        assertEquals("明日の会議で説明します。", converter.convert("明日の会議で説明します。"))
        assertEquals("明天的會議。テストの画像を確認します。", converter.convert("明天的会议。テストの画像を確認します。"))
        assertEquals("這個軟件需要更新。", converter.convert("这个软件需要更新。"))
    }

    @Test fun `E1 final dictation output keeps Japanese kanji and technical words`() = runBlocking {
        val source = "明天的会議で GitHub Actions を確認して、然後 git push。"
        val whisper = mock<WhisperClient>()
        whenever(whisper.transcribe(any(), any())).thenReturn(source)
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { error("No personalization in this field") }
        val pipeline = TranscriptionPipeline(whisper, llmClient(config(), source), dictionary, OpenCCConverter()) { true }
        val result = pipeline.process(ByteArray(1))
        assertEquals(LlmClient.RefinementStatus.APPLIED, result.refinementStatus)
        assertEquals("明天的会議で GitHub Actions を確認して、然後 git push。", result.text)
    }

    // ---- Problem 5: dictionary corrections can never flip facts ----

    @Test fun `learned rules that change numbers or negation are never applied`() {
        val dictionary = DictionaryManager(mock<SharedPreferences>()) {
            repository("下午三點開" to "下午四點開", "不要" to "可以", "Kotlun" to "Kotlin")
        }
        assertEquals("明天下午三點開會", dictionary.applyCorrections("明天下午三點開會", includePersonalization = true))
        assertEquals("你不要部署", dictionary.applyCorrections("你不要部署", includePersonalization = true))
        // A spelling-only rule from the same repository still applies.
        assertEquals("請用 Kotlin", dictionary.applyCorrections("請用 Kotlun", includePersonalization = true))
    }

    @Test fun `correction engine refuses sign currency unit date and negation changes`() {
        val rules = mapOf(
            "-3%" to "+3%", "美元" to "日圓", "十月三號" to "十月四號", "1,200" to "1,300",
            "三點" to "三時", "沒有" to "有", "ない" to "ある", "not" to "now", "吉他哈布" to "GitHub"
        )
        assertEquals(
            "報價 -3% 加 1,200 美元，十月三號三點前回覆，沒有備份。GitHub ではない。not yet",
            TextCorrectionEngine.apply(
                "報價 -3% 加 1,200 美元，十月三號三點前回覆，沒有備份。吉他哈布 ではない。not yet", rules
            )
        )
    }

    @Test fun `final correction pass after the guard cannot flip what the guard accepted`() = runBlocking {
        val source = "明天下午三點開會，你不要部署。"
        val whisper = mock<WhisperClient>()
        whenever(whisper.transcribe(any(), any())).thenReturn(source)
        val dictionary = DictionaryManager(mock<SharedPreferences>()) {
            repository("下午三點開" to "下午四點開", "不要" to "可以")
        }
        val pipeline = TranscriptionPipeline(whisper, llmClient(config(), source), dictionary, OpenCCConverter()) { true }
        val result = pipeline.process(ByteArray(1), includePersonalization = true)
        assertEquals("明天下午三點開會，你不要部署。", result.text)
    }

    // ---- Fail-closed Han replacement: only known aliases from the user's correction rules ----

    @Test fun `user correction rule is the alias that authorizes a Han span to become the term`() = runBlocking {
        val prefs = mock<SharedPreferences>()
        whenever(prefs.getString("corrections", null)).thenReturn(JSONObject().put("吉他哈布", "GitHub").toString())
        val dictionary = DictionaryManager(prefs) { error("Aliases never read learned data") }
        assertEquals("GitHub", dictionary.getSpellingAliases()["吉他哈布"])
        val accepted = LlmClient(config(), OkHttpClient.Builder().addInterceptor { chain ->
            jsonResponse(chain.request(), JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop")
                .put("message", JSONObject().put("content", "請檢查 GitHub 的設定。")))))
        }.build()) { dictionary.getSpellingAliases() }
        val applied = accepted.refineDictation("請檢查「吉他哈布」的設定。", vocabularyHint = "[\"GitHub\"]")
        assertEquals(LlmClient.RefinementStatus.APPLIED, applied.status)
        assertEquals("請檢查 GitHub 的設定。", applied.text)
        val rejected = accepted.refineDictation("請檢查資料庫的設定。", vocabularyHint = "[\"GitHub\"]")
        assertEquals(LlmClient.RefinementStatus.REJECTED, rejected.status)
        assertEquals("請檢查資料庫的設定。", rejected.text)
    }

    // ---- Problem 6: case-insensitive technical corrections, no misspelled hint ----

    @Test fun `technical and learned spelling corrections ignore case`() {
        assertEquals(
            "GitHub Actions、GitHub、GitHub、GitHub Actions、CI/CD",
            VocabularyHintPolicy.applyCorrections("Github actions、gitHub、Git hub、GITHUB ACTIONS、Ci/Cd")
        )
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository("Kotlun" to "Kotlin") }
        assertEquals("Kotlin、Kotlin、Kotlin", dictionary.applyCorrections("kotlun、KOTLUN、Kotlun", includePersonalization = true))
        // Word boundaries are still respected regardless of case.
        assertEquals("mygithubx", VocabularyHintPolicy.applyCorrections("mygithubx"))
    }

    @Test fun `misspelled GitPush is no longer sent as a spelling hint`() {
        val prompt = DictionaryManager(mock<SharedPreferences>()) { error("unused") }.buildWhisperPrompt()
        assertFalse(prompt.split('、').contains("GitPush"))
        assertTrue(prompt.split('、').contains("git push"))
    }

    // ---- E17: learned and custom words reach the next real STT and LLM requests ----

    @Test fun `learned and custom words reach real STT multipart and LLM vocabulary requests`() = runBlocking {
        val prefs = mock<SharedPreferences>()
        whenever(prefs.getString("custom_words", null)).thenReturn(JSONArray(listOf("SGH Voice")).toString())
        val dictionary = DictionaryManager(prefs) { repository("Zorblat" to "Zorbit") }
        val config = config()
        for (personalized in listOf(true, false)) {
            var sttRequest: Request? = null
            var llmBody: JSONObject? = null
            val whisper = WhisperClient(config, OkHttpClient.Builder().addInterceptor { chain ->
                sttRequest = chain.request()
                jsonResponse(chain.request(), JSONObject().put("text", "請用 Zorblat 測試 SGH Voice"))
            }.build())
            val stt = "請用 Zorblat 測試 SGH Voice"
            val llmReply = if (personalized) "請用 Zorbit 測試 SGH Voice。" else "$stt。"
            val llm = llmClient(config, llmReply) { llmBody = it }
            val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }
            val result = pipeline.process(ByteArray(44), includePersonalization = personalized)

            val keywords = sttRequest!!.values("keywords[]")
            val user = JSONObject(llmBody!!.getJSONArray("messages").getJSONObject(1).getString("content"))
            val vocabulary = user.getJSONArray("vocabulary").let { array -> List(array.length()) { array.getString(it) } }
            assertTrue(keywords.contains("SGH Voice"))
            assertTrue(vocabulary.contains("SGH Voice"))
            assertEquals(LlmClient.RefinementStatus.APPLIED, result.refinementStatus)
            if (personalized) {
                assertTrue(keywords.contains("Zorbit"))
                assertTrue(vocabulary.contains("Zorbit"))
                assertEquals("請用 Zorbit 測試 SGH Voice", user.getString("source_text"))
                assertEquals("請用 Zorbit 測試 SGH Voice。", result.text)
            } else {
                // Negative control: a field without personalization never sends learned words.
                assertFalse(keywords.contains("Zorbit"))
                assertFalse(vocabulary.contains("Zorbit"))
                assertEquals("請用 Zorblat 測試 SGH Voice。", result.text)
            }
            whisper.shutdown()
        }
    }
}

private class FixesLearningStorage : LearningStorage {
    private val values = mutableMapOf<String, Any?>()
    override fun getString(key: String, defaultValue: String?) = values[key] as? String ?: defaultValue
    override fun getInt(key: String, defaultValue: Int) = values[key] as? Int ?: defaultValue
    override fun getBoolean(key: String, defaultValue: Boolean) = values[key] as? Boolean ?: defaultValue
    override fun update(values: Map<String, Any?>) { this.values.putAll(values) }
}
