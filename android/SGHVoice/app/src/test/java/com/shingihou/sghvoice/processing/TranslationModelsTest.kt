package com.shingihou.sghvoice.processing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class TranslationModelsTest {

    @Test
    fun `request removes duplicates and preserves target order`() {
        val request = TranslationRequest.create(
            listOf(
                TranslationLanguage.JAPANESE,
                TranslationLanguage.KOREAN,
                TranslationLanguage.JAPANESE,
                TranslationLanguage.ENGLISH
            )
        )

        assertEquals(
            listOf(
                TranslationLanguage.JAPANESE,
                TranslationLanguage.KOREAN,
                TranslationLanguage.ENGLISH
            ),
            request.targets
        )
    }

    @Test
    fun `request rejects an empty target list`() {
        assertThrows(IllegalArgumentException::class.java) {
            TranslationRequest.create(emptyList())
        }
    }

    @Test
    fun `request accepts all four supported targets`() {
        val request = TranslationRequest.create(TranslationLanguage.entries)

        assertEquals(TranslationRequest.MAX_TARGETS, request.targets.size)
    }

    @Test
    fun `fromTags ignores unknown tags but keeps valid languages`() {
        val request = TranslationRequest.fromTags(
            listOf("invalid", "zh-Hant", "ja", "zh-Hant")
        )

        assertEquals(
            listOf(
                TranslationLanguage.TRADITIONAL_CHINESE,
                TranslationLanguage.JAPANESE
            ),
            request.targets
        )
    }
}
