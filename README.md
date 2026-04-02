# 🎙 SGH Voice — 讓想法流動，不再卡在鍵盤上 (v1.6.1)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + 懂你的智慧潤稿，資料 100% 掌控在手。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.6.1-green)]()

---

## 🌟 v1.6.1 更新重點：更穩定、更人性

這次更新我們不只追求速度，更追求「懂你」。我們優化了 AI 的表達方式，讓產出的文字不再像冰冷的機器人，而是更流暢的自然語言。

| 重點功能 | 說明 |
|------|------|
| **🌐 雲端雙引擎備援** | 除了極速 Groq，新增 OpenRouter 支援 (200+ 模型)，預設 Nemotron Nano（實測 ~1.6s），確保服務永遠在線。 |
| **🔌 一鍵測試連線** | **(New)** Dashboard 設定頁新增「測試 LLM 連線」按鈕，即時顯示延遲與模型狀態。 |
| **📊 引擎狀態儀表板** | **(New)** 概覽頁即時顯示當前 STT 引擎、LLM 引擎 + 模型、使用場景。 |
| **🔒 安全加固** | **(New)** config.json 強制 600 權限、API 設定白名單驗證，防止未授權存取。 |
| **🧠 商務秘書 System Prompt** | 全新設計的 LLM 後處理：邏輯校正重組、結構化排版、日文敬語轉換、人性化加詞，一套 prompt 驅動所有引擎。 |
| **📱 Android 封測招募** | Android 版準備上線！我們正在招募首批測試夥伴，搶先體驗行動端的極速輸入。 |
| **🌍 全球語系適配** | 自動偵測你的 macOS 語言 (日/中/英)，從選單到日誌，給你最親切的介面。 |
| **⚡ 毫秒級反應** | 5 引擎自動 fallback，不到一秒的處理神速，讓你的思考與輸入完全同步。 |

---

## 🚀 30 秒快速開始 (macOS)

1.  **安裝**: 從 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載 `.dmg` 拖入應用程式。
2.  **設定**: 打開 Dashboard 填入你的 API Key (Groq 或 OpenRouter)。
3.  **說話**: 按住快捷鍵，說完放開，文字就已經幫你排版好貼上了。

---

## 🤖 Android 測試計畫 (NPP)

我們需要 20 位熱血的測試者協助 Android 版通過 Google Play 的審核。如果你是 Android 用戶且希望用語音解決繁瑣的打字，請務必加入我們！
👉 [立即填寫申請表](https://voice.shingihou.com/#beta)

---

## 🛠 技術深度

-   **5 引擎 LLM 路由**: Ollama (本地) / Groq / Claude / OpenAI / OpenRouter，智慧 fallback 鏈（全引擎覆蓋）。
-   **Dashboard 即時監控**: 一鍵測試連線、引擎狀態即時顯示、設定存檔即時生效免重啟。
-   **隱私第一**: config.json 強制 600 權限、API 欄位白名單驗證、聲紋驗證在本地完成。
-   **系統整合**: 透過 macOS 原生事件模擬，實現真正的「免切換」輸入。

---

© 2026 Shingihou Co., Ltd. All rights reserved.
