# SGH Voice — 自動進化指令 (Autonomous Evolution Loop)

Agent 讀取背景任務（maintenance_loop.sh）產出的診斷報告，將分析結果轉化為實際代碼修改。

啟動方式：`/loop "cat LOOP.md"`

---

## Step 1: 執行維護腳本 & 讀取報告

```bash
bash scripts/maintenance_loop.sh 2>&1 | tail -20
```

讀取產出的報告：
- `~/.voice-input/auto_triage_report.md` — 歷史錯誤分析
- `.kiro/specs/auto-upgrade-status.md` — 整體狀態

如果兩個檔案都不存在或內容為空，跳過後續步驟並回報「無需更新」。

## Step 2: 知識層更新（詞庫修正）

根據 auto_triage_report.md 中的 `A -> B` 替換建議：

1. 讀取 `~/.voice-input/dictionary.json`
2. 將新規則合併至 `corrections` 區塊
3. 衝突檢查：新規則不可與現有規則重複或矛盾
4. 繁中檢查：所有中文必須是繁體中文
5. 安全原則：若規則有歧義（例如同音異義詞），跳過並標記，不強行寫入

## Step 3: 領域辭書同步

檢查 `scripts/dict-update.py` 是否產出新的醫療術語：

1. 讀取 `~/.voice-input/dictionary.json` 的 `auto_added` 列表
2. 將新術語合併至 `custom_words`
3. 去重處理：確保詞庫不膨脹

## Step 4: 模型與參數優化

檢查 auto-upgrade-status.md 的模型評估部分：

1. 若 `hf-model-watch` 發現新模型且效能優於現行模型 → 更新 `config.py:LOCAL_MODEL_PATHS`
2. 若報告指出 LLM 在特定場景表現不佳 → 微調 `config.py:SCENE_PRESETS` 提示詞
3. 不做大規模重構，只做 Surgical Updates

## Step 5: 驗證 & 紀錄

1. 確認 `~/.voice-input/dictionary.json` 是合法 JSON
2. 確認 `config.py` 無語法錯誤：`python3 -c "import config"`
3. 將變更摘要附加至 `CHANGELOG.md` 的「自動進化紀錄」區塊，格式：

```markdown
### Auto-Evolution (YYYY-MM-DD)
- 新增修正規則 N 條：...
- 新增詞彙 N 個：...
- 模型/Prompt 調整：...
```

## Agent 行為準則

1. **Surgical Updates** — 只改必要的，不大規模重構
2. **Safety First** — 不確定的規則寧可跳過，標記在報告中
3. **繁體中文第一** — 所有中文輸出必須繁體
4. **冪等性** — 重複執行不應產生重複規則或副作用
