package com.shingihou.sghvoice.ime.japanese

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class JapaneseComposerTest {

    private val lexicon = JapaneseLexicon { reading ->
        when (reading) {
            "にほん" -> listOf(
                JapaneseLexiconEntry("二本", score = 10),
                JapaneseLexiconEntry("日本", score = 100)
            )
            "はし" -> listOf(
                JapaneseLexiconEntry("端", score = 5),
                JapaneseLexiconEntry("橋", score = 50),
                JapaneseLexiconEntry("箸", score = 30)
            )
            else -> emptyList()
        }
    }

    @Test
    fun `terminal n is finalized for candidates without losing composition`() {
        val composer = JapaneseComposer(lexicon)
        assertTrue(composer.appendRomaji("nihon"))

        assertEquals("にほn", composer.composition)
        assertEquals("にほん", composer.hiraganaReading)

        val candidates = composer.getCandidates()
        assertEquals(
            listOf("日本", "二本", "にほん", "ニホン"),
            candidates.map { it.text }
        )
        assertTrue(composer.hasComposition)
    }

    @Test
    fun `lexicon candidates are ranked before both kana fallbacks`() {
        val composer = JapaneseComposer(lexicon)
        assertTrue(composer.setRomaji("hashi"))

        val candidates = composer.getCandidates()

        assertEquals(listOf("橋", "箸", "端", "はし", "ハシ"), candidates.map { it.text })
        assertEquals(JapaneseCandidateSource.LEXICON, candidates.first().source)
        assertEquals(
            JapaneseCandidateSource.HIRAGANA_FALLBACK,
            candidates[candidates.lastIndex - 1].source
        )
        assertEquals(JapaneseCandidateSource.KATAKANA_FALLBACK, candidates.last().source)
    }

    @Test
    fun `incomplete reading predicts a longer dictionary entry`() {
        val predictiveLexicon = object : JapaneseLexicon {
            override fun lookup(reading: String): List<JapaneseLexiconEntry> =
                emptyList()

            override fun lookupPrefix(
                readingPrefix: String,
                limit: Int
            ): List<JapaneseLexiconEntry> =
                if (readingPrefix == "にほ") {
                    listOf(JapaneseLexiconEntry("日本", score = 100))
                        .take(limit)
                } else {
                    emptyList()
                }
        }
        val composer = JapaneseComposer(predictiveLexicon)
        assertTrue(composer.setRomaji("niho"))

        val candidates = composer.getCandidates()

        assertEquals("にほ", composer.hiraganaReading)
        assertEquals("日本", candidates.first().text)
        assertEquals(
            JapaneseCandidateSource.PREFIX_PREDICTION,
            candidates.first().source
        )
    }

    @Test
    fun `exact Japanese result stays ahead of higher scoring prefix prediction`() {
        val predictiveLexicon = object : JapaneseLexicon {
            override fun lookup(reading: String): List<JapaneseLexiconEntry> =
                if (reading == "にほん") {
                    listOf(JapaneseLexiconEntry("日本", score = 1))
                } else {
                    emptyList()
                }

            override fun lookupPrefix(
                readingPrefix: String,
                limit: Int
            ): List<JapaneseLexiconEntry> =
                listOf(JapaneseLexiconEntry("日本語", score = 10_000))
                    .take(limit)
        }
        val composer = JapaneseComposer(predictiveLexicon)
        assertTrue(composer.setRomaji("nihon"))

        val candidates = composer.getCandidates()

        assertEquals("日本", candidates.first().text)
        assertEquals(JapaneseCandidateSource.LEXICON, candidates.first().source)
        assertEquals("日本語", candidates[1].text)
    }

    @Test
    fun `katakana mode changes composition and fallback preference`() {
        val composer = JapaneseComposer(lexicon)
        composer.setScriptMode(JapaneseScriptMode.KATAKANA)
        assertTrue(composer.appendRomaji("ko-hi-"))

        assertEquals("コーヒー", composer.composition)
        assertEquals(
            listOf("コーヒー", "こーひー"),
            composer.getCandidates().map { it.text }
        )
        assertEquals(
            JapaneseCandidateSource.KATAKANA_FALLBACK,
            composer.getCandidates().first().source
        )
    }

    @Test
    fun `backspace removes one original keystroke and recomputes kana`() {
        val composer = JapaneseComposer()
        assertTrue(composer.appendRomaji("gakkou"))
        assertEquals("がっこう", composer.composition)

        assertTrue(composer.backspace())
        assertEquals("がっこ", composer.composition)
        assertEquals("gakko", composer.rawRomaji)

        composer.clear()
        assertFalse(composer.backspace())
    }

    @Test
    fun `candidate selection clears only after a valid selection`() {
        val composer = JapaneseComposer(lexicon)
        assertTrue(composer.setRomaji("hashi"))

        assertNull(composer.selectCandidate(index = 99))
        assertTrue(composer.hasComposition)

        val selected = composer.selectCandidate(index = 1)
        assertEquals("箸", selected?.text)
        assertFalse(composer.hasComposition)
        assertEquals("", composer.composition)
    }

    @Test
    fun `unresolved romaji remains available as a lossless raw candidate`() {
        val composer = JapaneseComposer()
        assertTrue(composer.appendRomaji("ky"))

        assertNull(composer.hiraganaReading)
        assertTrue(composer.hasPendingRomaji)
        assertEquals("ky", composer.getCandidates().single().text)
        assertEquals(
            JapaneseCandidateSource.UNRESOLVED_ROMAJI_FALLBACK,
            composer.commitRaw()?.source
        )
        assertFalse(composer.hasComposition)
    }

    @Test
    fun `commit raw finalizes terminal n and honors current script`() {
        val composer = JapaneseComposer()
        assertTrue(composer.setRomaji("pan"))
        composer.toggleScriptMode()

        val committed = composer.commitRaw()

        assertEquals("パン", committed?.text)
        assertEquals("ぱん", committed?.reading)
        assertFalse(composer.hasComposition)
    }

    @Test
    fun `invalid input is rejected transactionally`() {
        val composer = JapaneseComposer()
        assertTrue(composer.setRomaji("sushi"))
        assertFalse(composer.setRomaji("sushi!"))
        assertFalse(composer.appendRomaji('1'))
        assertEquals("すし", composer.composition)
    }
}
