package com.shingihou.sghvoice.ime

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.drawable.RippleDrawable
import android.app.Activity
import android.view.View
import android.widget.LinearLayout
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import com.shingihou.sghvoice.ime.manual.KeyAction
import com.shingihou.sghvoice.ime.manual.KeyboardLayer
import com.shingihou.sghvoice.ime.manual.ShiftState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Robolectric
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.robolectric.shadows.ShadowLooper
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h852dp-xxhdpi")
class KeyboardInteractionTest {
    private fun measure(keyboard: KeyboardView, widthDp: Int = 393): Int {
        val density = keyboard.resources.displayMetrics.density
        keyboard.measure(
            View.MeasureSpec.makeMeasureSpec((widthDp * density).toInt(), View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec((852 * density).toInt(), View.MeasureSpec.AT_MOST)
        )
        keyboard.layout(0, 0, keyboard.measuredWidth, keyboard.measuredHeight)
        return keyboard.measuredHeight
    }

    @Test fun `emoji opens inside every mode and returns without changing its footprint`() {
        val keyboard = KeyboardView(RuntimeEnvironment.getApplication())
        for (mode in KeyboardView.InputMode.entries) {
            keyboard.setInputMode(mode)
            val height = measure(keyboard)
            keyboard.findViewById<View>(R.id.btn_next_keyboard).performClick()
            assertEquals(height, measure(keyboard))
            val rows = keyboard.findViewById<LinearLayout>(R.id.manual_key_rows)
            val density = keyboard.resources.displayMetrics.density
            for (widthDp in listOf(320, 393, 480)) {
                assertEquals(height, measure(keyboard, widthDp))
                for (rowIndex in 0 until rows.childCount) {
                    val row = rows.getChildAt(rowIndex) as LinearLayout
                    for (column in 0 until row.childCount) {
                        val key = row.getChildAt(column)
                        assertTrue("${key.tag} at $widthDp dp", key.width >= 44 * density)
                        assertTrue(key.height >= 44 * density)
                    }
                }
            }
            keyboard.findViewWithTag<View>("emoji_close").performClick()
            assertEquals(height, measure(keyboard))
            assertEquals(if (mode == KeyboardView.InputMode.VOICE) View.VISIBLE else View.GONE,
                keyboard.findViewById<View>(R.id.panel_voice).visibility)
            assertTrue(keyboard.findViewWithTag<View>("emoji_close") == null)
        }
    }

    @Test fun `emoji return preserves Japanese flick and symbol layers`() {
        val keyboard = KeyboardView(RuntimeEnvironment.getApplication())
        keyboard.setInputMode(KeyboardView.InputMode.JAPANESE)
        keyboard.setJapaneseInputStyle(JapaneseInputStyle.KANA_12_KEY)
        val toggle = keyboard.findViewById<View>(R.id.btn_next_keyboard)
        toggle.performClick()
        assertTrue(keyboard.isMotionEventSplittingEnabled)
        toggle.performClick()
        assertFalse(keyboard.isMotionEventSplittingEnabled)
        assertTrue(keyboard.findViewWithTag<View>("japanese_kana_a") != null)
        keyboard.setManualKeyboardState(KeyboardLayer.SYMBOLS, ShiftState.OFF)
        toggle.performClick()
        toggle.performClick()
        assertTrue(keyboard.findViewWithTag<View>("japanese_symbol_20ac") != null)
    }

    @Test fun `emoji paging commits a complete ZWJ sequence and candidates preserve emoji`() {
        val keyboard = KeyboardView(RuntimeEnvironment.getApplication())
        val listener = mock<KeyboardView.KeyboardActionListener>()
        keyboard.setKeyboardActionListener(listener)
        keyboard.setInputMode(KeyboardView.InputMode.ENGLISH)
        keyboard.findViewById<View>(R.id.btn_next_keyboard).performClick()
        repeat(2) { keyboard.findViewWithTag<View>("emoji_next").performClick() }
        keyboard.findViewWithTag<View>("emoji_2_3_0").performClick()
        verify(listener).onKeyAction(KeyAction.InsertEmoji("👨‍👩‍👧‍👦"))
        keyboard.findViewWithTag<View>("emoji_close").performClick()
        val candidate = "家人👨‍👩‍👧‍👦"
        keyboard.updateCandidates("家", listOf(candidate))
        val candidates = keyboard.findViewById<LinearLayout>(R.id.candidate_container)
        candidates.getChildAt(0).performClick()
        verify(listener).onCandidateSelected(candidate)
    }

    @Test fun `toolbar no longer switches IME on tap but long press still opens system picker`() {
        val keyboard = KeyboardView(RuntimeEnvironment.getApplication())
        val listener = mock<KeyboardView.KeyboardActionListener>()
        keyboard.setKeyboardActionListener(listener)
        val toggle = keyboard.findViewById<View>(R.id.btn_next_keyboard)
        assertTrue(toggle.performLongClick())
        verify(listener).onKeyboardPickerRequested()
        assertTrue(keyboard.findViewWithTag<View>("emoji_close") == null)
        toggle.performClick()
        verify(listener, never()).onNextKeyboardPressed()
        assertTrue(keyboard.findViewWithTag<View>("emoji_close") != null)
    }

    @Test fun `recording closes emoji and disables its entry`() {
        val keyboard = KeyboardView(RuntimeEnvironment.getApplication())
        val toggle = keyboard.findViewById<View>(R.id.btn_next_keyboard)
        toggle.performClick()
        keyboard.updateState(VoiceInputIME.ImeState.RECORDING)
        assertFalse(toggle.isEnabled)
        toggle.performClick()
        assertEquals(View.VISIBLE, keyboard.findViewById<View>(R.id.panel_voice).visibility)
        keyboard.updateState(VoiceInputIME.ImeState.IDLE)
        assertTrue(toggle.isEnabled)
    }

    @Test @GraphicsMode(GraphicsMode.Mode.NATIVE)
    fun `recording feedback mask has no opaque oval boundary`() {
        val keyboard = KeyboardView(RuntimeEnvironment.getApplication())
        keyboard.setVoicePalette(VoicePalette.MINT.argb)
        keyboard.updateState(VoiceInputIME.ImeState.RECORDING)
        val background = keyboard.findViewById<View>(R.id.btn_mic).background
        // Android's transient Ripple animation may run on the render thread,
        // which Robolectric cannot reproduce reliably. Render its actual mask
        // as well: an opaque mask creates the hard boundary when ripple expands.
        val feedbackLayer = (background as? RippleDrawable)
            ?.findDrawableByLayerId(android.R.id.mask) ?: background
        feedbackLayer.setBounds(0, 0, 600, 300)
        feedbackLayer.state = intArrayOf(android.R.attr.state_enabled, android.R.attr.state_pressed)
        val bitmap = Bitmap.createBitmap(600, 300, Bitmap.Config.ARGB_8888)
        feedbackLayer.draw(Canvas(bitmap))
        val alpha = Color.alpha(bitmap.getPixel(300, 1))
        bitmap.recycle()
        assertTrue("Recording feedback has an opaque oval boundary: alpha=$alpha", alpha <= 3)
    }

    @Test @GraphicsMode(GraphicsMode.Mode.NATIVE)
    fun `recording touch feedback never paints a hard oval edge`() {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val keyboard = KeyboardView(activity)
        activity.setContentView(keyboard)
        measure(keyboard)
        keyboard.setVoicePalette(VoicePalette.MINT.argb)
        keyboard.updateState(VoiceInputIME.ImeState.RECORDING)
        val mic = keyboard.findViewById<View>(R.id.btn_mic)
        mic.layout(0, 0, 600, 300)
        for (state in listOf(android.R.attr.state_pressed, android.R.attr.state_focused)) {
            val background = mic.background
            background.setBounds(0, 0, 600, 300)
            background.setVisible(true, false)
            background.setHotspot(300f, 150f)
            background.state = intArrayOf(android.R.attr.state_enabled, state)
            // Let Android advance its ripple animation; jumpToCurrentState alone
            // does not exercise the held-touch transient on Robolectric.
            ShadowLooper.idleMainLooper(350, TimeUnit.MILLISECONDS)
            val bitmap = Bitmap.createBitmap(600, 300, Bitmap.Config.ARGB_8888)
            background.draw(Canvas(bitmap))
            val edgeAlpha = Color.alpha(bitmap.getPixel(300, 1))
            bitmap.recycle()
            assertTrue("Mic state $state painted an oval edge with alpha $edgeAlpha", edgeAlpha <= 3)
        }
    }
}
