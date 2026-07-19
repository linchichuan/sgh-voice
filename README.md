# 🎙 SGH Voice — 讓想法流動，不再卡在鍵盤上 (v2.6.0)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + **原生語言保持**，資料 100% 掌控在手。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-2.6.0-green)]()

---

## 🌟 v2.6.0：可信的中日英混講個人化

| 重點改進 | 說明 |
|------|------|
| **詞庫真正接通辨識** | Dashboard 手動詞彙現在同時進入 STT 與 LLM prompt；舊詞庫格式會安全遷移，不再只是 UI 看得到。 |
| **只從人工修正學習** | Clipboard／History 修正會持久化為 verified examples；模型自己的輸出禁止自動反餵詞庫，0 筆學習資料會如實顯示。 |
| **中日英 routing 可控** | 新增混合 Auto、中文、日文、英文模式；Local／Groq／OpenAI primary 與 Hybrid 長度門檻皆按設定執行。 |
| **不可變片段保護** | 英文縮寫、單字母、假名、數字、日期、金額、版本、URL、Email、路徑不會被 LLM 擅自翻譯或改值。 |
| **可量測的多語基準** | Benchmark 依音檔語言執行，不再硬鎖中文，並輸出 CER、script 保留率、術語保留率與延遲。 |
| **失敗狀態誠實呈現** | 自動輸入失敗不再顯示完整成功；逐字稿仍保留於 History，可修正並成為可信學習資料。 |

## 🌟 v2.5.4：Fn／地球鍵快捷鍵修正

| 重點修復 | 說明 |
|------|------|
| **支援 Fn／地球鍵** | 錄音鍵可設為 `fn+right_shift`；也接受 `right_fn+right_shift` 與 `Right Fn + Right Shift`。 |
| **macOS 原生監聽** | 正確處理 keycode 63 與 SecondaryFn flag，按下開始、放開停止。 |
| **設定頁快速套用** | 新增「Fn／地球鍵 + 右 Shift」按鈕，儲存後顯示正規化結果並立即套用。 |
| **清楚的硬體限制** | macOS 不區分左右 Fn；部分外接鍵盤的硬體 Fn 若不送出系統事件，App 無法偵測。 |

## 🌟 v2.5.3：可編輯、免重啟的快捷鍵

| 重點修復 | 說明 |
|------|------|
| **避開 Codex 衝突** | 預設錄音鍵改為 `Right Option + Right Shift`，不再占用 Codex 使用的 `Right Cmd`。 |
| **五組快捷鍵可編輯** | 錄音、Quick-Rewrite、重試、取消與連續錄音都能在 Dashboard 直接修改。 |
| **儲存後立即生效** | Listener 會讀取最新設定，不必重開 App，也不會累積重複的背景監聽器。 |
| **不破壞前景文字** | Rewrite／Retry／Cancel 改用純修飾鍵組合，不再把 Option 字元送進編輯欄位，也不依賴 Fn 功能鍵模式。 |
| **衝突與格式守門** | 單一修飾鍵、未知按鍵、macOS 保留組合及快捷鍵前綴衝突會在儲存時明確阻擋。 |

## 🌟 v2.5.2：直接輸入與原剪貼簿保護

| 重點修復 | 說明 |
|------|------|
| **無剪貼簿直接輸入** | 支援的文字欄位改用 macOS `AXSelectedText` 在游標處插入，不再先覆蓋 Clipboard。 |
| **完整 Clipboard transaction** | Terminal 等不支援直接插入的 App，僅短暫借用 pasteboard，完成後還原文字、圖片、檔案、HTML、RTF 等所有格式。 |
| **穩定系統授權** | Build 優先使用固定 Apple signing identity，不再於每次打包自動重置 Accessibility 權限。 |
| **全新圖示** | App icon 改為暖黑／米白雙色，無藍框、無螢光、無漸層；選單列改為適應淺色／深色模式的單色狀態圖示。 |

## v2.5.1：中日英混用準確度修正

本次依實際歷史與音檔重新檢視 macOS 全管線，優先修正「STT 已辨識正確、後處理卻把語系改壞」的問題。

| 重點修復 | 說明 |
|------|------|
| **日文字體保護** | OpenCC 改為 clause-aware；含假名的日文句段不再把 `画像／動画／来週／参考` 轉成中文異體。 |
| **Code-switch 守門** | LLM 不得把 `supplier` 音譯為片假名、把 `mini` 翻成中文，亦不得切換平假名／片假名。 |
| **三語技術詞庫** | 新增 `SEO / AEO / GEO / contact form / お問い合わせフォーム / カタカナ / ひらがな / JSON-LD / hreflang` 與真實誤辨別名。 |
| **可信個人化** | Few-shot 僅使用 History 中人工編輯確認、且 script profile 相符的範例；不再拿模型自己的輸出自我強化。 |
| **可靠性與隱私** | History 每筆原子落盤；paste debug 改為 metadata-only；Ghostty 與 Codex Desktop 納入 App context。 |

---

## 🚀 30 秒快速開始 (macOS)

1.  **安裝**: 從 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載 `.dmg` 拖入應用程式。
2.  **設定**: 打開 Dashboard；日常中日英混用建議先用 **Groq Whisper large-v3-turbo**，需要離線時再選本地 Whisper。
3.  **說話**: 按住 `Right Option + Right Shift`，無論是日文、英文或中文，都能精準轉錄並保持原語。

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
