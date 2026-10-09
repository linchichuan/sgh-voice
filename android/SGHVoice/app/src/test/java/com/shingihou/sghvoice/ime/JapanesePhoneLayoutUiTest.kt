package com.shingihou.sghvoice.ime

import android.app.Activity
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import com.shingihou.sghvoice.ime.manual.KeyAction
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.*
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.shadows.ShadowLooper
import org.robolectric.shadows.ShadowPopupMenu
import java.io.File
import java.util.Locale

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], qualifiers = "w393dp-h852dp-xxhdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class JapanesePhoneLayoutUiTest {
    private fun keyboard(width: Int = 393, scale: Float = 1f): KeyboardView {
        val activity = Robolectric.buildActivity(Activity::class.java).setup().get()
        val context = activity.createConfigurationContext(Configuration(activity.resources.configuration).apply {
            screenWidthDp = width
            fontScale = scale
            setLocale(Locale.JAPANESE)
        })
        return KeyboardView(context).also {
            activity.setContentView(it)
            it.setInputMode(KeyboardView.InputMode.JAPANESE)
            it.setJapaneseInputStyle(JapaneseInputStyle.KANA_12_KEY)
            measure(it, width)
        }
    }

    private fun measure(view: KeyboardView, width: Int = 393) {
        val density = view.resources.displayMetrics.density
        view.measure(View.MeasureSpec.makeMeasureSpec((width * density).toInt(), View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec((852 * density).toInt(), View.MeasureSpec.AT_MOST))
        view.layout(0, 0, view.measuredWidth, view.measuredHeight)
    }

    private fun keys(view: KeyboardView): List<TextView> {
        val rows = view.findViewById<LinearLayout>(R.id.manual_key_rows)
        return (0 until rows.childCount).flatMap { r ->
            val row = rows.getChildAt(r) as LinearLayout
            (0 until row.childCount).map { row.getChildAt(it) as TextView }
        }
    }

    private fun bounds(view: KeyboardView) = keys(view).map {
        val xy = IntArray(2).also(it::getLocationInWindow)
        listOf(xy[0], xy[1], it.width, it.height)
    }

    @Test fun `four rows stay anchored through kana candidate and clear states at all supported scales`() {
        for (width in listOf(320, 393)) for (font in listOf(1f, 1.5f)) {
            val view = keyboard(width, font)
            for (percent in listOf(90, 100, 125)) {
                view.setKeyboardHeightPercent(percent)
                view.updateCandidates("", emptyList())
                measure(view, width)
                val expected = bounds(view)
                val height = view.height
                val originalKeys = keys(view)
                assertEquals(20, originalKeys.size)
                for ((text, choices) in listOf("あ" to listOf("あ", "ア"),
                    "あせ" to listOf("汗", "褪せ", "あせ", "アセ"), "" to emptyList())) {
                    view.updateCandidates(text, choices)
                    measure(view, width)
                    ShadowLooper.idleMainLooper()
                    measure(view, width)
                    assertEquals("$width / $font / $percent", expected, bounds(view))
                    assertEquals(height, view.height)
                    keys(view).forEachIndexed { i, key ->
                        assertSame("Typing must not recreate a flick key", originalKeys[i], key)
                        assertTrue(key.width >= 44 * view.resources.displayMetrics.density)
                        assertTrue(key.height >= 44 * view.resources.displayMetrics.density)
                        assertTrue("Background assignment must not overwrite inner text padding",
                            key.paddingLeft >= 6 * view.resources.displayMetrics.density)
                        assertTrue("${key.tag} must fit inside the quiet key cap", key.layout.getLineWidth(0) <=
                            key.width - key.paddingLeft - key.paddingRight)
                    }
                }
            }
        }
    }

    @Test fun `conversion opens even two kana choices without committing and closing restores identical keys`() {
        val view = keyboard()
        val listener = mock<KeyboardView.KeyboardActionListener>()
        view.setKeyboardActionListener(listener)
        view.findViewWithTag<View>("japanese_kana_space").performClick()
        verify(listener).onKeyAction(KeyAction.Space)
        clearInvocations(listener)
        view.updateCandidates("あ", listOf("あ", "ア"))
        measure(view)
        ShadowLooper.idleMainLooper()
        measure(view)
        val baseline = bounds(view)
        val reading = view.findViewById<View>(R.id.tv_composition)
        val strip = view.findViewById<View>(R.id.candidate_container)
        val readingPosition = IntArray(2).also(reading::getLocationInWindow)
        val stripPosition = IntArray(2).also(strip::getLocationInWindow)
        assertTrue("The reading must not take width away from candidates",
            readingPosition[1] + reading.height <= stripPosition[1])
        for (id in listOf("japanese_kana_convert", "japanese_kana_space")) {
            view.findViewWithTag<View>(id).performClick()
            measure(view)
            ShadowLooper.idleMainLooper()
            assertEquals(View.VISIBLE, view.findViewById<View>(R.id.candidate_expanded_panel).visibility)
            verifyNoInteractions(listener)
            view.findViewById<View>(R.id.btn_expand_candidates).performClick()
            measure(view)
            assertEquals(baseline, bounds(view))
        }
        assertEquals("確定", view.findViewWithTag<TextView>("japanese_kana_enter").text.toString())
        view.findViewWithTag<View>("japanese_kana_enter").performClick()
        verify(listener).onKeyAction(KeyAction.Enter)
        view.findViewWithTag<View>("japanese_kana_reverse").performClick()
        verify(listener).onKeyAction(KeyAction.ReverseJapaneseKana)
    }

    @Test fun `input menu retains script romaji and number access without invoking system keyboard picker`() {
        val view = keyboard()
        val listener = mock<KeyboardView.KeyboardActionListener>()
        view.setKeyboardActionListener(listener)
        for (choice in listOf(1, 2, 3)) {
            view.findViewWithTag<View>("japanese_input_options").performClick()
            val popup = ShadowPopupMenu.getLatestPopupMenu()
            assertEquals(3, popup.menu.size())
            popup.menu.performIdentifierAction(choice, 0)
        }
        verify(listener).onKeyAction(KeyAction.ToggleJapaneseScript)
        verify(listener).onKeyAction(KeyAction.ToggleJapaneseLayout)
        verify(listener).onKeyAction(KeyAction.FinalizeJapaneseKana)
        verify(listener, never()).onKeyboardPickerRequested()
        verify(listener, never()).onNextKeyboardPressed()
        assertNotNull(view.findViewWithTag<View>("japanese_character_31"))
        view.findViewWithTag<View>("japanese_letters").performClick()
        assertNotNull(view.findViewWithTag<View>("japanese_kana_a"))
    }

    @Test fun `render native Japanese idle composing and compact large font previews`() {
        val output = File("build/reports/keyboard-preview").apply { mkdirs() }
        for ((width, font, name) in listOf(Triple(393, 1f, "standard"), Triple(320, 1.5f, "compact-large-font"))) {
            val view = keyboard(width, font)
            for (composing in listOf(false, true)) {
                view.updateCandidates(if (composing) "あせ" else "",
                    if (composing) listOf("汗", "褪せ", "あせ", "アセ", "汗だく", "焦り") else emptyList())
                measure(view, width)
                ShadowLooper.idleMainLooper()
                measure(view, width)
                val image = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
                view.draw(Canvas(image))
                File(output, "japanese-rails-$name-${if (composing) "typing" else "idle"}.png")
                    .outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
                image.recycle()
            }
        }
    }
}
