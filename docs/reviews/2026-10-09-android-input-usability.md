# Android 輸入操作改善（2026-10-09）

## 範圍與發布狀態

只修改 Android 輸入法，不改網站、後端、供應商或雲端學習。依使用者要求先看介面再發布，本輪沒有 commit、push、Firebase 部署或 Play 上傳。版本號仍為 2.8.7 / 37；本機 debug APK 不是可覆蓋既有正式簽章版本的公開更新。

開始前已存在的 `build.sh` 修改與網站兩個舊版 APK 未變更、未納入本輪。

## 修改內容

- **錄音觸控背景**：移除有實心橢圓邊緣的 RippleDrawable mask，保留極淡、柔邊的 pressed/focused 回饋。沒有新增外框或陰影。
- **Emoji**：右上角笑臉開啟 72 個本機常用 emoji（三頁），長按仍可開啟系統輸入法選單。返回保留原本模式、日文 flick 與符號層。錄音處理中停用入口。整個 Unicode 字串一次提交，寫入失敗不丟棄待確認文字。
- **日文**：字典候選額滿也保留平假名與片假名。Enter 確認原始假名；Space 保留字典選字。游標移動、模式切換與 emoji 不強制選第一個漢字候選。
- **英文**：加入 558 個手工整理的常用詞前綴建議，與既有自訂詞、個人詞排名整合；只有使用者點候選才接受，不自動改字。不儲存輸入、不連網。不是完整拼字修正或下一詞預測。
- **錄音續接**：`onStartInput(..., restarting=true)` 可確認同一欄位時，保留 STARTING/RECORDING 與 session/operation token。欄位識別不明且 connection 改變、敏感欄位、真的隱藏輸入法或切換欄位仍停止／走既有草稿保護。STOPPING/PROCESSING 不重新綁定目的欄位。
- **亮屏**：只有 STARTING/RECORDING 設定 `View.keepScreenOn`；停止、離開、銷毀均解除。沒有背景持續錄音權限或永久 wake lock。
- **密碼保護**：所有模式在敏感欄位不鏡像顯示 composition/candidates；拒絕 stale 候選點擊。英文也遵守 no-suggestions 欄位設定。

## 修改檔案

以下路徑相對 `android/SGHVoice/`：

- `app/src/main/java/com/shingihou/sghvoice/ime/KeyboardView.kt`
- `app/src/main/java/com/shingihou/sghvoice/ime/VoiceInputIME.kt`
- `app/src/main/java/com/shingihou/sghvoice/ime/japanese/JapaneseComposer.kt`
- `app/src/main/java/com/shingihou/sghvoice/ime/manual/EnglishComposer.kt`
- `app/src/main/java/com/shingihou/sghvoice/ime/manual/LocalEnglishCandidateProvider.kt`（新增）
- `app/src/main/java/com/shingihou/sghvoice/ime/manual/EmojiPalette.kt`（新增）
- `app/src/main/java/com/shingihou/sghvoice/ime/manual/ManualKeyboardModels.kt`
- `app/src/main/java/com/shingihou/sghvoice/ime/manual/ManualKeyboardLayoutProvider.kt`
- `app/src/main/res/values{,-en,-ja}/strings.xml`
- `app/src/test/java/com/shingihou/sghvoice/ime/AndroidInputUsabilityTest.kt`（新增）
- `app/src/test/java/com/shingihou/sghvoice/ime/KeyboardInteractionTest.kt`（新增）
- `app/src/test/java/com/shingihou/sghvoice/ime/KeyboardGeometryTest.kt`
- `app/src/test/java/com/shingihou/sghvoice/ime/japanese/JapaneseComposerTest.kt`
- `app/src/test/java/com/shingihou/sghvoice/ime/manual/EnglishComposerTest.kt`

## 驗證證據

1. Composer 舊行為：25 tests / 2 failures，重現假名被候選截斷與缺少英文通用詞。`/tmp/sgh-oct09-composer-red.log`。
2. 真實 KeyboardView 的原生繪圖：原錄音 ripple mask 邊緣 alpha=255，7 tests / 1 failure；修正後 UI/geometry/layout 26 tests 通過。`/tmp/sgh-oct09-ui-mask-red.log`、`/tmp/sgh-oct09-ui-green.log`。完整 ripple 動畫未在 Robolectric 重現，不把 mask 證據當成實機錄影。
3. 真實 IME handler + Android InputConnection：原程式 5 tests / 4 failures，重現重啟誤停、未保持亮屏、Enter 強制漢字、emoji 尚未接線。`/tmp/sgh-oct09-ime-red.log`。英文 production provider 另有 1 test / 1 failure，`/tmp/sgh-oct09-english-ime-red.log`。
4. 全量中間檢查 445 tests / 1 failure，額外抓到密碼 composition 明文，修正後重新執行。`/tmp/sgh-oct09-integrated.log`。
5. 最終驗證命令：`./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug --no-daemon`，BUILD SUCCESSFUL（1m 40s）。XML 加總 **445 tests、0 failures、0 errors、0 skipped**。Lint **0 errors、115 warnings**（尚非零警告，包含依賴版本、未使用資源等）；debug APK 建置成功。log `/tmp/sgh-oct09-final-green.log`，APK `android/SGHVoice/app/build/outputs/apk/debug/app-debug.apk`。

預覽為實際 KeyboardView 原生渲染的合成狀態，不是實機截圖：

- `android/SGHVoice/app/build/reports/keyboard-preview/voice-recording-pressed-100.png`
- `android/SGHVoice/app/build/reports/keyboard-preview/zhuyin-emoji-100.png`
- 同目錄包含各模式一般畫面與 emoji 畫面。

## 尚需實機確認與刻意保留的限制

- `adb devices -l` 沒有連接裝置；未呼叫付費 API、未做真實麥克風或跨 App 錄音實測。Robolectric lifecycle 測試是 callback/state/token 證據，不是真實錄音不中斷的保證。
- **左下角切換鍵**：原程式注音左下角是 `?123` 數字符號切換；App 外部輸入法切換原在右上方。Android 導覽列的鍵盤切換圖示未移除，仍需使用者提供該按鈕截圖與手機型號定位。
- 不會越過使用者主動鎖屏或 App 真的失去輸入焦點去背景錄音；這些情況保留既有草稿／手動插入流程。
- 既有兩分鐘自動送出上限保留，不等於無限長錄音。部分 App 滑動若真的銷毀／切換 editor，仍可能停止；只修正確定同欄位的 restart。
- Emoji 字型外觀取決於 Android 版本，尚無最近使用、搜尋或膚色選擇。
- 需使用者先確認錄音按下畫面與 emoji 入口，再另行處理簽章、版本遞增與公開下載。

## 官方生命週期參考

- [InputMethodService](https://developer.android.com/reference/android/inputmethodservice/InputMethodService)：`restarting` 與 `onFinishInputView` 的差異。
- [Keep the screen on](https://developer.android.com/develop/background-work/background-tasks/awake/screen-on)：僅在需要時使用與解除 keepScreenOn。

Agent Team：兩個 worker 分別處理 composer 與 KeyboardView；主 agent 整合 IME、資源字串、生命週期與驗證。Composer worker 另做唯讀整合檢查。
