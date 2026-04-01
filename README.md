# 🎙 SGH Voice — 極致 AI 語音輸入助手 (v1.6.0)

**[English](README.en.md) | [日本語](README.ja.md) | 繁體中文**

> 說話即成專業文章。中日英三語自動辨識 + AI 智慧潤稿，資料 100% 掌控。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.6.0-green)]()

---

## 🌟 v1.6.0 重大更新

SGH Voice v1.6.0 強化了雲端備援能力，並啟動了 Android 平台的正式上線準備計畫。

| 特色功能 | 說明 |
|------|------|
| **🌐 OpenRouter 整合** | **(New)** 支援 OpenRouter API，可調用 200+ 種 AI 模型（如 DeepSeek V3, Qwen 2.5 72B）作為穩定備援。 |
| **📱 Android NPP 招募** | **(New)** 開啟 Android 封測計畫，招募外部測試者以滿足 Google Play 上線要求。 |
| **🌐 系統語言自動適配** | 選單、浮動視窗與後台日誌自動根據 macOS 系統語系 (日/中/英) 切換。 |
| **旗艦模型支援** | 內建優化對 **Qwen 3.5 (本地)** 與 **Llama 3.3 70B (雲端)** 的整合。 |
| **極致反應速度** | 透過 Groq 與本地 MLX 加速，平均處理時間低於 **1 秒**。 |
| **🔐 聲紋驗證** | 只辨識綁定的聲音，自動過濾其他人說話與環境噪音。 |
| **Hybrid 智慧分流** | 短音訊本地、長音訊雲端，兼顧隱私與效能。 |

---

## 🚀 快速開始 (macOS)

### 1. 下載安裝
前往 [Releases](https://github.com/linchichuan/sgh-voice/releases) 下載最新的 `.dmg` 檔案 (Apple Silicon 專用)。

### 2. 環境準備 (選配，建議使用)
- **本地端 (推薦)**: 安裝 [Ollama](https://ollama.com/) 並執行 `ollama run qwen3.5:latest`。
- **雲端備援 (推薦)**: 在 Dashboard 設定 **OpenRouter API Key**，確保在 Groq 忙碌時仍能正常潤稿。

---

## 🤖 Android 測試招募 (NPP)

我們正在進行 Android 版的 Google Play 上線前測試。如果您願意參與為期 14 天的封測並協助我們達成 20 人測試門檻，請前往 [官方網站](https://voice.shingihou.com/#beta) 提交您的 Gmail 資訊。

---

## 🛠 技術架構

- **多雲路由層**: 智慧切換 Groq (極速) 與 OpenRouter (穩定備援)，確保服務不中斷。
- **語言感知層**: 自動偵測 OS 環境，即時切換 UI 與 Log 語言 (Supports ja, zh, en)。
- **音訊層**: 高性能聲紋驗證與靜音偵測，防止幻覺產生。
- **ASR 層**: 混合模式 (Hybrid)，15 秒內音訊本地 MLX 辨識，長音訊走 Groq/OpenAI。
- **系統層**: 使用 macOS Quartz CGEvent 實現無縫自動貼上。

---

© 2026 Shingihou Co., Ltd. All rights reserved.
