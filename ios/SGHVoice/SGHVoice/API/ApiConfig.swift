import Foundation
import Security

/// API 金鑰與設定管理 (Keychain & UserDefaults)
class ApiConfig {
    static let shared = ApiConfig()
    
    // UserDefaults
    private let defaults = UserDefaults.standard
    
    // Keys
    private let keyOpenAIApiKey = "openai_api_key"
    private let keyAnthropicApiKey = "anthropic_api_key"
    private let keyGroqApiKey = "groq_api_key"
    private let keyWhisperModel = "whisper_model"
    private let keyClaudeModel = "claude_model"
    private let keyLanguagePref = "language_preference"
    private let keyOutputStyle = "output_style"
    private let keySetupComplete = "setup_complete"
    private let keySttEngine = "stt_engine"
    private let keyLlmEngine = "llm_engine"
    private let keyTranslationTargets = "translation_targets"
    private let keyCloudProcessingConsentVersion = "cloud_processing_consent_version"
    
    // 預設模型
    static let defaultWhisperModel = "whisper-1"
    static let defaultClaudeModel = "claude-haiku-4-5-20251001"
    static let defaultGroqLlmModel = "openai/gpt-oss-120b"
    // v2 adds explicit disclosure for dictionary and scene prompts sent with STT requests.
    static let currentCloudProcessingConsentVersion = 2
    static let supportedClaudeModels = [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-5",
        "claude-opus-5",
        "claude-opus-4-8",
        "claude-fable-5"
    ]
    
    // MARK: - Keychain Methods
    private func saveToKeychain(key: String, value: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key
        ]

        guard !value.isEmpty else {
            SecItemDelete(query as CFDictionary)
            return
        }
        guard let data = value.data(using: .utf8) else { return }

        let attributes: [String: Any] = [
            kSecValueData as String: data
        ]
        let updateStatus = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)

        if updateStatus == errSecItemNotFound {
            var addQuery = query
            addQuery[kSecValueData as String] = data
            addQuery[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
            if addStatus != errSecSuccess {
                print("Keychain add failed with status: \(addStatus)")
            }
        } else if updateStatus != errSecSuccess {
            print("Keychain update failed with status: \(updateStatus)")
        }
    }
    
    private func loadFromKeychain(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: kCFBooleanTrue!,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var dataTypeRef: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &dataTypeRef)
        
        if status == errSecSuccess, let data = dataTypeRef as? Data {
            return String(data: data, encoding: .utf8)
        }
        return nil
    }
    
    private func deleteFromKeychain(key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }
    
    // MARK: - API Keys
    var openAiApiKey: String {
        get {
            return (loadFromKeychain(key: keyOpenAIApiKey) ?? "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        set {
            saveToKeychain(
                key: keyOpenAIApiKey,
                value: newValue.trimmingCharacters(in: .whitespacesAndNewlines)
            )
        }
    }
    
    var anthropicApiKey: String {
        get {
            return (loadFromKeychain(key: keyAnthropicApiKey) ?? "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        set {
            saveToKeychain(
                key: keyAnthropicApiKey,
                value: newValue.trimmingCharacters(in: .whitespacesAndNewlines)
            )
        }
    }
    
    var groqApiKey: String {
        get {
            return (loadFromKeychain(key: keyGroqApiKey) ?? "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
        }
        set {
            saveToKeychain(
                key: keyGroqApiKey,
                value: newValue.trimmingCharacters(in: .whitespacesAndNewlines)
            )
        }
    }
    
    // MARK: - Settings (UserDefaults)
    var whisperModel: String {
        get {
            let saved = defaults.string(forKey: keyWhisperModel)?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return saved.isEmpty ? ApiConfig.defaultWhisperModel : saved
        }
        set {
            let trimmed = newValue.trimmingCharacters(in: .whitespacesAndNewlines)
            defaults.set(trimmed.isEmpty ? ApiConfig.defaultWhisperModel : trimmed, forKey: keyWhisperModel)
        }
    }
    
    var claudeModel: String {
        get {
            let saved = defaults.string(forKey: keyClaudeModel)?
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return saved.isEmpty ? ApiConfig.defaultClaudeModel : saved
        }
        set {
            let trimmed = newValue.trimmingCharacters(in: .whitespacesAndNewlines)
            defaults.set(trimmed.isEmpty ? ApiConfig.defaultClaudeModel : trimmed, forKey: keyClaudeModel)
        }
    }
    
    var outputStyle: String {
        get { return defaults.string(forKey: keyOutputStyle) ?? "normal" }
        set { defaults.set(newValue, forKey: keyOutputStyle) }
    }
    
    var languagePreference: String {
        get { return defaults.string(forKey: keyLanguagePref) ?? "auto" }
        set { defaults.set(newValue, forKey: keyLanguagePref) }
    }
    
    var isSetupComplete: Bool {
        get { return defaults.bool(forKey: keySetupComplete) }
        set { defaults.set(newValue, forKey: keySetupComplete) }
    }
    
    var sttEngine: String {
        get { return defaults.string(forKey: keySttEngine) ?? "openai" }
        set { defaults.set(newValue, forKey: keySttEngine) }
    }
    
    var llmEngine: String {
        get { return defaults.string(forKey: keyLlmEngine) ?? "claude" }
        set { defaults.set(newValue, forKey: keyLlmEngine) }
    }

    var translationTargets: [TranslationLanguage] {
        get {
            let saved = defaults.stringArray(forKey: keyTranslationTargets) ?? []
            let targets = saved.compactMap(TranslationLanguage.init(rawValue:))
            return (try? TranslationContract.normalizedTargets(targets)) ?? [.japanese]
        }
        set {
            let targets = (try? TranslationContract.normalizedTargets(newValue)) ?? [.japanese]
            defaults.set(targets.map(\.rawValue), forKey: keyTranslationTargets)
        }
    }

    var hasSpeechToTextKey: Bool {
        switch sttEngine {
        case "openai":
            return !openAiApiKey.isEmpty
        case "groq":
            return !groqApiKey.isEmpty
        default:
            return false
        }
    }

    var hasConfiguredLlmKey: Bool {
        switch llmEngine {
        case "none":
            return false
        case "claude":
            return !anthropicApiKey.isEmpty
        case "openai":
            return !openAiApiKey.isEmpty
        case "groq":
            return !groqApiKey.isEmpty
        default:
            return false
        }
    }

    var canDictate: Bool {
        hasSpeechToTextKey && (llmEngine == "none" || hasConfiguredLlmKey)
    }

    var canTranslate: Bool {
        hasSpeechToTextKey && hasConfiguredLlmKey
    }

    var hasCloudProcessingConsent: Bool {
        get {
            defaults.integer(forKey: keyCloudProcessingConsentVersion)
                >= ApiConfig.currentCloudProcessingConsentVersion
        }
        set {
            if newValue {
                defaults.set(
                    ApiConfig.currentCloudProcessingConsentVersion,
                    forKey: keyCloudProcessingConsentVersion
                )
            } else {
                defaults.removeObject(forKey: keyCloudProcessingConsentVersion)
            }
        }
    }
    
    var hasApiKeys: Bool {
        canDictate
    }
    
    func clearAll() {
        deleteFromKeychain(key: keyOpenAIApiKey)
        deleteFromKeychain(key: keyAnthropicApiKey)
        deleteFromKeychain(key: keyGroqApiKey)
        
        defaults.removeObject(forKey: keyWhisperModel)
        defaults.removeObject(forKey: keyClaudeModel)
        defaults.removeObject(forKey: keyLanguagePref)
        defaults.removeObject(forKey: keyOutputStyle)
        defaults.removeObject(forKey: keySetupComplete)
        defaults.removeObject(forKey: keySttEngine)
        defaults.removeObject(forKey: keyLlmEngine)
        defaults.removeObject(forKey: keyTranslationTargets)
        defaults.removeObject(forKey: keyCloudProcessingConsentVersion)
    }
}
