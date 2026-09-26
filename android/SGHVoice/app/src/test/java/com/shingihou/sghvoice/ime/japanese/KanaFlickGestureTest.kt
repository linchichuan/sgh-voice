package com.shingihou.sghvoice.ime.japanese

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class KanaFlickGestureTest {
    private val gesture = KanaFlickGesture(touchSlop = 10f)

    @Test
    fun `tap selects the central kana`() {
        assertTrue(gesture.begin(4, 30f, 20f))
        assertEquals(KanaFlickDirection.CENTER, gesture.end(4, 30f, 20f))
        assertFalse(gesture.isActive)
    }

    @Test
    fun `four directions follow displacement from the original finger location`() {
        val cases = listOf(
            Triple(18f, 20f, KanaFlickDirection.LEFT),
            Triple(30f, 8f, KanaFlickDirection.UP),
            Triple(42f, 20f, KanaFlickDirection.RIGHT),
            Triple(30f, 32f, KanaFlickDirection.DOWN)
        )
        cases.forEach { (x, y, expected) ->
            gesture.begin(0, 30f, 20f)
            assertEquals(expected, gesture.end(0, x, y))
        }
    }

    @Test
    fun `threshold is radial and inclusive for a central tap`() {
        gesture.begin(0, 0f, 0f)
        assertEquals(KanaFlickDirection.CENTER, gesture.move(0, 10f, 0f))
        assertEquals(KanaFlickDirection.CENTER, gesture.move(0, 6f, 8f))
        assertEquals(KanaFlickDirection.RIGHT, gesture.move(0, 10.01f, 0f))
        assertEquals(KanaFlickDirection.LEFT, gesture.move(0, -10.01f, 0f))
        assertEquals(KanaFlickDirection.UP, gesture.move(0, 0f, -10.01f))
        assertEquals(KanaFlickDirection.DOWN, gesture.move(0, 0f, 10.01f))
    }

    @Test
    fun `diagonal movement uses its dominant axis with a deterministic vertical tie`() {
        gesture.begin(0, 0f, 0f)
        assertEquals(KanaFlickDirection.LEFT, gesture.move(0, -30f, -15f))
        assertEquals(KanaFlickDirection.UP, gesture.move(0, -15f, -30f))
        assertEquals(KanaFlickDirection.UP, gesture.move(0, 20f, -20f))
        assertEquals(KanaFlickDirection.DOWN, gesture.move(0, -20f, 20f))
    }

    @Test
    fun `selection can change directions and return to center before release`() {
        gesture.begin(0, 40f, 40f)
        assertEquals(KanaFlickDirection.LEFT, gesture.move(0, 10f, 40f))
        assertEquals(KanaFlickDirection.UP, gesture.move(0, 40f, 10f))
        assertEquals(KanaFlickDirection.RIGHT, gesture.move(0, 70f, 40f))
        assertEquals(KanaFlickDirection.CENTER, gesture.end(0, 42f, 40f))
    }

    @Test
    fun `release uses its final coordinate even without a move event`() {
        gesture.begin(0, 40f, 40f)
        assertEquals(KanaFlickDirection.DOWN, gesture.end(0, 40f, 70f))
    }

    @Test
    fun `a finished gesture cannot produce a second result`() {
        gesture.begin(0, 40f, 40f)
        assertEquals(KanaFlickDirection.LEFT, gesture.end(0, 10f, 40f))
        assertNull(gesture.end(0, 10f, 40f))
        assertNull(gesture.move(0, 10f, 40f))
    }

    @Test
    fun `cancel discards the current selection`() {
        gesture.begin(0, 40f, 40f)
        gesture.move(0, 10f, 40f)
        gesture.cancel()
        assertFalse(gesture.isActive)
        assertNull(gesture.direction)
        assertNull(gesture.end(0, 10f, 40f))
    }

    @Test
    fun `secondary pointer cancels rather than taking over or committing`() {
        gesture.begin(4, 40f, 40f)
        gesture.move(4, 10f, 40f)
        gesture.secondaryPointerDown()
        assertNull(gesture.end(9, 40f, 40f))
        assertNull(gesture.end(4, 10f, 40f))
        assertFalse(gesture.isActive)
    }

    @Test
    fun `unexpected new down during a gesture also fails closed`() {
        gesture.begin(4, 40f, 40f)
        assertFalse(gesture.begin(9, 40f, 40f))
        assertNull(gesture.end(9, 40f, 40f))
        assertNull(gesture.end(4, 40f, 40f))
    }

    @Test
    fun `missing original pointer cancels the gesture`() {
        gesture.begin(4, 40f, 40f)
        assertNull(gesture.move(9, 10f, 40f))
        assertNull(gesture.end(4, 10f, 40f))
    }

    @Test
    fun `release from the wrong pointer emits nothing`() {
        gesture.begin(4, 40f, 40f)
        assertNull(gesture.end(9, 10f, 40f))
        assertFalse(gesture.isActive)
    }

    @Test
    fun `a fresh gesture after cancellation still works`() {
        gesture.begin(4, 40f, 40f)
        gesture.secondaryPointerDown()
        gesture.begin(7, 40f, 40f)
        assertEquals(KanaFlickDirection.RIGHT, gesture.end(7, 70f, 40f))
    }

    @Test
    fun `rapid independent taps append central kana instead of cycling`() {
        val composer = JapaneseComposer()
        composer.setInputStyle(JapaneseInputStyle.KANA_12_KEY)
        repeat(5) {
            gesture.begin(0, 40f, 40f)
            val direction = requireNotNull(gesture.end(0, 40f, 40f))
            assertTrue(composer.appendKana(requireNotNull(Kana12Key.kanaForDirection("na", direction))))
        }
        assertEquals("ななななな", composer.composition)
    }

    @Test
    fun `fresh consecutive flicks use independent origins`() {
        gesture.begin(0, 40f, 40f)
        assertEquals(KanaFlickDirection.LEFT, gesture.end(0, 20f, 40f))
        gesture.begin(0, 5f, 5f)
        assertEquals(KanaFlickDirection.UP, gesture.end(0, 5f, -15f))
    }

    @Test
    fun `nonfinite pointer coordinates fail closed`() {
        assertFalse(gesture.begin(0, Float.NaN, 0f))
        gesture.begin(0, 40f, 40f)
        assertNull(gesture.end(0, Float.POSITIVE_INFINITY, 0f))
        assertFalse(gesture.isActive)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `zero threshold is rejected`() {
        KanaFlickGesture(0f)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `nonfinite threshold is rejected`() {
        KanaFlickGesture(Float.NaN)
    }
}
