# Android 語音整理與鍵盤操作修復

日期：2026-10-03。範圍：本機實作、測試及預覽；未 Commit、Push、Firebase 部署或 Play 上傳。

## 修復內容

| 問題 | 根因與調整 |
| --- | --- |
| 正確整理退回逐字稿 | 守門以原始否定詞、撤回的數字及字元保留率比較。新增 `ExplicitSpeechRepair`，只在比較時辨識有標點分隔的明確改口；提示詞同步說明。實際輸出仍取 LLM 結果，不用正規表示式重寫全文。 |
| 改口與真正否定混淆 | 允許「三點，不是，四點」「GitHub 啊，沒有，在…」等狹義模式；仍保護真正否定、技術詞、路徑及最終數量。無明確依據的語句仍保守退回原文。 |
| 詞庫順序 | 自訂／已確認詞先入選，Whisper prompt 再反向排列，讓重要詞留在尾端；800 字元上限不是 224 tokens 的精確換算。 |
| 新轉錄模型 | 新增可選的 `gpt-transcribe` 與專用 `keywords[]`、`languages[]`。既有模型偏好不變，新安裝才採新預設。詳見同目錄 OpenAI contract 文件。 |
| 英文移動游標後仍輸入舊位置 | 宿主游標移動、選取或結束組字時，清除舊 composer 狀態，但保留已輸入文字及新選取位置。 |
| Enter 要按兩次 | 一次按鍵同時確認英文組字並執行宿主 Enter 動作。 |
| 日文只有 flick | 中央點擊重新接回連按循環；850ms 內同鍵換字，方向 flick 仍可直接選字。 |
| 日文缺少文字游標左右鍵 | 右側加入 ←／→，先確認組字再移動文字框游標；かな／カナ 改放底列。保留 Romaji 切換與原配色。 |

## 主要修改檔案

路徑皆位於 `android/SGHVoice/app/src/`：

- `main/java/com/shingihou/sghvoice/api/`：`ExplicitSpeechRepair.kt`、`LlmClient.kt`、`WhisperClient.kt`、`ApiConfig.kt`、`ApiModelCatalog.kt`。
- `main/java/com/shingihou/sghvoice/processing/`：`VocabularyHintPolicy.kt`、`DictionaryManager.kt`、`RecognitionLanguage.kt`。
- `main/java/com/shingihou/sghvoice/ime/`：`VoiceInputIME.kt`、`KeyboardView.kt`；`japanese/KanaFlickKeyView.kt`；`manual/InputCursorMovement.kt`、`ManualKeyboardModels.kt`、`ManualKeyboardLayoutProvider.kt`。
- `main/java/com/shingihou/sghvoice/ui/SetupScreen.kt` 與三種語系 `strings.xml`。
- 對應 API、語音安全守門、詞庫、IME InputConnection、Kana 與 layout 測試；`debug/README.md`。

未修改原先已存在的 `build.sh` 變更或舊下載 APK。

## 驗證方式

先重現兩個使用者改口案例，以及英文游標、Enter、Kana tap 路由和缺少方向鍵的紅燈，再修復。回歸包含真實 IME handler＋Android Editable/InputConnection、production KeyboardView 渲染，以及攔截 HTTP 的合成回應。LLM 整理流程涵蓋 Claude、OpenAI、Groq 的實際請求／解析／驗證程式，但不是對供應商的真實呼叫。

完整命令：

```sh
cd android/SGHVoice
./gradlew testDebugUnitTest assembleDebug lintDebug --no-daemon -Pkotlin.incremental=false
```

最終工作區全套 298 項測試通過，無失敗、錯誤或跳過；Debug APK 編譯成功；lint 無 error（112 個 warning）。最後一次命令回傳 `BUILD SUCCESSFUL`。測試報告位於 `app/build/test-results/testDebugUnitTest/`，lint 報告位於 `app/build/reports/lint-results-debug.html`。`git diff --check` 通過。

## 預覽與驗收

- `/Volumes/Satechi_SSD/voice-input/release-output/android-ui-preview-2026-10-03/japanese-keyboard.png`
- `/Volumes/Satechi_SSD/voice-input/release-output/android-ui-preview-2026-10-03/english-keyboard.png`
- Debug 編譯產物：`android/SGHVoice/app/build/outputs/apk/debug/app-debug.apk`。這不是給既有正式安裝覆蓋更新的簽章版本；不要為了安裝它先刪除正式 App。

沒有連接 Android 手機，未驗證 Chrome、聊天 App 等實際宿主；沒有上傳音訊或使用真人 API key，不能據此宣稱新模型辨識率已提升。

使用者先看日文鍵盤預覽。確認後再進入正式版本號、簽章 APK、發布與下載驗證；本輪沒有變更線上 2.8.6。安裝正式新版後，既有使用者需到設定的 OpenAI 語音辨識模型選擇 GPT-Transcribe；雲端整理亦須有已選用且可用的整理服務。

實機應確認：移動英文游標後輸入、一次 Enter、日文連按與 flick 混用、左右鍵在輸入框內移動，以及有真實否定詞的長句改口與條列整理。
