# SGH Voice Windows 離線版（日文・醫療機構）交接

最後更新：2026-10-05
分支：`ccr-0bdb0e97-3m6efc`（以 `codex/windows-build-offline-20261004-r2` 為基礎）

## 目標與已確定的決策

| 項目 | 決定 |
|---|---|
| 對象 | 日本醫療機構中不能連網的 Windows 端末 |
| 交付 | 單一安裝檔（內含語音模型），透過 USB 或 Google Drive 交付同一個檔案 |
| 辨識 | 只做日文，在本機 CPU 上執行（int8），不使用任何雲端服務 |
| LLM 整理 | 本機產生日文 SOAP 草稿（Qwen3.5-4B，llama.cpp CPU，子行程、不連網）；只用於草稿，必須由醫師確認 |
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
   └─ model-verified.json（模型驗證快取：版本號 + 檔案大小 + 修改時間 + 檔頭檔尾 1 MiB 雜湊）
```

- `resources/windows/model-ja-v1.json`：固定的 repository、revision、各檔案大小與 SHA-256。
- `windows_client/models.py`：只負責「找到」並「驗證」內建模型，沒有任何網路程式碼。
- `scripts/fetch_windows_model.py`：只在建置時使用，依清單下載並驗證模型，放進 bundle。不會打包進 App。
- 第一次啟動時會完整計算 SHA-256；之後只要檔案大小、修改時間和檔頭檔尾 1 MiB 的雜湊都沒變，就跳過完整計算。
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

安裝檔的 SHA-256 會隨每次建置改變（內含 build metadata）；交付時以當次建置的 `SHA256SUMS.txt` 為準。CI 全部通過後，會把安裝檔和 `SHA256SUMS.txt` 上傳成 artifact `SGHVoice-Windows-offline`（在該次 Actions run 頁面最下方下載，GitHub 預設保留 90 天；下載後是 zip，需先解壓）。

## 音檔匯入（WAV／MP3）

- `windows_client/audio_import.py`：以安裝包內既有的 libsndfile（soundfile）解碼 WAV／MP3，轉單聲道，先低通濾波（避免高頻折疊）再轉成 16 kHz PCM16 WAV，以 30 秒為單位分段處理，長錄音不會整個載入記憶體。上限 3 小時或 2 GB。不使用 FFmpeg，也不連網。
- 辨識使用「檔案模式」：開啟內建的 Silero VAD 跳過靜音段，每個段落換行，並回報進度。
- UI：「音声ファイルを文字起こし…」「テキストを保存…」（UTF-8 BOM、CRLF，記事本可直接開啟）；可隨時取消；結果只做預覽，不自動貼入其他程式。
- 原始檔不修改、不上傳；轉檔用的暫存檔辨識後即刪除。
- **未支援 M4A（AAC）**：iPhone 語音備忘錄和多數 Android 錄音 App 預設是 M4A，需要另外加 AAC 解碼，列為下一步。
- CI：把 FLEURS 語音接成 44.1 kHz 立體聲 MP3（3 段）和 48 kHz 立體聲 24-bit WAV（2 段），中間有 2 秒停頓，放在日文且含空白的資料夾／檔名下（`スマホ 録音\ボイスメモ 0001.mp3`、`ICレコーダー 録音.wav`），在封鎖網路的狀態下用 frozen App 讀入並辨識，兩種格式的字錯率都需低於上限。

## 長時間錄音（看診一次錄完）

- 即時錄音上限由 3 分鐘改為 60 分鐘（`windows_client/controller.py` `MAX_RECORDING_SECONDS`）；無聲自動停止由 2 分鐘改為 10 分鐘（安靜的理學檢查不會被切斷）。
- 超過 30 秒的錄音改用「檔案模式」辨識（VAD 跳過靜音、每段換行、顯示進度）；短口述維持原本行為。
- 交給辨識器的只有 WAV 路徑，錄音的記憶體陣列會先釋放（60 分鐘約 230 MB）。
- UI 顯示「録音中 mm:ss（最長 60:00）」；達到上限時自動停止並辨識，提示使用者確認。
- 只錄本機麥克風：視訊看診戴耳機時，對方聲音不會被錄到。

## 本機 SOAP 草稿（2026-10-06）

### 模型比較（Windows CI，AMD EPYC 2 核 4 執行緒，llama.cpp b11435 CPU，Q4_K_M，虛構看診逐字稿 1,352 字）

| 模型 | 授權 | 檔案 | 總時間 | prompt 速度 | 生成速度 | 記憶體峰值 | 事實檢查 | 觀察 |
|---|---|---|---|---|---|---|---|---|
| **Qwen3.5-4B（採用）** | Apache-2.0 | 2.74 GB | 89 秒 | 30 tok/s | 9.7 tok/s | 5.1 GB | 全部保留、無捏造 | 忠實、簡潔；但省略了「胸痛なし」等否定症狀（已在 prompt 加規則） |
| Qwen3-4B-Instruct-2507 | Apache-2.0 | 2.50 GB | 125 秒 | 30 tok/s | 8.4 tok/s | 6.8 GB | 全部保留 | 混入簡體字「头痛」、改寫警示症狀、自行加入條件 |
| Sarashina2.2-3B | MIT | 2.07 GB | 57 秒 | 41 tok/s | 13.4 tok/s | 4.7 GB | 漏掉 148/92 | 日文最自然，但把「力が入らない」改成「しびれ」；上下文只有 8K |
| Qwen3.5-2B | Apache-2.0 | 1.28 GB | 33 秒 | 78 tok/s | 21.7 tok/s | 2.3 GB | 漏 4 項 | S 與 O 重複，不堪用 |

推算：30 分鐘看診約 6,000～9,000 字，2 核機器上約 4～6 分鐘；一般 4 核以上電腦應較快（需實機量測）。

### 架構

- `resources/windows/llm-ja-v1.json`：llama.cpp 官方 Windows CPU 發行檔（tag + zip SHA-256）與 GGUF（大小 + SHA-256）。
- `scripts/fetch_windows_llm.py`（只在建置時）：下載並驗證，只取出 `llama-completion.exe`、DLL 與授權檔，放到 `<app>\llm\`。
- `windows_client/soap.py`：以子行程執行 `llama-completion.exe`（prompt 走私有暫存檔、結果走 stdout），不開任何連接埠、不傳任何下載參數；低優先權執行；可取消；30 分鐘逾時。
- 第一次使用時完整比對 GGUF 的 SHA-256，之後用快取（`%LOCALAPPDATA%\SGHVoice\llm-verified.json`）。
- 輸出必須有 S/O/A/P 四個標題；草稿裡「逐字稿中找不到的數字與片假名用語」會列在「要確認」區，作為捏造的警示。
- 錄音超過 30 秒或匯入音檔後自動產生（可在設定關閉）；也可按「SOAP 下書きを作成」用（修改過的）逐字稿重新產生。
- 自動輸入開啟時，長錄音只貼入 SOAP 草稿（逐字稿留在畫面）；手動產生的草稿一律不自動貼入。
- 記憶體不到 16 GB 的電腦，產生 SOAP 時會先釋放語音模型（約 2 GB），下次錄音再載入。
- 錄音檔在開始產生 SOAP 前就刪除。

### 安裝檔

兩個模型合計約 4.4 GB，超過單一安裝檔上限，所以改用 Inno Setup 的 DiskSpanning：產出 `SGHVoice-Windows-<ver>-x64-unsigned.exe` 加上 `…-1.bin`、`…-2.bin` 等分割檔，**必須放在同一個資料夾**，執行 .exe 即可。`SHA256SUMS.txt` 包含所有分割檔。

**需要使用者修改 workflow**：`.github/workflows/windows-medical.yml` 的 artifact `path` 要加一行 `dist/windows/*.bin`，否則 artifact 只有 .exe，無法安裝。

### 驗證範圍

CI 在封鎖 Python 網路的狀態下，用 frozen App 對虛構逐字稿產生 SOAP，檢查四個標題、必須保留的數值（血壓、HbA1c、eGFR、藥名與劑量、過敏、回診）與不得出現的藥物／檢查。注意：llama.cpp 是子行程，不受 Python 的網路封鎖影響；我們只確認程式碼不傳任何網路參數。這不是臨床準確度的驗證。

## 尚待處理（交付前必須完成）

1. **程式碼簽章**（W8）：未簽章的安裝檔可能被醫院的防毒軟體或白名單擋下。
2. **實機驗證**（W9）：實機麥克風、全域快捷鍵、電子病歷輸入欄、日文 IME、一般使用者權限、Windows 10/11 Enterprise LTSC、VDI／遠端桌面、低規格端末的速度。
3. **授權的法務確認**：
   - Intel OpenMP（`libiomp5md.dll`，CTranslate2 CPU 版的依賴）授權條款 3.3：用在醫療系統時，要求使用者賠償 Intel 並使其免責。需要法務判斷能否接受，或改用不依賴 Intel OpenMP 的 CTranslate2 建置。
4. **醫療口述評測**：FLEURS 是唸稿的維基百科句子，不代表醫療口述的準確度。需要準備不含患者資料的角色扮演錄音再評測一次。
5. **SOAP 草稿評測**：目前只用一段虛構逐字稿檢查。需要多段角色扮演（不同科別、30 分鐘長度、含否定與用藥變更），由醫師審閱草稿品質與捏造率；並在實機量測 8 GB／4 核電腦的時間與記憶體。
6. **法規定位**：SOAP 草稿只是記錄輔助，不做診斷；對外說明時不得宣稱診斷或治療效果，也需確認是否落入醫療機器程式（SaMD）的範圍（需專家確認）。
