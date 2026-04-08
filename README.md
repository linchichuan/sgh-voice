# 🎙 SGH Voice — 讓想法流動，不再卡在鍵盤上 (v1.9.5)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + **機械式純文字精修**，資料 100% 掌控在手。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.9.5-green)]()

---

## 🌟 v1.9.5 重大更新：純粹輸入，拒絕聊天

這次更新我們解決了 AI 「太愛說話」的問題。SGH Voice 現在回歸工具本質，成為一個安靜且精準的文字轉碼零件。

| 重點功能 | 說明 |
|------|------|
| **🤐 絕對禁言模式** | **(New)** 重新定義 LLM 為「機械式轉碼器」，嚴禁 AI 回答使用者的問題或進行任何對話。 |
| **🛡️ 幻覺自動攔截** | **(New)** 新增語境偵測，若 AI 嘗試說出「好的、了解、您目前...」等廢話，系統將自動捨棄並回退原文。 |
| **✂️ 外科手術級編輯** | 延續 v1.8.0 的精準局部修改，選取文字後用語音下令，100% 保留您的原始排版。 |
| **🌍 全球語系適配** | 選單與日誌全面支援日/中/英三語，根據作業系統自動切換。 |
| **⚡ 毫秒級反應** | 透過優化後的啟動順序與多雲路由，維持不到一秒的處理神速。 |

---

## 🚀 30 秒快速開始 (macOS)

1.  **安裝**: 從 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載 `.dmg` 拖入應用程式。
2.  **設定**: 打開 Dashboard 填入您的 API Key (Groq 或 OpenRouter)。
3.  **說話**: 按住快捷鍵，說完放開，乾淨、精準的文字即刻貼上。

---

## 🤖 Android 測試計畫 (NPP)

我們需要 20 位熱血的測試者協助 Android 版通過 Google Play 審核。如果您是 Android 用戶，請務必加入我們！
👉 [立即填寫申請表](https://voice.shingihou.com/#beta)

---

## 🛠 技術深度

-   **轉碼協議**: 採用極低 Temperature (0.0) 與機械式指令集，確保輸出穩定性。
-   **多雲路由**: 智慧分流 ASR (mlx-whisper/Groq) 與 LLM (Llama 3.3/OpenRouter/Claude)。
-   **系統感知**: 自動偵測 OS 語系，並透過 Quartz 事件實現全系統級自動貼上。

---

© 2026 Shingihou Co., Ltd. All rights reserved.
