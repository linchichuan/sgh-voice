package com.shingihou.sghvoice.ime

import android.view.View
import android.content.res.Configuration
import android.widget.LinearLayout
import android.graphics.Bitmap
import android.graphics.Canvas
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
import java.io.File
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
    }
}
