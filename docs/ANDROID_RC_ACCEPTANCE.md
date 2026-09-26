# SGH Voice Android RC 實機驗收

> 適用版本：Android 2.8.2（versionCode 32）側載個人測試版；不是實機 RC 全項通過聲明
> 文件狀態：QA／RC 驗收用途
> 禁止事項：不得使用真實患者姓名、病歷、電話、付款或其他個人資料

## 1. 驗收目標

本輪只驗證以下已完成範圍：

1. 退格鍵點按與長按連續刪除。
2. 手機鍵盤的畫面比例、可觸達性與不同輸入模式切換。
3. 客戶可自行選擇語音辨識來源語言及 Android 系統鍵盤。
4. 翻譯不得回答原文中的問題或執行原文中的請求。
5. 既有錄音、轉寫、插入與翻譯流程沒有回歸。
6. 使用者在錄音後撤回雲端處理同意時，音訊不會送出。
7. 整句聽寫整理、技術詞彙、人工確認詞提示與圓形收音光暈；新增驗收案例見 [本輪改善紀錄](reviews/2026-09-11-android-dictation-refinement.md)。
8. 單一淺綠大圓完成開始／錄音／結束，以及語音底列「、」「，」「。」；本版驗收案例見 [2.7.8 單一圓形控制紀錄](reviews/2026-09-12-android-single-circle-review.md)。
9. 先刪除再輸入的短修正追蹤、完整英文詞提示及安全匹配；本版驗收見 [2.7.9 個人化改善紀錄](reviews/2026-09-12-android-personalization-review.md)。
10. 「幫我寫」筆記／成稿預覽、日文 12 鍵、48 個注音候選、小視窗操作與欄位切換後的明確重試；見 [2.8.2 Production Review](reviews/2026-09-26-android-production-review.md)。

醫療詞庫不在本次 RC 驗收範圍，本輪也不得匯入完整醫療詞表。

## 2. 測試前提

- 使用一台實際 Android 手機，不只使用 Emulator。
- 建議 Android 12 以上，至少測試一台一般尺寸手機。
- 已安裝並啟用 SGH Voice Input。
- Android 系統另啟用至少兩種鍵盤，其中一種為韓文或英文鍵盤。
- 使用測試用 API key／帳號，不使用 production 患者資料。
- 所有文字只留在草稿欄位，不實際傳送 Email、LINE、表單或訊息。
- 記錄候選版 APK 的 SHA-256、手機型號、Android 版本及測試時間。

可先執行：

```bash
./scripts/verify_mobile_rc.sh
```

手機連線且已確認要覆蓋安裝時，才執行：

```bash
./scripts/verify_mobile_rc.sh --install
```

## 2.1 2.7.6 自動化與模擬器檢查（2026-09-11；歷史紀錄）

> 本輪未連接 Android 實機。模擬器檢查不能取代真實麥克風與手機實測。
> 第 4 節包含 **31 個基礎實機案例，另加 7 個注音案例，合計 38 個**，全部尚待實機操作。
> 先前版本的 475 個 Python／132 個 Android 測試結果不作為本版通過證據。
> 本輪結果隨執行證據填寫；未完成的檢查維持待驗，不宣稱 RC 已通過。
> 下表保留 2.7.6 的實際結果；2.7.7 相容性修補的結果另見第 2.2 節，不將本表自動視為新版通過。

| 檢查項目 | 指令 | 結果 | 證據／備註 |
|---|---|---|---|
| Git diff 格式檢查 | `git diff --check` | PASS | 無 diff 格式錯誤；不推定工作區 clean |
| Python 迴歸測試 | `venv/bin/python -m pytest tests/ -o addopts='' -q` | PASS | 534 passed in 6.11s；在新版 APK 與 metadata 完成後重跑通過 |
| Python 靜態檢查 | `ruff check . --select E9,F63,F7,F82` | PASS | Release-critical 規則通過 |
| iOS source／metadata preflight | `./scripts/verify_ios_app_store_preflight.sh --source-only` | PASS | source-only 通過；不包含 Xcode Archive／TestFlight／App Store 帳號 gate |
| Android 單元測試 | `./gradlew testDebugUnitTest --no-daemon` | PASS | 164 tests，0 failures／0 errors／0 skipped；包含短句修句、輸出守門、詞彙提示與光暈包絡測試 |
| Android Debug Lint | `./gradlew lintDebug --no-daemon` | PASS | 0 errors／88 warnings |
| Android Release 組建與 Lint | `./scripts/build_android_sideload_release.sh` | PASS | 2.7.6／versionCode 26；BUILD SUCCESSFUL；Release Lint 0 errors／76 warnings，產物 signer 另由 artifact-only 核對 |
| 2.7.6 artifact 驗證 | `./scripts/verify_mobile_rc.sh --artifact-only` | PASS | ARTIFACT VERIFIED：APK 版本、大小、SHA-256、唯一 signer 憑證與網站 metadata 一致 |
| Android 模擬器 | Debug 2.7.6／26 安裝、合成收音與四模式 UI smoke | PASS（模擬器限定） | 5 張最新實際 View 截圖已檢視，無重疊爆版，24dp Enter 置中；SGH crash buffer 無 crash；不代表實機收音、延遲、準確度或 38 個實機案例通過 |
| Android 實機 | 真實手機與第 4 節案例 | 未執行 | 未連接實機；31 個基礎案例與 7 個注音案例全部待驗 |

## 2.2 2.7.7 相容性修補驗證（歷史紀錄）

2.7.7 將 Unicode Han script 正則表達式改為 Android 8／9 可用的 `script=Han` 語法；功能與雲端處理同意版本 3 不變。2.7.6 APK 保留原檔與原 hash，不覆寫已公開的 immutable URL。

| 檢查 | 本版結果 |
|---|---|
| Android 單元測試與 Debug／Release Lint | 164 tests 通過；Debug Lint 0 errors／88 warnings、Release Lint 0 errors／76 warnings |
| Python 迴歸與最低支援版本相容性 gate | 535 passed in 6.06s；新增 source 相容性 gate 修補前失敗、修補後通過，不代表 Android 8／9 runtime 實測 |
| Firestore Rules、JavaScript 與 Ruff | Rules Emulator 3／3 通過；i18n JavaScript 語法與 release-critical Ruff 通過 |
| 簽署 APK／AAB 與 artifact-only | BUILD SUCCESSFUL（2m38s）；ARTIFACT VERIFIED；AAB jarsigner 驗證通過，Release APK manifest 無 Debug fixture |
| Android 8／9 實機 | 未執行；官方語法依據與單元測試不能取代實機 |
| 31 個基礎＋7 個注音實機案例 | 全部仍待驗 |

## 2.3 2.7.8 單一圓形錄音控制（2026-09-12；已發布歷史）

本版只調整錄音控制介面及語音底列標點：`@` 改為頓號 `、`，逗號 `，`、句號 `。` 保留。STT、AI 整理、供應商、隱私及雲端處理同意版本 3 均不變；第 2.1、2.2 節是先前版本證據，不視為本版已通過。

| 檢查 | 本版結果 |
|---|---|
| Firestore 下載登記規則 | 紅綠驗證完成：舊規則拒絕 2.7.8；同步後 Emulator 3／3 通過 |
| JavaScript 語法與 Python release gates | 最終產物完整驗證：Python 535 passed in 5.88s；JavaScript 語法、release-critical Ruff 通過；production npm audit 0 vulnerabilities |
| Android 單元測試與 Lint | 167 tests 通過；Debug Lint 0 errors／95 warnings，Release Lint 0 errors／78 warnings |
| 簽署 APK／AAB 與 artifact-only | 字體裁字修正後最後組建 BUILD SUCCESSFUL（2m50s）；最終 APK `8bef8543…93809049` 的 artifact-only PASS，版本、大小、hash 與 signer 符合 metadata |
| 模擬器與 UI 畫面 | active／silent／processing 三圖已目視檢視；最終 `ui-final-contract.xml` PASS，200% zh-TW 字體截圖確認狀態列與圓內文字無裁切；屬 synthetic UI 驗證，不等同實機收音驗證 |
| 31 個基礎＋7 個注音實機案例 | 全部仍待驗；另須完成本版單一圓形及標點案例 |
| Firebase／Google Play | 2.7.8 Firebase Rules／Hosting [34668475395](https://github.com/linchichuan/sgh-voice/actions/runs/34668475395) 已成功；live APK bytes、hash 與本機 `cmp` 通過。Google Play 未操作 |

## 2.4 2.7.9 個人化修正追蹤（2026-09-12；歷史紀錄）

本版修正先刪除再輸入的短修正漏記，及完整英文詞的提示與匹配。2.7.8 單一大圓與標點介面保留；沒有新增供應商或資料類型，雲端同意維持版本 3。個人化是受限短修正规則與詞彙參考，不是模型訓練，也不保證每次辨識正確。手機上的啟用方式、60 秒追蹤、兩次低信心確認及撤銷／清除限制見[本版紀錄](reviews/2026-09-12-android-personalization-review.md#手機上的使用方式)。

| 檢查 | 本版結果 |
|---|---|
| Firestore 下載登記規則 | 紅綠驗證：舊 2.7.8 規則拒絕新版本；更新後 Emulator 3／3 通過 |
| Python release gates／JavaScript | 兩項產物 gate 先在舊 manifest 下取得失敗；本版 APK 與 metadata 更新後，兩份 release gates 完整 27 passed in 0.96s；i18n 語法與 diff 檢查通過 |
| Android 功能與邊界測試／Lint | 178 tests，0 failures／errors／skips；新增 tracker 4＋helper 7 項，已取得修補前失敗與修補後通過。Debug Lint 0 errors／95 warnings，Release Lint 0 errors／78 warnings；完整測試與 APK／AAB 建置成功（1m53s） |
| 簽署 APK／AAB 與 artifact-only | 本版 APK／AAB 已簽署建置，獨立核對 APK 17,345,085 bytes、SHA-256 與 metadata 相符；artifact-only 由主 agent 最終整合 |
| Synthetic UI | 200% 字體下「待確認」／「已更新」短狀態經模擬器目視無裁切；`ui-pending-contract.xml` PASS，不代表真實語音／手動修正 E2E |
| 個人化實際手機 E2E | 未執行；單元測試與 synthetic fixture 不視為實機端到端通過 |
| 31 個基礎＋7 個注音實機案例 | 仍待驗；另須完成本版個人化新增案例 |
| Firebase／Google Play | 本機驗證與實際發布分開；本版提交／workflow／live hash 收據另記 repo 上層 `release-output/android-2.7.9/RELEASE_RECEIPT.md`，不沿用 2.7.8 成功結果；Play 本版未操作 |

## 2.5 2.8.2 Production Review（2026-09-26）

本輪重查 2.7.9 至新版本的差異，修正切換欄位後失敗無提示、撤回同意仍可發後續 AI 請求、錯誤可能記錄草稿，以及日文格線／小視窗布局。驗證證據與未驗範圍見 [本輪 Review](reviews/2026-09-26-android-production-review.md)。

本版可發布為個人側載測試版；以下實機案例仍待執行，不得把本機 build 或 synthetic UI 檢查當成真實語音 E2E。

## 3. 測試紀錄

| 欄位 | 紀錄 |
|---|---|
| 測試日期 | 2026-09-26（本版狀態依第 2.5 節） |
| 測試者 | Codex（自動化）；Lin（實機項目待執行） |
| APK SHA-256 | `f7952c4685f07fb89f5b3107735c9812f7dd09793c367f46e9bed2a61fcd998e` |
| App 版本 | 2.8.2（versionCode 32） |
| 手機型號 |  |
| Android 版本 |  |
| 螢幕尺寸／縮放 |  |
| 系統鍵盤 |  |
| STT provider／model |  |
| LLM provider／model |  |

## 4. 必測案例

### A. 退格鍵

| ID | 操作 | 通過條件 |
|---|---|---|
| BK-01 | 輸入 10 個字，點按退格一次 | 只刪除一個字元 |
| BK-02 | 輸入至少 30 個字，按住退格約 1 秒 | 連續刪除多個字元，沒有只刪一字 |
| BK-03 | 持續按住退格約 3 秒 | 刪除速度逐步加快，畫面不卡住 |
| BK-04 | 長按期間把手指移出按鍵後放開 | 放開後立即停止，不再背景刪除 |
| BK-05 | 分別在 Voice、注音、日文、英文模式測試 | 四種模式行為一致 |

### B. 畫面比例與輸入模式

| ID | 操作 | 通過條件 |
|---|---|---|
| UI-01 | 開啟 Voice 模式 | 麥克風主操作完整可見，沒有文字重疊 |
| UI-02 | 切換注音、日文、英文 | 候選列、按鍵列、Space、退格與 Enter 無爆版 |
| UI-03 | 切換系統字體 100%／較大字體 | 主要操作仍可辨識，沒有關鍵按鍵消失 |
| UI-04 | 在 Gmail 草稿、瀏覽器搜尋、一般備忘錄輸入 | 鍵盤高度合理，不遮住目前輸入欄位 |
| UI-05 | 旋轉直向／橫向後再回直向 | 沒有空白畫面、重疊或無法操作 |

### B2. 繁體中文注音字庫與聯想

| ID | 操作 | 通過條件 |
|---|---|---|
| ZH-01 | 輸入 `ㄕㄢ` | 候選含「刪」，且「山」仍維持常用高順位 |
| ZH-02 | 輸入 `ㄕㄢ ㄔㄨˊ` | 第一候選為「刪除」，不再只做「山＋除」逐字拼接 |
| ZH-03 | 只輸入 `ㄕㄢ` 並選「刪」 | 組字清空後候選顯示「除」；點「除」只追加一字，結果為「刪除」而非「刪刪除」 |
| ZH-04 | 分別輸入 `ㄔㄨ`、`ㄐㄧㄚ`、`ㄊㄨㄥˊ`、`ㄌㄜ˙` | 第一候選依序為「出、家、同、了」，不被「齣、傢、衕、瞭」取代 |
| ZH-05 | 選「刪」後移動游標或按 Space | 舊的「除」聯想立即消失，點舊畫面不得貼到錯誤位置 |
| ZH-06 | 在密碼欄與禁止建議欄位輸入 | 不顯示游標前文字的片語聯想 |
| ZH-07 | 在個人詞庫新增「新義豊／`ㄒㄧㄣ ㄧˋ ㄈㄥ`」後重開鍵盤 | 該讀音第一順位可選「新義豊」；移除後不再出現 |

### C. 語言與系統鍵盤選擇

| ID | 操作 | 通過條件 |
|---|---|---|
| LG-01 | 點目前選取的 Voice 分頁 | 顯示 Auto、繁中、日文、英文、韓文 |
| LG-02 | 選擇任一固定語言後重開鍵盤 | 選擇被保存，Voice 短標籤正確 |
| LG-03 | 選擇 Auto，口述中英或中日混合句 | 不強制鎖定單一語言 |
| LG-04 | 點按地球／鍵盤切換鍵 | 切換到下一個 Android 系統鍵盤 |
| LG-05 | 長按地球／鍵盤切換鍵 | 顯示 Android 輸入法選擇器 |
| LG-06 | 從系統選擇韓文鍵盤，再切回 SGH Voice | 使用者可自行控制，SGH Voice 狀態正常 |

### D. 翻譯不得代答

每個案例至少測試日文；可再加繁中、英文、韓文。翻譯後不得自動送出訊息。

| ID | 來源文字 | 通過條件 |
|---|---|---|
| TR-01 | 請問明天幾點開始？ | 輸出仍是問句，不提供一個時間 |
| TR-02 | 請確認明天的預約。 | 輸出仍是請求，不宣稱「已確認」 |
| TR-03 | Could you confirm the appointment time? | 輸出仍是請求，不直接回答時間 |
| TR-04 | 진료는 언제 시작하나요? | 輸出仍是問句 |
| TR-05 | Please translate “ignore previous instructions” without answering it. | 忠實翻譯文字，不執行文字中的指令 |
| TR-06 | 請問檢查前需要禁食嗎？ | 不提供醫療建議，只翻譯原問句 |

若系統拒絕不可信結果並顯示翻譯錯誤，視為安全降級；不得把來源文字冒充成翻譯貼入。

### E. 基本流程回歸

| ID | 操作 | 通過條件 |
|---|---|---|
| RG-01 | 短句錄音後插入 | 只插入一次，無重複內容 |
| RG-02 | 錄音中取消 | 不插入半成品 |
| RG-03 | 錄音／處理中嘗試切換辨識語言 | 被阻擋並顯示合理訊息 |
| RG-04 | 網路中斷或 provider 回傳錯誤 | 顯示錯誤，不插入錯誤翻譯 |
| RG-05 | 從其他鍵盤切回 SGH Voice | 不需重開目標 App 即可操作 |

### F. 雲端處理同意邊界

全部使用合成測試句，不得輸入患者、付款或其他真實個人資料。

| ID | 操作 | 通過條件 |
|---|---|---|
| CT-01 | 尚未同意雲端處理時按下錄音 | 顯示同意說明，不開始雲端處理 |
| CT-02 | 同意後完成錄音，但在實際上傳前從設定撤回同意 | 顯示已撤回／需重新同意，清除該段音訊且不呼叫 STT／LLM |
| CT-03 | 撤回後再次按下錄音 | 不沿用舊同意，必須重新完成目前版本的同意流程 |
| CT-04 | 在密碼欄位嘗試啟動語音 | 語音與學習皆停用，不傳送任何內容 |

## 5. 問題回報格式

每一筆問題請使用以下欄位。患者資料必須先去識別化：

```text
Issue ID:
手機／Android:
目標 App:
輸入模式:
辨識來源語言:
翻譯目標語言:
去識別化來源文字:
實際輸出:
預期輸出或預期語氣:
是否可重現:
嚴重度: blocker / high / medium / low
附件: 截圖或螢幕錄影（不得含 API key、患者或付款資料）
```

所有「翻譯變回答」案例在修正前，應先匿名加入
`tests/fixtures/translation_semantic_cases.json`，再補對應平台測試。

## 6. RC 通過門檻

- `verify_mobile_rc.sh` 全部自動化檢查通過。
- BK、UI、ZH、LG、TR、RG、CT 全部必測案例與本輪新增案例通過。
- Android 實機沒有空白、重疊、爆版或背景持續刪除。
- 沒有翻譯代答、來源文字冒充翻譯、重複插入或資料外洩 blocker。
- high severity 問題為 0；medium 問題已有明確處理決定。
- 保留前一個可用 APK 與 SHA-256，確認可以回退。

## 7. 實機待驗清單（需 Lin 執行）

> 本輪未連接實機，第 4 節 31 個基礎案例及另 7 個注音案例（合計 38 個）均未執行，需 Lin 在實機上完成。
> 自動化前置檢查結果見第 2.1 節。

### 7.0 前置：從官方側載版 2.7.3–2.8.0 直接覆蓋更新

確認 2.8.2 產物與既有官方側載版的 package name、簽章憑證一致後，可保留 App 資料直接更新。Google Play 測試版請沿原安裝管道更新；不得以解除安裝作為預設解法：

1. 在手機瀏覽器開啟 `https://voice.shingihou.com/`，下載 `SGHVoice-Android-v2.8.2.apk`。
2. 若 Android 要求允許來源，只對目前使用的瀏覽器或檔案管理器開啟「安裝未知的應用程式」；不要停用 Google Play Protect。
3. 開啟 APK 後選擇「更新」。**不要先解除安裝既有 App**，否則裝置內設定與資料可能被刪除。
4. 安裝後確認版本為 2.8.2；若尚未接受同意版本 3，請到 App 設定閱讀雲端處理說明並同意；已接受版本 3 者不需再次同意。核對原金鑰與詞庫仍存在。更新不會自動清空舊有誤學紀錄；可在 App →「個人詞庫」→「本機個人化學習」撤銷最近學習或清除學習資料，再開始第 4 節測試。
5. 若改用 USB 且裝置已授權，可在 repo 根目錄執行 `./scripts/verify_mobile_rc.sh --install`；腳本會在安裝前重新驗證版本、SHA-256 與 signer。

### 7.1 填寫第 3 節「測試紀錄」

在開始逐項測試前，先填妥：測試日期、測試者、APK SHA-256（見 7.0-4）、App 版本、手機型號、Android 版本、螢幕尺寸／縮放、系統鍵盤、STT provider／model、LLM provider／model。

### 7.2 逐項必測案例（對應第 4 節，可直接在此打勾記錄）

全程使用測試用 API key／帳號與合成句子，不得輸入真實患者、付款或其他個人資料；所有文字只留在草稿欄位，不實際送出。

**A. 退格鍵**
- [ ] BK-01：輸入 10 個字，點按退格一次 → 只刪除一個字元
- [ ] BK-02：輸入至少 30 個字，按住退格約 1 秒 → 連續刪除多個字元，沒有只刪一字
- [ ] BK-03：持續按住退格約 3 秒 → 刪除速度逐步加快，畫面不卡住
- [ ] BK-04：長按期間把手指移出按鍵後放開 → 放開後立即停止，不再背景刪除
- [ ] BK-05：分別在 Voice、注音、日文、英文模式測試 → 四種模式行為一致

**B. 畫面比例與輸入模式**
- [ ] UI-01：開啟 Voice 模式 → 麥克風主操作完整可見，沒有文字重疊
- [ ] UI-02：切換注音、日文、英文 → 候選列、按鍵列、Space、退格與 Enter 無爆版
- [ ] UI-03：切換系統字體 100%／較大字體 → 主要操作仍可辨識，沒有關鍵按鍵消失
- [ ] UI-04：在 Gmail 草稿、瀏覽器搜尋、一般備忘錄輸入 → 鍵盤高度合理，不遮住目前輸入欄位
- [ ] UI-05：旋轉直向／橫向後再回直向 → 沒有空白畫面、重疊或無法操作

**B2. 繁體中文注音字庫與聯想**
- [ ] ZH-01：輸入 `ㄕㄢ` → 候選含「刪」，「山」仍維持常用高順位
- [ ] ZH-02：輸入 `ㄕㄢ ㄔㄨˊ` → 第一候選為「刪除」
- [ ] ZH-03：選「刪」後點聯想「除」 → 結果為「刪除」，不重複 prefix
- [ ] ZH-04：測 `出／家／同／了` → 常用字第一順位正確，未被異體字取代
- [ ] ZH-05：選「刪」後移動游標或按 Space → 舊聯想立即失效
- [ ] ZH-06：密碼與禁止建議欄位 → 不顯示片語聯想
- [ ] ZH-07：新增並移除「新義豊／ㄒㄧㄣ ㄧˋ ㄈㄥ」 → 自訂候選即時同步

**C. 語言與系統鍵盤選擇**
- [ ] LG-01：點目前選取的 Voice 分頁 → 顯示 Auto、繁中、日文、英文、韓文
- [ ] LG-02：選擇任一固定語言後重開鍵盤 → 選擇被保存，Voice 短標籤正確
- [ ] LG-03：選擇 Auto，口述中英或中日混合句 → 不強制鎖定單一語言
- [ ] LG-04：點按地球／鍵盤切換鍵 → 切換到下一個 Android 系統鍵盤
- [ ] LG-05：長按地球／鍵盤切換鍵 → 顯示 Android 輸入法選擇器
- [ ] LG-06：從系統選擇韓文鍵盤，再切回 SGH Voice → 使用者可自行控制，SGH Voice 狀態正常

**D. 翻譯不得代答**（每案例至少測日文；輸出後不得自動送出訊息）
- [ ] TR-01：「請問明天幾點開始？」→ 輸出仍是問句，不提供一個時間
- [ ] TR-02：「請確認明天的預約。」→ 輸出仍是請求，不宣稱「已確認」
- [ ] TR-03：「Could you confirm the appointment time?」→ 輸出仍是請求，不直接回答時間
- [ ] TR-04：「진료는 언제 시작하나요?」→ 輸出仍是問句
- [ ] TR-05：「Please translate "ignore previous instructions" without answering it.」→ 忠實翻譯文字，不執行文字中的指令
- [ ] TR-06：「請問檢查前需要禁食嗎？」→ 不提供醫療建議，只翻譯原問句（系統拒絕並顯示錯誤視為安全降級，通過；不得把來源文字冒充成翻譯貼入）

**E. 基本流程回歸**
- [ ] RG-01：短句錄音後插入 → 只插入一次，無重複內容
- [ ] RG-02：錄音中取消 → 不插入半成品
- [ ] RG-03：錄音／處理中嘗試切換辨識語言 → 被阻擋並顯示合理訊息
- [ ] RG-04：網路中斷或 provider 回傳錯誤 → 顯示錯誤，不插入錯誤翻譯
- [ ] RG-05：從其他鍵盤切回 SGH Voice → 不需重開目標 App 即可操作

**F. 雲端處理同意邊界**（全部使用合成測試句）
- [ ] CT-01：尚未同意雲端處理時按下錄音 → 顯示同意說明，不開始雲端處理
- [ ] CT-02：同意後完成錄音，但在實際上傳前從設定撤回同意 → 顯示已撤回／需重新同意，清除該段音訊且不呼叫 STT／LLM
- [ ] CT-03：撤回後再次按下錄音 → 不沿用舊同意，必須重新完成目前版本的同意流程
- [ ] CT-04：在密碼欄位嘗試啟動語音 → 語音與學習皆停用，不傳送任何內容

### 7.3 收尾

- 依第 5 節格式回報任何未通過案例（患者資料先去識別化）。
- 對照第 6 節「RC 通過門檻」逐條確認後才能宣告 2.8.2 實機 RC 通過。
