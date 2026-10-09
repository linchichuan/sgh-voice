package com.shingihou.sghvoice.processing

import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.api.CloudProcessingConsentException
import com.shingihou.sghvoice.api.TranslationException
import com.shingihou.sghvoice.api.ComposeException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

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
    private val openCCConverter: OpenCCConverter,
    private val cloudProcessingAllowed: () -> Boolean
) {

    /** Per-operation, content-free timings. Never persisted or uploaded. */
    data class Timings(val recognitionMs: Long, val textProcessingMs: Long, val totalMs: Long)

    private fun elapsedMs(started: Long): Long =
        ((System.nanoTime() - started) / 1_000_000L).coerceAtLeast(0)

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
        val error: String? = null,
        val refinementStatus: LlmClient.RefinementStatus? = null,
        /** Corrected source of a translation; never learn target-language edits as source corrections. */
        val sourceText: String = "",
        /**
         * Dictation only: the text the user would have seen without AI cleanup (STT after the
         * same dictionary/OpenCC passes). Learning may only learn spans that came from it.
         */
        val learningBaseline: String = "",
        val timings: Timings? = null
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
    suspend fun process(
        wavData: ByteArray,
        callback: ProgressCallback? = null,
        includePersonalization: Boolean = false,
        recentContext: () -> String = { "" }
    ): Result =
        process(wavData, VoiceTask.Dictation, callback, includePersonalization, recentContext)

    /**
     * 依任務明確分流口述與翻譯。翻譯只在來源文字套一次詞庫修正，目標文字不再
     * 套來源修正；OpenCC 也只套用在 zh-Hant 目標。
     * 個人化必須由當次欄位明確允許；未提供欄位決策的呼叫端預設不讀取學習資料。
     */
    suspend fun process(
        wavData: ByteArray,
        task: VoiceTask,
        callback: ProgressCallback? = null,
        includePersonalization: Boolean = false,
        recentContext: () -> String = { "" }
    ): Result {
        val startedAt = System.nanoTime()
        try {
            currentCoroutineContext().ensureActive()
            requireCloudProcessingConsent()
            // === 第一層：Whisper 語音辨識 ===
            callback?.onWhisperStarted()
            val whisperPrompt = dictionaryManager.buildWhisperPrompt(includePersonalization)
            requireCloudProcessingConsent()
            val rawText = whisperClient.transcribe(wavData, whisperPrompt)
            val recognitionMs = elapsedMs(startedAt)
            // Focus handoff may keep this operation alive. Re-check consent after
            // STT before reading learned data or starting another cloud request.
            currentCoroutineContext().ensureActive()
            requireCloudProcessingConsent()

            if (rawText.isBlank()) {
                val result = Result(text = "", rawText = "", success = true)
                callback?.onCompleted(result)
                return result
            }
            callback?.onWhisperCompleted(rawText)
            val textStartedAt = System.nanoTime()

            // === 第二層：詞庫修正 ===
            val correctedText = dictionaryManager.applyCorrections(rawText, includePersonalization)
            // Keep a resolver, not a private text snapshot, across asynchronous STT.
            // Resolve only at the LLM boundary; the caller rechecks expiry, edits and focus.
            val allowedContext = { if (includePersonalization) recentContext() else "" }

            val result = when (task) {
                VoiceTask.Dictation -> processDictation(
                    correctedText, rawText, callback, includePersonalization, allowedContext
                )
                VoiceTask.Compose -> Result(
                    text = correctedText,
                    rawText = rawText,
                    success = true
                )
                is VoiceTask.Translation ->
                    processTranslation(correctedText, rawText, task.request, callback, allowedContext)
            }
            currentCoroutineContext().ensureActive()
            val measuredResult = result.copy(timings = Timings(
                recognitionMs, elapsedMs(textStartedAt), elapsedMs(startedAt)
            ))
            callback?.onCompleted(measuredResult)
            return measuredResult

        } catch (error: CancellationException) {
            throw error
        } catch (e: Exception) {
            val errorMsg = when (e) {
                is CloudProcessingConsentException -> CloudProcessingConsentException.MESSAGE
                is TranslationException -> e.message ?: "Translation failed."
                else -> "Voice processing failed."
            }
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
     * Explicit, faithful organization of the entire in-memory draft. Unlike a writing brief,
     * these segments are inert speech: never execute a dictated instruction or invent an answer.
     * A failed/disabled guard must leave the original draft available, not mark raw text as done.
     */
    suspend fun organizeNotes(notes: String, includePersonalization: Boolean = false): String {
        currentCoroutineContext().ensureActive()
        requireCloudProcessingConsent()
        if (notes.isBlank() || notes.length > VoiceDraftState.MAX_COMPOSE_CHARACTERS) {
            throw ComposeException("Draft is empty or too long.")
        }
        val result = processDictation(notes, notes, null, includePersonalization, { "" })
        currentCoroutineContext().ensureActive()
        requireCloudProcessingConsent()
        if (result.refinementStatus != LlmClient.RefinementStatus.APPLIED || result.text.isBlank() ||
            result.text.length > VoiceDraftState.MAX_PENDING_CHARACTERS) {
            throw ComposeException("Draft organization was unavailable or rejected.")
        }
        return result.text
    }

    /** Compose only after the user confirms all captured segments. No dictation fallback. */
    suspend fun composeNotes(notes: String): String {
        currentCoroutineContext().ensureActive()
        requireCloudProcessingConsent()
        val draft = llmClient.compose(notes)
        currentCoroutineContext().ensureActive()
        requireCloudProcessingConsent()
        // The requested output can be Japanese. A global Chinese conversion
        // would corrupt Japanese kanji such as 画像; the compose prompt owns
        // Traditional Chinese output instead.
        return draft
    }

    private suspend fun processDictation(
        correctedText: String,
        rawText: String,
        callback: ProgressCallback?,
        includePersonalization: Boolean,
        recentContext: () -> String
    ): Result {
        callback?.onLlmStarted()
        requireCloudProcessingConsent()
        val sceneExtra = dictionaryManager.getSceneSystemPromptExtra()
        val vocabularyHint = dictionaryManager.buildLlmVocabularyHint(correctedText, includePersonalization)
        requireCloudProcessingConsent()
        // Re-check after STT and progress callbacks: focus/setting may have changed while awaiting audio.
        val currentContext = recentContext()
        val refinement = try {
            llmClient.refineDictation(
                correctedText, sceneExtra,
                vocabularyHint = vocabularyHint,
                previousContext = currentContext
            )
        } catch (error: CancellationException) {
            throw error
        } catch (error: CloudProcessingConsentException) {
            throw error
        } catch (_: Exception) {
            // 一般口述維持既有降級策略：LLM 失敗仍可輸出詞庫修正後文字。
            LlmClient.RefinementResult(correctedText, LlmClient.RefinementStatus.UNAVAILABLE)
        }

        currentCoroutineContext().ensureActive()
        requireCloudProcessingConsent()
        val traditionalText = openCCConverter.convert(refinement.text)
        val finalText = dictionaryManager.applyCorrections(traditionalText, includePersonalization)
        // What the user would have seen without AI cleanup: STT through the same local passes.
        // An empty baseline disables learning for this turn (fail closed), never the dictation.
        val learningBaseline = if (refinement.status == LlmClient.RefinementStatus.APPLIED) {
            runCatching {
                dictionaryManager.applyCorrections(openCCConverter.convert(correctedText), includePersonalization)
            }.getOrNull().orEmpty()
        } else finalText
        return Result(
            text = finalText,
            rawText = rawText,
            success = true,
            refinementStatus = refinement.status,
            learningBaseline = learningBaseline
        )
    }

    private suspend fun processTranslation(
        correctedText: String,
        rawText: String,
        request: TranslationRequest,
        callback: ProgressCallback?,
        recentContext: () -> String
    ): Result {
        callback?.onLlmStarted()
        requireCloudProcessingConsent()
        val currentContext = recentContext()
        val translated = llmClient.translate(correctedText, request, currentContext)
        requireCloudProcessingConsent()
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
            success = true,
            sourceText = correctedText
        )
    }

    /**
     * 僅執行 Whisper 辨識（不進行後處理）
     * 用於快速模式或除錯
     */
    suspend fun transcribeOnly(wavData: ByteArray, includePersonalization: Boolean = false): Result {
        return try {
            currentCoroutineContext().ensureActive()
            requireCloudProcessingConsent()
            val whisperPrompt = dictionaryManager.buildWhisperPrompt(includePersonalization)
            requireCloudProcessingConsent()
            val rawText = whisperClient.transcribe(wavData, whisperPrompt)
            currentCoroutineContext().ensureActive()
            requireCloudProcessingConsent()
            Result(text = rawText, rawText = rawText, success = true)
        } catch (error: CancellationException) {
            throw error
        } catch (e: Exception) {
            Result(success = false, error = if (e is CloudProcessingConsentException) {
                CloudProcessingConsentException.MESSAGE
            } else {
                "Transcription failed."
            })
        }
    }

    private fun requireCloudProcessingConsent() {
        if (!cloudProcessingAllowed()) throw CloudProcessingConsentException()
    }
}
