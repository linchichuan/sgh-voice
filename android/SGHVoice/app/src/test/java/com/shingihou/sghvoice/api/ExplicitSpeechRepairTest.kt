package com.shingihou.sghvoice.api

import org.junit.Assert.*
import org.junit.Test

class ExplicitSpeechRepairTest {
    @Test fun `repair keeps final quantity including adjacent Chinese prefix`() {
        assertEquals("下午四點開會。", ExplicitSpeechRepair.normalize("下午三點，不是，四點開會。"))
        assertEquals("5點開會。", ExplicitSpeechRepair.normalize("3點，不是，4點，不是，5點開會。"))
        assertEquals("四點半開會。", ExplicitSpeechRepair.normalize("三點，不是，四點半開會。"))
    }

    @Test fun `comparisons and incompatible units are not spoken repairs`() {
        for (text in listOf("三點不是四點。", "三點，不是，四人。", "不要部署，沒有備份。",
            "-三點，不是，四點。", "- 三點，不是，四點。", "+三點，不是，四點。",
            "負三點，不是，四點。", "負 三點，不是，四點。", "第三點，不是，四點。",
            "第 三點，不是，四點。",
            "− 三點，不是，四點。", "－三點，不是，四點。", "＋三點，不是，四點。",
            "沒有，在外接式硬碟裡也找不到。", "有備份嗎？沒有啊，沒有，在硬碟裡找不到。")) {
            assertEquals(text, ExplicitSpeechRepair.normalize(text))
        }
    }

    @Test fun `final Chinese quantity cannot silently change`() {
        val source = "今天下午三點，不是，四點開會，請確認 GitHub Actions。"
        assertTrue(ExplicitSpeechRepair.preservesCorrectedQuantities(source,
            "今天下午四點開會，請確認 GitHub Actions。"))
        assertTrue(ExplicitSpeechRepair.preservesCorrectedQuantities(source,
            "今天下午4 點開會，請確認 GitHub Actions。"))
        assertFalse(ExplicitSpeechRepair.preservesCorrectedQuantities(source,
            "今天下午五點開會，請確認 GitHub Actions。"))
        assertFalse(ExplicitSpeechRepair.preservesCorrectedQuantities(source,
            "今天下午三點開會，請確認 GitHub Actions。"))
        assertFalse(ExplicitSpeechRepair.preservesCorrectedQuantities(
            "三點，不是，四點半開會。", "四點開會。"))
    }

    @Test fun `only unambiguous bounded integer quantities have equivalent spelling`() {
        for ((source, expected) in listOf(
            "四點開會" to "4點開會", "收二十元" to "收20元", "兩個人" to "2個人",
            "一百零二件" to "102件", "一千零二十次" to "1020次",
            "九千九百九十九份" to "9999份", "零次" to "0次"
        )) assertEquals(source, expected, ExplicitSpeechRepair.canonicalizeQuantities(source))

        for (source in listOf(
            "二〇二六年十月四日", "四號", "四點半", "四點五元", "4.5元", "04元",
            "負四元", "負 四元", "-四元", "- 四元", "+四元", "−四元", "－四元", "＋四元", "四萬個", "一百二元",
            "三四個", "四/五元", "v四點", "id_四點", "第十四個", "四點A",
            "`四點`", "https://example.com/會議四點", "/tmp/會議四點"
        )) assertEquals(source, source, ExplicitSpeechRepair.canonicalizeQuantities(source))
    }
}
