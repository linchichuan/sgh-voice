package com.shingihou.sghvoice.processing

import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import kotlinx.coroutines.CancellationException

/**
 * 語音辨識處理管線
 * 四層處理流程：
 * 1. Whisper STT — 語音轉文字（含三語提示詞）
 * 2. 詞庫修正 — 自訂詞彙替換（最長匹配優先）
 * 3. LLM 後處理 — 去填充詞、修正標點、潤稿 (支援 Claude/OpenAI/Groq)
 * 4. OpenCC s2twp — 繁體中文最終防護
 * 5. 最終詞庫修正 — 防止 LLM／OpenCC 把已學會的專有詞改回去
 */
class TranscriptionPipeline(
    private val whisperClient: WhisperClient,
    private val llmClient: LlmClient,
    private val dictionaryManager: DictionaryManager,
    private val openCCConverter: OpenCCConverter
) {

    /**
     * 處理結果封裝
     *
     * @property text 最終處理後的文字
     * @property rawText Whisper 原始辨識文字
     * @property success 是否成功
     * @property error 錯誤訊息（失敗時）
     */
    data class Result(
        val text: String = "",
        val rawText: String = "",
        val translations: List<TranslationOutput> = emptyList(),
        val success: Boolean = true,
        val error: String? = null
    )

    /**
     * 處理回呼介面
     * 讓 UI 可以在各階段更新狀態
     */
    interface ProgressCallback {
        /** 開始 Whisper 語音辨識 */
        fun onWhisperStarted()

        /** Whisper 辨識完成 */
        fun onWhisperCompleted(text: String)

        /** 開始 LLM 後處理 */
        fun onLlmStarted()

        /** 全部處理完成 */
        fun onCompleted(result: Result)

        /** 處理過程發生錯誤 */
        fun onError(error: String)
    }

    /**
     * 執行完整的四層處理管線
     *
     * @param wavData WAV 格式音訊資料
     * @param callback 進度回呼（可選）
     * @return 處理結果
     */
    suspend fun process(wavData: ByteArray, callback: ProgressCallback? = null): Result =
        process(wavData, VoiceTask.Dictation, callback)

    /**
     * 依任務明確分流口述與翻譯。翻譯只在來源文字套一次詞庫修正，目標文字不再
     * 套來源修正；OpenCC 也只套用在 zh-Hant 目標。
     */
    suspend fun process(
        wavData: ByteArray,
        task: VoiceTask,
        callback: ProgressCallback? = null
    ): Result {
        try {
            // === 第一層：Whisper 語音辨識 ===
            callback?.onWhisperStarted()
            val whisperPrompt = dictionaryManager.buildWhisperPrompt()
            val rawText = whisperClient.transcribe(wavData, whisperPrompt)

            if (rawText.isBlank()) {
                val result = Result(text = "", rawText = "", success = true)
                callback?.onCompleted(result)
                return result
            }
            callback?.onWhisperCompleted(rawText)

            // === 第二層：詞庫修正 ===
            val correctedText = dictionaryManager.applyCorrections(rawText)

            val result = when (task) {
                VoiceTask.Dictation -> processDictation(correctedText, rawText, callback)
                is VoiceTask.Translation ->
                    processTranslation(correctedText, rawText, task.request, callback)
            }
            callback?.onCompleted(result)
            return result

        } catch (error: CancellationException) {
            throw error
        } catch (e: Exception) {
            val errorMsg = e.message ?: "Unknown error"
            callback?.onError(errorMsg)
            return Result(
                text = "",
                rawText = "",
                success = false,
                error = errorMsg
            )
        }
    }

    private suspend fun processDictation(
        correctedText: String,
        rawText: String,
        callback: ProgressCallback?
    ): Result {
        callback?.onLlmStarted()
        val sceneExtra = dictionaryManager.getSceneSystemPromptExtra()
        val processedText = try {
            llmClient.postProcess(correctedText, sceneExtra)
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            // 一般口述維持既有降級策略：LLM 失敗仍可輸出詞庫修正後文字。
            correctedText
        }

        val traditionalText = openCCConverter.convert(processedText)
        val finalText = dictionaryManager.applyCorrections(traditionalText)
        return Result(
            text = finalText,
            rawText = rawText,
            success = true
        )
    }

    private suspend fun processTranslation(
        correctedText: String,
        rawText: String,
        request: TranslationRequest,
        callback: ProgressCallback?
    ): Result {
        callback?.onLlmStarted()
        val translated = llmClient.translate(correctedText, request)
        val finalized = translated.map { output ->
            if (output.language == TranslationLanguage.TRADITIONAL_CHINESE) {
                output.copy(text = openCCConverter.convert(output.text))
            } else {
                output
            }
        }
        return Result(
            text = finalized.first().text,
            rawText = rawText,
            translations = finalized,
            success = true
        )
    }

    /**
     * 僅執行 Whisper 辨識（不進行後處理）
     * 用於快速模式或除錯
     */
    suspend fun transcribeOnly(wavData: ByteArray): Result {
        return try {
            val whisperPrompt = dictionaryManager.buildWhisperPrompt()
            val rawText = whisperClient.transcribe(wavData, whisperPrompt)
            Result(text = rawText, rawText = rawText, success = true)
        } catch (error: CancellationException) {
            throw error
        } catch (e: Exception) {
            Result(success = false, error = e.message ?: "Transcription failed")
        }
    }
}
