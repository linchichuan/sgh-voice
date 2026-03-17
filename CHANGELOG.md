# Changelog

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
