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

        // 系統提示詞：語音辨識後處理規則
        private const val SYSTEM_PROMPT = """語音辨識後處理。規則：
1. 刪除填充詞：嗯、啊、那個、就是、えーと、あの、um、uh、like
2. 口語自我修正→只保留最終版本
3. 標點符號：加上正確標點，適當分段
4. 不改寫核心句意，保持原語言（中/日/英混合保持原樣）
5. 只輸出結果，不加解釋
6. 所有中文必須是繁體中文"""
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
        if (apiKey.isBlank()) {
            // API 金鑰未設定時直接回傳原文（降級處理）
            return text
        }

        return withContext(Dispatchers.IO) {
            val requestJson = JSONObject().apply {
                put("model", apiConfig.claudeModel)
                put("max_tokens", MAX_TOKENS)
                put("system", SYSTEM_PROMPT)
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

            val response = httpClient.awaitCall(request)
            val body = response.body?.string()
                ?: throw ClaudeException("Claude API 回傳空白回應")

            if (!response.isSuccessful) {
                val errorMsg = try {
                    val errorJson = JSONObject(body)
                    errorJson.optJSONObject("error")?.optString("message")
                        ?: "HTTP ${response.code}"
                } catch (_: Exception) {
                    "HTTP ${response.code}: $body"
                }
                throw ClaudeException("Claude API 錯誤：$errorMsg")
            }

            try {
                val json = JSONObject(body)
                val content = json.getJSONArray("content")
                if (content.length() > 0) {
                    content.getJSONObject(0).getString("text").trim()
                } else {
                    text // 無回應時回傳原文
                }
            } catch (e: Exception) {
                throw ClaudeException("無法解析 Claude 回應：${e.message}")
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
                        ClaudeException("網路連線失敗：${e.message}")
                    )
                }
            }
        })
    }
}

/** Claude API 例外類別 */
class ClaudeException(message: String, cause: Throwable? = null) : Exception(message, cause)
