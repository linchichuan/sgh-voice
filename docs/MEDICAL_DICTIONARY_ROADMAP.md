# SGH Voice 醫療詞庫分階段規劃

> 狀態：規劃文件，**本輪不實作**
>
> 基準日期：2026-07-30
>
> 適用範圍：Android、iOS、macOS 語音輸入流程

## 1. 決策摘要

現階段不應把完整醫療詞表直接塞進 Whisper 或 LLM prompt。大型固定詞表會增加短音訊、低音量及非醫療場景誤植詞彙的風險，也會放大手機端記憶體、啟動時間及三端行為不一致的問題。

建議採用「版本化詞庫 + 科別／租戶／語言分片 + 每次只選少量詞彙注入」：

1. 詞庫可以比 prompt 大，但每次只載入使用情境需要的 shard。
2. ASR 前只注入使用者固定詞與目前場景的少量高順位詞。
3. ASR 後以索引找出可能相關的 alias，再做可回溯、非連鎖的確定性修正。
4. 高風險或有歧義的醫療詞不做模糊自動替換，只提供候選或維持原文。
5. 所有共用／租戶醫療詞都必須有人工作業、來源與版本紀錄，不能由自動學習直接升級。

醫療詞庫只是一項語音辨識與拼寫輔助，不代表醫療內容正確、臨床可用或任何法規要求已滿足；正式導入前仍需由各租戶指定的人員完成領域、語言與使用流程驗證。

## 2. 現況基線

### 2.1 三端既有結構

| 平台 | 詞彙來源與持久化 | Prompt 現況 | 修正現況 | 已知差異 |
|---|---|---|---|---|
| macOS（Python） | `BASE_CUSTOM_WORDS`、`SCENE_PRESETS`、設定檔詞彙、個人手動詞彙；JSON 保存 global／scene／app correction | 明確優先序為設定詞彙 → 個人手動 → scene → base；硬上限 20 詞／200 字；不會截斷單一詞 | base → 使用者 scene → 內建 scene → app → 使用者 global；長詞優先；有自動學習守門 | 已有 `medical`，另有以 edit mode 處理的 `medical_consultation`／SOAP 場景 |
| Android | base、scene、使用者自訂詞；`SharedPreferences`；另有 personalization repository | 使用者詞 → scene → base；上限 50 詞／800 字 | base → scene → 使用者 → learned；`TextCorrectionEngine` 為單次非連鎖、長詞優先，ASCII 有單字邊界 | mobile 上限高於 macOS；learned correction 優先級最高 |
| iOS | base、scene、使用者自訂詞；`UserDefaults` | 先放進 `Set` 再取 50 詞／800 字，因此順位不穩定，且 800 字截斷可能切到詞中間 | base → scene → 使用者；依長度逐條 `replacingOccurrences` | 尚無 Android 的非連鎖／ASCII 邊界保護，也沒有相同的 learned、scene／app 層 |

現有 medical scene 都是小型靜態清單，包含檢查、科別、藥品、生技及繁中醫療詞。macOS 的 `medical_consultation` 是內容重整指令，不是一般詞庫；未來也應維持「詞彙辨識」與「SOAP 摘要」兩條不同管線。

### 2.2 現有測試可作為後續基線

- macOS 測試已驗證去重、手動詞優先、20 詞／200 字上限、不可截斷單詞、scene 覆蓋層與 medical scene schema。
- Android 測試已驗證最長匹配、非連鎖替換、ASCII 單字邊界及翻譯流程只對來源文字套一次詞庫修正。
- iOS 已有口述／翻譯不得回答使用者問題的安全測試，但尚缺 DictionaryManager 的順位、上限、非連鎖與邊界 parity 測試。

### 2.3 導入前必要前置

醫療詞庫 MVP 開始前，三端必須先建立同一份可測試的詞庫契約：

- 相同的 layer 名稱與覆蓋順序。
- 相同的 prompt budget 與「不可截斷詞」規則。
- 相同的 Unicode normalization、大小寫及 ASCII 邊界規則。
- 相同的歧義處理、非連鎖替換及停用規則。
- dictation、translation、edit／SOAP 三種任務不得混用詞庫行為。

若未先完成 parity，增加詞彙量只會讓三端輸出差異更難追查。

## 3. 目標與非目標

### 3.1 目標

- 降低經人工驗證的醫療專有詞、檢查名、科別名與縮寫之辨識／拼寫錯誤。
- 支援繁體中文、日文、英文及後續韓文的獨立選擇與混合使用；實際啟用語言由客戶／使用者選擇，不由系統強制猜測。
- 讓不同診所、醫療機構或團隊擁有隔離的 tenant overlay，不污染共用詞庫。
- 在離線或遠端服務不可用時，仍可使用最後一個已驗證版本。
- 每一筆共用或租戶詞彙都能回答「來自哪裡、誰核准、何時生效、如何撤回」。
- 在不顯著增加 prompt、延遲、記憶體及幻覺風險的前提下，取得可量測的改善。

### 3.2 非目標

- 不建立完整醫學知識圖譜或把所有醫學術語載入裝置。
- 不做診斷、用藥建議、劑量判斷、禁忌檢查、療效推論或任何臨床決策支援。
- 不因為詞庫命中就改變、補寫或回答口述內容。
- 不把一般口述中的問題當成指令；「系統直接回答」屬 dictation／translation contract 問題，不能靠醫療詞庫解決。
- 不在未明確要求翻譯時翻譯藥名、醫療術語或縮寫。
- 不以患者姓名、病歷、錄音、診斷內容或其他個人資料建立共用詞庫。
- 不自動抓取公開網站後直接發布；公開可讀不等於可自由重製或商用。
- 不在 MVP 對接電子病歷、醫院主資料或院內身份系統。

## 4. 建議目標架構

```text
版本化來源資料
    ↓ 來源／授權／人工審核
common shard + specialty shard + tenant overlay + user layer
    ↓ 依租戶、科別、語言、版本選擇
本機索引與 last-known-good cache
    ├─ ASR 前：少量 pinned／高順位詞 → vocabulary prompt
    ├─ ASR 後：文字正規化 → alias 檢索 → 確定性修正
    └─ LLM：同一份精簡 canonical vocabulary，僅允許修正明顯同音誤辨
    ↓
輸出驗證、版本記錄、可回滾結果
```

### 4.1 Layer 與覆蓋順序

建議跨平台統一為：

1. `base`：產品必要的低風險基礎詞。
2. `common-medical`：跨科別且已審核的通用醫療詞。
3. `specialty`：目前科別 shard。
4. `tenant`：該租戶正式用語、院內系統名與經審核別名。
5. `user-manual`：使用者明確新增的個人詞與 correction，最高優先。

`user-learned` 不得直接覆蓋共用、科別或租戶醫療規則。它只能：

- 留在個人隔離層；
- 通過現有 meaningful-correction 守門；
- 遇到藥名、劑量／單位、方向性、否定詞或歧義縮寫時停止自動套用；
- 若要升級為 tenant 或共用規則，必須重新走人工審核。

同一 alias 若在有效 shards 對應到不同 canonical term，應標記為 `ambiguous`，不得做確定性替換。

### 4.2 建議資料模型

每一個 bundle 應為不可變、可版本化資料，最少包含：

```json
{
  "schema_version": 1,
  "bundle_version": "2026.07.30-rc1",
  "tenant_id": "common-or-opaque-tenant-id",
  "specialty": "general-medical",
  "language": "ja-JP",
  "generated_at": "ISO-8601",
  "source_manifest_version": "opaque-version",
  "terms": [
    {
      "term_id": "opaque-stable-id",
      "canonical": "canonical spelling",
      "aliases": ["verified spoken or ASR variant"],
      "term_type": "exam|department|medication|anatomy|acronym|organization",
      "languages": ["ja-JP"],
      "specialties": ["general-medical"],
      "priority": 50,
      "case_sensitive": false,
      "auto_replace": false,
      "risk_class": "normal|ambiguous|high",
      "status": "reviewed",
      "source_ids": ["source-record-id"],
      "reviewed_by": ["role-or-review-id"],
      "reviewed_at": "ISO-8601"
    }
  ]
}
```

來源 manifest 另行保存：

- 來源名稱與正式 URL／文件識別碼。
- 取得日期、版本或發布日期。
- 使用條款、授權範圍及內部判定紀錄。
- 允許的用途、地域、期限及再散布限制。
- 資料 owner、審核者與更新週期。
- 撤回或過期條件。

bundle 不應包含完整來源文件、患者原文、API key、token 或其他 secret。

### 4.3 分片策略

建議 shard key：

```text
tenant_id / specialty / language / bundle_version
```

分片維度：

- **科別**：先從 `general-medical` 起步，再依實際 pilot 增加內科、皮膚科等；不要預先建立沒有測試語料與 reviewer 的科別。
- **租戶**：`common` 只放跨租戶通用詞；院內稱呼、產品名、系統名放在 tenant overlay。
- **語言**：`zh-Hant-TW`、`ja-JP`、`en`、`ko-KR` 分開；共用拉丁縮寫可放 `mixed-latin`，但仍需標示適用語言。
- **詞類**：不必成為獨立實體 shard，但須可過濾 medication、exam、department、acronym 等類別。

繁中、日文、英文可利用現有三語基線先做 MVP。韓文只有在有合法資料來源、韓語 reviewer 與測試集後才啟用；UI 的語言選擇與詞庫啟用狀態必須分開呈現，避免讓使用者誤以為選到鍵盤語言就代表已有相同品質的醫療詞庫。

## 5. 資源與 Prompt 上限

以下是第一版工程 guardrail，不是永久產品規格。任何提高上限的變更都必須附裝置 profiling 與負向語料結果。

### 5.1 Vocabulary prompt

- 三端統一硬上限：**20 個完整詞、200 個 Unicode 字元**。
- 此上限包含 user、tenant、specialty、common 與 base 的總和，不是各 layer 各有 20 個。
- 不得在 200 字邊界切斷單一詞；放不下就跳過該詞。
- ASR 與 LLM 若都需要 canonical vocabulary，應重用同一選取結果，不再各自擴張。
- 固定 medical policy prompt 建議不超過 **500 字元**，只描述保留原文與不得推測等規則，不列出整份詞表。
- translation target 不得套用來源語言 correction；只有明確翻譯任務才可使用經審核的 target terminology mapping。

初始欄位配額：

| 優先層 | 每次保留上限 | 說明 |
|---|---:|---|
| user-manual／pinned | 8 詞 | 使用者明確指定，最高優先 |
| tenant | 4 詞 | 當前租戶正式名稱與高頻術語 |
| specialty／common-medical | 6 詞 | 依場景、近期使用與 ranking 選取 |
| base | 2 詞 | 僅補剩餘位置 |

若高優先層未用滿，名額可往下流；任何情況仍不可超過 20 詞／200 字。

### 5.2 Bundle、索引與快取

每個 active shard 的初始上限：

- 最多 5,000 個 canonical terms。
- 最多 10,000 個 aliases。
- 壓縮後最多 2 MB。
- 單一裝置同時在記憶體維持最多 3 個 shards。
- 詞庫索引新增記憶體以 20 MB 為初始上限。
- 本機保留 active 與上一個 last-known-good 版本，其他版本由受控清理移除。

超過任一上限時，不得直接放寬；應先再拆 specialty／language shard 或改善索引格式。

### 5.3 每次請求的處理預算

- ASR 前 ranking 只產生最多 20 詞。
- ASR 後 alias retrieval 最多回傳 50 個候選，再由確定性規則縮減。
- 詞庫造成的額外 p95 延遲目標不超過 50 ms；純 retrieval p95 目標不超過 30 ms。
- 不得為了 ranking 上傳完整原始錄音、患者文字或前景 App 內容。
- 短音訊、靜音與低音量必須走負向測試；不能因為開啟 medical shard 就輸出未口述的醫療詞。

## 6. 檢索與快取策略

### 6.1 ASR 前

ASR 前還沒有 transcript，不能做真正的語意檢索。選詞只能根據：

- 使用者選擇的輸入語言。
- 使用者／租戶選擇的 active specialty。
- 使用者 pinned terms。
- 該租戶近期已驗證的詞頻；只保留去識別化計數，不保留患者句子。
- 詞彙的人工 priority、版本與停用狀態。

不要把當前 App 名稱、剪貼簿或輸入框全文預設送到遠端做選詞。

### 6.2 ASR 後

建議流程：

1. 對 transcript 做 NFC normalization、大小寫與標點的受控正規化。
2. 以 exact alias map、前綴／n-gram index 找候選。
3. 只有唯一且已核准 `auto_replace=true` 的 alias 才做確定性替換。
4. Android 現有的「長詞優先、單次非連鎖、ASCII 單字邊界」作為跨平台最低行為。
5. 模糊比對只能用於候選排序或人工建議，不得自動替換高風險詞。
6. correction 後再執行一次 locked output validation，避免 LLM 把 canonical term 改回去或新增未出現內容。

劑量、單位、左右側、陽性／陰性、否定詞、容易混淆的縮寫與相似藥名預設 `auto_replace=false`。

### 6.3 Cache

- 記憶體使用 LRU，key 為完整 shard key；最多 3 個 active shards。
- 磁碟只保存版本化 bundle、索引、checksum、狀態與 last-known-good 指標。
- bundle 更新應先下載至 staging、驗證 schema／checksum／授權狀態，再原子切換 active pointer。
- 遠端不可用或新版本驗證失敗時，繼續使用 last-known-good，不得改成空詞庫後靜默輸出不同結果。
- tenant 切換時清除上一租戶的記憶體 cache；隔離測試需證明無跨租戶命中。
- ranking cache 不保存原始患者句子；如需近期詞頻，只保存 term ID 與受限計數。

## 7. 資料來源治理與授權

### 7.1 來源接受原則

優先評估：

- 官方公開名錄、產品正式標示或主管機關正式資料。
- 租戶自行擁有且明確授權本系統使用的院內術語表。
- 授權條款允許目前用途、地域、裝置散布與衍生索引的資料集。

以下情況不得匯入：

- 無法確認授權或禁止再散布／商業使用。
- 來源只有網頁可存取，但沒有足以支持重製及打包的權利依據。
- 第三方付費詞庫、標準術語或分類系統未取得所需合約。
- 從患者紀錄、客服紀錄、醫師口述或錄音直接擷取且未完成適當授權、去識別與審核。
- 無來源、無版本、無 reviewer 或由模型自行生成的「看起來合理」術語。

現有 `scripts/dict-update.py` 類型的抓取流程可作為候選收集工具，但候選不得自動進入 production bundle；每一個實際來源仍須個別確認使用條款、資料品質與更新責任。

### 7.2 審核狀態

```text
candidate → source-verified → language-reviewed → domain-reviewed
          → staged → active → deprecated／revoked
```

- `candidate` 不可進入 runtime。
- 一般詞至少需語言 reviewer 與資料 owner 核准。
- medication、劑量／單位、歧義縮寫等高風險類別需再由租戶指定的領域 reviewer 核准。
- reviewer 身份可以記錄為內部 role／ID，不需將個人資料打包到裝置。
- 每次修改 canonical、alias、auto-replace 或 risk class 都產生新版本，不原地覆寫已發布 bundle。

### 7.3 安全輸入檢查

匯入時至少拒絕：

- 空字串、控制字元、異常超長詞、整句指令或 prompt 片段。
- alias 與 canonical 完全相同的無效 correction。
- 同一範圍內一個 alias 對應多個 canonical 而未標記歧義。
- 包含患者識別資料、聯絡方式、帳號、token 或其他 secret。
- 缺少來源、授權狀態、語言、版本或 reviewer 的資料。

## 8. 人工驗證、發布與回滾

### 8.1 驗證資料

每個 shard 至少需要：

- 正向語料：該詞在自然句、不同說話者、速度與口音中的錄音。
- 混語語料：繁中／日／英及後續韓文 code-switch。
- 近音負例：相似一般詞、相似藥名或縮寫。
- 非醫療負例：一般工作、聊天、地址、品牌及技術詞。
- 靜音、短音訊、低音量及背景噪音。
- dictation 問句／命令句，確認系統保持 transcript 而不是回答。
- translation 測試，確認來源 correction 不會污染目標語言。

測試集應去識別、取得適當使用權，且 release set 不得同時用於調整 ranking 權重。

### 8.2 發布流程

1. 產生 immutable release candidate 與 source manifest。
2. 執行 schema、重複、歧義、prompt budget 與跨平台 golden tests。
3. 語言／領域 reviewer 簽核。
4. 在非正式患者工作流的 opt-in pilot 使用。
5. 觀察負向插入、人工回改、延遲、記憶體與 crash。
6. 逐租戶啟用；不可一次全量推送。
7. 保存 release report、版本與回滾結果。

### 8.3 回滾

- 每個 tenant／specialty／language shard 可獨立停用或 pin 舊版。
- active bundle 與 last-known-good bundle 都需可在離線狀態切換。
- 回滾不得刪除使用者自己的 manual words；只停用有問題的共用／科別／租戶版本。
- bundle 進入 `revoked` 後，清除相關記憶體 cache，禁止下次啟動重新載入。
- 每個 release candidate 必須先做一次 rollback drill，未成功不得發布。
- 緊急停用應支援整個 medical layer 與單一 term／alias 兩種粒度。

## 9. 品質指標與發布門檻

### 9.1 核心品質指標

| 指標 | 定義 |
|---|---|
| Medical Term Error Rate（MTER） | 已標註醫療詞 span 中的遺漏、錯字及錯詞比例 |
| Term precision／recall | 輸出的 canonical term 是否真的被口述，以及應辨識的詞是否被保留 |
| False medical insertion rate | 原音訊未出現，但輸出新增醫療詞的比例 |
| Harmful substitution rate | 藥名、數值、單位、側別、否定或歧義縮寫被改錯的比例 |
| Script preservation | 繁中、日文、英文、韓文原有 script span 是否被不當翻譯或轉寫 |
| User revert rate | 使用者將詞庫修正結果改回或刪除的比例 |
| No-answer contract rate | 口述問句／指令句被當成 transcript，而不是收到系統回答的比例 |
| Runtime overhead | 詞庫造成的 p50／p95 延遲、記憶體、bundle 大小、crash |
| Isolation | tenant A 的詞是否可能在 tenant B 命中 |

### 9.2 初始 go／no-go 門檻

下列數值是 pilot 工程門檻，不代表正式環境的醫療準確性保證：

- held-out 正向測試的 MTER 相對 baseline 至少下降 15%。
- false medical insertion rate 不得比 baseline 增加超過 0.1 個百分點，且負向測試絕對值不超過 0.5%。
- 固定 release validation set 中，harmful substitution 必須為 0；這只代表測試集通過，不代表正式使用零風險。
- mixed-language script preservation 不得比 baseline 下降超過 0.5 個百分點。
- 詞庫額外 p95 延遲不超過 50 ms、索引額外記憶體不超過 20 MB。
- tenant isolation、bundle rollback、revoked term 停用測試必須全部通過。
- dictation／translation 的 no-answer contract 不得因 medical prompt 或 vocabulary 發生回歸。

樣本太少、信賴區間過寬或測試語料不具代表性時，不得以表面達標判定可發布。

## 10. 分階段路線圖

### 10.1 MVP：小型、靜態、可撤回的 pilot

**範圍**

- 一個 opt-in pilot tenant。
- 一個 `general-medical` specialty。
- 先支援現有主軸 `zh-Hant-TW`、`ja-JP`、`en`。
- 最多 300 個 canonical terms、600 個人工驗證 aliases。
- 先納入科別、檢查名、組織名及低歧義縮寫；medication 預設只做 canonical prompt bias，不啟用模糊 auto-replace。
- 使用本機版本化 bundle，不做即時 server retrieval。
- 無自動爬取發布、無跨租戶共享學習、無患者資料學習。

**必要工作**

- 寫出跨平台 Dictionary Contract 與 JSON schema。
- 讓三端 prompt 統一為 20 詞／200 字且不切詞。
- 把 Android 的非連鎖、長詞優先、ASCII 邊界行為做成跨平台 golden tests。
- 建立 baseline／held-out／negative audio corpus。
- 實作 bundle validator、source manifest、版本 pin 與手動 rollback。
- 完成 reviewer checklist 與 pilot 使用說明。

**MVP 退出條件**

- 三端 golden tests、品質門檻及 rollback drill 全部通過。
- 每筆 active term 有來源、授權狀態與 reviewer。
- pilot 沒有跨租戶資料流或患者資料寫入詞庫。
- 若達不到品質門檻，保留現有小型 static medical scene，不進 Phase 1。

### 10.2 Phase 1：科別與租戶分片

**範圍**

- 依真實需求擴充至最多 3 個 specialties。
- 增加 tenant overlay、版本化更新、staging 與 last-known-good cache。
- 有韓語資料來源、reviewer 與測試集時，才加入 `ko-KR` shard。
- 建立 exact alias／n-gram 本機索引與最多 50 候選的 post-ASR retrieval。
- 建立審核後的 term disable、bundle revoke、逐租戶 rollout。
- 只收集去識別的 term 命中、回改與效能指標。

**Phase 1 退出條件**

- 每個 specialty／language shard 都有獨立的正向與負向測試。
- tenant cache 切換與隔離測試通過。
- 更新、離線降級、單詞停用與整包回滾可操作。
- 維運團隊能在約定時間內處理來源更新、review queue 與緊急撤回。

### 10.3 Phase 2：受控擴展與更精細 ranking

**候選範圍**

- 在有明確需求與 reviewer 的前提下增加 specialties／languages。
- 以裝置端近期 term ID、使用者 pinned terms 及 specialty context 改善 ranking。
- 研究 phonetic index，但高風險詞仍不做未審核的模糊替換。
- 若確有必要，再評估隱私受控的 server-side retrieval；必須先完成資料最小化、保存期限、地域、租戶隔離與契約審查。
- 建立來源版本更新偵測、差異審核與自動產生 release candidate；發布仍需人工核准。

**Phase 2 不應改變的底線**

- 不把整份詞庫塞進 prompt。
- 不用模型自動發布 canonical term 或 correction。
- 不由詞庫提供診斷、用藥或劑量結論。
- 不以患者內容訓練或擴充共用詞庫。
- 不取消版本、審核、隔離及回滾機制。

## 11. 主要風險與對策

| 風險 | 可能影響 | 必要對策 |
|---|---|---|
| Prompt 過長 | 短音訊或低音量時誤植詞彙 | 20 詞／200 字硬上限、negative audio gate |
| 相似藥名／縮寫 | 改成另一個有效但錯誤的醫療詞 | 標記 high／ambiguous、預設不自動替換、領域 reviewer |
| 三端行為漂移 | 同一音訊輸出不同 | canonical contract、共享 fixtures、每版 parity report |
| iOS 連鎖替換／不穩定順位 | correction 被二次改寫、重要詞被擠掉 | MVP 前統一非連鎖 engine 與 deterministic priority |
| 自動學習污染 | 個人錯誤規則覆蓋正式詞 | learned layer 隔離，不得自動升級 medical layer |
| 授權不明 | 無法合法打包或商用 | source manifest、逐來源審核、無權利即拒絕 |
| 跨租戶洩漏 | 院內用語或資訊出現在其他客戶 | opaque tenant key、cache 清除、隔離測試 |
| 患者資料進入詞庫 | 隱私、保留與刪除風險 | 禁止原文學習，只允許 term ID／去識別計數 |
| 過期或撤回詞 | 舊名稱持續 bias 輸出 | immutable version、revoked 狀態、更新 owner、緊急停用 |
| 詞庫被當成知識庫 | LLM 補寫或回答醫療內容 | inert transcript contract、靜態短 policy、輸出 validator |
| 裝置資源不足 | 鍵盤卡頓、記憶體壓力、crash | shard 上限、LRU、profiling、超限再分片 |
| 沒有 reviewer 容量 | 候選堆積、錯誤無法及時撤回 | 明確 owner／SLA；容量不足時停止擴充 |

## 12. 暫停、回退或終止條件

出現以下任一情況，應停止擴大 rollout，回到 last-known-good 或關閉 medical layer：

- 無法證明主要資料來源的允許用途或再散布範圍。
- 發現患者資料、secret 或跨租戶資料進入 bundle、索引、cache 或 logs。
- 發生藥名、數值、單位、方向性、否定詞等重大錯誤，且無法以單詞停用立即隔離。
- false medical insertion 或 harmful substitution 未達門檻。
- 連續兩個 release candidate 無法在 held-out set 取得具意義的 MTER 改善。
- 詞庫造成的延遲、記憶體或 crash 回歸超過預算，且再分片後仍無法改善。
- rollback drill、last-known-good、tenant isolation 任一失敗。
- 沒有足夠的語言／領域 reviewer 或無法維持來源更新與撤回流程。
- medical prompt 使 dictation／translation 再度出現「回答問題」或補寫內容的回歸。

若小型、審核式詞庫仍無法比現有 static scene 帶來穩定改善，應終止大型詞庫方向，改採使用者 pinned terms、租戶小型正式詞表與改善 ASR 模型／音訊品質。

## 13. 實作前待決策清單

- 選定第一個 pilot tenant 與 `general-medical` 的具體使用流程。
- 指定資料 owner、語言 reviewer、領域 reviewer 與緊急撤回責任人。
- 確認 MVP 的三個語言資料來源及使用權；韓文暫不預設啟用。
- 決定 bundle 由 App 內建或受控下載；兩者都需版本、checksum 與 rollback。
- 決定匿名品質計數是否啟用、保存多久、由誰可查看。
- 先完成三端 Dictionary Contract，再開始匯入第一批 candidate terms。
- 建立明確的 patient-data exclusion 與 source-manifest 稽核表。

本文件完成的是可執行規劃與發布門檻；尚未新增醫療詞彙、索引、下載服務、管理 UI、資料來源或 runtime 行為。
