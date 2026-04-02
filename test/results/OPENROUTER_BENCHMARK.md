# OpenRouter 免費模型基準測試報告

- **測試時間**: 2026-04-02 10:58:33
- **模型數**: 6
- **樣本數/模型**: 3
- **System Prompt**: 516 字元

## 排名（按平均延遲）

| # | 模型 | 類別 | 平均延遲 | 最快 | 最慢 | 品質問題 | 錯誤 |
|---|------|------|----------|------|------|----------|------|
| 🥇 | Nemotron 3 Nano 30B | 極速 | 1.62s | 1.36s | 1.88s | 0 | 1 |
| 🥈 | Step 3.5 Flash | 極速 | 9.50s | 9.50s | 9.50s | 0 | 2 |
| 🥉 | Qwen 3.6 Plus Preview | 旗艦 | 42.87s | 24.70s | 57.72s | 3/3 | 0 |
| 4 | Qwen 3 30B MoE | 極速 | 999.00s | 0.00s | 0.00s | 0 | 3 |
| 5 | DeepSeek V3 0324 | 旗艦 | 999.00s | 0.00s | 0.00s | 0 | 3 |
| 6 | Gemini 2.5 Flash | 旗艦 | 999.00s | 0.00s | 0.00s | 0 | 3 |

## 推薦

**語音後處理最佳選擇**: `nvidia/nemotron-3-nano-30b-a3b:free`（Nemotron 3 Nano 30B）
- 平均延遲 1.62s，類別：極速

## 詳細結果

### Qwen 3 30B MoE (`qwen/qwen3-30b-a3b:free`)

- **中日英混合短句**: ❌ 錯誤 — Error code: 404 - {'error': {'message': 'No endpoints found for qwen/qwen3-30b-a3b:free.', 'code': 404}, 'user_id': 'user_2d1hhoRndc9sg28XRbTog8YzUBd'

- **日文商務**: ❌ 錯誤 — Error code: 404 - {'error': {'message': 'No endpoints found for qwen/qwen3-30b-a3b:free.', 'code': 404}, 'user_id': 'user_2d1hhoRndc9sg28XRbTog8YzUBd'

- **中文多重點**: ❌ 錯誤 — Error code: 404 - {'error': {'message': 'No endpoints found for qwen/qwen3-30b-a3b:free.', 'code': 404}, 'user_id': 'user_2d1hhoRndc9sg28XRbTog8YzUBd'

### Nemotron 3 Nano 30B (`nvidia/nemotron-3-nano-30b-a3b:free`)

- **中日英混合短句** (1.36s)
  ```
  林様、いつもお世話になっております。  
KusuriJapanのご注文につきまして、発送日が来週の水曜日であると確認させていただいてよろしいでしょうか。
  ```

- **日文商務** (1.88s)
  ```
  〇〇様

お世話になっております。来月の東京出張に際し、15日～18日の間のホテル予約をお願い申し上げます。
  ```

- **中文多重點**: ❌ 錯誤 — 'NoneType' object has no attribute 'strip'

### Step 3.5 Flash (`stepfun/step-3.5-flash:free`)

- **中日英混合短句**: ❌ 錯誤 — 'NoneType' object has no attribute 'strip'

- **日文商務**: ❌ 錯誤 — 'NoneType' object has no attribute 'strip'

- **中文多重點** (9.50s)
  ```
  【今日会议重点摘要】
1. 官网改版与内容更新计划
2. 物流方案与时效安排
3. 出差日程及相关事宜确认
  ```

### Qwen 3.6 Plus Preview (`qwen/qwen3.6-plus-preview:free`)

- **中日英混合短句** (57.72s) ⚠️ 輸出過長
  ```
  【件名】KusuriJapan orderのshipping date確認のお願い

林さん
お世話になっております。

標記の件につきまして、以下の点をご確認いただけますでしょうか。
・KusuriJapanのorderにおけるshipping dateは、来週の水曜日となっておりますでしょうか。

お手数をおかけしますが、ご確認のほど何卒よろしくお願い申し上げます。
  ```

- **日文商務** (24.70s) ⚠️ 輸出過長
  ```
  お世話になっております。
来月の東京出張に伴い、宿泊ホテルの手配をお願い申し上げます。

【手配内容】
・日程：15日（チェックイン）～18日（チェックアウト）／3泊
・エリア：東京都内

上記日程にて、至急ご手配いただけますでしょうか。
ご予算や立地条件等の詳細がございましたら、あわせてご指示ください。
何卒よろしくお願い申し上げます。
  ```

- **中文多重點** (46.19s) ⚠️ 輸出過長
  ```
  【今日會議重點摘要】

各位同仁您好：

感謝今日撥冗參與會議。為確保後續執行順利，已將會議決議與待辦事項整理如下，敬請查閱：

• **網站更新**：確認改版內容與上線時程，請相關團隊依計畫推進測試與發布作業。
• **物流安排**：盤點配送流程與合作廠商，優化出貨效率與倉儲調度。
• **出差日程確認**：核對航班、住宿與拜訪行程，請於指定期限內回覆最終確認名單。

如有任何補充或需協調之處，
  ```

### DeepSeek V3 0324 (`deepseek/deepseek-chat-v3-0324:free`)

- **中日英混合短句**: ❌ 錯誤 — Error code: 404 - {'error': {'message': 'No endpoints found for deepseek/deepseek-chat-v3-0324:free.', 'code': 404}, 'user_id': 'user_2d1hhoRndc9sg28X

- **日文商務**: ❌ 錯誤 — Error code: 404 - {'error': {'message': 'No endpoints found for deepseek/deepseek-chat-v3-0324:free.', 'code': 404}, 'user_id': 'user_2d1hhoRndc9sg28X

- **中文多重點**: ❌ 錯誤 — Error code: 404 - {'error': {'message': 'No endpoints found for deepseek/deepseek-chat-v3-0324:free.', 'code': 404}, 'user_id': 'user_2d1hhoRndc9sg28X

### Gemini 2.5 Flash (`google/gemini-2.5-flash-preview:free`)

- **中日英混合短句**: ❌ 錯誤 — Error code: 400 - {'error': {'message': 'google/gemini-2.5-flash-preview:free is not a valid model ID', 'code': 400}, 'user_id': 'user_2d1hhoRndc9sg28

- **日文商務**: ❌ 錯誤 — Error code: 400 - {'error': {'message': 'google/gemini-2.5-flash-preview:free is not a valid model ID', 'code': 400}, 'user_id': 'user_2d1hhoRndc9sg28

- **中文多重點**: ❌ 錯誤 — Error code: 400 - {'error': {'message': 'google/gemini-2.5-flash-preview:free is not a valid model ID', 'code': 400}, 'user_id': 'user_2d1hhoRndc9sg28
