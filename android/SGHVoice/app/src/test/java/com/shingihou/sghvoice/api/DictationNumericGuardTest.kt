package com.shingihou.sghvoice.api

import com.shingihou.sghvoice.processing.NumericFacts
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
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * 2026-10-03 acceptance (07) numeric/sign gaps. Every case goes through the real
 * request -> parse -> validateLlmResult path; only the HTTP transport is synthetic.
 * Expected values are literals, never derived from the code under test.
 */
class DictationNumericGuardTest {
    private val config = mock<ApiConfig>().also {
        whenever(it.llmEngine).thenReturn("groq")
        whenever(it.groqApiKey).thenReturn("synthetic-test-key")
        whenever(it.groqLlmModel).thenReturn("test-model")
        whenever(it.outputStyle).thenReturn("normal")
        whenever(it.hasCloudProcessingConsent).thenReturn(true)
    }

    private fun refine(source: String, reply: String) = runBlocking {
        val transport = OkHttpClient.Builder().addInterceptor { chain ->
            val response = JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop")
                .put("message", JSONObject().put("content", reply))))
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                .code(200).message("OK")
                .body(response.toString().toResponseBody("application/json".toMediaType())).build()
        }.build()
        LlmClient(config, transport) { emptyMap() }.refineDictation(source, vocabularyHint = "[]")
    }

    private fun assertApplied(source: String, reply: String) {
        val result = refine(source, reply)
        assertEquals("$source -> $reply", LlmClient.RefinementStatus.APPLIED, result.status)
        assertEquals(reply, result.text)
    }

    private fun assertRejected(source: String, reply: String) {
        val result = refine(source, reply)
        assertEquals("$source -> $reply", LlmClient.RefinementStatus.REJECTED, result.status)
        assertEquals(source, result.text)
    }

    // ---- 07-probe failures (were APPLIED) ----

    @Test fun `B4 dropped 負 sign is rejected`() = assertRejected("明天氣溫負五度。", "明天氣溫五度。")
    @Test fun `B4c dropped minus before 萬 amount is rejected`() = assertRejected("損益是 -300 萬。", "損益是 300 萬。")
    @Test fun `E1 changed Chinese numeral after 負 is rejected`() = assertRejected("明天氣溫負五度。", "明天氣溫負六度。")
    @Test fun `E2 dropped ASCII minus before 度 is rejected`() = assertRejected("明天氣溫 -5 度。", "明天氣溫 5 度。")
    @Test fun `E3 dropped 零下 is rejected`() = assertRejected("明天氣溫零下五度。", "明天氣溫五度。")
    @Test fun `E5 三公里 to 五公里 is rejected`() = assertRejected("距離大概三公里。", "距離大概五公里。")
    @Test fun `E6 七十公斤 to 七十五公斤 is rejected`() = assertRejected("體重七十公斤。", "體重七十五公斤。")
    @Test fun `E9 dropped minus before dollars is rejected`() =
        assertRejected("The balance is -200 dollars.", "The balance is 200 dollars.")
    @Test fun `E10 dropped マイナス is rejected`() = assertRejected("気温はマイナス五度です。", "気温は五度です。")

    // ---- 07-probe cases that were already rejected stay rejected ----

    @Test fun `already rejected numeric cases stay rejected`() {
        assertRejected("損益是 -300 萬。", "損益是 -500 萬。")
        assertRejected("The distance is 3 km.", "The distance is 5 km.")
        assertRejected("利潤 -5%。", "利潤 5%。")
        assertRejected("The invoice is 1,200 dollars.", "The invoice is 1,500 dollars.")
        assertRejected("預算是三萬日圓，不要超過。", "預算是五萬日圓，不要超過。")
    }

    // ---- additional numeric forms ----

    @Test fun `other value and sign changes are rejected`() {
        assertRejected("預算是三千兩百元。", "預算是三千五百元。")
        assertRejected("預算大概一萬五。", "預算大概一萬。")
        assertRejected("我們二〇二六年出貨。", "我們2027年出貨。")
        assertRejected("目標是減三公斤。", "目標是三公斤。")
        assertRejected("The change is minus 5 percent.", "The change is 5 percent.")
        assertRejected("成長是百分之五。", "成長是6%。")
        assertRejected("明天氣溫負五度。", "明天氣溫-6度。")
        assertRejected("気温はプラス五度です。", "気温はマイナス五度です。")
    }

    // ---- positive controls: correct cleanups must still be applied ----

    @Test fun `Chinese numeral to Arabic with the same value is applied`() {
        assertApplied("距離大概三公里。", "距離大概3公里。")
        assertApplied("我們二〇二六年三月出貨", "我們2026年3月出貨。")
        assertApplied("體重七十五公斤。", "體重75公斤。")
        assertApplied("明天氣溫負五度。", "明天氣溫-5度。")
    }

    @Test fun `filler removal and punctuation with unchanged numbers is applied`() {
        assertApplied("嗯我們明天要去開會然後討論一下預算", "我們明天要去開會，然後討論一下預算。")
        assertApplied("嗯預算大概是三萬五千元然後禮拜二交", "預算大概是三萬五千元，然後禮拜二交。")
        assertApplied("明天氣溫負五度", "明天氣溫負五度。")
        assertApplied("損益是 -300 萬", "損益是 -300 萬。")
    }

    // The owner chose retaining uncertain content over guessing what is a filler.
    // 那個 may identify a specific budget; 就是 may express emphasis, not hesitation.
    @Test fun `ambiguous discourse word deletion keeps original content`() {
        assertRejected("嗯那個我們明天就是要去開會然後討論一下預算", "我們明天要去開會，然後討論一下預算。")
        assertRejected("嗯那個預算大概是三萬五千元然後禮拜二交", "預算大概是三萬五千元，然後禮拜二交。")
    }

    @Test fun `spoken ordinal points become a numbered list`() {
        assertApplied("第一點準備報價單第二點寄給客戶", "1. 準備報價單\n2. 寄給客戶")
    }

    @Test fun `explicit numeric self correction is still applied`() {
        assertApplied("我們三點，不對，四點開會", "我們四點開會。")
    }

    // ---- extractor unit checks (literal expectations) ----

    @Test fun `extractor reads sign value and unit`() {
        assertEquals(listOf("-|5|度"), NumericFacts.extract("明天氣溫負五度").map { it.toString() })
        assertEquals(listOf("-|5|度"), NumericFacts.extract("明天氣溫零下五度").map { it.toString() })
        assertEquals(listOf("-|5|度"), NumericFacts.extract("気温はマイナス五度").map { it.toString() })
        assertEquals(listOf("-|3000000|"), NumericFacts.extract("損益是 -300 萬").map { it.toString() })
        assertEquals(listOf("|3200|元"), NumericFacts.extract("三千兩百元").map { it.toString() })
        assertEquals(listOf("|15000|"), NumericFacts.extract("一萬五").map { it.toString() })
        assertEquals(listOf("|2026|年", "|3|月"), NumericFacts.extract("二〇二六年三月").map { it.toString() })
        assertEquals(listOf("|1200|dollar"), NumericFacts.extract("1,200 dollars").map { it.toString() })
        assertEquals(listOf("|5|%"), NumericFacts.extract("百分之五").map { it.toString() })
        // Ordinals and idioms are not quantities.
        assertEquals(emptyList<String>(), NumericFacts.extract("第一點準備，討論一下，一起去").map { it.toString() })
    }

    // ---- dictionary side uses the same extractor ----

    @Test fun `dictionary rules may not delete a sign word or change a numeric fact`() {
        assertEquals("気温はマイナス五度", TextCorrectionEngine.apply("気温はマイナス五度", mapOf("マイナス" to "")))
        assertEquals("明天零下五度", TextCorrectionEngine.apply("明天零下五度", mapOf("零下" to "")))
        assertEquals("明天零下五度", TextCorrectionEngine.apply("明天零下五度", mapOf("下五" to "上五")))
        assertTrue(NumericFacts.sameFacts("三公里", "3公里"))
        assertFalse(NumericFacts.sameFacts("負五度", "五度"))
        // Spelling-only rules still apply next to numbers.
        assertEquals("預算三萬日圓用 GitHub", TextCorrectionEngine.apply("預算三萬日圓用 Git Hub", mapOf("Git Hub" to "GitHub")))
    }
}
