package com.shingihou.sghvoice.processing

import com.github.houbb.opencc4j.util.ZhConverterUtil

/**
 * OpenCC 繁體中文轉換器
 * 使用 opencc4j 執行 s2twp（簡體→繁體台灣用語）轉換
 * 三層繁中防護的最後一道防線
 *
 * 只轉換中文子句；含平假名／片假名的子句視為日文，整段保持原字形
 * （否則 opencc 會把日文新字體 画像／会議 改成 畫像／會議）。
 */
class OpenCCConverter {

    private companion object {
        // Clause delimiters; the Japanese 、 is deliberately not a delimiter so a
        // Japanese sentence stays one clause.
        val CLAUSE = Regex("[^。！？!?\\n，,；;]*[。！？!?\\n，,；;]*")
        val KANA = Regex("[\\u3041-\\u309F\\u30A1-\\u30FA\\u30FC-\\u30FF\\uFF66-\\uFF9F]")
    }

    /**
     * 將文字中的簡體中文轉換為繁體中文（台灣用語）
     * 使用 s2twp 模式：簡體 → 繁體 + 台灣慣用詞
     *
     * @param text 待轉換的文字（可能包含中/日/英混合內容）
     * @return 轉換後的文字，中文部分為繁體，英日文不受影響
     */
    fun convert(text: String): String {
        if (text.isBlank()) return text

        return try {
            if (!KANA.containsMatchIn(text)) return ZhConverterUtil.toTraditional(text)
            CLAUSE.findAll(text).joinToString("") { clause ->
                val value = clause.value
                if (value.isEmpty() || KANA.containsMatchIn(value)) value
                else ZhConverterUtil.toTraditional(value)
            }
        } catch (e: Exception) {
            // 轉換失敗時回傳原文，確保不會中斷流程
            text
        }
    }

    /**
     * 檢查文字是否包含簡體中文字元
     * 用於判斷是否需要執行轉換
     */
    fun containsSimplifiedChinese(text: String): Boolean {
        return try {
            val converted = ZhConverterUtil.toTraditional(text)
            converted != text
        } catch (_: Exception) {
            false
        }
    }
}
