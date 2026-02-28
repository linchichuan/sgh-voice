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
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.processing.TranscriptionPipeline
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * SGH Voice 語音輸入法服務
 * 實作 InputMethodService，提供 Push-to-Talk 語音輸入功能
 *
 * 狀態流程：IDLE → RECORDING → PROCESSING → DONE → IDLE
 *                                    ↓
 *                                  ERROR → IDLE
 */
class VoiceInputIME : InputMethodService(), KeyboardView.KeyboardActionListener {

    /** 輸入法狀態 */
    enum class ImeState {
        IDLE,       // 待機中，可開始錄音
        RECORDING,  // 錄音中
        PROCESSING, // 處理中（辨識 + 後處理）
        DONE,       // 完成，結果已輸入
        ERROR       // 發生錯誤
    }

    private var currentState = ImeState.IDLE
    private var keyboardView: KeyboardView? = null

    // 核心元件
    private lateinit var apiConfig: ApiConfig
    private lateinit var audioRecorder: AudioRecorder
    private lateinit var pipeline: TranscriptionPipeline

    // 協程管理
    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var recordingJob: Job? = null
    private var processingJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        initComponents()
    }

    override fun onCreateInputView(): View {
        keyboardView = KeyboardView(this).apply {
            setKeyboardActionListener(this@VoiceInputIME)
            updateState(currentState)
        }
        return keyboardView!!
    }

    override fun onDestroy() {
        serviceScope.cancel()
        audioRecorder.release()
        super.onDestroy()
    }

    // ===== KeyboardActionListener 實作 =====

    /** 麥克風按下 → 開始錄音 */
    override fun onMicPressed() {
        if (currentState != ImeState.IDLE && currentState != ImeState.DONE && currentState != ImeState.ERROR) {
            return
        }

        vibrateShort()
        setState(ImeState.RECORDING)

        recordingJob = serviceScope.launch {
            try {
                audioRecorder.startRecording()
            } catch (e: Exception) {
                setState(ImeState.ERROR)
                keyboardView?.setStatusText(getString(R.string.msg_record_failed) + "${e.message}")
            }
        }
    }

    /** 麥克風放開 → 停止錄音並開始處理 */
    override fun onMicReleased() {
        if (currentState != ImeState.RECORDING) return

        vibrateShort()
        recordingJob?.cancel()

        val wavData = audioRecorder.stopRecording()
        if (wavData == null || wavData.size <= 44) {
            // 錄音太短（只有標頭），回到待機
            setState(ImeState.IDLE)
            keyboardView?.setStatusText(getString(R.string.msg_record_too_short))
            return
        }

        processAudio(wavData)
    }

    /** 退格鍵 → 刪除一個字元 */
    override fun onBackspacePressed() {
        val ic = currentInputConnection ?: return
        ic.deleteSurroundingText(1, 0)
    }

    /** 空白鍵 → 輸入空格 */
    override fun onSpacePressed() {
        val ic = currentInputConnection ?: return
        ic.commitText(" ", 1)
    }

    /** 換行鍵 → 輸入換行或執行編輯器動作 */
    override fun onEnterPressed() {
        val ic = currentInputConnection ?: return
        // 嘗試執行編輯器的預設動作（如送出表單），失敗則輸入換行
        val editorInfo = currentInputEditorInfo
        if (editorInfo != null) {
            val actionId = editorInfo.imeOptions and
                    android.view.inputmethod.EditorInfo.IME_MASK_ACTION
            if (actionId != android.view.inputmethod.EditorInfo.IME_ACTION_NONE) {
                ic.performEditorAction(actionId)
                return
            }
        }
        ic.commitText("\n", 1)
    }

    // ===== 內部方法 =====

    /** 初始化所有核心元件 */
    private fun initComponents() {
        apiConfig = ApiConfig(this)
        audioRecorder = AudioRecorder()

        val whisperClient = WhisperClient(apiConfig)
        val claudeClient = ClaudeClient(apiConfig)
        val dictionaryManager = DictionaryManager(this)
        val openCCConverter = OpenCCConverter()

        pipeline = TranscriptionPipeline(
            whisperClient, claudeClient, dictionaryManager, openCCConverter
        )
    }

    /** 處理錄製的音訊：執行四層管線 */
    private fun processAudio(wavData: ByteArray) {
        setState(ImeState.PROCESSING)

        processingJob = serviceScope.launch {
            val callback = object : TranscriptionPipeline.ProgressCallback {
                override fun onWhisperStarted() {
                    keyboardView?.setStatusText(getString(R.string.msg_recognizing))
                }

                override fun onWhisperCompleted(text: String) {
                    keyboardView?.setStatusText(getString(R.string.msg_post_processing))
                }

                override fun onClaudeStarted() {
                    keyboardView?.setStatusText(getString(R.string.msg_ai_processing))
                }

                override fun onCompleted(result: TranscriptionPipeline.Result) {
                    if (result.success && result.text.isNotBlank()) {
                        // 將結果輸入至目標應用程式
                        commitTextToEditor(result.text)
                        setState(ImeState.DONE)
                    } else if (result.text.isBlank()) {
                        setState(ImeState.IDLE)
                        keyboardView?.setStatusText(getString(R.string.msg_no_speech))
                    } else {
                        setState(ImeState.ERROR)
                        keyboardView?.setStatusText(getString(R.string.msg_process_failed) + "${result.error}")
                    }
                }

                override fun onError(error: String) {
                    setState(ImeState.ERROR)
                    keyboardView?.setStatusText(getString(R.string.msg_error) + "$error")
                }
            }

            pipeline.process(wavData, callback)
        }
    }

    /** 將文字提交至目標輸入框 */
    private fun commitTextToEditor(text: String) {
        val ic = currentInputConnection ?: return
        ic.commitText(text, 1)
    }

    /** 更新輸入法狀態 */
    private fun setState(state: ImeState) {
        currentState = state
        keyboardView?.updateState(state)
    }

    /** 短震動回饋 */
    private fun vibrateShort() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = getSystemService(VIBRATOR_MANAGER_SERVICE) as VibratorManager
                val vibrator = vibratorManager.defaultVibrator
                vibrator.vibrate(VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                val vibrator = getSystemService(VIBRATOR_SERVICE) as Vibrator
                vibrator.vibrate(VibrationEffect.createOneShot(30, VibrationEffect.DEFAULT_AMPLITUDE))
            }
        } catch (_: Exception) {
            // 震動失敗不影響功能
        }
    }
}
