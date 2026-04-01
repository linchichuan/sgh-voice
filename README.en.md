# 🎙 SGH Voice — AI Voice Input Tool (v1.6.0)

**English** | **[日本語](README.ja.md)** | **[繁體中文](README.md)**

> Speak and get professional text. Trilingual Chinese-Japanese-English auto-detection + smart AI post-processing. 100% data ownership.

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-1.6.0-green)]()

---

## 🌟 What's New in v1.6.0

| Feature | Details |
|---------|---------|
| **🌐 OpenRouter Integration** | 200+ models including free ones (Qwen 3.6, DeepSeek V3, Gemini 2.5 Flash). Cloud backup ensures service never goes down. |
| **🧠 7-Rule System Prompt** | Redesigned LLM post-processing: filler removal, self-correction detection, proper noun correction, structured long-text formatting. One prompt powers all 5 engines. |
| **📱 Android Beta Recruitment** | Android version ready for testing! Join the first wave of testers. |
| **⚡ 5-Engine LLM Routing** | Ollama (local) / Groq / Claude / OpenAI / OpenRouter with automatic fallback chain. |
| **🌍 OS Language Adaptation** | Auto-detects your macOS language (JA/ZH/EN) for the friendliest UI experience. |

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Trilingual Mixing** | Freely switch between Traditional Chinese, Japanese, and English within the same sentence |
| **Traditional Chinese Triple Protection** | Whisper prompt → Claude system prompt → OpenCC s2twp |
| **Hybrid Smart Routing** | Short audio → local mlx-whisper, long audio → OpenAI Cloud |
| **AI Post-Processing** | Remove filler words (um, uh, えーと), self-correction detection, punctuation |
| **Personal Dictionary Learning** | Automatically accumulate correction rules, improving accuracy over time |
| **Smart Replace** | Trigger words like `@mail`, `@phone` auto-expand to configured values |
| **9 Rewrite Modes** | Concise / Formal / Meeting / Email / Technical / Casual / EN / JA / ZH translation |
| **🏥 Medical Scene Mode** | Japanese medical terminology, drug names, biotech glossary (v1.2) |
| **🩺 Medical Consultation** | Automatically condenses doctor-patient dialogue into a professional SOAP note format |
| **📋 Clipboard Auto-Learn** | Select and copy manually corrected text, and the system automatically learns the corrections for your personal dictionary |
| **Push-to-Talk / Toggle** | Hold Right Cmd to dictate, or tap once to start/stop |
| **Cross-Application** | System-level voice input, auto-paste to cursor position |
| **Web Dashboard** | Usage stats, history, dictionary management, settings |
| **Android IME** | Android keyboard IME, voice input in any app |
| **iOS App** | Native iPhone / iPad app, tap to record and transcribe instantly (v1.3) |

---

## Quick Start (DMG Installation)

### System Requirements

- macOS 14.0+ (Sonoma or later)
- Apple Silicon (M1/M2/M3/M4)
- Internet connection (if using cloud APIs)
- **Storage**: ~100MB (cloud-only) / ~3-6GB (with local models)

### API Keys & Model Preparation

This tool offers maximum flexibility — run entirely locally for free, or use powerful cloud APIs:

#### Plan A: Full Cloud (Recommended — lowest resource usage, highest accuracy)

1. **OpenAI API Key** (`sk-...`)
   - Purpose: Speech-to-Text (STT)
   - Get it: [OpenAI Platform](https://platform.openai.com/api-keys)
2. **Anthropic API Key** (`sk-ant-...`) (optional but highly recommended)
   - Purpose: AI post-processing (filler removal, terminology correction, formatting)
   - Get it: [Anthropic Console](https://console.anthropic.com/settings/keys)

#### Plan B: Hybrid Smart Routing (Local STT + Cloud LLM)

1. **Local Whisper model** — auto-downloads on first use (~1.5GB)
2. **Anthropic API Key** (same as Plan A)

#### Plan C: Fully Local (Free & maximum privacy)

1. **Local Whisper model** (auto-downloads)
2. **Local Ollama model** — Install [Ollama](https://ollama.com/download/mac), then run: `ollama run qwen2.5:3b`

### Installation

1. Download `SGH Voice-1.6.0-apple-silicon.dmg` from [Releases](https://github.com/linchichuan/sgh-voice/releases)
2. Drag **Voice Input** to Applications
3. First launch: Right-click → **Open** (allow macOS Gatekeeper once)
4. Menu bar shows 🎙 icon → click **Open Dashboard**
5. Configure API keys or enable **Hybrid Mode** in Dashboard settings

### macOS Permissions

| Permission | Purpose | Target |
|------------|---------|--------|
| Microphone | Recording | Voice Input |
| Accessibility | Auto-paste (Cmd+V) | Voice Input |
| Input Monitoring | Global hotkey listening | Voice Input |

---

## iOS App

### Requirements

- iPhone or iPad with iOS 17.0+
- Internet connection (for Whisper & Claude APIs)

### Features

- 🎤 **One-tap recording** — Large record button, tap to start/stop
- 🧠 **Whisper + Claude pipeline** — Same AI quality as desktop version
- 🏥 **Medical scene mode** — Pre-loaded Japanese medical terminology
- 📋 **One-tap copy** — Copy transcribed text to clipboard instantly
- 🔐 **Secure API key storage** — Keys stored in iOS Keychain
- ⚙️ **Customizable settings** — Model, style, scene, all configurable

### Setup

1. Open the project in Xcode: `ios/SGHVoice/SGHVoice.xcodeproj`
2. Select your device or simulator, press **▶️ Run**
3. Enter your API keys in Settings within the app
4. Tap the microphone button to start recording!

---

## Android IME

### Requirements

- Android 8.0+ (API 26)
- Internet connection

### Features

- ⌨️ **System keyboard** — Works in any app as an input method
- 🎤 **In-keyboard recording** — Tap microphone on keyboard to dictate
- 🏥 **Medical scene mode** — Shared terminology with desktop version
- 🔑 **BYOK** — Bring your own OpenAI & Anthropic API keys

### Installation

Download the APK from [Releases](https://github.com/linchichuan/sgh-voice/releases), or build from source at `android/SGHVoice/`.

---

## Usage

### Push-to-Talk (Default)

1. Menu bar shows 🎙
2. **Hold Right Cmd (⌘)** to start recording
3. **Release** to stop — auto-transcribes and pastes to cursor

### Dashboard

Click menu bar 🎙 → **Open Dashboard**, or visit `http://localhost:7865`

- **Overview**: Time saved, cost estimates, usage stats
- **History**: Search, copy, rewrite all transcription results
- **Dictionary**: Manage custom vocabulary and correction rules
- **Settings**: API keys, language, hotkeys, Hybrid mode toggle

---

## Architecture

### Five-Layer Processing Pipeline

```text
Hold hotkey → Microphone recording
       ↓
Layer 1: Whisper STT (Hybrid: local mlx-whisper / Cloud OpenAI)
       ↓
Layer 2: Dictionary correction (memory.apply_corrections)
       ↓
Layer 3: Smart Replace (@mail → email, etc.)
       ↓
Layer 4: LLM post-processing (5 engines: Ollama / Groq / Claude / OpenAI / OpenRouter)
       ↓
Layer 5: OpenCC s2twp (Traditional Chinese final protection)
       ↓
       Auto-paste to cursor
```

### Hybrid Smart Routing

| Condition | Route | Latency |
|-----------|-------|---------|
| Recording < 15s | Local mlx-whisper | ~0.5s |
| Recording ≥ 15s | Cloud OpenAI Whisper | ~1-2s |
| Text < 30 chars, no fillers | Skip LLM, dictionary only | ~0s |
| Text < 30 chars | Local Ollama Qwen 2.5 | ~0.3s |
| Text ≥ 30 chars | Cloud Claude Haiku 4.5 | ~0.5-1s |

### Tech Stack

```text
Runtime:          Python 3.12+
STT (Local):      mlx-whisper (Apple Silicon optimized)
STT (Cloud):      OpenAI Whisper API
LLM (Local):      Ollama + Qwen 3.5
LLM (Cloud):      Groq / Claude / OpenAI / OpenRouter (5-engine auto-fallback)
TradChinese:      OpenCC (s2twp)
Recording:        sounddevice + numpy
Hotkeys:          pynput
System:           rumps (macOS menu bar)
Dashboard:        Flask + vanilla HTML/JS
Auto-paste:       pyperclip + AppleScript (Cmd+V)
Packaging:        PyInstaller + create-dmg
iOS:              Swift, SwiftUI, Combine, AVFoundation
Android:          Kotlin, Jetpack Compose, OkHttp
```

---

## Cost Comparison

| Solution | Monthly Cost |
|----------|-------------|
| Typeless Pro | $12/mo |
| Wispr Flow | $12/mo |
| Superwhisper | $8.49/mo |
| **SGH Voice (normal use)** | **~$3-8/mo (API fees)** |
| **SGH Voice (short sentences)** | **~$1-3/mo (mostly local)** |

---

## Project Structure

```text
sgh-voice/
├── app.py              # Main app (menu bar + CLI + hotkeys)
├── transcriber.py      # Whisper + LLM five-layer pipeline
├── recorder.py         # Audio recording (sounddevice)
├── memory.py           # Dictionary memory + auto-learning
├── config.py           # Settings, scene presets, data persistence
├── dashboard.py        # Flask Web Dashboard
├── build.sh            # One-click DMG packaging
├── requirements.txt    # Python dependencies
├── static/
│   └── index.html      # Dashboard UI
├── android/SGHVoice/   # Android IME (Kotlin + Jetpack Compose)
├── ios/SGHVoice/       # iOS App (Swift + SwiftUI)
│   └── SGHVoice/
│       ├── API/        # ApiConfig, WhisperClient, ClaudeClient
│       ├── Audio/      # AudioRecorder (AVFoundation)
│       ├── Processing/ # DictionaryManager, TranscriptionPipeline
│       └── UI/         # MainView, MainViewModel, SettingsView
└── sgh-voice-web/      # Product website (voice.shingihou.com)
```

---

## Privacy & Security

| Item | Approach |
|------|----------|
| Audio data | Sent only to OpenAI/Anthropic APIs, no other servers |
| API Keys | Stored locally in `~/.voice-input/config.json` (macOS) or Keychain (iOS) |
| History | All stored locally, max 2000 entries |
| Account required | No |
| Data tracking | None |

---

## License

Private — Shingihou Co., Ltd. (新義豊株式会社) Internal Use

## Developer

**Lin Chichuan (林紀全)** — CEO, Shingihou Co., Ltd.

- 🌐 [shingihou.com](https://shingihou.com)
- 🎙️ [voice.shingihou.com](https://voice.shingihou.com)
- 📧 <service@shingihou.com>
