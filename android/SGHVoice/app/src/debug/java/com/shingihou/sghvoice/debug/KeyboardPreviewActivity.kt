package com.shingihou.sghvoice.debug

import android.content.Intent
import android.content.res.Configuration
import android.graphics.Typeface
import android.graphics.Rect
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.Gravity
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.ComposeView
import androidx.core.content.ContextCompat
import androidx.core.graphics.ColorUtils
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.KeyboardView
import com.shingihou.sghvoice.ime.VoiceInputIME
import com.shingihou.sghvoice.ime.VoicePalette
import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import com.shingihou.sghvoice.ime.manual.KeyAction
import com.shingihou.sghvoice.processing.RecognitionLanguage
import com.shingihou.sghvoice.processing.TranslationLanguage
import com.shingihou.sghvoice.processing.TranslationRequest
import com.shingihou.sghvoice.ui.VoicePalettePicker
import java.util.Locale

/**
 * Deterministic visual fixture. Uses the real keyboard view without creating
 * the IME service, reading preferences, requesting audio, or contacting an API.
 * This entire activity and its manifest entry are excluded from release builds.
 */
class KeyboardPreviewActivity : ComponentActivity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var keyboard: KeyboardView
    private lateinit var previewDetails: TextView
    private lateinit var previewText: EditText
    private var previewMode = KeyboardView.InputMode.VOICE
    private var previewState = VoiceInputIME.ImeState.RECORDING
    private var previewLevel = 0.6f
    private var stopAtMillis = 0L
    private var lastAction: KeyAction? = null
    private var micActionCount = 0
    private var contractResult = ""
    private var previewPalette = VoicePalette.MINT

    private val feedSample = object : Runnable {
        override fun run() {
            if (SystemClock.uptimeMillis() >= stopAtMillis) {
                keyboard.setAudioLevel(0f)
                keyboard.updateState(VoiceInputIME.ImeState.IDLE)
                previewDetails.text = "Synthetic preview finished · no microphone was used"
                return
            }
            keyboard.setAudioLevel(previewLevel)
            handler.postDelayed(this, 50L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(ContextCompat.getColor(context, R.color.keyboard_bg))
        }
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val top = insets.getInsets(WindowInsetsCompat.Type.statusBars()).top
            view.setPadding(0, top, 0, 0)
            insets
        }
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(28), dp(24), dp(24))
        }
        header.addView(TextView(this).apply {
            text = "Keyboard preview"
            textSize = 24f
            typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
            setTextColor(ContextCompat.getColor(context, R.color.key_text))
        })
        previewDetails = TextView(this).apply {
            textSize = 13f
            setPadding(0, dp(12), 0, dp(20))
            setTextColor(ContextCompat.getColor(context, R.color.keyboard_muted_text))
        }
        header.addView(previewDetails)
        previewText = EditText(this).apply {
            setText("今天整理 GitHub Actions，確認 CI/CD 後再執行 git push。\n\nThis is synthetic preview text.")
            textSize = 18f
            gravity = Gravity.TOP or Gravity.START
            minLines = 5
            showSoftInputOnFocus = false
            isFocusable = false
            setPadding(dp(18), dp(18), dp(18), dp(18))
            setTextColor(ContextCompat.getColor(context, R.color.key_text))
            background = GradientDrawable().apply {
                cornerRadius = dp(16).toFloat()
                setColor(ContextCompat.getColor(context, R.color.keyboard_secondary_bg))
            }
        }
        header.addView(previewText, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        root.addView(header, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        val keyboardContext = createConfigurationContext(Configuration(resources.configuration).apply {
            intent.getStringExtra("locale")?.let { setLocale(Locale.forLanguageTag(it)) }
            val requestedScale = intent.getFloatExtra("fontScale", fontScale)
            if (requestedScale in 0.85f..2f) fontScale = requestedScale
            intent.getIntExtra("heightDp", 0).takeIf { it >= 240 }?.let { screenHeightDp = it }
        })
        keyboard = KeyboardView(keyboardContext)
        keyboard.setKeyboardActionListener(object : KeyboardView.KeyboardActionListener {
            override fun onMicToggle() {
                micActionCount++
                previewState = if (previewState == VoiceInputIME.ImeState.RECORDING) {
                    VoiceInputIME.ImeState.PROCESSING
                } else VoiceInputIME.ImeState.RECORDING
                startPreview()
            }

            override fun onVoiceActionModeChanged(mode: KeyboardView.VoiceActionMode) {
                keyboard.setVoiceActionMode(mode)
            }

            override fun onComposeContinue() = Unit
            override fun onComposeGenerate() = Unit
            override fun onComposeClear() = Unit
            override fun onPendingInsert() = Unit
            override fun onPendingDiscard() = Unit
            override fun onPendingRetry() {
                keyboard.setRetryAvailable(false)
                keyboard.updateState(VoiceInputIME.ImeState.PROCESSING)
            }
            override fun onDraftPreviewRequested() = keyboard.showDraftPreview()

            override fun onTranslationPickerRequested() {
                keyboard.showTranslationPanel(listOf(TranslationLanguage.JAPANESE))
            }

            override fun onTranslationRequested(request: TranslationRequest) {
                previewState = VoiceInputIME.ImeState.RECORDING
                startPreview()
                keyboard.setTranslationRecordingMode()
            }

            override fun onRecognitionLanguageChanged(language: RecognitionLanguage) {
                keyboard.setRecognitionLanguage(language)
            }

            override fun onInputModeChanged(mode: KeyboardView.InputMode) {
                previewMode = mode
                startPreview()
            }

            override fun onKeyAction(action: KeyAction) {
                lastAction = action
                when (action) {
                    is KeyAction.InsertText -> previewText.append(action.text)
                    KeyAction.Space -> previewText.append(" ")
                    KeyAction.Enter -> previewText.append("\n")
                    else -> Unit
                }
            }

            override fun onCandidateSelected(candidate: String) = Unit
            override fun onNextKeyboardPressed() = Unit
            override fun onKeyboardPickerRequested() = Unit
        })
        if (intent.getStringExtra("mode") == "palette") {
            header.setPadding(dp(20), dp(8), dp(20), dp(8))
            (header.getChildAt(0) as TextView).apply {
                text = "Microphone colours · synthetic preview"
                textSize = 18f
            }
            previewDetails.visibility = View.GONE
            previewText.visibility = View.GONE
            header.addView(ComposeView(keyboard.context).apply {
                setContent {
                    var selected by remember {
                        mutableStateOf(VoicePalette.fromPreference(intent.getStringExtra("palette")))
                    }
                    MaterialTheme {
                        VoicePalettePicker(selected) {
                            selected = it
                            previewPalette = it
                            keyboard.setVoicePalette(it.argb)
                        }
                    }
                }
            })
        }
        root.addView(keyboard, LinearLayout.LayoutParams(
            intent.getIntExtra("widthDp", 0).takeIf { it >= 240 }?.let(::dp)
                ?: LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { gravity = Gravity.CENTER_HORIZONTAL })
        setContentView(root)
        readPreviewOptions(intent)
        if (intent.getBooleanExtra("verify", false)) keyboard.post { verifyCircleContract() }
    }

    override fun onStart() {
        super.onStart()
        startPreview()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        readPreviewOptions(intent)
        startPreview()
    }

    private fun readPreviewOptions(intent: Intent) {
        previewPalette = VoicePalette.fromPreference(intent.getStringExtra("palette"))
        previewMode = runCatching {
            KeyboardView.InputMode.valueOf(intent.getStringExtra("mode").orEmpty().uppercase(Locale.ROOT))
        }.getOrDefault(KeyboardView.InputMode.VOICE)
        previewState = runCatching {
            VoiceInputIME.ImeState.valueOf(intent.getStringExtra("state").orEmpty().uppercase(Locale.ROOT))
        }.getOrDefault(VoiceInputIME.ImeState.RECORDING)
        val requestedLevel = intent.getFloatExtra("level", 0.6f)
        previewLevel = if (requestedLevel.isFinite()) requestedLevel.coerceIn(0f, 1f) else 0f
    }

    private fun startPreview() {
        handler.removeCallbacks(feedSample)
        keyboard.setAudioLevel(0f)
        keyboard.setInputMode(previewMode)
        keyboard.setVoicePalette(previewPalette.argb)
        keyboard.setVoiceActionMode(
            if (intent.getStringExtra("task") == "compose") KeyboardView.VoiceActionMode.COMPOSE
            else KeyboardView.VoiceActionMode.DICTATION
        )
        keyboard.setJapaneseInputStyle(
            if (intent.getStringExtra("japaneseStyle") == "kana") JapaneseInputStyle.KANA_12_KEY
            else JapaneseInputStyle.ROMAJI
        )
        val draftKind = intent.getStringExtra("draft")
        keyboard.setDraftActions(draftKind == "notes", draftKind == "pending")
        keyboard.setDraftPreview(if (draftKind in listOf("notes", "pending")) {
            "請寫一則訊息給團隊，說明今天已確認 GitHub Actions 與 CI/CD。\n\n" +
                "請大家更新 Android 測試版，確認日文鍵盤與語音輸入。這是模擬文字，沒有讀取任何個人內容。\n\n" +
                "追加內容：請保持語氣簡潔，完成測試後提供回饋。"
        } else "")
        keyboard.setRetryAvailable(intent.getBooleanExtra("retry", false))
        keyboard.updateState(previewState)
        if (intent.getBooleanExtra("preview", false)) keyboard.showDraftPreview()
        if (intent.getBooleanExtra("translation", false)) {
            keyboard.showTranslationPanel(listOf(TranslationLanguage.JAPANESE))
        }
        if (previewMode == KeyboardView.InputMode.ZHUYIN) {
            keyboard.updateCandidates("ㄕㄢ", listOf("刪", "山", "衫", "珊", "刪除", "刪掉", "刪減"))
        }
        when (intent.getStringExtra("learning")) {
            "pending" -> keyboard.setStatusText(keyboard.context.getString(R.string.status_learning_pending_short))
            "saved" -> keyboard.setStatusText(keyboard.context.getString(R.string.status_learning_saved_short))
        }
        previewDetails.text = "DEBUG · synthetic only\nMode: ${previewMode.name.lowercase(Locale.ROOT)} · " +
            "state: ${previewState.name.lowercase(Locale.ROOT)} · level: $previewLevel\n" +
            "Audio feedback stops after 10 seconds.\n$contractResult"
        if (previewMode == KeyboardView.InputMode.VOICE && previewState == VoiceInputIME.ImeState.RECORDING) {
            stopAtMillis = SystemClock.uptimeMillis() + 10_000L
            handler.post(feedSample)
        }
    }

    /** Device-side checks of visible geometry and the real View action surface. */
    private fun verifyCircleContract() {
        contractResult = runCatching {
            keyboard.setInputMode(KeyboardView.InputMode.VOICE)
            val control = keyboard.findViewById<View>(R.id.btn_mic)
            val waveform = keyboard.findViewById<View>(R.id.audio_waveform)
            val label = keyboard.findViewById<TextView>(R.id.mic_action_label)
            val status = keyboard.findViewById<TextView>(R.id.tv_status)
            VoicePalette.entries.forEach {
                keyboard.setVoicePalette(it.argb)
                check(ColorUtils.calculateContrast(label.currentTextColor, it.argb) >= 4.5) {
                    "Palette caption contrast is below 4.5:1"
                }
            }
            val config = keyboard.context.resources.configuration
            val heightFraction = if (keyboard.width >= dp(600) && config.screenHeightDp < 500) 0.72f else 0.80f
            check(keyboard.height <= dp((config.screenHeightDp * heightFraction).toInt()) + dp(2)) {
                "Keyboard exceeds the window height budget"
            }
            check(control.width == control.height && control.width >= dp(84)) { "Control must remain circular and touchable" }
            check(waveform.parent === control) { "Audio feedback must be inside the control" }
            check(waveform.width <= control.width && waveform.height <= control.height) { "Feedback outside circle" }
            check(label.layout.height <= label.height) { "Action caption is vertically clipped" }
            check((0 until label.lineCount).all { label.layout.getLineWidth(it) <= label.width }) { "Action caption is horizontally clipped" }
            check(status.layout.height <= status.height) { "Recording status is vertically clipped" }
            listOf(VoiceInputIME.ImeState.STARTING, VoiceInputIME.ImeState.STOPPING, VoiceInputIME.ImeState.PROCESSING).forEach {
                keyboard.updateState(it)
                check(!control.isEnabled) { "Busy state must not accept another recording action" }
                check(waveform.visibility != View.VISIBLE) { "Busy state must not pretend to capture sound" }
            }
            previewState = VoiceInputIME.ImeState.RECORDING
            keyboard.updateState(previewState)
            val beforeTap = micActionCount
            check(control.performClick())
            check(micActionCount == beforeTap + 1) { "One tap must produce one mic action" }
            check(previewState == VoiceInputIME.ImeState.PROCESSING)
            listOf(R.id.btn_layer to "、", R.id.btn_comma to "，", R.id.btn_period to "。").forEach { (id, text) ->
                keyboard.findViewById<View>(id).performClick()
                check(lastAction == KeyAction.InsertText(text)) { "Punctuation inserts wrong text" }
            }
            keyboard.updateState(VoiceInputIME.ImeState.IDLE)
            control.performLongClick()
            check(keyboard.findViewById<View>(R.id.voice_capture_area).visibility == View.GONE)
            check(keyboard.findViewById<View>(R.id.translation_panel).visibility == View.VISIBLE)
            keyboard.findViewById<View>(R.id.btn_translation_cancel).performClick()
            check(control.visibility == View.VISIBLE && control.isEnabled)
            val bottom = keyboard.findViewById<View>(R.id.voice_action_row)
            val visible = Rect()
            check(bottom.getGlobalVisibleRect(visible) && visible.height() == bottom.height) {
                "Bottom actions are clipped"
            }
            "PASS: 6 palette contrasts / circle / busy states / single tap / 、，。 / translation / bottom controls / " +
                "height ${keyboard.height}px of ${dp(config.screenHeightDp)}px"
        }.getOrElse { "FAIL: ${it.message}" }
        Log.i("KeyboardPreview", contractResult)
        readPreviewOptions(intent)
        startPreview()
    }

    override fun onStop() {
        handler.removeCallbacks(feedSample)
        keyboard.setAudioLevel(0f)
        super.onStop()
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}
