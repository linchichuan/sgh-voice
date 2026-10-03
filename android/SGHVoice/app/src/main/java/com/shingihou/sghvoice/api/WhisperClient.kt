package com.shingihou.sghvoice.api

import com.shingihou.sghvoice.processing.VocabularyHintPolicy
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
import java.net.SocketTimeoutException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resumeWithException

/**
 * Existing BYOK file-transcription adapter for OpenAI and Groq.
 * Provider-specific multipart fields stay here; callers supply audio and spelling references.
 */
class WhisperClient(
    private val apiConfig: ApiConfig,
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()
) {

    companion object {
        private const val WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"
        private const val GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
    }

    /**
     * 傳送 WAV 音訊至 Whisper API 進行語音辨識
     *
     * @param wavData WAV 格式的音訊資料（含 44 byte 標頭）
     * @param initialPrompt VocabularyHintPolicy 產生的「、」分隔拼字清單；
     * gpt-transcribe 轉為 keywords，其他模型保留 prompt。
     * @return 辨識後的文字結果
     * @throws WhisperException 當 API 呼叫失敗時拋出
     */
    suspend fun transcribe(wavData: ByteArray, initialPrompt: String = ""): String {
        val sttEngine = apiConfig.sttEngine
        val useGroq = sttEngine == "groq" || (sttEngine == "openai" && apiConfig.openAiApiKey.isBlank() && apiConfig.groqApiKey.isNotBlank())
        
        val apiKey = if (useGroq) apiConfig.groqApiKey else apiConfig.openAiApiKey
        val apiUrl = if (useGroq) GROQ_API_URL else WHISPER_API_URL
        val modelName = if (useGroq) apiConfig.groqSttModel else apiConfig.whisperModel

        if (apiKey.isBlank()) {
            throw WhisperException("OpenAI or Groq API key not set")
        }

        return withContext(Dispatchers.IO) {
            val requestBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart(
                    "file",
                    "recording.wav",
                    wavData.toRequestBody("audio/wav".toMediaType())
                )
                .addFormDataPart("model", modelName)
                .addFormDataPart("response_format", "json")
                .apply {
                    if (!useGroq && modelName == ApiModelCatalog.OPENAI_STT_GPT_TRANSCRIBE) {
                        // The new model replaces language with languages; never send both.
                        apiConfig.recognitionLanguage.transcriptionLanguages.forEach {
                            addFormDataPart("languages[]", it)
                        }
                        VocabularyHintPolicy.transcriptionKeywords(initialPrompt).forEach {
                            addFormDataPart("keywords[]", it)
                        }
                    } else {
                        // Legacy OpenAI/Groq models must not receive unsupported new fields.
                        apiConfig.recognitionLanguage.apiCode?.let { language ->
                            addFormDataPart("language", language)
                        }
                        if (initialPrompt.isNotBlank()) addFormDataPart("prompt", initialPrompt)
                    }
                }
                .build()

            val request = Request.Builder()
                .url(apiUrl)
                .header("Authorization", "Bearer $apiKey")
                .post(requestBody)
                .build()

            if (!apiConfig.hasCloudProcessingConsent) throw CloudProcessingConsentException()
            httpClient.awaitCall(request).use { response ->
                if (!response.isSuccessful) {
                    throw WhisperException("Speech recognition HTTP ${response.code}")
                }
                val body = response.body?.string()
                    ?: throw WhisperException("Speech recognition returned an empty response")
                try {
                    val text = JSONObject(body).get("text")
                    if (text !is String) throw IllegalArgumentException()
                    text.trim()
                } catch (_: Exception) {
                    throw WhisperException("Speech recognition returned an invalid response")
                }
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
@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
private suspend fun OkHttpClient.awaitCall(request: Request): Response {
    return suspendCancellableCoroutine { continuation ->
        val call = newCall(request)
        continuation.invokeOnCancellation { call.cancel() }

        call.enqueue(object : Callback {
            override fun onResponse(call: Call, response: Response) {
                continuation.resume(response, onCancellation = { response.close() })
            }

            override fun onFailure(call: Call, e: IOException) {
                if (!continuation.isCancelled) {
                    continuation.resumeWithException(
                        WhisperException(if (e is SocketTimeoutException) {
                            "Speech recognition timed out"
                        } else {
                            "Speech recognition network error"
                        })
                    )
                }
            }
        })
    }
}

/** Whisper API 例外類別 */
class WhisperException(message: String, cause: Throwable? = null) : Exception(message, cause)
