# Android 2.8.7：Production Review 修復與品牌間距

> 同日較早階段紀錄。後續 CC 詞彙修改與本輪安全修復的最終行為，請見 [安全學習修復](2026-10-03-android-safe-learning-final.md)；下列 322 測試與 APK 雜湊不可當作最新候選包的證據。

狀態：本機候選版，versionCode 37。尚未 Commit、Push 或部署；公開下載仍不得視為新版已上線。使用者要求先預覽再上傳，待確認後才發布個人更新 APK；不變更 Google Play 測試招募流程。

## Review 修復

1. 近期上下文不再於錄音結束時存成字串快照。STT 完成、回呼及同意檢查之後，開始 LLM 整理／翻譯之前才讀取；重新核對同一操作、輸入階段、InputConnection、設定及 60 秒期限。過期／清除回空，已辨識的人工修正讀到最新版。不能撤回已交付傳輸的請求。
2. 明確改口中的「四點」與「4 點」可做等值比較，不再只因寫法不同而退回原文。只接受有限、明確的 0–9999 常規中文整數＋限定單位；比較正規化不改寫輸出。日期、版本、路徑、識別碼、小數、半點與歧義寫法不放寬。所有數量都比對數值＋單位＋順序，不因等值轉換允許「元」變「美元」或刪掉單位。正負號涵蓋 ASCII、Unicode minus 及全形符號；實際值和真正否定仍保護。

## UI 檢查

| Before | After | Why |
| --- | --- | --- |
| Logo 與 SGH 緊鄰無間隔 | SGH 文字前恰好一個 U+0020 半形空格，沒有額外 margin | 符合使用者最新要求 |
| 品牌整組置中、正常寬度 22sp | 保留位置、字級與旁邊模式列；280/320/393/480dp、字體 1/1.5 倍驗證 | 不因小改動擠壓按鍵 |

本輪沒有改錄音色彩、波形、鍵盤高度或額外動態。預覽為正式 KeyboardView 的 native graphics 合成畫面，非實機麥克風測試。

## 修改檔案

- `ime/VoiceInputIME.kt`、`processing/TranscriptionPipeline.kt`：延後解析前文。
- `api/ExplicitSpeechRepair.kt`、`api/LlmClient.kt`：比較用數量標準化與守門。
- `res/values{,-en,-ja}/strings.xml`：單一半形空格。
- `app/build.gradle.kts`：2.8.7 / 37。
- `PersonalizedTranscriptionBoundaryTest`、`ExplicitSpeechRepairTest`、`LlmClientDictationSafetyTest`、`DictationRefinementTest`、`KeyboardGeometryTest`：回歸。
- `src/debug/README.md`、本文件、`2026-10-03-android-context-learning.md`：同步行為與限制。

以上是本次 Review 後增量，工作區另有前幾輪尚未提交的英文／日文操作、新 STT 選項與詞庫學習修復。未覆蓋 unrelated `build.sh` 及舊 APK。

## 驗證紀錄

- 修前新增逾期測試實際失敗；改 resolver 後針對性測試通過。
- 數字測試額外攔截到新負號被忽略；獨立複查另指出等值數字需連單位比對，新增測試確認換幣別確實誤過（1 test / 1 failure）。修復後完整 322 tests 通過，0 failures/errors/skipped。
- 既有 Keychain wrapper 的 `verifyReleaseSigningConfig` 通過。Review 所見是直接 Gradle 缺少注入設定，不是金鑰遺失；沒有輸出或更換金鑰。
- 最終命令：`./scripts/build_android_sideload_release.sh testDebugUnitTest assembleDebug lintDebug lintRelease assembleRelease --no-daemon`。BUILD SUCCESSFUL；Debug／Release APK 建置成功，Debug lint 0 errors / 113 warnings，Release lint 0 errors / 95 warnings。`git diff --check` 通過。
- 正式 APK v2 簽章驗證成功，唯一 signer 與實際 2.8.6 APK 一致；aapt 確認 package `com.shingihou.sghvoice`、versionName 2.8.7、versionCode 37。
- 本機候選產物：repo 上層 `release-output/android-2.8.7/SGHVoice-Android-v2.8.7.apk`，17,539,948 bytes；SHA-256 `26b193dc5e614544086dbeb7d41356229b30790f89c1ec64cbad0439aec19da1`。尚未放入公開網站下載目錄，release manifest 未變更。
- 預覽：repo 上層 `release-output/android-2.8.7-preview/voice-recording.png`、`english.png`、`japanese.png`。排版檢查遵循 emil-design-eng 的保留整體一致性原則，只調整一個空格，保留字級及鍵盤尺寸。

Agent Team：worker 實作數量比較；reviewer 獨立檢查期限與數量安全。主 agent 修前文流程、品牌間距，實際跑 RED/GREEN、完整測試、建置與簽章核對。

## 未完成／發布門檻

- 使用者確認品牌間距預覽後才上傳 APK。
- 沒有連接實機，常用 App 的游標、kana、錄音／長句與詞彙學習仍需手機驗收。
- 供應商仍為合成 contract 回歸，未用真人錄音／實際付費 API 證明新 STT 準確率。
- Drive/Firebase 同步保持規劃狀態，未啟用 OAuth、未上傳私人資料。
- 新 APK 應同簽章直接覆蓋側載版，不要先解除安裝；Google Play 安裝版應沿原管道更新。
