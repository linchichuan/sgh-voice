import SwiftUI

struct MainView: View {
    @StateObject private var viewModel = MainViewModel()
    @State private var showingSettings = false
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                // Header Status Section
                HStack {
                    Image(systemName: viewModel.isRecording ? "mic.fill" : "mic.slash")
                        .foregroundColor(viewModel.isRecording ? .red : .gray)
                        .scaleEffect(viewModel.isRecording ? 1.2 : 1.0)
                        .animation(.easeInOut(duration: 0.5).repeatForever(autoreverses: true), value: viewModel.isRecording)
                    
                    Text(viewModel.statusMessage)
                        .font(.subheadline)
                        .foregroundColor(viewModel.isRecording ? .red : .secondary)
                        .multilineTextAlignment(.leading)
                    
                    Spacer()
                    
                    if viewModel.isProcessing {
                        ProgressView()
                    }
                }
                .padding(.horizontal)
                .padding(.top, 10)
                
                // Transcribed Text Result Area
                ZStack(alignment: .topLeading) {
                    RoundedRectangle(cornerRadius: 15, style: .continuous)
                        #if canImport(UIKit)
                        .fill(Color(UIColor.secondarySystemBackground))
                        #else
                        .fill(Color.gray.opacity(0.1))
                        #endif
                        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 5)
                    
                    ScrollView {
                        Text(viewModel.transcribedText.isEmpty ? "轉換結果將顯示在這裡..." : viewModel.transcribedText)
                            .padding()
                            .foregroundColor(viewModel.transcribedText.isEmpty ? .secondary : .primary)
                            .font(.body)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    
                    // Copy action button
                    if !viewModel.transcribedText.isEmpty && !viewModel.isRecording && !viewModel.isProcessing {
                        VStack {
                            Spacer()
                            HStack {
                                Spacer()
                                Button(action: {
                                    #if canImport(UIKit)
                                    UIPasteboard.general.string = viewModel.transcribedText
                                    
                                    // Haptic
                                    let generator = UINotificationFeedbackGenerator()
                                    generator.notificationOccurred(.success)
                                    #elseif os(macOS)
                                    NSPasteboard.general.clearContents()
                                    NSPasteboard.general.setString(viewModel.transcribedText, forType: .string)
                                    #endif
                                }) {
                                    Image(systemName: "doc.on.doc")
                                        .padding(12)
                                        .background(Color.blue)
                                        .foregroundColor(.white)
                                        .clipShape(Circle())
                                        .shadow(radius: 3)
                                }
                                .padding()
                            }
                        }
                    }
                }
                .padding(.horizontal)
                
                // Original text toggle (Optional expanding section or just text below)
                if !viewModel.rawText.isEmpty && viewModel.rawText != viewModel.transcribedText {
                    DisclosureGroup("顯示原始辨識文字") {
                        Text(viewModel.rawText)
                            .font(.footnote)
                            .foregroundColor(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 5)
                    }
                    .padding(.horizontal)
                }
                
                Spacer()
                
                // Big Record Button
                Button(action: {
                    if !ApiConfig.shared.hasApiKeys {
                        showingSettings = true
                        return
                    }
                    viewModel.toggleRecording()
                }) {
                    ZStack {
                        Circle()
                            .fill(viewModel.isRecording ? Color.red : Color.blue)
                            .frame(width: 80, height: 80)
                            .shadow(color: (viewModel.isRecording ? Color.red : Color.blue).opacity(0.3), radius: 10, x: 0, y: 5)
                        
                        Image(systemName: viewModel.isRecording ? "stop.fill" : "mic.fill")
                            .font(.system(size: 30))
                            .foregroundColor(.white)
                    }
                }
                .disabled(viewModel.isProcessing)
                .padding(.bottom, 40)
            }
            .navigationTitle("SGH Voice")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        showingSettings = true
                    }) {
                        Image(systemName: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $showingSettings) {
                NavigationStack {
                    SettingsView()
                        .navigationBarItems(trailing: Button("完成") {
                            showingSettings = false
                            
                            // Re-check scene and style preferences if modified
                            viewModel.selectedScene = DictionaryManager.shared.activeScene
                            viewModel.outputStyle = ApiConfig.shared.outputStyle
                        })
                }
            }
        }
    }
}

#if DEBUG
#Preview {
    MainView()
}
#endif
