package com.shingihou.sghvoice.processing

import android.content.Context
import android.content.SharedPreferences
import com.shingihou.sghvoice.learning.CorrectionScope
import com.shingihou.sghvoice.learning.LearnedTerms
import com.shingihou.sghvoice.learning.PersonalizationRepository
import org.json.JSONArray
import org.json.JSONObject

/**
 * 詞庫管理器
 * 管理自訂詞彙與修正規則，用於提升辨識精確度
 * 以最長匹配優先原則進行詞彙修正
 */
class DictionaryManager internal constructor(
    private val prefs: SharedPreferences,
    personalizationProvider: () -> PersonalizationRepository
) {
    constructor(context: Context) : this(
        context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE),
        { PersonalizationRepository.getInstance(context.applicationContext) }
    )

    companion object {
        private const val PREF_NAME = "sgh_voice_dictionary"
        private const val KEY_CUSTOM_WORDS = "custom_words"
        private const val KEY_CORRECTIONS = "corrections"
        private const val KEY_SCENE_WORDS_PREFIX = "scene_custom_words."
        const val MAX_SCENE_CUSTOM_WORDS = 100

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

        // ─── 使用場景預設；僅提供拼字與格式參考，不是新增事實的來源。───
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
            "software_development" to ScenePreset(
                label = "軟體開發",
                customWords = listOf(
                    "GitHub", "GitHub Actions", "CI/CD", "git push", "pull request",
                    "TypeScript", "Kotlin", "Firebase", "Gradle", "API", "WebSocket",
                    "commit", "deployment", "Docker"
                ),
                corrections = emptyMap(),
                systemPromptExtra = "軟體開發場景：保留原文中的產品名、程式碼、指令與檔名拼寫；" +
                    "不把普通詞擅自改成產品名，不新增操作步驟、技術細節或事實。" +
                    "依原文意思補標點和分段，不改變語言。"
            ),
            "business_japanese" to ScenePreset(
                label = "商務日文",
                customWords = listOf(
                    "見積書", "請求書", "納期", "契約書", "発注書", "稟議", "議事録",
                    "ご確認", "お打ち合わせ", "担当者", "取引先", "お世話になっております"
                ),
                corrections = emptyMap(),
                systemPromptExtra = "商務日文場景：若原文為日文，保留原本敬語程度；" +
                    "不因場景而翻譯語言，不額外加入寒暄、敬稱、姓名、日期、金額或承諾。" +
                    "依原文意思補標點與分段，不新增事實。"
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

        /**
         * Built-in spellings the dictation guard may accept as a repair of a misheard span
         * (同音字／片假名 → 已知詞). Never sent to a provider by this function.
         */
        internal fun builtInSpellingTerms(): List<String> =
            VocabularyHintPolicy.technicalTerms + BASE_CUSTOM_WORDS + BASE_CORRECTIONS.values +
                SCENE_PRESETS.values.flatMap { it.customWords }

        /** Built-in known mishearings (wrong -> right): base and scene correction rules. */
        internal fun builtInSpellingAliases(): Map<String, String> =
            SCENE_PRESETS.values.fold(BASE_CORRECTIONS) { acc, scene -> acc + scene.corrections }
    }

    // A denied field must not initialize/read the learned repository just to build a prompt.
    private val personalization by lazy(personalizationProvider)

    /** 自訂詞彙清單（用於 Whisper prompt 提升辨識率） */
    private var customWords: MutableList<String> = mutableListOf()

    /** 修正對照表（錯誤 → 正確） */
    private var corrections: MutableMap<String, String> = mutableMapOf()

    /** 目前啟用的場景 */
    var activeScene: String
        get() = prefs.getString("active_scene", "general")?.takeIf { it in SCENE_PRESETS } ?: "general"
        set(value) { prefs.edit().putString("active_scene", value.takeIf { it in SCENE_PRESETS } ?: "general").apply() }

    init {
        loadCustomWords()
        loadCorrections()
    }

    /**
     * 建立 Whisper 提示詞
     * 合併使用者詞彙、人工修正學到的完整詞與場景詞彙，幫助 Whisper 辨識專有名詞。
     * 最多 50 個完整詞、800 字元；先選個人詞，最後排列在 Whisper 保留的提示尾端。
     * 字元限制不是 token 計數。新式 STT 會將此拼字清單轉為獨立 keywords。
     */
    fun buildWhisperPrompt(includePersonalization: Boolean = false): String {
        refreshFromDisk()
        val sceneWords = SCENE_PRESETS[activeScene]?.customWords ?: emptyList()
        return VocabularyHintPolicy.buildWhisperPrompt(
            customWords = customWords + corrections.values,
            // Only 已生效 words; 待確認 words stay on the device until confirmed.
            learnedWords = if (includePersonalization) personalization.getPromptWords(limit = 50) else emptyList(),
            sceneWords = sceneWords,
            baseWords = BASE_CUSTOM_WORDS,
            sceneCustomWords = getSceneCustomWords()
        )
    }

    /** 拼字參考 JSON；只讀人工新增／人工編輯確認的詞，不把 AI 輸出寫回詞庫。 */
    fun buildLlmVocabularyHint(text: String, includePersonalization: Boolean = false): String {
        refreshFromDisk()
        val scene = SCENE_PRESETS[activeScene]
        return VocabularyHintPolicy.buildLlmVocabularyHint(
            text = text,
            customWords = customWords + corrections.values,
            // A learned CJK->CJK pair is STT-only: handing it to the LLM invites
            // replacement in unrelated contexts (在家裡 → 再加裡, バスケット → パスケット).
            learnedWords = if (includePersonalization) learnedLlmWords() else emptyList(),
            sceneWords = scene?.customWords ?: emptyList(),
            baseWords = BASE_CUSTOM_WORDS,
            corrections = BASE_CORRECTIONS + (scene?.corrections ?: emptyMap()) + corrections,
            sceneCustomWords = getSceneCustomWords()
        )
    }

    /**
     * 套用詞彙修正
     * 合併基礎修正 + 場景修正 + 使用者自訂修正（使用者規則 > 場景規則 > 基底規則）
     * 以最長匹配優先原則，將辨識錯誤的詞彙替換為正確版本
     *
     * @param text 需要修正的文字
     * @return 修正後的文字
     */
    fun applyCorrections(text: String, includePersonalization: Boolean = false): String {
        refreshFromDisk()
        val sceneCorrections = SCENE_PRESETS[activeScene]?.corrections ?: emptyMap()
        val learnedCorrections = linkedMapOf<String, String>().apply {
            // Repository 已依信心、證據與最近使用排序；同一錯字只採最高順位。
            // Only 已生效 rules replace text, and only in the language context they were learned in.
            if (includePersonalization && personalization.isEnabled()) {
                val textScope = LearnedTerms.textScope(text)
                personalization.getActiveVoiceCorrections()
                    // Han and kana have no reliable word boundaries. A learned バス→パス
                    // must not rewrite バスケット. CJK rules are never literal replacements;
                    // CJK->CJK is STT-only, CJK->Latin may be a guarded spelling alias.
                    // Word-bounded Latin and user-entered manual rules are unaffected.
                    .filter { !containsCjk(it.wrongText) && !containsCjk(it.correctedText) }
                    .filter { it.scope == CorrectionScope.ANY || it.scope == CorrectionScope.LATIN || it.scope == textScope }
                    .forEach { rule -> putIfAbsent(rule.wrongText, rule.correctedText) }
            }
        }
        // 合併修正規則：人工編輯學習 > 使用者自訂 > 場景 > 基底
        val merged = BASE_CORRECTIONS + sceneCorrections + corrections + learnedCorrections
        // 單次由左至右掃描可避免 A→B、B→C 產生非預期連鎖替換。
        return VocabularyHintPolicy.applyCorrections(text, merged, learnedCorrections.keys)
    }

    private fun learnedLlmWords(): List<String> {
        if (!personalization.isEnabled()) return emptyList()
        return personalization.getActiveVoiceCorrections()
            .asSequence()
            .filterNot { isCjkToCjk(it.wrongText, it.correctedText) }
            .map { it.promptText }
            .filter { it.isNotBlank() }
            .distinct()
            .take(50)
            .toList()
    }

    private fun isCjkToCjk(wrong: String, corrected: String): Boolean = containsCjk(wrong) && containsCjk(corrected)

    private fun containsCjk(text: String): Boolean = text.codePoints().anyMatch {
        when (Character.UnicodeScript.of(it)) {
            Character.UnicodeScript.HAN,
            Character.UnicodeScript.HIRAGANA,
            Character.UnicodeScript.KATAKANA -> true
            else -> it == 0x30FC || it == 0xFF70
        }
    }

    /**
     * Known mishearings the dictation guard may accept as a Han/kanji span being replaced by
     * the right-hand spelling: built-in, active-scene and user-entered correction rules, plus
     * 已生效 learned rules when [includeLearned] (the current field allows personalization).
     * 待確認 learned rules are never aliases. Manual and built-in rules win over learned ones.
     */
    fun getSpellingAliases(includeLearned: Boolean = false): Map<String, String> {
        refreshFromDisk()
        val learned = if (includeLearned && personalization.isEnabled()) {
            // CJK->ASCII terms stay aliases; CJK->CJK pairs (including pure kana) never do.
            personalization.getLearnedSpellingAliases().filterNot { isCjkToCjk(it.key, it.value) }
        } else emptyMap()
        return learned + builtInSpellingAliases() + (SCENE_PRESETS[activeScene]?.corrections ?: emptyMap()) + corrections
    }

    /**
     * 取得目前場景的 Claude 額外 system prompt
     */
    fun getSceneSystemPromptExtra(): String {
        return SCENE_PRESETS[activeScene]?.systemPromptExtra ?: ""
    }

    /** Local, manually entered scene terms. These never create literal replacement rules. */
    fun getSceneCustomWords(sceneId: String = activeScene): List<String> {
        if (sceneId !in SCENE_PRESETS) return emptyList()
        return runCatching {
            val raw = prefs.getString(KEY_SCENE_WORDS_PREFIX + sceneId, null) ?: return emptyList()
            val array = JSONArray(raw)
            (0 until array.length()).asSequence()
                .mapNotNull { VocabularyHintPolicy.sanitizeTerm(array.optString(it)) }
                .distinctBy { it.lowercase(java.util.Locale.ROOT) }
                .take(MAX_SCENE_CUSTOM_WORDS)
                .toList()
        }.getOrDefault(emptyList())
    }

    /** Returns false for invalid, duplicate or over-limit terms; cloud prompt budgets still apply. */
    fun addSceneCustomWord(word: String, sceneId: String = activeScene): Boolean {
        if (sceneId !in SCENE_PRESETS) return false
        val normalized = VocabularyHintPolicy.sanitizeTerm(word) ?: return false
        val words = getSceneCustomWords(sceneId)
        if (words.size >= MAX_SCENE_CUSTOM_WORDS || words.any { it.equals(normalized, ignoreCase = true) }) return false
        saveSceneCustomWords(sceneId, words + normalized)
        return true
    }

    fun removeSceneCustomWord(word: String, sceneId: String = activeScene) {
        if (sceneId !in SCENE_PRESETS) return
        saveSceneCustomWords(sceneId, getSceneCustomWords(sceneId).filterNot { it == word })
    }

    private fun saveSceneCustomWords(sceneId: String, words: List<String>) {
        val array = JSONArray()
        words.forEach { array.put(it) }
        prefs.edit().putString(KEY_SCENE_WORDS_PREFIX + sceneId, array.toString()).apply()
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
    fun getCustomWords(): List<String> {
        loadCustomWords()
        return customWords.toList()
    }

    /** 取得所有修正規則 */
    fun getCorrections(): Map<String, String> {
        loadCorrections()
        return corrections.toMap()
    }

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

    private fun refreshFromDisk() {
        loadCustomWords()
        loadCorrections()
    }

}

/**
 * 單次、非連鎖的最長詞彙替換器。獨立成純 Kotlin 物件以便 JVM 測試。
 */
internal object TextCorrectionEngine {
    private val literalToken = Regex(
        "`[^`\\r\\n]+`|(?:https?://|www\\.)[^\\s<>]+|" +
            "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}|" +
            "[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+|" +
            "(?:[A-Za-z]:[\\\\/]|(?:\\.\\.?|~)?/)[^\\s<>]+",
        RegexOption.IGNORE_CASE
    )

    /**
     * @param nameProtectedKeys rules (learned ones) that may never touch a name next to a
     * title (林先生, Mr. Lin). Manual/built-in rules are known aliases and may.
     */
    fun apply(text: String, corrections: Map<String, String>, nameProtectedKeys: Set<String> = emptySet()): String {
        // A dictionary/learned rule may fix spelling only. Rules whose two sides differ in a
        // number, unit, date, sign, currency or negation are never applied (problem 5).
        val sortedCorrections = corrections.entries
            .filter { it.key.isNotEmpty() && it.key != it.value }
            .filter { FactPreservation.correctionPreservesFacts(it.key, it.value) }
            .sortedByDescending { it.key.length }
        if (sortedCorrections.isEmpty()) return text
        val protectedRanges = literalRanges(text)
        val nameRanges = if (nameProtectedKeys.isEmpty()) emptyList() else FactPreservation.nameRanges(text)

        val corrected = buildString(text.length) {
            var offset = 0
            var rangeIndex = 0
            while (offset < text.length) {
                while (rangeIndex < protectedRanges.size && protectedRanges[rangeIndex].last < offset) {
                    rangeIndex += 1
                }
                val protectedRange = protectedRanges.getOrNull(rangeIndex)
                if (protectedRange != null && offset in protectedRange) {
                    append(text, offset, protectedRange.last + 1)
                    offset = protectedRange.last + 1
                    continue
                }
                val candidates = if (nameRanges.isEmpty()) sortedCorrections else sortedCorrections.filter { entry ->
                    entry.key !in nameProtectedKeys || nameRanges.none {
                        offset <= it.last && offset + entry.key.length > it.first
                    }
                }
                val match = findMatch(text, offset, candidates, protectedRange)
                if (match == null) {
                    append(text[offset])
                    offset += 1
                } else {
                    append(match.value)
                    offset += match.key.length
                }
            }
        }
        // In context a spelling rule may still touch a quantity (下五 -> 上五 in 零下五度). The
        // dictation guard's extractor decides: any changed numeric fact keeps the original text.
        return if (NumericFacts.sameFacts(text, corrected)) corrected else text
    }

    /**
     * Longest rule wins. English spelling rules also match case-insensitively
     * (Github actions, gitHub, KOTLUN); among equally long rules an exact-case match wins.
     */
    private fun findMatch(
        text: String,
        offset: Int,
        sortedCorrections: List<Map.Entry<String, String>>,
        protectedRange: IntRange?
    ): Map.Entry<String, String>? {
        var best: Map.Entry<String, String>? = null
        for (entry in sortedCorrections) {
            val wrong = entry.key
            if (best != null && wrong.length < best.key.length) break
            if (protectedRange != null && offset + wrong.length > protectedRange.first) continue
            val exact = text.regionMatches(offset, wrong, 0, wrong.length)
            val caseless = !exact && best == null && wrong.any { it in 'A'..'Z' || it in 'a'..'z' } &&
                text.regionMatches(offset, wrong, 0, wrong.length, ignoreCase = true)
            if (!exact && !caseless) continue
            if (!hasSafeAsciiWordBoundary(text, offset, wrong)) continue
            if (exact) return entry
            best = entry
        }
        return best
    }

    internal fun containsUnprotectedTerm(text: String, word: String): Boolean {
        if (word.isEmpty()) return false
        val protectedRanges = literalRanges(text)
        var start = text.indexOf(word, ignoreCase = true)
        while (start >= 0) {
            if (hasSafeAsciiWordBoundary(text, start, word) &&
                protectedRanges.none { start <= it.last && start + word.length > it.first }
            ) return true
            start = text.indexOf(word, start + 1, ignoreCase = true)
        }
        return false
    }

    private fun literalRanges(text: String): List<IntRange> = literalToken.findAll(text)
        // CI/CD is also shaped like a relative path; retain the explicitly supported acronym.
        .filterNot { it.value.equals("ci/cd", ignoreCase = true) }
        .map { it.range }
        .toList()

    /** ASCII 詞的首尾各自守門；CJK 可直接相鄰，多詞片語也不能吃掉英文單字的一半。 */
    private fun hasSafeAsciiWordBoundary(text: String, start: Int, wrong: String): Boolean {
        val end = start + wrong.length
        val leftSafe =
            !isAsciiWordCharacter(wrong.first()) || start == 0 ||
                !isAsciiWordCharacter(text[start - 1])
        val rightSafe =
            !isAsciiWordCharacter(wrong.last()) || end == text.length ||
                !isAsciiWordCharacter(text[end])
        return leftSafe && rightSafe
    }

    private fun isAsciiWordCharacter(char: Char): Boolean =
        char in 'A'..'Z' || char in 'a'..'z' || char in '0'..'9' || char == '_'
}
