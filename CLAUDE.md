# Voice Input — 專案記憶

## 專案概述
AI 語音輸入工具，替代 Typeless（$30/月）。串接 Whisper + LLM，自己的資料自己掌控。

## 最高優先規則
- **所有中文輸出必須是繁體中文**，不允許簡體中文
- 多語混合（中/英/日）時，中文部分強制繁體，英日保持原樣
- 繁中三層防護：Whisper prompt → LLM system prompt → OpenCC s2twp

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
- 詳見 `.kiro/specs/android-voice-input/tasks.md`

## 技術堆疊
### macOS 版（現行）
Python 3.12+, mlx-whisper, Ollama Qwen, Claude Haiku 4.5, Flask, OpenCC

### 處理管線（5 層）
1. **Whisper STT**: Hybrid (Local mlx-whisper / Cloud OpenAI) + custom_words prompt
2. **詞庫修正**: memory.apply_corrections()
3. **Smart Replace**: `@mail`→email 等觸發詞展開
4. **LLM 後處理**: Hybrid (Local Qwen / Cloud Claude) 去填充詞+潤稿
5. **OpenCC s2twp**: 繁體中文最終防護

### Android 版（無後端，直接呼叫 API）
Kotlin, Jetpack Compose, OkHttp, OpenAI Whisper API, Claude API, opencc4j

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

## Skills
- `/macos-voice-input` — macOS 版完整開發技能（管線、最佳化、API 呼叫）
- `/android-voice-keyboard` — Android IME 鍵盤開發技能（無後端架構）
