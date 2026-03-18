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
            return "API Key 未設定，請先到設定頁填入。"
        case let .networkError(message):
            return "LLM 網路錯誤：\(message)"
        case let .invalidResponse(message):
            return "LLM 回應錯誤：\(message)"
        case .emptyResponse:
            return "LLM 回傳空結果。"
        case let .parseError(message):
            return "LLM 解析失敗：\(message)"
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
    
    // 短文本門檻：20 字以下且無填充詞時跳過 LLM 處理
    private let shortTextThreshold = 20
    
    // 填充詞清單
    private let fillerWords = [
        "嗯", "啊", "那個", "就是", "然後", "對啊", "就是說",
        "えーと", "あの", "えー", "まあ", "その",
        "um", "uh", "like", "you know", "well", "so"
    ]
    
    // 系統提示詞
    private let basePrompt = "語音辨識後處理。規則：
1. 刪除填充詞：嗯、啊、那個、就是、えー特、あの、um、uh、like
2. 口語自我修正→只保留最終版本
3. 標點符號：加上正確標點，適當分段
4. 不改寫核心句意，保持原語言（中/日/英混合保持原樣）
5. 只輸出結果，不加解釋
6. 所有中文必須是繁體中文
"
    
    private func getSystemPrompt() -> String {
        let style = ApiConfig.shared.outputStyle
        let base = basePrompt
        var prompt = ""
        
        switch style {
        case "line":
            prompt = base + "7. 語氣設定為【LINE 訊息】：文字精簡、口語自然，不要過於死板。"
        case "email":
            prompt = base + "7. 語氣設定為【正式 Email】：文字得體、結構嚴謹且專業。"
        default:
            prompt = base + "7. 語氣設定為【一般文字】：語氣中立，字句稍微順過即可。"
        }
        
        let sceneExtra = DictionaryManager.shared.getSceneSystemPromptExtra()
        if !sceneExtra.isEmpty {
            prompt += "
" + sceneExtra
        }
        return prompt
    }
    
    func postProcess(text: String) async throws -> String {
        if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return text }
        if ApiConfig.shared.llmEngine == "none" { return text }
        
        // 短文本且無填充詞 → 跳過 LLM 處理
        if text.count <= shortTextThreshold && !containsFillerWords(text) {
            return text
        }
        
        let engine = ApiConfig.shared.llmEngine
        let systemPrompt = getSystemPrompt()
        
        switch engine {
        case "claude":
            return try await processClaude(text: text, systemPrompt: systemPrompt)
        case "openai":
            return try await processOpenAiLike(text: text, systemPrompt: systemPrompt, url: openAiApiUrl, apiKey: ApiConfig.shared.openAiApiKey, model: "gpt-4o")
        case "groq":
            return try await processOpenAiLike(text: text, systemPrompt: systemPrompt, url: groqApiUrl, apiKey: ApiConfig.shared.groqApiKey, model: ApiConfig.defaultGroqLlmModel)
        default:
            return text
        }
    }
    
    private func processClaude(text: String, systemPrompt: String) async throws -> String {
        let apiKey = ApiConfig.shared.anthropicApiKey
        if apiKey.isEmpty { throw LlmError.apiKeyNotSet }
        
        var request = URLRequest(url: claudeApiUrl)
        request.httpMethod = "POST"
        request.addValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.addValue(anthropicVersion, forHTTPHeaderField: "anthropic-version")
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "model": ApiConfig.shared.claudeModel,
            "max_tokens": maxTokens,
            "system": systemPrompt,
            "messages": [
                ["role": "user", "content": text]
            ]
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            return text // Fallback to original
        }
        
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        if let content = json?["content"] as? [[String: Any]], let first = content.first, let result = first["text"] as? String {
            return result.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return text
    }
    
    private func processOpenAiLike(text: String, systemPrompt: String, url: URL, apiKey: String, model: String) async throws -> String {
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
            "temperature": 0.0
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
            return text
        }
        
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        if let choices = json?["choices"] as? [[String: Any]], let first = choices.first, let message = first["message"] as? [String: Any], let result = message["content"] as? String {
            return result.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return text
    }
    
    private func containsFillerWords(_ text: String) -> BooleanLiteralType {
        let lowerText = text.lowercased()
        return fillerWords.contains { lowerText.contains($0.lowercased()) }
    }
}
