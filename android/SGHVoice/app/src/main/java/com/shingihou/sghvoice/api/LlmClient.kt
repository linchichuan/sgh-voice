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
 * 通用 LLM 客戶端
 * 支援 Anthropic Claude, OpenAI GPT, 以及 Groq (OpenAI 相容)
 */
class LlmClient(private val apiConfig: ApiConfig) {

    companion object {
        private const val CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
        private const val OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
        private const val GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
        
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
        
        // 系統提示詞
        private const val BASE_PROMPT = "語音辨識後處理。規則：\n1. 刪除填充詞：嗯、啊、那個、就是、えー特、あの、um、uh、like\n2. 口語自我修正→只保留最終版本\n3. 標點符號：加上正確標點，適當分段\n4. 不改寫核心句意，保持原語言（中/日/英混合保持原樣）\n5. 只輸出結果，不加解釋\n6. 所有中文必須是繁體中文\n"
        
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
     */
    suspend fun postProcess(text: String, sceneExtra: String = ""): String {
        if (text.isBlank()) return text
        if (apiConfig.llmEngine == "none") return text

        // 短文本且無填充詞 → 跳過 LLM 處理
        if (text.length <= SHORT_TEXT_THRESHOLD && !containsFillerWords(text)) {
            return text
        }

        // 決定提示詞
        var systemPrompt = when (apiConfig.outputStyle) {
            "line" -> LINE_PROMPT
            "email" -> EMAIL_PROMPT
            else -> NORMAL_PROMPT
        }
        if (sceneExtra.isNotBlank()) {
            systemPrompt = "$systemPrompt\n$sceneExtra"
        }

        val engine = apiConfig.llmEngine
        return when (engine) {
            "claude" -> processClaude(text, systemPrompt)
            "openai" -> processOpenAiLike(text, systemPrompt, OPENAI_API_URL, apiConfig.openAiApiKey, "gpt-4o")
            "groq" -> processOpenAiLike(text, systemPrompt, GROQ_API_URL, apiConfig.groqApiKey, ApiConfig.DEFAULT_GROQ_LLM_MODEL)
            else -> text
        }
    }

    private suspend fun processClaude(text: String, systemPrompt: String): String {
        val apiKey = apiConfig.anthropicApiKey
        if (apiKey.isBlank()) return text

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
                .post(requestJson.toString().toRequestBody("application/json".toMediaType()))
                .build()

            executeRequest(request) { json ->
                val content = json.getJSONArray("content")
                if (content.length() > 0) content.getJSONObject(0).getString("text").trim() else text
            }
        }
    }

    private suspend fun processOpenAiLike(text: String, systemPrompt: String, url: String, apiKey: String, model: String): String {
        if (apiKey.isBlank()) return text

        return withContext(Dispatchers.IO) {
            val requestJson = JSONObject().apply {
                put("model", model)
                put("messages", JSONArray().apply {
                    put(JSONObject().apply {
                        put("role", "system")
                        put("content", systemPrompt)
                    })
                    put(JSONObject().apply {
                        put("role", "user")
                        put("content", text)
                    })
                })
                put("temperature", 0.0)
            }

            val request = Request.Builder()
                .url(url)
                .header("Authorization", "Bearer $apiKey")
                .post(requestJson.toString().toRequestBody("application/json".toMediaType()))
                .build()

            executeRequest(request) { json ->
                val choices = json.getJSONArray("choices")
                if (choices.length() > 0) {
                    choices.getJSONObject(0).getJSONObject("message").getString("content").trim()
                } else text
            }
        }
    }

    private suspend fun executeRequest(request: Request, parser: (JSONObject) -> String): String {
        return try {
            val response = httpClient.awaitCall(request)
            val body = response.body?.string() ?: return ""
            if (!response.isSuccessful) return ""
            parser(JSONObject(body))
        } catch (e: Exception) {
            ""
        }
    }

    private fun containsFillerWords(text: String): Boolean {
        val lowerText = text.lowercase()
        return FILLER_WORDS.any { filler -> lowerText.contains(filler.lowercase()) }
    }

    fun shutdown() {
        httpClient.dispatcher.executorService.shutdown()
        httpClient.connectionPool.evictAll()
    }
}

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
                    continuation.resumeWithException(e)
                }
            }
        })
    }
}
