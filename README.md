# 🎙 SGH Voice — 讓想法流動，不再卡在鍵盤上 (v1.9.7)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + **原生語言保持**，資料 100% 掌控在手。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.9.7-green)]()

---

## 🌟 v1.9.7 重大更新：三語混合，原汁原味

這次更新我們優化了多語言環境下的表現，確保您說日文就是日文，說英文就是英文，絕不擅自翻譯。

| 重點功能 | 說明 |
|------|------|
| **🌐 原生語言保持** | **(New)** 重新設計的 STT 與 LLM 引導，確保中/日/英混合輸入時能 100% 保持原始語言，嚴禁自動翻譯。 |
| **🏆 Qwen 3.6 Plus** | **(New)** Dashboard 正式支援 2026 最新旗艦 Qwen 3.6，提供更精準的意圖理解。 |
| **🎙️ Qwen3-ASR 推薦** | 針對 CJK 語境優化的本地 ASR 引擎，解決漢字同音異義字問題。 |
| **🤐 絕對禁言模式** | 延續機械轉碼器設計，嚴禁 AI 回答問題或進行多餘對話。 |
| **🛡️ 幻覺攔截升級** | 強化對話語式偵測，自動過濾所有嘗試聊天的廢話。 |

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
