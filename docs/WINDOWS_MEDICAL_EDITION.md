# SGH Voice Windows 離線版（日文・醫療機構）交接

最後更新：2026-10-05
分支：`ccr-0bdb0e97-3m6efc`（以 `codex/windows-build-offline-20261004-r2` 為基礎）

## 目標與已確定的決策

| 項目 | 決定 |
|---|---|
| 對象 | 日本醫療機構中不能連網的 Windows 端末 |
| 交付 | 單一安裝檔（內含語音模型），透過 USB 或 Google Drive 交付同一個檔案 |
| 辨識 | 只做日文，在本機 CPU 上執行（int8），不使用任何雲端服務 |
| LLM 整理 | 第一版不放（不含 Qwen） |
| 安裝方式 | 全機安裝（院方 IT 用管理員權限安裝到 Program Files，所有帳號共用） |
| 學習 | 不自動學習；詞彙表只顯示候選，不改寫辨識結果（沿用 r2 設計） |
| 不移植 | `repair` 分支的 `38b01d4`（OpenAI 雲端辨識 2.7.6） |

## 架構

```
SGHVoice-Windows-<ver>-x64-unsigned.exe（全機安裝）
└─ C:\Program Files\SGHVoice\
   ├─ SGH Voice.exe + _internal\（PyInstaller，CPU 版 CTranslate2）
   └─ models\<id>\（模型檔，以 nocompression 存放）

%LOCALAPPDATA%\SGHVoice\（各使用者）
   ├─ config.json
   └─ model-verified.json（模型驗證快取：版本號 + 檔案大小 + 修改時間）
```

- `resources/windows/model-ja-v1.json`：固定的 repository、revision、各檔案大小與 SHA-256。
- `windows_client/models.py`：只負責「找到」並「驗證」內建模型，沒有任何網路程式碼。
- `scripts/fetch_windows_model.py`：只在建置時使用，依清單下載並驗證模型，放進 bundle。不會打包進 App。
- 第一次啟動時會完整計算 SHA-256；之後只要檔案的大小和修改時間沒變，就跳過完整計算。
- 驗證未完成或失敗時不能錄音，畫面會請使用者重新安裝。

## 驗證方式（CI）

GitHub App 沒有修改 workflow 的權限，所以沿用既有的手動 workflow `windows-build.yml`，由人在 GitHub 上觸發（Actions → Windows installer (manual, unsigned) → Run workflow → 選擇分支）。它會依序執行：

1. Windows 原始碼測試
2. `windows/build.ps1`：PyInstaller → 下載並驗證模型 → frozen 自我測試（含 `bundled_model`）→ Inno Setup → 發行檢查 → 產生 `SHA256SUMS.txt`
3. `windows/offline-test.ps1`：在封鎖 Python 網路連線的狀態下，用安裝包內的模型（完整 SHA-256 驗證）辨識 5 段 FLEURS 日文語音，字錯率需低於上限
4. `windows/install-test.ps1`：全機安裝 → 逐檔比對 → HKLM 登錄 → 共用捷徑 → 安裝後自我測試 → 解除安裝

## 狀態

| 項目 | 狀態 |
|---|---|
| W1 以 r2 為基礎、移植 CI 監控 | 完成 |
| W2 日文模型評測 | 腳本完成；Windows CI 執行結果見下方 |
| W3–W7 實作 | 完成；本機（Linux）Windows 測試全數通過；Windows CI 建置待執行 |
| W8 程式碼簽章 | 未開始（需購買憑證） |
| W9 實機驗證 | 未開始（需實體 Windows 端末） |
| W10 文件 | 日文導入手順書 `docs/ja/windows-offline-install-guide.md`、SHA256SUMS 自動產生、授權聲明已加入模型段落 |

## 尚待處理（交付前必須完成）

1. **程式碼簽章**（W8）：未簽章的安裝檔可能被醫院的防毒軟體或白名單擋下。
2. **實機驗證**（W9）：實機麥克風、全域快捷鍵、電子病歷輸入欄、日文 IME、一般使用者權限、Windows 10/11 Enterprise LTSC、VDI／遠端桌面、低規格端末的速度。
3. **授權的法務確認**：
   - Intel OpenMP（`libiomp5md.dll`，CTranslate2 CPU 版的依賴）授權條款 3.3：用在醫療系統時，要求使用者賠償 Intel 並使其免責。需要法務判斷能否接受，或改用不依賴 Intel OpenMP 的 CTranslate2 建置。
   - kotoba-whisper 的訓練資料來自 ReazonSpeech。模型本身標示 Apache-2.0，但訓練資料授權對商業散布的影響尚未確認。
4. **醫療口述評測**：FLEURS 是唸稿的維基百科句子，不代表醫療口述的準確度。需要準備不含患者資料的角色扮演錄音再評測一次。
