package com.shingihou.sghvoice.ime.manual

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ManualKeyboardLayoutProviderTest {
    private val provider = ManualKeyboardLayoutProvider()

    @Test
    fun `English QWERTY reflects shift state and common actions`() {
        val lowercase = provider.layout(ManualKeyboardMode.ENGLISH)
        val uppercase = provider.layout(
            ManualKeyboardMode.ENGLISH,
            shiftState = ShiftState.ONCE
        )

        assertEquals(
            "qwertyuiop",
            lowercase.rows.first().keys.joinToString("") { it.label }
        )
        assertEquals(
            "QWERTYUIOP",
            uppercase.rows.first().keys.joinToString("") { it.label }
        )
        assertTrue(lowercase.rows[2].keys.first().action is KeyAction.Shift)
        assertTrue(lowercase.rows[2].keys.last().action is KeyAction.Backspace)
        assertTrue(lowercase.rows.last().keys[2].action is KeyAction.Space)
    }

    @Test
    fun `Japanese layout reuses QWERTY and exposes script punctuation`() {
        val layout = provider.layout(ManualKeyboardMode.JAPANESE)
        val bottomLabels = layout.rows.last().keys.map { it.label }

        assertEquals(
            "qwertyuiop",
            layout.rows.first().keys.joinToString("") { it.label }
        )
        assertTrue(
            layout.rows.last().keys.any {
                it.action is KeyAction.ToggleJapaneseScript
            }
        )
        assertTrue("、" in bottomLabels)
        assertTrue("。" in bottomLabels)
    }

    @Test
    fun `Zhuyin adapter exposes every phonetic and tone symbol`() {
        val layout = provider.layout(ManualKeyboardMode.ZHUYIN)
        val symbols = layout.rows
            .dropLast(1)
            .flatMap { row -> row.keys }
            .map { it.label }
            .toSet()

        assertEquals(41, symbols.size)
        assertTrue("ㄅ" in symbols)
        assertTrue("ㄦ" in symbols)
        assertTrue("ˇ" in symbols)
        assertTrue("˙" in symbols)
    }

    @Test
    fun `Numeric and symbol layers are available to every mode`() {
        ManualKeyboardMode.entries.forEach { mode ->
            val numbers = provider.layout(mode, KeyboardLayer.NUMBERS)
            val symbols = provider.layout(mode, KeyboardLayer.SYMBOLS)

            assertEquals("1234567890", numbers.rows.first().keys.joinToString("") { it.label })
            assertTrue(symbols.rows.flattenKeys().any { it.label == "€" })
            assertTrue(
                symbols.rows.flattenKeys().any {
                    it.action == KeyAction.SwitchLayer(KeyboardLayer.LETTERS)
                }
            )
        }
    }

    @Test
    fun `Every key advertises an accessible touch target`() {
        ManualKeyboardMode.entries.forEach { mode ->
            KeyboardLayer.entries.forEach { layer ->
                provider.layout(mode, layer).rows.flattenKeys().forEach { key ->
                    assertTrue(
                        "${key.id} was smaller than the minimum touch target",
                        key.minTouchTargetDp >= KeySpec.MIN_TOUCH_TARGET_DP
                    )
                    assertTrue(key.contentDescription.isNotBlank())
                }
            }
        }
    }

    private fun List<KeyboardRow>.flattenKeys(): List<KeySpec> =
        flatMap { it.keys }
}
