package com.shingihou.sghvoice.api

import com.github.houbb.opencc4j.util.ZhConverterUtil
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
import kotlin.math.min

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

        // 尾部截斷觸發門檻：raw 必須 ≥10 字、final 至少 > raw × 1.15、實質補寫 ≥4 字
        private const val MIN_RAW_LEN_FOR_TRUNCATE = 10
        private const val TRUNCATE_LEN_RATIO = 1.15
        private const val MIN_SUBSTANTIVE_TRAILING = 4
        private const val MIN_RAW_TAIL_LEN = 4
        private val TRIM_PUNCT_CHARS = "，。、！？.,!?\n\t ".toCharArray()
        private val SENTENCE_END_PUNCT = "，。、！？.,!?\n\t".toCharArray()
    }

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .build()

    /**
     * 對語音辨識結果進行後處理
     *
     * @param mode "dictate"（預設）= 口述清理，會套用尾部幻覺截斷；
     *             "edit"            = 改寫/翻譯/Email 草稿等，LLM 本來就該主動加內容，跳過截斷。
     */
    suspend fun postProcess(text: String, sceneExtra: String = "", mode: String = "dictate"): String {
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
        val raw = when (engine) {
            "claude" -> processClaude(text, systemPrompt)
            "openai" -> processOpenAiLike(text, systemPrompt, OPENAI_API_URL, apiConfig.openAiApiKey, "gpt-4o")
            "groq" -> processOpenAiLike(text, systemPrompt, GROQ_API_URL, apiConfig.groqApiKey, ApiConfig.DEFAULT_GROQ_LLM_MODEL)
            else -> return text
        }

        // LLM 失敗（空字串）→ fallback 到原 text
        if (raw.isBlank()) return text

        // 守門：偵測尾部幻覺（LLM 自己接話）並截斷。validateLlmResult 回 null = 該丟棄。
        val validated = validateLlmResult(text, raw, mode)
        return validated ?: text
    }

    /**
     * LLM 結果守門：目前實作只做尾部補寫截斷（dictate mode）。
     * 全段幻覺偵測（_is_llm_hallucination）尚未移植，視之後需要再加。
     *
     * @return null = 應丟棄（fallback 原 text）；非 null = 處理後可用字串
     */
    internal fun validateLlmResult(rawInput: String, llmResult: String, mode: String): String? {
        if (llmResult.isBlank()) return null
        if (mode != "dictate") return llmResult
        val truncated = truncateTrailingHallucination(rawInput, llmResult)
        return truncated ?: llmResult
    }

    /**
     * 偵測「raw 內容完整保留，但 LLM 在結尾自己接話」的補寫型幻覺，回傳截斷版。
     * 不是這種模式回 null（caller 用原 result）。
     *
     * 對應 macOS 版 transcriber.py:_truncate_trailing_hallucination。
     * Kotlin 沒有 difflib，改用「raw 尾段定位 + 尾段後的實質補寫長度」啟發式判斷。
     */
    internal fun truncateTrailingHallucination(originalText: String, llmResult: String): String? {
        if (originalText.isBlank() || llmResult.isBlank()) return null
        val oRaw = originalText.trim()
        val rRaw = llmResult.trim()
        if (oRaw.length < MIN_RAW_LEN_FOR_TRUNCATE) return null
        if (rRaw.length <= oRaw.length * TRUNCATE_LEN_RATIO) return null

        // 同時用 OpenCC s2twp 正規化 raw 跟 final，避免 simplified vs traditional 比對 miss
        val o = safeToTraditional(oRaw)
        val r = safeToTraditional(rRaw)

        // 取 raw 尾段（最多 10 字，但不少於 raw 的一半，避免太短誤判）作為定位錨點。
        // 去掉純標點/空白後若不足 4 字 → 跳過，不夠特徵。
        val tailLen = min(10, o.length / 2).coerceAtLeast(1)
        val rawTailWithPunct = o.substring(o.length - tailLen)
        val rawTail = rawTailWithPunct.trimEnd(*TRIM_PUNCT_CHARS)
        if (rawTail.length < MIN_RAW_TAIL_LEN) return null

        // 在 r 找 rawTail 的最末出現位置
        val idx = r.lastIndexOf(rawTail)
        if (idx < 0) return null

        val endInResult = idx + rawTail.length
        if (endInResult >= r.length) return null

        val trailing = r.substring(endInResult)
        val substantive = trailing.trim(*TRIM_PUNCT_CHARS)
        if (substantive.length < MIN_SUBSTANTIVE_TRAILING) return null

        // 觸發截斷
        var truncated = r.substring(0, endInResult)
        if (truncated.isNotEmpty() && truncated.last() !in SENTENCE_END_PUNCT) {
            // 從原 trailing 取第一個句尾標點接上；沒有則補中文句號
            val firstEnd = trailing.firstOrNull { it in "。！？.!?".toCharArray() }
            truncated += (firstEnd ?: '。')
        }
        return truncated
    }

    private fun safeToTraditional(text: String): String {
        return try {
            ZhConverterUtil.toTraditional(text)
        } catch (_: Exception) {
            text
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
