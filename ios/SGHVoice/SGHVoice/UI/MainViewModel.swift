import Foundation
import SwiftUI
import Combine

@MainActor
class MainViewModel: ObservableObject, TranscriptionProgressDelegate {
    private static let maximumRecordingDurationSeconds = 600
    
    @Published var isRecording = false
    @Published private(set) var audioLevel: Float = 0
    @Published var transcribedText = ""
    @Published var rawText = ""
    @Published private(set) var statusMessage = L10n.text("準備就緒")
    @Published private(set) var statusIsError = false
    @Published var isProcessing = false
    @Published private(set) var isPreparingRecording = false
    @Published private(set) var activeIntent: TranscriptionIntent = .dictate
    @Published var selectedTranslationTargets: [TranslationLanguage] {
        didSet {
            if let normalized = try? TranslationContract.normalizedTargets(selectedTranslationTargets) {
                ApiConfig.shared.translationTargets = normalized
            }
        }
    }
    
    // Scene presettings expose
    @Published var selectedScene: String {
        didSet {
            DictionaryManager.shared.activeScene = selectedScene
        }
    }
    
    @Published var outputStyle: String {
        didSet {
            ApiConfig.shared.outputStyle = outputStyle
        }
    }
    
    private let audioRecorder = AudioRecorder()
    private let pipeline = TranscriptionPipeline.shared
    private var recordingPreparationTask: Task<Void, Never>?
    private var recordingLimitTask: Task<Void, Never>?
    
    init() {
        self.selectedScene = DictionaryManager.shared.activeScene
        self.outputStyle = ApiConfig.shared.outputStyle
        self.selectedTranslationTargets = ApiConfig.shared.translationTargets
        audioRecorder.onLevel = { [weak self] level in
            Task { @MainActor [weak self] in
                guard let self, self.isRecording else { return }
                self.audioLevel = level
            }
        }
        pipeline.delegate = self
    }
    
    // MARK: - Actions
    
    func toggleDictationRecording() {
        if isRecording {
            stopRecording()
        } else {
            startRecording(intent: .dictate)
        }
    }

    func startTranslationRecording(targets: [TranslationLanguage]) {
        guard !isRecording, !isProcessing, !isPreparingRecording else { return }
        do {
            let normalized = try TranslationContract.normalizedTargets(targets)
            selectedTranslationTargets = normalized
            startRecording(intent: .translate(normalized))
        } catch {
            setStatusMessage(error.localizedDescription, isError: true)
        }
    }

    func stopRecording() {
        guard isRecording else { return }
        stopActiveRecording()
    }

    func stopRecordingForPrivacy() {
        guard isRecording || isPreparingRecording else { return }
        recordingPreparationTask?.cancel()
        recordingPreparationTask = nil
        recordingLimitTask?.cancel()
        recordingLimitTask = nil
        audioRecorder.release()
        audioLevel = 0
        isRecording = false
        isPreparingRecording = false
        setLocalizedStatus("App 進入背景，已停止並刪除暫存錄音")
    }

    private func startRecording(intent: TranscriptionIntent) {
        guard !isRecording, !isProcessing, !isPreparingRecording else { return }
        isPreparingRecording = true
        setLocalizedStatus("正在準備麥克風...")
        recordingPreparationTask?.cancel()
        recordingPreparationTask = Task {
            defer { self.isPreparingRecording = false }
            do {
                self.activeIntent = intent
                try Task.checkCancellation()
                try await audioRecorder.startRecording()
                try Task.checkCancellation()
                self.isRecording = true
                self.audioLevel = 0
                self.setLocalizedStatus(intent.isTranslation ? "翻譯錄音中..." : "聽寫錄音中...")
                self.transcribedText = ""
                self.rawText = ""
                self.scheduleRecordingLimit()
                
                // Add soft haptic feedback
                #if canImport(UIKit)
                let generator = UIImpactFeedbackGenerator(style: .medium)
                generator.impactOccurred()
                #endif
            } catch is CancellationError {
                self.audioRecorder.release()
            } catch {
                self.setStatusMessage(
                    L10n.format("錄音失敗: %@", error.localizedDescription),
                    isError: true
                )
                self.isRecording = false
                self.audioLevel = 0
            }
            self.recordingPreparationTask = nil
        }
    }
    
    private func scheduleRecordingLimit() {
        recordingLimitTask?.cancel()
        recordingLimitTask = Task { [weak self] in
            do {
                try await Task.sleep(
                    for: .seconds(Self.maximumRecordingDurationSeconds)
                )
            } catch {
                return
            }
            guard !Task.isCancelled else { return }
            self?.stopActiveRecording(limitReached: true)
        }
    }

    private func stopActiveRecording(limitReached: Bool = false) {
        recordingLimitTask?.cancel()
        recordingLimitTask = nil
        audioLevel = 0
        Task {
            if limitReached {
                self.setLocalizedStatus("錄音已達 10 分鐘上限，正在處理...")
            }
            guard let wavData = await audioRecorder.stopRecording() else {
                self.setLocalizedStatus("無法取得錄音檔", isError: true)
                self.isRecording = false
                return
            }
            self.isRecording = false
            self.isProcessing = true
            
            // Add soft haptic feedback
            #if canImport(UIKit)
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()
            #endif
            
            // 快照本次錄音意圖，處理途中即使使用者改設定也不改變目標。
            let intentSnapshot = activeIntent
            // Consent may be withdrawn while recording. Re-check immediately
            // before the first provider call and discard the in-memory WAV.
            guard ApiConfig.shared.hasCloudProcessingConsent else {
                self.isProcessing = false
                self.setLocalizedStatus(
                    "雲端處理同意已撤回，本次錄音已刪除",
                    isError: true
                )
                return
            }
            let _ = await pipeline.process(wavData: wavData, intent: intentSnapshot)
        }
    }
    
    // MARK: - TranscriptionProgressDelegate
    
    nonisolated func onWhisperStarted() {
        Task { @MainActor in
            self.setLocalizedStatus("正在將語音轉文字 (Whisper)...")
        }
    }
    
    nonisolated func onWhisperCompleted(text: String) {
        Task { @MainActor in
            self.rawText = text
            if !self.activeIntent.isTranslation {
                self.transcribedText = text
            }
        }
    }
    
    nonisolated func onLlmStarted() {
        Task { @MainActor in
            self.setLocalizedStatus(
                self.activeIntent.isTranslation
                    ? "正在翻譯所選語言 (AI)..."
                    : "正在整理逐字稿 (AI)..."
            )
        }
    }
    
    nonisolated func onCompleted(result: TranscriptionResult) {
        Task { @MainActor in
            self.isProcessing = false
            if result.success {
                self.transcribedText = result.text
                self.rawText = result.rawText
                self.setLocalizedStatus("處理完成")
                
                // Success Haptic
                #if canImport(UIKit)
                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.success)
                #endif
            } else {
                self.setStatusMessage(
                    L10n.format(
                        "處理失敗: %@",
                        result.error ?? L10n.text("未知錯誤")
                    ),
                    isError: true
                )
                if self.activeIntent.isTranslation {
                    self.transcribedText = ""
                }
                
                // Error Haptic
                #if canImport(UIKit)
                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.error)
                #endif
            }
        }
    }
    
    nonisolated func onError(error: String) {
        Task { @MainActor in
            self.isProcessing = false
            if self.activeIntent.isTranslation {
                self.transcribedText = ""
            }
            self.setStatusMessage(
                L10n.format("發生錯誤: %@", error),
                isError: true
            )
        }
    }

    func setCopiedStatus() {
        setLocalizedStatus("已複製結果")
    }

    private func setLocalizedStatus(_ key: String, isError: Bool = false) {
        setStatusMessage(L10n.text(key), isError: isError)
    }

    private func setStatusMessage(_ message: String, isError: Bool = false) {
        statusMessage = message
        statusIsError = isError
    }
}
