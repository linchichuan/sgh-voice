package com.shingihou.sghvoice.ime

import android.inputmethodservice.InputMethodService
import android.os.Build
import android.os.SystemClock
import android.util.Log
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputConnection
import android.view.inputmethod.InputMethodManager
import android.widget.Toast
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.audio.AudioRecorder
import com.shingihou.sghvoice.ime.japanese.AndroidJapaneseLexicon
import com.shingihou.sghvoice.ime.japanese.JapaneseCandidate
import com.shingihou.sghvoice.ime.japanese.JapaneseComposer
import com.shingihou.sghvoice.ime.manual.EnglishCandidate
import com.shingihou.sghvoice.ime.manual.EnglishCandidateProvider
import com.shingihou.sghvoice.ime.manual.EnglishComposer
import com.shingihou.sghvoice.ime.manual.EnglishEdit
import com.shingihou.sghvoice.ime.manual.KeyAction
import com.shingihou.sghvoice.ime.manual.ShiftState
import com.shingihou.sghvoice.learning.BoundedTextSnapshot
import com.shingihou.sghvoice.learning.CorrectionRecordStatus
import com.shingihou.sghvoice.learning.CorrectionReplacement
import com.shingihou.sghvoice.learning.LearningLanguage
import com.shingihou.sghvoice.learning.LearningPolicy
import com.shingihou.sghvoice.learning.LearningPolicyDecision
import com.shingihou.sghvoice.learning.PersonalizationRepository
import com.shingihou.sghvoice.learning.VoiceCorrectionTracker
import com.shingihou.sghvoice.learning.VoiceCorrectionTrackingStatus
import com.shingihou.sghvoice.processing.DictionaryManager
import com.shingihou.sghvoice.processing.OpenCCConverter
import com.shingihou.sghvoice.processing.RecognitionLanguage
import com.shingihou.sghvoice.processing.TranslationLanguage
import com.shingihou.sghvoice.processing.TranslationOutput
import com.shingihou.sghvoice.processing.TranslationRequest
import com.shingihou.sghvoice.processing.TranscriptionPipeline
import com.shingihou.sghvoice.processing.VoiceTask
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

/**
 * SGH Voice 輸入法服務。
 *
 * 同一個 IME 內提供語音與注音兩種模式。語音使用點按切換錄音，並以 input
 * session / operation token 確保非同步辨識結果不會寫入後來切換的新欄位。
 */
class VoiceInputIME : InputMethodService(), KeyboardView.KeyboardActionListener {

    companion object {
        private const val TAG = "SGHVoiceIME"
        private const val PIPELINE_WAIT_ATTEMPTS = 50
        private const val PIPELINE_WAIT_INTERVAL_MS = 100L
        private const val MAX_RECORDING_DURATION_MS = 120_000L
        private const val MIN_WAV_SIZE_BYTES = 8_044
        private const val ZHUYIN_CANDIDATE_LIMIT = 24
        private const val ZHUYIN_CONTEXT_CODE_POINTS = 16
        private const val JAPANESE_CANDIDATE_LIMIT = 24
        private const val ENGLISH_CANDIDATE_LIMIT = 12
        private const val SNAPSHOT_SIDE_CODE_POINTS = 600
        private const val CORRECTION_DEBOUNCE_MS = 450L
    }

    enum class ImeState {
        IDLE,
        STARTING,
        RECORDING,
        STOPPING,
        PROCESSING,
        DONE,
        ERROR
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var currentState = ImeState.IDLE
    private var currentInputMode = KeyboardView.InputMode.VOICE
    private var keyboardView: KeyboardView? = null

    private var apiConfig: ApiConfig? = null
    private var audioRecorder: AudioRecorder? = null
    private lateinit var dictionaryManager: DictionaryManager
    private lateinit var personalization: PersonalizationRepository

    @Volatile
    private var pipeline: TranscriptionPipeline? = null

    private lateinit var zhuyinLexicon: AndroidZhuyinLexicon
    private lateinit var zhuyinComposer: ZhuyinComposer
    private lateinit var japaneseLexicon: AndroidJapaneseLexicon
    private lateinit var japaneseComposer: JapaneseComposer
    private lateinit var englishComposer: EnglishComposer

    private var inputSessionId = 0L
    private var voiceOperationId = 0L
    private var recordingControlJob: Job? = null
    private var recordingTimerJob: Job? = null
    private var transcriptionJob: Job? = null
    private var correctionInspectionJob: Job? = null
    private val voiceCorrectionTracker = VoiceCorrectionTracker()
    private var lastCommittedVoiceText = ""
    private var currentLearningDecision: LearningPolicyDecision = LearningPolicy.evaluate(null)
    private var activeVoiceTask: VoiceTask = VoiceTask.Dictation

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "onCreate")

        try {
            apiConfig = ApiConfig(this)
            audioRecorder = AudioRecorder().also { recorder ->
                recorder.setLevelListener { level ->
                    val view = keyboardView ?: return@setLevelListener
                    view.post {
                        if (keyboardView === view && currentState == ImeState.RECORDING) {
                            view.setAudioLevel(level)
                        }
                    }
                }
            }
            dictionaryManager = DictionaryManager(this)
            personalization = PersonalizationRepository.getInstance(this)
            zhuyinLexicon = AndroidZhuyinLexicon(this)
            zhuyinComposer = ZhuyinComposer(zhuyinLexicon)
            japaneseLexicon = AndroidJapaneseLexicon(this)
            japaneseComposer = JapaneseComposer(japaneseLexicon)
            englishComposer = EnglishComposer(
                candidateProvider = EnglishCandidateProvider { prefix, limit ->
                    buildEnglishCandidates(prefix, limit)
                }
            )
        } catch (error: Exception) {
            Log.e(TAG, "Base component initialization failed", error)
        }

        preparePipeline()
    }

    override fun onCreateInputView(): View {
        val view = KeyboardView(this).apply {
            setKeyboardActionListener(this@VoiceInputIME)
            setInputMode(currentInputMode)
            setRecognitionLanguage(
                apiConfig?.recognitionLanguage ?: RecognitionLanguage.AUTO
            )
            updateState(currentState)
        }
        keyboardView = view
        updateManualUi()
        return view
    }

    override fun onStartInput(attribute: EditorInfo?, restarting: Boolean) {
        super.onStartInput(attribute, restarting)
        beginInputSession(attribute)
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        keyboardView?.setInputMode(currentInputMode)
        keyboardView?.setRecognitionLanguage(
            apiConfig?.recognitionLanguage ?: RecognitionLanguage.AUTO
        )
        keyboardView?.updateState(currentState)
        updateManualUi()
    }

    override fun onFinishInputView(finishingInput: Boolean) {
        finishInputSession()
        super.onFinishInputView(finishingInput)
    }

    override fun onFinishInput() {
        finishInputSession()
        super.onFinishInput()
    }

    override fun onUnbindInput() {
        finishInputSession()
        super.onUnbindInput()
    }

    override fun onDestroy() {
        invalidateVoiceOperation(resetState = false)
        cancelCorrectionTracking()
        serviceScope.cancel()
        audioRecorder?.release()
        keyboardView = null
        super.onDestroy()
    }

    override fun onEvaluateFullscreenMode(): Boolean = false

    override fun onEvaluateInputViewShown(): Boolean {
        super.onEvaluateInputViewShown()
        return true
    }

    private fun preparePipeline() {
        serviceScope.launch(Dispatchers.Default) {
            if (::zhuyinLexicon.isInitialized) {
                try {
                    zhuyinLexicon.warmUp()
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    Log.e(TAG, "Zhuyin lexicon warm-up failed", error)
                }
            }
            if (::japaneseLexicon.isInitialized) {
                try {
                    japaneseLexicon.warmUp()
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    Log.e(TAG, "Japanese lexicon warm-up failed", error)
                }
            }

            try {
                val config = apiConfig ?: ApiConfig(this@VoiceInputIME)
                val whisperClient = WhisperClient(config)
                val llmClient = LlmClient(config)
                val openCCConverter = OpenCCConverter()
                pipeline = TranscriptionPipeline(
                    whisperClient = whisperClient,
                    llmClient = llmClient,
                    dictionaryManager = dictionaryManager,
                    openCCConverter = openCCConverter
                )
                Log.d(TAG, "Pipeline initialized")
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                Log.e(TAG, "Pipeline initialization failed", error)
                withContext(Dispatchers.Main) {
                    showError(getString(R.string.msg_initialization_failed))
                }
            }
        }
    }

    private fun beginInputSession(editorInfo: EditorInfo?) {
        inputSessionId += 1
        invalidateVoiceOperation(resetState = true)
        currentLearningDecision = LearningPolicy.evaluate(editorInfo)
        resetManualComposers()
        cancelCorrectionTracking()
        updateManualUi()
    }

    private fun finishInputSession() {
        inputSessionId += 1
        invalidateVoiceOperation(resetState = true)
        currentInputConnection?.finishComposingText()
        resetManualComposers()
        cancelCorrectionTracking()
        updateManualUi()
    }

    private fun resetManualComposers() {
        if (::zhuyinComposer.isInitialized) zhuyinComposer.clear()
        if (::japaneseComposer.isInitialized) japaneseComposer.clear()
        if (::englishComposer.isInitialized) englishComposer.reset()
    }

    private fun cancelCorrectionTracking() {
        correctionInspectionJob?.cancel()
        correctionInspectionJob = null
        voiceCorrectionTracker.cancel()
        lastCommittedVoiceText = ""
    }

    private fun invalidateVoiceOperation(resetState: Boolean) {
        voiceOperationId += 1
        recordingControlJob?.cancel()
        recordingControlJob = null
        recordingTimerJob?.cancel()
        recordingTimerJob = null
        transcriptionJob?.cancel()
        transcriptionJob = null
        activeVoiceTask = VoiceTask.Dictation

        if (resetState) {
            setState(ImeState.IDLE)
        }

        val recorder = audioRecorder
        if (recorder != null) {
            serviceScope.launch {
                try {
                    recorder.abortAndDiscard()
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    Log.w(TAG, "Unable to discard active recording", error)
                }
            }
        }
    }

    private fun isCurrentOperation(sessionId: Long, operationId: Long): Boolean =
        sessionId == inputSessionId && operationId == voiceOperationId

    // ===== KeyboardActionListener =====

    override fun onMicToggle() {
        if (currentLearningDecision.sensitiveField) {
            showError(getString(R.string.msg_voice_disabled_sensitive))
            return
        }
        when (currentState) {
            ImeState.IDLE,
            ImeState.DONE,
            ImeState.ERROR -> {
                inspectVoiceCorrection()
                startRecording(VoiceTask.Dictation)
            }

            ImeState.RECORDING -> stopRecordingAndProcess()

            ImeState.STARTING,
            ImeState.STOPPING,
            ImeState.PROCESSING -> Unit
        }
    }

    override fun onTranslationPickerRequested() {
        if (currentLearningDecision.sensitiveField) {
            showError(getString(R.string.msg_voice_disabled_sensitive))
            return
        }
        if (currentState == ImeState.RECORDING && activeVoiceTask is VoiceTask.Translation) {
            invalidateVoiceOperation(resetState = true)
            keyboardView?.setStatusText(getString(R.string.msg_translation_cancelled))
            return
        }
        if (
            currentState != ImeState.IDLE &&
            currentState != ImeState.DONE &&
            currentState != ImeState.ERROR
        ) {
            return
        }
        val config = apiConfig ?: ApiConfig(this).also { apiConfig = it }
        keyboardView?.showTranslationPanel(config.translationTargets)
    }

    override fun onTranslationRequested(request: TranslationRequest) {
        if (currentLearningDecision.sensitiveField) {
            showError(getString(R.string.msg_voice_disabled_sensitive))
            return
        }
        if (
            currentState != ImeState.IDLE &&
            currentState != ImeState.DONE &&
            currentState != ImeState.ERROR
        ) {
            return
        }

        val config = apiConfig ?: ApiConfig(this).also { apiConfig = it }
        if (!hasSelectedLlmKey(config)) {
            showError(getString(R.string.msg_missing_translation_key))
            return
        }
        config.translationTargets = request.targets
        inspectVoiceCorrection()
        startRecording(VoiceTask.Translation(request))
    }

    private fun hasSelectedLlmKey(config: ApiConfig): Boolean =
        when (config.llmEngine) {
            "claude" -> config.anthropicApiKey.isNotBlank()
            "openai" -> config.openAiApiKey.isNotBlank()
            "groq" -> config.groqApiKey.isNotBlank()
            else -> false
        }

    private fun startRecording(task: VoiceTask) {
        val config = apiConfig ?: ApiConfig(this).also { apiConfig = it }
        if (!config.hasCloudProcessingConsent) {
            showError(getString(R.string.msg_cloud_consent_required))
            return
        }
        val hasSttKey = if (config.sttEngine == "groq") {
            config.groqApiKey.isNotBlank()
        } else {
            config.openAiApiKey.isNotBlank()
        }
        if (!hasSttKey) {
            showError(getString(R.string.msg_missing_stt_key))
            return
        }

        val recorder = audioRecorder
        if (recorder == null) {
            showError(getString(R.string.msg_initialization_failed))
            return
        }

        invalidateVoiceOperation(resetState = false)
        activeVoiceTask = task
        val sessionId = inputSessionId
        val operationId = voiceOperationId
        setState(ImeState.STARTING)

        recordingControlJob = serviceScope.launch {
            try {
                recorder.startRecording()
                if (!isCurrentOperation(sessionId, operationId)) {
                    recorder.abortAndDiscard()
                    return@launch
                }

                setState(ImeState.RECORDING)
                if (task is VoiceTask.Translation) {
                    keyboardView?.setTranslationRecordingMode()
                }
                startRecordingTimer(sessionId, operationId)
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (isCurrentOperation(sessionId, operationId)) {
                    Log.e(TAG, "Recording failed", error)
                    showError(getString(R.string.msg_record_failed) + (error.message ?: ""))
                }
            }
        }
    }

    private fun startRecordingTimer(sessionId: Long, operationId: Long) {
        recordingTimerJob?.cancel()
        recordingTimerJob = serviceScope.launch {
            val startedAt = SystemClock.elapsedRealtime()
            while (isCurrentOperation(sessionId, operationId) &&
                currentState == ImeState.RECORDING
            ) {
                val elapsedMs = SystemClock.elapsedRealtime() - startedAt
                if (elapsedMs >= MAX_RECORDING_DURATION_MS) {
                    keyboardView?.setStatusText(getString(R.string.status_recording_limit))
                    recordingTimerJob = null
                    stopRecordingAndProcess()
                    return@launch
                }
                keyboardView?.setRecordingElapsed(
                    formattedElapsed = formatElapsed(elapsedMs),
                    translating = activeVoiceTask is VoiceTask.Translation
                )
                delay(1_000)
            }
        }
    }

    private fun stopRecordingAndProcess() {
        if (currentState != ImeState.RECORDING) return

        val recorder = audioRecorder ?: return
        val sessionId = inputSessionId
        val operationId = voiceOperationId
        val targetConnection = currentInputConnection
        val task = activeVoiceTask

        recordingTimerJob?.cancel()
        recordingTimerJob = null
        setState(ImeState.STOPPING)

        recordingControlJob = serviceScope.launch {
            try {
                val wavData = recorder.stopRecording()
                if (!isCurrentOperation(sessionId, operationId)) return@launch

                if (wavData == null || wavData.size < MIN_WAV_SIZE_BYTES) {
                    setState(ImeState.IDLE)
                    keyboardView?.setStatusText(getString(R.string.msg_record_too_short))
                    return@launch
                }
                if (targetConnection == null) {
                    showError(getString(R.string.msg_input_connection_lost))
                    return@launch
                }

                transcribeAndCommit(
                    wavData = wavData,
                    sessionId = sessionId,
                    operationId = operationId,
                    targetConnection = targetConnection,
                    task = task
                )
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (isCurrentOperation(sessionId, operationId)) {
                    Log.e(TAG, "Unable to stop recording", error)
                    showError(getString(R.string.msg_record_failed) + (error.message ?: ""))
                }
            }
        }
    }

    private fun transcribeAndCommit(
        wavData: ByteArray,
        sessionId: Long,
        operationId: Long,
        targetConnection: InputConnection,
        task: VoiceTask
    ) {
        setState(ImeState.PROCESSING)
        transcriptionJob = serviceScope.launch {
            val activePipeline = awaitPipeline(sessionId, operationId) ?: return@launch

            try {
                // Consent can be withdrawn while the user is recording or while
                // the pipeline is warming up. Re-check at the actual upload
                // boundary and destroy the in-memory WAV before returning.
                val config = apiConfig ?: ApiConfig(this@VoiceInputIME).also {
                    apiConfig = it
                }
                if (!config.hasCloudProcessingConsent) {
                    wavData.fill(0)
                    if (isCurrentOperation(sessionId, operationId)) {
                        showError(getString(R.string.msg_cloud_consent_required))
                    }
                    return@launch
                }
                activePipeline.process(
                    wavData,
                    task,
                    object : TranscriptionPipeline.ProgressCallback {
                        override fun onWhisperStarted() {
                            updateStatusIfCurrent(
                                sessionId,
                                operationId,
                                R.string.msg_recognizing
                            )
                        }

                        override fun onWhisperCompleted(text: String) {
                            updateStatusIfCurrent(
                                sessionId,
                                operationId,
                                R.string.msg_post_processing
                            )
                        }

                        override fun onLlmStarted() {
                            updateStatusIfCurrent(
                                sessionId,
                                operationId,
                                if (task is VoiceTask.Translation) {
                                    R.string.msg_translating
                                } else {
                                    R.string.msg_ai_processing
                                }
                            )
                        }

                        override fun onCompleted(result: TranscriptionPipeline.Result) {
                            if (!isCurrentOperation(sessionId, operationId)) return

                            val textToCommit = when (task) {
                                VoiceTask.Dictation -> result.text
                                is VoiceTask.Translation ->
                                    formatTranslationOutputs(result.translations)
                            }
                            if (result.success && textToCommit.isNotBlank()) {
                                if (targetConnection.commitText(textToCommit, 1)) {
                                    setState(ImeState.DONE)
                                    if (task == VoiceTask.Dictation) {
                                        beginVoiceCorrectionTracking(
                                            sessionId = sessionId,
                                            connection = targetConnection,
                                            committedText = textToCommit
                                        )
                                    } else {
                                        // 翻譯不是錯字修正，不能寫入來源語言的學習詞庫。
                                        cancelCorrectionTracking()
                                    }
                                } else {
                                    showError(getString(R.string.msg_input_connection_lost))
                                }
                            } else if (result.success) {
                                showError(getString(R.string.msg_no_speech))
                            } else {
                                showError(
                                    if (task is VoiceTask.Translation) {
                                        getString(
                                            R.string.msg_translation_failed_detail,
                                            translationErrorHint(result.error.orEmpty())
                                        )
                                    } else {
                                        getString(R.string.msg_process_failed) +
                                            (result.error ?: getString(R.string.msg_unknown_error))
                                    }
                                )
                            }
                        }

                        override fun onError(error: String) {
                            if (isCurrentOperation(sessionId, operationId)) {
                                if (task is VoiceTask.Translation) {
                                    Log.e(TAG, "Translation failed: $error")
                                }
                                showError(
                                    if (task is VoiceTask.Translation) {
                                        getString(
                                            R.string.msg_translation_failed_detail,
                                            translationErrorHint(error)
                                        )
                                    } else {
                                        getString(R.string.msg_error) + error
                                    }
                                )
                            }
                        }
                    }
                )
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                if (isCurrentOperation(sessionId, operationId)) {
                    Log.e(TAG, "Transcription failed", error)
                    showError(
                        getString(R.string.msg_process_failed) +
                            (error.message ?: getString(R.string.msg_unknown_error))
                    )
                }
            }
        }
    }

    private fun translationErrorHint(error: String): String {
        val normalized = error.lowercase()
        return getString(
            when {
                "401" in normalized ||
                    "403" in normalized ||
                    "api key" in normalized -> R.string.translation_error_auth

                "404" in normalized ||
                    "model" in normalized && (
                        "not found" in normalized ||
                            "unavailable" in normalized ||
                            "access" in normalized
                        ) -> R.string.translation_error_model

                "429" in normalized ||
                    "rate limit" in normalized ||
                    "quota" in normalized ||
                    "credit" in normalized -> R.string.translation_error_quota

                "json" in normalized ||
                    "schema" in normalized ||
                    "parse" in normalized ||
                    "empty response" in normalized -> R.string.translation_error_format

                "semantic" in normalized ||
                    "answered source" in normalized ||
                    "source intent" in normalized -> R.string.translation_error_semantic

                "network" in normalized ||
                    "timeout" in normalized ||
                    "connection" in normalized -> R.string.translation_error_network

                else -> R.string.translation_error_unknown
            }
        )
    }

    private fun formatTranslationOutputs(outputs: List<TranslationOutput>): String {
        if (outputs.isEmpty()) return ""
        if (outputs.size == 1) return outputs.first().text
        return outputs.joinToString("\n") { output ->
            getString(
                R.string.translation_output_format,
                getString(translationLanguageLabel(output.language)),
                output.text
            )
        }
    }

    private fun translationLanguageLabel(language: TranslationLanguage): Int =
        when (language) {
            TranslationLanguage.TRADITIONAL_CHINESE -> R.string.translation_language_zh_hant
            TranslationLanguage.JAPANESE -> R.string.translation_language_ja
            TranslationLanguage.ENGLISH -> R.string.translation_language_en
            TranslationLanguage.KOREAN -> R.string.translation_language_ko
        }

    private suspend fun awaitPipeline(
        sessionId: Long,
        operationId: Long
    ): TranscriptionPipeline? {
        pipeline?.let { return it }
        keyboardView?.setStatusText(getString(R.string.msg_initializing))

        repeat(PIPELINE_WAIT_ATTEMPTS) {
            if (!isCurrentOperation(sessionId, operationId)) return null
            pipeline?.let { return it }
            delay(PIPELINE_WAIT_INTERVAL_MS)
        }

        if (isCurrentOperation(sessionId, operationId)) {
            showError(getString(R.string.msg_initialization_timeout))
        }
        return null
    }

    private fun updateStatusIfCurrent(
        sessionId: Long,
        operationId: Long,
        messageRes: Int
    ) {
        if (isCurrentOperation(sessionId, operationId)) {
            keyboardView?.setStatusText(getString(messageRes))
        }
    }

    override fun onRecognitionLanguageChanged(language: RecognitionLanguage) {
        if (
            currentState != ImeState.IDLE &&
            currentState != ImeState.DONE &&
            currentState != ImeState.ERROR
        ) {
            keyboardView?.setStatusText(
                getString(R.string.msg_recognition_language_busy)
            )
            return
        }
        val config = apiConfig ?: ApiConfig(this).also { apiConfig = it }
        config.recognitionLanguage = language
        keyboardView?.setRecognitionLanguage(language)
        keyboardView?.announceForAccessibility(
            getString(
                R.string.msg_recognition_language_changed,
                getString(recognitionLanguageLabel(language))
            )
        )
    }

    private fun recognitionLanguageLabel(language: RecognitionLanguage): Int =
        when (language) {
            RecognitionLanguage.AUTO -> R.string.recognition_language_auto
            RecognitionLanguage.TRADITIONAL_CHINESE ->
                R.string.recognition_language_traditional_chinese
            RecognitionLanguage.JAPANESE -> R.string.recognition_language_japanese
            RecognitionLanguage.ENGLISH -> R.string.recognition_language_english
            RecognitionLanguage.KOREAN -> R.string.recognition_language_korean
        }

    override fun onInputModeChanged(mode: KeyboardView.InputMode) {
        if (mode == currentInputMode) return

        commitActiveComposition()
        inspectVoiceCorrection()
        invalidateVoiceOperation(resetState = true)
        currentInputMode = mode
        keyboardView?.setInputMode(mode)
        updateManualUi()
    }

    override fun onKeyAction(action: KeyAction) {
        when (currentInputMode) {
            KeyboardView.InputMode.VOICE -> handleVoiceKey(action)
            KeyboardView.InputMode.ZHUYIN -> handleZhuyinKey(action)
            KeyboardView.InputMode.JAPANESE -> handleJapaneseKey(action)
            KeyboardView.InputMode.ENGLISH -> handleEnglishKey(action)
        }
    }

    override fun onCandidateSelected(candidate: String) {
        when (currentInputMode) {
            KeyboardView.InputMode.ZHUYIN -> selectZhuyinCandidate(candidate)
            KeyboardView.InputMode.JAPANESE -> selectJapaneseCandidate(candidate)
            KeyboardView.InputMode.ENGLISH -> selectEnglishCandidate(candidate)
            KeyboardView.InputMode.VOICE -> Unit
        }
    }

    private fun handleVoiceKey(action: KeyAction) {
        when (action) {
            is KeyAction.InsertText -> currentInputConnection?.commitText(action.text, 1)
            KeyAction.Backspace ->
                currentInputConnection?.deleteSurroundingTextInCodePoints(1, 0)
            KeyAction.Space -> currentInputConnection?.commitText(" ", 1)
            KeyAction.Enter -> performEnterAction()
            KeyAction.Shift,
            KeyAction.ToggleJapaneseScript,
            is KeyAction.SwitchLayer -> Unit
        }
    }

    private fun handleZhuyinKey(action: KeyAction) {
        if (!::zhuyinComposer.isInitialized) return
        when (action) {
            is KeyAction.InsertText -> {
                val symbol = action.text.singleOrNull()
                if (symbol != null && symbol in ZhuyinComposer.STANDARD_SYMBOLS) {
                    zhuyinComposer.append(symbol)
                } else {
                    commitZhuyinBest()
                    currentInputConnection?.commitText(action.text, 1)
                }
                updateManualUi()
            }

            KeyAction.Backspace -> {
                if (zhuyinComposer.hasComposition) {
                    zhuyinComposer.backspace()
                    updateManualUi()
                } else {
                    currentInputConnection?.deleteSurroundingTextInCodePoints(1, 0)
                    updateManualUi()
                }
            }

            KeyAction.Space -> {
                if (!commitZhuyinBest()) {
                    currentInputConnection?.commitText(" ", 1)
                    updateManualUi()
                }
            }

            KeyAction.Enter -> {
                if (!commitZhuyinBest()) {
                    performEnterAction()
                    updateManualUi()
                }
            }

            KeyAction.Shift,
            KeyAction.ToggleJapaneseScript,
            is KeyAction.SwitchLayer -> Unit
        }
    }

    private fun handleJapaneseKey(action: KeyAction) {
        if (!::japaneseComposer.isInitialized) return
        when (action) {
            is KeyAction.InsertText -> {
                if (!japaneseComposer.appendRomaji(action.text)) {
                    commitJapaneseBest()
                    currentInputConnection?.commitText(action.text, 1)
                }
                updateManualUi()
            }

            KeyAction.Backspace -> {
                if (japaneseComposer.hasComposition) {
                    japaneseComposer.backspace()
                    updateManualUi()
                } else {
                    currentInputConnection?.deleteSurroundingTextInCodePoints(1, 0)
                }
            }

            KeyAction.Space -> {
                if (!commitJapaneseBest()) currentInputConnection?.commitText(" ", 1)
            }

            KeyAction.Enter -> {
                if (!commitJapaneseBest()) performEnterAction()
            }

            KeyAction.ToggleJapaneseScript -> {
                japaneseComposer.toggleScriptMode()
                updateManualUi()
            }

            KeyAction.Shift -> Unit
            is KeyAction.SwitchLayer -> Unit
        }
    }

    private fun handleEnglishKey(action: KeyAction) {
        if (!::englishComposer.isInitialized) return
        when (action) {
            is KeyAction.InsertText -> {
                val character = action.text.singleOrNull()
                if (character != null &&
                    (character.isLetter() || character == '\'' || character == '-')
                ) {
                    applyEnglishEdit(englishComposer.inputCharacter(character))
                    keyboardView?.setManualKeyboardState(shift = englishComposer.shiftState)
                } else {
                    applyEnglishEdit(englishComposer.commitWord())
                    currentInputConnection?.commitText(action.text, 1)
                }
            }

            KeyAction.Backspace -> applyEnglishEdit(englishComposer.backspace())
            KeyAction.Space -> applyEnglishEdit(englishComposer.commitWord(" "))
            KeyAction.Enter -> {
                val hadComposition = englishComposer.isComposing
                applyEnglishEdit(englishComposer.commitWord())
                if (!hadComposition) performEnterAction()
            }

            KeyAction.Shift -> {
                val state = englishComposer.pressShift()
                keyboardView?.setManualKeyboardState(shift = state)
                updateManualUi()
            }

            KeyAction.ToggleJapaneseScript,
            is KeyAction.SwitchLayer -> Unit
        }
    }

    override fun onNextKeyboardPressed() {
        commitActiveComposition()
        invalidateVoiceOperation(resetState = true)
        val switched = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P &&
            switchToNextInputMethod(false)
        if (!switched) {
            (getSystemService(INPUT_METHOD_SERVICE) as? InputMethodManager)
                ?.showInputMethodPicker()
        }
    }

    override fun onKeyboardPickerRequested() {
        commitActiveComposition()
        invalidateVoiceOperation(resetState = true)
        (getSystemService(INPUT_METHOD_SERVICE) as? InputMethodManager)
            ?.showInputMethodPicker()
    }

    private fun selectZhuyinCandidate(candidate: String) {
        if (!::zhuyinComposer.isInitialized) return
        // Re-read the cursor context immediately before committing. This makes
        // an associated suffix fail closed if the user moved the cursor after
        // the candidate strip was rendered.
        val selected = rankedZhuyinCandidateObjects()
            .firstOrNull { it.text == candidate }
            ?: return
        val hadComposition = zhuyinComposer.hasComposition
        if (currentInputConnection?.commitText(selected.text, 1) == true) {
            if (personalizationAllowed()) {
                personalization.recordCandidateSelection(
                    LearningLanguage.ZHUYIN,
                    selected.reading,
                    selected.text
                )
            }
            if (hadComposition) zhuyinComposer.clear()
            updateManualUi()
        }
    }

    private fun selectJapaneseCandidate(candidate: String) {
        if (!::japaneseComposer.isInitialized || !japaneseComposer.hasComposition) return
        val reading = japaneseComposer.hiraganaReading ?: japaneseComposer.composition
        val selected = rankedJapaneseCandidates().firstOrNull { it.text == candidate } ?: return
        if (currentInputConnection?.commitText(selected.text, 1) == true) {
            if (personalizationAllowed()) {
                personalization.recordCandidateSelection(
                    LearningLanguage.JAPANESE,
                    reading,
                    selected.text
                )
            }
            japaneseComposer.clear()
            updateManualUi()
        }
    }

    private fun selectEnglishCandidate(candidate: String) {
        if (!::englishComposer.isInitialized || !englishComposer.isComposing) return
        val prefix = englishComposer.currentWord
        val selected = englishComposer.candidates(ENGLISH_CANDIDATE_LIMIT)
            .firstOrNull { it.text == candidate }
            ?: return
        applyEnglishEdit(englishComposer.acceptCandidate(selected, separator = " "))
        if (personalizationAllowed()) {
            personalization.recordCandidateSelection(
                LearningLanguage.ENGLISH,
                prefix,
                selected.text
            )
        }
    }

    private fun commitZhuyinBest(): Boolean {
        if (!::zhuyinComposer.isInitialized || !zhuyinComposer.hasComposition) {
            return false
        }
        val selected = rankedZhuyinCandidates().firstOrNull()
            ?: zhuyinComposer.peekBestOrRaw()?.text
            ?: return false
        if (currentInputConnection?.commitText(selected, 1) == true) {
            zhuyinComposer.clear()
            updateManualUi()
        }
        return true
    }

    private fun commitJapaneseBest(): Boolean {
        if (!::japaneseComposer.isInitialized || !japaneseComposer.hasComposition) {
            return false
        }
        val selected = rankedJapaneseCandidates().firstOrNull()
            ?: japaneseComposer.peekBestOrRaw()
            ?: return false
        if (currentInputConnection?.commitText(selected.text, 1) == true) {
            japaneseComposer.clear()
            updateManualUi()
        }
        return true
    }

    private fun commitEnglishComposition(): Boolean {
        if (!::englishComposer.isInitialized || !englishComposer.isComposing) return false
        applyEnglishEdit(englishComposer.commitWord())
        return true
    }

    private fun commitActiveComposition(): Boolean {
        return when (currentInputMode) {
            KeyboardView.InputMode.ZHUYIN -> commitZhuyinBest()
            KeyboardView.InputMode.JAPANESE -> commitJapaneseBest()
            KeyboardView.InputMode.ENGLISH -> commitEnglishComposition()
            KeyboardView.InputMode.VOICE -> false
        }
    }

    private fun applyEnglishEdit(edit: EnglishEdit) {
        val connection = currentInputConnection ?: return
        when (edit) {
            is EnglishEdit.SetComposingText -> connection.setComposingText(edit.text, 1)
            is EnglishEdit.CommitText -> connection.commitText(edit.text, 1)
            EnglishEdit.ClearComposition -> {
                connection.setComposingText("", 1)
                connection.finishComposingText()
            }

            EnglishEdit.DeleteBeforeCursor ->
                connection.deleteSurroundingTextInCodePoints(1, 0)
            EnglishEdit.NoOp -> Unit
        }
        updateManualUi()
    }

    private fun performEnterAction() {
        inspectVoiceCorrection()
        val inputConnection = currentInputConnection ?: return
        val actionId = currentInputEditorInfo?.imeOptions?.and(EditorInfo.IME_MASK_ACTION)
            ?: EditorInfo.IME_ACTION_NONE
        if (actionId != EditorInfo.IME_ACTION_NONE &&
            actionId != EditorInfo.IME_ACTION_UNSPECIFIED
        ) {
            inputConnection.performEditorAction(actionId)
        } else {
            inputConnection.commitText("\n", 1)
        }
    }

    private fun rankedZhuyinCandidates(): List<String> {
        return rankedZhuyinCandidateObjects().map { it.text }
    }

    private fun rankedZhuyinCandidateObjects(): List<ZhuyinCandidate> {
        if (!::zhuyinComposer.isInitialized) return emptyList()
        val candidates = if (zhuyinComposer.hasComposition) {
            zhuyinComposer.getCandidates(
                limit = ZHUYIN_CANDIDATE_LIMIT,
                includeRawFallback = true
            )
        } else {
            if (!currentLearningDecision.localSuggestionsAllowed) return emptyList()
            val previousText = currentInputConnection?.getTextBeforeCursor(
                ZHUYIN_CONTEXT_CODE_POINTS,
                0
            )?.toString().orEmpty()
            zhuyinComposer.getContextCandidates(
                previousText,
                ZHUYIN_CANDIDATE_LIMIT
            )
        }
        if (candidates.isEmpty()) return emptyList()
        val inputKey = candidates.first().reading
        val rankedTexts = rankCandidates(
            LearningLanguage.ZHUYIN,
            inputKey,
            candidates.map { it.text }
        )
        return rankedTexts.mapNotNull { text ->
            candidates.firstOrNull { it.text == text }
        }
    }

    private fun rankedJapaneseCandidates(): List<JapaneseCandidate> {
        if (!::japaneseComposer.isInitialized) return emptyList()
        val candidates = japaneseComposer.getCandidates(JAPANESE_CANDIDATE_LIMIT)
        val reading = japaneseComposer.hiraganaReading ?: japaneseComposer.composition
        val rankedTexts = rankCandidates(
            LearningLanguage.JAPANESE,
            reading,
            candidates.map { it.text }
        )
        return rankedTexts.mapNotNull { text -> candidates.firstOrNull { it.text == text } }
    }

    private fun rankCandidates(
        language: LearningLanguage,
        inputKey: String,
        candidates: List<String>
    ): List<String> {
        return if (personalizationAllowed()) {
            personalization.rankCandidates(language, inputKey, candidates)
        } else {
            candidates
        }
    }

    private fun buildEnglishCandidates(prefix: String, limit: Int): List<EnglishCandidate> {
        if (prefix.isBlank() || !::dictionaryManager.isInitialized) return emptyList()
        val localTerms = (
            dictionaryManager.getCustomWords() +
                if (::personalization.isInitialized) {
                    personalization.getPromptWords(LearningLanguage.ENGLISH, 50)
                } else {
                    emptyList()
                }
            )
            .asSequence()
            .filter { term ->
                term.length > prefix.length &&
                    term.startsWith(prefix, ignoreCase = true) &&
                    term.all { it.isLetter() || it == '\'' || it == '-' }
            }
            .distinctBy { it.lowercase(Locale.ROOT) }
            .take(limit * 2)
            .toList()
        val ranked = rankCandidates(
            LearningLanguage.ENGLISH,
            prefix,
            localTerms
        )
        return ranked.take(limit).mapIndexed { index, term ->
            EnglishCandidate(text = term, score = ranked.size - index)
        }
    }

    private fun personalizationAllowed(): Boolean =
        ::personalization.isInitialized &&
            personalization.isEnabled() &&
            currentLearningDecision.personalizationAllowed

    private fun updateManualUi() {
        val view = keyboardView ?: return
        when (currentInputMode) {
            KeyboardView.InputMode.VOICE -> view.updateCandidates("", emptyList())
            KeyboardView.InputMode.ZHUYIN -> {
                val composition = if (::zhuyinComposer.isInitialized) {
                    zhuyinComposer.composition
                } else {
                    ""
                }
                view.updateCandidates(composition, rankedZhuyinCandidates())
            }

            KeyboardView.InputMode.JAPANESE -> {
                val composition = if (::japaneseComposer.isInitialized) {
                    view.setJapaneseScriptMode(japaneseComposer.scriptMode)
                    japaneseComposer.composition
                } else {
                    ""
                }
                view.updateCandidates(
                    composition,
                    rankedJapaneseCandidates().map { it.text }
                )
            }

            KeyboardView.InputMode.ENGLISH -> {
                val composition = if (::englishComposer.isInitialized) {
                    englishComposer.currentWord
                } else {
                    ""
                }
                val candidates = if (::englishComposer.isInitialized) {
                    englishComposer.candidates(ENGLISH_CANDIDATE_LIMIT).map { it.text }
                } else {
                    emptyList()
                }
                view.updateCandidates(composition, candidates)
            }
        }
    }

    private fun beginVoiceCorrectionTracking(
        sessionId: Long,
        connection: InputConnection,
        committedText: String
    ) {
        cancelCorrectionTracking()
        if (!personalizationAllowed() || committedText.isBlank()) return
        lastCommittedVoiceText = committedText

        fun tryBegin(): Boolean {
            if (sessionId != inputSessionId) return false
            val snapshot = readBoundedSnapshot(connection) ?: return false
            return voiceCorrectionTracker.begin(
                sessionId = sessionId,
                committedText = committedText,
                afterCommitSnapshot = snapshot,
                learningAllowed = true
            )
        }

        if (!tryBegin()) {
            serviceScope.launch {
                delay(80)
                if (!tryBegin() && sessionId == inputSessionId) {
                    lastCommittedVoiceText = ""
                }
            }
        }
    }

    override fun onUpdateSelection(
        oldSelStart: Int,
        oldSelEnd: Int,
        newSelStart: Int,
        newSelEnd: Int,
        candidatesStart: Int,
        candidatesEnd: Int
    ) {
        super.onUpdateSelection(
            oldSelStart,
            oldSelEnd,
            newSelStart,
            newSelEnd,
            candidatesStart,
            candidatesEnd
        )
        if (currentInputMode == KeyboardView.InputMode.ZHUYIN &&
            ::zhuyinComposer.isInitialized &&
            !zhuyinComposer.hasComposition
        ) {
            updateManualUi()
        }
        if (!personalizationAllowed() ||
            !voiceCorrectionTracker.isTracking(inputSessionId)
        ) {
            return
        }

        correctionInspectionJob?.cancel()
        correctionInspectionJob = serviceScope.launch {
            delay(CORRECTION_DEBOUNCE_MS)
            inspectVoiceCorrection()
        }
    }

    private fun inspectVoiceCorrection() {
        if (!personalizationAllowed()) {
            cancelCorrectionTracking()
            return
        }
        if (::englishComposer.isInitialized &&
            currentInputMode == KeyboardView.InputMode.ENGLISH &&
            englishComposer.isComposing
        ) {
            return
        }
        val snapshot = currentInputConnection?.let(::readBoundedSnapshot) ?: return
        val result = voiceCorrectionTracker.inspect(inputSessionId, snapshot)
        if (result.status != VoiceCorrectionTrackingStatus.CORRECTION_FOUND) return

        val replacement = result.replacement?.let(::expandShortCorrection) ?: return
        val recorded = personalization.recordVoiceCorrection(
            language = LearningLanguage.MIXED,
            wrongText = replacement.wrongText,
            correctedText = replacement.correctedText,
            highConfidence = result.highConfidence
        )
        lastCommittedVoiceText = ""

        if (recorded.status == CorrectionRecordStatus.ACTIVATED) {
            val message = getString(
                R.string.status_learning_saved,
                replacement.wrongText,
                replacement.correctedText
            )
            keyboardView?.setStatusText(message)
            Toast.makeText(applicationContext, message, Toast.LENGTH_SHORT).show()
        }
    }

    /**
     * 單一漢字的全域取代風險太高，因此以語音句中相鄰的穩定字元擴成
     * 短語規則。例如「新義豐公司 → 新義豊公司」，而不是「豐 → 豊」。
     */
    private fun expandShortCorrection(
        replacement: CorrectionReplacement
    ): CorrectionReplacement? {
        val wrongLength = replacement.wrongText.codePointCount(
            0,
            replacement.wrongText.length
        )
        val correctedLength = replacement.correctedText.codePointCount(
            0,
            replacement.correctedText.length
        )
        if (wrongLength >= 2 && correctedLength >= 2) return replacement
        if (lastCommittedVoiceText.isBlank()) return null

        val original = lastCommittedVoiceText.codePoints().toArray()
        val start = replacement.unchangedPrefixCodePoints
        val end = start + wrongLength
        if (start !in 0..original.size || end !in 0..original.size || end < start) {
            return null
        }

        var expandedStart = start
        var expandedEnd = end
        repeat(2) {
            if (expandedStart > 0 && Character.isLetterOrDigit(original[expandedStart - 1])) {
                expandedStart -= 1
            }
            if (expandedEnd < original.size && Character.isLetterOrDigit(original[expandedEnd])) {
                expandedEnd += 1
            }
        }
        if (expandedStart == start && expandedEnd == end) return null

        val left = original.copyOfRange(expandedStart, start).toUnicodeString()
        val right = original.copyOfRange(end, expandedEnd).toUnicodeString()
        return replacement.copy(
            wrongText = left + replacement.wrongText + right,
            correctedText = left + replacement.correctedText + right
        )
    }

    private fun readBoundedSnapshot(connection: InputConnection): BoundedTextSnapshot? {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val surrounding = connection.getSurroundingText(
                SNAPSHOT_SIDE_CODE_POINTS,
                SNAPSHOT_SIDE_CODE_POINTS,
                0
            )
            if (surrounding != null) {
                val text = surrounding.text.toString()
                val selectionStart = surrounding.selectionStart.coerceIn(0, text.length)
                val selectionEnd = surrounding.selectionEnd
                    .coerceIn(selectionStart, text.length)
                return BoundedTextSnapshot(
                    beforeCursor = text.substring(0, selectionStart),
                    selectedText = text.substring(selectionStart, selectionEnd),
                    afterCursor = text.substring(selectionEnd),
                    windowStartOffset = surrounding.offset
                )
            }
        }

        val before = connection.getTextBeforeCursor(
            SNAPSHOT_SIDE_CODE_POINTS,
            0
        )?.toString() ?: return null
        val selected = connection.getSelectedText(0)?.toString().orEmpty()
        val after = connection.getTextAfterCursor(
            SNAPSHOT_SIDE_CODE_POINTS,
            0
        )?.toString() ?: return null
        return BoundedTextSnapshot(
            beforeCursor = before,
            selectedText = selected,
            afterCursor = after
        )
    }

    private fun setState(state: ImeState) {
        currentState = state
        keyboardView?.updateState(state)
    }

    private fun showError(message: String) {
        setState(ImeState.ERROR)
        keyboardView?.setStatusText(message)
    }

    private fun formatElapsed(elapsedMs: Long): String {
        val totalSeconds = elapsedMs / 1_000
        val minutes = totalSeconds / 60
        val seconds = totalSeconds % 60
        return String.format(Locale.ROOT, "%02d:%02d", minutes, seconds)
    }

    private fun IntArray.toUnicodeString(): String = buildString(size) {
        this@toUnicodeString.forEach(::appendCodePoint)
    }
}
