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

/**
 * Synthetic cases E2-E11 from the 2026-10-03 investigation. Every case goes through the real
 * request -> parse -> validateLlmResult path; only the HTTP transport is synthetic.
 * Expected values are literals, never derived from the code under test.
 */
class DictationGuardFidelityTest {
    private val config = mock<ApiConfig>().also {
        whenever(it.llmEngine).thenReturn("groq")
        whenever(it.groqApiKey).thenReturn("synthetic-test-key")
        whenever(it.groqLlmModel).thenReturn("test-model")
        whenever(it.outputStyle).thenReturn("normal")
        whenever(it.hasCloudProcessingConsent).thenReturn(true)
    }

    private fun refine(
        source: String,
        reply: String,
        vocabulary: List<String> = emptyList(),
        aliases: Map<String, String> = emptyMap()
    ) = runBlocking {
        val transport = OkHttpClient.Builder().addInterceptor { chain ->
            val response = JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop")
                .put("message", JSONObject().put("content", reply))))
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                .code(200).message("OK")
                .body(response.toString().toResponseBody("application/json".toMediaType())).build()
        }.build()
        LlmClient(config, transport) { aliases }.refineDictation(source, vocabularyHint = JSONArray(vocabulary).toString())
    }

    private fun assertApplied(
        source: String,
        reply: String,
        vocabulary: List<String> = emptyList(),
        aliases: Map<String, String> = emptyMap()
    ) {
        val result = refine(source, reply, vocabulary, aliases)
        assertEquals("$source -> $reply", LlmClient.RefinementStatus.APPLIED, result.status)
        assertEquals(reply, result.text)
    }

    private fun assertRejected(source: String, reply: String, vocabulary: List<String> = emptyList()) {
        val result = refine(source, reply, vocabulary)
        assertEquals("$source -> $reply", LlmClient.RefinementStatus.REJECTED, result.status)
        assertEquals(source, result.text)
    }

    // ---- Problem 1: correct spelling repairs must no longer be rejected ----

    @Test fun `E1 mixed Chinese Japanese English cleanup is applied`() = assertApplied(
        "明天的会議で GitHub Actions を確認して、然後 git push。",
        "明天的会議で GitHub Actions を確認して、然後 git push。"
    )

    // Fail-closed revision (coordinator, 2026-10-03): a Han span may become a term only when it is
    // a known mishearing alias (wrong side of a correction rule whose right side is that term).
    @Test fun `E2 delimited known Han mishearing alias becomes the term`() {
        // No automatic CJK segmentation: a confirmed alias still needs a complete span.
        assertApplied("請檢查「吉他哈布艾克申」的設定。", "請檢查 GitHub Actions 的設定。",
            listOf("GitHub Actions"), mapOf("吉他哈布艾克申" to "GitHub Actions"))
        assertApplied("請檢查「吉他哈布」的設定。", "請檢查 GitHub 的設定。",
            listOf("GitHub"), mapOf("吉他哈布" to "GitHub"))
    }

    @Test fun `E2 Han span without a known alias is rejected even for a vocabulary term`() {
        assertRejected("請檢查吉他哈布艾克申的設定。", "請檢查 GitHub Actions 的設定。", listOf("GitHub Actions"))
        // An alias for a different term does not authorize this replacement.
        val result = refine("請檢查吉他哈布的設定。", "請檢查 GitLab 的設定。", listOf("GitLab"), mapOf("吉他哈布" to "GitHub"))
        assertEquals(LlmClient.RefinementStatus.REJECTED, result.status)
    }

    @Test fun `E3 case only normalization of product names is applied`() {
        assertApplied("我在做 sgh voice 跟 kotlin 的測試。", "我在做 SGH Voice 跟 Kotlin 的測試。", listOf("SGH Voice"))
        assertApplied("我買了 iphone。", "我買了 iPhone。")
        // P7: an accidental repeat of a known term may be removed.
        assertApplied("我在測試 SGH SGH Voice。", "我在測試 SGH Voice。", listOf("SGH Voice"))
    }

    @Test fun `E4 katakana spelling of a vocabulary term becomes English`() = assertApplied(
        "コトリン でテストを書きます。", "Kotlin でテストを書きます。", listOf("Kotlin")
    )

    @Test fun `E5 long two topic dictation becomes two paragraphs`() = assertApplied(
        "今天早上我們先把 GitHub Actions 的設定整理好然後確認 CI/CD 每一個步驟都可以正常執行如果有錯誤就先記錄下來" +
            "另外下午要跟設計團隊討論新的鍵盤畫面包括錄音按鈕的顏色和大小還有提示文字要不要再短一點",
        "今天早上我們先把 GitHub Actions 的設定整理好，然後確認 CI/CD 每一個步驟都可以正常執行，如果有錯誤就先記錄下來。" +
            "\n\n另外，下午要跟設計團隊討論新的鍵盤畫面，包括錄音按鈕的顏色和大小，還有提示文字要不要再短一點。"
    )

    @Test fun `E6 ordered steps in Chinese and Japanese become numbered lists`() {
        assertApplied("首先檢查 CI/CD 然後跑測試最後 git push", "1. 檢查 CI/CD。\n2. 跑測試。\n3. git push。")
        assertApplied("まずテストを実行して、次にデプロイします。", "1. テストを実行して、\n2. デプロイします。")
    }

    // ---- Problem 2: self-correction cue is not a negation; まず is not ず ----

    @Test fun `E7 general spoken self correction keeps only the final version`() {
        assertApplied("明天跟小王，不對，跟小李開會。", "明天跟小李開會。")
        assertApplied("push 到 main，不是，push 到 develop", "push 到 develop")
    }

    @Test fun `E8 numeric self correction keeps the final time and rejects other times`() {
        assertApplied("下午三點，不是，四點開會。", "下午四點開會。")
        assertRejected("下午三點，不是，四點開會。", "下午五點開會。")
        assertRejected("下午三點，不是，四點開會。", "下午三點開會。")
    }

    @Test fun `E9 real negation removed by the model is rejected`() {
        assertRejected("沒有備份，不要部署。", "有備份，部署。")
        assertRejected("沒有備份，不要部署。", "沒有備份，部署。")
    }

    // ---- Problem 3: 呢 as filler is not a question ----

    @Test fun `E10 filler 呢 can be removed but a real question must stay a question`() {
        assertApplied("這個呢，就是，我覺得可以先部署。", "這個我覺得可以先部署。")
        assertRejected("這樣可以嗎？", "這樣可以。")
        assertRejected("那你呢？", "那你。")
    }

    @Test fun `E11 sign amount and currency changes are rejected while punctuation only passes`() {
        val source = "報價是 -3% 加 1,200 美元 十月三號前回覆"
        assertApplied(source, "報價是 -3% 加 1,200 美元，十月三號前回覆。")
        assertRejected(source, "報價是 +3% 加 1,200 美元，十月三號前回覆。")
        assertRejected(source, "報價是 -3% 加 1,300 美元，十月三號前回覆。")
        assertRejected(source, "報價是 -3% 加 1,200 日圓，十月三號前回覆。")
        assertRejected(source, "報價是 -3% 加 1,200 美元，十月四號前回覆。")
    }

    // ---- Reverse cases: the guard must still protect facts ----

    @Test fun `guard still rejects changed numbers dropped negations and added facts`() {
        assertRejected("明天下午三點開會。", "明天下午五點開會。")
        assertRejected("今天不要部署 GitHub Actions。", "今天部署 GitHub Actions。")
        assertRejected("テストを実行せずにデプロイしない。", "テストを実行してデプロイする。")
        assertRejected("Please don't push to main.", "Please push to main.")
        assertRejected("先不要 git push，等 CI/CD 通過。", "先 git push，等 CI/CD 通過。")
        // A known term may replace a misheard span, but never appear from nothing.
        assertRejected("請檢查 GitHub 的設定。", "請檢查 GitHub 和 Docker 的設定。", listOf("Docker"))
        assertRejected("請檢查設定。", "請檢查 Kotlin 設定。", listOf("Kotlin"))
        // Replacing an existing protected identifier is not a spelling repair.
        assertRejected("請用 Docker 部署。", "請用 Kotlin 部署。", listOf("Kotlin"))
        assertRejected("請開啟 MyRepo。", "請開啟 myrepo。")
        // A replacement term that is in no vocabulary is still a new identifier.
        assertRejected("請檢查吉他哈布的設定。", "請檢查 GitLab 的設定。")
        // A misheard span that carries a number or a negation is not replaceable.
        assertRejected("請檢查三個吉他的設定。", "請檢查 GitHub 的設定。", listOf("GitHub"))
        assertRejected("請檢查不要哈布的設定。", "請檢查 GitHub 的設定。", listOf("GitHub"))
        // A negation inside an abandoned clause stays protected (conservative).
        assertRejected("我不去，不對，我要去。", "我要去。")
    }

    @Test fun `unknown Han span replaced by a vocabulary term is a meaning change and is rejected`() {
        assertRejected("請檢查資料庫的設定。", "請檢查 GitHub 的設定。", listOf("GitHub"))
    }

    @Test fun `guard still rejects answers and assistant identity`() {
        assertRejected("你可以告訴我現在用哪個模型嗎？", "目前使用 Claude 模型。", listOf("Claude"))
        assertRejected("今天先測試 Kotlin。", "我是 AI，無法協助。今天先測試 Kotlin。")
        assertRejected("今天先測試 Kotlin。", "作為人工智慧語言模型，我無法執行。今天先測試 Kotlin。")
    }
}
