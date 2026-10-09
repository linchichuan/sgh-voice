package com.shingihou.sghvoice.ime

import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class TraditionalZhuyinDisplayTest {
    @Test fun `stock traditional candidates exclude three simplified variants at their common readings`() {
        val lexicon = AndroidZhuyinLexicon(RuntimeEnvironment.getApplication())
        for ((reading, forms) in listOf("ㄊㄧˇ" to ("體" to "体"), "ㄨㄤˇ" to ("網" to "网"), "ㄨㄢˋ" to ("萬" to "万"))) {
            val exact = lexicon.lookup(reading).map { it.text }
            assertTrue(exact.contains(forms.first))
            assertFalse("$reading must not suggest ${forms.second}", exact.contains(forms.second))
            assertFalse(lexicon.lookupToneFolded(reading, 48).any { it.text == forms.second })
            assertFalse(lexicon.lookupPrefix(reading, 48).any { it.text == forms.second })
        }
        assertTrue("云 is also a legitimate traditional word, not a global replacement", lexicon.lookup("ㄩㄣˊ").any { it.text == "云" })
    }
}
