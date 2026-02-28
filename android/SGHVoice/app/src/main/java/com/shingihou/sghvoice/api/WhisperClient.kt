package com.shingihou.sghvoice.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resumeWithException

/**
 * OpenAI Whisper API 客戶端
 * 將錄音的 WAV 檔傳送至 Whisper API 取得語音辨識結果
 */
class WhisperClient(private val apiConfig: ApiConfig) {

    companion object {
        private const val WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"
        private const val TIMEOUT_SECONDS = 30L
    }

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .build()

    /**
     * 傳送 WAV 音訊至 Whisper API 進行語音辨識
     *
     * @param wavData WAV 格式的音訊資料（含 44 byte 標頭）
     * @param initialPrompt 提示詞，用於提升辨識精確度（包含自訂詞彙）
     * @return 辨識後的文字結果
     * @throws WhisperException 當 API 呼叫失敗時拋出
     */
    suspend fun transcribe(wavData: ByteArray, initialPrompt: String = ""): String {
        val apiKey = apiConfig.openAiApiKey
        if (apiKey.isBlank()) {
            throw WhisperException("OpenAI API key not set")
        }

        return withContext(Dispatchers.IO) {
            val requestBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart(
                    "file",
                    "recording.wav",
                    wavData.toRequestBody("audio/wav".toMediaType())
                )
                .addFormDataPart("model", apiConfig.whisperModel)
                .addFormDataPart("response_format", "json")
                .apply {
                    // 提示詞：包含自訂詞彙以提升三語混合辨識
                    if (initialPrompt.isNotBlank()) {
                        addFormDataPart("prompt", initialPrompt)
                    }
                }
                .build()

            val request = Request.Builder()
                .url(WHISPER_API_URL)
                .header("Authorization", "Bearer $apiKey")
                .post(requestBody)
                .build()

            val response = httpClient.awaitCall(request)

            val body = response.body?.string()
                ?: throw WhisperException("Whisper API returned empty response")

            if (!response.isSuccessful) {
                val errorMsg = try {
                    val errorJson = JSONObject(body)
                    errorJson.optJSONObject("error")?.optString("message")
                        ?: "HTTP ${response.code}"
                } catch (_: Exception) {
                    "HTTP ${response.code}: $body"
                }
                throw WhisperException("Whisper API error: $errorMsg")
            }

            try {
                val json = JSONObject(body)
                json.getString("text").trim()
            } catch (e: Exception) {
                throw WhisperException("Failed to parse Whisper response: ${e.message}")
            }
        }
    }

    /** 關閉 HTTP 客戶端連線池 */
    fun shutdown() {
        httpClient.dispatcher.executorService.shutdown()
        httpClient.connectionPool.evictAll()
    }
}

/**
 * OkHttp Call 的協程擴充函式
 * 將回呼式呼叫轉換為 suspend 函式
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
                        WhisperException("Network error: ${e.message}")
                    )
                }
            }
        })
    }
}

/** Whisper API 例外類別 */
class WhisperException(message: String, cause: Throwable? = null) : Exception(message, cause)
