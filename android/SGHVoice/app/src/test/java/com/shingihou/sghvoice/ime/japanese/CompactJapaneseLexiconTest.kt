package com.shingihou.sghvoice.ime.japanese

import java.io.ByteArrayInputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CompactJapaneseLexiconTest {

    private fun load(text: String, limit: Int = 24): CompactJapaneseLexicon =
        CompactJapaneseLexicon.load(
            ByteArrayInputStream(text.trimIndent().toByteArray(Charsets.UTF_8)),
            maxCandidatesPerReading = limit
        )

    @Test
    fun `loads exact readings and ranks candidates by score`() {
        val lexicon = load(
            """
            # generated test data
            はし	2000	端
            はし	3099	橋
            はし	3000	箸
            にほん	3000	日本
            """
        )

        assertEquals(listOf("橋", "箸", "端"), lexicon.lookup("はし").map { it.text })
        assertEquals(listOf("日本"), lexicon.lookup("にほん").map { it.text })
        assertTrue(lexicon.lookup("にほ").isEmpty())
        assertEquals(2, lexicon.readingCount)
        assertEquals(4, lexicon.candidateCount)
    }

    @Test
    fun `normalizes katakana and half width katakana readings`() {
        val lexicon = load("こーひー\t3000\t珈琲")

        assertEquals("珈琲", lexicon.lookup("コーヒー").single().text)
        assertEquals("珈琲", lexicon.lookup("ｺｰﾋｰ").single().text)
    }

    @Test
    fun `bounded prefix lookup predicts longer readings`() {
        val lexicon = load(
            """
            にほん	4075	日本
            にほんご	2098	日本語
            にほんしゅ	5089	日本酒
            にほんじん	2099	日本人
            にゅーす	3000	ニュース
            """
        )

        assertEquals(
            listOf("日本", "日本酒"),
            lexicon.lookupPrefix("にほ", limit = 2).map { it.text }
        )
        assertEquals(
            listOf("日本", "日本酒"),
            lexicon.lookupPrefix("ニホ", limit = 2).map { it.text }
        )
    }

    @Test
    fun `deduplicates candidates using the highest score`() {
        val lexicon = load(
            """
            はし	100	橋
            はし	900	橋
            """
        )

        assertEquals(900, lexicon.lookup("はし").single().score)
        assertEquals(1, lexicon.candidateCount)
    }

    @Test
    fun `ignores comments and malformed records without failing the keyboard`() {
        val lexicon = load(
            """
            # comment

            missing-columns
            はし	not-a-number	橋
            ${'\t'}100${'\t'}空
            はし	500	箸
            """
        )

        assertEquals(listOf("箸"), lexicon.lookup("はし").map { it.text })
    }

    @Test
    fun `applies a per reading candidate limit after ranking`() {
        val lexicon = load(
            """
            はし	1	端
            はし	3	橋
            はし	2	箸
            """,
            limit = 2
        )

        assertEquals(listOf("橋", "箸"), lexicon.lookup("はし").map { it.text })
    }
}
