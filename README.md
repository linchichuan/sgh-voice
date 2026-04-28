# 🎙 SGH Voice — 讓想法流動，不再卡在鍵盤上 (v2.1.0)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + **原生語言保持**，資料 100% 掌控在手。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-2.1.0-green)]()

---

## 🌟 v2.1.0 重大更新：個人化與生產力升級

本次新增個人化 few-shot 後處理、全域 Quick-Rewrite 熱鍵、連續錄音模式與 VAD 自動分段，讓語音輸入更貼近個人寫作習慣，也更適合長時間工作流。

| 重點修復 | 說明 |
|------|------|
| **🧠 個人化 Few-shot 後處理** | 最近 3 筆 `whisper_raw → final_text` 歷史會自動注入 LLM messages，讓 5 個引擎沿用使用者標點、語氣與用詞習慣。 |
| **🎯 Dictionary 從歷史學習** | 新增 CLI 與 Dashboard endpoint，可從歷史修正中提取高頻詞典候選，支援 dry-run / apply 兩段式流程。 |
| **✏️ 全域 Quick-Rewrite 熱鍵** | 選取任意 App 文字後按 `right_option+r`，LLM 會改寫並自動貼回，支援 concise/formal/casual/email/technical/translate 等風格。 |
| **🎙 連續錄音模式** | 新增 VAD 自動分段，支援 voice/silence 邊界偵測、最短/最長片段保護與尾端靜音裁切。 |
| **💾 錄音檔外移** | 音檔備份預設移至 `/Volumes/Satechi_SSD/voice-input/audio_backup`，SSD 未掛載時自動略過備份。 |

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
