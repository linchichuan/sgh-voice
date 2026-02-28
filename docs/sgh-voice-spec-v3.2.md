# 🎙 SGH Voice — 產品規格書 (Claude Code 開發文件)

> **專案名稱**: SGH Voice (Shingihou Voice Input System)
> **版本**: v3.2 (2026-02-23 更新 — 整合 Purri / Typeless / ByeType / 中國競品 / 2026 市場分析)
> **目標平台**: Android 鍵盤 (IME) + Zeabur 雲端後端
> **使用者**: 林紀全 (CEO, 新義豊株式会社) — 個人/公司內部使用
> **核心差異化**: 中日英三語混合辨識 + 醫療業務專用語音鍵盤
> **競品分析涵蓋**: 25+ 產品（含 Purri、ByeType、Typeless、Wispr Flow、Willow、Aqua、中國三大 + 開源方案）

---

## 一、競品分析摘要

### 1.1 市場主要產品

| 產品 | 平台 | 定價 | 核心特色 | 不足之處 |
|------|------|------|---------|---------|
| **Wispr Flow** | Mac/Win/iOS (Android 開發中) | $12/月 | 上下文感知、自動調整語氣、95%+ 準確率、SOC2/HIPAA、100+ 語言、語音捷徑 | 雲端處理隱私疑慮、佔 800MB RAM、無 Android、$81M 融資但需訂閱 |
| **Superwhisper** | Mac/iOS | $8.49/月 或 $249 終身 | 離線 whisper.cpp、自訂 AI 模式+自訂 prompt、詞彙替換、上下文感知、多 AI 模型 | 設定複雜、無 Android/Windows、離線模型在舊機效能差 |
| **Willow Voice** | Mac/Win/iOS (Android 開發中) | $15/月 | 風格匹配（email 正式/聊天口語）、AI 改寫、200ms 延遲、安靜模式、學習用戶風格 | 無 Android、iOS 實作有 bug、SOC2 但雲端處理 |
| **Aqua Voice** | Mac/Win | $8/月 | 超快（50ms 啟動/450ms 輸出）、800 自訂詞、自然語言風格指令、上下文感知 | 無 Android/iOS、純雲端、免費只有 1000 字/月 |
| **VoiceInk** | Mac (開源) | $25 一次性 | 離線 whisper.cpp、Power Mode（偵測 App 切模式）、Smart Modes、自訂 prompt | 僅 Mac、依賴 Whisper 無 LLM 後處理 |
| **TalkTastic** | macOS | 未公開 | 上下文感知鍵盤、Ghostwriter 輸出、自動調整語氣/風格/長度 | 僅 Mac |
| **Monologue** | Mac | $10/月 | 本地模型選項、依 App 自訂語氣、學習寫作風格 | 僅 Mac、1000 字/月免費 |
| **Dragon Anywhere** | Android/iOS | $14.99/月 | 專業級準確度、語音命令、自訂詞彙、格式控制 | 貴、舊技術架構、學習曲線陡 |
| **Purri** ⭐ | macOS | 免費 (BYOK) | 台灣開發者、繁體中文優先（保證不出簡體）、極簡按住說話→自動貼上、AI 潤飾情境（通用/會議/Email/技術）、重新潤飾、用量+費用追蹤、長按+短按雙模式、BYOK OpenAI、無帳號/無追蹤 | 僅 macOS、僅 OpenAI、無自訂詞庫、無上下文感知、無多語混合 |
| **Typeless** ⭐ | Mac/Win/**Android** | $12/月 | **已有 Android 鍵盤**、AI 填充詞移除、自我修正偵測（刪掉口誤只留最終意圖）、混合語言翻譯、上下文感知、6 分鐘連續錄音 | 訂閱制、Android 版 UI 極簡（只有麥克風按鈕） |
| **Gboard 語音** | Android (內建) | 免費 | 內建免裝、Google STT 引擎、60+ 語言、即時辨識 | 無 AI 後處理、三語混合效果差、無自訂詞庫、無格式調整 |
| **Spokenly** | Mac/iOS | 免費 (BYOK) | 自訂 system prompt、多 AI 模型（GPT-4/Claude/本地）、自動語言偵測、iOS 版極佳、開發者回應快 | 上下文感知有限、需要技術能力設定 API key |
| **Voibe** | Mac | 一次性購買 | 100% 離線、Apple Silicon 優化、零延遲、開發者工具支援（Cursor/VS Code） | 僅 Mac、僅 Apple Silicon、無 AI 改寫 |
| **FluidVoice** | Mac (開源) | 免費 | 完全開源 GPL v3、25 語言自動偵測、macOS 原生語音引擎、可選 AI 增強 | 僅 Mac、功能較基礎 |
| **Ito** | Mac/Win/Linux (開源) | 免費 | 開源語音助手、捕捉意圖而非逐字、Rust 工具鏈高效能、跨平台 | 早期階段、需技術能力 |
| **ByeType** ⭐ | **iOS** (macOS 開發中) | Beta 免費 | 台灣開發者用 Claude Code 7天完成、iOS 客製化鍵盤、WhisperKit 本地+雲端雙引擎、情境感知格式、語音指令修正文字、自訂 prompt/風格、BYOK 多 vendor（OpenAI/Anthropic/Gemini/ElevenLabs）、20 語言 | 僅 iOS、Beta 階段、無 Android |
| **AutoTyper 智譜** | Mac/Win | 免費（智譜帳號） | 中國智譜 AI 大模型驅動、中文優化 | 僅中國市場、需智譜帳號、隱私疑慮 |
| **豆包輸入法** | Android/iOS | 免費 | 字節跳動推出、AI 語音輸入、中文極佳 | 僅中國市場、字節生態綁定、隱私疑慮 |
| **OpenWhispr** | Mac/Win (開源) | 免費 | TypeScript 開源、桌面版、Whisper 本地 | 無手機版、基礎功能 |
| **Freeflow** | Mac (開源) | 免費 | MIT License、Zach Latta（Hack Club）開發 | 早期階段 |

### 1.2a 重點競品深入分析

#### 🐱 Purri — 台灣開發者，繁體中文標竿

**為什麼重要**：Purri 是我們目前看到唯一一個「以台灣繁體中文使用者為核心」的語音輸入產品，它的設計哲學值得參考。

| 項目 | Purri 做法 | SGH Voice 對應策略 |
|------|-----------|-------------------|
| **繁中保證** | prompt 明確指定繁體中文，保證不出簡體 | ✅ 採用：Claude prompt 加入「繁體中文，絕對不輸出簡體中文」規則 |
| **極簡操作** | 按住說話→放開→自動貼上，零學習成本 | ✅ 採用：預設體驗同樣極簡，進階功能不擋路 |
| **雙錄音模式** | 長按模式 + 短按模式（靜音自動停） | ✅ 採用：Android 鍵盤同時支援長按和短按切換 |
| **AI 潤飾情境** | 通用/會議紀錄/Email/技術文件（4 個） | ✅ 超越：我們有 9 個 Smart Mode + 自訂模式 |
| **重新潤飾** | 結果不滿意可換情境重跑 | ✅ 採用：改寫按鈕列（7 種改寫） |
| **用量+費用追蹤** | 月費估算、token 用量一目瞭然 | ✅ 採用：Dashboard 加入 token 用量和費用估算 |
| **BYOK 免費** | 自帶 OpenAI key，免費使用 | ✅ 我們更進階：自架後端，完全掌控 |
| **隱私** | 無帳號/無追蹤/API key 存 Keychain | ✅ 對齊：我們也是零追蹤設計 |
| **語言** | 僅繁體中文 | ❌ 我們超越：三語混合（繁中+日文+英文） |
| **平台** | 僅 macOS | ❌ 我們不同：Android 鍵盤（互補市場） |
| **自訂詞庫** | 無 | ❌ 我們有：40+ 修正規則 + 自訂詞彙 |
| **上下文感知** | 無 | ❌ 我們有：Power Mode 自動偵測 App |

#### ⌨️ Typeless — 唯一有 Android 鍵盤的 AI 語音產品

**為什麼重要**：Typeless 是我們在 Android 鍵盤形態上的唯一直接競品（2026 年 2 月 MakeUseOf 評測）。

| 項目 | Typeless 做法 | SGH Voice 對應策略 |
|------|-------------|-------------------|
| **Android IME** | 已上線，Google Play 可下載 | ⚠️ 直接競爭：但他們面向英語市場，我們面向三語 |
| **自我修正偵測** | 「下午兩點，不對，四點」→ 只輸出「下午四點」 | ✅ 已有：Layer 4 Claude prompt 含此功能 |
| **填充詞移除** | 自動刪除 um、uh、like 等 | ✅ 已有：Layer 4 Claude prompt 含此功能 |
| **混合語言翻譯** | 支援 6+ 語言混合口述，自動翻譯成目標語言 | ❌ 關鍵差異：Typeless 會翻譯，我們保留原語言 |
| **UI** | 極簡（只有大麥克風按鈕+空白鍵+退格） | 我們更完整：模式列+候選區+改寫列+標點按鍵 |
| **6 分鐘連續** | 單次最長 6 分鐘 | 我們先做 2 分鐘，後續擴展 |
| **上下文感知** | 偵測 App 類型調整輸出 | ✅ 我們也有：Power Mode |
| **定價** | $12/月訂閱 | 我們免費（自架） |

#### ⚠️ Typeless 隱私疑慮警告（2026/02/10 日本團隊逆向分析）

ByeType 開發者引用日本團隊的逆向工程報告，指出 Typeless 存在以下隱私風險：
- 語音辨識為雲端處理（非本地）
- 可能蒐集：完整 URL、前景 App/視窗標題、螢幕可見文字、剪貼簿內容、系統層級鍵盤事件
- 本機 DB 以明文保存轉錄內容與瀏覽資訊
- 與官方「Zero data retention」行銷說法存在落差
- 高敏感權限（Accessibility/螢幕錄影）+ 營運透明度不足 = 風險放大

**對 SGH Voice 的啟示**：這正好強化我們「自架後端 + 零追蹤 + 音檔不落地」的安全設計優勢。

#### 📱 ByeType — 台灣 AI 工程師用 Claude Code 7 天完成的 iOS 語音鍵盤

**為什麼重要**：證明了一個人用 Claude Code 可以在 7 天內做出可比擬 Typeless/WisprFlow 的 AI 語音工具，也是我們 Android 版的「對照實驗」。

| 項目 | ByeType 做法 | SGH Voice 對應策略 |
|------|-------------|-------------------|
| **開發方式** | Claude Code + Compound Engineering Plan skill + ui-ux-pro-max-skill | ✅ 我們也用 Claude Code 開發 |
| **開發成本** | $330 USD（Claude Max $100 + Extra $230），7 天 | 我們可以參考這個預算和時間估算 |
| **模型選擇** | 首選 Opus 4.6（長時間一致性優於 Sonnet） | ✅ 規格書指定用 Opus 4.6 |
| **雙引擎** | WhisperKit 本地 + 雲端 Vendor 可選 | ⚠️ 我們目前僅雲端 Whisper，未來可考慮本地引擎 |
| **多 AI Vendor** | OpenAI/Anthropic/Gemini/ElevenLabs | 我們目前 OpenAI(Whisper) + Anthropic(Claude) |
| **語音指令修正** | 口述修改已辨識文字（不用手動打字修改） | 🆕 值得加入：Phase 3 新功能 |
| **自訂 prompt** | 使用者可自訂潤飾風格的 prompt | ✅ 已有：Dashboard 模式編輯 |
| **平台** | iOS（macOS 開發中） | 我們是 Android（互補市場） |
| **參考架構** | OpenWhispr（TypeScript 桌面版開源） | 我們自建 FastAPI 後端 |

**ByeType 開發者的關鍵經驗（Claude Code 踩坑）**：
1. **State Management**：Agentic Coding 容易遺漏狀態管理，主架構流程需人工用自然語言清楚描述
2. **音訊處理**：需理解取樣率/格式差異，ASR vendor 有支援限制
3. **功能交互影響**：新功能加入後，已實作的 feature 可能受影響，需全面回歸測試

### 1.2 業界共通的核心功能 (Must-Have)

從所有競品歸納出 2025-2026 年 AI 語音輸入的標準功能：

1. **上下文感知 (Context Awareness)**
   - 偵測使用者正在哪個 App 裡，自動調整輸出格式和語氣
   - Email App → 正式語氣 + 問候/結尾
   - 聊天 App → 簡短口語
   - IDE/Code → 保留技術術語
   - 這是目前所有頂級產品的核心差異化功能

2. **填充詞移除 + 自我修正偵測**
   - 自動移除「嗯」「啊」「那個」「えーと」「um」「uh」
   - 偵測口語修正：「下午兩點，不對，四點」→ 只輸出「下午四點」
   - Wispr Flow 稱之為 "zero-edit rate"（80%+ 不需要任何修改）

3. **自訂詞庫 / 個人辭典**
   - 加入公司名稱、人名、專業術語
   - 部分產品支援自動學習（辨識錯誤修正後自動記錄）
   - Aqua Voice 支援 800 個自訂詞

4. **文字展開 / 語音捷徑 (Voice Shortcuts / Text Expansion)**
   - 說「我的地址」→ 自動展開為完整地址
   - Wispr Flow 稱為 "Flow Shortcuts"
   - Aqua Voice 稱為 "Autofill"

5. **多模式 (Smart Modes)**
   - 口述 / Email / 聊天 / 會議紀錄 / 翻譯 / AI 助手
   - 每個模式有不同的 AI 處理 prompt
   - Superwhisper 支援完全自訂模式 prompt

6. **Push-to-Talk**
   - 按住說話、放開辨識（桌面版通常用 Fn 鍵）
   - 部分支援 Hands-free mode（雙擊啟動，說完自動停）

7. **AI 改寫 / 後編輯 (AI Rewrite)**
   - 辨識完後，一鍵改語氣（更正式/更口語/更簡短/更詳細）
   - Willow Voice 的特色功能

8. **安靜模式 (Whisper Mode)**
   - 在安靜環境下小聲說也能辨識
   - Wispr Flow 和 Willow Voice 都有此功能

9. **個人化學習 (Personalization)**
   - 學習用戶的寫作風格和常用詞彙
   - 使用越久越準確
   - Wispr Flow: "learns your voice over time"

10. **隱私/安全**
    - SOC2 / HIPAA 合規（企業版）
    - 零資料保留選項
    - 部分產品支援離線模式

### 1.3 我們的獨特優勢 (Unique Differentiators)

**目前沒有任何競品能同時做到以下三點**：

| 優勢 | 說明 | 競品狀態 |
|------|------|---------|
| **真正的三語混合辨識** | 同一句話混合繁體中文+日文+英文，每個詞保持原語言不翻譯 | Purri 只支援繁中、Typeless 混語會翻譯成單一語言、其他競品都不支援同句混語 |
| **Android 鍵盤** | 系統級 IME 鍵盤，在任何 App 都能用 | Wispr/Willow/Aqua/Purri 都沒有 Android 版；Typeless 有但 UI 極簡 |
| **醫療業務專用** | 預裝日本醫療法規/藥品/診所相關詞庫 | 沒有針對日本醫療業務的語音產品 |
| **自架後端 (Self-hosted)** | 完全掌控資料，不依賴第三方 SaaS | Purri 用 BYOK 但仍限 OpenAI；其他競品都是他們的雲端 |
| **繁體中文保證** | 參考 Purri，Claude prompt 明確指定「繁體中文，絕對不輸出簡體」 | Purri 做到了這點，但它不支援日文/英文混合 |

### 1.4 2026 年市場格局總結

> ByeType 開發者精準總結：**「技術成熟/功能差異不大，白熱化產品賽道。使用者經驗/如何觸及使用者成為關鍵。」**

**定價趨勢：**
- Freemium + BYOK 正在興起（Purri、Spokenly、VoiceInk、ByeType）— 用戶自帶 API key 免費用
- 訂閱制主流在 $8-15/月（Wispr $12、Willow $15、Aqua $8、Typeless $12）
- 一次性購買仍有市場（VoiceInk $25、Voibe 一次性、Superwhisper $249 終身）
- 企業版：客製定價 + SOC2/HIPAA

**平台覆蓋：**
- macOS 是紅海：20+ 產品競爭
- **Android 是藍海**：僅 Typeless 和 Dragon Anywhere 有 AI 語音鍵盤（且 Typeless 有隱私疑慮）
- iOS：Wispr Flow、Willow、ByeType 有覆蓋
- Windows：Wispr Flow、Typeless、Aqua 有覆蓋
- 中國封閉市場：智譜 AutoTyper、豆包輸入法、微信輸入法（技術強但不出海）

**競品創辦人背景（參考 ByeType 整理）：**
- Wispr Flow：CEO Tanay Kothari 27歲 Stanford CS → $30M 融資
- Willow：兩位 20 歲 Stanford 華裔輟學生 → $4.2M 融資（YC 2025 batch）
- Typeless：留美中國人 Huang Song，2025 年底推出，主切中國外東亞市場
- ByeType：台灣 AI 工程師 Wei-Ren Lan，7 年語音 AI 經驗

**技術趨勢：**
- 2024-2025：從「逐字轉寫」進化到「AI 理解意圖」
- 2026：上下文感知 + 個人化風格學習成為標配
- 離線 vs 雲端兩派並存：隱私敏感用戶偏好離線（WhisperKit/whisper.cpp），品質追求者偏好雲端
- **iOS 端本地模型成熟**：WhisperKit（Argmax 優化）可在 iPhone 上跑 Whisper
- 開源方案大量出現：VoiceInk、OpenWhispr、FluidVoice、Freeflow、Ito、Handy

**隱私成為關鍵差異化：**
- Typeless 隱私疑慮被日本團隊揭露 → 使用者信任危機
- Wispr Flow / Willow 靠 SOC2 / HIPAA 認證建立信任
- 小開發者靠 BYOK + 本地模型 + 開源建立信任
- **我們的優勢**：自架後端 + 零追蹤 + 音檔不落地 + 開源可審計

**我們的市場定位：**
```
       高精度/AI 功能
            ↑
            │  Wispr Flow ★    Willow ★
            │        Aqua ★
            │
            │  ByeType (iOS)   SGH Voice ← 我們在這裡
            │                  (三語 + 醫療 + Android)
            │
            │  Typeless ⚠️     Purri
            │  (隱私疑慮)
  Android ←─┼──────────────────────────→ macOS/iOS 限定
            │
            │  Gboard          Apple Dictation
            │  (基礎功能)
            │
            ↓
       基礎轉寫
```

### 1.5 開源架構參考（供 Claude Code 開發用）

從 ByeType 和其他開源專案歸納，AI Dictation 的技術核心流程一致：

```
1. 使用者按下客製化鍵盤 → 觸發錄音
2. 音檔 → 語音辨識模型（Whisper API / WhisperKit 本地）
3. 透過系統 API 取得使用者正在輸入的 App 類別（mail/note/chat/search）
4. 辨識逐字稿 + App 場景 prompt → LLM 潤飾格式化
5. 輸出至游標位置
```

**流程的兩大要求**（引用 ByeType）：(a) 準確率高 (b) 完成時間快

**可參考的開源架構：**
| 專案 | 語言 | 用途 |
|------|------|------|
| [OpenWhispr](https://github.com/OpenWhispr/openwhispr) | TypeScript | 桌面版架構參考（ByeType 實際參考此專案） |
| [VoiceInk](https://github.com/AugustDev/VoiceInk) | Swift | macOS 版 AI Dictation 完整實作 |
| [FluidVoice](https://github.com/altic-dev/FluidVoice) | Swift | macOS 離線辨識 + AI 增強 |
| [WhisperInput](https://github.com/alex-vt/WhisperInput) | Kotlin | **Android Whisper 鍵盤**（最直接參考） |
| [FUTO Voice Input](https://gitlab.futo.org/alex/voiceinput) | Kotlin | **Android Whisper IME**（支援大模型+多語言） |

---

## 二、系統架構

### 2.1 整體架構

```
┌──────────────────────────────────┐
│  Android 手機 (鍵盤 IME)          │
│  ├─ VoiceKeyboardService        │
│  │   ├─ 錄音 (PCM 16kHz mono)   │
│  │   ├─ 模式選擇列               │
│  │   ├─ 候選區 (預覽+確認)       │
│  │   ├─ Power Mode (偵測 App)    │
│  │   └─ 基礎按鍵 (標點/空格/退格) │
│  ├─ ApiClient                   │
│  │   └─ HTTPS + Bearer Token    │
│  └─ SetupActivity               │
│      └─ 伺服器設定 + 鍵盤啟用    │
└───────────┬─────────────────────┘
            │ HTTPS (音檔上傳)
            ▼
┌─────────────────────────────────┐
│  Zeabur 後端 (Tokyo Region)      │
│  FastAPI + Python               │
│  ├─ /api/transcribe             │
│  │   ├─ [Layer 1] Whisper API   │──→ OpenAI (HTTPS, 不指定語言)
│  │   │   └─ 三語混合 prompt     │
│  │   ├─ [Layer 2] 詞庫修正      │
│  │   │   └─ 40+ 預設規則        │
│  │   ├─ [Layer 3] Smart Replace │
│  │   │   └─ 觸發詞展開          │
│  │   └─ [Layer 4] Claude 後處理  │──→ Anthropic (HTTPS, ZDR)
│  │       └─ 模式 prompt + 上下文 │
│  ├─ /api/modes                  │
│  ├─ /api/dictionary             │
│  ├─ /api/smart-replace          │
│  ├─ /api/power-rules            │
│  ├─ /api/history                │
│  ├─ /api/history/reprocess      │  ← NEW: 重新潤飾（參考 Purri）
│  ├─ /api/stats                  │  ← 含 token 用量+費用估算
│  └─ Dashboard (靜態網頁)         │
│                                 │
│  [持久儲存] /var/data            │
│  ├─ dictionary.json             │
│  ├─ modes.json                  │
│  ├─ smart_replace.json          │
│  ├─ power_rules.json            │
│  ├─ history.json                │
│  └─ stats.json                  │
└─────────────────────────────────┘
```

### 2.2 資安設計

| 層級 | 措施 | 說明 |
|------|------|------|
| 傳輸 | HTTPS | Zeabur 預設全站 TLS |
| 認證 | Bearer Token | 所有 API 端點都驗證 |
| 音檔 | 不落地 (in-memory) | 用 `io.BytesIO` 處理，不寫硬碟 |
| OpenAI | API 預設不訓練 | 可在 OpenAI 設定 Zero Data Retention |
| Anthropic | 預設 ZDR | API 呼叫不保留 |
| 歷史 | 可清除 | Dashboard 一鍵清除 |
| 涉及病患 | 提醒脫敏 | 避免全名+病歷號同時口述 |

---

## 三、功能規格

### 3.1 三語混合辨識管線 (核心技術)

這是整個系統最核心、也最難的部分。使用者可能說出：

> 「幫我跟鈴木先生のクリニック確認一下 appointment 的時間，然後把処方箋的 scan 寄到 author@shingihou.com」

**四層處理管線：**

#### Layer 1: Whisper API + 三語提示詞

```python
# 不指定 language（讓 Whisper 自動偵測，支援混語）
# 注入包含三語的 prompt，暗示 Whisper 這三種語言都會出現
prompt = "新義豊,KusuriJapan,個人輸入,薬機法,患者,クリニック,appointment,visa,workflow..."
```

- 使用 OpenAI Whisper API `whisper-1` 模型
- **不指定 language 參數**（指定任何一種語言會讓另外兩種全部辨識錯）
- prompt 包含三語詞彙（最多 224 tokens / ~800 字元）
- prompt 從 dictionary.json 的 custom_words + corrections values 自動組建

#### Layer 2: 詞庫自動修正

```python
# 預設 40+ 條修正規則，包含：
# - 品牌名稱統一（新义丰→新義豊, kusuri japan→KusuriJapan）
# - 三語混淆修正（カクニン→確認, ビザ→visa, アポ→appointment）
# - 法規術語（药机法→薬機法, 个人输入→個人輸入）
# - 技術術語（ultra vox→Ultravox, n8n→n8n）
# 長的優先比對，避免部分匹配
```

#### Layer 3: Smart Replace (觸發詞展開)

```
@mail → author@shingihou.com
@addr → 福岡県福岡市博多区博多駅南3-17-15
@co   → 新義豊株式会社
@coen → Shingihou Co., Ltd.
@name → 林 紀全
@ms   → MedicalSupporter
@kj   → KusuriJapan
@sgh  → SGH Phone
@pmd  → 薬機法（PMD Act）
```

#### Layer 4: Claude 後處理

```
系統提示核心規則：
1. 使用者經常在同一句話裡混合繁體中文、日文、英文
2. 每個詞保持原本說話時的語言，絕對不要翻譯
3. 如果 Whisper 把中文聽成日文片假名，還原為中文
4. 移除填充詞（嗯、啊、那個、えーと、あの、um、uh）
5. 偵測口語自我修正，只保留最終意圖（例：「兩點，不對，四點」→「四點」）
6. 根據當前模式的 prompt 調整輸出格式
7. ⚠️ 繁體中文保證（參考 Purri）：所有中文輸出一律使用繁體中文，
   絕對不輸出簡體中文。即使 Whisper 辨識結果含簡體字，也要轉為繁體。
8. 標點符號：中文段落使用全形標點（，。！？：；），
   日文段落使用日文標點，英文段落使用半形標點

使用者語言習慣描述：
- 日常溝通：繁體中文
- 日本醫療/法規術語：日文（患者、診察、処方、薬機法）
- 日本商業禮儀：日文（お疲れ様、よろしくお願いします）
- 國際/技術用語：英文（API、workflow、appointment、visa）
- 公司品牌固定寫法：新義豊、KusuriJapan、MedicalSupporter、SGH Phone
```

### 3.2 Smart Modes (9 個預設模式)

| ID | 圖示 | 名稱 | 行為描述 |
|----|------|------|---------|
| `dictate` | 📝 | 口述 | 直接轉文字。移除填充詞，保持混語原貌。 |
| `email` | ✉️ | Email | 自動格式化為 Email。判斷語言：日文為主用日文禮儀（拝啓等），中文為主用中文格式。 |
| `chat` | 💬 | 聊天 | 簡短口語化訊息。適合 LINE / Slack。 |
| `meeting` | 📋 | 會議 | 條列重點，區分討論/決議/待辦，標注負責人和時程。 |
| `code` | 💻 | 程式 | 保留技術術語，輸出 code/command 格式。 |
| `translate_zh` | 🇹🇼 | →中文 | 翻譯為繁體中文，專業術語保留原文加註。 |
| `translate_ja` | 🇯🇵 | →日本語 | 翻譯為日文，用商業敬語。 |
| `translate_en` | 🇺🇸 | →EN | 翻譯為英文。 |
| `assistant` | 🤖 | AI 助手 | 語音 Q&A。回答顯示在鍵盤上，不輸入文字框。點擊複製。 |

每個模式都有獨立的 Claude prompt，存在 `modes.json`，可透過 Dashboard 新增/修改。

### 3.3 Power Mode (上下文感知)

參考 Wispr Flow 和 VoiceInk 的做法，根據使用者正在用的 App 自動切換模式：

```json
{
  "enabled": true,
  "app_rules": {
    "com.google.android.gm": "email",
    "jp.naver.line.android": "chat",
    "com.linecorp.chatapp": "chat",
    "com.slack": "chat",
    "com.whatsapp": "chat",
    "com.facebook.orca": "chat",
    "com.termux": "code"
  }
}
```

Android 端透過 `currentInputEditorInfo.packageName` 取得目前 App 的 package name。

### 3.4 AI 改寫 (Post-Edit Rewrite) — 參考 Willow Voice

**新功能**：辨識結果出來後，可以一鍵改寫：

| 改寫選項 | 說明 |
|---------|------|
| ✨ 精簡 | 縮短文字，保留核心意思 |
| 📝 詳述 | 擴展細節，補充脈絡 |
| 👔 正式 | 轉為正式/商業語氣 |
| 💬 口語 | 轉為輕鬆/聊天語氣 |
| 🇹🇼 翻中 | 翻譯為繁體中文 |
| 🇯🇵 翻日 | 翻譯為日文 |
| 🇺🇸 翻英 | 翻譯為英文 |

實作方式：辨識結果顯示在候選區後，底部顯示改寫按鈕列。點擊後呼叫 `/api/rewrite` 端點，用 Claude 改寫。

### 3.5 自動學習 (Auto-Learning) — 參考 Wispr Flow / Willow Voice

當使用者在候選區看到辨識結果，手動修改後再輸入時，系統記錄修正對：

```
辨識結果: "カクニンして"
使用者修改: "確認して"
→ 自動加入 corrections: { "カクニン": "確認" }
```

短期先不實作（需要更複雜的 UI），但 API 端點預留。

### 3.6 Dashboard (Web 管理介面)

透過 Zeabur 網址存取的管理頁面，功能包含：

- 📊 統計：今日/本週/累計口述次數、字數、節省時間
- 💰 用量追蹤（參考 Purri）：本月 Whisper token 用量、Claude token 用量、估算費用（USD）、歷史月份對比
- 📖 歷史：搜尋/瀏覽所有辨識紀錄（raw + corrected + final 三欄對照）
- 🔄 重新潤飾（參考 Purri）：從歷史紀錄中選取，換模式重跑 Claude 處理
- 📚 詞庫：管理修正規則和自訂詞彙
- 🔄 Smart Replace：管理觸發詞
- 🎯 模式：管理/新增/編輯模式和 prompt
- ⚡ Power Rules：管理 App→模式 對應
- 🗑️ 清除歷史：一鍵清除所有紀錄（資安功能）

---

## 四、Android 鍵盤 UI 規格

### 4.1 鍵盤佈局

```
┌──────────────────────────────────────────────────┐
│ ⚡Auto │ 📝口述 │ ✉️Email │ 💬聊天 │ 📋會議 │ ... │  ← 模式列（可左右滑動）
├──────────────────────────────────────────────────┤
│                                                  │
│  辨識結果文字顯示在這裡                             │  ← 候選區（點擊輸入）
│  ↑ 點擊即可輸入 · ✉️ Email · 1.2s                 │
│                                                  │
│  [✨精簡] [👔正式] [💬口語] [🇹🇼中] [🇯🇵日] [🇺🇸EN] │  ← 改寫列（辨識後顯示）
├──────────────────────────────────────────────────┤
│          按住麥克風說話（中日英皆可）                │  ← 狀態文字
│                                                  │
│      [⌨️切鍵盤]      ( 🎙 )      [⌫退格]         │  ← 主操作列
│                                                  │
│  [，] [         Voice Input          ] [。] [↵]  │  ← 底部列
└──────────────────────────────────────────────────┘
```

### 4.2 操作流程

1. 使用者在任何 App 的輸入框喚出鍵盤
2. 看到 Voice Input 鍵盤介面
3. 頂部模式列：左右滑動選模式（預設 ⚡Auto = Power Mode）
4. **按住**中間麥克風按鈕 → 開始錄音（長按模式，預設）
   - 按鈕變紅 + 脈衝動畫
   - 輕微震動回饋 (50ms)
   - 狀態文字：「🔴 錄音中...放開即辨識」
5. **放開** → 停止錄音
   - 輕微震動回饋 (30ms)
   - 狀態文字：「⏳ 辨識中...」
   - PCM → WAV → 上傳到後端

   **短按模式**（參考 Purri，可在設定切換）：
   - 點一下麥克風 → 開始錄音
   - 再點一下 → 停止錄音
   - 或靜音 1.5 秒後自動停止
   - 適合較長的口述場景
6. 辨識結果顯示在候選區
   - 一般模式：顯示處理後的文字 + 改寫按鈕列
   - AI 助手模式：顯示回答 + 「🤖 AI 回答 — 點擊複製」
7. **點擊候選區** → 文字輸入到目前的輸入框
   - 或點擊改寫按鈕 → 改寫後再點擊輸入

### 4.3 視覺設計

- 深色主題（#1b1b2f 背景）
- 紫色強調色（#6c5ce7）
- 錄音中紅色（#e74c3c）
- 成功綠色（#00d2a0）
- 處理中黃色（#fdcb6e）

### 4.4 Android 元件結構

```
com.shingihou.voiceinput/
├── VoiceKeyboardService.kt    ← IME 主服務
│   ├─ 錄音管理 (AudioRecord, PCM 16kHz)
│   ├─ 長按/短按雙錄音模式 (NEW - 參考 Purri)
│   ├─ 短按模式靜音偵測 (1.5s 無聲自動停) (NEW)
│   ├─ PCM → WAV 轉換 (in-memory)
│   ├─ 模式選擇 UI
│   ├─ 候選區 UI
│   ├─ 改寫按鈕列 UI
│   ├─ Power Mode 偵測 (currentInputEditorInfo.packageName)
│   └─ 脈衝動畫 + 震動回饋
├── ApiClient.kt               ← 後端通訊
│   ├─ transcribe(audio, mode, appId)
│   ├─ rewrite(text, style)
│   ├─ reprocess(historyId, newMode) (NEW - 參考 Purri)
│   ├─ getModes()
│   └─ ping()
└── SetupActivity.kt           ← 設定頁面
    ├─ 伺服器 URL + Auth Token 輸入
    ├─ 連線測試
    ├─ 錄音模式切換（長按/短按）(NEW - 參考 Purri)
    ├─ 啟用鍵盤引導
    └─ Dashboard 連結
```

---

## 五、後端 API 規格

### 5.1 端點清單

| Method | Path | 說明 |
|--------|------|------|
| POST | `/api/transcribe` | 核心：上傳音檔 → 辨識 → 回傳結果 |
| POST | `/api/rewrite` | **NEW** 改寫已辨識的文字 |
| GET | `/api/stats` | 統計數據（含 token 用量+費用估算） |
| GET | `/api/history` | 辨識歷史（支援 search/n/month 參數） |
| POST | `/api/history/reprocess` | **NEW** 從歷史紀錄重新潤飾（換模式重跑，參考 Purri） |
| POST | `/api/history/clear` | 清除所有歷史 |
| GET | `/api/dictionary` | 取得詞庫 |
| POST | `/api/dictionary/correction` | 新增修正規則 |
| DELETE | `/api/dictionary/correction` | 刪除修正規則 |
| POST | `/api/dictionary/word` | 新增自訂詞彙 |
| DELETE | `/api/dictionary/word` | 刪除自訂詞彙 |
| GET | `/api/modes` | 取得所有模式 |
| POST | `/api/modes/{mode_id}` | 新增/更新模式 |
| DELETE | `/api/modes/{mode_id}` | 刪除模式 |
| GET | `/api/smart-replace` | 取得所有觸發詞 |
| POST | `/api/smart-replace` | 新增/更新觸發詞 |
| DELETE | `/api/smart-replace` | 刪除觸發詞 |
| GET | `/api/power-rules` | 取得 Power Mode 規則 |
| POST | `/api/power-rules` | 更新 Power Mode 規則 |
| GET | `/api/ping` | 健康檢查 |
| GET | `/` | Dashboard 網頁 |

### 5.2 核心端點詳細

#### POST /api/transcribe

```
Request:
  Content-Type: multipart/form-data
  Authorization: Bearer {token}
  Body:
    audio: File (WAV/WebM/M4A)
    mode: string (default: "dictate")
    app_id: string (Android package name, for Power Mode)

Response 200:
{
  "raw": "Whisper 原始辨識文字",
  "corrected": "詞庫修正 + Smart Replace 後的文字",
  "final": "Claude 處理後的最終文字",
  "mode": "email",
  "mode_name": "Email",
  "mode_icon": "✉️",
  "is_assistant": false,
  "process_time": 1.83
}

Error 400:
{ "error": "too_short", "message": "錄音太短" }
{ "error": "no_speech", "message": "未偵測到語音" }
```

#### POST /api/rewrite (NEW)

```
Request:
  Content-Type: application/json
  Authorization: Bearer {token}
  Body:
  {
    "text": "要改寫的文字",
    "style": "concise|expand|formal|casual|translate_zh|translate_ja|translate_en"
  }

Response 200:
{
  "original": "原始文字",
  "rewritten": "改寫後的文字",
  "style": "formal"
}
```

#### POST /api/history/reprocess (NEW - 參考 Purri 重新潤飾)

```
Request:
  Content-Type: application/json
  Authorization: Bearer {token}
  Body:
  {
    "history_id": "紀錄 ID",
    "new_mode": "email"
  }

Response 200:
{
  "original_raw": "Whisper 原始辨識文字",
  "original_final": "原本的處理結果",
  "new_final": "換模式後的新結果",
  "new_mode": "email",
  "new_mode_name": "Email"
}
```

#### GET /api/stats (更新 — 含用量追蹤)

```
Response 200:
{
  "today": { "count": 12, "words": 580, "saved_minutes": 4.8 },
  "week": { "count": 67, "words": 3200, "saved_minutes": 26.7 },
  "total": { "count": 450, "words": 21000, "saved_minutes": 175 },
  "usage": {
    "current_month": "2026-02",
    "whisper_seconds": 1350,
    "whisper_cost_usd": 0.54,
    "claude_input_tokens": 45000,
    "claude_output_tokens": 22000,
    "claude_cost_usd": 0.89,
    "total_cost_usd": 1.43
  },
  "monthly_history": [
    { "month": "2026-01", "total_cost_usd": 3.21, "count": 280 },
    { "month": "2025-12", "total_cost_usd": 2.85, "count": 245 }
  ]
}
```

### 5.3 技術棧

```
後端：
  - Python 3.11
  - FastAPI + uvicorn
  - openai (Whisper API)
  - anthropic (Claude API)
  - JSON 檔案儲存（/var/data）

部署：
  - Zeabur (Tokyo Region)
  - Dockerfile
  - 持久儲存掛載 /var/data

Android：
  - Kotlin
  - Min SDK 26 (Android 8.0)
  - OkHttp3 (HTTP)
  - Coroutines (async)
  - Material 3

環境變數：
  - OPENAI_API_KEY: Whisper API
  - ANTHROPIC_API_KEY: Claude API
  - AUTH_TOKEN: API 存取密碼
  - DATA_DIR: 資料儲存路徑（預設 /var/data）
  - CLAUDE_MODEL: Claude 模型（預設 claude-sonnet-4-5-20250929）
```

---

## 六、預裝資料

### 6.1 詞庫 (dictionary.json)

**修正規則 (~40 條)**：

| 類別 | 範例 |
|------|------|
| 品牌統一 | 新义丰→新義豊, kusuri japan→KusuriJapan, medical supporter→MedicalSupporter |
| 三語混淆 | カクニン→確認, レンラク→連絡, ビザ→visa, アポ→appointment |
| 法規術語 | 药机法→薬機法, 个人输入→個人輸入, tfda→TFDA |
| 技術術語 | ultra vox→Ultravox, claude code→Claude Code, mcp→MCP |
| 人名地名 | 林纪全→林 紀全, 福冈→福岡 |

**自訂詞彙 (~45 個)**：繁中+日文+英文混合的 Whisper prompt 提示詞。

### 6.2 Smart Replace (~9 條)

`@mail`, `@addr`, `@co`, `@coen`, `@name`, `@ms`, `@kj`, `@sgh`, `@pmd`

### 6.3 Power Mode Rules

Gmail→email, LINE→chat, Slack→chat, WhatsApp→chat, Termux→code

---

## 七、開發優先順序

### Phase 1: 核心可用 (MVP)

- [ ] 後端：FastAPI + Whisper + Claude + 四層管線
- [ ] 後端：所有 API 端點（含 /api/rewrite、/api/history/reprocess）
- [ ] 後端：Dashboard（統計+用量費用追蹤+詞庫管理）
- [ ] Android：鍵盤 IME 基礎架構
- [ ] Android：Push-to-talk 錄音（長按模式）
- [ ] Android：候選區顯示+點擊輸入
- [ ] Android：模式選擇列（9 個預設模式）
- [ ] Android：SetupActivity（含錄音模式切換：長按/短按）
- [ ] 部署：Dockerfile + Zeabur 部署指南

### Phase 2: 競品對齊（對標 Purri + Typeless）

- [ ] Android：短按錄音模式（點一下開始、再點一下停止、靜音自動停）— 參考 Purri
- [ ] Android：Power Mode (自動偵測 App)
- [ ] Android：改寫按鈕列（7 種改寫）— 參考 Purri 重新潤飾 + Willow AI Rewrite
- [ ] 後端：用量追蹤 API（token 數+費用估算）— 參考 Purri
- [ ] 後端：歷史重新潤飾 API — 參考 Purri
- [ ] 後端：Dashboard 完整功能（歷史搜尋+重新潤飾、模式編輯、Power Rules 編輯）
- [ ] Android：AI 助手模式 → 顯示回答+複製

### Phase 3: 超越競品

- [ ] 自動學習（記錄使用者修正，自動更新詞庫）— 對標 Wispr Flow / Willow
- [ ] 語音捷徑觸發詞偵測優化（@mail 等語音觸發，不限文字輸入）
- [ ] Dashboard 趨勢圖表（日/週/月用量+費用曲線）
- [ ] Hands-free mode（雙擊啟動，靜音 1.5 秒自動停）— 對標 Typeless 6 分鐘連續
- [ ] 安靜模式（低音量辨識優化）— 對標 Wispr Whisper Mode
- [ ] 語音指令修正文字（口述修改已辨識文字，不用手動打字）— 參考 ByeType
- [ ] 個人化風格學習（記錄用戶常用表達方式，微調 Claude prompt）

---

## 八、Claude Code 開發方法（參考 ByeType 實戰經驗）

### 8.1 開發工具準備

參考 ByeType 開發者成功用 Claude Code 7 天完成 iOS AI 語音鍵盤的經驗，我們的 Android 版建議採用類似工作流：

**Claude Code 配置：**
- 模型：首選 **Opus 4.6**（長時間處理維持一致性優於 Sonnet）
- 估計開發成本：~$200-400 USD（Claude Max + Extra Usage）

**Skills 準備：**
| Skill | 用途 |
|-------|------|
| `shingihou-business-automation` | 已有的 SGH 業務自動化 skill |
| Compound Engineering Plan（建議加入） | 結構化的 plan → review → implement 工作流 |
| UI/UX 優化 skill（建議加入） | 評估/優化介面設計 |

**Context 準備（給 Claude Code 的參考資料）：**
```
必要 Context：
├── 本規格書（sgh-voice-spec-v3.2.md）
├── 參考架構：WhisperInput（Kotlin Android Whisper 鍵盤）
├── 參考架構：FUTO Voice Input（Kotlin Android Whisper IME）
├── OpenAI Whisper API 文件
├── Anthropic Claude API 文件
├── Android IME 開發文件
└── 競品截圖：ByeType / Typeless / Purri 的 UI 截圖
```

### 8.2 施工流程（建議）

```
1. Claude Code Plan Mode → 規劃 feature + test（輸出 markdown 供人 review）
2. 人工 Review Plan → 確認架構/流程正確
3. Claude Code Implement → 實作功能
4. 人工測試 → 在真機上驗證
5. 修正 Bug → Claude Code Debug
6. Git commit → 進入下一個 feature
```

### 8.3 已知坑（ByeType 經驗 + Android 特有）

| 坑 | 說明 | 對策 |
|----|------|------|
| **State Management** | Agentic Coding 容易遺漏狀態管理，觸發 loop 或殘留狀態 | 主架構流程必須人工用自然語言清楚描述 |
| **音訊格式** | ASR vendor 有取樣率/格式限制（Whisper 要 16kHz mono） | 在規格書中明確指定：PCM 16kHz mono → WAV |
| **功能交互** | 新功能加入後可能影響已完成的功能 | 每次新功能後做全面回歸測試 |
| **Android IME 生命週期** | 跟 Activity 不同，Service 可能被系統回收 | 注意 `onCreateInputView` / `onStartInputView` 的差異 |
| **權限取得** | `RECORD_AUDIO` 在 IME Service 裡 runtime request 有限制 | 在 SetupActivity 裡提前取得權限 |
| **鍵盤高度** | 不同手機鍵盤高度不同，候選區可能被擋住 | 使用 `setInputView()` 動態調整高度 |

---

## 九、檔案結構

```
sgh-voice/
├── backend/
│   ├── main.py              ← FastAPI 主程式
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .gitignore
│   └── static/
│       └── index.html       ← Dashboard
├── android/                  ← Android Studio 專案
│   ├── build.gradle
│   ├── settings.gradle
│   ├── gradle.properties
│   └── app/
│       ├── build.gradle
│       └── src/main/
│           ├── AndroidManifest.xml
│           ├── res/
│           │   ├── layout/
│           │   │   ├── keyboard_view.xml
│           │   │   └── activity_setup.xml
│           │   ├── drawable/     ← 所有背景/圖示
│           │   ├── values/       ← strings.xml
│           │   └── xml/
│           │       └── method.xml
│           └── java/com/shingihou/voiceinput/
│               ├── VoiceKeyboardService.kt
│               ├── ApiClient.kt
│               └── SetupActivity.kt
├── ARCHITECTURE.md           ← 架構設計文件
├── INSTALL.md                ← 完整安裝教學
└── BUILD.md                  ← Android Studio 編譯教學
```

---

## 十、重要注意事項

### 10.1 Whisper 三語混合的已知限制

- Whisper 傾向「猜一個語言然後全部用那個語言辨識」
- **絕對不要**指定 `language` 參數
- prompt 必須包含三語詞彙來暗示混語場景
- 即使如此，仍會有 10-20% 的混語錯誤，依靠 Layer 2 和 Layer 4 修正
- 中文和日文共用漢字，Whisper 經常搞混（例如「確認」和「カクニン」）

### 10.2 Android IME 開發要點

- `RECORD_AUDIO` 權限必須在 runtime request
- `AudioRecord` 需要 `SAMPLE_RATE=16000, CHANNEL_IN_MONO, ENCODING_PCM_16BIT`
- PCM → WAV 需要手動寫 44 byte header
- 音檔用 `ByteArrayOutputStream` 收集，不寫入檔案系統（資安）
- `currentInputEditorInfo.packageName` 可以取得目前 App 的 package name
- 候選區使用 `commitText()` 輸入文字
- IME 服務的生命週期跟 Activity 不同，注意 `onCreateInputView` 和 `onStartInputView`

### 10.3 費用預估

| 服務 | 用量假設 | 月費 |
|------|---------|------|
| OpenAI Whisper | 每天 30 次 × 15 秒 = 7.5 分鐘/天 | ~$3-5 |
| Anthropic Claude | 每天 30 次 × ~500 token | ~$2-4 |
| Zeabur | Free/Developer Plan | $0-5 |
| **合計** | | **$5-14/月** |
