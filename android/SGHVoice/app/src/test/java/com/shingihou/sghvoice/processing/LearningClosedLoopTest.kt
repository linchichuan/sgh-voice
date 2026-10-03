package com.shingihou.sghvoice.processing

import android.content.SharedPreferences
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.learning.BoundedTextSnapshot
import com.shingihou.sghvoice.learning.CorrectionRecordStatus
import com.shingihou.sghvoice.learning.LearningLanguage
import com.shingihou.sghvoice.learning.LearningStorage
import com.shingihou.sghvoice.learning.PersonalizationRepository
import com.shingihou.sghvoice.learning.RecentVoiceContext
import com.shingihou.sghvoice.learning.VoiceCorrectionTracker
import com.shingihou.sghvoice.learning.VoiceLearningGate
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
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * End-to-end learning loop with real modules: WhisperClient (multipart captured by an
 * interceptor), LlmClient (JSON body captured, synthetic reply), DictionaryManager,
 * PersonalizationRepository, VoiceCorrectionTracker, OpenCC and TranscriptionPipeline.
 * Only storage and HTTP transport are synthetic. No paid API is called.
 */
class LearningClosedLoopTest {

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

    private fun Request.values(name: String): List<String> = (body as MultipartBody).parts
        .filter { it.headers?.get("Content-Disposition") == "form-data; name=\"$name\"" }
        .map { part -> Buffer().also { part.body.writeTo(it) }.readUtf8() }

    private class Exchange {
        var keywords: List<String> = emptyList()
        var vocabulary: List<String> = emptyList()
        var sourceText: String = ""
        var hasPreviousContext = false
    }

    private fun userContent(body: JSONObject) =
        JSONObject(body.getJSONArray("messages").getJSONObject(1).getString("content"))

    /** One dictation through the real pipeline. [reply] maps the LLM source_text to its answer. */
    private fun dictate(
        dictionary: DictionaryManager,
        stt: String,
        reply: (String) -> String,
        aliases: () -> Map<String, String>,
        context: () -> String = { "" }
    ): Pair<TranscriptionPipeline.Result, Exchange> = runBlocking {
        val exchange = Exchange()
        val config = config()
        val whisper = WhisperClient(config, OkHttpClient.Builder().addInterceptor { chain ->
            exchange.keywords = chain.request().values("keywords[]")
            jsonResponse(chain.request(), JSONObject().put("text", stt))
        }.build())
        val llm = LlmClient(config, OkHttpClient.Builder().addInterceptor { chain ->
            val body = JSONObject(Buffer().also { chain.request().body!!.writeTo(it) }.readUtf8())
            val user = userContent(body)
            exchange.sourceText = user.getString("source_text")
            exchange.hasPreviousContext = user.has("previous_context")
            exchange.vocabulary = user.getJSONArray("vocabulary").let { a -> List(a.length()) { a.getString(it) } }
            jsonResponse(chain.request(), JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop")
                .put("message", JSONObject().put("content", reply(exchange.sourceText))))))
        }.build(), aliases)
        val pipeline = TranscriptionPipeline(whisper, llm, dictionary, OpenCCConverter()) { true }
        val result = pipeline.process(ByteArray(44), VoiceTask.Dictation, includePersonalization = true,
            recentContext = context)
        whisper.shutdown()
        result to exchange
    }

    /** What the IME does after commit: track from the gate's STT baseline, let the user edit, finalize. */
    private fun userCorrects(
        repository: PersonalizationRepository,
        result: TranscriptionPipeline.Result,
        edited: String,
        turnId: Long
    ): List<CorrectionRecordStatus> {
        val baseline = VoiceLearningGate.trackingBaseline(VoiceTask.Dictation, result)!!
        var now = 0L
        val tracker = VoiceCorrectionTracker(clockElapsedMillis = { now })
        fun snapshot(text: String) = BoundedTextSnapshot("前文：$text", afterCursor = "：後文", windowStartOffset = 0)
        assertTrue(tracker.begin(turnId, result.text, snapshot(result.text), sttText = baseline))
        now = 3_000L
        tracker.inspect(turnId, snapshot(edited))
        now = 8_000L
        return tracker.finish(turnId).map {
            repository.recordVoiceCorrection(LearningLanguage.MIXED, it.replacement, it.highConfidence, turnId, it.scope).status
        }
    }

    @Test fun `correction is pending after one turn, active after a second, then used by STT LLM and output`() {
        val repository = PersonalizationRepository(ClosedLoopStorage())
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }
        val aliases = { dictionary.getSpellingAliases(includeLearned = true) }
        val echoWithPeriod = { source: String -> if (source.endsWith("。")) source else "$source。" }

        // Turn 1: STT misspells, AI keeps it, the user fixes it.
        val (first, firstExchange) = dictate(dictionary, "請用Zorblat測試", echoWithPeriod, aliases)
        assertEquals("請用Zorblat測試。", first.text)
        assertFalse(firstExchange.keywords.contains("Zorbit"))
        assertEquals(listOf(CorrectionRecordStatus.EVIDENCE_RECORDED),
            userCorrects(repository, first, "請用Zorbit測試。", turnId = 1L))

        // Control: while pending the word stays local; text is never replaced.
        val (pending, pendingExchange) = dictate(dictionary, "再用Zorblat一次", echoWithPeriod, aliases)
        assertFalse(pendingExchange.keywords.contains("Zorbit"))
        assertFalse(pendingExchange.vocabulary.contains("Zorbit"))
        assertEquals("再用Zorblat一次", pendingExchange.sourceText)
        assertEquals("再用Zorblat一次。", pending.text)

        // Turn 2: the same fix in a different voice turn activates the rule.
        assertEquals(listOf(CorrectionRecordStatus.ACTIVATED),
            userCorrects(repository, pending, "再用Zorbit一次。", turnId = 2L))

        // Next dictation: STT keywords, LLM vocabulary, source_text and final output all use it.
        val (next, nextExchange) = dictate(dictionary, "明天用Zorblat寫測試",
            { "明天用 Zorbit 寫測試。" }, aliases)
        assertTrue(nextExchange.keywords.contains("Zorbit"))
        assertTrue(nextExchange.vocabulary.contains("Zorbit"))
        assertEquals("明天用Zorbit寫測試", nextExchange.sourceText)
        assertEquals(LlmClient.RefinementStatus.APPLIED, next.refinementStatus)
        assertEquals("明天用 Zorbit 寫測試。", next.text)
    }

    @Test fun `an active learned Han alias lets the guard accept the learned word, pending does not`() {
        val repository = PersonalizationRepository(ClosedLoopStorage())
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }
        val reply = "請檢查 GitHub 的設定。"
        fun guard(includeLearned: Boolean, source: String = "請檢查「吉他哈布」的設定。") = runBlocking {
            val config = config()
            LlmClient(config, OkHttpClient.Builder().addInterceptor { chain ->
                jsonResponse(chain.request(), JSONObject().put("choices", JSONArray().put(JSONObject()
                    .put("finish_reason", "stop").put("message", JSONObject().put("content", reply)))))
            }.build()) { dictionary.getSpellingAliases(includeLearned) }
                .refineDictation(source,
                    vocabularyHint = dictionary.buildLlmVocabularyHint(source, true))
        }

        repository.recordVoiceCorrection(LearningLanguage.MIXED, "吉他哈布", "GitHub", true, turnId = 1L)
        assertEquals("Pending rule is not an alias", LlmClient.RefinementStatus.REJECTED, guard(true).status)

        repository.recordVoiceCorrection(LearningLanguage.MIXED, "吉他哈布", "GitHub", true, turnId = 2L)
        val applied = guard(true)
        assertEquals(LlmClient.RefinementStatus.APPLIED, applied.status)
        assertEquals(reply, applied.text)
        // Even active aliases cannot prove a word boundary inside a connected Han phrase.
        assertEquals(LlmClient.RefinementStatus.REJECTED,
            guard(true, "請檢查吉他哈布的設定。").status)
        assertEquals("A field without personalization gets no learned alias",
            LlmClient.RefinementStatus.REJECTED, guard(false).status)
    }

    @Test fun `AI wording reverted by the user is not learned through the real pipeline`() {
        val repository = PersonalizationRepository(ClosedLoopStorage())
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }
        // Use an explicitly accepted spelling repair, not a synonym rewrite that the
        // owner-approved strict policy now rejects before insertion.
        val (result, _) = dictate(dictionary, "コトリン でテストを書く", { "Kotlin でテストを書く。" },
            { dictionary.getSpellingAliases(includeLearned = true) })
        assertEquals(LlmClient.RefinementStatus.APPLIED, result.refinementStatus)
        assertEquals("Kotlin でテストを書く。", result.text)
        assertTrue(userCorrects(repository, result, "コトリン でテストを書く。", turnId = 1L).isEmpty())
        assertTrue(repository.getVoiceCorrections().isEmpty())
    }

    @Test fun `unconfirmed synonym rewrite is rejected before the learning pipeline`() {
        val repository = PersonalizationRepository(ClosedLoopStorage())
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }
        val (result, _) = dictate(dictionary, "我先檢查然後部署", { "我先檢查，接著部署。" },
            { dictionary.getSpellingAliases(includeLearned = true) })
        assertEquals(LlmClient.RefinementStatus.REJECTED, result.refinementStatus)
        assertEquals("我先檢查然後部署", result.text)
    }

    @Test fun `E19 expired previous context is not sent and live context cannot be copied into output`() {
        val repository = PersonalizationRepository(ClosedLoopStorage())
        val dictionary = DictionaryManager(mock<SharedPreferences>()) { repository }
        val aliases = { dictionary.getSpellingAliases(includeLearned = true) }
        var now = 0L
        val context = RecentVoiceContext { now }
        context.remember(1L, "王小明說下午三點到。", true)

        now = 61_000L
        val (_, expired) = dictate(dictionary, "他說明天會來", { "他說明天會來。" }, aliases) { context.get(1L, true) }
        assertFalse(expired.hasPreviousContext)

        now = 0L
        context.remember(1L, "王小明說下午三點到。", true)
        now = 10_000L
        for (copied in listOf("王小明說明天會來。", "王小明說下午三點到。他說明天會來。")) {
            val (result, live) = dictate(dictionary, "他說明天會來", { copied }, aliases) { context.get(1L, true) }
            assertTrue(live.hasPreviousContext)
            assertEquals(LlmClient.RefinementStatus.REJECTED, result.refinementStatus)
            assertEquals("他說明天會來", result.text)
        }
        val (fine, _) = dictate(dictionary, "他說明天會來", { "他說明天會來。" }, aliases) { context.get(1L, true) }
        assertEquals(LlmClient.RefinementStatus.APPLIED, fine.refinementStatus)
        assertEquals("他說明天會來。", fine.text)
    }
}

private class ClosedLoopStorage : LearningStorage {
    private val values = mutableMapOf<String, Any>()
    override fun getString(key: String, defaultValue: String?) = values[key] as? String ?: defaultValue
    override fun getInt(key: String, defaultValue: Int) = values[key] as? Int ?: defaultValue
    override fun getBoolean(key: String, defaultValue: Boolean) = values[key] as? Boolean ?: defaultValue
    override fun update(values: Map<String, Any?>) {
        values.forEach { (key, value) -> if (value == null) this.values.remove(key) else this.values[key] = value }
    }
}
