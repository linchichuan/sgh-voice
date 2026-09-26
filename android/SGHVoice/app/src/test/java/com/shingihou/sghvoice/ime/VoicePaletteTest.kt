package com.shingihou.sghvoice.ime

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.pow

class VoicePaletteTest {
    @Test fun `unknown or missing preference returns light mint`() {
        assertEquals(VoicePalette.MINT, VoicePalette.fromPreference(null))
        assertEquals(VoicePalette.MINT, VoicePalette.fromPreference("removed-theme"))
        VoicePalette.entries.forEach { assertEquals(it, VoicePalette.fromPreference(it.preferenceValue)) }
    }

    @Test fun `all palettes are light and contrast with fixed text`() {
        fun luminance(color: Int): Double = listOf(16, 8, 0).map { shift ->
            val s = ((color shr shift) and 255) / 255.0
            if (s <= 0.04045) s / 12.92 else ((s + 0.055) / 1.055).pow(2.4)
        }.let { it[0] * 0.2126 + it[1] * 0.7152 + it[2] * 0.0722 }
        val text = luminance(0xFF25372F.toInt())
        VoicePalette.entries.forEach {
            assertEquals(255, it.argb ushr 24)
            assertTrue(luminance(it.argb) > 0.75)
            assertTrue((luminance(it.argb) + 0.05) / (text + 0.05) >= 4.5)
        }
    }
}
