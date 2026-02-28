# SGH Voice — Claude Code 執行指南

> 這份文件告訴你「怎麼啟動 Claude Code」以及「每個階段要貼什麼 prompt」。

---

## 0. 前置準備（在開 Claude Code 之前）

### 資料夾結構
```bash
mkdir -p sgh-voice/docs
# 把規格書放進去
cp sgh-voice-spec-v3.2.md sgh-voice/docs/sgh-voice-spec.md
# 把 CLAUDE.md 放到根目錄
cp CLAUDE.md sgh-voice/CLAUDE.md
cd sgh-voice
git init
```

### 環境
- 安裝 Python 3.11+、Android Studio、Kotlin
- 準備好 OpenAI API Key 和 Anthropic API Key
- 確認有 Zeabur 帳號

### Claude Code 設定
```bash
# 啟動 Claude Code
claude

# 確認模型（建議 Opus 4.6）
/model opus
```

---

## 1. Phase 1 啟動 Prompt — 後端 MVP

> 複製以下整段貼進 Claude Code：

```
讀取 docs/sgh-voice-spec.md 和 CLAUDE.md，理解整個專案。

現在開始實作 Phase 1: 後端 MVP。

請按以下順序逐步實作，每完成一個步驟就停下來讓我確認：

### Step 1: 專案骨架
建立 backend/ 資料夾，包含：
- main.py（FastAPI 空架構，含所有端點路由但先回 placeholder）
- requirements.txt（fastapi, uvicorn, openai, anthropic, python-multipart）
- Dockerfile（Python 3.11 slim, 安裝依賴, uvicorn 啟動）
- .env.example（列出所有需要的環境變數）

### Step 2: 四層處理管線
在 main.py 實作 POST /api/transcribe 的完整四層管線：
- Layer 1: Whisper API（不指定 language，用三語 prompt）
- Layer 2: 詞庫修正（從 dictionary.json 讀取規則）
- Layer 3: Smart Replace（從 smart_replace.json 讀取觸發詞）
- Layer 4: Claude 後處理（從 modes.json 讀取模式 prompt）

音檔只用 io.BytesIO，不落地。

### Step 3: 預裝資料
建立 /var/data 的初始 JSON 檔案：
- dictionary.json（規格書第六章的 40+ 修正規則和 45 個自訂詞彙）
- modes.json（9 個 Smart Mode，每個都有完整的 Claude system prompt）
- smart_replace.json（9 條觸發詞）
- power_rules.json（App→模式對應）
- history.json（空陣列）
- stats.json（初始化統計）

特別注意 modes.json 裡每個模式的 Claude prompt 都要包含：
1. 三語混合保持規則
2. 繁體中文保證（絕不輸出簡體）
3. 填充詞移除清單（中日英三語的填充詞）
4. 口語自我修正偵測
5. 該模式特有的格式要求

### Step 4: 所有 API 端點
實作規格書第五章的所有端點，包含：
- POST /api/rewrite（改寫）
- POST /api/history/reprocess（重新潤飾）
- GET /api/stats（含 token 用量+費用估算）
- 所有 dictionary / modes / smart-replace / power-rules CRUD

### Step 5: Dashboard
在 backend/static/index.html 建立單頁 Dashboard：
- 統計面板（今日/本週/累計 + 費用估算）
- 歷史紀錄（搜尋+重新潤飾）
- 詞庫管理（新增/刪除修正規則和自訂詞彙）
- 模式管理（新增/編輯模式 prompt）
- Smart Replace 管理
- Power Rules 管理
- 一鍵清除歷史

用 Tailwind CDN + vanilla JS，深色主題（#1b1b2f 背景，#6c5ce7 紫色強調）。

完成後，給我完整的啟動測試指令。
```

---

## 2. Phase 1 啟動 Prompt — Android 鍵盤

> 後端確認 OK 後，貼這段：

```
後端已完成。現在開始實作 Android 鍵盤 IME。

讀取 docs/sgh-voice-spec.md 第四章（Android 鍵盤 UI 規格）。

請建立完整的 Android Studio 專案：

### Step 1: 專案結構
建立 android/ 資料夾，完整的 Android Studio 專案結構：
- package: com.shingihou.voiceinput
- minSdk: 26, targetSdk: 34
- 依賴：OkHttp3, Coroutines, Material 3

### Step 2: VoiceKeyboardService.kt
IME 主服務，功能：
- 鍵盤 UI 佈局（參考規格書 4.1 的 ASCII 圖）
  - 頂部模式列（9 個模式，可左右滑動）
  - 候選區（顯示辨識結果，點擊輸入）
  - 改寫按鈕列（7 個改寫選項，辨識後顯示）
  - 麥克風按鈕（長按錄音，支援脈衝動畫+震動）
  - 底部列（常用標點+空白+退格+換行）
- 長按錄音模式（預設）：
  - 按住 → 開始錄音（PCM 16kHz mono）
  - 放開 → 停止 → 上傳到後端
- 短按錄音模式（可在設定切換）：
  - 點一下 → 開始
  - 再點一下 → 停止
  - 靜音 1.5 秒自動停止
- Power Mode：讀取 currentInputEditorInfo.packageName，自動切模式
- 視覺設計：深色主題，參考規格書 4.3 的顏色值

### Step 3: ApiClient.kt
- transcribe(audioBytes, mode, appId) → TranscribeResult
- rewrite(text, style) → RewriteResult
- getModes() → List<Mode>
- ping() → Boolean
- 所有請求帶 Bearer Token
- 超時設定：連線 10s，讀取 30s（Whisper+Claude 需要時間）

### Step 4: SetupActivity.kt
- 伺服器 URL 輸入
- Auth Token 輸入
- 連線測試按鈕（呼叫 /api/ping）
- 錄音模式切換（長按/短按）
- 「啟用鍵盤」按鈕 → 跳轉系統設定
- Dashboard 連結

### Step 5: BUILD.md
完整的 Android Studio 編譯教學：
- 如何用 Android Studio 開啟專案
- 如何設定伺服器 URL
- 如何編譯 APK
- 如何在手機上安裝和啟用鍵盤

完成後確認鍵盤可以正常編譯。
```

---

## 3. Phase 2 Prompt — 功能強化

```
Phase 1 完成。開始 Phase 2 功能強化。

請逐一實作以下功能，每個做完讓我測試：

1. Android 短按錄音模式
   - 在 SetupActivity 加入切換開關
   - VoiceKeyboardService 支援兩種模式
   - 短按模式：靜音偵測（1.5s 無聲自動停止）

2. Power Mode 完整實作
   - 讀取 /api/power-rules 的 App→模式對應
   - 鍵盤頂部模式列自動切換到對應模式
   - 顯示 ⚡Auto 標示

3. 改寫按鈕列完整實作
   - 辨識結果出來後，底部顯示 7 個改寫按鈕
   - 點擊後呼叫 /api/rewrite
   - 改寫結果替換候選區文字

4. 用量追蹤
   - 後端 /api/stats 回傳 token 用量和費用估算
   - Dashboard 顯示本月費用、月份對比圖表

5. 歷史重新潤飾
   - Dashboard 歷史紀錄頁加入「重新潤飾」按鈕
   - 可選擇不同模式重跑 Claude 處理
   - 顯示原始結果和新結果對比

6. AI 助手模式
   - mode=assistant 時，Claude 回答問題而非潤飾文字
   - 鍵盤候選區顯示「🤖 AI 回答 — 點擊複製」
   - 點擊後複製到剪貼簿，不輸入文字框
```

---

## 4. Phase 3 Prompt — 超越競品

```
Phase 2 完成。開始 Phase 3 進階功能。

請實作：

1. Hands-free 模式
   - 雙擊麥克風按鈕啟動
   - 持續錄音，靜音 2 秒自動停止
   - 最長 2 分鐘

2. 語音指令修正文字（參考 ByeType）
   - 辨識結果顯示在候選區時
   - 再按一次麥克風，用口述修改文字
   - 例如：「把三點改成四點」「刪掉最後一句」「加上謝謝」
   - 用 Claude 理解修改指令並套用

3. Dashboard 趨勢圖表
   - 用 Chart.js 繪製日/週/月用量曲線
   - 費用估算趨勢圖
   - 按模式分類的使用統計

4. 安靜模式
   - 降低錄音觸發門檻
   - 在麥克風按鈕旁加入靜音切換
```

---

## 5. Debug 常用 Prompt

### 三語混合問題
```
三語混合辨識結果異常。
輸入：「幫我跟鈴木先生のクリニック確認一下 appointment」
期待：保持中日英三語原貌
實際：[貼上實際結果]

請檢查四層管線，找出哪一層出問題。特別注意：
- Layer 1: Whisper prompt 是否包含三語詞彙
- Layer 2: 詞庫修正是否錯誤替換
- Layer 4: Claude prompt 是否意外翻譯
```

### Android 鍵盤問題
```
鍵盤 [描述問題]。

請檢查：
1. VoiceKeyboardService 的 onCreateInputView / onStartInputView
2. 權限是否正確（RECORD_AUDIO, INTERNET）
3. ApiClient 的超時設定
4. UI 更新是否在 Main thread
```

### 後端 API 問題
```
/api/transcribe 回傳 [錯誤訊息]。

請檢查：
1. 音檔格式（WAV header 是否正確）
2. Whisper API 呼叫參數
3. Claude API 呼叫是否正確帶入模式 prompt
4. JSON 檔案讀寫是否有 race condition
```

---

## 6. 重要提醒

### 每次開新 session 的開場白
```
繼續 SGH Voice 開發。請先讀取 CLAUDE.md 和 docs/sgh-voice-spec.md 確認專案狀態。
上次進度：[描述上次做到哪裡]
今天要做：[描述今天目標]
```

### 要 Claude Code review 程式碼
```
請 review 目前的程式碼，特別檢查：
1. 三語混合是否會被意外翻譯
2. 音檔是否有落地（不應該寫入硬碟）
3. 繁體中文保證是否在所有 Claude prompt 中
4. 錯誤處理是否完整
5. Android IME 生命週期是否正確
```
