package com.shingihou.sghvoice.processing

import com.shingihou.sghvoice.api.ClaudeClient
import com.shingihou.sghvoice.api.WhisperClient

/**
 * 語音辨識處理管線
 * 四層處理流程：
 * 1. Whisper STT — 語音轉文字（含三語提示詞）
 * 2. 詞庫修正 — 自訂詞彙替換（最長匹配優先）
 * 3. Claude 後處理 — 去填充詞、修正標點、潤稿
 * 4. OpenCC s2twp — 繁體中文最終防護
 */
class TranscriptionPipeline(
    private val whisperClient: WhisperClient,
    private val claudeClient: ClaudeClient,
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

        /** 開始 Claude 後處理 */
        fun onClaudeStarted()

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
    suspend fun process(wavData: ByteArray, callback: ProgressCallback? = null): Result {
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

            // === 第三層：Claude 後處理（含場景指令）===
            callback?.onClaudeStarted()
            val sceneExtra = dictionaryManager.getSceneSystemPromptExtra()
            val processedText = try {
                claudeClient.postProcess(correctedText, sceneExtra)
            } catch (e: Exception) {
                // Claude 失敗時降級為使用詞庫修正後的結果
                correctedText
            }

            // === 第四層：OpenCC 繁體中文轉換 ===
            val finalText = openCCConverter.convert(processedText)

            val result = Result(
                text = finalText,
                rawText = rawText,
                success = true
            )
            callback?.onCompleted(result)
            return result

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

    /**
     * 僅執行 Whisper 辨識（不進行後處理）
     * 用於快速模式或除錯
     */
    suspend fun transcribeOnly(wavData: ByteArray): Result {
        return try {
            val whisperPrompt = dictionaryManager.buildWhisperPrompt()
            val rawText = whisperClient.transcribe(wavData, whisperPrompt)
            Result(text = rawText, rawText = rawText, success = true)
        } catch (e: Exception) {
            Result(success = false, error = e.message ?: "Transcription failed")
        }
    }
}
