# Voice Input Improvement Loop

## Loop Protocol (gstack SELECTIVE EXPANSION)

### 10-Star Thinking
Before implementing, ask yourself:
- 5-star: Does the basic job. Checks the box.
- 10-star: Delights users, solves the deeper need, sets up future features.
Always aim for 10-star.

### Completeness Principle
AI makes implementation 10-100x faster. Never ship a simplified version
when the complete solution is within reach. 150 lines done right > 80 lines half-done.

### Task Selection
Pick the ONE task with highest user impact, not the easiest.
Check each role's "Next Ideas" for higher-impact alternatives.

---

## Project Context

- **What**: AI 語音輸入工具（macOS），Whisper STT + LLM 後處理，替代 Typeless
- **Users**: 林紀全（新義豊 CEO），日常三語混合（中/日/英）語音輸入
- **Stack**: Python 3.12+, Flask, mlx-whisper, OpenCC, Ollama/Groq/Claude/OpenAI/OpenRouter
- **Branch**: main
- **Build**: `python3 -c "import ast; ast.parse(open('config.py').read()); ast.parse(open('transcriber.py').read()); ast.parse(open('dashboard.py').read()); ast.parse(open('app.py').read()); ast.parse(open('memory.py').read()); print('OK')"`
- **Language**: 繁體中文（UI / 註解 / commit message），程式碼英文

### Rules
1. **所有中文必須是繁體中文**，不允許簡體中文
2. 不得破壞現有 5 層管線（Whisper → 詞庫修正 → Smart Replace → LLM → OpenCC）
3. Dashboard UI 必須維持 6 語言 i18n（繁中/日/英/韓/泰/越南）
4. API Key 在 GET /api/config 必須遮蔽中間部分
5. 不得引入新的重量級依賴（PyTorch, TensorFlow 等），保持輕量打包
6. config.json 格式必須向下相容（新欄位需有合理預設值）
7. 所有修改完成後，也要同步更新 CLAUDE.md 對應的段落

### Auto-Evolution Integration
每次迴圈開始前，先執行原有的自動進化流程：
1. `bash scripts/maintenance_loop.sh 2>&1 | tail -20`
2. 讀取 `~/.voice-input/auto_triage_report.md`，將修正建議寫入詞庫
3. 確認 `~/.voice-input/dictionary.json` 合法 JSON

---

## Roles & Rotation

Rotation order (advance to next after each task):
**品質工程師 -> UX 設計師 -> 效能工程師 -> 安全工程師 -> (repeat)**

One full rotation = 1 cycle. Increment cycle number when last role completes.

---

## Current Pointer

Next: **安全工程師** (role 4) | Cycle 2

---

## Completed

| Date | Role | Summary | Files | Result |
|------|------|---------|-------|--------|
| 2026-03-31 | 品質工程師 | 建立 _DICTATE_SYSTEM prompt 自動化品質測試（5 樣本 × 7 檢查規則），發現翻譯問題：Groq Llama 違反「禁止翻譯」規則（中→日、英→中） | `scripts/test_prompt_quality.py`, `test/results/PROMPT_QUALITY.md` | pass (3/5 樣本通過, 16/18 檢查通過) |
| 2026-04-02 | UX 設計師 | Dashboard 加入「測試 LLM 連線」按鈕：後端 POST /api/test-llm 支援 5 引擎，前端即時顯示延遲與模型，6 語言 i18n | `dashboard.py`, `static/index.html` | pass |
| 2026-04-02 | 效能工程師 | OpenRouter 基準測試：6 模型 × 3 樣本實測。🥇Nemotron Nano 1.62s、移除已下架模型（Qwen 30B MoE/DeepSeek V3/Gemini）、預設改為 Nemotron | `scripts/benchmark_openrouter.py`, `config.py`, `transcriber.py`, `static/index.html` | pass |
| 2026-04-02 | 安全工程師 | API Key 安全加固：config.json 強制 chmod 600、資料目錄 chmod 700、POST /api/config 加入 dict 驗證 + 白名單欄位過濾 | `config.py`, `dashboard.py` | pass |
| 2026-04-02 | 品質工程師 | LLM fallback 鏈修正：(1) `llm_engine` 加入 DEFAULT_CONFIG 防被白名單丟棄 (2) Ollama fallback 在非 Hybrid 模式下也可觸發 | `config.py`, `transcriber.py` | pass |
| 2026-04-02 | UX 設計師 | Dashboard 概覽頁新增引擎狀態列：即時顯示 STT 引擎、LLM 引擎+模型、使用場景，6 語言 i18n | `static/index.html` | pass |
| 2026-04-03 | 品質工程師 | 修復 4 個 bug：warmup_kwargs typo、get_service_status 缺失、openai_model/app_styles 白名單缺漏；README 三語版本號升至 v1.6.5 | `transcriber.py`, `config.py`, `dashboard.py`, `README*.md` | pass |
| 2026-04-03 | 效能工程師 | LLM 路由智慧化：短句（≤30字）優先 Ollama→Groq，長文依 pref_engine 走旗艦，大幅降低短句 API 成本 | `transcriber.py` | pass |

---

## Failed

| Date | Role | Attempted | Reason |
|------|------|-----------|--------|

---

## Tasks by Role

### 品質工程師
**Focus**: 辨識品質、LLM 後處理準確度、錯誤處理

**Pending**:
- ~~為 _DICTATE_SYSTEM prompt 建立自動化品質測試~~ done（發現翻譯問題，Groq Llama 對語言一致性指令遵從度不足）
- ~~檢查 LLM fallback 鏈完整覆蓋~~ done（修復 `llm_engine` 未在 DEFAULT_CONFIG + Ollama 非 Hybrid 失效兩個 bug）
- history.json 的 threading lock 是否有 deadlock 風險（高併發場景）

**Next Ideas**: LLM 幻覺偵測強化（目前只檢查自我介紹特徵詞，可加入更多 pattern）

### UX 設計師
**Focus**: Dashboard 使用體驗、設定流程、視覺回饋

**Pending**:
- ~~Dashboard 設定頁加入「測試連線」按鈕~~ done（POST /api/test-llm，5 引擎皆支援，顯示延遲+模型名稱）
- 設定儲存後加入引擎狀態即時更新（目前只有 toast）
- ~~Dashboard 首頁引擎狀態即時顯示~~ done（STT/LLM/場景三欄狀態列，讀取 /api/config 渲染）

**Next Ideas**: 深色/淺色主題切換、行動裝置響應式佈局優化

### 效能工程師
**Focus**: 延遲優化、資源使用、Token 成本

**Pending**:
- ~~OpenRouter 免費模型延遲基準測試~~ done（🥇Nemotron Nano 1.62s，移除 3 個已下架模型，預設改為 Nemotron）
- ~~LLM 路由智慧化~~ done（短句≤30字走 Ollama→Groq，長文走 pref_engine 旗艦）
- Whisper 預熱時間優化（目前 sleep(3) 等待 UI，可改為事件驅動）

**Next Ideas**: 串流式 LLM 回應（邊生成邊貼上）、模型自動降級（延遲超標時自動切換輕量模型）

### 安全工程師
**Focus**: API Key 安全、輸入驗證、資料保護

**Pending**:
- ~~審計 API Key 存取路徑 + config.json 權限加固~~ done（chmod 600/700 + POST 白名單過濾）
- ~~Dashboard API endpoint 輸入驗證~~ done（dict 類型檢查 + DEFAULT_CONFIG 白名單）
- OpenRouter API Key 格式驗證（sk-or- 前綴檢查）

**Next Ideas**: config.json 加密儲存（目前明文）、API 呼叫 audit log
