import Foundation

enum LlmError: Error {
    case apiKeyNotSet
    case networkError(String)
    case invalidResponse(String)
    case emptyResponse
    case parseError(String)
}

extension LlmError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .apiKeyNotSet:
            return L10n.text("API Key 未設定，請先到設定頁填入。")
        case let .networkError(message):
            return L10n.format("LLM 網路錯誤：%@", message)
        case let .invalidResponse(message):
            return L10n.format("LLM 回應錯誤：%@", message)
        case .emptyResponse:
            return L10n.text("LLM 回傳空結果。")
        case let .parseError(message):
            return L10n.format("LLM 解析失敗：%@", message)
        }
    }
}

/// 通用 LLM 客戶端
/// 支援 Anthropic Claude, OpenAI GPT, 以及 Groq (OpenAI 相容)
class LlmClient {
    static let shared = LlmClient()
    
    private let claudeApiUrl = URL(string: "https://api.anthropic.com/v1/messages")!
    private let openAiApiUrl = URL(string: "https://api.openai.com/v1/chat/completions")!
    private let groqApiUrl = URL(string: "https://api.groq.com/openai/v1/chat/completions")!
    
    private let anthropicVersion = "2023-06-01"
    private let maxTokens = 1024
    private let translationMaxTokens = 2048

    private lazy var session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.urlCache = nil
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.httpCookieStorage = nil
        configuration.httpShouldSetCookies = false
        configuration.timeoutIntervalForRequest = 90
        return URLSession(configuration: configuration)
    }()
    
    // 短文本門檻：20 字以下且無填充詞時跳過 LLM 處理
    private let shortTextThreshold = 20
    
    // 填充詞清單
    private let fillerWords = [
        "嗯", "啊", "那個", "就是", "然後", "對啊", "就是說",
        "えーと", "あの", "えー", "まあ", "その",
        "um", "uh", "like", "you know", "well", "so"
    ]
    
    private func getSystemPrompt() -> String {
        let style = ApiConfig.shared.outputStyle
        let base = DictationContract.lockedSystemPrompt
        var prompt = ""
        
        switch style {
        case "line":
            prompt = base + "\nSTYLE: LINE 訊息。只調整標點與分段，不得精簡、改寫或回答。"
        case "email":
            prompt = base + "\nSTYLE: 正式 Email。只調整標點與分段，不得新增稱謂、內容、結尾或回答。"
        default:
            prompt = base + "\nSTYLE: 一般文字。只調整標點與分段，不得改寫或回答。"
        }
        
        let sceneExtra = DictionaryManager.shared.getSceneSystemPromptExtra()
        if !sceneExtra.isEmpty {
            prompt += "\n" + sceneExtra
        }
        return prompt
    }
    
    /// LLM 後處理。
    /// - Parameter mode: "dictate"（口述清理，預設）會套用尾部幻覺截斷；"edit"（Quick-Rewrite /
    ///   翻譯 / Email / 語音指令改寫）會跳過截斷，因為這些模式 LLM 本來就該主動加內容。
    ///   既有 caller 不指定 mode 時等同 "dictate"，不破壞向後相容。
    func postProcess(text: String, mode: String = "dictate") async throws -> String {
        if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return text }
        if ApiConfig.shared.llmEngine == "none" { return text }

        // 短文本且無填充詞 → 跳過 LLM 處理
        if text.count <= shortTextThreshold && !containsFillerWords(text) {
            return text
        }

        let engine = ApiConfig.shared.llmEngine
        let systemPrompt = getSystemPrompt()

        let llmResult: String
        switch engine {
        case "claude":
            llmResult = try await processClaude(
                text: DictationContract.wrappedSource(text),
                systemPrompt: systemPrompt,
                maxTokens: maxTokens
            )
        case "openai":
            llmResult = try await processOpenAiLike(
                text: DictationContract.wrappedSource(text),
                systemPrompt: systemPrompt,
                url: openAiApiUrl,
                apiKey: ApiConfig.shared.openAiApiKey,
                model: "gpt-4o",
                maxTokens: maxTokens
            )
        case "groq":
            llmResult = try await processOpenAiLike(
                text: DictationContract.wrappedSource(text),
                systemPrompt: systemPrompt,
                url: groqApiUrl,
                apiKey: ApiConfig.shared.groqApiKey,
                model: ApiConfig.defaultGroqLlmModel,
                maxTokens: maxTokens
            )
        default:
            return text
        }

        // 守門：尾部 LLM 補寫截斷（只在 dictate mode 套用）
        if let validated = validateLlmResult(rawInput: text, llmResult: llmResult, mode: mode) {
            return validated
        }
        // validateLlmResult 回傳 nil → discard，fallback 用原始輸入
        return text
    }

    /// 一次 LLM 呼叫完成 1–4 種語言翻譯；回應不符合嚴格 JSON 契約時直接失敗。
    /// 翻譯失敗不得回退成來源文字，以免 UI 把原文冒充翻譯結果。
    func translate(
        text: String,
        targets: [TranslationLanguage]
    ) async throws -> [TranslationLanguage: String] {
        let source = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !source.isEmpty else { throw LlmError.emptyResponse }

        let normalized = try TranslationContract.normalizedTargets(targets)
        let systemPrompt = try TranslationContract.systemPrompt(for: normalized)
        let wrappedSource = try TranslationContract.wrappedSource(source)

        let response: String
        switch ApiConfig.shared.llmEngine {
        case "claude":
            response = try await processClaude(
                text: wrappedSource,
                systemPrompt: systemPrompt,
                maxTokens: translationMaxTokens
            )
        case "openai":
            response = try await processOpenAiLike(
                text: wrappedSource,
                systemPrompt: systemPrompt,
                url: openAiApiUrl,
                apiKey: ApiConfig.shared.openAiApiKey,
                model: "gpt-4o",
                maxTokens: translationMaxTokens
            )
        case "groq":
            response = try await processOpenAiLike(
                text: wrappedSource,
                systemPrompt: systemPrompt,
                url: groqApiUrl,
                apiKey: ApiConfig.shared.groqApiKey,
                model: ApiConfig.defaultGroqLlmModel,
                maxTokens: translationMaxTokens
            )
        default:
            throw LlmError.apiKeyNotSet
        }
        let translations = try TranslationContract.parse(response, targets: normalized)
        return try TranslationContract.validateSemantics(
            source: source,
            translations: translations
        )
    }
    
    private func processClaude(
        text: String,
        systemPrompt: String,
        maxTokens: Int
    ) async throws -> String {
        let apiKey = ApiConfig.shared.anthropicApiKey
        if apiKey.isEmpty { throw LlmError.apiKeyNotSet }

        var request = URLRequest(url: claudeApiUrl)
        request.httpMethod = "POST"
        request.addValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.addValue(anthropicVersion, forHTTPHeaderField: "anthropic-version")
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = Self.claudeRequestBody(
            model: ApiConfig.shared.claudeModel,
            text: text,
            systemPrompt: systemPrompt,
            maxTokens: maxTokens
        )

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await perform(request)
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw LlmError.invalidResponse(apiErrorMessage(data: data, response: response))
        }

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw LlmError.parseError("Invalid Claude response object")
        }
        return try Self.parseClaudeText(json)
    }

    static func claudeRequestBody(
        model: String,
        text: String,
        systemPrompt: String,
        maxTokens: Int
    ) -> [String: Any] {
        var body: [String: Any] = [
            "model": model,
            "max_tokens": maxTokens,
            "system": systemPrompt,
            "messages": [
                ["role": "user", "content": text]
            ]
        ]

        switch model {
        case "claude-sonnet-5", "claude-opus-5":
            body["thinking"] = ["type": "disabled"]
            body["output_config"] = ["effort": "low"]
        case "claude-fable-5":
            body["thinking"] = ["type": "adaptive"]
            body["output_config"] = ["effort": "low"]
        default:
            break
        }
        return body
    }

    static func parseClaudeText(_ json: [String: Any]) throws -> String {
        if json["stop_reason"] as? String == "refusal" {
            throw LlmError.invalidResponse("Claude refused this request.")
        }
        guard let content = json["content"] as? [[String: Any]] else {
            throw LlmError.parseError("Missing Claude response content")
        }
        let text = content.compactMap { block -> String? in
            guard block["type"] as? String == "text" else { return nil }
            return (block["text"] as? String)?
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        .filter { !$0.isEmpty }
        .joined(separator: "\n")

        guard !text.isEmpty else {
            throw LlmError.parseError("Missing Claude response text")
        }
        return text
    }
    
    private func processOpenAiLike(
        text: String,
        systemPrompt: String,
        url: URL,
        apiKey: String,
        model: String,
        maxTokens: Int
    ) async throws -> String {
        if apiKey.isEmpty { throw LlmError.apiKeyNotSet }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "model": model,
            "messages": [
                ["role": "system", "content": systemPrompt],
                ["role": "user", "content": text]
            ],
            "temperature": 0.0,
            "max_tokens": maxTokens
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await perform(request)
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            throw LlmError.invalidResponse(apiErrorMessage(data: data, response: response))
        }
        
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        if let choices = json?["choices"] as? [[String: Any]], let first = choices.first, let message = first["message"] as? [String: Any], let result = message["content"] as? String {
            return result.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        throw LlmError.parseError("Missing OpenAI-compatible response text")
    }

    private func apiErrorMessage(data: Data, response: URLResponse) -> String {
        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? -1
        if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let error = object["error"] as? [String: Any],
           let message = error["message"] as? String,
           !message.isEmpty {
            return "HTTP \(statusCode) - \(message)"
        }
        return "HTTP \(statusCode)"
    }

    private func perform(_ request: URLRequest) async throws -> (Data, URLResponse) {
        do {
            return try await session.data(for: request)
        } catch let error as URLError {
            switch error.code {
            case .timedOut:
                throw LlmError.networkError(L10n.text("連線逾時，請檢查網路或稍後重試。"))
            case .notConnectedToInternet:
                throw LlmError.networkError(L10n.text("裝置目前沒有網路連線。"))
            default:
                throw LlmError.networkError(error.localizedDescription)
            }
        } catch {
            throw LlmError.networkError(error.localizedDescription)
        }
    }
    
    private func containsFillerWords(_ text: String) -> BooleanLiteralType {
        let lowerText = text.lowercased()
        return fillerWords.contains { lowerText.contains($0.lowercased()) }
    }

    // MARK: - LLM 結果守門（移植自 macOS transcriber.py:_validate_llm_result）

    /// LLM 結果守門。回傳 nil 表示應該捨棄（caller 用 rawInput fallback），
    /// 否則回傳處理後字串（可能已截斷尾部補寫）。
    ///
    /// - 目前 iOS 版未實作全段幻覺偵測（macOS 的 `_is_llm_hallucination`），
    ///   只移植「尾部補寫截斷」邏輯。後續若要補上全段檢查可在此擴充。
    /// - mode=="edit" 會跳過截斷：Quick-Rewrite / 翻譯 / Email / 語音指令改寫
    ///   本來就是 LLM 主動加內容，截斷會誤毀正常輸出。
    ///
    /// 範例（單元 test 級別）：
    ///   raw  = "今天天氣很好我們去公園散步色色名稱不用到這麼大"
    ///   llm  = "今天天氣很好，我們去公園散步，色色名稱不用到這麼大，所以你看能不能調整。而且你仔細看，從"
    ///   mode = "dictate"
    ///   → 回傳 "今天天氣很好，我們去公園散步，色色名稱不用到這麼大。"
    ///
    ///   同上 raw/llm，mode = "edit" → 回傳原 llm（不截斷）
    ///
    ///   raw = "翻譯這句"，llm = "Translate this sentence." → 回傳 llm（無擴寫對應，不截斷）
    func validateLlmResult(rawInput: String, llmResult: String, mode: String) -> String? {
        if mode != "dictate" {
            return llmResult.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        guard let safeCandidate = DictationContract.validateCandidate(
            source: rawInput,
            candidate: llmResult
        ) else {
            print("[LlmClient] 🛡️ 捨棄疑似回答／改寫型輸出，改用原始逐字稿")
            return nil
        }
        if let truncated = truncateTrailingHallucination(
            originalText: rawInput,
            llmResult: safeCandidate
        ) {
            print("[LlmClient] ✂️ 截斷尾部 LLM 補寫（\(safeCandidate.count)字→\(truncated.count)字）")
            return truncated
        }
        return safeCandidate
    }

    /// 偵測「raw 內容完整保留，但 LLM 在結尾自己接話」的補寫型幻覺，回傳截斷版。
    /// - 若不是這種模式（含完全改寫、無擴寫、純標點擴寫）→ 回傳 nil（caller 用原 llmResult）。
    /// - 觸發條件：raw ≥10 字，final 比 raw 長 15% 以上，且 raw 的尾段（≥2 個字元的尾段）能在
    ///   final 找到對應位置，該位置之後 final 還有 ≥4 個實質字元（去掉純標點/空白）。
    ///
    /// ⚠️ Swift 版限制：未引入 OpenCC s2twp 簡繁正規化。若 raw 為簡體、LLM 輸出繁體擴寫，
    /// 後 N 字反查可能 miss → 漏截。可接受的安全側失敗（不會誤截正常輸出）。
    /// TODO: 加 OpenCC s2twp 提升簡繁混合準確度。
    ///
    /// Swift 沒有 difflib，採用簡化版：取 raw 的後 N 字（N = min(10, raw.count/2)，至少 2），
    /// 用 String.range(of:options:.backwards) 在 llmResult 內反向搜尋，找最後出現位置。
    func truncateTrailingHallucination(originalText: String, llmResult: String) -> String? {
        let trimChars = CharacterSet(charactersIn: " ，。、！？.,!?\n\t")
        let oRaw = originalText.trimmingCharacters(in: .whitespacesAndNewlines)
        let r = llmResult.trimmingCharacters(in: .whitespacesAndNewlines)

        if oRaw.count < 10 { return nil }                       // 太短易誤判
        if Double(r.count) <= Double(oRaw.count) * 1.15 { return nil }  // 沒明顯擴寫

        // 取 raw 結尾「去掉純標點後」的最後 N 個字元（rstrip 標點/空白）
        let trimCharSet: Set<Character> = [" ", "，", "。", "、", "！", "？", ".", ",", "!", "?", "\n", "\t"]
        var oClean = oRaw
        while let last = oClean.last, trimCharSet.contains(last) {
            oClean.removeLast()
        }
        if oClean.count < 2 { return nil }

        // N = min(10, oClean.count / 2)，至少 2 才有意義
        let n = max(2, min(10, oClean.count / 2))
        let tail = String(oClean.suffix(n))

        // 在 r 中反向搜尋 tail 的最後出現位置
        guard let tailRange = r.range(of: tail, options: .backwards) else {
            return nil  // 找不到 → 可能是完全改寫，安全跳過
        }

        // end_in_result = tailRange.upperBound 的 String.Index
        let endIndex = tailRange.upperBound
        let trailing = String(r[endIndex...])

        // 去掉純標點/空白後，實質字元 ≥ 4 才視為補寫型幻覺
        let substantive = trailing.trimmingCharacters(in: trimChars)
        if substantive.count < 4 { return nil }

        // 截斷
        var truncated = String(r[..<endIndex])

        // 末尾若無結束標點，從 trailing 取第一個句號/驚嘆/問號接上；都沒有就補中文句號
        let endingPunct: Set<Character> = ["，", "。", "、", "！", "？", ".", ",", "!", "?", "\n", "\t"]
        let strongEndingPunct: Set<Character> = ["。", "！", "？", ".", "!", "?"]
        if let last = truncated.last, !endingPunct.contains(last) {
            var picked: Character? = nil
            for ch in trailing where strongEndingPunct.contains(ch) {
                picked = ch
                break
            }
            truncated.append(picked ?? "。")
        }
        return truncated
    }
}
