package com.shingihou.sghvoice.processing

import com.github.houbb.opencc4j.util.ZhConverterUtil

/**
 * OpenCC 繁體中文轉換器
 * 使用 opencc4j 執行 s2twp（簡體→繁體台灣用語）轉換
 * 三層繁中防護的最後一道防線
 *
 * 只轉換中文字元，英文與日文保持原樣
 */
class OpenCCConverter {

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
            // opencc4j 的 toTraditional 會處理簡體→繁體轉換
            // 非中文字元（英文、日文假名、數字、標點）不會被影響
            ZhConverterUtil.toTraditional(text)
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
