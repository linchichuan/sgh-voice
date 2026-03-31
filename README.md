# 🎙 SGH Voice — 極致 AI 語音輸入助手 (v1.5.1)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + AI 智慧潤稿，資料 100% 掌控。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.5.0-green)]()

---

## 🌟 2026 旗艦級更新 (v1.5.0)

SGH Voice v1.5.0 帶來了效能與品質的全面躍升，支援最新的旗艦 AI 模型，並實現了不到一秒的處理延遲。

| 特色功能 | 說明 |
|------|------|
| **旗艦模型支援** | 內建優化對 **Qwen 3.5 (本地)** 與 **Llama 3.3 70B (雲端)** 的整合 |
| **極致反應速度** | 透過 Groq 與本地 MLX 加速，平均處理時間低於 **1 秒** |
| **三語自動檢測** | 同一句話中繁體中文、日文、英文自由切換，自動校正不翻譯 |
| **🔐 聲紋驗證** | 只辨識綁定的聲音，自動過濾其他人說話與環境噪音 |
| **Hybrid 智慧分流** | 短音訊本地、長音訊雲端，兼顧隱私與效能 |
| **AI 智慧潤稿** | 去填充詞、語氣優化、自我修正偵測、專業排版 |
| **🏥 醫療特化模式** | 支援繁中、日文醫療術語・藥品名・生技名詞專用詞庫 |
| **跨平台支援** | macOS (DMG), Android (IME), iOS App 全面升級 |

---

## 🚀 快速開始 (macOS)

### 1. 下載安裝
前往 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載最新的 `.dmg` 檔案 (Apple Silicon 專用)。

### 2. 環境準備 (選配，建議使用)
- **本地端 (推薦)**: 安裝 [Ollama](https://ollama.com/) 並執行 `ollama run qwen3.5:latest`。
- **本地 ASR**: 執行 `pip install mlx-whisper` 以獲得最快的本地轉錄體驗。

### 3. API 金鑰設定
啟動 App 後，在選單列圖示旁開啟 **Dashboard**，填入您的 Groq API Key 或 Anthropic API Key。

---

## 🛠 技術架構

- **音訊層**: 高性能聲紋驗證與靜音偵測，防止幻覺產生。
- **ASR 層**: 混合模式 (Hybrid)，15 秒內音訊本地 MLX 辨識，長音訊走 Groq/OpenAI。
- **LLM 層**: 
  - **本地**: Ollama Qwen 3.5 (最新 2026 旗艦)。
  - **雲端**: Groq Llama 3.3 70B / Anthropic Claude 4.5。
- **系統層**: 使用 macOS Quartz CGEvent 實現無縫自動貼上。

---

## 📝 授權與隱私
- **100% 資料自主**: 本地模式下所有音訊與文字處理均在您的設備上完成。
- **通用 Prompt**: 內建專業商務潤稿邏輯，不含任何個人資訊或特定習慣。

---

© 2026 Shingihou Co., Ltd. All rights reserved.
