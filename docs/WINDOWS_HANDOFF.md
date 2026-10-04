# SGH Voice Windows 離線測試版交接 — 2026-10-04

## 已交付與剩餘範圍

[下載 Windows x64 測試安裝檔](https://github.com/linchichuan/sgh-voice/releases/download/windows-offline-preview-20261004/SGHVoice-Windows-2.7.5-x64-unsigned.exe)
／[版本說明及驗證報告](https://github.com/linchichuan/sgh-voice/releases/tag/windows-offline-preview-20261004)。
這是真正的 Windows unsigned installer，標記 prerelease，不取代既有正式版。

| 項目 | 狀態 | 證據／限制 |
|---|---|---|
| Windows 本機辨識原始碼 | PUSHED | 獨立 `codex/windows-native`；建置固定 source SHA 見下方 |
| 真正 Windows 建置 | PASS | Windows Server 2022 x64、Python 3.12.10；239 tests、65 subtests 與 Ruff 通過 |
| 安裝／已安裝 EXE／解除安裝 | PASS | 全部檔案 hash、HKCU registration、捷徑、已安裝程式自測、清理及外部測試資料保留通過 |
| 本機 CPU 推論 | PASS, LIMITED | 合成靜音，Python socket guard 開啟且攔截嘗試數為 0；非完整 OS 網路監測或語音品質測試 |
| 公開 Windows 測試版 | PUBLISHED | Release 非草稿且為 prerelease；未登入 Range GET 回應 206、總長度與 MZ header 相符 |
| Windows 10/11 真實桌面驗收 | NOT VERIFIED | 實體麥克風、一般使用者安裝、快捷鍵、目標貼字與臨床準確率尚未驗證 |
| 自家下載頁 | NOT DEPLOYED | Firebase 本機登入失效，現有方案及共用額度尚未確認；不更動認證或假設可免費部署 |
| 正式 Windows 下載狀態 | PENDING | 網站 manifest 維持 pending；公開測試版不等於正式版驗收 |

## 固定交付身分

- Installer：`SGHVoice-Windows-2.7.5-x64-unsigned.exe`
- 大小：**43,648,095 bytes**（約 44 MB）
- SHA-256：`67f4f3f2c14ecccaf4c7d151641a27b9486b88f2ccf5a0ec0941b62a26795b3d`
- 建置來源：`4750f47dbb86efd11db77292f8f03d10a8068b2d`
- Release tag：`windows-offline-preview-20261004`
- [成功 Windows run 37202178595](https://github.com/linchichuan/sgh-voice/actions/runs/37202178595)，Windows job 耗時 2 分 38 秒。
- 建置 workflow 分支：`codex/windows-build-offline-20261004-r2`，commit `f8257e8ac8d82a231984dee849dafbe5a9ba79e7`；checkout 上述固定 source。

完整安裝檔下載後核對 SHA-256，與 GitHub asset digest 及 `windows-build.json` 相同。
同版附上 `windows-smoke.json`、`windows-installed-smoke.json`、
`windows-install-test.json`、`windows-offline-test.json` 與第三方授權聲明。
報告中 `published: false` 是建置當時的狀態；它們保留原始內容，後續發布狀態以 Release 為準。
本文件更新不改變 installer 的 source 身分。

## 現有功能與本機執行範圍

- 原生 Tk/ttk 繁中／日文／英文介面，錄音、音量、取消、結果預覽、人工編輯、明確複製、快捷鍵與設定。
- faster-whisper／CTranslate2 在本機 CPU 以 int8 辨識，不要求 API key、不呼叫雲端辨識、不退回雲端。
- 本版停用雲端 LLM 整理與翻譯，保留辨識原文讓人員核對；未加入本機 LLM。
- 預設不保存逐字稿歷史、不自動貼字。自動輸入須 opt-in，並核對原目標與焦點；焦點變動或失敗時保留預覽。Win32 SendInput 成功不保證目標欄位收到文字，不能突破權限邊界。
- 明確按 Copy 才修改剪貼簿，設定 Windows history／cloud exclusions；無法保證阻止其他剪貼簿工具讀取。
- 預設 `Ctrl+Alt+F9` 開始／停止，`Ctrl+Alt+F10` 取消；資料存於 `%LOCALAPPDATA%\SGHVoice`。
- 加入 20 個日文精神科用語的可選拼寫候選、來源及合成範例。只供人工核對，不自動改詞、不替換藥名／劑量／否定語意，不宣稱辨識率已有提升。

## 模型準備

Installer **不含模型**。首次明確確認下載
[Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base)
固定 revision `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`，MIT，
總計 **147,882,941 bytes（約 148 MB）**，或選擇已備妥的本機模型資料夾。
下載前顯示來源與容量，逐檔核對大小與 SHA-256，無需帳號／token。
模型準備是連網下載公開檔案；錄音辨識本身在本機執行。啟動、錄音不會暗中下載；
模型不完整或失敗不會改用雲端。來源權重為 FP16，執行時計算為 CPU int8。

Windows x64 CPU 需 SSE 4.1。8 GB RAM、至少 1 GB 磁碟餘量為工程建議，非實測最低規格。
不要求 GPU／CUDA，不承諾即時速度。套件包含 CPU／VC runtime DLL；仍需乾淨 Windows
10/11 標準使用者實測。未簽章可能遇到系統信任提示；若遭政策阻擋記錄 BLOCKED，不要求關閉安全機制。

## 已執行的驗證與成本

Windows source tests 於固定 source SHA 通過 **239 tests + 65 subtests**。
CI 實際執行安裝程式、從 source 目錄之外啟動已安裝程式自測、解除安裝。
runner 為 Windows Server 2022 管理員環境，因此 `standardUserTested: false`。
合成靜音的 frozen CPU 模型推論用時 1.656 秒；此數字不是語音辨識速度基準，
Python socket guard 不能作為 native DLL／整個作業系統零網路流量的證明。

先前一次 Windows run 因 Git 換行與 UTF-8 測試問題失敗，未產出／發布安裝檔；
修復後本次全部通過。macOS 離線整合階段另有 870 tests／65 subtests 通過，
只能補充來源測試，不替代 Windows 證據。

使用 public repo 標準 `windows-2022` runner 與 Release assets，無付費 runner、
無 Actions artifact/cache/snapshot upload、無新 credential、API 或簽章購買。
依 [GitHub Actions 計費規則](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
及 [Release 配額](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas)
評估此路徑無增額服務費；不代表稽核了其他既有帳單。未修復或啟動無效的 Parallels Windows VM。

## 官網與後續驗收

`voice.shingihou.com` 對應 Firebase project `sgh-meishi`、site `sgh-voice`。
建議最小上線內容為測試版說明頁與首頁連結，EXE 留在 GitHub Release。
`windows-preview.html` 與功能分支中的三語入口已準備，下載 gate 及既有平台流程
共 46 tests 通過；並經獨立來源審閱。此 HTML 尚未部署至 production。
隔離的最小 production patch 只加首頁一個連結，需在部署前核對仍符合現有首頁基線。
Firebase 既有 production workflow 同時部署 Hosting 與 Firestore rules，不能直接重跑來做此變更。
部署前須確認既有方案／共用流量額度與授權，或取得精確費用／部署範圍的批准；不新增 credential。
Hosting release 會替換完整版本，不能只把兩個檔案的目錄 deploy 到 production；
須保留全部現有 Mac／Android 靜態資產與 config。下一次 main 部署也須保留新入口。

互動驗收步驟見 [WINDOWS_BUILD.md](WINDOWS_BUILD.md)：使用非敏感合成語音，
驗證實體錄音、離線辨識、快捷鍵、IME／Unicode 貼字、剪貼簿、焦點改變及標準使用者安裝。
此測試版已可下載，不要求使用者先提供 Windows 電腦才交付安裝檔；
在得到上述實機證據前，正式 Windows manifest 保持 pending。

main 基線為 `e096d3c977d9b9cdc98c17639ceaf6e39ebc5822`，本任務未 push main。
原始 `/Volumes/Satechi_SSD/voice-input/source` Android checkout 的 dirty 檔、APK、
Android 2.8.9 尚未發布改動與 JEV 研究 worktree 均未納入 Windows 發布。
