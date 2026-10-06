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

`.github/workflows/windows-medical.yml`（由使用者建立）在這條分支每次 push 時，於 GitHub 標準 Windows runner 執行 `windows/ci-medical.ps1`：

1. Windows 原始碼測試（ruff + pytest）
2. `windows/build.ps1`：PyInstaller → 依清單下載並驗證模型 → frozen 自我測試（含 `bundled_model`）→ Inno Setup → 發行檢查 → `SHA256SUMS.txt`
3. `windows/offline-test.ps1`：封鎖 Python 網路連線，用安裝包內的模型（完整 SHA-256 驗證）辨識 5 段 FLEURS 日文語音，字錯率上限 15%
4. `windows/install-test.ps1`：全機安裝 → 逐檔比對 → HKLM 登錄 → 共用捷徑 → 安裝後自我測試 → 解除安裝
5. 模型比較（選用，預設關閉；用 `-BenchmarkSeconds 2100` 開啟）

## 模型選擇（2026-10-05 Windows CI 實測，AMD EPYC 2 核 4 執行緒，CPU int8）

FLEURS ja_jp dev 15 段唸稿語音（CC-BY 4.0）＋ 1 段 3.5 分鐘的長錄音：

| 模型 | 字錯率 | 每段處理時間（中位數） | 自動標點 | 長錄音 | 記憶體峰值 |
|---|---|---|---|---|---|
| **Whisper large-v3-turbo（採用）** | **5.9%** | 11.4 秒 | 40% | 內容完整 | 1.96 GB |
| kotoba-whisper v2.0 | 6.3% | 11.1 秒 | 13% | **漏掉整段內容** | 1.85 GB |
| Whisper small | 15.3% | 3.1 秒 | 87% | 完整，錯字多 | 0.71 GB |
| Whisper base（舊預覽版） | 25.4% | 1.1 秒 | 80% | 錯字很多 | 0.35 GB |

採用 `mobiuslabsgmbh/faster-whisper-large-v3-turbo@0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf`：

- 字錯率最低；長錄音不漏字（kotoba 在 3.5 分鐘錄音中整段漏字，對病歷口述是嚴重缺陷）。
- 第一版沒有 LLM 整理，標點只能靠辨識模型自己加；turbo 的標點比例較高。
- 授權單純：OpenAI Whisper 權重與 CTranslate2 轉換版都是 MIT，沒有 kotoba 訓練資料（ReazonSpeech）的授權疑慮。
- 速度和 kotoba 相同：在 2 核 runner 上，處理時間約等於語音長度（RTF 約 0.87）。一般 4 核以上的辦公室電腦應該較快，需實測。
- small 是低規格端末的備案（速度約快 3.7 倍，但字錯率高 2.6 倍）。

FLEURS 是唸稿的維基百科句子，**不代表醫療口述的準確度**。

## 建置與離線測試（run #4，commit 76ad7e8，large-v3-turbo，嚴格比對）

| 項目 | 結果 |
|---|---|
| 建置 | PASS（模型依清單嚴格驗證 SHA-256） |
| 模型 SHA-256 驗證 | 1.55 秒 |
| 離線日文辨識 | 5 段 FLEURS，整體字錯率 4.2%（0%～6.5%），上限 15%，網路連線嘗試 0 次 |
| 全機安裝 → 安裝後自我測試 → 解除安裝 | PASS |

`SHA256SUMS.txt`（run #4）：

```
703d84d021f72507333444ec56cf4c5636bc93babff1bb77db238385dbf805f7  SGHVoice-Windows-2.7.5-x64-unsigned.exe
b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e  models/whisper-large-v3-turbo-ct2/config.json
e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da  models/whisper-large-v3-turbo-ct2/model.bin
7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711  models/whisper-large-v3-turbo-ct2/preprocessor_config.json
297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd  models/whisper-large-v3-turbo-ct2/tokenizer.json
c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1  models/whisper-large-v3-turbo-ct2/vocabulary.json
```

安裝檔的 SHA-256 會隨每次建置改變（內含 build metadata）；交付時以當次建置的 `SHA256SUMS.txt` 為準。CI 不上傳安裝檔（不使用 artifact／release），要交付時需另外在 Windows 上執行 `windows/build.ps1` 產出，或另行決定發佈方式。

## 音檔匯入（WAV／MP3）

- `windows_client/audio_import.py`：以安裝包內既有的 libsndfile（soundfile）解碼 WAV／MP3，轉單聲道，先低通濾波（避免高頻折疊）再轉成 16 kHz PCM16 WAV，以 30 秒為單位分段處理，長錄音不會整個載入記憶體。上限 3 小時或 2 GB。不使用 FFmpeg，也不連網。
- 辨識使用「檔案模式」：開啟內建的 Silero VAD 跳過靜音段，每個段落換行，並回報進度。
- UI：「音声ファイルを文字起こし…」「テキストを保存…」（UTF-8 BOM、CRLF，記事本可直接開啟）；可隨時取消；結果只做預覽，不自動貼入其他程式。
- 原始檔不修改、不上傳；轉檔用的暫存檔辨識後即刪除。
- **未支援 M4A（AAC）**：iPhone 語音備忘錄和多數 Android 錄音 App 預設是 M4A，需要另外加 AAC 解碼，列為下一步。
- CI：把 3 段 FLEURS 語音接成 44.1 kHz 立體聲 MP3（中間有 2 秒停頓），在封鎖網路的狀態下，用 frozen App 讀入並辨識，字錯率需低於上限。

## 尚待處理（交付前必須完成）

1. **程式碼簽章**（W8）：未簽章的安裝檔可能被醫院的防毒軟體或白名單擋下。
2. **實機驗證**（W9）：實機麥克風、全域快捷鍵、電子病歷輸入欄、日文 IME、一般使用者權限、Windows 10/11 Enterprise LTSC、VDI／遠端桌面、低規格端末的速度。
3. **授權的法務確認**：
   - Intel OpenMP（`libiomp5md.dll`，CTranslate2 CPU 版的依賴）授權條款 3.3：用在醫療系統時，要求使用者賠償 Intel 並使其免責。需要法務判斷能否接受，或改用不依賴 Intel OpenMP 的 CTranslate2 建置。
4. **醫療口述評測**：FLEURS 是唸稿的維基百科句子，不代表醫療口述的準確度。需要準備不含患者資料的角色扮演錄音再評測一次。
