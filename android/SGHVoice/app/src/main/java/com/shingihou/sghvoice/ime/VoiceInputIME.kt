package com.shingihou.sghvoice.ime

import android.inputmethodservice.InputMethodService
import android.os.Build
import android.os.SystemClock
import android.util.Log
import android.view.View
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputConnection
import android.text.InputType
import android.view.inputmethod.InputMethodManager
import android.widget.Toast
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.ComposeException
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.audio.AudioRecorder
import com.shingihou.sghvoice.ime.japanese.AndroidJapaneseLexicon
import com.shingihou.sghvoice.ime.japanese.JapaneseCandidate
import com.shingihou.sghvoice.ime.japanese.JapaneseComposer
import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import com.shingihou.sghvoice.ime.manual.EnglishCandidate
import com.shingihou.sghvoice.ime.manual.EnglishCandidateProvider
import com.shingihou.sghvoice.ime.manual.EnglishComposer
import com.shingihou.sghvoice.ime.manual.EnglishEdit
import com.shingihou.sghvoice.ime.manual.LocalEnglishCandidateProvider
import com.shingihou.sghvoice.ime.manual.AndroidEnglishCandidateProvider
import com.shingihou.sghvoice.ime.manual.KeyAction
import com.shingihou.sghvoice.ime.manual.InputCursorMovement
import com.shingihou.sghvoice.ime.manual.ShiftState
import com.shingihou.sghvoice.learning.BoundedTextSnapshot
import com.shingihou.sghvoice.learning.CorrectionRecordStatus
import com.shingihou.sghvoice.learning.LearningLanguage
import com.shingihou.sghvoice.learning.LearningPolicy
import com.shingihou.sghvoice.learning.LearningPolicyDecision
import com.shingihou.sghvoice.learning.PersonalizationRepository
import com.shingihou.sghvoice.learning.VoiceCorrectionTracker
import com.shingihou.sghvoice.learning.VoiceCorrectionTrackingStatus
import com.shingihou.sghvoice.learning.VoiceLearningGate
import com.shingihou.sghvoice.processing.DictionaryManager
import com.shingihou.sghvoice.processing.OpenCCConverter
import com.shingihou.sghvoice.processing.RecognitionLanguage
import com.shingihou.sghvoice.processing.TranslationLanguage
import com.shingihou.sghvoice.processing.TranslationOutput
import com.shingihou.sghvoice.processing.TranslationRequest
import com.shingihou.sghvoice.processing.TranscriptionPipeline
import com.shingihou.sghvoice.processing.VoiceTask
import com.shingihou.sghvoice.processing.VoiceDraftState
import com.shingihou.sghvoice.processing.RetryableVoiceCapture
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
        private const val ZHUYIN_CANDIDATE_LIMIT = 48
        private const val ZHUYIN_CONTEXT_CODE_POINTS = 16
        private const val JAPANESE_CANDIDATE_LIMIT = 24
        private const val ENGLISH_CANDIDATE_LIMIT = 12
        private const val SNAPSHOT_SIDE_CODE_POINTS = 600
        private const val CORRECTION_DEBOUNCE_MS = 450L
        private const val CORRECTION_DEADLINE_MARGIN_MS = 400L
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
    private var voiceActionMode = KeyboardView.VoiceActionMode.DICTATION
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
    private lateinit var englishLexicon: AndroidEnglishCandidateProvider

    private var inputSessionId = 0L
    private var voiceOperationId = 0L
    private var recordingControlJob: Job? = null
    private var recordingTimerJob: Job? = null
    private var transcriptionJob: Job? = null
    private var composeJob: Job? = null
    private var focusCaptureJob: Job? = null
    private val pendingHandoffOperations = mutableSetOf<Pair<Long, Long>>()
    private val drafts = VoiceDraftState()
    private val retryCapture = RetryableVoiceCapture()
    private var draftNotice: Int? = null
    private var clearComposeArmedUntil = 0L
    private var correctionInspectionJob: Job? = null
    private var correctionDeadlineJob: Job? = null
    /** Identifies one voice insertion; evidence from the same turn counts once. */
    private var voiceTurnId = 0L
    private var voiceTurnCounter = 0L
    private val voiceCorrectionTracker = VoiceCorrectionTracker()
    private val recentVoiceContext = com.shingihou.sghvoice.learning.RecentVoiceContext()
    private var lastCommittedVoiceText = ""
    private var currentLearningDecision: LearningPolicyDecision = LearningPolicy.evaluate(null)
    private var activeVoiceTask: VoiceTask = VoiceTask.Dictation
    private var japaneseInputStyle = JapaneseInputStyle.ROMAJI
    private val zhuyinReselection = ZhuyinReselection()
    private var pendingZhuyinLearning: ZhuyinCandidate? = null

    // Snapshot identity: EditorInfo itself is mutable and selection changes are not
    // a new editor. Anonymous fields additionally require the same connection.
    private data class RecordingEditor(
        val packageName: String?, val fieldId: Int, val fieldName: String?,
        val inputType: Int, val imeOptions: Int, val privateOptions: String?
    )
    private var recordingEditor: RecordingEditor? = null
    private var recordingEditorConnection: InputConnection? = null
    private fun recordingEditor(info: EditorInfo?) = info?.let {
        RecordingEditor(it.packageName, it.fieldId, it.fieldName, it.inputType, it.imeOptions, it.privateImeOptions)
    }
    private fun microphoneActive() = currentState == ImeState.STARTING || currentState == ImeState.RECORDING

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
            englishLexicon = AndroidEnglishCandidateProvider(this)
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
            setVoiceActionMode(voiceActionMode)
            setVoicePalette((apiConfig?.voicePalette ?: VoicePalette.MINT).argb)
            setKeyboardHeightPercent(apiConfig?.keyboardHeightPercent ?: KeyboardSizing.DEFAULT_PERCENT)
            setJapaneseInputStyle(japaneseInputStyle)
            updateState(currentState)
            keepScreenOn = microphoneActive()
            setDraftActions(drafts.hasComposeNotes, drafts.hasPendingText && !currentLearningDecision.sensitiveField)
        }
        keyboardView = view
        refreshDraftActions()
        updateManualUi()
        return view
    }

    override fun onStartInput(attribute: EditorInfo?, restarting: Boolean) {
        super.onStartInput(attribute, restarting)
        val incoming = recordingEditor(attribute)
        if (restarting && microphoneActive() && incoming != null &&
            !incoming.packageName.isNullOrBlank() && incoming == recordingEditor &&
            !LearningPolicy.evaluate(attribute).sensitiveField &&
            (incoming.fieldId > 0 || !incoming.fieldName.isNullOrBlank() ||
                (recordingEditorConnection != null && recordingEditorConnection === currentInputConnection))
        ) {
            // A host refresh (restartInput), not a focus loss: keep the capture
            // and its session token. The destination is captured when stopping.
            return
        }
        beginInputSession(attribute)
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        keyboardView?.setInputMode(currentInputMode)
        keyboardView?.setRecognitionLanguage(
            apiConfig?.recognitionLanguage ?: RecognitionLanguage.AUTO
        )
        keyboardView?.setVoiceActionMode(voiceActionMode)
        keyboardView?.setVoicePalette((apiConfig?.voicePalette ?: VoicePalette.MINT).argb)
        keyboardView?.setKeyboardHeightPercent(apiConfig?.keyboardHeightPercent ?: KeyboardSizing.DEFAULT_PERCENT)
        keyboardView?.setJapaneseInputStyle(japaneseInputStyle)
        keyboardView?.updateState(currentState)
        keyboardView?.keepScreenOn = microphoneActive()
        refreshDraftActions()
        showAvailableDraftStatus()
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
        retryCapture.clear()
        drafts.clearCompose()
        drafts.clearPending()
        focusCaptureJob?.cancel()
        pendingHandoffOperations.clear()
        invalidateVoiceOperation(resetState = false)
        composeJob?.cancel()
        finalizeCorrectionTracking(reinspect = false)
        cancelCorrectionTracking()
        serviceScope.cancel()
        audioRecorder?.release()
        keyboardView?.keepScreenOn = false
        recordingEditor = null
        recordingEditorConnection = null
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
            if (::englishLexicon.isInitialized) englishLexicon.warmUp()

            try {
                val config = apiConfig ?: ApiConfig(this@VoiceInputIME)
                val whisperClient = WhisperClient(config)
                // 已生效 learned rules are aliases only while the current field allows personalization.
                val llmClient = LlmClient(config) {
                    dictionaryManager.getSpellingAliases(includeLearned = personalizationAllowed())
                }
                val openCCConverter = OpenCCConverter()
                pipeline = TranscriptionPipeline(
                    whisperClient = whisperClient,
                    llmClient = llmClient,
                    dictionaryManager = dictionaryManager,
                    openCCConverter = openCCConverter,
                    cloudProcessingAllowed = { config.hasCloudProcessingConsent }
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
        // Learn the previous field's final edits (no re-read: the connection is already the new field).
        finalizeCorrectionTracking(reinspect = false)
        preserveSpeechOnFocusLoss()
        inputSessionId += 1
        invalidateVoiceOperation(resetState = true, preserveInFlight = pendingHandoffOperations.isNotEmpty())
        currentLearningDecision = LearningPolicy.evaluate(editorInfo)
        recordingEditor = recordingEditor(editorInfo)
        recordingEditorConnection = currentInputConnection
        resetManualComposers()
        cancelCorrectionTracking()
        updateManualUi()
        refreshDraftActions()
    }

    private fun finishInputSession() {
        finalizeZhuyinSelectionLearning()
        recordingEditor = null
        recordingEditorConnection = null
        finalizeCorrectionTracking(reinspect = true)
        preserveSpeechOnFocusLoss()
        inputSessionId += 1
        invalidateVoiceOperation(resetState = true, preserveInFlight = pendingHandoffOperations.isNotEmpty())
        currentInputConnection?.finishComposingText()
        resetManualComposers()
        cancelCorrectionTracking()
        updateManualUi()
        refreshDraftActions()
    }

    private fun resetManualComposers() {
        pendingZhuyinLearning = null
        zhuyinReselection.clear()
        if (::zhuyinComposer.isInitialized) zhuyinComposer.clear()
        if (::japaneseComposer.isInitialized) japaneseComposer.clear()
        if (::englishComposer.isInitialized) englishComposer.reset()
    }

    private fun cancelCorrectionTracking() {
        correctionInspectionJob?.cancel()
        correctionInspectionJob = null
        correctionDeadlineJob?.cancel()
        correctionDeadlineJob = null
        voiceCorrectionTracker.cancel()
        lastCommittedVoiceText = ""
        recentVoiceContext.clear()
    }

    private fun invalidateVoiceOperation(
        resetState: Boolean,
        preserveInFlight: Boolean = false
    ) {
        val keepHandoff = preserveInFlight || pendingHandoffOperations.isNotEmpty()
        voiceOperationId += 1
        if (!keepHandoff) {
            recordingControlJob?.cancel()
            recordingControlJob = null
        }
        recordingTimerJob?.cancel()
        recordingTimerJob = null
        if (!keepHandoff) {
            transcriptionJob?.cancel()
            transcriptionJob = null
        }
        activeVoiceTask = VoiceTask.Dictation

        if (resetState) {
            setState(ImeState.IDLE)
        }

        val recorder = audioRecorder
        if (recorder != null && !keepHandoff && focusCaptureJob?.isActive != true) {
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

    private fun refreshDraftActions() {
        if (apiConfig?.hasCloudProcessingConsent != true) retryCapture.clear()
        val canShow = !currentLearningDecision.sensitiveField
        keyboardView?.setDraftActions(
            drafts.hasComposeNotes && canShow,
            drafts.hasPendingText && canShow
        )
        keyboardView?.setRetryAvailable(retryCapture.isAvailable && canShow)
        keyboardView?.setDraftPreview(if (canShow) {
            drafts.peekPending()?.text ?: drafts.composeNotes()
        } else "")
    }

    private fun showAvailableDraftStatus() {
        if (currentInputMode != KeyboardView.InputMode.VOICE ||
            currentLearningDecision.sensitiveField
        ) return
        when {
            focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty() ->
                keyboardView?.setStatusText(getString(R.string.voice_pending_processing))
            retryCapture.isAvailable ->
                keyboardView?.setStatusText(getString(R.string.voice_retry_saved))
            draftNotice != null -> keyboardView?.setStatusText(getString(draftNotice!!))
            drafts.hasPendingText ->
                keyboardView?.setStatusText(getString(R.string.voice_pending_saved))
            voiceActionMode == KeyboardView.VoiceActionMode.COMPOSE && drafts.hasComposeNotes ->
                keyboardView?.setStatusText(
                    getString(R.string.voice_compose_ready, drafts.composeSegmentCount)
                )
        }
    }

    private fun isPendingHandoff(sessionId: Long, operationId: Long): Boolean =
        (sessionId to operationId) in pendingHandoffOperations

    private fun rememberCaptureFailure(wav: ByteArray?, task: VoiceTask, personalized: Boolean) {
        val consent = apiConfig?.hasCloudProcessingConsent == true
        val saved = consent && wav != null && retryCapture.retain(wav, task, personalized)
        draftNotice = when {
            !consent -> R.string.msg_cloud_consent_required
            saved -> R.string.voice_retry_saved
            else -> R.string.voice_handoff_failed
        }
        refreshDraftActions()
        if (!currentLearningDecision.sensitiveField) {
            keyboardView?.setStatusText(getString(draftNotice!!))
        }
    }

    /** Android closes the IME on focus loss. Never auto-insert into the new editor. */
    private fun preserveSpeechOnFocusLoss() {
        when (currentState) {
            ImeState.RECORDING -> {
                if (focusCaptureJob?.isActive == true) return
                val recorder = audioRecorder ?: return
                val task = activeVoiceTask
                val includePersonalization = personalizationAllowed()
                recordingTimerJob?.cancel()
                recordingTimerJob = null
                focusCaptureJob = serviceScope.launch {
                    var wav: ByteArray? = null
                    try {
                        wav = recorder.stopRecording()
                        val data = wav
                        if (data == null || data.size < MIN_WAV_SIZE_BYTES) {
                            draftNotice = R.string.msg_record_too_short
                            return@launch
                        }
                        val activePipeline = awaitPipelineForDraft()
                        if (activePipeline == null || apiConfig?.hasCloudProcessingConsent != true) {
                            rememberCaptureFailure(data, task, includePersonalization)
                            return@launch
                        }
                        val result = activePipeline.process(data, task, includePersonalization = includePersonalization)
                        if (!result.success) rememberCaptureFailure(data, task, includePersonalization)
                        else saveInterruptedResult(task, result)
                    } catch (error: CancellationException) {
                        throw error
                    } catch (error: Exception) {
                        Log.w(TAG, "Interrupted voice processing failed")
                        rememberCaptureFailure(wav, task, includePersonalization)
                    } finally {
                        wav?.fill(0)
                        focusCaptureJob = null
                        refreshDraftActions()
                        showAvailableDraftStatus()
                    }
                }
            }

            ImeState.STOPPING,
            ImeState.PROCESSING -> {
                if (composeJob?.isActive != true && focusCaptureJob?.isActive != true) {
                    pendingHandoffOperations += inputSessionId to voiceOperationId
                }
            }

            else -> Unit
        }
    }

    private suspend fun awaitPipelineForDraft(): TranscriptionPipeline? {
        repeat(PIPELINE_WAIT_ATTEMPTS) {
            pipeline?.let { return it }
            delay(PIPELINE_WAIT_INTERVAL_MS)
        }
        return pipeline
    }

    private fun saveInterruptedResult(task: VoiceTask, result: TranscriptionPipeline.Result) {
        if (!result.success || result.text.isBlank()) {
            draftNotice = if (result.success) R.string.msg_no_speech else R.string.voice_handoff_failed
            showAvailableDraftStatus()
            return
        }
        draftNotice = null
        var overflow = false
        val saved = when (task) {
            VoiceTask.Compose -> {
                if (drafts.appendComposeSegment(result.text)) true
                else {
                    overflow = true
                    drafts.savePending(
                        result.text, VoiceDraftState.PendingOrigin.COMPOSE_OVERFLOW
                    )
                }
            }
            VoiceTask.Dictation -> drafts.savePending(
                result.text, VoiceDraftState.PendingOrigin.DICTATION
            )
            is VoiceTask.Translation ->
                drafts.savePending(
                    formatTranslationOutputs(result.translations),
                    VoiceDraftState.PendingOrigin.TRANSLATION
                )
        }
        if (!saved) {
            Log.w(TAG, "Interrupted voice text exceeded the in-memory draft limit")
            draftNotice = R.string.voice_pending_too_long
            showAvailableDraftStatus()
            return
        }
        refreshDraftActions()
        if (!currentLearningDecision.sensitiveField && currentInputMode == KeyboardView.InputMode.VOICE) {
            keyboardView?.setStatusText(
                if (overflow) {
                    getString(R.string.voice_compose_overflow_saved)
                } else if (task == VoiceTask.Compose) {
                    getString(R.string.voice_compose_ready, drafts.composeSegmentCount)
                } else {
                    getString(R.string.voice_pending_saved)
                }
            )
        }
    }

    // ===== KeyboardActionListener =====

    override fun onMicToggle() {
        if (currentLearningDecision.sensitiveField) {
            showError(getString(R.string.msg_voice_disabled_sensitive))
            return
        }
        if (focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty() ||
            composeJob?.isActive == true || drafts.hasPendingText || retryCapture.isAvailable
        ) {
            keyboardView?.setStatusText(getString(
                if (retryCapture.isAvailable) R.string.voice_retry_saved
                else if (drafts.hasPendingText) R.string.voice_pending_saved
                else R.string.voice_pending_processing
            ))
            return
        }
        when (currentState) {
            ImeState.IDLE,
            ImeState.DONE,
            ImeState.ERROR -> {
                finalizeCorrectionTracking(reinspect = true)
                startRecording(
                    if (voiceActionMode == KeyboardView.VoiceActionMode.COMPOSE) {
                        VoiceTask.Compose
                    } else {
                        VoiceTask.Dictation
                    }
                )
            }

            ImeState.RECORDING -> stopRecordingAndProcess()

            ImeState.STARTING,
            ImeState.STOPPING,
            ImeState.PROCESSING -> Unit
        }
    }

    override fun onVoiceActionModeChanged(mode: KeyboardView.VoiceActionMode) {
        if (currentState !in setOf(ImeState.IDLE, ImeState.DONE, ImeState.ERROR)) return
        voiceActionMode = mode
        keyboardView?.setVoiceActionMode(mode)
        keyboardView?.updateState(currentState)
        refreshDraftActions()
        showAvailableDraftStatus()
    }

    override fun onComposeContinue() {
        if (voiceActionMode != KeyboardView.VoiceActionMode.COMPOSE ||
            currentState !in setOf(ImeState.IDLE, ImeState.DONE, ImeState.ERROR)
        ) return
        if (currentLearningDecision.sensitiveField) {
            showError(getString(R.string.msg_voice_disabled_sensitive))
            return
        }
        if (focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty() ||
            composeJob?.isActive == true || drafts.hasPendingText || retryCapture.isAvailable
        ) {
            keyboardView?.setStatusText(getString(
                if (retryCapture.isAvailable) R.string.voice_retry_saved
                else if (drafts.hasPendingText) R.string.voice_pending_saved
                else R.string.voice_pending_processing
            ))
            return
        }
        startRecording(VoiceTask.Compose)
    }

    override fun onComposeClear() {
        if (currentState !in setOf(ImeState.IDLE, ImeState.DONE, ImeState.ERROR)) return
        if (focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty() || retryCapture.isAvailable) {
            keyboardView?.setStatusText(getString(R.string.voice_pending_processing))
            return
        }
        val now = SystemClock.elapsedRealtime()
        if (now > clearComposeArmedUntil) {
            clearComposeArmedUntil = now + 4_000L
            keyboardView?.setStatusText(getString(R.string.voice_compose_clear_confirm))
            return
        }
        clearComposeArmedUntil = 0L
        composeJob?.cancel()
        composeJob = null
        drafts.clearCompose()
        draftNotice = null
        keyboardView?.hideDraftPreview()
        refreshDraftActions()
        keyboardView?.setStatusText(getString(R.string.voice_compose_cleared))
    }

    override fun onComposeGenerate() {
        if (voiceActionMode != KeyboardView.VoiceActionMode.COMPOSE ||
            currentState !in setOf(ImeState.IDLE, ImeState.DONE, ImeState.ERROR) ||
            !drafts.hasComposeNotes
        ) return
        if (drafts.hasPendingText || retryCapture.isAvailable) {
            showAvailableDraftStatus()
            return
        }
        if (focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty()) {
            keyboardView?.setStatusText(getString(R.string.voice_pending_processing))
            return
        }
        if (currentLearningDecision.sensitiveField) {
            showError(getString(R.string.msg_voice_disabled_sensitive))
            return
        }
        val config = apiConfig ?: ApiConfig(this).also { apiConfig = it }
        if (!config.hasCloudProcessingConsent) {
            showError(getString(R.string.msg_cloud_consent_required))
            return
        }
        if (!hasSelectedLlmKey(config)) {
            showError(getString(R.string.voice_compose_requires_model))
            return
        }
        if (currentInputConnection == null) return
        val sessionId = inputSessionId
        val operationId = voiceOperationId
        val notes = drafts.composeNotes()
        setState(ImeState.PROCESSING)
        keyboardView?.setStatusText(getString(R.string.voice_compose_processing))
        composeJob?.cancel()
        composeJob = serviceScope.launch {
            val activePipeline = awaitPipeline(sessionId, operationId) ?: return@launch
            try {
                val draft = activePipeline.composeNotes(notes)
                if (drafts.composeNotes() != notes) return@launch
                // Generated content always requires review and explicit insertion.
                drafts.savePending(draft, VoiceDraftState.PendingOrigin.COMPOSED_DRAFT)
                draftNotice = null
                if (isCurrentOperation(sessionId, operationId)) {
                    setState(ImeState.DONE)
                    keyboardView?.setStatusText(getString(R.string.voice_pending_saved))
                }
                refreshDraftActions()
                if (isCurrentOperation(sessionId, operationId) && !currentLearningDecision.sensitiveField) {
                    keyboardView?.showDraftPreview()
                }
            } catch (error: CancellationException) {
                throw error
            } catch (error: ComposeException) {
                Log.w(TAG, "Writing draft unavailable")
                draftNotice = R.string.voice_compose_failed
                if (isCurrentOperation(sessionId, operationId)) {
                    showError(getString(R.string.voice_compose_failed))
                }
            } catch (error: Exception) {
                Log.e(TAG, "Writing draft failed")
                draftNotice = R.string.voice_compose_failed
                if (isCurrentOperation(sessionId, operationId)) {
                    showError(getString(R.string.voice_compose_failed))
                }
            }
        }
    }

    override fun onPendingInsert() {
        if (focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty() || composeJob?.isActive == true) return
        if (currentLearningDecision.sensitiveField ||
            currentState !in setOf(ImeState.IDLE, ImeState.DONE, ImeState.ERROR)
        ) return
        val pending = drafts.peekPending() ?: return
        val connection = currentInputConnection ?: return
        if (connection.commitText(pending.text, 1)) {
            draftNotice = null
            drafts.clearPending()
            if (pending.origin == VoiceDraftState.PendingOrigin.COMPOSED_DRAFT) {
                drafts.clearCompose()
            }
            refreshDraftActions()
            keyboardView?.hideDraftPreview()
            setState(ImeState.DONE)
        } else {
            showError(getString(R.string.msg_input_connection_lost))
        }
    }

    override fun onPendingDiscard() {
        if (focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty()) return
        if (currentState !in setOf(ImeState.IDLE, ImeState.DONE, ImeState.ERROR)) return
        retryCapture.clear()
        draftNotice = null
        drafts.clearPending()
        keyboardView?.hideDraftPreview()
        refreshDraftActions()
        keyboardView?.setStatusText(getString(R.string.voice_pending_discarded))
    }

    override fun onDraftPreviewRequested() {
        if (currentLearningDecision.sensitiveField) return
        refreshDraftActions()
        keyboardView?.showDraftPreview()
    }

    override fun onPendingRetry() {
        if (currentLearningDecision.sensitiveField || focusCaptureJob?.isActive == true ||
            pendingHandoffOperations.isNotEmpty() || composeJob?.isActive == true ||
            currentState !in setOf(ImeState.IDLE, ImeState.DONE, ImeState.ERROR)
        ) return
        if (apiConfig?.hasCloudProcessingConsent != true) {
            retryCapture.clear()
            draftNotice = R.string.msg_cloud_consent_required
            refreshDraftActions()
            showAvailableDraftStatus()
            return
        }
        val capture = retryCapture.take() ?: return
        draftNotice = null
        setState(ImeState.PROCESSING)
        focusCaptureJob = serviceScope.launch {
            try {
                val activePipeline = awaitPipelineForDraft()
                if (activePipeline == null) {
                    rememberCaptureFailure(capture.wav, capture.task, capture.includePersonalization)
                } else {
                    val result = activePipeline.process(
                        capture.wav, capture.task,
                        includePersonalization = capture.includePersonalization && personalizationAllowed()
                    )
                    if (result.success) saveInterruptedResult(capture.task, result)
                    else rememberCaptureFailure(capture.wav, capture.task, capture.includePersonalization)
                }
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                rememberCaptureFailure(capture.wav, capture.task, capture.includePersonalization)
            } finally {
                capture.wav.fill(0)
                focusCaptureJob = null
                setState(ImeState.IDLE)
                refreshDraftActions()
                showAvailableDraftStatus()
            }
        }
        refreshDraftActions()
    }

    override fun onTranslationPickerRequested() {
        if (focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty() ||
            composeJob?.isActive == true || drafts.hasPendingText || retryCapture.isAvailable
        ) {
            showAvailableDraftStatus()
            return
        }
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
        if (focusCaptureJob?.isActive == true || pendingHandoffOperations.isNotEmpty() ||
            composeJob?.isActive == true || drafts.hasPendingText || retryCapture.isAvailable
        ) {
            keyboardView?.setStatusText(getString(
                if (retryCapture.isAvailable) R.string.voice_retry_saved
                else if (drafts.hasPendingText) R.string.voice_pending_saved
                else R.string.voice_pending_processing
            ))
            return
        }

        val config = apiConfig ?: ApiConfig(this).also { apiConfig = it }
        if (!hasSelectedLlmKey(config)) {
            showError(getString(R.string.msg_missing_translation_key))
            return
        }
        config.translationTargets = request.targets
        finalizeCorrectionTracking(reinspect = true)
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
        draftNotice = null
        keyboardView?.hideDraftPreview()
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
        val includePersonalization = personalizationAllowed()

        val useRecentContext = includePersonalization && apiConfig?.recentVoiceContextEnabled == true

        recordingTimerJob?.cancel()
        recordingTimerJob = null
        setState(ImeState.STOPPING)

        recordingControlJob = serviceScope.launch {
            try {
                val wavData = recorder.stopRecording()
                if (!isCurrentOperation(sessionId, operationId) &&
                    !isPendingHandoff(sessionId, operationId)
                ) {
                    wavData?.fill(0)
                    return@launch
                }

                if (wavData == null || wavData.size < MIN_WAV_SIZE_BYTES) {
                    wavData?.fill(0)
                    if (isPendingHandoff(sessionId, operationId)) draftNotice = R.string.msg_record_too_short
                    pendingHandoffOperations.remove(sessionId to operationId)
                    if (isCurrentOperation(sessionId, operationId)) {
                        setState(ImeState.IDLE)
                        keyboardView?.setStatusText(getString(R.string.msg_record_too_short))
                    }
                    showAvailableDraftStatus()
                    return@launch
                }
                if (targetConnection == null) {
                    rememberCaptureFailure(wavData, task, includePersonalization)
                    wavData.fill(0)
                    pendingHandoffOperations.remove(sessionId to operationId)
                    if (isCurrentOperation(sessionId, operationId)) {
                        showError(getString(R.string.msg_input_connection_lost))
                    }
                    return@launch
                }

                transcribeAndCommit(
                    wavData = wavData,
                    sessionId = sessionId,
                    operationId = operationId,
                    targetConnection = targetConnection,
                    task = task,
                    includePersonalization = includePersonalization,
                    useRecentContext = useRecentContext
                )
            } catch (error: CancellationException) {
                pendingHandoffOperations.remove(sessionId to operationId)
                throw error
            } catch (error: Exception) {
                if (isPendingHandoff(sessionId, operationId)) draftNotice = R.string.voice_handoff_failed
                pendingHandoffOperations.remove(sessionId to operationId)
                if (isCurrentOperation(sessionId, operationId)) {
                    Log.e(TAG, "Unable to stop recording")
                    showError(getString(R.string.msg_record_failed))
                }
                showAvailableDraftStatus()
            }
        }
    }

    private fun transcribeAndCommit(
        wavData: ByteArray,
        sessionId: Long,
        operationId: Long,
        targetConnection: InputConnection,
        task: VoiceTask,
        includePersonalization: Boolean,
        useRecentContext: Boolean = false
    ) {
        if (isCurrentOperation(sessionId, operationId)) setState(ImeState.PROCESSING)
        transcriptionJob = serviceScope.launch {
            val activePipeline = awaitPipeline(sessionId, operationId) ?: run {
                rememberCaptureFailure(wavData, task, includePersonalization)
                pendingHandoffOperations.remove(sessionId to operationId)
                wavData.fill(0)
                refreshDraftActions()
                showAvailableDraftStatus()
                return@launch
            }

            try {
                // Consent can be withdrawn while the user is recording or while
                // the pipeline is warming up. Re-check at the actual upload
                // boundary and destroy the in-memory WAV before returning.
                val config = apiConfig ?: ApiConfig(this@VoiceInputIME).also {
                    apiConfig = it
                }
                if (!config.hasCloudProcessingConsent) {
                    draftNotice = R.string.msg_cloud_consent_required
                    wavData.fill(0)
                    if (isCurrentOperation(sessionId, operationId)) {
                        showError(getString(R.string.msg_cloud_consent_required))
                    }
                    return@launch
                }
                if ((!isCurrentOperation(sessionId, operationId) ||
                    currentInputConnection !== targetConnection) &&
                    !isPendingHandoff(sessionId, operationId)
                ) {
                    wavData.fill(0)
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
                            draftNotice = null
                            if (isPendingHandoff(sessionId, operationId)) {
                                saveInterruptedResult(task, result)
                                return
                            }
                            if (!isCurrentOperation(sessionId, operationId) || currentInputConnection !== targetConnection) return

                            if (task == VoiceTask.Compose) {
                                if (result.success && result.text.isNotBlank()) {
                                    if (drafts.appendComposeSegment(result.text)) {
                                        setState(ImeState.DONE)
                                        keyboardView?.setStatusText(
                                            getString(R.string.voice_compose_ready, drafts.composeSegmentCount)
                                        )
                                        refreshDraftActions()
                                    } else {
                                        if (drafts.savePending(
                                                result.text,
                                                VoiceDraftState.PendingOrigin.COMPOSE_OVERFLOW
                                            )
                                        ) {
                                            setState(ImeState.DONE)
                                            refreshDraftActions()
                                            keyboardView?.setStatusText(
                                                getString(R.string.voice_compose_overflow_saved)
                                            )
                                        } else {
                                            showError(getString(R.string.voice_pending_too_long))
                                        }
                                    }
                                } else {
                                    showError(
                                        if (result.success) getString(R.string.msg_no_speech)
                                        else getString(R.string.msg_process_failed)
                                    )
                                }
                                return
                            }

                            val textToCommit = when (task) {
                                VoiceTask.Dictation -> result.text
                                VoiceTask.Compose -> return
                                is VoiceTask.Translation ->
                                    formatTranslationOutputs(result.translations)
                            }
                            if (result.success && textToCommit.isNotBlank()) {
                                if (targetConnection.commitText(textToCommit, 1)) {
                                    setState(ImeState.DONE)
                                    if (task == VoiceTask.Dictation) {
                                        when (result.refinementStatus) {
                                            LlmClient.RefinementStatus.UNAVAILABLE ->
                                                keyboardView?.setStatusText(getString(R.string.msg_ai_unavailable))
                                            LlmClient.RefinementStatus.REJECTED ->
                                                keyboardView?.setStatusText(getString(R.string.msg_ai_rejected))
                                            else -> Unit
                                        }
                                        // Learning compares edits with the STT-derived baseline, never AI text.
                                        val baseline = VoiceLearningGate.trackingBaseline(task, result)
                                        if (baseline != null) {
                                            beginVoiceCorrectionTracking(
                                                sessionId = sessionId,
                                                connection = targetConnection,
                                                committedText = textToCommit,
                                                sttBaseline = baseline
                                            )
                                        } else {
                                            finalizeCorrectionTracking(reinspect = false)
                                            cancelCorrectionTracking()
                                        }
                                    } else {
                                        // 翻譯不是錯字修正，不能寫入來源語言的學習詞庫。
                                        finalizeCorrectionTracking(reinspect = false)
                                        cancelCorrectionTracking()
                                        // Only the spoken source becomes temporary context, never the translation.
                                        recentVoiceContext.remember(sessionId, result.sourceText,
                                            personalizationAllowed() && apiConfig?.recentVoiceContextEnabled == true)
                                    }
                                } else {
                                    saveInterruptedResult(task, result)
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
                            rememberCaptureFailure(wavData, task, includePersonalization)
                            if (isCurrentOperation(sessionId, operationId)) {
                                if (task is VoiceTask.Translation) {
                                    Log.e(TAG, "Translation failed")
                                }
                                showError(getString(draftNotice ?: R.string.voice_handoff_failed))
                            }
                        }
                    },
                    includePersonalization = includePersonalization,
                    recentContext = {
                        // Executed on the IME main coroutine immediately before LLM processing,
                        // after STT/progress callbacks, never retaining a pre-STT text snapshot.
                        if (useRecentContext && isCurrentOperation(sessionId, operationId) &&
                            currentInputConnection === targetConnection) {
                            recentVoiceContext.get(sessionId, personalizationAllowed() &&
                                apiConfig?.recentVoiceContextEnabled == true)
                        } else ""
                    }
                )
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                rememberCaptureFailure(wavData, task, includePersonalization)
                if (isCurrentOperation(sessionId, operationId)) {
                    Log.e(TAG, "Transcription failed")
                    showError(getString(draftNotice ?: R.string.voice_handoff_failed))
                }
            } finally {
                pendingHandoffOperations.remove(sessionId to operationId)
                wavData.fill(0)
                refreshDraftActions()
                showAvailableDraftStatus()
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
            if (!isCurrentOperation(sessionId, operationId) &&
                !isPendingHandoff(sessionId, operationId)
            ) return null
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
        finalizeZhuyinSelectionLearning()
        zhuyinReselection.clear()
        if (mode == currentInputMode) return

        commitActiveComposition()
        inspectVoiceCorrection()
        preserveSpeechOnFocusLoss()
        invalidateVoiceOperation(resetState = true)
        currentInputMode = mode
        keyboardView?.setInputMode(mode)
        updateManualUi()
        refreshDraftActions()
        showAvailableDraftStatus()
    }

    override fun onKeyAction(action: KeyAction) {
        if (action != KeyAction.Backspace) finalizeZhuyinSelectionLearning()
        pendingZhuyinLearning = null
        zhuyinReselection.clear()
        keyboardView?.setZhuyinReselectAvailable(false)
        if (action is KeyAction.InsertEmoji) {
            insertEmoji(action.text)
            return
        }
        if (action == KeyAction.ToggleEmoji || action == KeyAction.NextEmojiPage) return
        if (action == KeyAction.CursorLeft || action == KeyAction.CursorRight) {
            commitActiveComposition()
            if (currentInputMode == KeyboardView.InputMode.JAPANESE &&
                ::japaneseComposer.isInitialized && japaneseComposer.hasComposition) return
            currentInputConnection?.let { connection ->
                connection.finishComposingText()
                InputCursorMovement.move(connection, toRight = action == KeyAction.CursorRight)
            }
            return
        }
        when (currentInputMode) {
            KeyboardView.InputMode.VOICE -> handleVoiceKey(action)
            KeyboardView.InputMode.ZHUYIN -> handleZhuyinKey(action)
            KeyboardView.InputMode.JAPANESE -> handleJapaneseKey(action)
            KeyboardView.InputMode.ENGLISH -> handleEnglishKey(action)
        }
    }

    override fun onCandidateSelected(candidate: String) {
        if (currentLearningDecision.sensitiveField) return
        when (currentInputMode) {
            KeyboardView.InputMode.ZHUYIN -> selectZhuyinCandidate(candidate)
            KeyboardView.InputMode.JAPANESE -> selectJapaneseCandidate(candidate)
            KeyboardView.InputMode.ENGLISH -> selectEnglishCandidate(candidate)
            KeyboardView.InputMode.VOICE -> Unit
        }
    }

    override fun onZhuyinReselectRequested() {
        if (currentInputMode != KeyboardView.InputMode.ZHUYIN || currentLearningDecision.sensitiveField ||
            !::zhuyinComposer.isInitialized) return
        val reading = zhuyinReselection.restore(currentInputConnection, inputSessionId)
        pendingZhuyinLearning = null
        if (reading != null) zhuyinComposer.setComposition(reading)
        updateManualUi()
    }

    private fun handleVoiceKey(action: KeyAction) {
        when (action) {
            KeyAction.ToggleEmoji, KeyAction.NextEmojiPage, is KeyAction.InsertEmoji -> Unit
            is KeyAction.InsertText -> currentInputConnection?.commitText(action.text, 1)
            KeyAction.Backspace ->
                currentInputConnection?.deleteSurroundingTextInCodePoints(1, 0)
            KeyAction.Space -> currentInputConnection?.commitText(" ", 1)
            KeyAction.Enter -> performEnterAction()
            KeyAction.Shift,
            KeyAction.ToggleJapaneseScript,
            KeyAction.ToggleJapaneseLayout,
            is KeyAction.TapJapaneseKana,
            KeyAction.TransformJapaneseKana,
            KeyAction.FinalizeJapaneseKana,
            KeyAction.CursorLeft,
            KeyAction.CursorRight,
            is KeyAction.SwitchLayer -> Unit
        }
    }

    private fun handleZhuyinKey(action: KeyAction) {
        if (!::zhuyinComposer.isInitialized) return
        when (action) {
            KeyAction.ToggleEmoji, KeyAction.NextEmojiPage, is KeyAction.InsertEmoji -> Unit
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
            KeyAction.ToggleJapaneseLayout,
            is KeyAction.TapJapaneseKana,
            KeyAction.TransformJapaneseKana,
            KeyAction.FinalizeJapaneseKana,
            KeyAction.CursorLeft,
            KeyAction.CursorRight,
            is KeyAction.SwitchLayer -> Unit
        }
    }

    private fun handleJapaneseKey(action: KeyAction) {
        if (!::japaneseComposer.isInitialized) return
        when (action) {
            KeyAction.ToggleEmoji, KeyAction.NextEmojiPage, is KeyAction.InsertEmoji -> Unit
            is KeyAction.InsertText -> {
                val accepted = if (japaneseInputStyle == JapaneseInputStyle.KANA_12_KEY) {
                    japaneseComposer.appendKana(action.text)
                } else {
                    japaneseComposer.appendRomaji(action.text)
                }
                if (!accepted) {
                    commitJapaneseRaw()
                    if (japaneseComposer.hasComposition) return
                    currentInputConnection?.commitText(action.text, 1)
                }
                updateManualUi()
            }

            is KeyAction.TapJapaneseKana -> {
                japaneseComposer.tapKana(action.group, SystemClock.uptimeMillis())
                updateManualUi()
            }

            KeyAction.TransformJapaneseKana -> {
                japaneseComposer.transformLastKana()
                updateManualUi()
            }

            KeyAction.FinalizeJapaneseKana -> japaneseComposer.finalizeKanaTap()

            KeyAction.ToggleJapaneseLayout -> {
                if (japaneseComposer.hasComposition) commitJapaneseRaw()
                if (japaneseComposer.hasComposition) return
                val next = if (japaneseInputStyle == JapaneseInputStyle.ROMAJI) {
                    JapaneseInputStyle.KANA_12_KEY
                } else {
                    JapaneseInputStyle.ROMAJI
                }
                if (japaneseComposer.setInputStyle(next)) {
                    japaneseInputStyle = next
                    keyboardView?.setJapaneseInputStyle(next)
                    updateManualUi()
                }
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
                if (!commitJapaneseRaw()) performEnterAction()
            }

            KeyAction.ToggleJapaneseScript -> {
                japaneseComposer.toggleScriptMode()
                updateManualUi()
            }

            KeyAction.Shift -> Unit
            KeyAction.CursorLeft, KeyAction.CursorRight -> Unit
            is KeyAction.SwitchLayer -> Unit
        }
    }

    private fun handleEnglishKey(action: KeyAction) {
        if (!::englishComposer.isInitialized) return
        when (action) {
            KeyAction.ToggleEmoji, KeyAction.NextEmojiPage, is KeyAction.InsertEmoji -> Unit
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
                applyEnglishEdit(englishComposer.commitWord())
                performEnterAction()
            }

            KeyAction.Shift -> {
                val state = englishComposer.pressShift()
                keyboardView?.setManualKeyboardState(shift = state)
                updateManualUi()
            }

            KeyAction.ToggleJapaneseScript,
            KeyAction.ToggleJapaneseLayout,
            is KeyAction.TapJapaneseKana,
            KeyAction.TransformJapaneseKana,
            KeyAction.FinalizeJapaneseKana,
            KeyAction.CursorLeft,
            KeyAction.CursorRight,
            is KeyAction.SwitchLayer -> Unit
        }
    }

    override fun onNextKeyboardPressed() {
        commitActiveComposition()
        preserveSpeechOnFocusLoss()
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
        preserveSpeechOnFocusLoss()
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
        val originalReading = zhuyinComposer.composition
        finalizeZhuyinSelectionLearning()
        zhuyinReselection.clear()
        if (currentInputConnection?.commitText(selected.text, 1) == true) {
            if (!hadComposition && personalizationAllowed()) {
                personalization.recordCandidateSelection(
                    LearningLanguage.ZHUYIN,
                    selected.reading,
                    selected.text
                )
            }
            if (hadComposition) zhuyinComposer.consumeCandidate(selected)
            if (hadComposition && !currentLearningDecision.sensitiveField) {
                currentInputConnection?.let { zhuyinReselection.remember(it, inputSessionId, originalReading, selected.text) }
                pendingZhuyinLearning = selected
            }
            updateManualUi()
        }
    }

    private fun finalizeZhuyinSelectionLearning() {
        val candidate = pendingZhuyinLearning ?: return
        pendingZhuyinLearning = null
        if (personalizationAllowed() && zhuyinReselection.isAvailable(currentInputConnection, inputSessionId)) {
            personalization.recordCandidateSelection(LearningLanguage.ZHUYIN, candidate.reading, candidate.text)
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
        if (!currentLearningDecision.localSuggestionsAllowed) return
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
        val selected = rankedZhuyinCandidateObjects().firstOrNull { it.source != ZhuyinCandidateSource.HEAD_MATCH }?.text
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

    private fun commitJapaneseRaw(): Boolean {
        if (!::japaneseComposer.isInitialized || !japaneseComposer.hasComposition) return false
        val raw = japaneseComposer.peekRaw() ?: return false
        if (currentInputConnection?.commitText(raw.text, 1) == true) {
            japaneseComposer.clear()
            updateManualUi()
        }
        return true
    }

    private fun insertEmoji(emoji: String) {
        if (currentState in setOf(ImeState.STARTING, ImeState.RECORDING, ImeState.STOPPING, ImeState.PROCESSING)) return
        val connection = currentInputConnection ?: return
        val prefix = when (currentInputMode) {
            KeyboardView.InputMode.JAPANESE -> if (::japaneseComposer.isInitialized) japaneseComposer.peekRaw()?.text.orEmpty() else ""
            KeyboardView.InputMode.ZHUYIN -> if (::zhuyinComposer.isInitialized && zhuyinComposer.hasComposition)
                rankedZhuyinCandidateObjects().firstOrNull { it.source != ZhuyinCandidateSource.HEAD_MATCH }?.text
                    ?: zhuyinComposer.peekBestOrRaw()?.text.orEmpty() else ""
            KeyboardView.InputMode.ENGLISH -> if (::englishComposer.isInitialized) englishComposer.currentWord else ""
            KeyboardView.InputMode.VOICE -> ""
        }
        // One commit keeps a multi-code-point emoji intact. Do not discard the
        // pending word if the editor rejects the write or has lost its connection.
        if (connection.commitText(prefix + emoji, 1)) {
            when (currentInputMode) {
                KeyboardView.InputMode.JAPANESE -> if (::japaneseComposer.isInitialized) japaneseComposer.clear()
                KeyboardView.InputMode.ZHUYIN -> if (::zhuyinComposer.isInitialized) zhuyinComposer.clear()
                KeyboardView.InputMode.ENGLISH -> if (::englishComposer.isInitialized) englishComposer.commitWord()
                KeyboardView.InputMode.VOICE -> Unit
            }
            updateManualUi()
        }
    }

    private fun commitActiveComposition(): Boolean {
        return when (currentInputMode) {
            KeyboardView.InputMode.ZHUYIN -> commitZhuyinBest()
            KeyboardView.InputMode.JAPANESE -> commitJapaneseRaw()
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
        // Enter usually sends or leaves the text: treat the voice turn's edits as final.
        finalizeCorrectionTracking(reinspect = true)
        val inputConnection = currentInputConnection ?: return
        val options = currentInputEditorInfo?.imeOptions ?: EditorInfo.IME_ACTION_NONE
        val actionId = options and EditorInfo.IME_MASK_ACTION
        // Multiline editors can carry an action but explicitly require the
        // keyboard's Enter key to insert a newline instead of invoking it.
        if (options and EditorInfo.IME_FLAG_NO_ENTER_ACTION == 0 &&
            actionId != EditorInfo.IME_ACTION_NONE &&
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
        val inputKey = if (zhuyinComposer.hasComposition) zhuyinComposer.normalizedReading else candidates.first().reading
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
        if (prefix.isBlank() || limit <= 0 || !currentLearningDecision.localSuggestionsAllowed) return emptyList()
        val localTerms = (
            (if (::dictionaryManager.isInitialized && currentLearningDecision.personalizationAllowed)
                dictionaryManager.getCustomWords() else emptyList()) +
                (if (personalizationAllowed()) {
                    personalization.getPromptWords(LearningLanguage.ENGLISH, 50)
                } else {
                    emptyList()
                }) + (if (::englishLexicon.isInitialized) englishLexicon else LocalEnglishCandidateProvider)
                    .candidates(prefix, limit).map { it.text }
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
        view.setZhuyinReselectAvailable(currentInputMode == KeyboardView.InputMode.ZHUYIN &&
            !currentLearningDecision.sensitiveField && zhuyinReselection.isAvailable(currentInputConnection, inputSessionId))
        if (currentLearningDecision.sensitiveField) {
            // Never mirror a password into our plaintext composition/candidate UI.
            view.updateCandidates("", emptyList())
            return
        }
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
                val candidates = if (::englishComposer.isInitialized && currentLearningDecision.localSuggestionsAllowed) {
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
        committedText: String,
        sttBaseline: String
    ) {
        // The previous voice turn ends here; its tracker is already final (re-reading now
        // would see this new insertion).
        finalizeCorrectionTracking(reinspect = false)
        cancelCorrectionTracking()
        if (!personalizationAllowed() || committedText.isBlank()) return
        lastCommittedVoiceText = committedText
        voiceTurnCounter += 1
        val turnId = System.currentTimeMillis() * 1_000L + voiceTurnCounter % 1_000L
        voiceTurnId = turnId

        fun tryBegin(): Boolean {
            if (sessionId != inputSessionId) return false
            val snapshot = readBoundedSnapshot(connection) ?: return false
            val started = voiceCorrectionTracker.begin(
                sessionId = sessionId,
                committedText = committedText,
                afterCommitSnapshot = snapshot,
                learningAllowed = true,
                sttText = sttBaseline
            )
            if (started) {
                recentVoiceContext.remember(sessionId, committedText,
                    apiConfig?.recentVoiceContextEnabled == true)
                scheduleCorrectionDeadline(sessionId, turnId)
            }
            return started
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
        keyboardView?.setZhuyinReselectAvailable(currentInputMode == KeyboardView.InputMode.ZHUYIN &&
            !currentLearningDecision.sensitiveField && zhuyinReselection.isAvailable(currentInputConnection, inputSessionId))
        if (currentInputMode == KeyboardView.InputMode.ENGLISH &&
            ::englishComposer.isInitialized && englishComposer.isComposing &&
            (candidatesStart < 0 || candidatesEnd < 0 ||
                newSelStart != candidatesEnd || newSelEnd != candidatesEnd)
        ) {
            // The host moved the caret, selected text or ended composition. Keep
            // its existing text and selection; never replay the stale word there.
            englishComposer.reset(resetShift = false)
            currentInputConnection?.finishComposingText()
            updateManualUi()
        }
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
        // Observation only: nothing is learned from intermediate editor states (spec 1).
        val result = voiceCorrectionTracker.inspect(inputSessionId, snapshot)
        if (result.originalText != null && result.editedText != null) {
            recentVoiceContext.corrected(inputSessionId, result.originalText, result.editedText)
            lastCommittedVoiceText = result.editedText
        } else if (result.status != VoiceCorrectionTrackingStatus.NO_CHANGE) {
            recentVoiceContext.clear()
        }
    }

    /** Ends tracking at the turn deadline, unless the last edit is too recent to be final. */
    private fun scheduleCorrectionDeadline(sessionId: Long, turnId: Long) {
        correctionDeadlineJob?.cancel()
        correctionDeadlineJob = serviceScope.launch {
            delay(VoiceCorrectionTracker.DEFAULT_SESSION_DURATION_MILLIS - CORRECTION_DEADLINE_MARGIN_MS)
            if (sessionId == inputSessionId && turnId == voiceTurnId &&
                voiceCorrectionTracker.isTracking(sessionId)
            ) {
                finalizeCorrectionTracking(
                    reinspect = true,
                    requireSettledMillis = VoiceCorrectionTracker.SETTLE_MILLIS
                )
            }
        }
    }

    /**
     * Ends the current voice turn and learns its corrections from the final text versus the
     * inserted text. Recent voice context is left as is; callers clear it when appropriate.
     */
    private fun finalizeCorrectionTracking(reinspect: Boolean, requireSettledMillis: Long = 0L) {
        correctionInspectionJob?.cancel()
        correctionInspectionJob = null
        correctionDeadlineJob?.cancel()
        correctionDeadlineJob = null
        if (!personalizationAllowed()) {
            voiceCorrectionTracker.cancel()
            return
        }
        if (reinspect) inspectVoiceCorrection()
        val learned = voiceCorrectionTracker.finish(requireSettledMillis = requireSettledMillis)
        if (learned.isEmpty()) return
        val recorded = learned.mapNotNull { correction ->
            val result = personalization.recordVoiceCorrection(
                LearningLanguage.MIXED,
                correction.replacement,
                correction.highConfidence,
                voiceTurnId,
                correction.scope
            )
            if (result.status == CorrectionRecordStatus.REJECTED) null else correction to result.status
        }
        if (recorded.isEmpty()) return
        val anyActivated = recorded.any { it.second == CorrectionRecordStatus.ACTIVATED }
        val message = if (recorded.size == 1) {
            val (correction, status) = recorded.single()
            getString(
                if (status == CorrectionRecordStatus.ACTIVATED) R.string.status_learning_saved
                else R.string.status_learning_pending,
                correction.replacement.wrongText,
                correction.replacement.correctedText
            )
        } else {
            getString(R.string.status_learning_multiple, recorded.size)
        }
        keyboardView?.setStatusText(getString(
            if (anyActivated) R.string.status_learning_saved_short else R.string.status_learning_pending_short
        ))
        Toast.makeText(applicationContext, message, Toast.LENGTH_SHORT).show()
    }

    private fun readBoundedSnapshot(connection: InputConnection): BoundedTextSnapshot? {
        // Read no more than needed to find this voice insertion, with a hard cap.
        val sideLimit = (lastCommittedVoiceText.codePointCount(0, lastCommittedVoiceText.length) + 24)
            .coerceIn(SNAPSHOT_SIDE_CODE_POINTS, 2_200)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val surrounding = connection.getSurroundingText(
                sideLimit,
                sideLimit,
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
            sideLimit,
            0
        )?.toString() ?: return null
        val selected = connection.getSelectedText(0)?.toString().orEmpty()
        val after = connection.getTextAfterCursor(
            sideLimit,
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
        keyboardView?.keepScreenOn = microphoneActive()
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
}
