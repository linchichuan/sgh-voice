package com.shingihou.sghvoice.ime.manual

import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ManualKeyboardLayoutProviderTest {
    private val provider = ManualKeyboardLayoutProvider()

    @Test fun `Japanese phone layout centers twelve keys between two four key rails`() {
        val layout = provider.layout(ManualKeyboardMode.JAPANESE,
            japaneseInputStyle = JapaneseInputStyle.KANA_12_KEY)
        assertEquals("No fifth toolbar below the kana matrix", 4, layout.rows.size)
        assertTrue(layout.rows.all { it.keys.size == 5 })
        assertEquals(listOf(listOf("あ", "か", "さ"), listOf("た", "な", "は"),
            listOf("ま", "や", "ら"), listOf("小゛゜", "わ", "、。?!")),
            layout.rows.map { it.keys.subList(1, 4).map { key -> key.label } })
        assertEquals(KeyAction.CursorLeft, layout.rows[1].keys.first().action)
        assertEquals(KeyAction.CursorRight, layout.rows[1].keys.last().action)
        assertEquals(KeyAction.Backspace, layout.rows[0].keys.last().action)
        assertEquals(KeyAction.Enter, layout.rows[3].keys.last().action)
        layout.rows.forEach { row ->
            assertEquals(listOf(.75f, 1f, 1f, 1f, .75f), row.keys.map { it.widthWeight })
        }
    }

    @Test fun `English always shows a directly tappable number row above the letters`() {
        for (shift in ShiftState.entries) {
            val layout = provider.layout(ManualKeyboardMode.ENGLISH, shiftState = shift)
            assertEquals("1234567890", layout.rows.first().keys.joinToString("") { it.label })
            assertEquals(5, layout.rows.size)
            assertEquals("1234567890".map { KeyAction.InsertText(it.toString()) },
                layout.rows.first().keys.map { it.action })
        }
    }

    @Test
    fun `English QWERTY reflects shift state and common actions`() {
        val lowercase = provider.layout(ManualKeyboardMode.ENGLISH)
        val uppercase = provider.layout(
            ManualKeyboardMode.ENGLISH,
            shiftState = ShiftState.ONCE
        )

        assertEquals(
            "qwertyuiop",
            lowercase.rows[1].keys.joinToString("") { it.label }
        )
        assertEquals(
            "QWERTYUIOP",
            uppercase.rows[1].keys.joinToString("") { it.label }
        )
        assertTrue(lowercase.rows[3].keys.first().action is KeyAction.Shift)
        assertTrue(lowercase.rows[3].keys.last().action is KeyAction.Backspace)
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
    fun `Japanese 12 key layout has kana groups and exposes input options`() {
        val layout = provider.layout(
            ManualKeyboardMode.JAPANESE,
            japaneseInputStyle = JapaneseInputStyle.KANA_12_KEY
        )
        val keys = layout.rows.flattenKeys()

        assertEquals(4, layout.rows.size)
        assertEquals(listOf("あ", "か", "さ"), layout.rows.first().keys.subList(1, 4).map { it.label })
        assertEquals(10, keys.count { it.action is KeyAction.TapJapaneseKana })
        assertTrue(keys.any { it.action == KeyAction.TransformJapaneseKana })
        assertTrue(keys.any { it.action == KeyAction.CursorLeft })
        assertTrue(keys.any { it.action == KeyAction.CursorRight })
        assertTrue(keys.any { it.action == KeyAction.JapaneseInputOptions })
        assertTrue(keys.any { it.action == KeyAction.ShowJapaneseCandidates })
        assertTrue(keys.any { it.action == KeyAction.ReverseJapaneseKana })
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
            assertEquals(5, row.keys.size)
            assertEquals(columnWeights, row.keys.map { it.widthWeight })
            assertEquals(1, row.keys.subList(1, 4).map { it.widthWeight }.distinct().size)
            assertTrue(row.keys.last().widthWeight < row.keys[1].widthWeight)
            assertEquals(row.keys.first().widthWeight, row.keys.last().widthWeight)
        }
        assertEquals(
            listOf(KeyAction.Backspace, KeyAction.CursorRight,
                KeyAction.Space, KeyAction.Enter),
            keypadRows.map { it.keys.last().action }
        )
        assertEquals("わ", keypadRows.last().keys[2].label)
        assertEquals(
            listOf(KeyAction.ReverseJapaneseKana, KeyAction.CursorLeft,
                KeyAction.ShowJapaneseCandidates, KeyAction.JapaneseInputOptions),
            layout.rows.map { it.keys.first().action }
        )
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
