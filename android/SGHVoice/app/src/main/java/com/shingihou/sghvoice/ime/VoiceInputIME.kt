package com.shingihou.sghvoice.ime

import android.inputmethodservice.InputMethodService
import android.os.Vibrator
import android.os.VibratorManager
import android.os.Build
import android.os.VibrationEffect
import android.view.View
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.api.ClaudeClient
import com.shingihou.sghvoice.api.WhisperClient
import com.shingihou.sghvoice.audio.AudioRecorder
import com.shingihou.sghvoice.processing.DictionaryManager
import com.shingihou.sghvoice.processing.OpenCCConverter
import com.shingihou.sghvoice.processing.TranscriptionPipeline
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * SGH Voice 語音輸入法服務
 */
class VoiceInputIME : InputMethodService(), KeyboardView.KeyboardActionListener {

    enum class ImeState { IDLE, RECORDING, PROCESSING, DONE, ERROR }

    private var currentState = ImeState.IDLE
    private var keyboardView: KeyboardView? = null

    // 延遲初始化的核心元件
    private lateinit var apiConfig: ApiConfig
    private lateinit var audioRecorder: AudioRecorder
    private lateinit var pipeline: TranscriptionPipeline

    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    override fun onCreate() {
        super.onCreate()
        // 核心配置初始化
        apiConfig = ApiConfig(this)
        audioRecorder = AudioRecorder()
        
        // 將耗時的 Pipeline 初始化移到協程中
        serviceScope.launch(Dispatchers.Default) {
            val whisperClient = WhisperClient(apiConfig)
            val claudeClient = ClaudeClient(apiConfig)
            val dictionaryManager = DictionaryManager(this@VoiceInputIME)
            val openCCConverter = OpenCCConverter()

            pipeline = TranscriptionPipeline(
                whisperClient, claudeClient, dictionaryManager, openCCConverter
            )
        }
    }

    override fun onCreateInputView(): View {
        // 每次重新建立 View 確保 UI 更新
        keyboardView = KeyboardView(this).apply {
            setKeyboardActionListener(this@VoiceInputIME)
            updateState(currentState)
        }
        return keyboardView!!
    }

    // 當輸入法視圖顯示時刷新狀態
    override fun onStartInputView(info: android.view.inputmethod.EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        keyboardView?.updateState(currentState)
    }

    override fun onDestroy() {
        serviceScope.cancel()
        audioRecorder.release()
        super.onDestroy()
    }

    // ===== KeyboardActionListener =====

    override fun onMicPressed() {
        if (currentState == ImeState.PROCESSING) return
        vibrateShort()
        setState(ImeState.RECORDING)
        serviceScope.launch {
            try {
                audioRecorder.startRecording()
            } catch (e: Exception) {
                setState(ImeState.ERROR)
                keyboardView?.setStatusText("錄音失敗：${e.message}")
            }
        }
    }

    override fun onMicReleased() {
        if (currentState != ImeState.RECORDING) return
        vibrateShort()
        val wavData = audioRecorder.stopRecording()
        if (wavData == null || wavData.size <= 44) {
            setState(ImeState.IDLE)
            return
        }
        processAudio(wavData)
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
            val actionId = editorInfo.imeOptions and android.view.inputmethod.EditorInfo.IME_MASK_ACTION
            if (actionId != android.view.inputmethod.EditorInfo.IME_ACTION_NONE) {
                ic.performEditorAction(actionId)
                return
            }
        }
        ic.commitText("\n", 1)
    }

    private fun processAudio(wavData: ByteArray) {
        setState(ImeState.PROCESSING)
        serviceScope.launch {
            pipeline.process(wavData, object : TranscriptionPipeline.ProgressCallback {
                override fun onWhisperStarted() { keyboardView?.setStatusText("語音辨識中...") }
                override fun onWhisperCompleted(text: String) { keyboardView?.setStatusText("後處理中...") }
                override fun onClaudeStarted() { keyboardView?.setStatusText("AI 潤稿中...") }
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

    private fun setState(state: ImeState) {
        currentState = state
        keyboardView?.updateState(state)
    }

    private fun vibrateShort() {
        val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager).defaultVibrator
        } else {
            @Suppress("DEPRECATION") getSystemService(VIBRATOR_SERVICE) as Vibrator
        }
        vibrator.vibrate(VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE))
    }
}
