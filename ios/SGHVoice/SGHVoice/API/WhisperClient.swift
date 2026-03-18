import Foundation

enum WhisperError: Error {
    case apiKeyNotSet
    case networkError(String)
    case invalidResponse(String)
    case emptyResponse
    case parseError(String)
}

extension WhisperError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .apiKeyNotSet:
            return "API Key 未設定（OpenAI 或 Groq），請先到設定頁填入。"
        case let .networkError(message):
            return "Whisper 網路錯誤：\(message)"
        case let .invalidResponse(message):
            return "Whisper 回應錯誤：\(message)"
        case .emptyResponse:
            return "Whisper 回傳空結果。"
        case let .parseError(message):
            return "Whisper 解析失敗：\(message)"
        }
    }
}

/// OpenAI Whisper API 客戶端
/// 將錄音的 WAV 檔傳送至 Whisper API 取得語音辨識結果
class WhisperClient {
    static let shared = WhisperClient()
    
    private let openAiApiUrl = URL(string: "https://api.openai.com/v1/audio/transcriptions")!
    private let groqApiUrl = URL(string: "https://api.groq.com/openai/v1/audio/transcriptions")!
    
    /// 傳送 WAV 音訊至 Whisper API 進行語音辨識
    ///
    /// - Parameters:
    ///   - wavData: WAV 格式的音訊資料（含 44 byte 標頭）
    ///   - initialPrompt: 提示詞，用於提升辨識精確度（包含自訂詞彙）
    /// - Returns: 辨識後的文字結果
    func transcribe(wavData: Data, initialPrompt: String = "") async throws -> String {
        let sttEngine = ApiConfig.shared.sttEngine
        let useGroq = sttEngine == "groq" || (sttEngine == "openai" && ApiConfig.shared.openAiApiKey.isEmpty && !ApiConfig.shared.groqApiKey.isEmpty)
        
        let apiKey = useGroq ? ApiConfig.shared.groqApiKey : ApiConfig.shared.openAiApiKey
        let apiUrl = useGroq ? groqApiUrl : openAiApiUrl
        let modelName = useGroq ? "whisper-large-v3-turbo" : (ApiConfig.shared.whisperModel.isEmpty ? ApiConfig.defaultWhisperModel : ApiConfig.shared.whisperModel)
        
        if apiKey.isEmpty {
            throw WhisperError.apiKeyNotSet
        }
        
        var request = URLRequest(url: apiUrl)
        request.httpMethod = "POST"
        request.timeoutInterval = 90
        request.addValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        
        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        var body = Data()
        
        // Add file part
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"recording.wav\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/wav\r\n\r\n".data(using: .utf8)!)
        body.append(wavData)
        body.append("\r\n".data(using: .utf8)!)
        
        // Add model part
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"model\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(modelName)\r\n".data(using: .utf8)!)
        
        // Add response_format part
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"response_format\"\r\n\r\n".data(using: .utf8)!)
        body.append("json\r\n".data(using: .utf8)!)
        
        // Add prompt part
        if !initialPrompt.isEmpty {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"prompt\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(initialPrompt)\r\n".data(using: .utf8)!)
        }
        
        // Close boundary
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        
        request.httpBody = body
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw WhisperError.invalidResponse("Not HTTP URL Response")
            }
            
            if !(200...299).contains(httpResponse.statusCode) {
                throw WhisperError.invalidResponse(parseApiErrorMessage(data: data, statusCode: httpResponse.statusCode))
            }
            
            let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
            guard let text = json?["text"] as? String else {
                throw WhisperError.parseError("Missing 'text' in response")
            }
            
            return text.trimmingCharacters(in: .whitespacesAndNewlines)
            
        } catch let error as WhisperError {
            throw error
        } catch let error as URLError {
            switch error.code {
            case .timedOut:
                throw WhisperError.networkError("連線逾時（timeout），請檢查網路或稍後重試。")
            case .notConnectedToInternet:
                throw WhisperError.networkError("裝置目前沒有網路連線。")
            default:
                throw WhisperError.networkError(error.localizedDescription)
            }
        } catch {
            throw WhisperError.networkError(error.localizedDescription)
        }
    }

    private func parseApiErrorMessage(data: Data, statusCode: Int) -> String {
        struct OpenAIErrorResponse: Decodable {
            struct APIError: Decodable {
                let message: String?
                let type: String?
                let code: String?
            }
            let error: APIError?
        }

        if let decoded = try? JSONDecoder().decode(OpenAIErrorResponse.self, from: data),
           let message = decoded.error?.message,
           !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return "HTTP \(statusCode) - \(message)"
        }

        let raw = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
        if let raw, !raw.isEmpty {
            return "HTTP \(statusCode) - \(raw)"
        }
        return "HTTP \(statusCode)"
    }
}
