import Foundation

struct TranscriptionResult {
    let text: String
    let rawText: String
    let success: Bool
    let error: String?
    
    init(text: String = "", rawText: String = "", success: Bool = true, error: String? = nil) {
        self.text = text
        self.rawText = rawText
        self.success = success
        self.error = error
    }
}

protocol TranscriptionProgressDelegate: AnyObject {
    func onWhisperStarted()
    func onWhisperCompleted(text: String)
    func onClaudeStarted()
    func onCompleted(result: TranscriptionResult)
    func onError(error: String)
}

/// 語音辨識處理管線
/// 四層處理流程：
/// 1. Whisper STT — 語音轉文字（含三語提示詞）
/// 2. 詞庫修正 — 自訂詞彙替換（最長匹配優先）
/// 3. Claude 後處理 — 去填充詞、修正標點、潤稿
/// 4. 繁體中文最終防護 (iOS 版目前依賴 Claude 提示詞，後續可擴充 OpenCC)
class TranscriptionPipeline {
    static let shared = TranscriptionPipeline()
    
    private let whisperClient = WhisperClient.shared
    private let claudeClient = ClaudeClient.shared
    private let dictionaryManager = DictionaryManager.shared
    
    weak var delegate: TranscriptionProgressDelegate?
    
    /// 執行完整的處理管線
    func process(wavData: Data) async -> TranscriptionResult {
        do {
            // === 第一層：Whisper 語音辨識 ===
            DispatchQueue.main.async { self.delegate?.onWhisperStarted() }
            
            let whisperPrompt = dictionaryManager.buildWhisperPrompt()
            let rawText = try await whisperClient.transcribe(wavData: wavData, initialPrompt: whisperPrompt)
            
            if rawText.isEmpty {
                let result = TranscriptionResult(text: "", rawText: "", success: true)
                DispatchQueue.main.async { self.delegate?.onCompleted(result: result) }
                return result
            }
            DispatchQueue.main.async { self.delegate?.onWhisperCompleted(text: rawText) }
            
            // === 第二層：詞庫修正 ===
            let correctedText = dictionaryManager.applyCorrections(to: rawText)
            
            // === 第三層：Claude 後處理（含場景指令）===
            DispatchQueue.main.async { self.delegate?.onClaudeStarted() }
            let sceneExtra = dictionaryManager.getSceneSystemPromptExtra()
            
            var finalText = correctedText
            do {
                finalText = try await claudeClient.postProcess(text: correctedText, sceneExtra: sceneExtra)
            } catch {
                // Claude 失敗時降級為使用詞庫修正後的結果
                print("Claude processing failed: \(error)")
            }
            
            // === 第四層：(留給 OpenCC 擴充，目前依靠 Claude prompt 強制切換繁體) ===
            
            let result = TranscriptionResult(text: finalText, rawText: rawText, success: true)
            DispatchQueue.main.async { self.delegate?.onCompleted(result: result) }
            return result
            
        } catch let error {
            let errorMsg = error.localizedDescription
            DispatchQueue.main.async { self.delegate?.onError(error: errorMsg) }
            return TranscriptionResult(text: "", rawText: "", success: false, error: errorMsg)
        }
    }
    
    /// 僅執行 Whisper 辨識（不進行後處理）
    func transcribeOnly(wavData: Data) async -> TranscriptionResult {
        do {
            let whisperPrompt = dictionaryManager.buildWhisperPrompt()
            let rawText = try await whisperClient.transcribe(wavData: wavData, initialPrompt: whisperPrompt)
            return TranscriptionResult(text: rawText, rawText: rawText, success: true)
        } catch {
            return TranscriptionResult(text: "", rawText: "", success: false, error: error.localizedDescription)
        }
    }
}
