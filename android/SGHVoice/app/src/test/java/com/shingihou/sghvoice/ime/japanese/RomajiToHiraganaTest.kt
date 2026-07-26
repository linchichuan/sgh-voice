package com.shingihou.sghvoice.ime.japanese

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RomajiToHiraganaTest {

    @Test
    fun `converts basic gojuon and uppercase input`() {
        assertEquals("たべもの", RomajiToHiragana.convert("tabemono").hiragana)
        assertEquals("すし", RomajiToHiragana.convert("SUSHI").hiragana)
        assertTrue(RomajiToHiragana.convert("SUSHI").isComplete)
    }

    @Test
    fun `converts doubled consonants and tch to sokuon`() {
        assertEquals("がっこう", RomajiToHiragana.convert("gakkou").hiragana)
        assertEquals("きって", RomajiToHiragana.convert("kitte").hiragana)
        assertEquals("まっちゃ", RomajiToHiragana.convert("matcha").hiragana)
        assertEquals("こっちゃ", RomajiToHiragana.convert("coccha").hiragana)
    }

    @Test
    fun `handles syllabic n without stealing na or nya`() {
        assertEquals("かんじ", RomajiToHiragana.convert("kanji").hiragana)
        assertEquals("こんにちは", RomajiToHiragana.convert("konnichiha").hiragana)
        assertEquals("きんようび", RomajiToHiragana.convert("kin'youbi").hiragana)
        assertEquals("にゃ", RomajiToHiragana.convert("nya").hiragana)
        assertEquals("んな", RomajiToHiragana.convert("nna").hiragana)
        assertEquals("ん", RomajiToHiragana.convert("nn").hiragana)
    }

    @Test
    fun `terminal single n can remain pending or be finalized`() {
        val composing = RomajiToHiragana.convert("kan")
        assertEquals("か", composing.hiragana)
        assertEquals("n", composing.pendingRomaji)
        assertFalse(composing.isComplete)

        val finalized = RomajiToHiragana.convert("kan", finalizeTerminalN = true)
        assertEquals("かん", finalized.hiragana)
        assertTrue(finalized.isComplete)
    }

    @Test
    fun `converts yoon explicit small kana and foreign sounds`() {
        assertEquals("きょう", RomajiToHiragana.convert("kyou").hiragana)
        assertEquals(
            "しゃしん",
            RomajiToHiragana.convert("shashin", finalizeTerminalN = true).hiragana
        )
        assertEquals("ぁぃぅぇぉ", RomajiToHiragana.convert("xaxixuxexo").hiragana)
        assertEquals("ゃゅょっ", RomajiToHiragana.convert("lyalyulyoltsu").hiragana)
        assertEquals("ふぁいる", RomajiToHiragana.convert("fairu").hiragana)
        assertEquals("てぃ", RomajiToHiragana.convert("thi").hiragana)
    }

    @Test
    fun `hyphen becomes the Japanese long vowel mark`() {
        assertEquals("こーひー", RomajiToHiragana.convert("ko-hi-").hiragana)
        assertEquals("コーヒー", JapaneseScripts.hiraganaToKatakana("こーひー"))
    }

    @Test
    fun `unfinished sequence is preserved as pending romaji`() {
        val result = RomajiToHiragana.convert("kanky")
        assertEquals("かん", result.hiragana)
        assertEquals("ky", result.pendingRomaji)
        assertEquals("かんky", result.displayText)
    }

    @Test
    fun `script conversion normalizes katakana lookup readings`() {
        assertEquals("ニホンゴ", JapaneseScripts.hiraganaToKatakana("にほんご"))
        assertEquals("にほんご", JapaneseScripts.katakanaToHiragana("ニホンゴ"))
        assertEquals("こーひー", JapaneseScripts.katakanaToHiragana("ｺｰﾋｰ"))
    }
}
