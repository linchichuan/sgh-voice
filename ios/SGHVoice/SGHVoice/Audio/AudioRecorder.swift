import Foundation
import AVFoundation

enum AudioRecorderError: Error {
    case permissionDenied(String)
    case setupFailed(String)
    case recordingFailed(String)
}

/// 音訊錄製器
/// 使用 AVAudioRecorder 錄製 16kHz 16bit Mono PCM 音訊 (WAV 格式)
class AudioRecorder: NSObject, AVAudioRecorderDelegate {
    
    private var audioRecorder: AVAudioRecorder?
    private var recordingURL: URL?
    
    private(set) var isRecording = false
    
    override init() {
        super.init()
        setupAudioSession()
    }
    
    private func setupAudioSession() {
        #if os(iOS)
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default, options: .defaultToSpeaker)
            try session.setActive(true)
        } catch {
            print("Failed to set up audio session: \(error)")
        }
        #endif
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
                throw AudioRecorderError.permissionDenied("未取得錄音權限，請先授予麥克風權限")
            }
        case .denied:
            throw AudioRecorderError.permissionDenied("未取得錄音權限，請先授予麥克風權限")
        case .granted:
            break
        @unknown default:
            throw AudioRecorderError.permissionDenied("未知的錄音權限狀態")
        }
        #endif
        
        let fileManager = FileManager.default
        let documentDirectory = fileManager.urls(for: .documentDirectory, in: .userDomainMask)[0]
        recordingURL = documentDirectory.appendingPathComponent("recording.wav")
        
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
            audioRecorder = try AVAudioRecorder(url: recordingURL!, settings: settings)
            audioRecorder?.delegate = self
            audioRecorder?.prepareToRecord()
            
            let success = audioRecorder?.record() ?? false
            if !success {
                throw AudioRecorderError.recordingFailed("AudioRecorder failed to start")
            }
            isRecording = true
        } catch let error as AudioRecorderError {
            throw error
        } catch {
            throw AudioRecorderError.setupFailed(error.localizedDescription)
        }
    }
    
    /// 停止錄音並取得 WAV 格式音訊資料
    /// - Returns: WAV 音訊資料，若失敗則回傳 nil
    func stopRecording() -> Data? {
        guard let recorder = audioRecorder, isRecording else { return nil }
        
        recorder.stop()
        isRecording = false
        audioRecorder = nil
        
        guard let url = recordingURL else { return nil }
        return try? Data(contentsOf: url)
    }
    
    /// 釋放資源
    func release() {
        if isRecording {
            audioRecorder?.stop()
        }
        isRecording = false
        audioRecorder = nil
    }
}
