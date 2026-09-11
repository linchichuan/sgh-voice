package com.shingihou.sghvoice.processing

import org.junit.Assert.assertEquals
import org.junit.Test

class TextCorrectionEngineTest {

    @Test
    fun `uses longest match and does not cascade replacement output`() {
        val rules = linkedMapOf(
            "新義豐" to "新義豊",
            "新義" to "錯誤",
            "新義豊" to "不應連鎖"
        )

        assertEquals(
            "公司是新義豊。",
            TextCorrectionEngine.apply("公司是新義豐。", rules)
        )
    }

    @Test
    fun `ascii correction requires word boundaries`() {
        val rules = mapOf("cloud" to "Claude")

        assertEquals(
            "Claude and cloudflare",
            TextCorrectionEngine.apply("cloud and cloudflare", rules)
        )
    }

    @Test
    fun `ascii names can touch cjk but must not replace part of a longer english phrase`() {
        assertEquals(
            "請用GitHub推送，git hubby 不要改，cloud coder 也不要改。",
            TextCorrectionEngine.apply(
                "請用github推送，git hubby 不要改，cloud coder 也不要改。",
                mapOf("github" to "GitHub", "git hub" to "GitHub", "cloud code" to "Claude Code")
            )
        )
    }

    @Test
    fun `cjk correction can match inside a sentence`() {
        assertEquals(
            "這是語音辨識測試",
            TextCorrectionEngine.apply(
                "這是語音辨是測試",
                mapOf("語音辨是" to "語音辨識")
            )
        )
    }
}
