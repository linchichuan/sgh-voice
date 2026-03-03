import Foundation

struct ScenePreset {
    let label: String
    let customWords: [String]
    let corrections: [String: String]
    let systemPromptExtra: String
}

/// 詞庫管理器
/// 管理自訂詞彙與修正規則，用於提升辨識精確度
/// 以最長匹配優先原則進行詞彙修正
class DictionaryManager {
    static let shared = DictionaryManager()
    
    private let defaults = UserDefaults.standard
    
    // Keys
    private let keyCustomWords = "custom_words"
    private let keyCorrections = "corrections"
    private let keyActiveScene = "active_scene"
    
    // 內部基礎詞庫
    private let baseCustomWords = [
        "新義豊", "Shingihou", "KusuriJapan", "Medical Supporter",
        "SGH Phone", "林紀全", "薬機法", "PMD Act",
        "Ultravox", "Twilio", "n8n", "LINE Bot",
        "福岡", "博多", "代表取締役", "繁體中文", "輸入法",
        "Repo", "Repository", "GitHub", "API", "Android", "Kotlin",
        "Whisper", "Claude", "Haiku", "Sonnet", "OpenCC",
        "Docker", "Zeabur", "Google Play", "IME",
        "Push-to-Talk", "PCM", "WAV", "WebSocket", "OkHttp", "SwiftData"
    ]
    
    private let baseCorrections: [String: String] = [
        "新義豐": "新義豊",
        "新义丰": "新義豊",
        "醫療supporter": "Medical Supporter",
        "medicalsupporter": "Medical Supporter",
        "薬日本": "kusurijapan",
        "林紀泉": "林紀全",
        "林記全": "林紀全",
        "輸入發": "輸入法",
        "繁體重文": "繁體中文",
        "語音辨是": "語音辨識",
        "cloud code": "Claude Code",
        "Cloud Code": "Claude Code",
        "cloud AI": "Claude AI",
        "Cloud AI": "Claude AI",
        "cloud haiku": "Claude Haiku",
        "Cloud Haiku": "Claude Haiku"
    ]
    
    // 使用場景預設
    let scenePresets: [String: ScenePreset] = [
        "general": ScenePreset(
            label: "一般",
            customWords: [],
            corrections: [:],
            systemPromptExtra: ""
        ),
        "medical": ScenePreset(
            label: "醫療・藥品・生技",
            customWords: [
                "心電図", "CT", "MRI", "エコー", "内視鏡", "カルテ", "レントゲン",
                "血液検査", "尿検査", "病理検査", "生検", "処方箋",
                "收縮壓", "舒張壓", "血氧飽和度", "SpO2", "HbA1c",
                "内科", "外科", "整形外科", "皮膚科", "眼科", "耳鼻咽喉科",
                "産婦人科", "小児科", "精神科", "循環器内科", "消化器内科",
                "アムロジピン", "メトホルミン", "ランソプラゾール", "ロキソニン",
                "アジスロマイシン", "プレドニゾロン", "ワーファリン", "インスリン",
                "オプジーボ", "キイトルーダ", "アバスチン", "ハーセプチン",
                "リリカ", "デパス", "マイスリー",
                "幹細胞", "iPS細胞", "CAR-T", "免疫チェックポイント",
                "PD-1", "PD-L1", "抗体医薬", "バイオシミラー",
                "再生医療", "遺伝子治療", "エクソソーム", "NK細胞",
                "電腦斷層", "核磁共振", "超音波", "胃鏡", "大腸鏡",
                "處方籤", "轉診單", "病歷", "掛號", "健保"
            ],
            corrections: [
                "心電図": "心電図", "处方笺": "處方箋", "处方签": "處方籤",
                "干细胞": "幹細胞", "免疫检查点": "免疫チェックポイント"
            ],
            systemPromptExtra: "8. 醫療場景專用：保留所有醫療術語、藥品名、檢查名稱的原文，不得簡化或改寫。日文醫療術語（カルテ、処方箋等）保持原樣。藥品名稱保持原文拼寫（アムロジピン、Opdivo 等）。"
        )
    ]
    
    // 動態資料
    private(set) var customWords: [String] = []
    private(set) var corrections: [String: String] = [:]
    
    var activeScene: String {
        get { return defaults.string(forKey: keyActiveScene) ?? "general" }
        set { defaults.set(newValue, forKey: keyActiveScene) }
    }
    
    private init() {
        loadCustomWords()
        loadCorrections()
    }
    
    /// 建立 Whisper 提示詞
    func buildWhisperPrompt() -> String {
        let sceneWords = scenePresets[activeScene]?.customWords ?? []
        var allWordsSet = Set(baseCustomWords)
        sceneWords.forEach { allWordsSet.insert($0) }
        customWords.forEach { allWordsSet.insert($0) }
        
        let allWords = Array(allWordsSet).prefix(50)
        if allWords.isEmpty { return "" }
        
        let prompt = allWords.joined(separator: "、")
        return String(prompt.prefix(800))
    }
    
    /// 套用詞彙修正
    func applyCorrections(to text: String) -> String {
        let sceneCorrections = scenePresets[activeScene]?.corrections ?? [:]
        
        var merged = baseCorrections
        sceneCorrections.forEach { merged[$0.key] = $0.value }
        corrections.forEach { merged[$0.key] = $0.value }
        
        if merged.isEmpty { return text }
        
        var result = text
        // 依鍵長度排序（最長優先匹配）
        let sortedKeys = merged.keys.sorted { $0.count > $1.count }
        
        for key in sortedKeys {
            if let correct = merged[key] {
                result = result.replacingOccurrences(of: key, with: correct)
            }
        }
        return result
    }
    
    /// 取得目前場景的 Claude 額外 system prompt
    func getSceneSystemPromptExtra() -> String {
        return scenePresets[activeScene]?.systemPromptExtra ?? ""
    }
    
    // MARK: - Data Management
    
    func addCustomWord(_ word: String) {
        let trimmed = word.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty && !customWords.contains(trimmed) {
            customWords.append(trimmed)
            saveCustomWords()
        }
    }
    
    func removeCustomWord(_ word: String) {
        customWords.removeAll { $0 == word }
        saveCustomWords()
    }
    
    func addCorrection(wrong: String, correct: String) {
        let trimmedWrong = wrong.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedCorrect = correct.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedWrong.isEmpty && !trimmedCorrect.isEmpty {
            corrections[trimmedWrong] = trimmedCorrect
            saveCorrections()
        }
    }
    
    func removeCorrection(wrong: String) {
        corrections.removeValue(forKey: wrong)
        saveCorrections()
    }
    
    // MARK: - Persistence
    
    private func loadCustomWords() {
        if let saved = defaults.stringArray(forKey: keyCustomWords) {
            customWords = saved
        }
    }
    
    private func saveCustomWords() {
        defaults.set(customWords, forKey: keyCustomWords)
    }
    
    private func loadCorrections() {
        if let saved = defaults.dictionary(forKey: keyCorrections) as? [String: String] {
            corrections = saved
        }
    }
    
    private func saveCorrections() {
        defaults.set(corrections, forKey: keyCorrections)
    }
}
