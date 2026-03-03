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
    private let keyWhisperModel = "whisper_model"
    private let keyClaudeModel = "claude_model"
    private let keyLanguagePref = "language_preference"
    private let keyOutputStyle = "output_style"
    private let keySetupComplete = "setup_complete"
    
    // 預設模型
    static let defaultWhisperModel = "whisper-1"
    static let defaultClaudeModel = "claude-haiku-4-5-20251001"
    
    // MARK: - Keychain Methods
    private func saveToKeychain(key: String, value: String) {
        if let data = value.data(using: .utf8) {
            let query: [String: Any] = [
                kSecClass as String: kSecClassGenericPassword,
                kSecAttrAccount as String: key,
                kSecValueData as String: data
            ]
            
            // Delete existing item
            SecItemDelete(query as CFDictionary)
            
            // Add new item
            SecItemAdd(query as CFDictionary, nil)
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
        get { return loadFromKeychain(key: keyOpenAIApiKey) ?? "" }
        set { saveToKeychain(key: keyOpenAIApiKey, value: newValue) }
    }
    
    var anthropicApiKey: String {
        get { return loadFromKeychain(key: keyAnthropicApiKey) ?? "" }
        set { saveToKeychain(key: keyAnthropicApiKey, value: newValue) }
    }
    
    // MARK: - Settings (UserDefaults)
    var whisperModel: String {
        get { return defaults.string(forKey: keyWhisperModel) ?? ApiConfig.defaultWhisperModel }
        set { defaults.set(newValue, forKey: keyWhisperModel) }
    }
    
    var claudeModel: String {
        get { return defaults.string(forKey: keyClaudeModel) ?? ApiConfig.defaultClaudeModel }
        set { defaults.set(newValue, forKey: keyClaudeModel) }
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
    
    var hasApiKeys: Bool {
        return !openAiApiKey.isEmpty && !anthropicApiKey.isEmpty
    }
    
    func clearAll() {
        deleteFromKeychain(key: keyOpenAIApiKey)
        deleteFromKeychain(key: keyAnthropicApiKey)
        
        defaults.removeObject(forKey: keyWhisperModel)
        defaults.removeObject(forKey: keyClaudeModel)
        defaults.removeObject(forKey: keyLanguagePref)
        defaults.removeObject(forKey: keyOutputStyle)
        defaults.removeObject(forKey: keySetupComplete)
    }
}
