package com.shingihou.sghvoice.ime

import java.nio.ByteBuffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class IndexedZhuyinAssetTest {

    @Test
    fun `sparse reader finds exact rows without loading the full lexicon`() {
        val fixture = indexedFixture(
            "ㄅ" to listOf("吧" to -10),
            "ㄔㄨ" to listOf("出" to -20, "齣" to -40),
            "ㄕㄢ" to listOf("山" to -10, "刪" to -20),
            "ㄕㄢ ㄔㄨˊ" to listOf("刪除" to -15)
        )

        val reader = IndexedZhuyinReader(
            ByteBuffer.wrap(fixture.data),
            parseZhuyinSparseIndex(fixture.index)
        )

        assertEquals(listOf("出", "齣"), reader.lookupExact("ㄔㄨ").map { it.text })
        assertEquals(listOf("刪除"), reader.lookupExact("ㄕㄢ ㄔㄨˊ").map { it.text })
        assertTrue(reader.lookupExact("ㄘㄜˋ").isEmpty())
    }

    @Test
    fun `sparse reader scans a bounded reading prefix across index blocks`() {
        val fixture = indexedFixture(
            "ㄅ" to listOf("吧" to -10),
            "ㄕ" to listOf("詩" to -10),
            "ㄕㄚ" to listOf("沙" to -10),
            "ㄕㄢ" to listOf("山" to -10, "刪" to -20),
            "ㄕㄤ" to listOf("商" to -10),
            "ㄙ" to listOf("思" to -10)
        )

        val reader = IndexedZhuyinReader(
            ByteBuffer.wrap(fixture.data),
            parseZhuyinSparseIndex(fixture.index)
        )
        val rows = reader.lookupPrefix("ㄕ", maxRows = 4)

        assertEquals(listOf("ㄕ", "ㄕㄚ", "ㄕㄢ", "ㄕㄤ"), rows.map { it.key })
        assertEquals(listOf("山", "刪"), rows[2].entries.map { it.text })
    }

    private data class Fixture(val data: ByteArray, val index: String)

    private fun indexedFixture(
        vararg rows: Pair<String, List<Pair<String, Int>>>
    ): Fixture {
        val data = StringBuilder()
        val index = StringBuilder("# stride=2\n")
        var offset = 0
        rows.sortedBy { it.first }.forEachIndexed { rowIndex, (key, entries) ->
            if (rowIndex % 2 == 0) index.append(key).append('\t').append(offset).append('\n')
            val line = key + "\t" + entries.joinToString("|") { (text, score) ->
                "$text:$score"
            } + "\n"
            data.append(line)
            offset += line.toByteArray(Charsets.UTF_8).size
        }
        return Fixture(data.toString().toByteArray(Charsets.UTF_8), index.toString())
    }
}
