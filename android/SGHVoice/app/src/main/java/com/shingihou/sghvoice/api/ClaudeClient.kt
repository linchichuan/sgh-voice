package com.shingihou.sghvoice.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resumeWithException

/**
 * Anthropic Claude API 客戶端
 * 語音辨識後處理：去填充詞、修正標點、保持三語混合
 */
class ClaudeClient(private val apiConfig: ApiConfig) {

    companion object {
        private const val CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
        private const val ANTHROPIC_VERSION = "2023-06-01"
        private const val TIMEOUT_SECONDS = 30L
        private const val MAX_TOKENS = 1024

        // 短文本門檻：20 字以下且無填充詞時跳過 LLM 處理
        private const val SHORT_TEXT_THRESHOLD = 20

        // 填充詞清單（中/日/英三語）
        private val FILLER_WORDS = listOf(
            "嗯", "啊", "那個", "就是", "然後", "對啊", "就是說",
            "えーと", "あの", "えー", "まあ", "その",
            "um", "uh", "like", "you know", "well", "so"
        )
        
        // 系統提示詞：語音辨識後處理規則 (分場合)
        private const val BASE_PROMPT = "語音辨識後處理。規則：\n1. 刪除填充詞：嗯、啊、那個、就是、えーと、あの、um、uh、like\n2. 口語自我修正→只保留最終版本\n3. 標點符號：加上正確標點，適當分段\n4. 不改寫核心句意，保持原語言（中/日/英混合保持原樣）\n5. 只輸出結果，不加解釋\n6. 所有中文必須是繁體中文\n"
        
        private const val LINE_PROMPT = BASE_PROMPT + "7. 語氣設定為【LINE 訊息】：文字精簡、口語自然，不要過於死板。"
        private const val EMAIL_PROMPT = BASE_PROMPT + "7. 語氣設定為【正式 Email】：文字得體、結構嚴謹且專業。"
        private const val NORMAL_PROMPT = BASE_PROMPT + "7. 語氣設定為【一般文字】：語氣中立，字句稍微順過即可。"
    }

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .build()

    /**
     * 對語音辨識結果進行後處理
     * 短文本（≤20 字且無填充詞）會跳過 LLM 處理直接回傳
     *
     * @param text Whisper 辨識後的原始文字
     * @return 後處理後的文字
     * @throws ClaudeException 當 API 呼叫失敗時拋出
     */
    suspend fun postProcess(text: String): String {
        // 空白文字直接回傳
        if (text.isBlank()) return text

        // 短文本且無填充詞 → 跳過 LLM 處理
        if (text.length <= SHORT_TEXT_THRESHOLD && !containsFillerWords(text)) {
            return text
        }

        val apiKey = apiConfig.anthropicApiKey
        // 完全離線模式（沒有 API Key 時直接回傳修正過自訂詞彙的原文）
        if (apiKey.isBlank()) {
            return text
        }

        // 決定提示詞（根據設定的轉換風格）
        val systemPrompt = when (apiConfig.outputStyle) {
            "line" -> LINE_PROMPT
            "email" -> EMAIL_PROMPT
            else -> NORMAL_PROMPT
        }

        return withContext(Dispatchers.IO) {
            val requestJson = JSONObject().apply {
                put("model", apiConfig.claudeModel)
                put("max_tokens", MAX_TOKENS)
                put("system", systemPrompt)
                put("messages", JSONArray().apply {
                    put(JSONObject().apply {
                        put("role", "user")
                        put("content", text)
                    })
                })
            }

            val request = Request.Builder()
                .url(CLAUDE_API_URL)
                .header("x-api-key", apiKey)
                .header("anthropic-version", ANTHROPIC_VERSION)
                .header("content-type", "application/json")
                .post(requestJson.toString().toRequestBody("application/json".toMediaType()))
                .build()

            val response = try {
                httpClient.awaitCall(request)
            } catch (e: Exception) {
                // 完全離線保護或網路錯誤：直接返回原文
                return@withContext text
            }
            
            val body = response.body?.string()
                ?: throw ClaudeException("Claude API returned empty response")

            if (!response.isSuccessful) {
                // 回應有錯誤，為了讓輸入法不要崩潰可以直接返回原文
                return@withContext text
            }

            try {
                val json = JSONObject(body)
                val content = json.getJSONArray("content")
                if (content.length() > 0) {
                    content.getJSONObject(0).getString("text").trim()
                } else {
                    text // Return original text if no content is found
                }
            } catch (e: Exception) {
                // 解析錯誤時直接返回原文
                return@withContext text
            }
        }
    }

    /**
     * 檢查文字中是否包含填充詞
     */
    private fun containsFillerWords(text: String): Boolean {
        val lowerText = text.lowercase()
        return FILLER_WORDS.any { filler ->
            lowerText.contains(filler.lowercase())
        }
    }

    /** 關閉 HTTP 客戶端連線池 */
    fun shutdown() {
        httpClient.dispatcher.executorService.shutdown()
        httpClient.connectionPool.evictAll()
    }
}

/**
 * OkHttp Call 的協程擴充函式（Claude 專用）
 */
private suspend fun OkHttpClient.awaitCall(request: Request): Response {
    return suspendCancellableCoroutine { continuation ->
        val call = newCall(request)
        continuation.invokeOnCancellation { call.cancel() }

        call.enqueue(object : Callback {
            override fun onResponse(call: Call, response: Response) {
                continuation.resumeWith(Result.success(response))
            }

            override fun onFailure(call: Call, e: IOException) {
                if (!continuation.isCancelled) {
                    continuation.resumeWithException(
                        ClaudeException("Network error: ${e.message}")
                    )
                }
            }
        })
    }
}

/** Claude API 例外類別 */
class ClaudeException(message: String, cause: Throwable? = null) : Exception(message, cause)
