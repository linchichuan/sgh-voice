package com.shingihou.sghvoice.processing

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject

/**
 * 詞庫管理器
 * 管理自訂詞彙與修正規則，用於提升辨識精確度
 * 以最長匹配優先原則進行詞彙修正
 */
class DictionaryManager(context: Context) {

    companion object {
        private const val PREF_NAME = "sgh_voice_dictionary"
        private const val KEY_CUSTOM_WORDS = "custom_words"
        private const val KEY_CORRECTIONS = "corrections"
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)

    /** 自訂詞彙清單（用於 Whisper prompt 提升辨識率） */
    private var customWords: MutableList<String> = mutableListOf()

    /** 修正對照表（錯誤 → 正確） */
    private var corrections: MutableMap<String, String> = mutableMapOf()

    init {
        loadCustomWords()
        loadCorrections()
        initDefaultCorrections()
    }

    /**
     * 建立 Whisper 提示詞
     * 將自訂詞彙串接為提示文字，幫助 Whisper 辨識專有名詞
     */
    fun buildWhisperPrompt(): String {
        val allWords = customWords.toSet()
        if (allWords.isEmpty()) return ""
        return allWords.joinToString("、")
    }

    /**
     * 套用詞彙修正
     * 以最長匹配優先原則，將辨識錯誤的詞彙替換為正確版本
     *
     * @param text 需要修正的文字
     * @return 修正後的文字
     */
    fun applyCorrections(text: String): String {
        if (corrections.isEmpty()) return text

        var result = text
        // 依鍵長度排序（最長優先匹配），避免短詞誤匹配
        val sortedCorrections = corrections.entries.sortedByDescending { it.key.length }

        for ((wrong, correct) in sortedCorrections) {
            result = result.replace(wrong, correct)
        }
        return result
    }

    /**
     * 新增自訂詞彙
     */
    fun addCustomWord(word: String) {
        if (word.isNotBlank() && word !in customWords) {
            customWords.add(word.trim())
            saveCustomWords()
        }
    }

    /**
     * 移除自訂詞彙
     */
    fun removeCustomWord(word: String) {
        customWords.remove(word)
        saveCustomWords()
    }

    /**
     * 新增修正規則
     */
    fun addCorrection(wrong: String, correct: String) {
        if (wrong.isNotBlank() && correct.isNotBlank()) {
            corrections[wrong.trim()] = correct.trim()
            saveCorrections()
        }
    }

    /**
     * 移除修正規則
     */
    fun removeCorrection(wrong: String) {
        corrections.remove(wrong)
        saveCorrections()
    }

    /** 取得所有自訂詞彙 */
    fun getCustomWords(): List<String> = customWords.toList()

    /** 取得所有修正規則 */
    fun getCorrections(): Map<String, String> = corrections.toMap()

    // ===== 內部方法 =====

    /** 初始化預設修正規則（新義豊相關用語） */
    private fun initDefaultCorrections() {
        val defaults = mapOf(
            "新義豐" to "新義豊",
            "新义丰" to "新義豊",
            "醫療supporter" to "Medical Supporter",
            "medicalsupporter" to "Medical Supporter",
            "薬日本" to "kusurijapan",
            "林紀泉" to "林紀全",
            "林記全" to "林紀全"
        )

        // 只新增尚未存在的預設規則
        for ((wrong, correct) in defaults) {
            if (wrong !in corrections) {
                corrections[wrong] = correct
            }
        }

        // 預設自訂詞彙（提升 Whisper 辨識率）
        val defaultWords = listOf(
            "新義豊", "林紀全", "Medical Supporter", "kusurijapan",
            "福岡", "繁體中文", "輸入法"
        )
        for (word in defaultWords) {
            if (word !in customWords) {
                customWords.add(word)
            }
        }

        saveCorrections()
        saveCustomWords()
    }

    /** 從 SharedPreferences 載入自訂詞彙 */
    private fun loadCustomWords() {
        val json = prefs.getString(KEY_CUSTOM_WORDS, null) ?: return
        try {
            val array = JSONArray(json)
            customWords.clear()
            for (i in 0 until array.length()) {
                customWords.add(array.getString(i))
            }
        } catch (_: Exception) {
            customWords.clear()
        }
    }

    /** 將自訂詞彙儲存至 SharedPreferences */
    private fun saveCustomWords() {
        val array = JSONArray()
        customWords.forEach { array.put(it) }
        prefs.edit().putString(KEY_CUSTOM_WORDS, array.toString()).apply()
    }

    /** 從 SharedPreferences 載入修正規則 */
    private fun loadCorrections() {
        val json = prefs.getString(KEY_CORRECTIONS, null) ?: return
        try {
            val obj = JSONObject(json)
            corrections.clear()
            obj.keys().forEach { key ->
                corrections[key] = obj.getString(key)
            }
        } catch (_: Exception) {
            corrections.clear()
        }
    }

    /** 將修正規則儲存至 SharedPreferences */
    private fun saveCorrections() {
        val obj = JSONObject()
        corrections.forEach { (k, v) -> obj.put(k, v) }
        prefs.edit().putString(KEY_CORRECTIONS, obj.toString()).apply()
    }
}
