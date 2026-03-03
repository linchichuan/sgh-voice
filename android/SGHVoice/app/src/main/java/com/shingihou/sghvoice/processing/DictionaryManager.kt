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

        /**
         * 內部基礎詞庫 — 提升辨識精度，不在 UI 顯示
         * 包含公司專有名詞、常見技術術語、人名修正等
         */
        private val BASE_CUSTOM_WORDS = listOf(
            "新義豊", "Shingihou", "KusuriJapan", "Medical Supporter",
            "SGH Phone", "林紀全", "薬機法", "PMD Act",
            "Ultravox", "Twilio", "n8n", "LINE Bot",
            "福岡", "博多", "代表取締役", "繁體中文", "輸入法",
            "Repo", "Repository", "GitHub", "API", "Android", "Kotlin",
            "Whisper", "Claude", "Haiku", "Sonnet", "OpenCC",
            "Docker", "Zeabur", "Google Play", "IME",
            "Push-to-Talk", "PCM", "WAV", "WebSocket", "OkHttp",
        )

        private val BASE_CORRECTIONS = mapOf(
            "新義豐" to "新義豊",
            "新义丰" to "新義豊",
            "醫療supporter" to "Medical Supporter",
            "medicalsupporter" to "Medical Supporter",
            "薬日本" to "kusurijapan",
            "林紀泉" to "林紀全",
            "林記全" to "林紀全",
            "輸入發" to "輸入法",
            "繁體重文" to "繁體中文",
            "語音辨是" to "語音辨識",
            // Claude 常被 Whisper 辨識為 cloud/Cloud
            "cloud code" to "Claude Code",
            "Cloud Code" to "Claude Code",
            "cloud AI" to "Claude AI",
            "Cloud AI" to "Claude AI",
            "cloud haiku" to "Claude Haiku",
            "Cloud Haiku" to "Claude Haiku",
        )

        // ─── 使用場景預設（同步自 macOS config.py SCENE_PRESETS）───
        data class ScenePreset(
            val label: String,
            val customWords: List<String>,
            val corrections: Map<String, String>,
            val systemPromptExtra: String
        )

        val SCENE_PRESETS = mapOf(
            "general" to ScenePreset(
                label = "一般",
                customWords = emptyList(),
                corrections = emptyMap(),
                systemPromptExtra = ""
            ),
            "medical" to ScenePreset(
                label = "醫療・藥品・生技",
                customWords = listOf(
                    // 日文醫療（診療科目・檢查）
                    "心電図", "CT", "MRI", "エコー", "内視鏡", "カルテ", "レントゲン",
                    "血液検査", "尿検査", "病理検査", "生検", "処方箋",
                    "收縮壓", "舒張壓", "血氧飽和度", "SpO2", "HbA1c",
                    // 診療科目
                    "内科", "外科", "整形外科", "皮膚科", "眼科", "耳鼻咽喉科",
                    "産婦人科", "小児科", "精神科", "循環器内科", "消化器内科",
                    // 藥品（日本常用處方藥）
                    "アムロジピン", "メトホルミン", "ランソプラゾール", "ロキソニン",
                    "アジスロマイシン", "プレドニゾロン", "ワーファリン", "インスリン",
                    "オプジーボ", "キイトルーダ", "アバスチン", "ハーセプチン",
                    "リリカ", "デパス", "マイスリー",
                    // 生技・再生醫療
                    "幹細胞", "iPS細胞", "CAR-T", "免疫チェックポイント",
                    "PD-1", "PD-L1", "抗体医薬", "バイオシミラー",
                    "再生医療", "遺伝子治療", "エクソソーム", "NK細胞",
                    // 臺灣醫療中文
                    "電腦斷層", "核磁共振", "超音波", "胃鏡", "大腸鏡",
                    "處方籤", "轉診單", "病歷", "掛號", "健保",
                ),
                corrections = mapOf(
                    "心電図" to "心電図", "处方笺" to "處方箋", "处方签" to "處方籤",
                    "干细胞" to "幹細胞", "免疫检查点" to "免疫チェックポイント",
                ),
                systemPromptExtra = "8. 醫療場景專用：保留所有醫療術語、藥品名、檢查名稱的原文，不得簡化或改寫。" +
                    "日文醫療術語（カルテ、処方箋等）保持原樣。" +
                    "藥品名稱保持原文拼寫（アムロジピン、Opdivo 等）。"
            )
        )
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)

    /** 自訂詞彙清單（用於 Whisper prompt 提升辨識率） */
    private var customWords: MutableList<String> = mutableListOf()

    /** 修正對照表（錯誤 → 正確） */
    private var corrections: MutableMap<String, String> = mutableMapOf()

    /** 目前啟用的場景 */
    var activeScene: String
        get() = prefs.getString("active_scene", "general") ?: "general"
        set(value) { prefs.edit().putString("active_scene", value).apply() }

    init {
        loadCustomWords()
        loadCorrections()
    }

    /**
     * 建立 Whisper 提示詞
     * 合併基礎詞庫 + 場景詞彙 + 使用者自訂詞彙，幫助 Whisper 辨識專有名詞
     * 上限 50 個（醫療術語較多）
     */
    fun buildWhisperPrompt(): String {
        val sceneWords = SCENE_PRESETS[activeScene]?.customWords ?: emptyList()
        val allWords = (BASE_CUSTOM_WORDS + sceneWords + customWords).toSet().take(50)
        if (allWords.isEmpty()) return ""
        val prompt = allWords.joinToString("、")
        return if (prompt.length > 800) prompt.take(800) else prompt
    }

    /**
     * 套用詞彙修正
     * 合併基礎修正 + 場景修正 + 使用者自訂修正（使用者規則 > 場景規則 > 基底規則）
     * 以最長匹配優先原則，將辨識錯誤的詞彙替換為正確版本
     *
     * @param text 需要修正的文字
     * @return 修正後的文字
     */
    fun applyCorrections(text: String): String {
        val sceneCorrections = SCENE_PRESETS[activeScene]?.corrections ?: emptyMap()
        // 合併修正規則：使用者自訂 > 場景 > 基底
        val merged = BASE_CORRECTIONS + sceneCorrections + corrections
        if (merged.isEmpty()) return text

        var result = text
        // 依鍵長度排序（最長優先匹配），避免短詞誤匹配
        val sortedCorrections = merged.entries.sortedByDescending { it.key.length }

        for ((wrong, correct) in sortedCorrections) {
            result = result.replace(wrong, correct)
        }
        return result
    }

    /**
     * 取得目前場景的 Claude 額外 system prompt
     */
    fun getSceneSystemPromptExtra(): String {
        return SCENE_PRESETS[activeScene]?.systemPromptExtra ?: ""
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
