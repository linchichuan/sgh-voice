import Foundation

enum WhisperError: Error {
    case apiKeyNotSet
    case networkError(String)
    case invalidResponse(String)
    case emptyResponse
    case parseError(String)
}

/// OpenAI Whisper API 客戶端
/// 將錄音的 WAV 檔傳送至 Whisper API 取得語音辨識結果
class WhisperClient {
    static let shared = WhisperClient()
    
    private let whisperApiUrl = URL(string: "https://api.openai.com/v1/audio/transcriptions")!
    
    /// 傳送 WAV 音訊至 Whisper API 進行語音辨識
    ///
    /// - Parameters:
    ///   - wavData: WAV 格式的音訊資料（含 44 byte 標頭）
    ///   - initialPrompt: 提示詞，用於提升辨識精確度（包含自訂詞彙）
    /// - Returns: 辨識後的文字結果
    func transcribe(wavData: Data, initialPrompt: String = "") async throws -> String {
        let apiKey = ApiConfig.shared.openAiApiKey
        let modelName = ApiConfig.shared.whisperModel
        
        if apiKey.isEmpty {
            throw WhisperError.apiKeyNotSet
        }
        
        var request = URLRequest(url: whisperApiUrl)
        request.httpMethod = "POST"
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
                let errorMsg = String(data: data, encoding: .utf8) ?? "HTTP \(httpResponse.statusCode)"
                throw WhisperError.invalidResponse(errorMsg)
            }
            
            let json = try JSONSerialization.jsonObject(with: data, options: []) as? [String: Any]
            guard let text = json?["text"] as? String else {
                throw WhisperError.parseError("Missing 'text' in response")
            }
            
            return text.trimmingCharacters(in: .whitespacesAndNewlines)
            
        } catch let error as WhisperError {
            throw error
        } catch {
            throw WhisperError.networkError(error.localizedDescription)
        }
    }
}
