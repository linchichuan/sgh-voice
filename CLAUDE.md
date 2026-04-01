# Voice Input — 專案記憶

## 專案概述

AI 語音輸入工具，替代 Typeless（$30/月）。串接 Whisper + LLM，自己的資料自己掌控。

## 最高優先規則

- **所有中文輸出必須是繁體中文**，不允許簡體中文
- 多語混合（中/英/日）時，中文部分強制繁體，英日保持原樣
- 繁中三層防護：Whisper prompt → LLM system prompt → OpenCC s2twp

## 功能更新記錄

- **2026-04-01**: OpenRouter 整合 + LLM prompt 優化 + Dashboard 即時設定生效
  - **OpenRouter 整合**：新增第 5 個 LLM 引擎，支援 200+ 模型（含免費模型）
    - `config.py`：新增 `openrouter_api_key`、`openrouter_model` 設定
    - `transcriber.py`：新增 `_openrouter_process()` 函數，OpenAI 相容 API（`https://openrouter.ai/api/v1`）
    - LLM 路由：5 引擎自動 fallback（Groq → OpenRouter → Claude → OpenAI → Ollama）
    - Dashboard UI：新增 API Key 欄位、模型下拉（分極速/旗艦/其他三組）、自訂模型 ID 輸入
    - 推薦極速免費模型：`qwen/qwen3-30b-a3b:free`（MoE，只啟用 3B 參數）
  - **LLM System Prompt 重構**：
    - `_DICTATE_SYSTEM` 優化為 7 規則版（~230 tokens），所有 LLM 引擎共用
    - `config.py:claude_system_prompt` 改為空字串，空值時自動 fallback 到 `_DICTATE_SYSTEM`
    - 所有 LLM 函數的讀取邏輯改為 `self.config.get(...) or self._DICTATE_SYSTEM`
    - Dashboard 標籤從「Claude 系統提示詞」→「LLM 後處理系統提示詞」（6 語言 i18n 更新）
  - **Dashboard 設定即時生效 Bug 修復**：
    - `dashboard.py:api_save_config()` 新增 `_engine.reload_config()` 呼叫
    - 原本改設定需重啟，現在按「儲存」即時生效

- **2026-03-03**: iOS App v1.0（SGH Voice for iOS）
  - **專案位置**：`ios/SGHVoice/`（Swift, SwiftUI, Combine）
  - **架構**：無後端，iOS App 直接呼叫 OpenAI Whisper API + Claude API
  - **核心模組**：
    - `API/ApiConfig.swift`：API 金鑰管理（Keychain 加密 + UserDefaults）
    - `API/WhisperClient.swift`：Whisper multipart/form-data 音訊上傳
    - `API/ClaudeClient.swift`：Claude 後處理（去填充詞、三語混合、風格切換）
    - `Audio/AudioRecorder.swift`：AVFoundation 錄音（16kHz 16bit Mono WAV）
    - `Processing/DictionaryManager.swift`：詞庫管理 + 場景預設（general/medical）
    - `Processing/TranscriptionPipeline.swift`：四層處理管線（Whisper → 詞庫修正 → Claude → 繁中防護）
    - `UI/MainView.swift`：主畫面（錄音按鈕 + 辨識結果 + 複製）
    - `UI/MainViewModel.swift`：MVVM ViewModel + TranscriptionProgressDelegate
    - `UI/SettingsView.swift`：API Key / 模型 / 風格 / 場景設定
  - **平台相容**：iOS / macOS Catalyst 雙平台（#if canImport(UIKit) / #if os(iOS)）
  - **Bundle ID**：`com.shingihou.SGHVoice`
  - **開發團隊**：Apple Developer ID `3295A59K9G`

- **2026-03-17**: 多平台同步升級 v1.4.0 & Groq 整合 & 自動進化迴圈
  - **Groq 整合**：Android 與 iOS 補齊 Groq API 支援，STT (Whisper-large-v3-turbo) 與 LLM (Llama 3) 速度極大化。
  - **通用 LLM 架構**：Android/iOS 原 `ClaudeClient` 升級為 `LlmClient`，支援在 Claude/OpenAI/Groq 之間自由切換。
  - **自動進化迴圈 (Evolution Loop)**：
    - `scripts/auto_triage.py`：利用 LLM 分析 `history.json` 中的使用者修正，產出字典優化建議。
    - `scripts/maintenance_loop.sh`：整合錯誤分析、模型監控、辭書更新的每日自動化任務。
    - `LOOP.md`：為 Agent (Claude Code) 建立的標準化進化指令集。
  - **版本同步**：macOS, iOS, Android 三平台版本號統一升級至 `1.4.0`。

- **2026-03-17**: Breeze-ASR-25 本地離線繁中 ASR 整合（v1.4.0）
  - **MediaTek Breeze-ASR-25**：基於 whisper-large-v2 微調，專為繁體中文 + 中英混用優化
  - **MLX 轉換腳本**：`scripts/convert_breeze_to_mlx.py`（HF Transformers → mlx-whisper 格式）
  - **4-bit 量化**：0.82 GB，30 秒音頻暖機推理 3.04 秒（whisper-turbo 10.58 秒的 3.5 倍速）
  - **模型路徑**：`config.py` 新增 `LOCAL_MODEL_PATHS` + `BREEZE_MODELS` 映射
  - **Transcriber 整合**：`_local_whisper()` 自動偵測 Breeze 模型，設定 `fp16=True`
  - **Dashboard UI**：Whisper 模型下拉新增 Breeze-ASR-25 4bit / fp16 選項
  - **模型檔案位置**：
    - fp16: `/Volumes/Satechi_SSD/huggingface/hub/breeze-asr-25-mlx/`（2.87 GB）
    - 4-bit: `/Volumes/Satechi_SSD/huggingface/hub/breeze-asr-25-mlx-4bit/`（0.82 GB）
  - **Granite 4.0 1B Speech 評估結果**：不支援中文，僅英/法/德/西/葡/日，不適用

- **2026-03-17**: 聲紋辨識（Speaker Verification）功能與效能修正（v1.3.0）
  - **純本地聲紋模組**: `voiceprint.py` 使用 MFCC + Numpy DCT，不依賴 PyTorch/Scipy，維持原打包體積
  - **背景音過濾**: Dashboard 新增「啟用聲紋驗證」開關與「相似度閾值」滑桿（預設 0.97）
  - **自動建立聲紋**: 直接從指定的音訊備份目錄讀取語音特徵，產生 80 維個人聲紋
  - **STT 前置過濾 (Step 0.5)**: 將不符合本人聲紋或純噪音（Webcam 背景音）的聲音直接丟棄，防止 Whisper 產生重複字元的幻覺
  - **UI 強化**: Dashboard 設定頁加入聲紋狀態指示（維度、檔案大小）與刪除重建功能

- **2026-03-01**: 醫療場景模式 + 自動學習 + 產品網站（v1.2）
  - **產品 Landing Page**（voice.shingihou.com）:
    - Firebase Hosting (`sgh-voice` site under `sgh-meishi` project)
    - 5 語言切換（日文預設 / 繁中 / 英文 / 越南 / 泰文）
    - Firestore 整合：Subscribe Email (`sgh-voice-subscribers`) + Contact Form (`sgh-voice-contacts`)
    - 隱私權政策頁：`voice.shingihou.com/privacy.html`（Google Play 用）
    - 檔案位置：`sgh-voice-web/`（index.html, style.css, i18n.js, main.js, privacy.html）
  - **場景模式**:
    - `config.py` 新增 `SCENE_PRESETS` 字典（general / medical），含場景專用詞庫、修正規則、LLM prompt
    - `DEFAULT_CONFIG` 新增 `active_scene` 設定項
    - `memory.py:build_whisper_prompt()` 新增 `scene_words` 參數，合併場景詞彙，上限 30→50，字元上限 500→800
    - `memory.py:apply_corrections()` 新增 `scene_corrections` 參數（使用者規則 > 場景規則 > 基底規則）
    - `transcriber.py` 三個 LLM 函數（`_local_llm_process` / `_claude_process` / `_openai_process`）注入場景 `system_prompt_extra`
    - `transcriber.py:process()` 的 Whisper prompt 和 apply_corrections 均傳入場景資料
    - Dashboard 設定頁新增「使用場景」下拉選單
  - **Dashboard 修正自動學習（Typeless 式）**:
    - `memory.py` 新增 `update_history_item()` 方法，更新 final_text 並標記 `edited`
    - `dashboard.py` 新增 `PATCH /api/history/<ts>` endpoint，更新歷史並觸發 `learn_correction()`
    - Dashboard 歷史頁新增「編輯」按鈕，支援行內 textarea 編輯、儲存時自動學習、toast 提示學習結果

## 已知問題與修復記錄

- **2026-02-20**: 修復 `app.py:144` 的 `audio_array or filepath` bug
  - 原因：numpy array 不能用 `or` 判斷 truth value
  - 修復：改為 `audio_array if audio_array is not None else filepath`

- **2026-02-24**: 全面優化（v1.1）
  - **Bug 修復**:
    - `transcriber.py:_whisper()` 加入 `prompt` 參數，呼叫 `memory.build_whisper_prompt()` 提升三語辨識
    - `static/index.html:18` CSS 色碼 `#5555660` → `#555566`
    - 新增 OpenCC s2twp 繁中防護第三層（`requirements.txt` + `transcriber.py`）
  - **設定一致性**:
    - `config.py` DEFAULT_CONFIG: `enable_hybrid_mode` 改 `True`、`claude_model` 改 `claude-haiku-4-5-20251001`
    - 新增 `local_whisper_model`、`backup_audio_dir` 設定項
    - `app.py` 備份路徑改從 config 讀取，不再硬編碼
  - **程式碼品質**:
    - `memory.py:build_whisper_prompt()` 合併 custom_words + auto_added 去重
    - `transcriber.py:_local_whisper()` 的 initial_prompt 改用 memory prompt
    - `dashboard.py` 新增 `set_memory()` 讓 VoiceEngine 與 Dashboard 共享 memory
    - `memory.py` history 加入 threading lock + 每 10 次完整寫入
    - `transcriber.py` 填充詞檢查改用預編譯正則 `_compile_filler_pattern()`
    - `recorder.py` Toggle 模式加入 RMS 靜音偵測，連續靜音自動停止
  - **新功能**:
    - Smart Replace (Layer 3): `@mail`、`@phone` 等觸發詞自動展開（`config.py` + `transcriber.py`）
    - Rewrite API (`/api/rewrite`): 精簡/正式/翻譯改寫（`dashboard.py`）
    - Token 用量追蹤: Whisper 秒數 + Claude token 記錄到 `stats.json`（`transcriber.py` + `dashboard.py`）
    - `/api/usage`、`/api/smart_replace` 新 API 端點
  - **Dashboard UI**:
    - 歷史頁：複製原文按鈕、改寫按鈕、XSS 修復（`esc()` 加入 `>` 和 `'` 逸出）
    - 統覽頁：本月估算費用卡片（Whisper + Claude 分開顯示）
    - 設定頁：Hybrid 模式開關、本地 Whisper/LLM 模型選擇、備份路徑

## Steering 與 Specs

- Steering: `.kiro/steering/` — product.md, tech.md, structure.md
- Specs: `.kiro/specs/android-voice-input/` — Android 版規格

## 開發中的規格

### Android Voice Input（架構已建立，編譯成功）

- **架構變更**：無後端，Android App 直接呼叫 API
- **辨識**：OpenAI Whisper API（直接從 App 呼叫）
- **後處理**：Claude Haiku 4.5（直接從 App 呼叫）
- **繁中保證**：Whisper prompt + Claude prompt + OpenCC (opencc4j)
- **輸入法**：Android InputMethodService
- **專案位置**：`android/SGHVoice/`（Kotlin, Jetpack Compose）
- **GitHub**：`linchichuan/sgh-voice` → `android-dev` 分支
- **場景模式同步**（v1.2）：
  - `DictionaryManager.kt` 新增 `ScenePreset` data class + `SCENE_PRESETS` 醫療詞庫
  - `buildWhisperPrompt()` 合併場景詞彙，上限 50 個、字元上限 800
  - `applyCorrections()` 三層優先權：使用者 > 場景 > 基底
  - `getSceneSystemPromptExtra()` 回傳場景 Claude prompt
  - `ClaudeClient.postProcess()` 新增 `sceneExtra` 參數
  - `TranscriptionPipeline` 自動注入場景指令
- 詳見 `.kiro/specs/android-voice-input/tasks.md`

### 產品網站（voice.shingihou.com）

- **技術**：靜態 HTML/CSS/JS（無框架），Firebase Hosting + Firestore
- **Firebase 專案**：`sgh-meishi`，Hosting site：`sgh-voice`
- **i18n**：日文（預設）、繁中、英文、越南文、泰文
- **功能**：Subscribe Email、Contact Form、隱私權政策
- **佈署**：`cd sgh-voice-web && firebase deploy --only hosting:sgh-voice --project sgh-meishi`

## 技術堆疊

### macOS 版（現行）

Python 3.12+, mlx-whisper, Ollama Qwen, Claude Haiku 4.5, Flask, OpenCC, OpenRouter

### 處理管線（5 層）+ 場景模式

1. **Whisper STT**: Hybrid (Local mlx-whisper / Cloud OpenAI) + custom_words + 場景詞彙 prompt
   - 本地模型選項：whisper-turbo（預設）/ Breeze-ASR-25 4bit（繁中最強）/ Breeze-ASR-25 fp16
   - Breeze 模型路徑由 `config.py:LOCAL_MODEL_PATHS` 映射
2. **詞庫修正**: memory.apply_corrections()（基底 + 場景 + 使用者，使用者優先）
3. **Smart Replace**: `@mail`→email 等觸發詞展開
4. **LLM 後處理**: 5 引擎可選（Ollama / Groq / Claude / OpenAI / OpenRouter）+ 場景 system_prompt_extra
5. **OpenCC s2twp**: 繁體中文最終防護

### 使用場景（SCENE_PRESETS in config.py）

- `general`: 一般用途（預設）
- `medical`: 醫療・藥品・生技（含日文醫療術語、處方藥名、生技名詞、臺灣醫療中文）

### LLM 後處理 System Prompt 架構

- **`_DICTATE_SYSTEM`**（`transcriber.py`）：內建最佳化 prompt，所有引擎共用
- **`claude_system_prompt`**（`config.py` / Dashboard）：使用者自訂 prompt，留空則用 `_DICTATE_SYSTEM`
- 讀取邏輯：`self.config.get("claude_system_prompt") or self._DICTATE_SYSTEM`
- 場景額外 prompt 由 `SCENE_PRESETS[scene]["system_prompt_extra"]` 追加
- App 感知風格 prompt 由 `detect_app_style()` 追加

### LLM 引擎（5 個，含自動 fallback）

| 引擎 | config key | 模型設定 key | 備註 |
|------|-----------|-------------|------|
| Ollama | — | `local_llm_model` | 本地免費，需安裝 Ollama |
| Groq | `groq_api_key` | `groq_model` | 極速雲端 |
| Claude | `anthropic_api_key` | `claude_model` | 品質最高 |
| OpenAI | `openai_api_key` | `openai_model` | GPT-4o |
| OpenRouter | `openrouter_api_key` | `openrouter_model` | 200+ 模型，含免費 |

### Android 版（無後端，直接呼叫 API）

Kotlin, Jetpack Compose, OkHttp, OpenAI/Groq Whisper API, Claude/OpenAI/Groq LLM API, opencc4j

### iOS 版（無後端，直接呼叫 API）

Swift, SwiftUI, Combine, AVFoundation, URLSession, Keychain, OpenAI/Groq Whisper API, Claude/OpenAI/Groq LLM API

### 未來升級路線

- **macOS 26+ SpeechAnalyzer**：Apple 原生離線 ASR，支援多語/VAD/即時字幕
- **Breeze-ASR 25**：聯發科開源 ASR 模型
- **Qwen 3 ASR**：阿里巴巴語音辨識模型
- **競品 ByeType**：即將推出 macOS 版，支援離線 ASR + 系統 ASR 一鍵啟動

## 競品分析（2026-02-24）

### Purri (v0.1.3) — wupingju/purri-releases

- macOS 選單列 App，免費 BYOK（自帶 OpenAI Key）
- 純雲端 OpenAI Whisper + GPT 潤飾
- 繁體中文優先但無三語混合
- 有情境潤飾（通用/會議/Email/技術文件）、歷史匯出、用量追蹤
- 無本地 Whisper、無詞庫學習、無 Smart Replace

### 我們的優勢

- 三語混合（中/日/英）+ 繁中三層防護
- Hybrid 本地+雲端（Apple Silicon mlx-whisper）
- 個人詞庫自動學習
- Smart Replace 觸發詞展開
- 9 種改寫情境（精簡/正式/會議/Email/技術/口語/翻英/翻日/翻中）
- 歷史匯出（TXT/CSV）
- 剪貼簿保護（貼上後自動還原原有剪貼簿）
- LLM 幻覺偵測（自我介紹特徵詞 + 長度比對）

## 本機 Loop 自動化（scripts/）

### 場景 0：自動進化與診斷 (v1.4.0)
- `scripts/auto_triage.py`：分析歷史修正紀錄，找出系統性錯誤。
- `scripts/maintenance_loop.sh`：每晚 04:00 執行的總指揮腳本。
- `LOOP.md`：Agent 專用進化指令集。
- 用法：`/loop "cat LOOP.md"`

### 場景 1：模型精度批次測試
- `scripts/benchmark_models.py`：比較 Breeze-ASR-25 4bit/fp16 vs Whisper Turbo
- 測試音檔：`test/audio/`，正確答案：`test/ground_truth/`，結果：`test/results/MODEL_BENCHMARK.md`
- 計算 CER（Character Error Rate）+ 耗時，生成 Markdown 報告
- Claude Code 用法：`/loop "python3 scripts/benchmark_models.py && cat test/results/MODEL_BENCHMARK.md"`

### 場景 2：HuggingFace 新模型監控
- `scripts/hf-model-watch.sh`：搜尋 HF 上最近 7 天的新 ASR 模型
- launchd 每天 08:00 執行，發現新模型推 macOS 通知
- 可選：有 ANTHROPIC_API_KEY 時自動用 Claude 評估相關性（7 分以上才通知）
- 追蹤檔案：`~/.voice-input/hf_seen_models.txt`

### 場景 3：業界辭書自動擴充
- `scripts/dict-update.py`：從 PMDA（新藥）+ MHLW（醫療制度）自動擷取術語
- launchd 每週日 03:00 執行，新術語寫入 `~/.voice-input/dictionary.json`
- 支援 `--dry-run` 乾跑模式

### launchd 排程管理
- 安裝：`bash scripts/install-launchd.sh`
- 卸載：`bash scripts/install-launchd.sh --uninstall`
- plist 定義：`scripts/launchd/`

## Skills

- `/macos-voice-input` — macOS 版完整開發技能（管線、最佳化、API 呼叫）
- `/android-voice-keyboard` — Android IME 鍵盤開發技能（無後端架構）
