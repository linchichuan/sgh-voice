import Foundation

enum ClaudeError: Error {
    case networkError(String)
    case invalidResponse
    case emptyResponse
}

/// Anthropic Claude API 客戶端
/// 語音辨識後處理：去填充詞、修正標點、保持三語混合
class ClaudeClient {
    static let shared = ClaudeClient()
    
    private let apiUrl = URL(string: "https://api.anthropic.com/v1/messages")!
    private let anthropicVersion = "2023-06-01"
    private let maxTokens = 1024
    
    // 短文本門檻：20 字以下且無填充詞時跳過 LLM 處理
    private let shortTextThreshold = 20
    
    // 填充詞清單（中/日/英三語）
    private let fillerWords = [
        "嗯", "啊", "那個", "就是", "然後", "對啊", "就是說",
        "えーと", "あの", "えー", "まあ", "その",
        "um", "uh", "like", "you know", "well", "so"
    ]
    
    // 系統提示詞：語音辨識後處理規則 (分場合)
    private let basePrompt = """
    語音辨識後處理。規則：
    1. 刪除填充詞：嗯、啊、那個、就是、えーと、あの、um、uh、like
    2. 口語自我修正→只保留最終版本
    3. 標點符號：加上正確標點，適當分段
    4. 不改寫核心句意，保持原語言（中/日/英混合保持原樣）
    5. 只輸出結果，不加解釋
    6. 所有中文必須是繁體中文\n
    """
    
    private var linePrompt: String { basePrompt + "7. 語氣設定為【LINE 訊息】：文字精簡、口語自然，不要過於死板。" }
    private var emailPrompt: String { basePrompt + "7. 語氣設定為【正式 Email】：文字得體、結構嚴謹且專業。" }
    private var normalPrompt: String { basePrompt + "7. 語氣設定為【一般文字】：語氣中立，字句稍微順過即可。" }
    
    /// 對語音辨識結果進行後處理
    func postProcess(text: String, sceneExtra: String = "") async throws -> String {
        // 空白文字直接回傳
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return text }
        
        // 短文本且無填充詞 → 跳過 LLM 處理
        if trimmed.count <= shortTextThreshold && !containsFillerWords(text) {
            return text
        }
        
        let apiKey = ApiConfig.shared.anthropicApiKey
        if apiKey.isEmpty {
            return text
        }
        
        // 決定提示詞（根據設定的轉換風格）
        var systemPrompt: String
        switch ApiConfig.shared.outputStyle {
        case "line":
            systemPrompt = linePrompt
        case "email":
            systemPrompt = emailPrompt
        default:
            systemPrompt = normalPrompt
        }
        
        if !sceneExtra.isEmpty {
            systemPrompt += "\n\(sceneExtra)"
        }
        
        var request = URLRequest(url: apiUrl)
        request.httpMethod = "POST"
        request.addValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.addValue(anthropicVersion, forHTTPHeaderField: "anthropic-version")
        request.addValue("application/json", forHTTPHeaderField: "content-type")
        
        let body: [String: Any] = [
            "model": ApiConfig.shared.claudeModel,
            "max_tokens": maxTokens,
            "system": systemPrompt,
            "messages": [
                [
                    "role": "user",
                    "content": text
                ]
            ]
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body, options: [])
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                return text
            }
            
            if !(200...299).contains(httpResponse.statusCode) {
                // 回應有錯誤，為了不崩潰直接返回原文
                return text
            }
            
            let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
            if let content = json?["content"] as? [[String: Any]],
               let firstContent = content.first,
               let replyText = firstContent["text"] as? String {
                return replyText.trimmingCharacters(in: .whitespacesAndNewlines)
            } else {
                return text
            }
        } catch {
            return text
        }
    }
    
    /// 檢查文字中是否包含填充詞
    private func containsFillerWords(_ text: String) -> Bool {
        let lowerText = text.lowercased()
        return fillerWords.contains { lowerText.contains($0.lowercased()) }
    }
}
