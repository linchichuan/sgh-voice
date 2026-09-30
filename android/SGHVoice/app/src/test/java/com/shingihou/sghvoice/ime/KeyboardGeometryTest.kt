package com.shingihou.sghvoice.ime

import android.view.View
import android.content.res.Configuration
import android.widget.LinearLayout
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.InsetDrawable
import android.widget.TextView
import android.widget.ImageView
import android.view.Gravity
import android.util.TypedValue
import androidx.core.graphics.Insets
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import com.shingihou.sghvoice.ime.manual.KeyboardLayer
import com.shingihou.sghvoice.ime.manual.ShiftState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.shadows.ShadowSystemClock
import java.io.File
import java.time.Duration
import java.util.Locale

/** Measures the production View, not a duplicate model of its layout. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h852dp-xxhdpi")
class KeyboardGeometryTest {
    private fun measure(view: KeyboardView, widthDp: Int = 393, heightDp: Int = 852): Int {
        val density = view.resources.displayMetrics.density
        view.measure(
            View.MeasureSpec.makeMeasureSpec((widthDp * density).toInt(), View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec((heightDp * density).toInt(), View.MeasureSpec.AT_MOST)
        )
        view.layout(0, 0, view.measuredWidth, view.measuredHeight)
        return view.measuredHeight
    }

    @Test fun `all input modes keep the same height as zhuyin`() {
        val view = KeyboardView(RuntimeEnvironment.getApplication())
        view.setInputMode(KeyboardView.InputMode.ZHUYIN)
        val reference = measure(view)
        assertEquals((372 * view.resources.displayMetrics.density).toInt(), reference)
        KeyboardView.InputMode.entries.forEach { mode ->
            view.setInputMode(mode)
            assertEquals("Mode $mode must not move the host text field", reference, measure(view))
        }
        view.setInputMode(KeyboardView.InputMode.JAPANESE)
        view.setJapaneseInputStyle(JapaneseInputStyle.KANA_12_KEY)
        assertEquals(reference, measure(view))
    }

    @Test fun `height setting applies equally and resets without shrinking English keys`() {
        val view = KeyboardView(RuntimeEnvironment.getApplication())
        for (percent in listOf(90, 95, 100, 110, 125, 100)) {
            view.setKeyboardHeightPercent(percent)
            val expected = (KeyboardSizing.heightDp(percent) * view.resources.displayMetrics.density).toInt()
            KeyboardView.InputMode.entries.forEach { mode ->
                view.setInputMode(mode)
                assertEquals("$mode $percent", expected, measure(view))
            }
            val rows = view.findViewById<LinearLayout>(R.id.manual_key_rows)
            val heights = (0 until rows.childCount).map { rows.getChildAt(it).height }
            assertTrue(heights.max() - heights.min() <= 1)
            assertTrue(heights.min() >= 44 * view.resources.displayMetrics.density)
            assertEquals(rows.height, heights.sum())
        }
    }

    @Test fun `symbols expanded candidates and recording state preserve footprint`() {
        val view = KeyboardView(RuntimeEnvironment.getApplication())
        val expected = measure(view)
        VoiceInputIME.ImeState.entries.forEach { state ->
            view.updateState(state)
            view.setDraftActions(true, true)
            assertEquals(state.toString(), expected, measure(view))
        }
        view.setInputMode(KeyboardView.InputMode.ZHUYIN)
        KeyboardLayer.entries.forEach { layer ->
            view.setManualKeyboardState(layer, ShiftState.OFF)
            assertEquals(layer.toString(), expected, measure(view))
        }
        view.updateCandidates("ㄓ", List(20) { "候選$it" })
        view.findViewById<View>(R.id.btn_expand_candidates).performClick()
        assertEquals(expected, measure(view))
    }

    @Test fun `short landscape and large fonts use a mode independent screen cap`() {
        val app = RuntimeEnvironment.getApplication()
        val context = app.createConfigurationContext(Configuration(app.resources.configuration).apply {
            screenHeightDp = 360
            screenWidthDp = 800
            fontScale = 1.5f
        })
        val view = KeyboardView(context)
        val expected = (288 * view.resources.displayMetrics.density).toInt()
        KeyboardView.InputMode.entries.forEach { mode ->
            view.setInputMode(mode)
            assertEquals(mode.toString(), expected, measure(view, 800, 360))
        }
    }

    @Test fun `navigation bar inset adds the same space to every mode`() {
        val view = KeyboardView(RuntimeEnvironment.getApplication())
        val baseline = measure(view)
        ViewCompat.dispatchApplyWindowInsets(view, WindowInsetsCompat.Builder()
            .setInsets(WindowInsetsCompat.Type.navigationBars(), Insets.of(0, 0, 0, 72)).build())
        KeyboardView.InputMode.entries.forEach { mode ->
            view.setInputMode(mode)
            assertEquals(baseline + 72, measure(view))
        }
    }

    @Test fun `normal typing restores overlapping touch dispatch after flick mode`() {
        val view = KeyboardView(RuntimeEnvironment.getApplication())
        view.setInputMode(KeyboardView.InputMode.JAPANESE)
        view.setJapaneseInputStyle(JapaneseInputStyle.KANA_12_KEY)
        assertTrue(!view.isMotionEventSplittingEnabled)
        view.setInputMode(KeyboardView.InputMode.ENGLISH)
        assertTrue(view.isMotionEventSplittingEnabled)
        val rows = view.findViewById<LinearLayout>(R.id.manual_key_rows)
        assertTrue(rows.isMotionEventSplittingEnabled)
        for (index in 0 until rows.childCount) {
            assertTrue((rows.getChildAt(index) as LinearLayout).isMotionEventSplittingEnabled)
        }
    }

    @Test fun `voice oval stays broad and task cards stay at opposite edges across phone sizes`() {
        val app = RuntimeEnvironment.getApplication()
        for (widthDp in listOf(320, 393, 480, 800)) {
            for (fontScale in listOf(1f, 1.5f)) {
                val heightDp = if (widthDp == 800) 360 else 852
                val context = app.createConfigurationContext(Configuration(app.resources.configuration).apply {
                    screenWidthDp = widthDp
                    screenHeightDp = heightDp
                    this.fontScale = fontScale
                    setLocale(Locale.ENGLISH)
                })
                val view = KeyboardView(context)
                view.setKeyboardHeightPercent(90)
                view.updateState(VoiceInputIME.ImeState.RECORDING)
                view.setRecordingElapsed("00:02")
                measure(view, widthDp, heightDp)
                val density = view.resources.displayMetrics.density
                val oval = view.findViewById<View>(R.id.btn_mic)
                val taskRow = view.findViewById<View>(R.id.voice_task_switch)
                val leftTask = view.findViewById<View>(R.id.btn_voice_dictation)
                val rightTask = view.findViewById<View>(R.id.btn_voice_compose)
                assertTrue("Oval is too narrow at $widthDp dp / $fontScale", oval.width >= view.width * 2 / 3)
                assertTrue("Oval must be wider than tall", oval.width > oval.height)
                assertTrue(oval.height >= 48 * density)
                assertEquals(0, leftTask.left)
                assertEquals(taskRow.width, rightTask.right)
                assertTrue(rightTask.left - leftTask.right >= 8 * density)
                assertTrue(leftTask.height >= 44 * density && rightTask.height >= 44 * density)
                val caption = view.findViewById<TextView>(R.id.mic_action_label)
                assertTrue("Caption clipped at $widthDp dp / $fontScale", caption.layout.height <= caption.height)
                val status = view.findViewById<TextView>(R.id.tv_status)
                assertTrue(status.text.contains("00:02"))
                assertTrue(status.layout.height <= status.height)
            }
        }
    }

    @Test fun `voice utility keys paint one third shorter while preserving touch height`() {
        val view = KeyboardView(RuntimeEnvironment.getApplication())
        measure(view)
        val density = view.resources.displayMetrics.density
        for (id in listOf(R.id.btn_layer, R.id.btn_comma, R.id.btn_space,
            R.id.btn_period, R.id.btn_backspace, R.id.btn_enter)) {
            val key = view.findViewById<View>(id)
            val background = key.background as InsetDrawable
            background.bounds = android.graphics.Rect(0, 0, key.width, key.height)
            val padding = android.graphics.Rect()
            background.getPadding(padding)
            assertTrue(key.height >= 48 * density)
            assertEquals((16 * density).toInt(), padding.top + padding.bottom)
        }
    }

    @Test fun `company logo and larger brand share the toolbar centre without crowding tabs`() {
        val app = RuntimeEnvironment.getApplication()
        for (widthDp in listOf(280, 320, 393, 480)) {
            for (fontScale in listOf(1f, 1.5f)) {
                val context = app.createConfigurationContext(Configuration(app.resources.configuration).apply {
                    screenWidthDp = widthDp
                    this.fontScale = fontScale
                })
                val view = KeyboardView(context)
                measure(view, widthDp)
                val group = view.findViewById<LinearLayout>(R.id.keyboard_brand_group)
                val logo = view.findViewById<ImageView>(R.id.keyboard_company_logo)
                val brand = view.findViewById<TextView>(R.id.tv_keyboard_brand)
                val tabs = view.findViewById<View>(R.id.mode_group)
                assertTrue(logo.drawable != null)
                assertEquals(Gravity.CENTER, group.gravity)
                assertEquals(tabs.top + tabs.height / 2, group.top + group.height / 2)
                assertTrue(group.right <= tabs.left)
                assertEquals("Logo and SGH must be adjacent", logo.right, brand.left)
                assertTrue("The combined brand must be centred",
                    kotlin.math.abs(logo.left + brand.right - group.width) <= 1)
                assertTrue(brand.right <= group.width)
                assertTrue(brand.layout.getEllipsisCount(0) == 0)
                assertTrue(brand.layout.getLineWidth(0) <= brand.width)
                if (widthDp >= 393 && fontScale == 1f) {
                    assertEquals(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP,
                        22f, context.resources.displayMetrics), brand.textSize, 0.1f)
                }
            }
        }
    }

    @Test @GraphicsMode(GraphicsMode.Mode.NATIVE)
    fun `live waves do not paint a dark wash over the light surface`() {
        val view = AudioWaveformView(RuntimeEnvironment.getApplication())
        view.layout(0, 0, 600, 300)
        view.setRecordingActive(true)
        repeat(12) {
            ShadowSystemClock.advanceBy(Duration.ofMillis(50))
            view.setAudioLevel(1f)
        }
        val bitmap = Bitmap.createBitmap(600, 300, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(bitmap))
        // Wave movement is limited to the upper half. The rest must stay clear
        // so loud audio cannot tint the parent's pastel gradient grey.
        for (x in listOf(150, 300, 450)) {
            assertEquals(0, android.graphics.Color.alpha(bitmap.getPixel(x, 210)))
        }
        bitmap.recycle()
    }

    @Test fun `voice task cards initialize selected state and paint 28dp inside 44dp targets`() {
        val view = KeyboardView(RuntimeEnvironment.getApplication())
        measure(view)
        val density = view.resources.displayMetrics.density
        val dictation = view.findViewById<View>(R.id.btn_voice_dictation)
        val compose = view.findViewById<View>(R.id.btn_voice_compose)
        assertTrue(dictation.isSelected && !compose.isSelected)
        for (mode in KeyboardView.VoiceActionMode.entries) {
            view.setVoiceActionMode(mode)
            for (task in listOf(dictation, compose)) {
                val background = task.background as InsetDrawable
                background.bounds = android.graphics.Rect(0, 0, task.width, task.height)
                val padding = android.graphics.Rect()
                background.getPadding(padding)
                assertEquals((44 * density).toInt(), task.height)
                assertEquals((28 * density).toInt(), task.height - padding.top - padding.bottom)
            }
        }
    }

    @Test @GraphicsMode(GraphicsMode.Mode.NATIVE)
    fun `render synthetic keyboard visual evidence`() {
        val app = RuntimeEnvironment.getApplication()
        val context = app.createConfigurationContext(Configuration(app.resources.configuration).apply {
            setLocale(Locale.forLanguageTag("zh-TW"))
        })
        val view = KeyboardView(context)
        val output = File("build/reports/keyboard-preview").apply { mkdirs() }
        view.setVoicePalette(VoicePalette.MINT.argb)
        KeyboardView.InputMode.entries.forEach { mode ->
            view.setInputMode(mode)
            if (mode == KeyboardView.InputMode.JAPANESE) view.setJapaneseInputStyle(JapaneseInputStyle.KANA_12_KEY)
            measure(view)
            val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
            view.draw(Canvas(bitmap))
            File(output, "${mode.name.lowercase()}-100.png").outputStream().use {
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
            }
            bitmap.recycle()
        }
        view.setInputMode(KeyboardView.InputMode.VOICE)
        view.updateState(VoiceInputIME.ImeState.RECORDING)
        view.setRecordingElapsed("00:02")
        repeat(12) {
            ShadowSystemClock.advanceBy(Duration.ofMillis(50))
            view.setAudioLevel(0.75f)
        }
        measure(view)
        val recording = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(recording))
        File(output, "voice-recording-100.png").outputStream().use {
            recording.compress(Bitmap.CompressFormat.PNG, 100, it)
        }
        recording.recycle()
    }
}
