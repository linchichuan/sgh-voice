package com.shingihou.sghvoice.api

import com.shingihou.sghvoice.processing.TextCorrectionEngine
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

/**
 * Gaps 1 and 2 found by the 05 acceptance probe, as formal tests on the real
 * request -> parse -> guard path (only HTTP is synthetic). Literal expectations only.
 */
class DictationGuardGapsTest {
    private val config = mock<ApiConfig>().also {
        whenever(it.llmEngine).thenReturn("groq")
        whenever(it.groqApiKey).thenReturn("synthetic-test-key")
        whenever(it.groqLlmModel).thenReturn("test-model")
        whenever(it.outputStyle).thenReturn("normal")
        whenever(it.hasCloudProcessingConsent).thenReturn(true)
    }

    private fun refine(source: String, reply: String, vocabulary: List<String> = emptyList()) = runBlocking {
        LlmClient(config, OkHttpClient.Builder().addInterceptor { chain ->
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200).message("OK")
                .body(JSONObject().put("choices", JSONArray().put(JSONObject().put("finish_reason", "stop")
                    .put("message", JSONObject().put("content", reply)))).toString()
                    .toResponseBody("application/json".toMediaType())).build()
        }.build()).refineDictation(source, vocabularyHint = JSONArray(vocabulary).toString())
    }

    private fun assertApplied(source: String, reply: String, vocabulary: List<String> = emptyList()) {
        val result = refine(source, reply, vocabulary)
        assertEquals("$source -> $reply", LlmClient.RefinementStatus.APPLIED, result.status)
        assertEquals(reply, result.text)
    }

    private fun assertRejected(source: String, reply: String, vocabulary: List<String> = emptyList()) {
        val result = refine(source, reply, vocabulary)
        assertEquals("$source -> $reply", LlmClient.RefinementStatus.REJECTED, result.status)
        assertEquals(source, result.text)
    }

    // ---- Gap 1: a real katakana word must not become an unrelated known term ----

    @Test fun `katakana real words are not replaced by unrelated known terms`() {
        assertRejected("データベースの設定を確認して。", "GitHubの設定を確認して。", listOf("GitHub"))
        assertRejected("サーバーの設定を確認して。", "Kotlinの設定を確認して。", listOf("Kotlin"))
    }

    @Test fun `katakana spelling of the same word may become the English term`() {
        assertApplied("コトリン でテストを書きます。", "Kotlin でテストを書きます。", listOf("Kotlin"))
        assertApplied("ギットハブ を確認します。", "GitHub を確認します。", listOf("GitHub"))
        assertApplied("GitHub アクションズ を確認します。", "GitHub Actions を確認します。", listOf("GitHub Actions"))
    }

    // ---- Gap 2: a person's name next to a title is protected ----

    @Test fun `a name next to a title cannot be replaced or deleted`() {
        assertRejected("請在十月五號前交給林先生。", "請在十月五號前交給王先生。")
        assertRejected("請在十月五號前交給林先生。", "請在十月五號前交給先生。")
        assertRejected("明天跟陳小姐開會。", "明天跟程小姐開會。")
        assertRejected("田中さんに資料を送ります。", "佐藤さんに資料を送ります。")
        assertRejected("Please send it to Mr. Lin today.", "Please send it to Mr. Wang today.")
        assertRejected("Please send it to Dr. Smith today.", "Please send it to Dr. today.")
    }

    @Test fun `a name next to a job title cannot be replaced`() {
        assertRejected("報告請寄給林經理。", "報告請寄給黃經理。")
        assertRejected("明日田中部長と打ち合わせです。", "明日中田部長と打ち合わせです。")
        assertRejected("鈴木社長に確認します。", "佐々木社長に確認します。")
        assertRejected("山口課長から連絡がありました。", "川口課長から連絡がありました。")
        assertRejected("這份文件給吳主任看。", "這份文件給胡主任看。")
        assertRejected("合約已經寄給周律師。", "合約已經寄給鄒律師。")
        assertRejected("剛剛王總打電話來。", "剛剛汪總打電話來。")
    }

    @Test fun `job titles keep ordinary cleanup and common words with 總 working`() {
        assertApplied("嗯報告請寄給林經理", "報告請寄給林經理。")
        assertApplied("我們總是先跑 CI 再 git push", "我們總是先跑 CI 再 git push。")
    }

    @Test fun `names survive ordinary cleanup and a known alias may fix a name`() {
        assertApplied("請在十月五號前交給林先生", "請在十月五號前交給林先生。")
        assertApplied("田中さん、資料を送ります", "田中さん、資料を送ります。")
        // 林紀泉 -> 林紀全 is a built-in known mishearing alias.
        assertApplied("請把文件交給「林紀泉」先生。", "請把文件交給「林紀全」先生。")
    }

    @Test fun `dictionary corrections cannot change a name next to a title`() {
        assertEquals("請交給林先生。", TextCorrectionEngine.apply("請交給林先生。", mapOf("林先生" to "王先生")))
        assertEquals("田中さんに送る。", TextCorrectionEngine.apply("田中さんに送る。", mapOf("田中さん" to "佐藤さん")))
    }
}
