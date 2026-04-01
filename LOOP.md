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

Next: **UX 設計師** (role 2) | Cycle 1

---

## Completed

| Date | Role | Summary | Files | Result |
|------|------|---------|-------|--------|
| 2026-03-31 | 品質工程師 | 建立 _DICTATE_SYSTEM prompt 自動化品質測試（5 樣本 × 7 檢查規則），發現翻譯問題：Groq Llama 違反「禁止翻譯」規則（中→日、英→中） | `scripts/test_prompt_quality.py`, `test/results/PROMPT_QUALITY.md` | pass (3/5 樣本通過, 16/18 檢查通過) |

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
- 檢查所有 LLM 函數的 fallback 鏈是否完整覆蓋（特別是 OpenRouter 新加入後的邊界情況）
- history.json 的 threading lock 是否有 deadlock 風險（高併發場景）

**Next Ideas**: LLM 幻覺偵測強化（目前只檢查自我介紹特徵詞，可加入更多 pattern）

### UX 設計師
**Focus**: Dashboard 使用體驗、設定流程、視覺回饋

**Pending**:
- Dashboard 設定頁 OpenRouter 模型選擇：加入「測試連線」按鈕，一鍵驗證 API Key + 模型是否可用
- 設定儲存後加入引擎狀態即時更新（目前只有 toast）
- Dashboard 首頁加入當前 LLM 引擎 + 模型的即時狀態顯示

**Next Ideas**: 深色/淺色主題切換、行動裝置響應式佈局優化

### 效能工程師
**Focus**: 延遲優化、資源使用、Token 成本

**Pending**:
- OpenRouter 免費模型延遲基準測試：自動測試 3 個極速模型的平均回應時間，產出報告
- LLM 路由智慧化：根據文字長度自動選擇模型（短句用小模型、長文用大模型）
- Whisper 預熱時間優化（目前 sleep(3) 等待 UI，可改為事件驅動）

**Next Ideas**: 串流式 LLM 回應（邊生成邊貼上）、模型自動降級（延遲超標時自動切換輕量模型）

### 安全工程師
**Focus**: API Key 安全、輸入驗證、資料保護

**Pending**:
- 審計所有 API Key 存取路徑，確保 config.json 的檔案權限正確（600）
- Dashboard API endpoint 輸入驗證（POST /api/config 的 data 類型檢查）
- OpenRouter API Key 格式驗證（sk-or- 前綴檢查）

**Next Ideas**: config.json 加密儲存（目前明文）、API 呼叫 audit log
