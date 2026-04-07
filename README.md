# 🎙 SGH Voice — 讓想法流動，不再卡在鍵盤上 (v1.8.0)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + **外科手術級智慧編輯**，資料 100% 掌控在手。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.8.0-green)]()

---

## 🌟 v1.8.0 重大更新：精準編輯與智慧過濾

這次更新我們帶來了更強大的「判斷力」。當對話環境混亂時，SGH Voice 能像專業祕書一樣，精準提取重點並過濾雜訊。

| 重點功能 | 說明 |
|------|------|
| **✂️ 外科手術級編輯** | **(New)** 選取文字後用語音下令修改，系統將以「最小變動」原則精準修正，100% 保留您辛苦排版好的結構。 |
| **🛡️ 訊號與雜訊過濾** | **(New)** 自動過濾視訊會議中的「聽得到嗎？」、「我找一下文件」等無關操作語，僅保留核心事實。 |
| **🧠 個人化風格記憶** | **(New)** 系統開始學習您的說話習慣與寫作風格，讓輸出的文字越來越像您的親筆。 |
| **🚀 啟動效能優化** | 解決了 macOS 下特定的系統警告，啟動更加平滑、不佔資源。 |
| **🌍 全球語系適配** | 選單與日誌全面支援日/中/英三語，根據作業系統自動切換。 |

---

## 🚀 30 秒快速開始 (macOS)

1.  **安裝**: 從 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載 `.dmg` 拖入應用程式。
2.  **設定**: 打開 Dashboard 填入您的 API Key (Groq 或 OpenRouter)。
3.  **說話**: 按住快捷鍵，說完放開，專業文案即刻完成。

---

## 🤖 Android 測試計畫 (NPP)

我們需要 20 位熱血的測試者協助 Android 版通過 Google Play 審核。如果您是 Android 用戶，請務必加入我們！
👉 [立即填寫申請表](https://voice.shingihou.com/#beta)

---

## 🛠 技術深度

-   **編輯協議**: 採用 XML 隔離技術與最小變動演算法，實現精準局部修改。
-   **多雲路由**: 智慧分流 ASR (mlx-whisper/Groq) 與 LLM (Llama 3.3/OpenRouter/Claude)。
-   **系統感知**: 自動偵測 OS 語系，並透過 Quartz 事件實現全系統級自動貼上。

---

© 2026 Shingihou Co., Ltd. All rights reserved.
