package com.shingihou.sghvoice.ime.manual

import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
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
        assertTrue(layout.rows.flattenKeys().any { it.action == KeyAction.ToggleJapaneseLayout })
    }

    @Test
    fun `Japanese 12 key layout has kana groups and retains Romaji switch`() {
        val layout = provider.layout(
            ManualKeyboardMode.JAPANESE,
            japaneseInputStyle = JapaneseInputStyle.KANA_12_KEY
        )
        val keys = layout.rows.flattenKeys()

        assertEquals(5, layout.rows.size)
        assertEquals(listOf("あ", "か", "さ"), layout.rows.first().keys.take(3).map { it.label })
        assertEquals(10, keys.count { it.action is KeyAction.TapJapaneseKana })
        assertTrue(keys.any { it.action == KeyAction.TransformJapaneseKana })
        assertTrue(keys.any { it.action == KeyAction.CursorLeft })
        assertTrue(keys.any { it.action == KeyAction.CursorRight })
        assertTrue(keys.any { it.action == KeyAction.ToggleJapaneseScript })
        assertTrue(keys.any { it.action == KeyAction.ToggleJapaneseLayout && it.label == "ABC" })
        assertTrue(keys.any { it.label == "あ" && "い" in it.alternatives })
        assertTrue(keys.any { it.action == KeyAction.Backspace })
    }

    @Test
    fun `Japanese phone keypad keeps all three columns aligned and actions reachable`() {
        val layout = provider.layout(
            ManualKeyboardMode.JAPANESE,
            japaneseInputStyle = JapaneseInputStyle.KANA_12_KEY
        )
        val keypadRows = layout.rows.take(4)
        val columnWeights = keypadRows.first().keys.map { it.widthWeight }

        keypadRows.forEach { row ->
            assertEquals(4, row.keys.size)
            assertEquals(columnWeights, row.keys.map { it.widthWeight })
            assertEquals(1, row.keys.take(3).map { it.widthWeight }.distinct().size)
            assertTrue(row.keys.last().widthWeight < row.keys.first().widthWeight)
        }
        assertEquals(
            listOf(KeyAction.Backspace, KeyAction.CursorLeft,
                KeyAction.CursorRight, KeyAction.Enter),
            keypadRows.map { it.keys.last().action }
        )
        assertEquals("わ", keypadRows.last().keys[1].label)
        assertEquals(
            listOf(KeyAction.SwitchLayer(KeyboardLayer.NUMBERS),
                KeyAction.ToggleJapaneseLayout, KeyAction.ToggleJapaneseScript, KeyAction.Space),
            layout.rows.last().keys.map { it.action }
        )
        val bottomKeys = layout.rows.last().keys
        assertTrue(bottomKeys.last().widthWeight > bottomKeys.dropLast(1).maxOf { it.widthWeight })
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
                val layouts = if (mode == ManualKeyboardMode.JAPANESE) {
                    JapaneseInputStyle.entries.map { provider.layout(mode, layer, japaneseInputStyle = it) }
                } else {
                    listOf(provider.layout(mode, layer))
                }
                layouts.flatMap { it.rows.flattenKeys() }.forEach { key ->
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
