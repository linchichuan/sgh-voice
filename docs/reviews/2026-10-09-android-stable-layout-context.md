# Android 鍵盤穩定性與語音整理改善

日期：2026-10-09。基底：`0d33993988da950a106dbf1b8099a1d5218d28d3`（2.8.9 / 39）。

範圍只限 Android。本輪未 commit、push、簽署正式 APK、Firebase 部署或修改公開下載頁；依使用者要求，UI 先預覽再上傳。既有研究筆記保留，原始 source checkout 的不相關修改未動。

## 1. 完成內容

### 鍵盤：穩定操作目標

| Before | After | Why |
| --- | --- | --- |
| 注音第一個字讓讀音列從 GONE 出現；第一列鍵子下移 28dp 並縮小 | 讀音與候選共用固定高度區塊；沒輸入時預留讀音位置 | 同一手指位置持續對到同一按鍵，避免按第二字時誤觸 |
| 英文缺少數字列 | 英文 LETTERS 頂列固定 `1 2 3 4 5 6 7 8 9 0`，Shift/Caps 不改數字 | 不必切換符號頁才能輸入數字 |
| 各手動模式候選區可能改變按鍵起點 | 注音、英文、日文共享固定候選區外框與按鍵區起點；日文十二鍵保留自身排列 | 降低切換模式的手指重新定位成本 |

沿用既有淺色、Logo、SGH、語音橢圓和高度設定，沒有新增裝飾、邊框或按鍵位移動畫。窄螢幕、大字體、90% 高度仍可能需要捲動，以保留觸控目標；不宣稱每一種手機都完全不捲動。

高度設定位置：**SGH Voice → 基本設定 → 鍵盤高度**，90–125%，下次開啟鍵盤時套用。

### 語音：標點、文脈與連續草稿

- 長句即使前面或最後已有一個句號，也會檢查是否仍有大段缺少標點。
- 補標點優先沿用已通過守門的整理結果，不把已清理的贅字又從原始 STT 帶回。
- 沿用最多一次、12 秒上限的額外標點請求；停用 AI 或服務失敗不增加請求。短而明確的中文陳述可本機補句號；不猜問句，也不保證所有內容都有理想標點。
- 新增否定詞邊界保護，拒絕把「不要部署」改成「不，要部署」等意思反轉。原有數字、姓名、否定及代答防護保留。
- 翻譯提示明確要求保留疑問／不確定性、自然標點、主題分段及明確第一／第二點的條列；不新增事實，不把前文重新翻譯。仍是一輪 STT 加一輪多語言翻譯，不加逐語言串行整理。
- 在既有「文章做成」累積草稿的產生按鈕新增二選一：**整理原話（不代寫）**／**幫我寫（按指令代寫）**。前者把本次完整段落送進忠實整理與守門，不把口述問題當成要求 AI 回答。
- 本次草稿上限 8,000 字元，結果先預覽、使用者再插入。整理失敗、被拒絕或輸出超過保存上限時保留原草稿，不誤報已保存。
- 普通口述原有最近前文 60 秒／512 字元機制不變；這次不是自動跨 App 長期記憶。連續草稿沿用輸入法服務記憶體，不新增雲端歷史儲存，服務被系統終止仍可能遺失未插入草稿。
- 成功輸入後，既有狀態列顯示本次辨識與整理／翻譯耗時。只在本機本次操作使用，不記錄內容、不上傳分析。數值含管線工作，不等同純供應商回應時間，也不是已實測加速的宣稱。

### 場景詞庫與修正記憶

入口：**SGH Voice → 個人詞庫 → 語音場景詞庫**。

- 新增軟體開發及商務日文場景，保留一般與醫療場景；各場景可手動加短詞，最多 100 個，每詞 64 字元。
- 場景專用詞按場景本機保存，僅選中場景參與提示。全域手動詞／既有已生效學習詞仍依原設計跨場景使用。
- 提示優先順序：全域手動詞 → 已確認學習詞 → 場景手動詞 → 固定詞。100 個場景詞也不能因此把高優先學習詞擠掉。
- 未確認學習詞仍不上傳；中文學習詞不新增直接字串替換。STT 50 詞／800 字元、LLM 32 詞／1,200 字元的既有限制不變，不代表所有詞每次都會送出。
- 同意雲端處理後，相關提示詞才隨既有辨識／整理請求送出；這是上下文提示，不是訓練個人模型。沒有新增 Drive、OAuth、Firebase 同步、全員共享個人詞或音訊集中保存。

## 2. 修改檔案

以下均相對 `android/SGHVoice/app/src/`：

- 原生鍵盤：`main/.../ime/KeyboardView.kt`、`main/.../ime/VoiceInputIME.kt`、`main/.../ime/manual/ManualKeyboardLayoutProvider.kt`、`main/res/layout/keyboard_view.xml`。
- 整理管線：`main/.../api/LlmClient.kt`、`main/.../processing/TranscriptionPipeline.kt`、`main/.../processing/FactPreservation.kt`。
- 場景詞庫：`main/.../processing/DictionaryManager.kt`、`main/.../processing/VocabularyHintPolicy.kt`、`main/.../ui/SetupScreen.kt`、新增 `main/.../ui/SceneVocabularyPicker.kt`。
- 中／日／英資源：`main/res/values{,-ja,-en}/draft_strings.xml`、`scene_strings.xml`。
- 測試：`ZhuyinCandidateUiTest`、`ManualKeyboardLayoutProviderTest`、`DictationPunctuationRecoveryTest`、`LlmClientDictationSafetyTest`、`LlmClientTranslationTest`、`TranscriptionPipelineTest`、新增 `ContinuousDraftOrganizationTest`、`DictionarySceneVocabularyTest`。

## 3. 測試與驗證

最終全量：**62 suites／512 tests，0 failures、0 errors、0 skipped**。`lintDebug` 與 `assembleDebug` 完成，Gradle `BUILD SUCCESSFUL`（1m 43s）。`git diff --check` 通過。

執行命令（於 `android/SGHVoice`）：

```sh
ANDROID_HOME=/Users/lin/Library/Android/sdk ./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug --no-daemon --max-workers=2
```

Lint 為 **0 errors／118 warnings**，並非零警告：包含依賴／target SDK 更新、UnusedResources、KTX 建議、文字與排版提示。本輪場景英文計數字串有 PluralsCandidate 提示、偏好儲存有 KTX 建議；不為這些提示做無關架構重構。完整明細：`android/SGHVoice/app/build/reports/lint-results-debug.html`。

Debug APK SHA-256：`6e761e2e9c283bbbc71fc81207b19271082951b775e4d8ac119a7b7bd765d118`。未更改正式版本號 `2.8.9 / 39`。

回歸證據：

- 原生 View 探針在修復前確認注音第一個字使按鍵 y 軸增加 28dp，修復後逐一比較所有按鍵 x/y/width/height。
- 覆蓋 320／393dp、1／1.5 倍字體、90／100／125% 鍵盤高度、空候選／長讀音／候選展開再收合。
- 英文數字列測試在修復前期待 `1234567890`、實際得到 `qwertyuiop`；修後檢查全部 Shift 狀態與直接數字輸入 action。
- 場景提示壓力案例：100 場景詞＋真實 repository 兩次確認的生效詞；修復前 7 tests／1 failed，失敗點是學習詞被排擠。
- 整理跨段落、問題不代答、撤回同意、改事實拒絕，以及超長輸出保留原稿均有合成測試。文字管線測試的 HTTP 由本機 interceptor 回覆，沒有真實付費 API 呼叫。
- 獨立 reviewer 以真實 guard／draft store 探針找到 5,999 字原稿被格式化成 16,988 字時「保存失敗卻顯示成功」；輸出上限與保存返回值均已補檢查，加入相同探針的回歸。

## 4. 產物與預覽

均相對本工作區：

- 英文數字列：`android/SGHVoice/app/build/reports/keyboard-preview/english-100.png`。
- 注音輸入前／後：`android/SGHVoice/app/build/reports/keyboard-preview/zhuyin-stable-comparison.png`。
- 個別圖：同資料夾 `zhuyin-stable-idle-100.png`、`zhuyin-stable-typing-100.png`。
- Debug APK：`android/SGHVoice/app/build/outputs/apk/debug/app-debug.apk`。這是驗證產物，**不是正式簽章的手機更新版**。

圖來自 Robolectric 執行真實 Android View 的本機渲染，不是設計稿，也不是實機／模擬器截圖。未加入使用者對話或醫療內容。

## 5. 發布門檻與限制

先讓使用者確認預覽，再另行正式打包、簽章、上傳與驗證下載路徑。本輪不修改已發布版本號或公開網站。

未做 Android 手機實測、真實麥克風辨識、付費模型品質／延遲比較或設定頁實機視覺驗收；因此不宣稱準確率提升幅度、翻譯已變快、絕不漏標點或所有焦點競態均已解決。Streaming 即時預覽及跨裝置雲端同步留待後續獨立驗收。

Agent Team：一位 worker 處理文字品質並唯讀交叉檢查草稿安全，一位處理場景詞庫；主 agent 處理鍵盤、連續草稿與耗時接線、整合修復、全量驗證及最終發布判斷。
