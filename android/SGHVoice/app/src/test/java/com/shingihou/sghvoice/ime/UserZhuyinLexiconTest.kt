package com.shingihou.sghvoice.ime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class UserZhuyinLexiconTest {

    @Test
    fun `custom entry requires one complete syllable per Han character`() {
        assertEquals(
            UserZhuyinEntry("新義豊", "ㄒㄧㄣ ㄧˋ ㄈㄥ"),
            normalizeUserZhuyinEntry(" 新義豊 ", " ㄒㄧㄣ  ㄧˋ ㄈㄥ ")
        )
        assertNull(normalizeUserZhuyinEntry("新義豊", "ㄒㄧㄣ ㄧˋ"))
        assertNull(normalizeUserZhuyinEntry("新義豊", "ㄒ ㄧˋ ㄈㄥ"))
        assertNull(normalizeUserZhuyinEntry("SGH", "ㄟㄙ ㄐㄧ ㄟㄑ"))
    }

    @Test
    fun `custom index supports exact tone-folded prefix and phrase completion`() {
        val index = UserZhuyinIndex(
            listOf(
                UserZhuyinEntry("新義豊", "ㄒㄧㄣ ㄧˋ ㄈㄥ"),
                UserZhuyinEntry("刪除鍵", "ㄕㄢ ㄔㄨˊ ㄐㄧㄢˋ")
            )
        )

        assertEquals(listOf("新義豊"), index.lookup("ㄒㄧㄣ ㄧˋ ㄈㄥ").map { it.text })
        assertEquals(
            listOf("新義豊"),
            index.lookupToneFolded("ㄒㄧㄣ ㄧ ㄈㄥ", 5).map { it.text }
        )
        assertEquals(listOf("刪除鍵"), index.lookupPrefix("ㄕㄢ ㄔ", 5).map { it.text })
        assertEquals(listOf("義豊"), index.lookupNext("新", 5).map { it.text })
        assertTrue(index.lookupNext("新 ", 5).isEmpty())
    }
}
