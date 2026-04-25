import SwiftUI

struct SettingsView: View {
    @State private var openAiKey = ""
    @State private var anthropicKey = ""
    @State private var groqKey = ""
    @State private var whisperModel = ""
    @State private var claudeModel = ""
    @State private var outputStyle = ""
    @State private var activeScene = ""
    @State private var sttEngine = ""
    @State private var llmEngine = ""
    
    // Scene Presets mapping from DictionaryManager
    let scenePresets = DictionaryManager.shared.scenePresets.map { key, value in
        (key, value.label)
    }.sorted { $0.1 < $1.1 }
    
    var body: some View {
        Form {
            Section(header: Text("API 服務引擎").font(.headline)) {
                Picker("語音辨識 (STT)", selection: $sttEngine) {
                    Text("OpenAI (精確)").tag("openai")
                    Text("Groq (極速)").tag("groq")
                }
                Picker("後處理 (LLM)", selection: $llmEngine) {
                    Text("Claude (Anthropic)").tag("claude")
                    Text("OpenAI (GPT-4o)").tag("openai")
                    Text("Groq (Llama 3)").tag("groq")
                    Text("不使用 (None)").tag("none")
                }
            }
            
            Section(header: Text("API 金鑰 (Keychain 加密儲存)").font(.headline)) {
                SecureField("OpenAI API Key (sk-...)", text: $openAiKey)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Anthropic API Key (sk-ant-...)", text: $anthropicKey)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                SecureField("Groq API Key (gsk-...)", text: $groqKey)
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
        groqKey = ApiConfig.shared.groqApiKey
        whisperModel = ApiConfig.shared.whisperModel
        claudeModel = ApiConfig.shared.claudeModel
        outputStyle = ApiConfig.shared.outputStyle
        activeScene = DictionaryManager.shared.activeScene
        sttEngine = ApiConfig.shared.sttEngine
        llmEngine = ApiConfig.shared.llmEngine
    }
    
    private func saveSettings() {
        ApiConfig.shared.openAiApiKey = openAiKey
        ApiConfig.shared.anthropicApiKey = anthropicKey
        ApiConfig.shared.groqApiKey = groqKey
        ApiConfig.shared.whisperModel = whisperModel
        ApiConfig.shared.claudeModel = claudeModel
        ApiConfig.shared.outputStyle = outputStyle
        DictionaryManager.shared.activeScene = activeScene
        ApiConfig.shared.sttEngine = sttEngine
        ApiConfig.shared.llmEngine = llmEngine
    }
}

#if DEBUG
#Preview {
    NavigationView {
        SettingsView()
    }
}
#endif
