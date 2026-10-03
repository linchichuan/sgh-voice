# Android 2.8.7：詞彙記憶與保守整理修復

本文件續接同日先前 2.8.7 候選紀錄。先前 322／401 個測試與 APK 雜湊只代表當時的候選產物，不代表目前這包修改。

## 使用者確認的產品原則

不確定的內容改動不自動套用、保留原文；包含單字修改。這不是「只限制兩字以上」：買／賣、沒有稱謂的姓名、否定所作用的句子都可能只差一個字。標點、段落、明確列點、明確改口及可驗證的拼字修正仍可整理。首次遇到的錯字、同義詞／文法改寫會較常退回原文。

## 修復範圍

- `LlmClient` 在既有數量、識別碼、姓名、否定檢查後，要求比較用的內容 token 序列一致，不再把字元相似率當成通過的充分條件。英文字邊界也保留。Prompt 同步要求不猜同音字或改寫實質內容。
- `DictationAlignment` 移除模糊的編輯距離／子音骨架推測，只接受確認別名、大小寫或有限的精確外來語寫法。既有資料庫→GitHub 等反例繼續拒絕。
- 以逐碼點繁簡比較避免新增逗號造成 OpenCC 詞組判斷差異；這是比較用正規化，不是聲稱 OpenCC 全面的語意問題已解決。
- `VoiceCorrectionLearning` 保留安全、短而完整的 CJK 提示；`PersonalizationRepository.getPromptWords` 對既存 ACTIVE 規則重新推導，解決診聊所→診療所顯示生效但提示為空。
- `DictionaryManager` 不再直接替換任何 learned Han／kana；CJK→CJK 僅供 STT 提示，不進 AI 別名與詞彙提示。手動建立的規則保留既有行為，不宣稱它們也完全避免部分替換。
- 獨立 Spec 驗收另找到 CJK→Latin 別名旁路，正式反例包含バスケット／可樂餅／バス停。現在 alignment 與最終 alias fallback 共用完整 CJK 邊界檢查，Han／hiragana／katakana 的 script 切換也不算分詞證據。有引號、空白等明確分隔的確認別名仍可用；連寫中文／日文（包含コトリンで）不推定詞界，只保留 STT 提示，未引入斷詞服務或偷偷恢復模糊比對。
- 獨立 Standards 驗收另找到 v1 migration 自動啟用 pending；現保留 legacy.active，缺失欄位預設 false。新增 migration 與 reload 的 STT／LLM／alias／literal 四路反例。

## 刻意變更的既有測試期望

- 先前要求新義豊公司／𠮷野全提示為空的測試改為完整短詞；周邊句子內容仍不得帶入。
- 先前期待純假名字面替換的測試改為 STT-only。
- `I has`→`I have`、刪掉有可能帶語意的「那個／就是」、然後→接著等未確認改寫改為拒絕；不是放寬反例。AI 文字不算人工修正的閉環改用允許的コトリン→Kotlin，保留原同義詞案例為拒絕測試。
- 先前期待已知中文／假名別名在連寫文章中自動修正的 positive fixtures 改用明確分隔；另外保留無邊界案例為 REJECTED。這是使用者核准之不確定不套用政策，不是辨識品質改善的證明。

## 驗證方式與邊界

沿用 public refinement 與 repository→dictionary／pipeline 的合成測試。HTTP 回覆與持久化介面為合成資料；實際 request／parse／guard／學習模組執行，沒有呼叫付費 API、讀出 key 或上傳真實錄音。原守門 8 探針修前 5 項失敗；新學中文提示、舊資料重載、假名部分替換皆先確認失敗再修。

最終 `testDebugUnitTest lintDebug assembleDebug` 通過：422 tests，0 failures/errors/skipped；Debug Lint 0 errors / 114 warnings（不宣稱零警告）。另以 repo 外的原獨立探針及 Spec reviewer 新探針跑 13 項，0 failures/errors。未完成實機／真實供應商準確率測試；STT 提示有帶入不等於下次辨識一定正確。

`build_android_sideload_release.sh` 執行上述 13 探針、`lintRelease assembleRelease` 成功；Release Lint 0 errors / 96 warnings。APK v2 簽章驗證成功，單一 signer 與最後公開 2.8.6 相同，package `com.shingihou.sghvoice`、versionName 2.8.7、versionCode 37。最新本機產物在 repo 上層 `release-output/android-2.8.7-safe-20261003/SGHVoice-Android-v2.8.7.apk`，17,581,752 bytes；SHA-256 `8f1f8ab2a4fea1c27a7bcc7b7826bf64e3b7274222ef8339fca0fbd56229f7dc`。同目錄 `voice-recording.png` 是本次實際 KeyboardView 測試渲染，非手機截圖。

公開舊 release 的 `verify_mobile_rc.sh --artifact-only` 另行通過；此結果只確認公開舊產物仍完整，並不代表新 APK 已上線。暫存區常見私鑰／token 特徵掃描 0 命中，非完整安全稽核。

若曾自行安裝過有問題的未發布候選版並已執行 v1→v2 migration，原 pending 狀態未留存，無法可靠追溯還原；請在詞彙設定人工核對或停用個人化。不能無依據將所有 v2 詞降級。正常從最後公開 2.8.6 升級則會走修正後 migration。

## Standards

獨立驗收所提 1 項 P1（pending migration）已修復並由 reviewer 唯讀複驗關閉，主 agent 跑測試確認。CJK 判定重複為非阻擋的維護性建議；本輪不做額外跨模組重構。無未解阻擋項。

## Spec

原三個根因及獨立 reviewer 找出的 CJK→Latin 邊界／fallback 旁路已修復。Reviewer 最終唯讀確認目前已識別的 blocker 關閉，main 重跑原／新反例全過。無未解阻擋項；不把有限測試解讀為所有語意變動或真實辨識都已獲保證。

Agent Team：worker 修詞彙與 migration；兩位獨立 reviewer 分別檢查 Standards／Spec；主 agent 修內容守門、執行測試與建置、整合提交範圍。

## 發布分界

本輪授權修復、驗收、Commit、Push main。公開網站 APK／下載 manifest 不變，Google Play 不變；UI 仍須先讓使用者看過再上傳新版 APK。Push 會觸發既有 CI 與其後的 Firebase workflow，不能將 source push 等同新版 APK 已發布。

不提交 unrelated `build.sh`、舊版未追蹤 APK 或任何 keystore／secret。Android 與既有同日相關文件按範圍提交；保留工作區其他修改。
