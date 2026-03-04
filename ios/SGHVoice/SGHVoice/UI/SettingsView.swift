import SwiftUI

struct SettingsView: View {
    @State private var openAiKey = ""
    @State private var anthropicKey = ""
    @State private var whisperModel = ""
    @State private var claudeModel = ""
    @State private var outputStyle = ""
    @State private var activeScene = ""
    
    // Scene Presets mapping from DictionaryManager
    let scenePresets = DictionaryManager.shared.scenePresets.map { key, value in
        (key, value.label)
    }.sorted { $0.1 < $1.1 }
    
    var body: some View {
        Form {
            Section(header: Text("API 金鑰 (Keychain 加密儲存)").font(.headline)) {
                SecureField("OpenAI API Key (sk-...)", text: $openAiKey)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Anthropic API Key (sk-ant-...)", text: $anthropicKey)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            }
            
            Section(header: Text("模型選用設定").font(.headline)) {
                TextField("Whisper 模型名稱", text: $whisperModel)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                TextField("Claude 模型名稱", text: $claudeModel)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                
                Button("恢復預設模型") {
                    whisperModel = ApiConfig.defaultWhisperModel
                    claudeModel = ApiConfig.defaultClaudeModel
                }
                .foregroundColor(.red)
            }
            
            Section(header: Text("風格與場景").font(.headline)) {
                Picker("預設輸出風格", selection: $outputStyle) {
                    Text("一般文字 (Normal)").tag("normal")
                    Text("LINE 聊天 (Line)").tag("line")
                    Text("正式信件 (Email)").tag("email")
                }
                
                Picker("語音使用場景", selection: $activeScene) {
                    ForEach(scenePresets, id: \.0) { preset in
                        Text(preset.1).tag(preset.0)
                    }
                }
            }
        }
        .navigationTitle("設定")
        .onAppear {
            loadSettings()
        }
        .onDisappear {
            saveSettings()
        }
    }
    
    private func loadSettings() {
        openAiKey = ApiConfig.shared.openAiApiKey
        anthropicKey = ApiConfig.shared.anthropicApiKey
        whisperModel = ApiConfig.shared.whisperModel
        claudeModel = ApiConfig.shared.claudeModel
        outputStyle = ApiConfig.shared.outputStyle
        activeScene = DictionaryManager.shared.activeScene
    }
    
    private func saveSettings() {
        ApiConfig.shared.openAiApiKey = openAiKey
        ApiConfig.shared.anthropicApiKey = anthropicKey
        ApiConfig.shared.whisperModel = whisperModel
        ApiConfig.shared.claudeModel = claudeModel
        ApiConfig.shared.outputStyle = outputStyle
        DictionaryManager.shared.activeScene = activeScene
    }
}

#Preview {
    NavigationView {
        SettingsView()
    }
}
