import SwiftUI

struct MainView: View {
    @StateObject private var viewModel = MainViewModel()
    @State private var showingSettings = false
    @State private var showingTranslationTargets = false
    @State private var openSettingsAfterTranslationSheet = false
    @State private var showingCloudProcessingConsent = false
    @State private var pendingCloudIntent: TranscriptionIntent?
    @Environment(\.scenePhase) private var scenePhase

    private let brandColor = Color(red: 0.12, green: 0.13, blue: 0.24)
    private let successColor = Color(red: 0.05, green: 0.52, blue: 0.43)

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    brandHeader
                    statusCard
                    resultCard

                    if !viewModel.rawText.isEmpty && viewModel.rawText != viewModel.transcribedText {
                        originalTranscript
                    }

                    recordingCard
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .frame(maxWidth: 720)
                .frame(maxWidth: .infinity)
            }
            .background(appBackground.ignoresSafeArea())
            .navigationTitle("")
            .toolbar {
                ToolbarItem(placement: .automatic) {
                    Button {
                        showingSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                            .frame(width: 44, height: 44)
                    }
                    .accessibilityLabel("開啟設定")
                }
            }
            .sheet(isPresented: $showingSettings) {
                NavigationStack {
                    SettingsView()
                        .toolbar {
                            ToolbarItem(placement: .confirmationAction) {
                                Button("完成") {
                                    showingSettings = false
                                    viewModel.selectedScene = DictionaryManager.shared.activeScene
                                    viewModel.outputStyle = ApiConfig.shared.outputStyle
                                }
                            }
                        }
                }
            }
            .sheet(isPresented: $showingTranslationTargets, onDismiss: {
                if openSettingsAfterTranslationSheet {
                    openSettingsAfterTranslationSheet = false
                    showingSettings = true
                }
            }) {
                TranslationTargetSheet(
                    targets: $viewModel.selectedTranslationTargets,
                    brandColor: brandColor
                ) {
                    beginTranslationFromSheet()
                }
            }
            .sheet(isPresented: $showingCloudProcessingConsent) {
                CloudProcessingConsentView(
                    onAgree: approveCloudProcessing,
                    onCancel: cancelCloudProcessing
                )
            }
            .onChange(of: scenePhase) { _, newPhase in
                if newPhase != .active {
                    viewModel.stopRecordingForPrivacy()
                }
            }
        }
    }

    private var brandHeader: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(brandColor)
                    .frame(width: 48, height: 48)
                Image(systemName: "waveform")
                    .font(.system(size: 23, weight: .semibold))
                    .foregroundStyle(.white)
            }
            .accessibilityHidden(true)

            VStack(alignment: .leading, spacing: 2) {
                Text("SGH Voice")
                    .font(.title2.weight(.bold))
                    .foregroundStyle(.primary)
                Text("聽寫與多語翻譯")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
        .frame(minHeight: 56)
    }

    private var statusCard: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(statusColor)
                .frame(width: 9, height: 9)
                .accessibilityHidden(true)

            Text(viewModel.statusMessage)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.primary)
                .frame(maxWidth: .infinity, alignment: .leading)

            if viewModel.isProcessing || viewModel.isPreparingRecording {
                ProgressView()
                    .controlSize(.small)
                    .accessibilityLabel("處理中")
            }
        }
        .padding(.horizontal, 14)
        .frame(minHeight: 48)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(Color.primary.opacity(0.09), lineWidth: 1)
        }
        .accessibilityElement(children: .combine)
    }

    private var resultCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label(
                    L10n.text(viewModel.activeIntent.isTranslation ? "翻譯結果" : "聽寫結果"),
                    systemImage: viewModel.activeIntent.isTranslation ? "character.book.closed" : "text.alignleft"
                )
                .font(.headline)
                .foregroundStyle(brandColor)

                Spacer()

                if !viewModel.transcribedText.isEmpty && !viewModel.isRecording && !viewModel.isProcessing {
                    Button {
                        copyResult()
                    } label: {
                        Image(systemName: "doc.on.doc")
                            .frame(width: 44, height: 44)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(brandColor)
                    .accessibilityLabel("複製結果")
                }
            }

            ScrollView {
                Text(resultText)
                    .font(.body)
                    .foregroundStyle(viewModel.transcribedText.isEmpty ? .secondary : .primary)
                    .frame(maxWidth: .infinity, alignment: .topLeading)
                    .textSelection(.enabled)
            }
            .frame(minHeight: 150)
        }
        .padding(16)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(Color.primary.opacity(0.10), lineWidth: 1)
        }
    }

    private var originalTranscript: some View {
        DisclosureGroup {
            Text(viewModel.rawText)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 8)
                .textSelection(.enabled)
        } label: {
            Text("顯示原始辨識文字")
                .font(.subheadline.weight(.medium))
        }
        .padding(14)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(Color.primary.opacity(0.09), lineWidth: 1)
        }
    }

    private var recordingCard: some View {
        VStack(spacing: 14) {
            HStack(spacing: 8) {
                modePill(
                    title: "聽寫",
                    selected: !viewModel.activeIntent.isTranslation,
                    systemImage: "mic"
                )

                if viewModel.activeIntent.isTranslation || !viewModel.selectedTranslationTargets.isEmpty {
                    modePill(
                        title: translationTargetSummary,
                        selected: viewModel.activeIntent.isTranslation,
                        systemImage: "character.book.closed"
                    )
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            RecordGestureButton(
                isRecording: viewModel.isRecording,
                isTranslation: viewModel.activeIntent.isTranslation,
                isDisabled: viewModel.isProcessing || viewModel.isPreparingRecording,
                brandColor: brandColor,
                onTap: handleRecordTap,
                onLongPress: handleRecordLongPress
            )

            Text(L10n.text(
                viewModel.isRecording
                    ? "點一下停止並送出處理"
                    : "點一下開始聽寫 · 長按選擇 1–4 種翻譯語言 · 最長 10 分鐘"
            ))
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(16)
        .background(.background)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(Color.primary.opacity(0.10), lineWidth: 1)
        }
    }

    private func modePill(title: String, selected: Bool, systemImage: String) -> some View {
        Label(L10n.text(title), systemImage: systemImage)
            .font(.caption.weight(.semibold))
            .foregroundStyle(selected ? Color.white : brandColor)
            .padding(.horizontal, 12)
            .frame(minHeight: 36)
            .background(selected ? brandColor : brandColor.opacity(0.08))
            .clipShape(Capsule())
    }

    private var appBackground: Color {
        #if canImport(UIKit)
        return Color(uiColor: .systemGroupedBackground)
        #else
        return Color.primary.opacity(0.035)
        #endif
    }

    private var statusColor: Color {
        if viewModel.isRecording { return .red }
        if viewModel.isProcessing || viewModel.isPreparingRecording { return .orange }
        if viewModel.statusIsError {
            return .red
        }
        return successColor
    }

    private var resultText: String {
        if !viewModel.transcribedText.isEmpty { return viewModel.transcribedText }
        return L10n.text(
            viewModel.activeIntent.isTranslation
                ? "翻譯完成後會顯示在這裡；失敗時不會用原文冒充翻譯。"
                : "整理後的逐字稿會顯示在這裡。"
        )
    }

    private var translationTargetSummary: String {
        viewModel.selectedTranslationTargets
            .map(\.shortLabel)
            .joined(separator: " · ")
    }

    private func handleRecordTap() {
        if viewModel.isRecording {
            viewModel.stopRecording()
            return
        }
        guard ApiConfig.shared.canDictate else {
            showingSettings = true
            return
        }
        requestRecording(intent: .dictate)
    }

    private func handleRecordLongPress() {
        if viewModel.isRecording {
            viewModel.stopRecording()
            return
        }
        showingTranslationTargets = true
    }

    private func beginTranslationFromSheet() {
        let targets = viewModel.selectedTranslationTargets
        guard ApiConfig.shared.canTranslate else {
            openSettingsAfterTranslationSheet = true
            showingTranslationTargets = false
            return
        }
        showingTranslationTargets = false
        requestRecording(intent: .translate(targets))
    }

    private func requestRecording(intent: TranscriptionIntent) {
        guard ApiConfig.shared.hasCloudProcessingConsent else {
            pendingCloudIntent = intent
            showingCloudProcessingConsent = true
            return
        }
        startApprovedRecording(intent)
    }

    private func approveCloudProcessing() {
        ApiConfig.shared.hasCloudProcessingConsent = true
        let intent = pendingCloudIntent
        pendingCloudIntent = nil
        showingCloudProcessingConsent = false
        if let intent {
            startApprovedRecording(intent)
        }
    }

    private func cancelCloudProcessing() {
        pendingCloudIntent = nil
        showingCloudProcessingConsent = false
    }

    private func startApprovedRecording(_ intent: TranscriptionIntent) {
        switch intent {
        case .dictate:
            guard ApiConfig.shared.canDictate else {
                showingSettings = true
                return
            }
            viewModel.toggleDictationRecording()
        case let .translate(targets):
            guard ApiConfig.shared.canTranslate else {
                showingSettings = true
                return
            }
            viewModel.startTranslationRecording(targets: targets)
        }
    }

    private func copyResult() {
        #if canImport(UIKit)
        UIPasteboard.general.string = viewModel.transcribedText
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)
        #elseif os(macOS)
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(viewModel.transcribedText, forType: .string)
        #endif
        viewModel.setCopiedStatus()
    }
}

private struct CloudProcessingConsentView: View {
    let onAgree: () -> Void
    let onCancel: () -> Void

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Label("外部 AI 處理同意", systemImage: "lock.shield")
                        .font(.title2.weight(.bold))

                    Text("SGH Voice 必須將資料傳送至你在設定中選擇的外部服務，才能完成語音辨識、逐字稿整理與翻譯。")

                    consentRow(
                        icon: "waveform",
                        title: "錄音音訊",
                        detail: "傳送至 OpenAI 或 Groq 的語音辨識 API。暫存檔會在讀取後或取消錄音時刪除。"
                    )
                    consentRow(
                        icon: "text.alignleft",
                        title: "逐字稿文字",
                        detail: "傳送至你選擇的 Anthropic、OpenAI 或 Groq 模型，用於整理或翻譯。"
                    )
                    consentRow(
                        icon: "text.book.closed",
                        title: "詞庫與場景提示",
                        detail: "預載詞彙、自訂詞彙與所選場景提示會隨語音辨識請求傳送至 OpenAI 或 Groq，以提升辨識正確率。"
                    )
                    consentRow(
                        icon: "key",
                        title: "使用者自備 API Key",
                        detail: "請求會依各服務商條款處理，可能與你的服務商帳號關聯；內容不會傳送至新義豊的伺服器。"
                    )

                    Text("醫療模式不得輸入可識別特定患者的姓名、聯絡方式、病歷號或其他個人資訊。")
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(.orange)

                    Link(
                        "查看完整隱私權政策",
                        destination: URL(string: "https://voice.shingihou.com/privacy.html")!
                    )

                    Button(action: onAgree) {
                        Text("同意並繼續")
                            .font(.headline)
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .frame(minHeight: 54)
                            .background(Color.accentColor)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
                .padding(20)
            }
            .navigationTitle("資料處理說明")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消", action: onCancel)
                }
            }
        }
    }

    private func consentRow(icon: String, title: String, detail: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .frame(width: 24)
                .foregroundStyle(.tint)
            VStack(alignment: .leading, spacing: 4) {
                Text(L10n.text(title)).font(.headline)
                Text(L10n.text(detail))
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct RecordGestureButton: View {
    let isRecording: Bool
    let isTranslation: Bool
    let isDisabled: Bool
    let brandColor: Color
    let onTap: () -> Void
    let onLongPress: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: isRecording ? "stop.fill" : "mic.fill")
                .font(.system(size: 22, weight: .semibold))
            Text(buttonTitle)
                .font(.headline)
        }
        .foregroundStyle(.white)
        .frame(maxWidth: .infinity)
        .frame(minHeight: 64)
        .background(isRecording ? Color.red : brandColor)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .contentShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .opacity(isDisabled ? 0.5 : 1)
        .allowsHitTesting(!isDisabled)
        .gesture(
            LongPressGesture(minimumDuration: 0.45, maximumDistance: 28)
                .exclusively(before: TapGesture())
                .onEnded { value in
                    switch value {
                    case .first(true):
                        onLongPress()
                    case .second:
                        onTap()
                    default:
                        break
                    }
                }
        )
        .accessibilityElement()
        .accessibilityAddTraits(.isButton)
        .accessibilityLabel(buttonTitle)
        .accessibilityHint(
            L10n.text(
                isRecording
                    ? "啟用可停止錄音"
                    : "啟用可開始聽寫；另有選擇翻譯語言動作"
            )
        )
        .accessibilityAction {
            onTap()
        }
        .accessibilityAction(named: Text("選擇翻譯語言")) {
            onLongPress()
        }
    }

    private var buttonTitle: String {
        if isRecording {
            return L10n.text(isTranslation ? "停止翻譯錄音" : "停止聽寫錄音")
        }
        return L10n.text("開始語音輸入")
    }
}

private struct TranslationTargetSheet: View {
    @Binding var targets: [TranslationLanguage]
    let brandColor: Color
    let onStart: () -> Void

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("翻譯成哪些語言？")
                        .font(.title2.weight(.bold))
                    Text("可同時選擇 1–4 種；一次語音辨識後，由同一次 AI 呼叫完成。")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                VStack(spacing: 8) {
                    ForEach(TranslationLanguage.allCases) { language in
                        targetRow(language)
                    }
                }

                Spacer(minLength: 8)

                Button(action: onStart) {
                    Label(
                        L10n.format("開始翻譯錄音（%ld 種）", targets.count),
                        systemImage: "mic.fill"
                    )
                    .font(.headline)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(minHeight: 56)
                    .background(brandColor)
                    .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                }
                .buttonStyle(.plain)
                .accessibilityHint("關閉語言選擇並開始錄音")
            }
            .padding(20)
            .navigationTitle("多語翻譯")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
            }
        }
    }

    private func targetRow(_ language: TranslationLanguage) -> some View {
        let selected = targets.contains(language)
        return Button {
            toggle(language)
        } label: {
            HStack(spacing: 12) {
                Text(language.shortLabel)
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(selected ? .white : brandColor)
                    .frame(width: 44, height: 44)
                    .background(selected ? brandColor : brandColor.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))

                Text(language.nativeName)
                    .font(.body.weight(.medium))
                    .foregroundStyle(.primary)
                Spacer()
                Image(systemName: selected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(selected ? brandColor : .secondary)
            }
            .padding(.horizontal, 12)
            .frame(minHeight: 60)
            .background(Color.primary.opacity(0.035))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(selected ? brandColor.opacity(0.5) : Color.primary.opacity(0.08), lineWidth: 1)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel(
            L10n.format(
                selected ? "%@，已選取" : "%@，未選取",
                language.nativeName
            )
        )
        .accessibilityHint(
            L10n.text(selected && targets.count == 1 ? "至少保留一種語言" : "啟用可切換")
        )
    }

    private func toggle(_ language: TranslationLanguage) {
        if let index = targets.firstIndex(of: language) {
            guard targets.count > 1 else { return }
            targets.remove(at: index)
        } else {
            guard targets.count < 4 else { return }
            targets.append(language)
        }
    }
}

#if DEBUG
#Preview {
    MainView()
}
#endif
