# 🎙 SGH Voice — AI 音声入力ツール (v2.5.4)

**[English](README.en.md)** | **日本語** | **[繁體中文](README.md)**

> 話すだけでプロの文章に。中国語・日本語・英語の3言語を自動認識 + スマート AI 後処理。データは100%自社管理。

[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![iOS](https://img.shields.io/badge/iOS-17.0+-blue?logo=apple)](https://github.com/linchichuan/sgh-voice/releases)
[![Android](https://img.shields.io/badge/Android-8.0+-green?logo=android)](https://github.com/linchichuan/sgh-voice/releases)
[![Version](https://img.shields.io/badge/Version-2.5.4-green)]()

---

## 🌟 v2.5.4 の新機能

| 機能 | 詳細 |
|------|------|
| **Fn／地球儀キー対応** | 録音キーに `fn+right_shift` を設定できます。`right_fn+right_shift` と `Right Fn + Right Shift` も受け付けます。 |
| **macOS ネイティブ監視** | keycode 63 と SecondaryFn flag を処理し、押下で開始・解放で停止します。 |
| **ワンクリック設定** | 設定画面に「Fn／地球儀 + 右 Shift」を追加し、保存後は正規化された値を表示します。 |
| **ハードウェア制限を明記** | macOS は Fn の左右を区別しません。外付けキーボード内だけで動作する Fn は検出できません。 |

## 🌟 v2.5.3 の新機能

| 機能 | 詳細 |
|------|------|
| **Codex との競合を回避** | 録音ホットキーを Codex が使用する `Right Cmd` から `Right Option + Right Shift` へ変更しました。 |
| **5種類のホットキーを編集可能** | 録音、Quick-Rewrite、リトライ、キャンセル、連続録音を設定画面で変更できます。 |
| **保存後すぐに反映** | App の再起動や monitor の重複登録なしで、実行中の listener が新設定へ切り替わります。 |
| **入力中の文字を保護** | Rewrite／Retry／Cancel は修飾キーだけの組み合わせを使用し、Option 文字の入力や Fn 設定への依存をなくしました。 |
| **競合チェック** | 単独の修飾キー、未対応キー、macOS の予約ショートカット、前方一致による競合を保存前に検出します。 |

## 🌟 v2.5.2 の新機能

| 機能 | 詳細 |
|------|------|
| **クリップボード不要の直接入力** | 対応する入力欄では macOS `AXSelectedText` を使用し、カーソル位置へ直接入力します。 |
| **クリップボードの完全復元** | Terminal などでは pasteboard を一時利用しますが、テキスト・画像・ファイル・HTML・RTF を含む元の内容を復元します。 |
| **安定した権限管理** | 固定 Apple signing identity を優先し、ビルドのたびにアクセシビリティ権限をリセットしない構成に変更しました。 |
| **新しいアイコン** | 青い外枠と欠けた文字を廃止し、メニューバーもライト／ダークモード対応の単色アイコンに変更しました。 |

## v2.5.1 の新機能

| 機能 | 詳細 |
|------|------|
| **日本語表記の保護** | OpenCC を文節単位にし、`画像／動画／来週／参考` などの日本語字体を保持します。 |
| **コードスイッチ保護** | LLM が英単語を翻訳・音訳したり、ひらがな／カタカナを切り替えたりした出力を破棄します。 |
| **技術用語辞書** | SEO/AEO/GEO、contact form、お問い合わせフォーム、JSON-LD、hreflang などを追加しました。 |
| **確認済み Few-shot** | History でユーザーが編集した、同一 script profile の例だけを個人化に利用します。 |
| **履歴とプライバシー** | History を毎回原子的に保存し、貼り付けログから本文を除外しました。 |

---

## 主な機能

| 機能 | 説明 |
|------|------|
| **3言語混在認識** | 同一文内で繁体中国語・日本語・英語を自由に切り替え可能 |
| **繁体中国語3層防御** | Whisper prompt → LLM contract → 文節対応 OpenCC s2twp |
| **Hybrid スマートルーティング** | 短い音声 → ローカル mlx-whisper、長い音声 → OpenAI Cloud |
| **AI 後処理** | フィラー除去（えーと、あの、um、嗯）、自己修正検出、句読点整形 |
| **個人辞書学習** | 修正ルールを自動蓄積し、使うほど認識精度が向上 |
| **スマート置換** | `@mail`、`@phone` などのトリガーワードを自動展開 |
| **9種類のリライト** | 簡潔 / フォーマル / 議事録 / メール / 技術文書 / カジュアル / 英訳 / 日訳 / 中訳 |
| **🏥 医療シーンモード** | 日本語医療用語・薬品名・バイオテク用語の専用辞書（v1.2） |
| **🩺 医療診察記録** | 医師と患者の会話から専門的なSOAP形式のカルテ概要を自動生成 |
| **📋 自動学習 (Auto-Learn)** | 入力枠で修正後、Cmd+Cでコピーするだけでシステムが自動的に修正ルールを学習 |
| **Push-to-Talk / Toggle** | Right Option + Right Shift 長押しで録音、またはワンタップで開始/停止 |
| **クロスアプリケーション** | システムレベルの音声入力、認識後カーソル位置に自動貼り付け |
| **Web ダッシュボード** | 使用統計、履歴、辞書管理、設定 |
| **Android IME** | Android キーボード入力方式、どのアプリでも音声入力可能 |
| **iOS アプリ** | iPhone / iPad ネイティブアプリ、タップで録音・即時認識（v1.3） |

---

## クイックスタート（DMG インストール）

### システム要件

- macOS 14.0+（Sonoma 以降）
- Apple Silicon（M1/M2/M3/M4）
- インターネット接続（クラウド API 使用時）
- **ストレージ**：約100MB（クラウドのみ）/ 約3〜6GB（ローカルモデル使用時）

### API キーとモデルの準備

本ツールは高い柔軟性を提供します。完全無料のローカルモード、または強力なクラウド API から選択できます：

#### プラン A：フルクラウド（推奨 — 省リソース、最高精度）

1. **OpenAI API Key**（`sk-...`）
   - 用途：音声テキスト変換（STT）
   - 取得：[OpenAI Platform](https://platform.openai.com/api-keys)
2. **Anthropic API Key**（`sk-ant-...`）（任意ですが強く推奨）
   - 用途：AI 後処理（フィラー除去、用語修正、自動整形）
   - 取得：[Anthropic Console](https://console.anthropic.com/settings/keys)

#### プラン B：Hybrid スマートルーティング（ローカル STT + クラウド LLM）

1. **ローカル Whisper モデル** — 初回使用時に自動ダウンロード（約1.5GB）
2. **Anthropic API Key**（プラン A と同じ）

#### プラン C：フルローカル（無料、最高プライバシー）

1. **ローカル Whisper モデル**（自動ダウンロード）
2. **ローカル Ollama モデル** — [Ollama](https://ollama.com/download/mac) をインストール後、`ollama run qwen2.5:3b` を実行

### インストール手順

1. [Releases](https://github.com/linchichuan/sgh-voice/releases) から最新の Apple Silicon 用 DMG をダウンロード
2. DMG を開き、**Voice Input** を Applications フォルダへドラッグ
3. 初回起動：右クリック → **開く**（macOS Gatekeeper を一度許可）
4. メニューバーに SGH Voice のマイクアイコンが表示されたら **Open Dashboard** をクリック
5. ダッシュボード設定で API キーを入力、または **Hybrid モード** を有効化

### macOS 権限設定

| 権限 | 用途 | 対象 |
|------|------|------|
| マイク | 録音 | Voice Input |
| アクセシビリティ | 自動貼り付け（Cmd+V） | Voice Input |
| 入力監視 | グローバルホットキー | Voice Input |

---

## iOS アプリ

### 動作要件

- iOS 17.0+ の iPhone または iPad
- インターネット接続（Whisper & Claude API 用）

### 機能

- 🎤 **ワンタップ録音** — 大きな録音ボタン、タップで開始/停止
- 🧠 **Whisper + Claude パイプライン** — デスクトップ版と同じ AI 品質
- 🏥 **医療シーンモード** — 日本語医療用語を事前搭載
- 📋 **ワンタップコピー** — 認識テキストを即座にクリップボードにコピー
- 🔐 **安全な API キー保管** — iOS Keychain に暗号化保存
- ⚙️ **カスタマイズ可能** — モデル、スタイル、シーンすべて設定可能

### セットアップ

1. Xcode でプロジェクトを開く：`ios/SGHVoice/SGHVoice.xcodeproj`
2. デバイスまたはシミュレータを選択して **▶️ 実行**
3. アプリ内の設定で API キーを入力
4. マイクボタンをタップして録音開始！

---

## Android IME

### 動作要件

- Android 8.0+（API 26）
- インターネット接続

### 機能

- ⌨️ **システムキーボード** — 入力方式として任意のアプリで使用可能
- 🎤 **キーボード内録音** — キーボード上のマイクボタンをタップしてディクテーション
- 🏥 **医療シーンモード** — デスクトップ版と共通の医療用語辞書
- 🔑 **BYOK** — OpenAI & Anthropic の API キーを自由に設定

### インストール

[Releases](https://github.com/linchichuan/sgh-voice/releases) から APK をダウンロード、または `android/SGHVoice/` からソースビルド。

---

## 使い方

### Push-to-Talk（デフォルト）

1. メニューバーに SGH Voice のマイクアイコンが表示
2. **Right Option（⌥）+ Right Shift（⇧）を長押し** して録音開始
3. **離す** と停止 → 自動認識してカーソル位置に貼り付け

### ダッシュボード

メニューバーの SGH Voice アイコン → **Open Dashboard**、またはブラウザで `http://localhost:7865`

- **概要**：節約時間、月額費用見積もり、使用統計
- **履歴**：検索、コピー、全認識結果のリライト
- **辞書**：カスタム語彙と修正ルールの管理
- **設定**：API キー、言語、ホットキー、Hybrid モード切替

---

## アーキテクチャ

### 5層処理パイプライン

```text
ホットキー長押し → マイク録音
       ↓
Layer 1: Whisper STT（Hybrid: ローカル mlx-whisper / クラウド OpenAI）
       ↓
Layer 2: 辞書修正（memory.apply_corrections）
       ↓
Layer 3: スマート置換（@mail → email 等）
       ↓
Layer 4: LLM 後処理（5エンジン: Ollama / Groq / Claude / OpenAI / OpenRouter）
       ↓
Layer 5: OpenCC s2twp（繁体中国語最終防御）
       ↓
       カーソル位置に自動貼り付け
```

### Hybrid スマートルーティング

| 条件 | ルート | レイテンシ |
|------|--------|-----------|
| 録音 < 15秒 | ローカル mlx-whisper | ~0.5s |
| 録音 ≥ 15秒 | クラウド OpenAI Whisper | ~1-2s |
| テキスト < 30文字、フィラーなし | LLM スキップ、辞書修正のみ | ~0s |
| テキスト < 30文字 | ローカル Ollama Qwen 2.5 | ~0.3s |
| テキスト ≥ 30文字 | クラウド Claude Haiku 4.5 | ~0.5-1s |

### 技術スタック

```text
ランタイム:         Python 3.12+
音声認識（ローカル）: mlx-whisper（Apple Silicon 最適化）
音声認識（クラウド）: OpenAI Whisper API
後処理（ローカル）:   Ollama + Qwen 3.5
後処理（クラウド）:   Groq / Claude / OpenAI / OpenRouter（5エンジン自動フォールバック）
繁体中国語変換:      OpenCC (s2twp)
録音:              sounddevice + numpy
ホットキー:         pynput
システム連携:        rumps (macOS メニューバー)
ダッシュボード:      Flask + 純正 HTML/JS
自動貼り付け:        pyperclip + AppleScript (Cmd+V)
パッケージング:      PyInstaller + create-dmg
iOS:               Swift, SwiftUI, Combine, AVFoundation
Android:           Kotlin, Jetpack Compose, OkHttp
```

---

## 費用比較

| ソリューション | 月額費用 |
|-------------|---------|
| Typeless Pro | $12/月 |
| Wispr Flow | $12/月 |
| Superwhisper | $8.49/月 |
| **SGH Voice（通常使用）** | **~$3-8/月（API 使用料）** |
| **SGH Voice（短文中心）** | **~$1-3/月（ほぼローカル）** |

---

## プロジェクト構成

```text
sgh-voice/
├── app.py              # メインアプリ（メニューバー + CLI + ホットキー）
├── transcriber.py      # Whisper + LLM 5層パイプライン
├── recorder.py         # 音声録音（sounddevice）
├── memory.py           # 辞書メモリ + 自動学習
├── config.py           # 設定、シーンプリセット、データ永続化
├── dashboard.py        # Flask Web ダッシュボード
├── build.sh            # ワンクリック DMG パッケージング
├── requirements.txt    # Python 依存関係
├── static/
│   └── index.html      # ダッシュボード UI
├── android/SGHVoice/   # Android IME（Kotlin + Jetpack Compose）
├── ios/SGHVoice/       # iOS アプリ（Swift + SwiftUI）
│   └── SGHVoice/
│       ├── API/        # ApiConfig, WhisperClient, ClaudeClient
│       ├── Audio/      # AudioRecorder (AVFoundation)
│       ├── Processing/ # DictionaryManager, TranscriptionPipeline
│       └── UI/         # MainView, MainViewModel, SettingsView
└── sgh-voice-web/      # 製品ウェブサイト (voice.shingihou.com)
```

---

## プライバシーとセキュリティ

| 項目 | 対応 |
|------|------|
| 音声データ | OpenAI/Anthropic API にのみ送信、他のサーバーを経由しない |
| API キー | ローカルの `~/.voice-input/config.json`（macOS）または Keychain（iOS）に保存 |
| 履歴 | すべてローカル保存、最大2000件 |
| アカウント | 不要 |
| データ追跡 | なし |

---

## ライセンス

Private — 新義豊株式会社 社内利用

## 開発者

**林 紀全（リン チチュアン）** — 代表取締役, 新義豊株式会社

- 🌐 [shingihou.com](https://shingihou.com)
- 🎙️ [voice.shingihou.com](https://voice.shingihou.com)
- 📧 <service@shingihou.com>
