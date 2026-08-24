package com.shingihou.sghvoice.processing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RecognitionLanguageTest {

    @Test
    fun `auto omits provider language while explicit choices use ISO codes`() {
        assertNull(RecognitionLanguage.AUTO.apiCode)
        assertEquals("zh", RecognitionLanguage.TRADITIONAL_CHINESE.apiCode)
        assertEquals("ja", RecognitionLanguage.JAPANESE.apiCode)
        assertEquals("en", RecognitionLanguage.ENGLISH.apiCode)
        assertEquals("ko", RecognitionLanguage.KOREAN.apiCode)
    }

    @Test
    fun `unknown or legacy blank values safely fall back to auto`() {
        assertEquals(
            RecognitionLanguage.AUTO,
            RecognitionLanguage.fromPreference(null)
        )
        assertEquals(
            RecognitionLanguage.AUTO,
            RecognitionLanguage.fromPreference("unknown")
        )
        assertEquals(
            RecognitionLanguage.KOREAN,
            RecognitionLanguage.fromPreference(" KO ")
        )
    }
}
