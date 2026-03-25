package com.shingihou.sghvoice.ime

import android.inputmethodservice.InputMethodService
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import android.view.View
import android.view.inputmethod.EditorInfo
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.audio.AudioRecorder
import com.shingihou.sghvoice.processing.DictionaryManager
import com.shingihou.sghvoice.processing.OpenCCConverter
import com.shingihou.sghvoice.processing.TranscriptionPipeline
import kotlinx.coroutines.*

/**
 * SGH Voice 語音輸入法服務 — 強化診斷與穩定性版本
 */
class VoiceInputIME : InputMethodService(), KeyboardView.KeyboardActionListener {

    companion object {
        private const val TAG = "SGHVoiceIME"
    }

    enum class ImeState { IDLE, RECORDING, PROCESSING, DONE, ERROR }

    private var currentState = ImeState.IDLE
    private var keyboardView: KeyboardView? = null

    private var apiConfig: ApiConfig? = null
    private var audioRecorder: AudioRecorder? = null
    private var pipeline: TranscriptionPipeline? = null

    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    override fun onCreate() {
        Log.d(TAG, "onCreate")
        super.onCreate()
        
        // 嘗試初始化基礎組件
        try {
            apiConfig = ApiConfig(this)
            audioRecorder = AudioRecorder()
            Log.d(TAG, "Base components initialized")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize base components", e)
        }

        // 背景初始化 Pipeline
        preparePipeline()
    }

    override fun onCreateInputView(): View {
        Log.d(TAG, "onCreateInputView")
        // 建立 View 並確保它有正確的佈局參數
        val view = KeyboardView(this).apply {
            setKeyboardActionListener(this@VoiceInputIME)
            updateState(currentState)
        }
        keyboardView = view
        return view
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        Log.d(TAG, "onStartInputView")
        super.onStartInputView(info, restarting)
        keyboardView?.updateState(currentState)
    }

    private fun preparePipeline() {
        serviceScope.launch(Dispatchers.Default) {
            try {
                Log.d(TAG, "Starting pipeline initialization...")
                val config = apiConfig ?: ApiConfig(this@VoiceInputIME)
                val whisperClient = WhisperClient(config)
                val llmClient = LlmClient(config)
                val dictionaryManager = DictionaryManager(this@VoiceInputIME)
                val openCCConverter = OpenCCConverter()

                pipeline = TranscriptionPipeline(
                    whisperClient, llmClient, dictionaryManager, openCCConverter
                )
                Log.d(TAG, "Pipeline initialized successfully")
            } catch (e: Exception) {
                Log.e(TAG, "Pipeline initialization failed", e)
                withContext(Dispatchers.Main) {
                    keyboardView?.setStatusText("初始化錯誤：${e.message}")
                }
            }
        }
    }

    override fun onEvaluateFullscreenMode(): Boolean {
        // 強制不進入全螢幕模式，這樣可以確保鍵盤作為 View 彈出
        return false
    }

    override fun onEvaluateInputViewShown(): Boolean {
        super.onEvaluateInputViewShown()
        // 強制顯示虛擬鍵盤，即使在連接了實體鍵盤的模擬器或裝置上也能顯示
        return true
    }

    override fun onWindowShown() {
        Log.d(TAG, "onWindowShown")
        super.onWindowShown()
    }

    override fun onDestroy() {
        Log.d(TAG, "onDestroy")
        serviceScope.cancel()
        audioRecorder?.release()
        super.onDestroy()
    }

    // ===== KeyboardActionListener 實作 =====

    override fun onMicPressed() {
        Log.d(TAG, "onMicPressed")
        if (currentState == ImeState.PROCESSING) return
        
        val config = apiConfig ?: ApiConfig(this)
        val hasSttKey = if (config.sttEngine == "groq") config.groqApiKey.isNotBlank() else config.openAiApiKey.isNotBlank()
        
        if (!hasSttKey) {
            keyboardView?.setStatusText("請先至 App 設定 API Key")
            return
        }

        vibrateShort()
        setState(ImeState.RECORDING)
        serviceScope.launch {
            try {
                audioRecorder?.startRecording()
            } catch (e: Exception) {
                Log.e(TAG, "Recording failed", e)
                setState(ImeState.ERROR)
                keyboardView?.setStatusText("錄音失敗：${e.message}")
            }
        }
    }

    override fun onMicReleased() {
        Log.d(TAG, "onMicReleased")
        if (currentState != ImeState.RECORDING) return
        vibrateShort()
        
        val wavData = audioRecorder?.stopRecording()
        if (wavData == null || wavData.size <= 44) {
            Log.d(TAG, "Recording too short or null")
            setState(ImeState.IDLE)
            return
        }
        
        processAudio(wavData)
    }

    private fun processAudio(wavData: ByteArray) {
        if (pipeline == null) {
            keyboardView?.setStatusText("系統初始化中，請稍候...")
            serviceScope.launch {
                var retryCount = 0
                while (pipeline == null && retryCount < 50) {
                    delay(100)
                    retryCount++
                }
                if (pipeline != null) {
                    executeTranscription(wavData)
                } else {
                    setState(ImeState.ERROR)
                    keyboardView?.setStatusText("初始化逾時，請重試")
                }
            }
        } else {
            executeTranscription(wavData)
        }
    }

    private fun executeTranscription(wavData: ByteArray) {
        setState(ImeState.PROCESSING)
        serviceScope.launch {
            pipeline?.process(wavData, object : TranscriptionPipeline.ProgressCallback {
                override fun onWhisperStarted() { keyboardView?.setStatusText("語音辨識中...") }
                override fun onWhisperCompleted(text: String) { keyboardView?.setStatusText("後處理中...") }
                override fun onLlmStarted() { keyboardView?.setStatusText("AI 潤稿中...") }
                override fun onCompleted(result: TranscriptionPipeline.Result) {
                    if (result.success && result.text.isNotBlank()) {
                        currentInputConnection?.commitText(result.text, 1)
                        setState(ImeState.DONE)
                    } else {
                        setState(ImeState.ERROR)
                        keyboardView?.setStatusText(if (result.text.isBlank()) "未偵測到語音" else "錯誤：${result.error}")
                    }
                }
                override fun onError(error: String) {
                    setState(ImeState.ERROR)
                    keyboardView?.setStatusText("錯誤：$error")
                }
            })
        }
    }

    override fun onBackspacePressed() {
        currentInputConnection?.deleteSurroundingText(1, 0)
    }

    override fun onSpacePressed() {
        currentInputConnection?.commitText(" ", 1)
    }

    override fun onEnterPressed() {
        val ic = currentInputConnection ?: return
        val editorInfo = currentInputEditorInfo
        if (editorInfo != null) {
            val actionId = editorInfo.imeOptions and EditorInfo.IME_MASK_ACTION
            if (actionId != EditorInfo.IME_ACTION_NONE) {
                ic.performEditorAction(actionId)
                return
            }
        }
        ic.commitText("\n", 1)
    }

    private fun setState(state: ImeState) {
        currentState = state
        keyboardView?.updateState(state)
    }

    private fun vibrateShort() {
        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
            } else {
                @Suppress("DEPRECATION") getSystemService(VIBRATOR_SERVICE) as Vibrator
            }
            vibrator.vibrate(VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE))
        } catch (_: Exception) {}
    }
}
