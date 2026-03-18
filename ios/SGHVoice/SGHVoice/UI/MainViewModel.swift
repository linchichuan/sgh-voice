import Foundation
import SwiftUI
import Combine

@MainActor
class MainViewModel: ObservableObject, TranscriptionProgressDelegate {
    
    @Published var isRecording = false
    @Published var transcribedText = ""
    @Published var rawText = ""
    @Published var statusMessage = "準備就緒"
    @Published var isProcessing = false
    
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
    
    init() {
        self.selectedScene = DictionaryManager.shared.activeScene
        self.outputStyle = ApiConfig.shared.outputStyle
        pipeline.delegate = self
    }
    
    // MARK: - Actions
    
    func toggleRecording() {
        if isRecording {
            stopRecording()
        } else {
            startRecording()
        }
    }
    
    private func startRecording() {
        Task {
            do {
                try await audioRecorder.startRecording()
                self.isRecording = true
                self.statusMessage = "錄音中..."
                self.transcribedText = ""
                self.rawText = ""
                
                // Add soft haptic feedback
                #if canImport(UIKit)
                let generator = UIImpactFeedbackGenerator(style: .medium)
                generator.impactOccurred()
                #endif
            } catch {
                self.statusMessage = "錄音失敗: \(error.localizedDescription)"
                self.isRecording = false
            }
        }
    }
    
    private func stopRecording() {
        Task {
            guard let wavData = audioRecorder.stopRecording() else {
                self.statusMessage = "無法取得錄音檔"
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
            
            // Starts processing pipeline
            let _ = await pipeline.process(wavData: wavData)
        }
    }
    
    // MARK: - TranscriptionProgressDelegate
    
    nonisolated func onWhisperStarted() {
        Task { @MainActor in
            self.statusMessage = "正在將語音轉文字 (Whisper)..."
        }
    }
    
    nonisolated func onWhisperCompleted(text: String) {
        Task { @MainActor in
            self.rawText = text
            self.transcribedText = text
        }
    }
    
    nonisolated func onLlmStarted() {
        Task { @MainActor in
            self.statusMessage = "正在潤飾文句與繁體處理 (AI)..."
        }
    }
    
    nonisolated func onCompleted(result: TranscriptionResult) {
        Task { @MainActor in
            self.isProcessing = false
            if result.success {
                self.transcribedText = result.text
                self.rawText = result.rawText
                self.statusMessage = "處理完成"
                
                // Success Haptic
                #if canImport(UIKit)
                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.success)
                #endif
            } else {
                self.statusMessage = "處理失敗: \(result.error ?? "Unknown error")"
                
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
            self.statusMessage = "發生錯誤: \(error)"
        }
    }
}
