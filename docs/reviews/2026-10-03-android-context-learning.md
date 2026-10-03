# Android 英文游標、修正學習與近期上下文

本機開發紀錄；尚未 Commit、Push 或發布，手機上的已安裝版本不會自行取得這些修改。

## 英文操作

以真實 IME handler 與 Android InputConnection 驗證 `hello → Space → world`、連續空白、選取後空白／Enter，以及 Enter 後繼續輸入的位置。新發現的問題是多行編輯器帶 `IME_FLAG_NO_ENTER_ACTION` 時，程式忽略該旗標而執行送出。已修復；明確允許 Send action 的編輯器仍保留送出行為。

這不等於已在使用者手機所有 App 重現或驗收 Space 的狀況。手機上目前仍是已發布版本；本機修復待預覽核准後發布。

## 詞彙記憶

現有流程原本就會將人工改字轉為本機短詞修正，並在欄位允許個人化時送進後續 STT 用詞提示與 LLM 詞庫資料；不是聲學模型訓練。

本輪修正：

- 同一段只處理第一個改字的限制，改為原有 60 秒期限內，最多 8 個不同修正。
- 每次以剛修正後的文字作為下一次比對基準，避免第二個詞因舊 offset 漏記。
- 相同修正及往返切換不重複計入確認證據；不同詞即使改的是同一個字母，仍可分別學習。
- 可追蹤的單段語音上限由 512 增至 2,048 Unicode codepoints；宿主文字讀取依需要限縮，每側最多 2,200 字元、總窗口最多 4,400 codepoints。超出或無法定位時不猜測。
- 永久保存仍只限短詞對照，不保存整篇文章／錄音；低信心資料仍需兩次獨立修正證據，沒有取消隱私欄位守門。
- 翻譯輸出不反向寫成來源語言的錯字規則。

## 近期上下文

在「設定 → 個人詞庫」加入「參考同一欄位的近期語音」，預設關閉，需個人化學習啟用。

開啟後，只保留同一輸入階段最近一次已插入且可定位的語音末尾最多 512 codepoints，限 60 秒、只在記憶體。已辨識的人工修改會更新該暫存，期限不延長。換欄位／結束輸入即清除；密碼、不允許個人化、關閉開關、無法定位或過期均不使用。失敗重試及跨欄位草稿不借用前文。

前文以獨立 JSON 資料欄位交給已選用的整理／翻譯服務；不是指令。提示明確限制只輸出當次語音，不重播前文、不搬入舊姓名／數字／事實；口述守門仍只比對當次語音。STT 等待期間切換欄位或關閉功能，送 LLM 前會再次檢查並清掉 context。翻譯成功後只暫存已修正的語音來源，不暫存譯文作為來源上下文。

Production Review 後補強：停止錄音不再擷取前文字串快照。管線在 STT 完成、進度回呼及雲端同意檢查之後，開始整理／翻譯前才執行 resolver；IME 重新檢查同一操作、欄位連線、設定與暫存的 60 秒期限。等待期間已辨識的改字會讀到新版，過期或清除則回空。未允許個人化時連 resolver 都不呼叫。此決策點之後已交給供應商的請求不能宣稱可撤回。

這不是跨文章／跨 App 的永久聊天記憶，也不保證辨識和翻譯百分之百正確。「文章作成」原有多段語音累積 notes 的方式保持不變。

## 修改檔案

- `VoiceInputIME.kt`、`VoiceCorrectionTracker.kt`、新增 `RecentVoiceContext.kt`。
- `LlmClient.kt`、`TranscriptionPipeline.kt` 的可選 bounded context 參數與資料／指令分離。
- `ApiConfig.kt`、`SetupScreen.kt`、繁中／日文／英文 `strings.xml`。
- `ManualInputConnectionTest`、`VoiceCorrectionLearningTest`、`VoiceCorrectionTrackerTest`、新增 `RecentVoiceContextTest`、`VoiceLearningConnectionTest`。
- `DictationRefinementTest`、`LlmClientTranslationTest`、`PersonalizedTranscriptionBoundaryTest`。

## 驗證

修改前：英文多行 Enter 回歸 12 項中 1 項失敗；同段第二次改字回歸失敗。英文針對性修復後 13/13 通過。

整合驗證命令：`./gradlew testDebugUnitTest assembleDebug lintDebug --no-daemon`。最終 `BUILD SUCCESSFUL`，317 項測試通過、無失敗／錯誤／跳過；Debug APK 編譯成功、lint 無 error，`git diff --check` 通過。報告位於 `app/build/test-results/testDebugUnitTest/` 與 `app/build/reports/lint-results-debug.html`。供應商回應使用合成資料，沒有上傳實際音訊或使用真人金鑰。

APK 僅為 `android/SGHVoice/app/build/outputs/apk/debug/app-debug.apk` 本機編譯產物，不是覆蓋手機正式版的更新包。不要為了安裝 Debug APK 解除安裝正式版。
