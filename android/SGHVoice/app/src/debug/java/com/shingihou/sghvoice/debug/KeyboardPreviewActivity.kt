package com.shingihou.sghvoice.debug

import android.app.Activity
import android.content.Intent
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.Gravity
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.KeyboardView
import com.shingihou.sghvoice.ime.VoiceInputIME
import java.util.Locale

/**
 * Deterministic visual fixture. Uses the real keyboard view without creating
 * the IME service, reading preferences, requesting audio, or contacting an API.
 * This entire activity and its manifest entry are excluded from release builds.
 */
class KeyboardPreviewActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var keyboard: KeyboardView
    private lateinit var previewDetails: TextView
    private var previewMode = KeyboardView.InputMode.VOICE
    private var previewState = VoiceInputIME.ImeState.RECORDING
    private var previewLevel = 0.6f
    private var stopAtMillis = 0L

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
        header.addView(EditText(this).apply {
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
        }, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        root.addView(header, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        keyboard = KeyboardView(this)
        root.addView(keyboard)
        setContentView(root)
        readPreviewOptions(intent)
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
        keyboard.updateState(previewState)
        previewDetails.text = "DEBUG · synthetic only\nMode: ${previewMode.name.lowercase(Locale.ROOT)} · " +
            "state: ${previewState.name.lowercase(Locale.ROOT)} · level: $previewLevel\n" +
            "Audio feedback stops after 10 seconds."
        if (previewMode == KeyboardView.InputMode.VOICE && previewState == VoiceInputIME.ImeState.RECORDING) {
            stopAtMillis = SystemClock.uptimeMillis() + 10_000L
            handler.post(feedSample)
        }
    }

    override fun onStop() {
        handler.removeCallbacks(feedSample)
        keyboard.setAudioLevel(0f)
        super.onStop()
    }

    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
}
