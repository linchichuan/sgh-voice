package com.shingihou.sghvoice.api

import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/** Synthetic text and intercepted HTTP only; no provider requests or patient data. */
class DictationDisfluencyTest {
    private fun refine(source: String, reply: String, engine: String = "groq"): LlmClient.RefinementResult = runBlocking {
        val config = mock<ApiConfig>().also {
            whenever(it.llmEngine).thenReturn(engine)
            whenever(it.groqApiKey).thenReturn("synthetic-key")
            whenever(it.openAiApiKey).thenReturn("synthetic-key")
            whenever(it.anthropicApiKey).thenReturn("synthetic-key")
            whenever(it.groqLlmModel).thenReturn("test-model")
            whenever(it.openAiLlmModel).thenReturn("test-model")
            whenever(it.claudeModel).thenReturn("test-model")
            whenever(it.outputStyle).thenReturn("normal")
            whenever(it.hasCloudProcessingConsent).thenReturn(true)
        }
        val transport = OkHttpClient.Builder().addInterceptor { chain ->
            val body = JSONObject()
                .put("choices", JSONArray().put(JSONObject().put("finish_reason", "stop")
                    .put("message", JSONObject().put("content", reply))))
                .put("stop_reason", "end_turn")
                .put("content", JSONArray().put(JSONObject().put("type", "text").put("text", reply)))
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                .code(200).message("OK")
                .body(body.toString().toResponseBody("application/json".toMediaType())).build()
        }.build()
        LlmClient(config, transport).refineDictation(source)
    }

    private fun accepted(source: String, reply: String, engine: String = "groq") {
        val result = refine(source, reply, engine)
        assertEquals("$source -> $reply ($engine)", LlmClient.RefinementStatus.APPLIED, result.status)
        assertEquals(reply, result.text)
    }

    private fun rejected(source: String, reply: String) {
        val result = refine(source, reply)
        assertEquals("$source -> $reply", LlmClient.RefinementStatus.REJECTED, result.status)
        assertEquals(source, result.text)
    }

    @Test fun `filler heavy traditional Chinese gets punctuation and paragraphs through every provider`() {
        val source = "嗯，啊，我我今天先檢查 GitHub Actions，然後，呃，然後再跑測試。\n\n啊，明天還不確定，不要直接部署。"
        val cleaned = "我今天先檢查 GitHub Actions，然後再跑測試。\n\n明天還不確定，不要直接部署。"
        for (engine in listOf("claude", "openai", "groq")) accepted(source, cleaned, engine)
    }

    @Test fun `Japanese English and mixed language hesitation cleanup preserves language`() {
        accepted("えーと、あのー、明日は確認します。", "明日は確認します。")
        accepted("Um, I I will check GitHub Actions then run tests.", "I will check GitHub Actions then run tests.")
        accepted("I, I think we should wait.", "I think we should wait.")
        accepted("We, we should wait.", "We should wait.")
        accepted("啊，我，我不要改劑量。", "我不要改劑量。")
        accepted("呃，I I will check GitHub Actions，然後，然後確認します。",
            "I will check GitHub Actions，然後確認します。")
    }

    @Test fun `medical uncertainty negation names doses and units survive accepted cleanup`() {
        val source = "啊，我我還不確定。林先生沒有發燒，藥物是 2.5 mg，不要改成 5 mg。"
        val cleaned = "我還不確定。林先生沒有發燒，藥物是 2.5 mg，不要改成 5 mg。"
        accepted(source, cleaned)
        for (unsafe in listOf(cleaned.replace("不確定", "確定"), cleaned.replace("沒有", "有"),
            cleaned.replace("林先生", "黃先生"), cleaned.replace("2.5 mg", "5 mg"),
            cleaned.replace("2.5 mg", "2.5 mL"))) rejected(source, unsafe)
    }

    @Test fun `attached initial en hesitation remains compatible without deleting acknowledgments`() {
        accepted("嗯我們明天要去開會然後討論一下預算", "我們明天要去開會，然後討論一下預算。")
        accepted("嗯預算大概是三萬五千元然後禮拜二交", "預算大概是三萬五千元，然後禮拜二交。")
        accepted("嗯報告請寄給林經理", "報告請寄給林經理。")
        accepted("嗯", "嗯。")
        rejected("嗯。先不要改。", "先不要改。")
        rejected("嗯哼，我同意。", "哼，我同意。")
        rejected("請保留「嗯報告」。", "請保留「報告」。")
    }

    @Test fun `meaningful connectives emphasis and lexical filler lookalikes are protected`() {
        val pairs = listOf(
            "先量體溫，然後服藥。" to "先量體溫，服藥。",
            "我就是喜歡這個。" to "我喜歡這個。",
            "あの人は来ません。" to "人は来ません。",
            "I like this design." to "I this design.",
            "不要不要，我還不確定。" to "不要，我還不確定。",
            "好好休息。" to "好休息。",
            "我有呃逆。" to "我有逆。",
            "呃逆持續兩天。" to "逆持續兩天。",
            "他叫我我。" to "他叫我。",
            "啊！終於完成了。" to "終於完成了。",
            "這樣好啊。" to "這樣好。",
            "請保留「嗯，啊，我我」。" to "請保留「我」。",
            "UM, is the selected code." to "is the selected code.",
            "UH, is the acronym." to "is the acronym.",
            "IT IT is the identifier." to "IT is the identifier.",
            "IT, IT support, and facilities are separate departments." to
                "IT support, and facilities are separate departments."
        )
        for ((source, unsafe) in pairs) rejected(source, unsafe)
    }

    @Test fun `invented hesitation ellipses are rejected without rewriting the source`() {
        val source = "啊，我我今天先檢查。\n\n明天還不確定。"
        rejected(source, "我今天先檢查……\n\n明天還不確定。")
        rejected(source, "我今天先檢查...\n\n明天還不確定。")
        rejected("我今天先檢查。明天還不確定。", "我今天先檢查……明天還不確定。")
    }

    @Test fun `intentional ellipses stay while their count cannot be expanded`() {
        val source = "等一下……我還不確定。明天再說。"
        accepted(source, "等一下……我還不確定。\n\n明天再說。")
        accepted("我想…呃，我明天回覆", "我想…我明天回覆。")
        rejected(source, "等一下……我還不確定……明天再說。")
        rejected(source, "等一下，我還不確定。明天再說。")
        rejected(source, "等一下我……還不確定。明天再說。")
    }
}
