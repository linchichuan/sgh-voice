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
    func onLlmStarted()
    func onCompleted(result: TranscriptionResult)
    func onError(error: String)
}

/// 語音辨識處理管線
/// 四層處理流程：
/// 1. Whisper STT — 語音轉文字（含三語提示詞）
/// 2. 詞庫修正 — 自訂詞彙替換（最長匹配優先）
/// 3. LLM 後處理 — 去填充詞、修正標點、潤稿 (支援 Claude/OpenAI/Groq)
/// 4. 繁體中文最終防護 (iOS 版目前依賴 LLM 提示詞，後續可擴充 OpenCC)
class TranscriptionPipeline {
    static let shared = TranscriptionPipeline()
    
    private let whisperClient = WhisperClient.shared
    private let llmClient = LlmClient.shared
    private let dictionaryManager = DictionaryManager.shared
    
    weak var delegate: TranscriptionProgressDelegate?
    
    /// 執行完整的處理管線。翻譯模式固定為一次 STT + 一次 LLM，
    /// 並在開始前快照目標語言，避免錄音途中改設定造成輸出錯置。
    func process(
        wavData: Data,
        intent: TranscriptionIntent = .dictate
    ) async -> TranscriptionResult {
        do {
            // === 第一層：Whisper 語音辨識 ===
            DispatchQueue.main.async { self.delegate?.onWhisperStarted() }
            
            let whisperPrompt = dictionaryManager.buildWhisperPrompt()
            let rawText = try await whisperClient.transcribe(wavData: wavData, initialPrompt: whisperPrompt)
            
            if rawText.isEmpty {
                let result = TranscriptionResult(
                    text: "",
                    rawText: "",
                    success: !intent.isTranslation,
                    error: intent.isTranslation ? L10n.text("沒有辨識到可翻譯的語音。") : nil
                )
                if result.success {
                    DispatchQueue.main.async { self.delegate?.onCompleted(result: result) }
                } else {
                    DispatchQueue.main.async {
                        self.delegate?.onError(error: result.error ?? L10n.text("翻譯失敗"))
                    }
                }
                return result
            }
            DispatchQueue.main.async { self.delegate?.onWhisperCompleted(text: rawText) }
            
            // === 第二層：詞庫修正 ===
            let correctedText = dictionaryManager.applyCorrections(to: rawText)
            
            // === 第三層：依錄音意圖執行聽寫清理或翻譯 ===
            DispatchQueue.main.async { self.delegate?.onLlmStarted() }

            let finalText: String
            switch intent {
            case .dictate:
                do {
                    finalText = try await llmClient.postProcess(text: correctedText)
                } catch {
                    // 一般聽寫可安全降級為詞庫修正後的逐字稿。
                    print("LLM processing failed: \(error)")
                    finalText = correctedText
                }
            case let .translate(targets):
                do {
                    let normalized = try TranslationContract.normalizedTargets(targets)
                    let translations = try await llmClient.translate(
                        text: correctedText,
                        targets: normalized
                    )
                    finalText = try TranslationContract.format(
                        translations,
                        targets: normalized
                    )
                } catch {
                    let message = L10n.format("翻譯失敗：%@", error.localizedDescription)
                    let result = TranscriptionResult(
                        text: "",
                        rawText: rawText,
                        success: false,
                        error: message
                    )
                    DispatchQueue.main.async { self.delegate?.onError(error: message) }
                    return result
                }
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
