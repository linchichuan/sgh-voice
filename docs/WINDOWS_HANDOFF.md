# SGH Voice Windows 離線版交接 — 2026-10-04

## 當前交付狀態

| 項目 | 狀態 | 證據／限制 |
|---|---|---|
| Windows 離線原始碼 | IN PROGRESS | 在獨立 `codex/windows-native` 分支整合；新版本的審查與 source SHA 尚待完成 |
| 舊版原始碼測試 | HISTORICAL PASS | 下方 755 tests／124 tests 數字屬於加入離線功能前的版本，不能當作本版通過證明 |
| 新版本測試／獨立審查 | PENDING | 需對最後固定的 source SHA 補上真實結果 |
| 本機模型推論／合成靜音測試 | NOT RUN | 正在加入，尚無本版實際推論通過證據 |
| Windows 建置／installer.exe | NOT RUN | 尚未有真正 Windows EXE；已有單次標準 runner＋Release 草稿的可行路徑 |
| Windows 安裝／解除安裝自動測試 | NOT RUN | `windows/install-test.ps1` 已準備，未在 Windows 執行 |
| 真實錄音／快捷鍵／目標貼字 | NOT VERIFIED | 需要互動 Windows 桌面與實體麥克風；CI／Mac 測試不能替代 |
| 公開網站穩定版下載 | PENDING | Windows manifest 維持 pending，尚未發布 Windows binary |
| Windows 測試 prerelease | NOT PUBLISHED | 需實際建置與有限自動檢查通過、下載核對後，才可標示限制供測試 |

先前基線為 public main `e096d3c977d9b9cdc98c17639ceaf6e39ebc5822`；先前 Windows
cloud-client 提交為 `761a73cc0f200e1b3481c7962b280013f5bc27f6`。後者不包含本次
離線改動，不可拿來填新 installer 的 source SHA。新 SHA 應在整合與審查完成後記錄。

原始 checkout `/Volumes/Satechi_SSD/voice-input/source` 的 Android 分支、既有
`build.sh` dirty 與未追蹤 APK 不納入本工作；JEV 研究 worktree 及 Android 2.8.9
未發布改動不在 Windows 交付範圍。

## 新的 Windows 行為

- 原生 Tk/ttk 繁中／日文／英文桌面介面：設定、音量、錄音狀態、結果預覽、人工編輯及明確複製。
- `windows_client/local_stt.py` 使用 faster-whisper／CTranslate2，在本機 CPU 以 int8 執行。Windows 路徑不要求 API key、不呼叫雲端辨識，也不在模型失敗時切換雲端。
- 此預覽版停用雲端 LLM 整理與翻譯，保留辨識原文供人工覆核；不把詞彙提示當成自動改寫。
- `windows_client/controller.py` 共用錄音與設定能力，一次處理一段錄音，保留取消、關閉清理與 3 分鐘錄音上限。舊雲端設定不得重新啟用 provider fallback。
- 預設不儲存 transcript history、不自動貼字、不讀取視窗內容。自動輸入須 opt-in；快捷鍵開始時記錄目標與焦點，完成時核對。焦點變動、目標關閉或送字失敗時保留預覽。
- Win32 Unicode SendInput 成功僅代表事件提交，不保證目標接受。IME、瀏覽器自訂欄位與密碼欄需實機檢查；不得以更高權限突破 Windows 輸入邊界。
- 明確按 Copy 才修改剪貼簿，設定 history／cloud exclusions；這不是阻止所有第三方剪貼簿工具讀取的保證。
- 快捷鍵預設 `Ctrl+Alt+F9` 錄音／停止、`Ctrl+Alt+F10` 取消；設定與模型存於 `%LOCALAPPDATA%\SGHVoice`。本版不需要新增雲端帳號或 credential。

以上描述目前原始碼的意圖與路徑；新版本測試和實際 Windows 行為仍須分別取得證據。

## 模型、硬體與隱私界線

模型為 [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base)，
來源是 OpenAI Whisper base multilingual 的 CTranslate2 轉換；授權 MIT。
固定 revision：
[`ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`](https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66)。
`resources/windows/model-base-v1.json` 記錄四個必要檔的 size／SHA256，總計
**147,882,941 bytes，約 148 MB**。來源權重為 FP16，程式載入時使用 CPU int8。

Installer 不內含模型權重。使用者可以選擇已準備的本機模型目錄，或在介面確認來源、
容量後明確按下載。啟動與錄音不會自行下載；setup 只向 Hugging Face 下載公開模型，
不需帳號／token，不上傳音訊或逐字稿。大小與 SHA256 全部核對後才啟用；下載失敗、
取消或模型不完整都回報錯誤，不退回雲端。模型準備完成後，錄音辨識在本機執行。

目標為 Windows x64，CPU 至少支援 **SSE 4.1**，依
[CTranslate2 官方硬體要求](https://opennmt.net/CTranslate2/hardware_support.html)。
**建議 8 GB RAM、至少 1 GB 磁碟餘量，是工程規劃建議，並非已實測最低需求**；仍須容納
最終程式、模型暫存及錄音。CPU、記憶體與音長會影響耗時，不保證即時速度。
不要求 GPU／CUDA。乾淨 Windows 環境尚須檢查 Visual C++ runtime 等相依性；若缺少應
先回報，不能靜默加裝。見 [官方安裝要求](https://opennmt.net/CTranslate2/installation.html)。

可選的本機日文精神科 lexicon 僅顯示有來源的拼寫候選，不自動替換逐字稿、不判定
臨床意義。**詞彙表存在不等於辨識準確率提升已有證據**。醫療抄錄需由人員核對原始
語音，尤其精確藥名、劑量、單位與否定語意；逐字稿和候選提示不是醫療建議。

## 零額外費用的建置與測試版交付路徑

目前沒有可用本機 Windows builder：GitHub self-hosted runner 數為 0，Parallels
Windows 11 VM 為 invalid。Mac PyInstaller 不能替代真正 Windows 建置；不自動修復
VM、購買環境或新增 credential。

[GitHub 官方計費規則](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
明載 public repo 標準 runner 免費。推薦限制為一個 `windows-2022` job、25 分鐘、
無 matrix、無 Actions artifact／cache／snapshot upload。既有授權看不到帳戶整體
artifact 用量；不以未知額度作為零費用保證。

改用既有 repo 的 Release 資產功能：[GitHub Free 公開 repo 完整功能](https://docs.github.com/en/get-started/learning-about-github/githubs-plans#github-free-for-personal-accounts)
及 [Release 配額](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas)
支持此交付方式。單檔須小於 2 GiB，每版最多 1000 個，總容量／頻寬不限；官方未另列
Release 資產費率。零增額費用評估依這些公開規則，不是帳單實測，也不涵蓋其他既有支出。

預定順序，**目前均未執行**：

1. 完成新離線 source 的測試／獨立審查並固定 SHA，先推不觸發 job 的功能分支。
2. 用本機已有授權建立指定 SHA 的 unpublished draft prerelease，不變更 main。
3. 推精確分支的一次性 workflow，checkout 固定 SHA，執行 Windows tests、打包、frozen self-test、模型離線推論／合成靜音、安裝與解除安裝測試。
4. 全部有限檢查通過才用 runner 的 ephemeral GITHUB_TOKEN 上傳明確列出的 EXE、hash manifest 與測試報告至既有草稿。不新增 credential，不把本機 token 傳到 runner，不覆寫其他資產。
5. 本機下載核對 SHA256／source SHA／報告，再發布 unsigned test prerelease，`make_latest=false`，明示實體麥克風與完整 Windows 桌面未驗收。

新 `workflow_dispatch` 必須存在 default branch 才能 dispatch；精確 feature-branch
`push` 觸發可避免先修改 main。manual workflow 已移除 artifact upload，並加入離線
推論及安裝／解除安裝步驟；本次下載交付使用另一個一次性 Release-only workflow。

本 source 修改 workflow，依 [Release API 權限](https://docs.github.com/en/rest/releases/releases#create-a-release)，
草稿建立及最後發布由本機已具 workflow scope 的授權完成；runner 的 `contents: write`
GITHUB_TOKEN 僅上傳到既有草稿，不能藉此增加 workflow 權限。詳細順序與 gate 見
[WINDOWS_BUILD.md](WINDOWS_BUILD.md)。

## 驗證證據要分開記錄

先前提交 `761a73cc0f200e1b3481c7962b280013f5bc27f6` 的歷史紀錄：Mac suite 755 tests
與 28 subtests 通過；獨立 reviewer 的 Windows source subset 124 tests 與 28 subtests
通過；Ruff、Node syntax 與 diff whitespace 檢查通過。這些是加入離線功能前的來源測試，
**不是新版本、新依賴、模型推論或 Windows runtime 的通過證明**。新版結果應補上執行
命令、source SHA、平台、日期與實際摘要，不沿用舊數字。

正在加入的本機模型推論和合成靜音檢查需記錄模型 revision、合成樣本與斷網條件。
合成靜音測試通過也不能證明真實語音準確率或醫療詞彙正確性。Windows installer smoke
將確認安裝檔位元組、捷徑、per-user registry、已安裝程式自測與卸載；runner 若是管理員，
必須明示未測 standard-user 權限。Windows Server runner 不等於 Windows 11 實體桌面驗收。

穩定網站下載仍需 exact installer 的安裝、實體錄音、快捷鍵、目標貼字、剪貼簿、隱私與
卸載驗收紀錄，綁定 installer SHA256 和 source SHA；其完成前 manifest 保持 pending。
測試 prerelease 只供有限測試，不自動開啟主網站 available 狀態。unsigned 程式若被
SmartScreen／Defender 阻擋，記錄 BLOCKED；不得要求使用者關閉安全機制。

尚未有 EXE、模型推論通過或已發布可下載連結可交付。下一步是完成離線 source 與 pipeline
審查並實際執行上述單次建置；不要求使用者先提供 Windows 機才能產出測試 installer。
正式網站發布範圍仍只限通過其驗收的 Windows installer／hash／入口，不包含 Android
發布、Mac 安裝檔替換、JEV 變更或簽章憑證修改。
