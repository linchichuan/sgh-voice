package com.shingihou.sghvoice.ime.manual

import com.shingihou.sghvoice.ime.japanese.CompactJapaneseLexicon
import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

/** Reports desktop JVM costs for the shipped data; this is not device acceptance. */
class OfflineLexiconPerformanceTest {
    private fun retainedHeap(): Long {
        repeat(2) { System.gc(); Thread.sleep(20) }
        return Runtime.getRuntime().let { it.totalMemory() - it.freeMemory() }
    }

    @Test
    fun `measure packaged lexicon loading and short prefix queries`() {
        val baseline = retainedHeap()
        val started = System.nanoTime()
        val english = File("src/main/assets/english/aosp_english.tsv").inputStream().use { CompactEnglishLexicon.load(it) }
        val englishLoadMs = (System.nanoTime() - started) / 1_000_000.0
        val englishHeap = retainedHeap()
        val japaneseStarted = System.nanoTime()
        val japanese = File("src/main/assets/japanese/jmdict_common.tsv").inputStream().use { CompactJapaneseLexicon.load(it) }
        val japaneseLoadMs = (System.nanoTime() - japaneseStarted) / 1_000_000.0
        val japaneseHeap = retainedHeap()
        println("OFFLINE_LEXICON load enMs=$englishLoadMs jaMs=$japaneseLoadMs enRetainedBytes=${englishHeap - baseline} jaRetainedBytes=${japaneseHeap - englishHeap}")
        for (prefix in listOf("a", "s", "th", "あ", "か", "し")) {
            val query: () -> Int = if (prefix[0] < '\u0080') {
                { english.candidates(prefix, 24).size }
            } else {
                { japanese.lookupPrefix(prefix, 24).size }
            }
            repeat(20) { query() }
            val times = LongArray(100) {
                val start = System.nanoTime()
                assertTrue(query() in 1..24)
                System.nanoTime() - start
            }.sorted()
            println("OFFLINE_LEXICON prefix=$prefix p50Ms=${times[50] / 1_000_000.0} p95Ms=${times[95] / 1_000_000.0} maxMs=${times.last() / 1_000_000.0}")
        }
    }
}
