# Android 2.7.9 個人化修正追蹤

日期：2026-09-12

版本：2.7.9（versionCode 29）

狀態：修補、Android 功能測試與簽署建置已在本機驗證；實際發布收據另行記錄，真實手機 E2E 與 Google Play 提交未執行。

## 1. 本版問題與修補

| 問題 | 處理範圍 | 限制 |
|---|---|---|
| 先刪除錯詞，再補入修正版時可能漏記 | 保留符合既有時間與欄位條件的修正追蹤，讓刪除後輸入的短修正可被捕捉 | 單純刪除不是學習；逾時、換欄位或不安全上下文不能直接視為已確認修正 |
| 英文修正差異只剩零碎字元，提示缺少完整詞 | 以完整英文詞作為詞彙參考，並檢查修正匹配邊界；包含中文前後文包圍英文詞的案例 | 不把任何子字串都替換，亦不將相鄰中文整段納入英文詞提示；自動學習仍受時間、定位與確認門檻限制 |
| 學習說明容易讓人以為沒有任何文字落盤 | 說明學習使用受限短修正规則，片段仍可能含個人內容，可撤銷或清除 | 音訊不作為個人化學習資料；這不是重新訓練 STT／LLM 模型 |

2.7.8 的單一淺綠錄音圓、圓內波紋與「、」「，」「。」保持不變。本版沒有新增供應商、資料類型或雲端處理流程；同意版本維持 3，既有版本 3 同意仍有效。不宣稱個人化可以保證辨識率或讓每一次輸出完全正確。

## 2. 個人化能力與邊界

- 已確認的短修正可用作本機修正规則，其正確詞彙可以加入所選 STT／AI 的提示；完整修正紀錄與候選頻率不因此上傳。
- 語音／AI 的原始輸出不會自動成為人工確認的詞；必須符合既有修正追蹤與安全規則。
- 短片段可能本身是一句短句或含個人內容，不能說成「完全不保存任何句子」。Android 不建立完整聽寫歷史檔案，與保存受限短修正规則是不同層次。
- 可撤銷最近一次學習、清除全部本機個人化資料或停用個人化；敏感欄位限制維持既有行為。目前沒有逐筆學習紀錄管理介面或自動到期機制（TTL）。
- 本次自動化與 synthetic 測試不等同真實手機麥克風、雲端辨識、手動修改與後續輸入的完整 E2E 驗證。

### 手機上的使用方式

1. 開啟 App →「個人詞庫」→「本機個人化學習」，確認已開啟；預設為開啟。已同意雲端說明版本 3 的使用者不需重新同意。
2. 語音輸出後，在同一輸入欄位、60 秒內做短範圍修正。先刪除再補字不會延長原本的 60 秒追蹤時間；只刪除、不補字不會當成可套用的修正规則。
3. 看到「已記下修正，待確認」時，代表只記錄到證據，尚未啟用；低信心的相同錯字／正字配對須記錄兩次，才會出現「已更新個人詞庫」。這裡的高／低信心指定位是否可靠，不代表語意一定正確。現行輸入框快照未提供已驗證的文件結尾旗標，常見整欄口述可能走低信心路徑，不能承諾每次改字必定學習。
4. 若要立即明確設定 GitHub Actions、CI/CD、git push 等常用詞，可在詞庫管理手動新增常用詞或錯誤修正规則，不必等待自動學習累積。個人化啟用且已同意雲端處理時，確認詞可作為所選 STT／AI 的提示；完整學習紀錄與候選頻率留在本機。
5. 可查看已學習的候選／啟用修正數量，並使用「撤銷最近學習」或「清除學習資料」。這不是逐筆瀏覽／刪除清單；清除自動學習資料不刪除手動詞庫。更新不會自動清空舊有誤學紀錄；若舊規則仍造成錯誤，可撤銷最近一次或自行清除學習資料。

## 3. 驗證與發布狀態

| 項目 | 本版證據 |
|---|---|
| 2.7.8 既有公開版 | 已完成 Firebase Rules／Hosting [34668475395](https://github.com/linchichuan/sgh-voice/actions/runs/34668475395)；live APK bytes／hash／`cmp` 通過，原 APK 不覆寫 |
| Firestore 2.7.9 下載登記 | 既有公開 client 測試先更新新版本：舊規則 1 fail／2 pass；更新規則後 Emulator 3／3 pass |
| 2.7.9 公開產物 gates | 預期版號先改為 2.7.9／29，在舊 manifest 下取得 2 項失敗；實際 APK 與 metadata 更新後，兩份 release gates 完整重跑 27 passed in 0.96s |
| Android 修正追蹤／詞彙提示測試、Lint | 完整 178 tests，0 failures／errors／skips；新增 11 項（tracker 4、helper 7）。Debug Lint 0 errors／95 warnings，Release Lint 0 errors／78 warnings；完整 test／lint／Debug APK／Release APK／AAB 建置成功（1m53s） |
| Android 修補紅綠證據 | tracker 首輪 9 tests／1 fail 後轉綠；helper 首輪 13 tests／1 fail 後轉綠。第二個英文完整詞案例曾取得 expected `Orbit`、actual `使用Orbit進行` 的失敗，修正後納入最終 178 項全綠 |
| 網站／Python／diff | 全部 Python 535 passed（5.65s）；Ruff、三份 JavaScript syntax、`git diff --check` 通過，production npm audit 0 vulnerabilities |
| Synthetic UI | 主 agent 檢查模擬器 200% 字體的「待確認」／「已更新」短狀態，無裁切；`ui-pending-contract.xml` PASS。合成狀態展示不是實際語音／手動修正 E2E |
| 簽署 APK／AAB、artifact-only | APK `ARTIFACT VERIFIED`，版號、大小、hash、APK v2 簽章與既有 signer 一致。AAB `jarsigner` verified，仍有自簽鏈／無 timestamp／JarFile 與 JarInputStream manifest-order 警告，不等同 Play 接收成功 |
| 真實手機 E2E／RC | 未執行；31 個基礎＋7 個注音案例及本版新增個人化案例仍待驗 |
| 2.7.9 Firebase／Google Play | 發布另核對同一提交、CI、workflow 與 live hash；Google Play 本版未操作 |

2.7.8 的功能及 UI 證據另見 [單一圓形錄音紀錄](2026-09-12-android-single-circle-review.md)；其成功部署不代表 2.7.9 已發布。

## 4. 本版手機驗收案例

以下只用合成詞彙，結果留在草稿，不對外發送。實測後刪除新增的測試學習規則。

- [ ] LEARN-01：轉錄後選定一個測試詞，先刪除再輸入修正版；符合條件時能記錄短修正，不在刪除途中把空字串學成結果。
- [ ] LEARN-02：對一個合成英文詞做中間字母修正，檢查後續提示使用完整詞而非孤立差異字母；其他較長單字中的相同片段不被無關替換。
- [ ] LEARN-03：只刪除、不補字，或超過追蹤條件後另輸入文字，不新增錯誤學習。
- [ ] LEARN-04：撤銷最近一次學習或清除本機個人化後，檢查狀態及啟用修正數量是否回復，原測試修正不再影響後續輸入；禁個人化欄位不使用已學習詞。
- [ ] LEARN-05：用非敏感的人造人名做短修正，檢查「待確認」／「已更新」狀態及啟用數量，並以撤銷最近一次或清除全部移除測試學習；使用者理解短片段仍可能含個人內容，沒有逐筆瀏覽／刪除介面。
- [ ] UI-08：2.7.8 的單一大圓操作、標點「、」「，」「。」及長按翻譯沒有回歸。

## 5. 網站文案只讀檢查

- `index.html` 與三語 `learning.local.desc` 已明示確認詞可送往所選 STT／AI；沒有找到 Android「純本機、不傳任何詞彙」的明確主張。
- `privacy.html` 的日／中／英第 2.3 節區分本機保存完整修正與發送正確詞提示；第 2.4 節說明不建立完整 Android 發話歷史。這不等於禁止保存任何完整短句。
- 「學習資料留在手機」類標題需配合其下的雲端詞彙提示說明閱讀，不能延伸成所有文字都不會離開手機。
- 只修正首頁 `learning.safe.desc` 靜態 fallback，與三語文案及實作一致：密碼欄停用語音與學習，禁止個人化欄只停用學習。未擴大修改隱私政策。

## 6. 產物

- APK：`https://voice.shingihou.com/downloads/SGHVoice-Android-v2.7.9.apk`
- APK SHA-256：`62292210cdcbb7e75b2a8148b24245dc578f91f491f3d626fbe0c5d86fefbe3d`。
- APK 大小：17,345,085 bytes（16.54 MiB）。
- Manifest：`sgh-voice-web/downloads/android-release.json`，由主 agent 依實際產物更新。
- AAB：`release-output/android-2.7.9/SGHVoice-Android-v2.7.9.aab`（repo 上層）；SHA-256 `29054de857e1121f94517c181c82ac66b86ffaa3295a9746724a1bb8db51d08c`。
- Git／CI／Firebase／live APK 發布收據：`release-output/android-2.7.9/RELEASE_RECEIPT.md`（repo 上層，由主 agent 完成發布後記錄）；不得沿用 2.7.8 版本或 hash。

已安裝官方側載版者，在 package name 與 signer 核對一致後直接覆蓋更新，不先解除安裝。Google Play 安裝版沿原管道更新。所有舊版 immutable APK 保留原內容。
