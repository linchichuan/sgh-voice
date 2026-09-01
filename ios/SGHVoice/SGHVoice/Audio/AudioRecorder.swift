import Foundation
import AVFoundation

enum AudioRecorderError: Error {
    case permissionDenied(String)
    case setupFailed(String)
    case recordingFailed(String)
}

extension AudioRecorderError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case let .permissionDenied(message),
             let .setupFailed(message),
             let .recordingFailed(message):
            return message
        }
    }
}

/// 音訊錄製器
/// 使用 AVAudioRecorder 錄製 16kHz 16bit Mono PCM 音訊 (WAV 格式)
class AudioRecorder: NSObject, AVAudioRecorderDelegate {

    private static let temporaryFilePrefix = "sgh-voice-"
    private var audioRecorder: AVAudioRecorder?
    private var recordingURL: URL?
    private var meterTimer: Timer?

    var onLevel: ((Float) -> Void)?
    
    private(set) var isRecording = false

    private func startMetering() {
        stopMetering()
        audioRecorder?.isMeteringEnabled = true
        let timer = Timer(timeInterval: 0.08, repeats: true) { [weak self] _ in
            guard let self, let recorder = self.audioRecorder, self.isRecording else {
                return
            }
            recorder.updateMeters()
            self.onLevel?(
                AudioLevelMeter.normalizedPower(
                    decibels: recorder.averagePower(forChannel: 0)
                )
            )
        }
        meterTimer = timer
        RunLoop.main.add(timer, forMode: .common)
    }

    private func stopMetering() {
        meterTimer?.invalidate()
        meterTimer = nil
        onLevel?(0)
    }

    override init() {
        super.init()
        removeOrphanedTemporaryRecordings()
    }
    
    private func activateAudioSession() throws {
        #if os(iOS)
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .default, options: .defaultToSpeaker)
        try session.setActive(true)
        #endif
    }

    private func deactivateAudioSession() {
        #if os(iOS)
        do {
            try AVAudioSession.sharedInstance().setActive(
                false,
                options: .notifyOthersOnDeactivation
            )
        } catch {
            print("Failed to deactivate audio session: \(error)")
        }
        #endif
    }

    private func removeTemporaryRecording() {
        guard let url = recordingURL else { return }
        try? FileManager.default.removeItem(at: url)
        recordingURL = nil
    }

    private func removeOrphanedTemporaryRecordings() {
        let directory = FileManager.default.temporaryDirectory
        guard let urls = try? FileManager.default.contentsOfDirectory(
            at: directory,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        ) else { return }

        for url in urls where
            url.lastPathComponent.hasPrefix(Self.temporaryFilePrefix)
                && url.pathExtension.lowercased() == "wav" {
            try? FileManager.default.removeItem(at: url)
        }
    }
    
    /// 開始錄音
    /// - Throws: AudioRecorderError 當權限不足或設定失敗時拋出
    func startRecording() async throws {
        #if os(iOS)
        let status = AVAudioApplication.shared.recordPermission
        switch status {
        case .undetermined:
            let granted = await AVAudioApplication.requestRecordPermission()
            if !granted {
                throw AudioRecorderError.permissionDenied(
                    L10n.text("未取得錄音權限，請先授予麥克風權限")
                )
            }
        case .denied:
            throw AudioRecorderError.permissionDenied(
                L10n.text("未取得錄音權限，請先授予麥克風權限")
            )
        case .granted:
            break
        @unknown default:
            throw AudioRecorderError.permissionDenied(L10n.text("未知的錄音權限狀態"))
        }
        #endif

        removeTemporaryRecording()
        recordingURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("\(Self.temporaryFilePrefix)\(UUID().uuidString).wav")
        
        // 錄音參數：16kHz、16bit、單聲道線性 PCM (.wav)
        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: 16000.0,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsFloatKey: false
        ]
        
        do {
            try activateAudioSession()
            guard let recordingURL else {
                throw AudioRecorderError.setupFailed(L10n.text("無法建立暫存錄音檔"))
            }
            audioRecorder = try AVAudioRecorder(url: recordingURL, settings: settings)
            audioRecorder?.delegate = self
            audioRecorder?.prepareToRecord()
            
            let success = audioRecorder?.record() ?? false
            if !success {
                throw AudioRecorderError.recordingFailed(L10n.text("無法開始錄音"))
            }
            isRecording = true
            startMetering()
        } catch let error as AudioRecorderError {
            audioRecorder = nil
            removeTemporaryRecording()
            deactivateAudioSession()
            throw error
        } catch {
            audioRecorder = nil
            removeTemporaryRecording()
            deactivateAudioSession()
            throw AudioRecorderError.setupFailed(error.localizedDescription)
        }
    }
    
    /// 停止錄音並取得 WAV 格式音訊資料
    /// - Returns: WAV 音訊資料，若失敗則回傳 nil
    func stopRecording() async -> Data? {
        guard let recorder = audioRecorder, isRecording else { return nil }
        
        recorder.stop()
        isRecording = false
        stopMetering()
        audioRecorder = nil
        deactivateAudioSession()

        guard let url = recordingURL else { return nil }
        recordingURL = nil
        return await Task.detached(priority: .userInitiated) {
            defer { try? FileManager.default.removeItem(at: url) }
            return try? Data(contentsOf: url, options: .mappedIfSafe)
        }.value
    }
    
    /// 釋放資源
    func release() {
        stopMetering()
        if isRecording {
            audioRecorder?.stop()
        }
        isRecording = false
        audioRecorder = nil
        removeTemporaryRecording()
        deactivateAudioSession()
    }
}
