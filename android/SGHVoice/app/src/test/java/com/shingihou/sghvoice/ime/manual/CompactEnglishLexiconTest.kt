package com.shingihou.sghvoice.ime.manual

import java.io.ByteArrayInputStream
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CompactEnglishLexiconTest {
    private fun load(text: String) = CompactEnglishLexicon.load(ByteArrayInputStream(text.toByteArray()))

    @Test
    fun `prefix completion ranks the entire range by frequency and excludes exact input`() {
        val lexicon = load("apple\t80\napply\t130\napplication\t100\nape\t200\nap\t250\n")
        assertEquals(listOf("ape", "apply", "application"), lexicon.candidates("AP", 3).map { it.text })
        assertEquals(listOf("apple"), lexicon.candidates("appl", 20).filter { it.text == "apple" }.map { it.text })
        assertTrue(lexicon.candidates("apple", 5).isEmpty())
    }

    @Test
    fun `bad rows are ignored and duplicate words retain maximum frequency`() {
        val lexicon = load("# notice\nvalid\t90\nvalid\t120\ninvalid\tnan\nUppercase\t200\nurl.test\t220\nzero\t0\n")
        assertEquals(1, lexicon.wordCount)
        assertEquals(120, lexicon.candidates("va", 3).single().score)
        assertTrue(lexicon.candidates("", 3).isEmpty())
        assertTrue(lexicon.candidates("v", 0).isEmpty())
    }

    @Test
    fun `curated seed order remains ahead of corpus words without duplicates`() {
        val lexicon = load("hello\t255\nhelpful\t254\nhelicopter\t253\nhelium\t252\n")
        val provider = SeededEnglishCandidateProvider(lexicon)
        val expectedSeeds = LocalEnglishCandidateProvider.candidates("hel", 20).map { it.text }
        val candidates = provider.candidates("hel", 20)
        assertEquals(expectedSeeds, candidates.take(expectedSeeds.size).map { it.text })
        assertTrue(candidates.any { it.text == "helicopter" })
        assertEquals(candidates.size, candidates.map { it.text }.distinct().size)
        assertTrue(candidates.first().score > candidates.last().score)
    }

    @Test
    fun `packaged dictionary expands everyday vocabulary offline`() {
        val lexicon = File("src/main/assets/english/aosp_english.tsv").inputStream().use { CompactEnglishLexicon.load(it) }
        assertTrue(lexicon.wordCount in 40_000..50_000)
        for ((prefix, expected) in listOf("architec" to "architecture", "infrastruc" to "infrastructure", "collabor" to "collaboration")) {
            assertTrue("$expected must be available", lexicon.candidates(prefix, 30).any { it.text == expected })
        }
    }
}
