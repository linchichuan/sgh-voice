import Foundation

/// OpenCC 繁體中文轉換器（s2twp：簡體 → 繁體 + 台灣慣用詞）
/// 三語混合三層防護的最後一道防線，鏡像 Android 版
/// `processing/OpenCCConverter.kt`（`com.github.houbb:opencc4j`，同樣走 s2twp）。
///
/// **詞表來源**：本檔不自創任何轉換規則，字典資料直接取自上游 OpenCC 專案
/// （https://github.com/BYVoid/OpenCC ，Apache License 2.0），與 macOS 版
/// `requirements.txt` 已使用的 `opencc-python-reimplemented` 套件內建的
/// s2twp 轉換鏈（見該套件 `opencc/config/s2twp.json`）完全同一組檔案：
///   1. STPhrases.txt + STCharacters.txt（簡體→繁體，片語優先於單字）
///   2. TWPhrases.txt（繁體→台灣慣用語，例如 软件→軟體）
///   3. TWVariants.txt（繁體異體字→台灣慣用字形）
/// 詞條內容同源複製到 `Resources/OpenCCData/`，僅正規化換行；完整授權與來源
/// 說明見該目錄 `NOTICE.txt`、`LICENSE-APACHE-2.0.txt`。
///
/// **演算法**：每個階段用「貪婪最長匹配」（從每個位置起，先試最長的字典
/// key，找不到就縮短一個字元再試，都找不到就照抄該字元往後移一格）。
/// STCharacters 的 key 恆為 1 字、STPhrases 的 key 恆為 ≥2 字（已對照
/// 上游資料驗證），所以把兩者合併成一個字典、統一做最長匹配，等價於
/// 上游 Python 實作「先整段套 STPhrases、剩餘部分才套 STCharacters」的
/// 兩階段行為，不需要真的分兩次掃描。
///
/// **Fail-open**：Bundle 內找不到字典檔（例如尚未透過 Xcode 打包驗證資源
/// 路徑）或解析失敗時，`convert(_:)` 原樣回傳輸入字串，不拋錯、不中斷
/// pipeline——與 Android 版 `OpenCCConverter.convert()` 的 try/catch 語意
/// 一致：這是防護層，不能變成新的當機來源。
final class OpenCCConverter {
    static let shared = OpenCCConverter()

    /// 一個轉換階段：key→value 對照表，以及表中最長 key 的字元數
    /// （用來限制「貪婪最長匹配」每個位置最多要往前試幾個字元）。
    private struct Stage {
        let map: [String: String]
        let maxKeyLength: Int
    }

    private let stages: [Stage]

    /// 三個階段字典是否都成功載入。任一階段缺失就整體視為不可用並
    /// fail-open（寧可跳過最終防護，不要用「只套了一半的轉換鏈」產生
    /// 不完整、可能更奇怪的輸出）。
    private let isAvailable: Bool

    private init() {
        let combinedSimplified = Self.loadStage(resourceNames: ["STPhrases", "STCharacters"])
        let twPhrases = Self.loadStage(resourceNames: ["TWPhrases"])
        let twVariants = Self.loadStage(resourceNames: ["TWVariants"])

        if let combinedSimplified, let twPhrases, let twVariants {
            self.stages = [combinedSimplified, twPhrases, twVariants]
            self.isAvailable = true
        } else {
            self.stages = []
            self.isAvailable = false
        }
    }

    /// 將文字中的簡體中文轉換為繁體中文（台灣用語）。
    /// 只轉換中文字元；英文、日文假名、數字、標點不受影響（字典裡沒有
    /// 對應 key，逐字複製時原樣通過）。
    ///
    /// - Parameter text: 待轉換的文字（可能包含中/日/英混合內容）
    /// - Returns: 轉換後的文字；字典不可用或輸入為空時原樣回傳輸入。
    func convert(_ text: String) -> String {
        guard isAvailable, !text.isEmpty else { return text }

        return Self.convertPreservingJapanese(text) { value in
            self.convertWithoutLanguageProtection(value)
        }
    }

    /// OpenCC 無法從 Han 字元判斷中日文。這裡鏡像 macOS 的
    /// `convert_traditional_preserving_japanese` 契約：含假名的 clause 預設視為
    /// 日文，只轉換其中帶有明確簡體提示的 Han run；無假名 clause 則先保護常見
    /// 日文新字體詞，再套用 s2twp。這可避免「来週の動画を参考にしてください」
    /// 被改成中文異體，同時仍能把「请确认软件设置」正規化為繁中。
    private static func convertPreservingJapanese(
        _ text: String,
        convert: (String) -> String
    ) -> String {
        var output = ""
        var clause = ""

        func flushClause() {
            guard !clause.isEmpty else { return }
            if containsKana(clause) {
                output += convertExplicitSimplifiedHanRuns(in: clause, convert: convert)
            } else {
                output += convertProtectingJapaneseTerms(clause, convert: convert)
            }
            clause = ""
        }

        for character in text {
            if clauseSeparators.contains(character) {
                flushClause()
                output.append(character)
            } else {
                clause.append(character)
            }
        }
        flushClause()
        return output
    }

    private func convertWithoutLanguageProtection(_ text: String) -> String {
        var chars = Array(text)
        for stage in stages {
            chars = Self.applyStage(chars, stage: stage)
        }
        return String(chars)
    }

    private static let clauseSeparators = Set<Character>("，,。！？!?；;\n")

    /// 與 macOS `multilingual.py` 同一組高頻日文新字體保護詞；按長度排序，
    /// 避免短詞先遮蔽長詞。
    private static let japaneseKanjiTerms = [
        "来週", "画像", "動画", "台風", "国際", "会議", "会社", "大学",
        "開発", "実装", "検証", "仕様", "画面", "機能", "設定", "処理",
        "変換", "対応", "連絡", "電話", "予約", "病院", "医療", "薬品",
        "患者", "受付", "診療", "請求", "保険", "計画", "関係", "状態", "参考",
        "学習", "写真", "説明", "検索", "選択", "登録", "更新", "削除", "保存",
        "編集", "入力", "出力", "送信", "受信", "接続", "認証", "権限", "環境",
        "運用", "改善", "最適化", "自動化"
    ].sorted { lhs, rhs in lhs.count > rhs.count }

    private static let ambiguousJapaneseKanjiTerms: Set<String> = ["参考"]
    private static let simplifiedHintTerms = [
        "数据", "视频", "软件", "优化", "设置", "问题", "确认", "处理",
        "开发", "体验", "云服务"
    ]
    private static let simplifiedHintCharacters = Set<Character>(
        "这们为发软网优个后关开问际图视频从还进过边门时产业东车书无验处确请"
    )

    private static func containsKana(_ text: String) -> Bool {
        text.unicodeScalars.contains { scalar in
            (0x3040...0x30FF).contains(scalar.value)
                || (0x31F0...0x31FF).contains(scalar.value)
        }
    }

    private static func isHan(_ character: Character) -> Bool {
        character.unicodeScalars.allSatisfy { scalar in
            (0x3400...0x9FFF).contains(scalar.value)
        }
    }

    private static func containsSimplifiedChineseHint(_ text: String) -> Bool {
        simplifiedHintTerms.contains(where: text.contains)
            || text.contains(where: simplifiedHintCharacters.contains)
    }

    private static func convertExplicitSimplifiedHanRuns(
        in clause: String,
        convert: (String) -> String
    ) -> String {
        var output = ""
        var run = ""

        func flushRun() {
            guard !run.isEmpty else { return }
            output += containsSimplifiedChineseHint(run)
                ? convertProtectingJapaneseTerms(run, chineseHint: true, convert: convert)
                : run
            run = ""
        }

        for character in clause {
            if isHan(character) {
                run.append(character)
            } else {
                flushRun()
                output.append(character)
            }
        }
        flushRun()
        return output
    }

    private static func convertProtectingJapaneseTerms(
        _ text: String,
        chineseHint: Bool = false,
        convert: (String) -> String
    ) -> String {
        let hasSimplifiedHint = containsSimplifiedChineseHint(text)
        var protected: [String: String] = [:]
        var masked = text

        for term in japaneseKanjiTerms {
            if ambiguousJapaneseKanjiTerms.contains(term)
                && (chineseHint || hasSimplifiedHint) {
                continue
            }
            guard masked.contains(term) else { continue }
            let placeholder = "ZXQJAPANESE\(protected.count)QXZ"
            protected[placeholder] = term
            masked = masked.replacingOccurrences(of: term, with: placeholder)
        }

        var converted = convert(masked)
        for (placeholder, term) in protected {
            converted = converted.replacingOccurrences(of: placeholder, with: term)
        }
        return converted
    }

    /// 檢查文字轉換後是否有變化（用於判斷是否包含簡體中文／台灣用語差異）。
    /// 對齊 Android 版 `OpenCCConverter.containsSimplifiedChinese()`。
    func containsSimplifiedChinese(_ text: String) -> Bool {
        guard isAvailable, !text.isEmpty else { return false }
        return convert(text) != text
    }

    // MARK: - 貪婪最長匹配

    private static func applyStage(_ input: [Character], stage: Stage) -> [Character] {
        guard !stage.map.isEmpty else { return input }
        var result: [Character] = []
        result.reserveCapacity(input.count)
        let n = input.count
        var i = 0
        while i < n {
            let maxLen = min(stage.maxKeyLength, n - i)
            var matchedLength = 0
            var matchedValue: String?
            var len = maxLen
            while len >= 1 {
                let candidate = String(input[i..<(i + len)])
                if let value = stage.map[candidate] {
                    matchedValue = value
                    matchedLength = len
                    break
                }
                len -= 1
            }
            if let matchedValue {
                result.append(contentsOf: matchedValue)
                i += matchedLength
            } else {
                result.append(input[i])
                i += 1
            }
        }
        return result
    }

    // MARK: - 字典載入

    private static func loadStage(resourceNames: [String]) -> Stage? {
        var map: [String: String] = [:]
        var maxKeyLength = 1
        var loadedAny = false

        for name in resourceNames {
            guard let url = resourceURL(named: name),
                  let content = try? String(contentsOf: url, encoding: .utf8)
            else {
                continue
            }
            loadedAny = true
            // 統一先把 CRLF 正規化成 LF 再切行——上游檔案裡 TWPhrases.txt 是
            // CRLF、其餘是 LF，靠 split 而非依賴平台特定的行尾偵測比較保險。
            let normalized = content.replacingOccurrences(of: "\r\n", with: "\n")
            for rawLine in normalized.split(separator: "\n", omittingEmptySubsequences: true) {
                let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !line.isEmpty else { continue }
                let columns = line.split(separator: "\t", maxSplits: 1, omittingEmptySubsequences: false)
                guard columns.count == 2 else { continue }
                let key = String(columns[0])
                var value = String(columns[1])
                // 部分 STCharacters／STPhrases 條目有多個候選（以空白分隔），
                // 沿用上游 Python 實作的規則：先取第一個候選。
                if let spaceIndex = value.firstIndex(of: " ") {
                    value = String(value[value.startIndex..<spaceIndex])
                }
                guard !key.isEmpty, !value.isEmpty else { continue }
                // 同一 stage 內若多個來源檔重複同一 key，保留先載入者
                // （STPhrases 在 STCharacters 之前載入，片語優先）。
                if map[key] == nil {
                    map[key] = value
                }
                maxKeyLength = max(maxKeyLength, key.count)
            }
        }

        guard loadedAny, !map.isEmpty else { return nil }
        return Stage(map: map, maxKeyLength: maxKeyLength)
    }

    /// 依序嘗試幾種常見的 bundle 資源尋找方式，涵蓋「子目錄結構被
    /// Xcode 保留」與「資源被攤平到 bundle 根目錄」兩種可能——本機
    /// 沒有完整 Xcode，無法實際打包驗證是哪一種，用 fallback 兜底。
    private static func resourceURL(named name: String) -> URL? {
        if let url = Bundle.main.url(forResource: name, withExtension: "txt", subdirectory: "OpenCCData") {
            return url
        }
        if let url = Bundle.main.url(forResource: name, withExtension: "txt") {
            return url
        }
        return nil
    }
}
