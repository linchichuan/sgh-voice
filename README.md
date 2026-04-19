# 🎙 SGH Voice — 讓想法流動，不再卡在鍵盤上 (v1.9.9)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + **原生語言保持**，資料 100% 掌控在手。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.9.9-green)]()

---

## 🌟 v1.9.9 重大更新：幻覺終結者（Anti-Hallucination Overhaul）

基於 762 筆真實歷史的差異分析，找出並修復了 LLM 後處理把指令當成對話回答的根本原因 — 模型選錯了。本次全面重構幻覺防護，幻覺率從 11.9% 降至 2.5%。

| 重點修復 | 說明 |
|------|------|
| **🎯 預設 LLM 改為 Claude Haiku 4.5** | **(Critical)** Groq + `gpt-oss-120b`（OpenAI 開源 reasoning 模型）幻覺率達 11.9%，會主動「重寫」輸入。改回 Claude 後降至 2.5%，差距 4.7 倍。 |
| **🔤 Whisper STT 注入個人詞庫** | **(New)** `_local_stt` / `_groq_stt` / `_whisper_api_fallback` 三函數現在會把使用者 `custom_words` + 場景詞彙 + 基礎詞庫一起餵給 Whisper，專有名詞首次正確率大幅提升。 |
| **🛡️ 三層幻覺檢測** | 66 個對話起手詞 + 9 個中段助理句型 + bigram 重疊率（< 30% 嚴判 / < 50% 配合縮減判定 / < 55% 配合擴寫判定）。 |
| **♻️ Whisper 重複幻覺 Sanitizer** | 偵測連續同一片段重複 ≥5 次（如「11.11.11...」、「財務所×16」），自動截斷到第一次出現。 |
| **⚡ 短指令自動 Skip LLM** | ≤60 字 + 全中日文 + 含動作詞（請、幫我、你幫、繼續、處理一下…）→ 直接跳過 LLM，避免被當成對話回答。 |
| **🎛️ System Prompt 完全重寫** | 移除舊版「條列呈現/長文整理」等誘導改寫的字眼，改成嚴格 transcoder 風格 + 雙語明確示範。 |
| **💾 啟用音檔備份** | 預設備份到 `~/.voice-input/audio_backup/`，為將來 CER 趨勢測試累積素材。 |

---

## 🚀 30 秒快速開始 (macOS)

1.  **安裝**: 從 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載 `.dmg` 拖入應用程式。
2.  **設定**: 打開 Dashboard 選項，首選 ASR 建議選擇 **Qwen3-ASR**。
3.  **說話**: 按住快捷鍵，無論是日文、英文或中文，都能精準轉錄並保持原語。

---

## 🤖 Android 測試計畫 (NPP)

我們需要 20 位熱血的測試者協助 Android 版通過 Google Play 審核。如果您是 Android 用戶，請務必加入我們！
👉 [立即填寫申請表](https://voice.shingihou.com/#beta)

---

## 🛠 技術深度

-   **多語引導協議**: 透過三語 Initial Prompt，將模型鎖定在「混合辨識」而非「翻譯」模式。
-   **轉碼安全**: 結合字數比例檢查與關鍵字過濾，雙重攔截 LLM 聊天幻覺。
-   **系統感知**: 自動偵測 OS 語系，給你最親切的介面。

---

© 2026 Shingihou Co., Ltd. All rights reserved.
