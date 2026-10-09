package com.shingihou.sghvoice.ime

import android.app.Activity
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.widget.NestedScrollView
import com.shingihou.sghvoice.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.shadows.ShadowLooper
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import java.io.File
import java.util.Locale

/** Exercises the actual native View, including its constrained IME height. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h852dp-xxhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ZhuyinCandidateUiTest {
    private fun measure(view: KeyboardView, widthDp: Int = 393, heightDp: Int = 852) {
        val density = view.resources.displayMetrics.density
        view.measure(
            View.MeasureSpec.makeMeasureSpec((widthDp * density).toInt(), View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec((heightDp * density).toInt(), View.MeasureSpec.AT_MOST)
        )
        view.layout(0, 0, view.measuredWidth, view.measuredHeight)
    }

    private fun keyboard(widthDp: Int = 393, fontScale: Float = 1f, locale: Locale = Locale.JAPANESE): KeyboardView {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val context = activity.createConfigurationContext(Configuration(activity.resources.configuration).apply {
            screenWidthDp = widthDp
            this.fontScale = fontScale
            setLocale(locale)
        })
        return KeyboardView(context).also {
            activity.setContentView(it)
            it.setInputMode(KeyboardView.InputMode.ZHUYIN)
            measure(it, widthDp)
        }
    }

    private fun populate(view: KeyboardView, widthDp: Int = 393) {
        view.updateCandidates("ㄅㄨˋ ㄓ ㄉㄠˋ ㄓ", listOf("不知道", "不知", "不", "部", "不知不覺已經到了目的地"))
        measure(view, widthDp)
        ShadowLooper.idleMainLooper()
        measure(view, widthDp)
    }

    @Test fun `candidate taps are larger and composition no longer consumes candidate width`() {
        val view = keyboard()
        populate(view)
        val density = view.resources.displayMetrics.density
        val candidates = view.findViewById<LinearLayout>(R.id.candidate_container)
        val first = candidates.getChildAt(0) as TextView
        assertTrue("Candidate tap height must increase beyond the old 44dp", first.height >= 52 * density)
        assertTrue("Three-character phrases should remain readable", first.textSize >= 21 * density)
        val composition = view.findViewById<TextView>(R.id.tv_composition)
        val composingPosition = IntArray(2).also(composition::getLocationInWindow)
        val candidatePosition = IntArray(2).also(candidates::getLocationInWindow)
        assertTrue("Composition should be above, not stealing the left of the candidate strip",
            composingPosition[1] + composition.height <= candidatePosition[1])
    }

    @Test fun `expanded long phrases wrap without ellipsis on narrow phones`() {
        val view = keyboard(widthDp = 320, fontScale = 1.5f)
        populate(view, 320)
        assertTrue(view.findViewById<View>(R.id.btn_expand_candidates).performClick())
        measure(view, 320)
        assertEquals("Expanded reading replaces the empty candidate bar",
            view.findViewById<View>(R.id.input_strip), view.findViewById<View>(R.id.tv_composition).parent)
        assertEquals(View.GONE, view.findViewById<View>(R.id.zhuyin_composition_summary).visibility)
        val grid = view.findViewById<GridLayout>(R.id.candidate_grid)
        assertTrue(grid.childCount >= 5)
        for (index in 0 until grid.childCount) {
            val candidate = grid.getChildAt(index) as TextView
            assertEquals(candidate.text.length, candidate.layout.getLineEnd(candidate.layout.lineCount - 1))
            for (line in 0 until candidate.layout.lineCount) {
                assertEquals("No candidate may be truncated", 0, candidate.layout.getEllipsisCount(line))
            }
        }
        val phrase = grid.getChildAt(4) as TextView
        assertTrue("Expanded candidates must allow multiple lines", phrase.maxLines > 1)
        assertEquals("Expanded candidates must never hide part of a phrase", null, phrase.ellipsize)
        assertTrue("Every character must be present in the native text layout",
            phrase.layout.getLineEnd(phrase.layout.lineCount - 1) == phrase.text.length)
        assertTrue(phrase.layout.height <= phrase.height - phrase.paddingTop - phrase.paddingBottom)
    }

    @Test fun `input language controls candidate glyph locale independently from device locale`() {
        val view = keyboard()
        for ((mode, locale) in listOf(
            KeyboardView.InputMode.ZHUYIN to Locale.TAIWAN,
            KeyboardView.InputMode.JAPANESE to Locale.JAPANESE,
            KeyboardView.InputMode.ENGLISH to Locale.ENGLISH
        )) {
            view.setInputMode(mode)
            populate(view)
            assertEquals(locale, view.findViewById<TextView>(R.id.tv_composition).textLocale)
            val candidates = view.findViewById<LinearLayout>(R.id.candidate_container)
            assertEquals(locale, (candidates.getChildAt(0) as TextView).textLocale)
        }
    }

    @Test fun `reselect only dispatches available zhuyin history and stays hidden in emoji`() {
        val view = keyboard()
        val listener = mock<KeyboardView.KeyboardActionListener>()
        view.setKeyboardActionListener(listener)
        val button = view.findViewById<View>(R.id.btn_zhuyin_reselect)
        assertEquals(View.VISIBLE, button.visibility)
        assertFalse(button.isEnabled)
        button.performClick()
        verify(listener, never()).onZhuyinReselectRequested()
        view.setZhuyinReselectAvailable(true)
        button.performClick()
        verify(listener).onZhuyinReselectRequested()
        view.findViewById<View>(R.id.btn_next_keyboard).performClick()
        assertEquals(View.GONE, button.visibility)
        assertFalse(button.isEnabled)
        view.findViewById<View>(R.id.btn_next_keyboard).performClick()
        assertEquals(View.VISIBLE, button.visibility)
        assertTrue(button.isEnabled)
        view.setInputMode(KeyboardView.InputMode.JAPANESE)
        assertEquals(View.GONE, button.visibility)
        assertFalse(button.isEnabled)
    }

    @Test fun `Japanese and English retain the original inline composition dimensions`() {
        val view = keyboard()
        populate(view)
        for (mode in listOf(KeyboardView.InputMode.JAPANESE, KeyboardView.InputMode.ENGLISH)) {
            view.setInputMode(mode)
            populate(view)
            val density = view.resources.displayMetrics.density
            val composition = view.findViewById<TextView>(R.id.tv_composition)
            assertEquals(view.findViewById<View>(R.id.input_strip), composition.parent)
            assertEquals((50 * density).toInt(), view.findViewById<View>(R.id.input_strip).height)
            assertEquals((44 * density).toInt(), composition.height)
            assertEquals((96 * density).toInt(), composition.maxWidth)
            assertEquals(View.GONE, view.findViewById<View>(R.id.zhuyin_composition_summary).visibility)
        }
    }

    @Test fun `candidate expansion preserves keyboard footprint and compact keys remain reachable`() {
        for (width in listOf(320, 393)) {
            val view = keyboard(width, 1.5f)
            view.setKeyboardHeightPercent(90)
            measure(view, width)
            val baseline = view.height
            populate(view, width)
            assertEquals(baseline, view.height)
            val rows = view.findViewById<LinearLayout>(R.id.manual_key_rows)
            val density = view.resources.displayMetrics.density
            for (rowIndex in 0 until rows.childCount) {
                val row = rows.getChildAt(rowIndex) as LinearLayout
                for (keyIndex in 0 until row.childCount) {
                    assertTrue(row.getChildAt(keyIndex).height >= 44 * density)
                }
            }
            val scroll = view.findViewById<NestedScrollView>(R.id.keyboard_content_scroll)
            assertTrue("Short keyboard must scroll instead of clipping the bottom keys",
                scroll.getChildAt(0).height > scroll.height)
            assertTrue(scroll.canScrollVertically(1))
            view.findViewById<View>(R.id.btn_expand_candidates).performClick()
            measure(view, width)
            assertEquals(baseline, view.height)
        }
    }

    @Test fun `render current native candidate strip and expanded list`() {
        val view = keyboard(locale = Locale.TAIWAN)
        populate(view)
        view.setZhuyinReselectAvailable(true)
        val output = File("build/reports/keyboard-preview").apply { mkdirs() }
        fun capture(name: String) {
            measure(view)
            val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
            view.draw(Canvas(bitmap))
            File(output, name).outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
            bitmap.recycle()
        }
        capture("zhuyin-candidates-100.png")
        view.findViewById<View>(R.id.btn_expand_candidates).performClick()
        capture("zhuyin-candidates-expanded-100.png")
    }
}
