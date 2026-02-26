# 🎙 SGH Voice — AI 語音輸入工具

> 替代 Typeless（$12/月）的自建方案。Whisper 語音辨識 + Claude/Qwen 智慧後處理，支援中日英三語混合，資料 100% 掌控在自己手中。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Private-gray)]()
[![Version](https://img.shields.io/badge/Version-1.1.0-green)]()

---

## 特色功能

| 功能 | 說明 |
|------|------|
| **三語混合辨識** | 同一句話中繁體中文、日文、英文自由切換，不會被翻譯 |
| **繁體中文三層防護** | Whisper prompt → Claude system prompt → OpenCC s2twp |
| **Hybrid 智慧分流** | 短音訊用本地 mlx-whisper，長音訊上 OpenAI Cloud |
| **AI 後處理** | 去填充詞（嗯、啊、えーと、um）、自我修正偵測、標點分段 |
| **個人詞庫學習** | 自動累積修正規則，越用越準 |
| **Smart Replace** | `@mail`、`@phone` 等觸發詞自動展開 |
| **9 種改寫模式** | 精簡 / 正式 / 會議 / Email / 技術 / 口語 / 翻英 / 翻日 / 翻中 |
| **Push-to-Talk / Toggle** | 按住 Right Cmd 說話，或按一下開始、再按一下停止 |
| **跨應用程式** | 系統級語音輸入，辨識完自動貼到游標位置 |
| **Web Dashboard** | 使用統計、歷史紀錄、詞庫管理、設定 |

---

## 快速開始（DMG 安裝）

### 系統需求

- macOS 14.0+ (Sonoma 或更新)
- Apple Silicon (M1/M2/M3/M4)
- OpenAI API Key（語音辨識用）
- Anthropic API Key（選用，AI 後處理潤稿）

### 安裝步驟

1. 從 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載 `SGH-Voice-1.1.0-apple-silicon.dmg`
2. 雙擊 DMG，將 **SGH Voice** 拖入 Applications 資料夾
3. 首次開啟：右鍵 → 打開（macOS Gatekeeper 需要允許一次）
4. 選單列出現 🎙 圖示後，點擊 **Open Dashboard**
5. 在 Dashboard 設定頁填入 API Key

### macOS 權限授權

首次使用需授權以下權限（系統設定 → 隱私與安全性）：

| 權限 | 用途 | 授權對象 |
|------|------|---------|
| 麥克風 | 錄音 | SGH Voice |
| 輔助使用 | 自動貼上（Cmd+V） | SGH Voice |
| 輸入監控 | 全域快捷鍵監聽 | SGH Voice |

---

## 使用方式

### Push-to-Talk（預設）

1. 選單列出現 🎙
2. **按住 Right Cmd（⌘）** 開始錄音
3. **放開** 停止，自動辨識並貼到游標位置

> 可在 Dashboard 設定中改為 Toggle 模式或其他快捷鍵。

### Dashboard

點擊選單列 🎙 → **Open Dashboard**，或瀏覽器開啟 `http://localhost:7865`

- **總覽**：節省時間、月費估算、使用統計
- **歷史紀錄**：搜尋、複製、改寫所有辨識結果
- **詞庫記憶**：管理自訂詞彙和修正規則
- **設定**：API Key、語言、快捷鍵、Hybrid 模式開關

---

## 技術架構

### 五層處理管線

```
按住快捷鍵 → 麥克風錄音
       ↓
Layer 1: Whisper STT（Hybrid 路由：本地 mlx-whisper / Cloud OpenAI）
       ↓
Layer 2: 詞庫修正（memory.apply_corrections）
       ↓
Layer 3: Smart Replace（@mail → email 等觸發詞展開）
       ↓
Layer 4: LLM 後處理（Hybrid：本地 Ollama Qwen / Cloud Claude Haiku 4.5）
       ↓
Layer 5: OpenCC s2twp（繁體中文最終防護）
       ↓
       自動貼到游標位置
```

### Hybrid 智慧分流

| 條件 | 路由 | 延遲 |
|------|------|------|
| 錄音 < 15 秒 | 本地 mlx-whisper | ~0.5s |
| 錄音 ≥ 15 秒 | Cloud OpenAI Whisper | ~1-2s |
| 文字 < 30 字且無填充詞 | 跳過 LLM，直接用詞庫修正 | ~0s |
| 文字 < 30 字 | 本地 Ollama Qwen 2.5 | ~0.3s |
| 文字 ≥ 30 字 | Cloud Claude Haiku 4.5 | ~0.5-1s |

### 技術堆疊

```
Runtime:         Python 3.12+
語音辨識（本地）: mlx-whisper (Apple Silicon 優化)
語音辨識（雲端）: OpenAI Whisper API
後處理（本地）:   Ollama + Qwen 2.5 3B
後處理（雲端）:   Anthropic Claude Haiku 4.5
繁中轉換:        OpenCC (s2twp)
錄音:            sounddevice + numpy
快捷鍵:          pynput
系統整合:        rumps (macOS 選單列)
Dashboard:       Flask + 原生 HTML/JS
自動貼上:        pyperclip + AppleScript (Cmd+V)
打包:            PyInstaller + create-dmg
```

### API 整合方式

**OpenAI Whisper API**
- 用途：語音轉文字（Cloud 路由）
- 音檔格式：WAV 16kHz mono
- 特色：`initial_prompt` 帶入自訂詞庫提升辨識精度
- 費用：約 $0.006/分鐘

**Anthropic Claude API**
- 用途：後處理潤稿（去填充詞、自我修正偵測、標點分段）
- 模型：Claude Haiku 4.5（速度優先）
- 特色：自訂 system prompt，保持三語混合不翻譯
- 費用：約 $0.001/次

**本地 Whisper (mlx-whisper)**
- 用途：短音訊快速辨識，無需網路
- 模型：`mlx-community/whisper-turbo`
- 特色：Apple Silicon Neural Engine 加速，beam_size=1 貪婪解碼

**本地 LLM (Ollama)**
- 用途：短文字快速後處理
- 模型：`qwen2.5:3b`
- 特色：完全離線，適合簡單去填充詞

---

## 費用比較

| 方案 | 月費 |
|------|------|
| Typeless Pro | $12/月 |
| Wispr Flow | $12/月 |
| Superwhisper | $8.49/月 |
| **SGH Voice（正常使用）** | **~$3-8/月（API 費用）** |
| **SGH Voice（短句為主）** | **~$1-3/月（多數走本地）** |

---

## 從原始碼開發

### 環境準備

```bash
# Clone
git clone https://github.com/linchichuan/sgh-voice.git
cd sgh-voice

# Python 虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 本地 Whisper（選用，Apple Silicon）
pip install mlx-whisper

# 本地 LLM（選用）
brew install ollama
ollama pull qwen2.5:3b
```

### 執行

```bash
python app.py              # 選單列 + Dashboard（日常使用）
python app.py --cli        # CLI 模式（初期訓練詞庫推薦）
python app.py --dashboard  # 只開 Dashboard
```

### CLI 模式操作

```
▶                          ← 按 Enter 開始錄音
🔴 錄音中... 按 Enter 停止
⏳ 辨識中...

📝 Whisper: 請幫我跟新义丰的客戶發一封信
📖 詞庫修正: 請幫我跟新義豊的客戶發一封信
🤖 Claude:  請幫我跟新義豊的客戶發一封信。
✅ 最終: 請幫我跟新義豊的客戶發一封信。

✏️  修正 (Enter 跳過): ← 手動修正後系統會自動學習
```

### 打包 DMG

```bash
chmod +x build.sh
./build.sh
# 產出：dist/SGH-Voice-1.1.0-apple-silicon.dmg
```

---

## 專案結構

```
sgh-voice/
├── app.py              # 主程式（選單列 + CLI + 快捷鍵）
├── transcriber.py      # Whisper + LLM 五層處理管線
├── recorder.py         # 音訊錄製（sounddevice）
├── memory.py           # 詞庫記憶 + 自動學習
├── config.py           # 設定與資料持久化
├── dashboard.py        # Flask Web Dashboard
├── dashboard_window.py # WebView 視窗啟動器
├── overlay.py          # 狀態覆蓋 UI
├── launcher.py         # App 啟動入口
├── build.sh            # 一鍵打包 DMG
├── requirements.txt    # Python 依賴
├── resources/
│   ├── icon.icns       # App 圖示
│   └── entitlements.plist
└── static/
    └── index.html      # Dashboard UI
```

本地資料位置：`~/.voice-input/`
```
~/.voice-input/
├── config.json         # 設定（含 API Key）
├── dictionary.json     # 詞庫（修正規則 + 自訂詞彙）
├── history.json        # 歷史紀錄
├── stats.json          # 使用統計
└── smart_replace.json  # Smart Replace 規則
```

---

## 隱私與安全

| 項目 | 做法 |
|------|------|
| 語音資料 | 僅傳送至 OpenAI/Anthropic API，不經過其他伺服器 |
| API Key | 存在本機 `~/.voice-input/config.json`，不上傳 |
| 歷史紀錄 | 全部存本地，最多保留 2000 筆 |
| 需要帳號 | 否 |
| 資料追蹤 | 無 |

---

## 授權

Private — 新義豊株式会社 (Shingihou Co., Ltd.) 內部使用

## 開發者

**林紀全 (Lin Chichuan)** — CEO, 新義豊株式会社
- 🌐 [shingihou.com](https://shingihou.com)
- 📧 service@shingihou.com
