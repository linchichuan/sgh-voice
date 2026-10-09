# Android 選字、離線字典與標點修復

## 範圍及發布狀態

延續同日 `2026-10-09-android-input-usability.md` 的本機修改，這一階段只處理 Android 注音選字、英文／日文字典和語音標點。未變更網站、Firebase、Google Play、帳號或付款設定；沒有 commit、push、正式簽章或公開更新。版本仍為 2.8.7 / 37。原先未提交的 Android 修改保留；無關的 `build.sh` 與網站舊 APK 未動。

## 完成內容

### 注音選字

- 在全句候選之外提供「前段」候選，例如 `ㄅㄨˋ ㄓ ㄉㄠˋ ㄅ` 可先選「不知道」，留下誤觸的 `ㄅ` 繼續編輯；也可先選「不」，留下 `ㄓ ㄉㄠˋ ㄅ`。
- 僅在 editor 成功接收候選後才消耗相應注音；Space、模式切換與 emoji 等隱式提交不使用部分候選，避免丟掉尾段。
- 新增一次「重選」：只撤銷剛才選中的那一段，恢復原注音。必須仍是同一 InputConnection、同一 session、同一游標與相鄰文字；選取範圍、游標移動、換欄位或繼續按鍵會讓它失效。
- 重選前暫緩候選學習，避免立即改掉的誤選污染個人排名。敏感欄位不保留此狀態。只在記憶體保留短的相鄰文字快照，沒有新增儲存或上傳。
- 這不是任意點選已輸入文章後重新轉換；editor 不提供可靠快照時，重選按鈕停用。

### 候選區 UI

- 注音讀音移至獨立 28dp 摘要列，不再佔住候選列左方 96dp。
- 注音候選列 56dp、候選觸控高度至少 52dp；「重選」48dp。一般按鍵仍保留最小觸控尺寸。
- 展開候選以兩欄顯示，長詞跨欄換行，不顯示省略號。展開時讀音回到上列，不保留空白候選帶。
- 整體鍵盤高度設定不變；較窄、90% 高度與大字體時沿用捲動避免裁切底部。
- 候選字型語系依模式使用 zh-TW／ja-JP／en-US，不依手機系統語言誤用字形。
- 英文與日文候選列原有尺寸維持。這一階段不再更動錄音橢圓。

### 字典

- 英文新增 AOSP 離線詞頻候選 45,371 詞，原 558 個精選詞仍優先。不是雲端建議、自動改字或完整拼字修正。
- 日文由 22,819 增至 32,005 候選（26,818 讀音），保留正常日文新字體，不套中文 OpenCC。
- 兩份 TSV 共約 1.46 MB（未壓縮），比前一階段新增約 820 KB；不以 APK 大小作為刪減常用詞的理由。
- 注音原本已有超過 15 萬候選，本次主要修選字行為。另限縮移除內建讀音候選的三個常見簡體單字變體「体／网／万」，保留繁體「體／網／萬」；不是全域簡轉繁，不影響手動自訂詞、複詞或合法「云」。
- 來源、固定版本、SHA-256、授權、重建命令及桌面 JVM 效能實測見 `2026-10-09-offline-keyboard-lexicons.md`。英文字頻來源本身為 2014 年，不宣稱是最新詞彙語料。

### 語音標點

- 重現原因：AI 第一輪改錯內容被保真檢查擋下，連同正確標點一起退回原文；以及第一輪直接回傳長串無標點文字。
- 第一輪成功回應、仍為長段無標點口述時，最多追加一次相同供應商的「只補標點」請求，以原始辨識文字為基礎，不帶前文或詞彙提示。追加請求最多等待 12 秒。
- 第二輪除標點與空白之外的字元及順序必須完全相同；英文詞邊界也必須相同，再經既有數字、否定、姓名等完整保真檢查。失敗仍回退，不放寬守門。
- AI 關閉、首請求失敗／空白、編輯／翻譯模式不追加此請求。每次請求都重新確認雲端處理同意；撤回同意及取消會中止，不偷偷重試。
- 可能多一次現有供應商 API 成本與等待，不新增供應商、不變更憑證與資料儲存。不保證所有標點都語意完美，也不保證短句或已有少量標點的長句會進入此補救路徑。

## 主要修改檔案

以下路徑相對 `android/SGHVoice/`；其他同日上一階段 dirty 檔案不是本階段新增。

- `app/src/main/java/com/shingihou/sghvoice/ime/{ZhuyinComposer,AndroidZhuyinLexicon,ZhuyinReselection,VoiceInputIME,KeyboardView}.kt`
- `app/src/main/java/com/shingihou/sghvoice/ime/manual/AndroidEnglishCandidateProvider.kt`
- `app/src/main/java/com/shingihou/sghvoice/ime/japanese/JapaneseLexicon.kt`
- `app/src/main/java/com/shingihou/sghvoice/api/LlmClient.kt`
- `app/src/main/java/com/shingihou/sghvoice/ui/SetupScreen.kt`
- `app/src/main/res/layout/keyboard_view.xml`、`app/src/main/res/values{,-en,-ja}/strings.xml`
- `app/src/main/assets/{english,japanese}/`、`tools/generate_{english,japanese}_lexicon.py`
- 對應 composer、IME、原生候選 UI、字典、效能、標點、generator 回歸測試。

## 驗證證據

- 注音前段選字：修改前 4 tests / 4 failures，log `/tmp/sgh-zhuyin-head-red.log`。
- 候選 UI：修改前觸控尺寸、長詞截斷及字型語系 3 個測試失敗；修改後走真實 KeyboardView 原生渲染，不是設計稿。
- 標點補救：修改前 3 個新測試失敗，log `/tmp/sgh-zhuyin-punctuation-check.log`。涵蓋 Claude/OpenAI/Groq 的 HTTP synthetic 回覆，不呼叫付費服務。
- 內建簡體單字候選：修改前實際 asset 測試失敗，log `/tmp/sgh-zhuyin-traditional-red.log`；不是 mock 字典。
- 舊 beam segmentation 測試新增 `includeHeadMatches=false`，保留原 4 個分段候選期望；新前段候選另測，沒有藉由放寬斷言隱藏回歸。
- Python generator 全 7 tests 通過；驗證資料篩選、資產 hash／大小、注音索引。
- 最終統一命令：`./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug --no-daemon --max-workers=2`，`BUILD SUCCESSFUL in 3m 5s`。XML 合計 **59 suites／475 tests，0 failures、0 errors、0 skipped**。其中前段選字 9、候選 UI 7、標點 6、實際注音資產 1 均通過。標點另包含第一次回覆後撤回雲端同意，只送出第一個請求的反向案例。
- Lint **0 errors、116 warnings**；不是零警告。新增授權按鈕沿用既有 `Uri.parse`，有 KTX `toUri` 的風格建議，未為此做無關重構。`git diff --check` 通過。最終 log：`/tmp/sgh-android-candidates-final.log`。
- Debug APK：`android/SGHVoice/app/build/outputs/apk/debug/app-debug.apk`，36,872,427 bytes（約 35.2 MiB），SHA-256 `222996bf7f3003ada0a714e23cd4e49647171687db75cf7131ca15e8b7bdd50a`。Debug 與既有 release 編譯設定不同，不能用這個大小差值宣稱字典造成多少正式 APK 增幅。

## 預覽與驗收限制

原生預覽位於 `app/build/reports/keyboard-preview/`：`zhuyin-candidates-100.png` 與 `zhuyin-candidates-expanded-100.png`。這是 Robolectric 的真實 View 合成狀態，不是手機截圖。

`adb devices -l` 顯示沒有已連接裝置；未測實體手機、真實麥克風、跨 App 輸入與付費 AI。桌面測得的查詢時間／heap 不是 Android 手機效能保證。主 agent 與 UI worker 已目視確認兩張最新預覽無文字裁切或重疊。UI 必須先由使用者確認，再另行版本遞增、正式簽章及發布；debug APK 不當成正式可覆蓋更新的下載連結。

Agent Team：一位負責候選 UI；另一位查核及擴充離線字典，另做標點補救的唯讀檢查。主 agent 實作組字、IME 整合、標點安全檢查，並執行最終全量驗證。
