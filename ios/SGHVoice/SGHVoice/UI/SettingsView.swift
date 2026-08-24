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
    @State private var hasCloudProcessingConsent = false
    @State private var showingClearDataConfirmation = false
    
    // Scene Presets mapping from DictionaryManager
    let scenePresets = DictionaryManager.shared.scenePresets.map { key, value in
        (key, value.label)
    }.sorted { $0.1 < $1.1 }
    
    var body: some View {
        Form {
            Section(header: Text("API 服務引擎").font(.headline)) {
                Picker("語音辨識 (STT)", selection: $sttEngine) {
                    Text("OpenAI").tag("openai")
                    Text("Groq").tag("groq")
                }
                Picker("後處理 (LLM)", selection: $llmEngine) {
                    Text("Claude (Anthropic)").tag("claude")
                    Text("OpenAI (GPT-4o)").tag("openai")
                    Text("Groq (GPT-OSS 120B)").tag("groq")
                    Text("不使用 (None)").tag("none")
                }
            }
            
            Section(header: Text("API 金鑰 (Keychain 加密儲存)").font(.headline)) {
                SecureField("OpenAI API Key (sk-...)", text: $openAiKey)
                    .apiCredentialInput()
                SecureField("Anthropic API Key (sk-ant-...)", text: $anthropicKey)
                    .apiCredentialInput()
                SecureField("Groq API Key (gsk-...)", text: $groqKey)
                    .apiCredentialInput()
            }
            
            Section(header: Text("模型選用設定").font(.headline)) {
                TextField("Whisper 模型名稱", text: $whisperModel)
                    .apiCredentialInput()

                Picker("Claude 模型", selection: $claudeModel) {
                    Text("Haiku 4.5（建議）")
                        .tag("claude-haiku-4-5-20251001")
                    Text("Sonnet 5")
                        .tag("claude-sonnet-5")
                    Text("Opus 5")
                        .tag("claude-opus-5")
                    Text("Opus 4.8")
                        .tag("claude-opus-4-8")
                    Text("Fable 5（30 天資料保留）")
                        .tag("claude-fable-5")
                    if !ApiConfig.supportedClaudeModels.contains(claudeModel) {
                        Text(L10n.format("自訂：%@", claudeModel)).tag(claudeModel)
                    }
                }

                TextField("自訂 Claude 模型 ID", text: $claudeModel)
                    .apiCredentialInput()

                Text("SGH Voice 會關閉 Sonnet 5／Opus 5 的額外 thinking；Fable 5 依官方限制使用 low effort。模型可用性、價格與資料處理條件以 Anthropic 最新公告為準。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                
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
                        Text(L10n.text(preset.1)).tag(preset.0)
                    }
                }
            }

            Section(header: Text("隱私與資料").font(.headline)) {
                Text("開始錄音前，App 會說明語音、逐字稿及語音辨識詞庫提示將傳送至你選擇的 OpenAI、Anthropic 或 Groq 服務。SGH Voice 不會將內容上傳至新義豊的伺服器。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)

                Text("醫療模式不得輸入可識別特定患者的姓名、聯絡方式、病歷號或其他個人資訊。")
                    .font(.footnote)
                    .foregroundStyle(.orange)

                Link(
                    "查看隱私權政策",
                    destination: URL(string: "https://voice.shingihou.com/privacy.html")!
                )

                if hasCloudProcessingConsent {
                    Button("撤回雲端處理同意") {
                        ApiConfig.shared.hasCloudProcessingConsent = false
                        hasCloudProcessingConsent = false
                    }
                }

                Button("清除 API 金鑰、詞庫與偏好設定", role: .destructive) {
                    showingClearDataConfirmation = true
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
        .confirmationDialog(
            "清除這台裝置上的 SGH Voice 設定？",
            isPresented: $showingClearDataConfirmation,
            titleVisibility: .visible
        ) {
            Button("清除 API 金鑰、詞庫與偏好設定", role: .destructive) {
                ApiConfig.shared.clearAll()
                DictionaryManager.shared.clearUserData()
                loadSettings()
            }
            Button("取消", role: .cancel) {}
        } message: {
            Text("此操作會刪除 Keychain 內的 API 金鑰、模型、使用偏好與自訂詞庫，且無法復原。")
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
        hasCloudProcessingConsent = ApiConfig.shared.hasCloudProcessingConsent
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

private extension View {
    @ViewBuilder
    func apiCredentialInput() -> some View {
        #if os(iOS)
        self
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
        #else
        self
        #endif
    }
}
