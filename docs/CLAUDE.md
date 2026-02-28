# SGH Voice — Claude Code 專案指令

> 這是 Claude Code 的專案級指令檔。放在 repo 根目錄，Claude Code 啟動時自動讀取。

## 專案概述

SGH Voice 是一個 Android AI 語音鍵盤 + 自架雲端後端系統。
使用者按住麥克風說話（中日英三語混合），放開後自動辨識、潤飾、貼上。

**完整產品規格書**：`docs/sgh-voice-spec.md`（必讀，892 行，含競品分析、架構、API 規格、UI 規格）

## 技術棧

```
後端：Python 3.11 + FastAPI + uvicorn
AI：OpenAI Whisper API + Anthropic Claude API
部署：Zeabur (Tokyo Region) + Docker
Android：Kotlin + Material 3 + OkHttp3 + Coroutines
最低 SDK：26 (Android 8.0)
資料儲存：JSON 檔案（/var/data）
```

## 專案結構

```
sgh-voice/
├── CLAUDE.md              ← 你正在讀的這個檔案
├── docs/
│   └── sgh-voice-spec.md  ← 完整產品規格書（必讀）
├── backend/
│   ├── main.py            ← FastAPI 主程式（所有端點）
│   ├── Dockerfile
│   ├── requirements.txt
│   └── static/
│       └── index.html     ← Dashboard 網頁
├── android/               ← Android Studio 專案
│   └── app/src/main/
│       ├── java/com/shingihou/voiceinput/
│       │   ├── VoiceKeyboardService.kt  ← IME 主服務
│       │   ├── ApiClient.kt             ← 後端通訊
│       │   └── SetupActivity.kt         ← 設定頁面
│       ├── res/
│       └── AndroidManifest.xml
├── ARCHITECTURE.md
├── INSTALL.md
└── BUILD.md
```

## 核心規則（每次修改前必讀）

### 1. 三語混合是第一優先

這個系統的核心價值是「同一句話混合繁體中文+日文+英文」。
每個功能的實作都必須確保三語混合正常運作。

範例輸入：「幫我跟鈴木先生のクリニック確認一下 appointment 的時間」
正確輸出：保持每個詞的原語言，不翻譯
錯誤輸出：把日文翻成中文，或把英文翻成中文

### 2. 繁體中文保證

所有中文輸出一律使用繁體中文，絕對不輸出簡體中文。
Claude prompt 必須明確包含此規則。

### 3. 音檔不落地

音檔在後端只用 `io.BytesIO` 處理，絕對不寫入硬碟。
這是資安設計，不可妥協。

### 4. Android IME 生命週期

IME Service 的生命週期跟 Activity 不同：
- `onCreateInputView()` 只在鍵盤第一次建立時呼叫
- `onStartInputView()` 每次鍵盤出現時呼叫
- 權限（RECORD_AUDIO）必須在 SetupActivity 取得，不能在 IME Service 裡 request

### 5. 四層處理管線順序

```
Layer 1: Whisper API（不指定 language，用三語 prompt）
Layer 2: 詞庫修正（長的優先比對）
Layer 3: Smart Replace（@mail → email 地址等）
Layer 4: Claude 後處理（模式 prompt + 填充詞移除 + 自我修正偵測）
```

四層順序不可更改。每層有獨立職責，不可合併。

## 編碼風格

### Python (後端)
- 使用 type hints
- 函數加 docstring
- 錯誤訊息用繁體中文
- 所有 API response 都用 JSON
- 敏感資訊從環境變數讀取

### Kotlin (Android)
- 使用 coroutines 處理非同步
- UI 更新必須在 Main thread
- 音訊處理用 IO dispatcher
- 命名：camelCase（函數/變數），PascalCase（類別）

## 測試重點

每次修改後，至少驗證：
1. 三語混合辨識：輸入中日英混合語句，確認不被翻譯
2. 模式切換：切換 Smart Mode 確認 prompt 正確套用
3. 候選區：辨識結果能正確顯示並點擊輸入
4. 改寫按鈕：至少測試「精簡」和「翻日」兩個改寫
5. 錯誤處理：錄音太短（<0.5s）和無網路的情況

## 環境變數

```
OPENAI_API_KEY=sk-xxx      # Whisper API
ANTHROPIC_API_KEY=sk-ant-xxx # Claude API
AUTH_TOKEN=你的密碼          # API 存取認證
DATA_DIR=/var/data           # 資料儲存路徑
CLAUDE_MODEL=claude-sonnet-4-5-20250929  # Claude 模型
```

## 部署指令

```bash
# 本地開發
cd backend && pip install -r requirements.txt && uvicorn main:app --reload

# Docker 建置
docker build -t sgh-voice ./backend
docker run -p 8000:8000 --env-file .env sgh-voice

# Zeabur 部署
git push  # Zeabur 自動偵測 Dockerfile 並部署
```

## 已知限制

- Whisper 三語混合仍有 10-20% 錯誤率，靠 Layer 2+4 修正
- Android IME 的 `RECORD_AUDIO` 權限在部分手機有相容性問題
- PCM → WAV 需要手動寫 44 byte header
- Zeabur free plan 有 cold start 延遲（~3-5 秒）
