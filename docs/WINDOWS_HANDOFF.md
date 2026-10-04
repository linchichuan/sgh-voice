# SGH Voice Windows 原始碼交付 — 2026-10-04

## 交付狀態

| 項目 | 狀態 | 證據／限制 |
|---|---|---|
| Windows 原始碼與建置流程 | PASS | 獨立 `codex/windows-native` 分支，基於 public main `e096d3c977d9b9cdc98c17639ceaf6e39ebc5822` |
| Mac 上單元／整合測試 | PASS | 755 tests + 28 subtests，11.95 秒；不代表 Windows 驗收 |
| 獨立原始碼審查 | PASS | reviewer 自行執行 Windows subset：124 tests + 28 subtests，無剩餘原始碼交付 blocker |
| 真正 Windows 建置／installer.exe | BLOCKED / NOT RUN | 尚無可用且已授權的 Windows builder；本次沒有 EXE |
| Windows 安裝／錄音／快捷鍵／貼字 | NOT VERIFIED | 需要互動 Windows 桌面與麥克風，CI smoke 不能替代 |
| 公開網站與 binary 發布 | NOT DONE | 未 push main，未 dispatch，未 deploy；Windows manifest 為 pending |

原始 checkout `/Volumes/Satechi_SSD/voice-input/source` 保留在 Android 分支，
既有 `build.sh` dirty 與兩個未追蹤 APK 不納入本工作。未更動 JEV 研究環境，
亦未混入 Android 2.8.9 未發布改動。交付前再次查詢 main，仍是上述 SHA。

## 已實作的流程

- `windows_launcher.py` + `windows_client/ui.py`：原生桌面 Tk/ttk 三語介面（繁中／日文／英文）、設定、真實音量、錄音狀態、結果預覽與明確複製。
- `windows_client/controller.py`：共用現有 Recorder / Transcriber / Memory；一次一段錄音、取消／關閉清理、3 分鐘錄音上限、供應商隔離。
- 首次啟動不送雲端；使用者須選 Groq 或 OpenAI、儲存自己的既有 API key 並明確同意。整理可關閉；雲端請求沿現有 provider／預算守門，不自動啟用跨 provider fallback。沒有在此工作呼叫付費 API。
- Windows 不提供 MLX／Breeze／Qwen MLX 離線辨識。若不啟用雲端，拒絕開始辨識，不能稱為 Windows 完整離線醫療方案。
- 預設不儲存 transcript history，不自動貼字、不收集視窗內容。勾選自動輸入後，快捷鍵啟動時記錄目標視窗與焦點，完成時再次核對。焦點改變／不支援內容／送字失敗皆保留預覽；不自動覆蓋剪貼簿或重試部分輸入。
- Win32 Unicode SendInput 支援 UTF-16；成功表示事件提交，不能保證目標程式接受文字。瀏覽器自訂密碼欄無法可靠辨識；自動輸入維持 opt-in，正式驗收需檢查 IME／Notepad／瀏覽器。
- 明確按 Copy 才修改剪貼簿，設定 Windows history／cloud exclusions；這不是防止所有第三方剪貼簿軟體讀取的保證。
- 預設快捷鍵為 `Ctrl+Alt+F9`（錄音／停止）與 `Ctrl+Alt+F10`（取消），可修改，衝突會回報。
- Windows 設定使用 `%LOCALAPPDATA%\SGHVoice`；金鑰只接受 Windows Credential Manager，失敗即拒絕明文保存。

## 建置與下載頁準備

`windows/build.ps1`、`windows/sghvoice.spec`、`windows/installer.iss` 準備每使用者、
無需系統管理員的 x64 unsigned installer；尚未執行。已固定 42 項依賴與 SHA256，
以官方 metadata 核對 Windows CPython 3.12 wheel／依賴閉包，未安裝。

`.github/workflows/windows-build.yml` 只有 workflow_dispatch，一個標準 windows-2022
job、25 分鐘 timeout、一天 artifact retention，不發 Release、不部署網站。

網站新增待驗收 Windows 卡片；只有真實安裝檔、SHA256、建置與綁定該 binary 的
Windows 驗收紀錄均通過，才能切為 available。現有 Mac／Android 登記與下載行為保留。

## 執行過的驗證

```sh
SGHVOICE_DATA_DIR=/tmp/sghvoice-windows-delivery-suite \
  /Volumes/Satechi_SSD/voice-input/source/venv-build312/bin/python \
  -m pytest tests/ -o addopts= -q
# 755 passed, 28 subtests passed in 11.95s

/Volumes/Satechi_SSD/voice-input/source/venv-build312/bin/python \
  -m ruff check . --select E9,F63,F7,F82
# All checks passed!

node --check sgh-voice-web/windows-download.js
node --check sgh-voice-web/i18n.js
git diff --check
# all exit 0
```

既有網站 Node recruitment-flow 9/9 通過。已用本機 Chrome 確認 Windows 待驗收卡片
與停用按鈕；未提交 Firebase 表單。上述全部是 Mac／mock／瀏覽器驗證，沒有 Windows
runtime 證據。

獨立審查發現並已修正：重建 Recorder 繞過舊串流 guard、關閉視窗過早退出留下 WAV、
Windows UTF-8 預設編碼、文件建立的 `.venv-windows/` 觸發 dirty build gate。

## 下一個必要介入

目前 GitHub self-hosted runner 數為 0，本機 Parallels `Windows 11` VM 為 invalid，
未啟動、修復或購買環境。Mac 的 PyInstaller 不支援直接建 Windows 安裝檔。

最短可行選項：核准一個標準 GitHub Windows 單次建置，並安排實際 Windows 測試者。
新手動 workflow 必須先透過受審查的流程進入 default branch 才可 dispatch；不能為此
直接推送完整未驗收 Windows 功能到 main。公開 repository 標準 runner 運算按官方
現行規則免費，但帳號 artifact 儲存額度／費用未審計，不承諾總費用為零。
另一選項是指定已有授權且可用的 Windows 機；修復 VM、新增軟體／環境／簽章均需先回報。

Windows 安裝、錄音、語系、整理、快捷鍵、焦點變動、剪貼簿、重新啟動與解除安裝的
逐項檢查見 [WINDOWS_BUILD.md](WINDOWS_BUILD.md)。unsigned build 不可要求使用者關閉
SmartScreen／Defender；若系統阻擋，記錄 BLOCKED。

正式上線範圍僅限：驗收通過的版本化 Windows installer + SHA256／manifest + 三語
下載入口。沒有 Android 發布、Mac 安裝檔替換、JEV 變更或憑證修改。
