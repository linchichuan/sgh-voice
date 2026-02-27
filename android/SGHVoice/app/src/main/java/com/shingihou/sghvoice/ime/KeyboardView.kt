package com.shingihou.sghvoice.ime

import android.content.Context
import android.content.res.ColorStateList
import android.util.AttributeSet
import android.view.LayoutInflater
import android.view.MotionEvent
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.shingihou.sghvoice.R

/**
 * 自訂鍵盤視圖
 * 包含大型麥克風按鈕、狀態文字、以及基本功能鍵（退格、空白、換行）
 */
class KeyboardView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : LinearLayout(context, attrs, defStyleAttr) {

    /** 鍵盤事件回呼介面 */
    interface KeyboardActionListener {
        /** 麥克風按下（開始錄音） */
        fun onMicPressed()

        /** 麥克風放開（停止錄音） */
        fun onMicReleased()

        /** 退格鍵按下 */
        fun onBackspacePressed()

        /** 空白鍵按下 */
        fun onSpacePressed()

        /** 換行鍵按下 */
        fun onEnterPressed()
    }

    private var listener: KeyboardActionListener? = null
    private lateinit var micButton: ImageButton
    private lateinit var statusText: TextView
    private lateinit var backspaceButton: TextView
    private lateinit var spaceButton: TextView
    private lateinit var enterButton: TextView

    init {
        LayoutInflater.from(context).inflate(R.layout.keyboard_view, this, true)
        setupViews()
    }

    /** 設定事件監聽器 */
    fun setKeyboardActionListener(listener: KeyboardActionListener) {
        this.listener = listener
    }

    /** 更新狀態文字 */
    fun setStatusText(text: String) {
        statusText.text = text
    }

    /**
     * 更新鍵盤狀態
     * 根據目前狀態改變麥克風按鈕外觀與狀態文字
     */
    fun updateState(state: VoiceInputIME.ImeState) {
        when (state) {
            VoiceInputIME.ImeState.IDLE -> {
                statusText.text = context.getString(R.string.status_idle)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                micButton.isEnabled = true
                micButton.alpha = 1.0f
                micButton.backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(context, R.color.mic_bg))
            }
            VoiceInputIME.ImeState.RECORDING -> {
                statusText.text = context.getString(R.string.status_recording)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_recording))
                micButton.isEnabled = true
                micButton.alpha = 1.0f
                micButton.backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(context, R.color.mic_bg_recording))
            }
            VoiceInputIME.ImeState.PROCESSING -> {
                statusText.text = context.getString(R.string.status_processing)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                micButton.isEnabled = false
                micButton.alpha = 0.5f
                micButton.backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(context, R.color.mic_bg))
            }
            VoiceInputIME.ImeState.DONE -> {
                statusText.text = context.getString(R.string.status_done)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_success))
                micButton.isEnabled = true
                micButton.alpha = 1.0f
                micButton.backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(context, R.color.mic_bg))
            }
            VoiceInputIME.ImeState.ERROR -> {
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_recording))
                micButton.isEnabled = true
                micButton.alpha = 1.0f
                micButton.backgroundTintList = ColorStateList.valueOf(ContextCompat.getColor(context, R.color.mic_bg))
            }
        }
    }

    /** 初始化各視圖元件與事件 */
    @Suppress("ClickableViewAccessibility")
    private fun setupViews() {
        micButton = findViewById(R.id.btn_mic)
        statusText = findViewById(R.id.tv_status)
        backspaceButton = findViewById(R.id.btn_backspace)
        spaceButton = findViewById(R.id.btn_space)
        enterButton = findViewById(R.id.btn_enter)

        // 麥克風按鈕：按住開始錄音，放開停止錄音（Push-to-Talk）
        micButton.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    listener?.onMicPressed()
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    listener?.onMicReleased()
                    true
                }
                else -> false
            }
        }

        // 退格鍵
        backspaceButton.setOnClickListener {
            listener?.onBackspacePressed()
        }

        // 空白鍵
        spaceButton.setOnClickListener {
            listener?.onSpacePressed()
        }

        // 換行鍵
        enterButton.setOnClickListener {
            listener?.onEnterPressed()
        }
    }
}
