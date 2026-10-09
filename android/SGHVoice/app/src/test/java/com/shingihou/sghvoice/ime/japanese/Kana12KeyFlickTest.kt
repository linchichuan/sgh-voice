package com.shingihou.sghvoice.ime.japanese

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class Kana12KeyFlickTest {
    @Test fun `reverse cycle preserves preceding kana and wraps without deleting`() {
        val composer = JapaneseComposer()
        org.junit.Assert.assertFalse(composer.reverseKana(0))
        composer.setInputStyle(JapaneseInputStyle.KANA_12_KEY)
        org.junit.Assert.assertFalse(composer.reverseKana(0))
        composer.appendKana("あ")
        composer.tapKana("na", 100)
        composer.tapKana("na", 200)
        assertEquals("あに", composer.composition)
        org.junit.Assert.assertTrue(composer.reverseKana(300))
        assertEquals("あな", composer.composition)
        composer.reverseKana(400)
        assertEquals("あの", composer.composition)
        composer.tapKana("na", 500)
        assertEquals("あな", composer.composition)
        composer.setScriptMode(JapaneseScriptMode.KATAKANA)
        composer.reverseKana(600)
        assertEquals("アノ", composer.composition)
    }

    private val directions = listOf(
        KanaFlickDirection.CENTER, KanaFlickDirection.LEFT, KanaFlickDirection.UP,
        KanaFlickDirection.RIGHT, KanaFlickDirection.DOWN
    )

    @Test
    fun `all full rows map center left up right down to vowel order`() {
        val expected = mapOf(
            "a" to listOf("あ", "い", "う", "え", "お"),
            "ka" to listOf("か", "き", "く", "け", "こ"),
            "sa" to listOf("さ", "し", "す", "せ", "そ"),
            "ta" to listOf("た", "ち", "つ", "て", "と"),
            "na" to listOf("な", "に", "ぬ", "ね", "の"),
            "ha" to listOf("は", "ひ", "ふ", "へ", "ほ"),
            "ma" to listOf("ま", "み", "む", "め", "も"),
            "ra" to listOf("ら", "り", "る", "れ", "ろ")
        )
        expected.forEach { (group, kana) ->
            assertEquals(group, kana, directions.map { Kana12Key.kanaForDirection(group, it) })
        }
    }

    @Test
    fun `ya uses center up down with no left or right fallback`() {
        assertEquals(listOf("や", null, "ゆ", null, "よ"), directions.map { Kana12Key.kanaForDirection("ya", it) })
    }

    @Test
    fun `wa uses center left up right with no downward fallback`() {
        assertEquals(listOf("わ", "を", "ん", "ー", null), directions.map { Kana12Key.kanaForDirection("wa", it) })
    }

    @Test
    fun `unknown groups never emit a kana`() {
        directions.forEach { assertNull(Kana12Key.kanaForDirection("unknown", it)) }
    }

    @Test
    fun `old multi tap group order is preserved for compatibility`() {
        assertEquals(listOf("や", "ゆ", "よ"), Kana12Key.groups["ya"])
        assertEquals(listOf("わ", "を", "ん", "ー"), Kana12Key.groups["wa"])
        assertEquals(850L, Kana12Key.MULTITAP_WINDOW_MS)
    }

    @Test
    fun `moving out of an unused position before release can choose a valid kana`() {
        val gesture = KanaFlickGesture(10f)
        gesture.begin(0, 30f, 30f)
        val emptySelection = requireNotNull(gesture.move(0, 0f, 30f))
        assertNull(Kana12Key.kanaForDirection("ya", emptySelection))
        val finalSelection = requireNotNull(gesture.end(0, 30f, 0f))
        assertEquals("ゆ", Kana12Key.kanaForDirection("ya", finalSelection))
    }

    @Test
    fun `flick output uses the existing kana composer and script modifiers`() {
        val composer = JapaneseComposer()
        composer.setInputStyle(JapaneseInputStyle.KANA_12_KEY)
        composer.appendKana(requireNotNull(Kana12Key.kanaForDirection("na", KanaFlickDirection.LEFT)))
        composer.appendKana(requireNotNull(Kana12Key.kanaForDirection("ha", KanaFlickDirection.DOWN)))
        composer.appendKana(requireNotNull(Kana12Key.kanaForDirection("wa", KanaFlickDirection.UP)))
        assertEquals("にほん", composer.composition)
        composer.setScriptMode(JapaneseScriptMode.KATAKANA)
        assertEquals("ニホン", composer.composition)
    }
}
