package com.shingihou.sghvoice.api

import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/** Independent release diagnostics; only the HTTP response is synthetic. No network/key use. */
class DictationContentPreservationTest {
    private fun check(source: String, reply: String, expected: LlmClient.RefinementStatus,
                      aliases: Map<String, String>? = null) = runBlocking {
        val config = mock<ApiConfig>()
        whenever(config.llmEngine).thenReturn("groq")
        whenever(config.groqApiKey).thenReturn("synthetic-probe")
        whenever(config.groqLlmModel).thenReturn("synthetic-model")
        whenever(config.outputStyle).thenReturn("normal")
        whenever(config.hasCloudProcessingConsent).thenReturn(true)
        val transport = OkHttpClient.Builder().addInterceptor { chain ->
            val json = JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop").put("message", JSONObject().put("content", reply))))
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                .code(200).message("OK").body(json.toString().toResponseBody("application/json".toMediaType())).build()
        }.build()
        val result = LlmClient(config, transport) {
            aliases ?: com.shingihou.sghvoice.processing.DictionaryManager.builtInSpellingAliases()
        }.refineDictation(source)
        println("SOURCE=$source CANDIDATE=$reply STATUS=${result.status}")
        assertEquals(source, expected, result.status)
        assertEquals(if (expected == LlmClient.RefinementStatus.APPLIED) reply else source, result.text)
    }

    @Test fun `opposite buy sell meaning must not be applied`() = check(
        "我明天要買股票，請先整理資料。", "我明天要賣股票，請先整理資料。", LlmClient.RefinementStatus.REJECTED)
    @Test fun `bare Chinese name must not be changed`() = check(
        "請把合約交給林紀全，明天再確認。", "請把合約交給林紀泉，明天再確認。", LlmClient.RefinementStatus.REJECTED)
    @Test fun `bare English surname must not be changed`() = check(
        "Please send the report to John Carter tomorrow.", "Please send the report to John Porter tomorrow.", LlmClient.RefinementStatus.REJECTED)
    @Test fun `negation must not move to another clause`() = check(
        "我不買股票，我賣債券。", "我買股票，我不賣債券。", LlmClient.RefinementStatus.REJECTED)
    @Test fun `home context must not be corrupted`() = check(
        "我今天在家裡休息，明天再處理。", "我今天再加裡休息，明天再處理。", LlmClient.RefinementStatus.REJECTED)
    @Test fun `titled name remains protected`() = check(
        "請把合約交給林經理，明天再確認。", "請把合約交給黃經理，明天再確認。", LlmClient.RefinementStatus.REJECTED)
    @Test fun `Chinese negative amount remains protected`() = check(
        "今天氣溫零下五度，明天再確認。", "今天氣溫五度，明天再確認。", LlmClient.RefinementStatus.REJECTED)
    @Test fun `punctuation only cleanup stays usable`() = check(
        "今天先整理資料明天再確認", "今天先整理資料，明天再確認。", LlmClient.RefinementStatus.APPLIED)
    @Test fun `consonant resemblance is not evidence of a known spelling`() = check(
        "コトランでテストを書きます。", "Kotlin でテストを書きます。", LlmClient.RefinementStatus.REJECTED)
    @Test fun `learned kana to English alias cannot replace inside a longer word`() = check(
        "バスケットを買います。", "Pathケットを買います。", LlmClient.RefinementStatus.REJECTED,
        mapOf("バス" to "Path"))
    @Test fun `learned Han to English alias cannot replace inside a longer word`() = check(
        "今天午餐有可樂餅。", "今天午餐有Claude餅。", LlmClient.RefinementStatus.REJECTED,
        mapOf("可樂" to "Claude"))
    @Test fun `different CJK scripts do not prove a word boundary`() = check(
        "バス停で待ちます。", "Path停で待ちます。", LlmClient.RefinementStatus.REJECTED,
        mapOf("バス" to "Path"))
    @Test fun `curated loanwords also require a complete CJK span`() = check(
        "コトリンでテストを書きます。", "Kotlin でテストを書きます。", LlmClient.RefinementStatus.REJECTED)
    @Test fun `confirmed alias with an explicit boundary remains useful`() = check(
        "請檢查「吉他哈布」的設定。", "請檢查 GitHub 的設定。", LlmClient.RefinementStatus.APPLIED,
        mapOf("吉他哈布" to "GitHub"))
}
