package com.shingihou.sghvoice.ime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ZhuyinComposerTest {

    @Test
    fun `standard Taiwan keyboard exposes all 37 symbols and four tone marks`() {
        assertEquals(37, ZhuyinComposer.PHONETIC_SYMBOLS.size)
        assertEquals(41, ZhuyinComposer.STANDARD_SYMBOLS.size)
        assertEquals('ㄆ', ZhuyinComposer.STANDARD_KEY_MAP['q'])
        assertEquals('ˇ', ZhuyinComposer.STANDARD_KEY_MAP['3'])
        assertEquals('ㄝ', ZhuyinComposer.STANDARD_KEY_MAP[','])
    }

    @Test
    fun `composes multiple syllables and returns phrase plus raw candidate`() {
        val composer = ZhuyinComposer()

        "ㄋㄧˇ".forEach { assertTrue(composer.append(it)) }
        assertTrue(composer.separateSyllable())
        "ㄏㄠˇ".forEach { assertTrue(composer.append(it)) }

        assertEquals("ㄋㄧˇ ㄏㄠˇ", composer.composition)
        assertEquals(listOf("ㄋㄧˇ", "ㄏㄠˇ"), composer.syllables)

        val candidates = composer.getCandidates()
        assertEquals("你好", candidates.first().text)
        assertEquals(ZhuyinCandidateSource.LEXICON, candidates.first().source)
        assertEquals("ㄋㄧˇㄏㄠˇ", candidates.last().text)
        assertEquals(ZhuyinCandidateSource.RAW_FALLBACK, candidates.last().source)
    }

    @Test
    fun `missing tone still predicts the common character`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("ㄋㄧ"))

        val candidates = composer.getCandidates(includeRawFallback = false)

        assertEquals("你", candidates.first().text)
        assertEquals(ZhuyinCandidateSource.TONE_FOLDED, candidates.first().source)
    }

    @Test
    fun `unfinished syllable uses bounded prefix prediction`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("ㄋ"))

        val candidates = composer.getCandidates(
            limit = 2,
            includeRawFallback = false
        )

        assertEquals(listOf("你"), candidates.map { it.text })
        assertEquals(ZhuyinCandidateSource.PREFIX_PREDICTION, candidates.first().source)
    }

    @Test
    fun `multiple exact syllables are combined with bounded beam search`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("ㄨㄛˇ ㄕˋ"))

        val candidates = composer.getCandidates(
            limit = 4,
            includeRawFallback = false
        )

        assertEquals(listOf("我是", "我事", "我市", "我室"), candidates.map { it.text })
        assertTrue(candidates.all { it.source == ZhuyinCandidateSource.SEGMENTED })
    }

    @Test
    fun `candidate selection returns commit value and clears composition`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("ㄕˋ"))

        val selected = composer.selectCandidate(index = 1)

        assertEquals("事", selected?.text)
        assertEquals("ㄕˋ", selected?.reading)
        assertFalse(composer.hasComposition)
        assertEquals("", composer.composition)
    }

    @Test
    fun `peek best candidate leaves composition intact until commit succeeds`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("ㄋㄧˇ"))

        assertEquals("你", composer.peekBestOrRaw()?.text)
        assertTrue(composer.hasComposition)
        assertEquals("你", composer.commitBestOrRaw()?.text)
        assertFalse(composer.hasComposition)
    }

    @Test
    fun `invalid candidate index does not discard composition`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("ㄋㄧˇ"))

        assertNull(composer.selectCandidate(index = 99))
        assertEquals("ㄋㄧˇ", composer.composition)
    }

    @Test
    fun `backspace first removes delimiter then symbols`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("ㄋㄧˇ ㄏㄠˇ"))
        assertTrue(composer.separateSyllable())
        assertEquals("ㄋㄧˇ ㄏㄠˇ ", composer.composition)

        assertTrue(composer.backspace())
        assertEquals("ㄋㄧˇ ㄏㄠˇ", composer.composition)
        assertTrue(composer.backspace())
        assertEquals("ㄋㄧˇ ㄏㄠ", composer.composition)

        composer.clear()
        assertFalse(composer.backspace())
    }

    @Test
    fun `tone and new initial can create automatic syllable boundary`() {
        val composer = ZhuyinComposer()

        "ㄋㄧˇㄏㄠˇ".forEach { assertTrue(composer.append(it)) }

        assertEquals("ㄋㄧˇ ㄏㄠˇ", composer.normalizedReading)
        assertEquals("你好", composer.commitBestOrRaw()?.text)
        assertFalse(composer.hasComposition)
    }

    @Test
    fun `first tone syllable can auto-separate before vowel-led syllable`() {
        val composer = ZhuyinComposer()

        "ㄓㄨㄥㄨㄣˊ".forEach { assertTrue(composer.append(it)) }

        assertEquals("ㄓㄨㄥ ㄨㄣˊ", composer.normalizedReading)
        assertEquals("中文", composer.commitBestOrRaw()?.text)
    }

    @Test
    fun `rejects invalid symbol ordering and incompatible combinations`() {
        val composer = ZhuyinComposer()

        assertFalse(composer.append('ˇ'))
        assertTrue(composer.append('ㄅ'))
        assertFalse(composer.append('ㄆ'))
        assertFalse(composer.append('ㄩ'))

        composer.clear()
        assertTrue(composer.append('ㄍ'))
        assertFalse(composer.append('ㄧ'))

        composer.clear()
        assertTrue(composer.append('ㄐ'))
        assertFalse(composer.append('ㄚ'))
        assertTrue(composer.append('ㄧ'))
        assertTrue(composer.append('ㄚ'))
    }

    @Test
    fun `custom lexicon is injectable and ranked by score`() {
        val customLexicon = ZhuyinLexicon { reading ->
            if (reading == "ㄘㄜˋ ㄕˋ") {
                listOf(
                    ZhuyinLexiconEntry("次試", score = 1),
                    ZhuyinLexiconEntry("測試", score = 100)
                )
            } else {
                emptyList()
            }
        }
        val composer = ZhuyinComposer(customLexicon)
        assertTrue(composer.setComposition("ㄘㄜˋ ㄕˋ"))

        assertEquals(listOf("測試", "次試"), composer.getCandidates(includeRawFallback = false).map { it.text })
    }

    @Test
    fun `unknown reading can be committed as raw Zhuyin without delimiters`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("ㄎㄨㄞˋ ㄌㄜˋ"))

        val committed = composer.commitRaw()

        assertEquals("ㄎㄨㄞˋㄌㄜˋ", committed?.text)
        assertEquals(ZhuyinCandidateSource.RAW_FALLBACK, committed?.source)
        assertFalse(composer.hasComposition)
    }

    @Test
    fun `set composition normalizes leading neutral tone and rolls back on failure`() {
        val composer = ZhuyinComposer()
        assertTrue(composer.setComposition("˙ㄉㄜ"))
        assertEquals("ㄉㄜ˙", composer.normalizedReading)

        assertFalse(composer.setComposition("ㄅㄩ"))
        assertEquals("ㄉㄜ˙", composer.normalizedReading)
    }

    @Test
    fun `standard hardware keys can drive composition`() {
        val composer = ZhuyinComposer()

        // s u 3 = ㄋ ㄧ ˇ
        assertTrue(composer.appendKey('s'))
        assertTrue(composer.appendKey('U'))
        assertTrue(composer.appendKey('3'))

        assertEquals("ㄋㄧˇ", composer.normalizedReading)
        assertFalse(composer.appendKey('?'))
    }
}
