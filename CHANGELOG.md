# Changelog

## v2.2.0 (2026-05-20) — Perceived Responsiveness & Production Trust

跨平台 Release：macOS / iOS / Android 三平台同步升版。針對「實際很快但感覺不夠快」做整體優化，10 個 bug 透過 4 輪 codex review loop 被攔下，沒一個 ship 出去。

### ⚡ 感知速度提升（macOS）
- **5 處固定 sleep → polling**：`paste_text` 的 `sleep(0.6)` 等修飾鍵 → Quartz `CGEventSourceFlagsState` 輪詢（典型 50-150ms 解除）。Quick-Rewrite 的 `sleep(0.25)` + `sleep(0.2)` 同樣改 polling。Overlay 過場 `sleep(0.4)` 移除。
- **AXValue 補刀邏輯修復**：原本長文 Quartz 成功後還補一次 AXValue 會把編輯器既有內容清空只剩貼上的字。現在只在 Quartz + osascript 都失敗才走 AXValue。
- **剪貼簿還原 3s → 1.5s + NSPasteboard.changeCount() race-free 守門**：使用者期間動過剪貼簿（即使內容碰巧相同）也不會被誤覆蓋。

### 🎮 工作流摩擦解除（macOS）
- **Retry hotkey** `right_option+y`：用 cache 的 raw STT 重跑 LLM，跳過 STT 階段（省 1.5s），不用重錄就能換一版輸出。
- **Cancel hotkey** `right_option+x`：錄音中按下 = 立刻丟棄音訊；處理中按下 = paste 階段自動跳過。Pipeline 已開始的 LLM call 會跑完但結果不貼。

### 👀 處理視覺化（macOS）
- **Overlay 階段化**：原本只有一個「處理中…」label，現在會依管線進度切換 `🎧 辨識中` → `✨ 整理中` → `📋 貼上中`，三語都有。
- 多 race 防護：`_pending_stage_prefix` 在 init / done / idle / recording / show_transcript 都會清，避免異步主執行緒排程跟背景 stage 設定的 race。

### 🛡️ 生產級信任修復（三平台）
- **LLM 尾部幻覺截斷**（macOS + iOS + Android）：偵測「raw 內容完整保留 + LLM 在結尾自己接話加新句子」的補寫型幻覺，自動截斷而非整段捨棄。例：raw 結尾「色色名稱不用到這麼大」，LLM 加上「，所以你看能不能調整。而且你仔細看，從」→ 自動截到「不用到這麼大。」
  - macOS 用 `difflib.SequenceMatcher` + OpenCC `s2twp` 雙向正規化，處理簡體 raw + LLM 繁化 + 擴寫的混合 case。
  - iOS 用 `String.range(of:options:.backwards)` 簡化版（暫無 OpenCC 依賴）。
  - Android 用 `String.lastIndexOf` + opencc4j `ZhConverterUtil.toTraditional` 同樣雙向正規化。
- **Mode gating**：只在 dictate mode 套用截斷，edit mode（Quick-Rewrite / 翻譯 / Email 草稿 / 語音指令改寫）跳過 — 改寫本來就是 LLM 應該加內容，截斷會誤毀正常輸出。

### 🔧 內部優化
- HTTP client cache（macOS）：5 個雲端 LLM/STT client 連線重用，每次省 200-500ms TCP/TLS handshake。
- Signal handler（macOS）：SIGINT/SIGTERM/atexit 乾淨關閉 PortAudio 串流，不再殘留 leaked semaphore。
- Anthropic 連線預熱（macOS）：啟動時背景送 1 token ping，第一次正式錄音不付握手成本。
- `_should_skip_llm` 邏輯保留（不放寬，避免犧牲品質）。

### 📦 平台版本
- macOS: v2.2.0 (app.py + Dashboard footer)
- iOS: MARKETING_VERSION 2.2.0
- Android: versionName 2.2.0, versionCode 15

### 🤖 開發品質
- 4 輪 codex auto-review loop 攔下 10 個 bug（含 4 個 UI race、3 個 LLM 截斷 edge case、1 個 cancel flag 殘留、1 個 retry cache 時機、1 個 clipboard race）。沒一個 ship。
- 約 +494 行 / 4 個檔案（macOS app/transcriber/overlay/config）+ iOS/Android LlmClient 各 ~80 行。

## v2.1.0 (2026-04-29) — Personalization & Productivity Release

- **個人化 Few-shot 後處理**：LLM 後處理會注入最近 3 筆 `whisper_raw → final_text` 歷史範例，5 個引擎統一支援，rewrite API 會自動跳過。
- **Dictionary 從歷史學習**：新增 `scripts/dictionary_promote_from_history.py` 與 `POST /api/dictionary/promote_from_history`，支援 dry-run / apply 兩段式流程與多重守門。
- **全域 Quick-Rewrite 熱鍵**：選取任意 App 文字後按 `right_option+r`，走 LLM fallback 鏈改寫並自動貼回。
- **連續錄音模式 + VAD 自動分段**：新增連續錄音 hotkey、voice/silence 邊界偵測、片段長度保護與尾端靜音裁切。
- **發布前穩定化**：修正連續模式切片呼叫 `transcribe()`；新增音訊品質前置守門、個人語氣 profile 生成 API/UI，以及場景/App 分層詞庫管理。
- **錄音檔搬離隱藏目錄**：`backup_audio_dir` 預設改為 `/Volumes/Satechi_SSD/voice-input/audio_backup`，SSD 未掛載時自動略過備份。

## v2.0.0 (2026-04-25) — Cross-Platform Release Sync

- **三平台版本同步**：macOS App/DMG、iOS project、Android Gradle、README、Firebase Landing Page 全部升級至 `2.0.0`。
- **GitHub Release asset 命名統一**：DMG 產物改為 `SGH.Voice-2.0.0-apple-silicon.dmg`，與 Release 下載 URL 格式一致。
- **RVC/TTS 工具鏈整合**：加入 RVC 推論工作區、批次 TTS、Spotify post-copy、長篇語音生成與提示文字正規化腳本。
- **iOS Release build 修正**：SwiftUI `#Preview` 僅在 Debug 編譯，避免 production build 被 preview macro 擋住。
- **延續反幻覺管線**：保留 Claude Haiku 4.5 預設、Whisper prompt 注入、重複幻覺 sanitizer、短指令 skip LLM 等 v1.9.9 安全策略。

## v1.9.9 (2026-04-19) — Anti-Hallucination Overhaul

基於 762 筆真實歷史的差異分析（`whisper_raw` vs `final_text`），定位並修復了 LLM 後處理把指令當成對話回答的根本原因。

### 🎯 主因（已修復）
- **預設 LLM 從 Groq + `gpt-oss-120b` 切回 Claude Haiku 4.5**：歷史數據顯示 Groq 上跑 OpenAI 的開源 reasoning 模型 `gpt-oss-120b` 幻覺率 11.9%（35/295 筆），而 Claude Haiku 4.5 僅 2.5%（6/239 筆），差距 **4.7 倍**。reasoning 模型本質會「主動思考並重寫」輸入，不適合做純 transcoding。
- **Groq fallback 模型改回 `llama-3.3-70b-versatile`**：傳統 instruct 模型，服從性比 reasoning 模型穩定。

### 🛡️ 幻覺防護全面升級（`transcriber.py`）
- **Whisper STT 注入個人詞庫**：原本 `_local_stt` / `_groq_stt` / `_whisper_api_fallback` 三函數都用固定 prompt，**完全沒有調用 `memory.build_whisper_prompt()`**。現在會把 `custom_words` + 當前場景詞彙 + `BASE_CUSTOM_WORDS` 一起餵給 Whisper（≤20 詞、≤200 字元）。
- **三層幻覺檢測**：
  - 66 個對話起手詞（請提供／我來幫／您可以／Sure／Here is…）
  - 9 個中段助理句型（…，請提供…）
  - 字元 bigram 重疊率：< 30% 嚴判 / < 50% 配合 < 70% 縮減 / < 55% 配合 > 120% 擴寫
  - 統計樣本：幻覺平均重疊 37%，正常平均 76%，分離度極佳
- **Whisper 重複幻覺 Sanitizer**：正則 `(.{1,15}?)\1{4,}` 偵測連續重複片段，截斷到第一次出現（解決「11.11.11×30」、「財務所×16」類災難）。
- **短指令自動 Skip LLM**：≤60 字 + 全中日文 + 含動作詞（請繼續｜幫我｜你幫｜麻煩｜執行｜處理一下｜懂嗎…）→ 直接跳過 LLM，避免被誤當對話回答。
- **`_DICTATE_SYSTEM` 完全重寫**：1600 chars，移除舊版「條列呈現／長文整理」等誘導改寫字眼，改成嚴格 transcoder 風格 + 雙語明確示範 + 短文 ≤20 字「return as-is」規則。

### 💾 設定變更
- `~/.voice-input/config.json`：
  - `llm_engine`: `groq` → `claude`
  - `groq_model`: `openai/gpt-oss-120b` → `llama-3.3-70b-versatile`
  - `claude_system_prompt`: 用戶自訂 616 字版本（含自相矛盾規則）→ `""`（fallback 至新版 `_DICTATE_SYSTEM`）
  - `backup_audio_dir`: `""` → `~/.voice-input/audio_backup/`（為將來 CER 趨勢分析累積素材）
- 舊 config 自動備份至 `~/.voice-input/config.json.bak.<timestamp>`

### 📊 預期效益（基於 762 筆歷史回算）
| 指標 | 之前 | 現在 |
|------|------|------|
| LLM 幻覺率 | 11.9% (Groq+GPT-OSS) | 2.5% (Claude Haiku) |
| 已知 23 筆對話洩漏 | — | 攔截 21+/23 (markers) + bigram 補強 |
| Whisper 重複幻覺（3 筆/2 月）| 直接輸出 | Sanitizer 截斷 → 0 |
| 短指令誤判為對話 | 經常 | Skip 邏輯阻擋 |
| 體感速度 | 中位 1.46s | 中位 4.05s（trade-off）|

### 🚧 注意
- Claude 比 Groq 慢約 2.5 秒，但正確性大幅提升 — 對「頭痛」級的幻覺問題是值得的 trade-off。
- 若想恢復速度，可改回 `llm_engine=groq`，**但保持 `groq_model=llama-3.3-70b-versatile`**，千萬別再用任何 reasoning 模型（gpt-oss / qwen-qwq / deepseek-r1）做 transcoding。

## v1.4.0 (2026-03-17)

- **整合 MediaTek Breeze-ASR-25**：專為繁體中文 + 中英混用優化，Apple Silicon 上的推理速度比 Whisper-turbo 快 3.5 倍。
- **本地離線模型優化**：新增 4-bit 量化模型支援 (0.82 GB)，大幅降低記憶體占用並維持優異辨識率。
- **自動化監控與測試體系**：
  - `scripts/benchmark_models.py`：支援批次測試各模型的 CER (Character Error Rate) 與耗時。
  - `scripts/hf-model-watch.sh`：每日監控 HuggingFace 新 ASR 模型並推送通知。
  - `scripts/dict-update.py`：每週自動從 PMDA/MHLW 擷取最新醫療術語更新至個人詞庫。
- **系統任務管理**：新增 `scripts/install-launchd.sh` 方便一鍵安裝/卸載 macOS 背景監控任務。
- **三平台版本號同步**：將 macOS、iOS、Android 版本號一致升級至 `1.4.0`，Landing Page 補齊各平台下載連結。

## v1.3.0 (2026-03-17)

- **聲紋辨識 (Speaker Verification)**：新增純本地聲紋驗證模組，可有效過濾背景噪音與非本人的語音輸入。
- **LLM 引擎動態切換**：Dashboard 新增引擎選擇器，支援在 Ollama (本地)、Claude、OpenAI 之間快速切換。
- **聲紋前置過濾 (Step 0.5)**：在辨識前先比對音訊特徵，非本人聲音直接丟棄，防止 Whisper 產生重複字元幻覺。
- **UI 強化與狀態顯示**：Dashboard 設定頁加入聲紋狀態指示（維度、檔案大小）、相似度閾值滑桿與聲紋重置功能。
- **基礎架構優化**：修復 `config.py` 中的路徑映射邏輯，並強化 LLM 超時處理機制。

## v1.2.1 (2026-03-03)

- 新增 Dashboard「詞庫學習懸浮提示」：新增詞彙、新增/更新修正規則時，右上角即時浮窗提示使用者。
- 懸浮提示支援多語系（zh-TW / ja / en / ko / th / vi）並加入短時間去重，避免重複洗版。
- 更新 macOS App / DMG 版本號至 `1.3.0`（`build.sh` / `voiceinput.spec` / README / Firebase 下載頁）。
- iOS / Android 不新增此懸浮提示（維持現有行為）。

## v1.2.0 (2026-03-03)

- 修復 Dashboard `static/index.html` 內的 JavaScript 語法錯誤，避免頁面因 i18n 區塊錯置而無法載入。
- 補齊越南語 (`vi`) i18n 字串到正確語言物件，避免翻譯鍵缺失。
- 調整本地 Ollama LLM timeout 策略：從固定短超時改為可配置（`local_llm_timeout_sec`，預設 6 秒）。
- 新增 Ollama timeout 退避與警告節流，降低連續 fallback 造成的重複錯誤訊息。
- 升級 macOS App/DMG 版本號至 `1.2.0`（`build.sh` / `voiceinput.spec` / README 下載指引）。
