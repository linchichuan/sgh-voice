# 🎙 SGH Voice — 讓想法流動，不再卡在鍵盤上 (v1.6.5)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + **資深秘書級智慧編輯**，資料 100% 掌控在手。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.6.5-green)]()

---

## 🌟 v1.6.5 更新重點：智慧重組與內容進化

這不僅僅是修復錯字，而是讓 AI 成為你的專業編輯。v1.6.5 引入了強大的「商務邏輯推理」機制。

| 重點功能 | 說明 |
|------|------|
| **✍️ 智慧編輯與重組** | **(New)** LLM 現在能主動識別語音重點，自動使用【標題】與「條列式」重新排版訊息。 |
| **🧠 商務邏輯校正** | **(New)** 具備語境推理能力（如：依冷藏環境將「クルー」修正為「クール」），並自動補全商務敬語與禮儀。 |
| **🌐 雲端雙引擎備援** | 整合 Groq (極速) 與 OpenRouter (穩定)，確保靈感爆發時服務永遠在線。 |
| **🎨 人性化語感** | 徹底移除 AI 生硬回答感，讓產出的文字更像真人秘書整理的結果。 |
| **📱 Android 封測招募** | 持續招募測試夥伴，搶先體驗行動端的極速輸入。 |
| **⚡ 毫秒級反應** | 延續不到一秒的處理神速，思考與輸入完全同步。 |

---

## 🚀 30 秒快速開始 (macOS)

1.  **安裝**: 從 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載 `.dmg` 拖入應用程式。
2.  **設定**: 打開 Dashboard 填入你的 API Key (Groq 或 OpenRouter)。
3.  **說話**: 按住快捷鍵，說完放開，專業條列式文案即刻完成。

---

## 🤖 Android 測試計畫 (NPP)

我們需要 20 位熱血的測試者協助 Android 版通過審核。
👉 [立即填寫申請表](https://voice.shingihou.com/#beta)

---

## 🛠 技術架構

-   **編輯引擎**: 資深秘書級 System Prompt，主動進行邏輯校正與格式重組。
-   **多雲路由**: 智慧分流 ASR (mlx-whisper/Groq) 與 LLM (Llama 3.3/OpenRouter/Claude)。
-   **系統感知**: 自動偵測 OS 語系，並透過 Quartz 事件實現全系統級自動貼上。

---

© 2026 Shingihou Co., Ltd. All rights reserved.
