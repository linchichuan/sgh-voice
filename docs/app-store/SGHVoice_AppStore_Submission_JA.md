# SGH Voice iOS — App Store Connect 提出パック（日本語）

> 作成基準日：2026年8月9日
> 対象：SGH Voice iOS 2.7.0（Build 8）
> Bundle ID：`com.shingihou.SGHVoice`
> 対応OS：iOS / iPadOS 17.0以降
> 対応デバイス：iPhone / iPad
> 事業者：新義豊株式会社（SHINGIHOU CO., LTD.）

本書は、現行リポジトリの実装と2026年8月9日時点のApple公式要件を照合して作成した、App Store Connectへ転記するための提出原稿です。

`［提出前入力］` と記載した箇所は、実在する担当者情報または審査専用情報へ置き換えてください。APIキー、パスワード、個人情報は本書、ソースコード、スクリーンショット、公開URLへ記載しません。

## 0. 提出可否

現時点では、以下を完了するまで **App Reviewへ提出しないでください**。

1. Apple Developer Programの法人登録と契約・年会費・Account Holder権限を有効化する。
2. Xcode 26以降およびiOS 26 SDK以降でRelease Archiveを作成し、実機・Archive検証を完了する。
3. 審査担当者がprovider API credentialを受け取らず全主要機能を確認できる、Shingihou Evaluation Accessを実装する。App Reviewへ渡すのは新義豊発行のfirst-party access codeだけとし、provider API keyは渡さない。
4. iPhone 6.9インチ用とiPad 13インチ用の実画面スクリーンショットを準備する。
5. App Privacyの回答、Privacy Manifest、公開プライバシーポリシー、実際の第三者AI設定を一致させる。

## 1. App Store基本情報

| App Store Connect項目 | 入力案 |
|---|---|
| Primary Language | Japanese |
| App Name | `SGH Voice - AI音声入力` |
| Subtitle | `話すだけで文字起こし・多言語翻訳` |
| Bundle ID | `com.shingihou.SGHVoice` |
| Version | `2.7.0` |
| Build | `8` |
| SKU | `SGHVOICE-IOS-2026`（既存SKUがある場合は変更しない） |
| Primary Category | `Productivity（仕事効率化）` |
| Secondary Category | `Utilities（ユーティリティ）` |
| Price | `Free`（第三者AIのAPI利用料は利用者が各社へ直接負担） |
| Copyright | `2026 SHINGIHOU CO., LTD.` |
| Version Release | 初回は `Manually release this version` を推奨 |

### 名称に関する注意

- App Nameは18 characters / UTF-8 26 bytes、Subtitleは16 characters / UTF-8 48 bytesです。
- App NameとSubtitleはいずれもAppleの30文字上限内です。
- App Store上で名称が既に使用されている場合は、App Nameを `SGH Voice by Shingihou` とし、Subtitleは変更しません。
- 「最速」「最高精度」「完全」「100%」等、根拠を提示できない比較・保証表現は追加しません。

### 現行iOS実装との照合

| 項目 | 現行実装 |
|---|---|
| STT | OpenAI：既定`whisper-1`（model欄は編集可）／Groq：`whisper-large-v3-turbo`固定 |
| LLM | Anthropic：`claude-haiku-4-5-20251001`ほか設定画面の5候補／OpenAI：`gpt-4o`／Groq：`openai/gpt-oss-120b`／None |
| 出力スタイル | `normal`＝一般文字、`line`＝LINE向け、`email`＝フォーマルメール |
| シーン | `general`＝一般、`medical`＝医療・薬品・生技用語プリセット |
| 翻訳先 | 繁體中文、日本語、English、한국어から1〜4言語 |

metadataへ記載する機能名はこの表を上限とし、他プラットフォームにのみ存在する機能を混在させません。

## 2. Promotional Text

以下をそのまま転記できます。

```text
話した内容を読みやすい文章へ整え、1回の録音から最大4言語へ翻訳。利用者が選んだ外部AIを使うBYOK方式で、APIキーはiOS Keychainに保存されます。
```

実測：81 characters / UTF-8 197 bytes。Appleの170 characters上限内です。

## 3. Description

以下をそのまま転記できます。

```text
SGH Voiceは、話した内容を文字に変換し、読みやすく整えたり、複数の言語へ翻訳したりできる音声入力アプリです。

録音ボタンをタップして話し、もう一度タップすると処理を開始します。認識後の文字は画面で確認し、ワンタップでコピーできます。質問や依頼を話した場合も、その内容に回答するのではなく、発話の意味と語調を保った文字として整理します。

主な機能
・ワンタップで録音を開始・停止
・1回につき最長10分の音声入力
・音声認識結果の句読点・改行・表記をAIで整理
・繁體中文、日本語、English、한국어から1〜4言語を選ぶ多言語翻訳
・元の音声認識結果と整理後の結果を確認
・一般、LINE向け、フォーマルメール向けの出力スタイル
・一般用および医療・薬品・生技用の用語プリセット
・結果をクリップボードへコピー

BYOK（Bring Your Own Key）方式
本アプリの利用には、OpenAIまたはGroqの音声認識APIキーが必要です。AIによる文章整理・翻訳には、選択したAnthropic、OpenAIまたはGroqのAPIキーが必要です。API利用料金、利用上限および契約条件は各サービス提供者の定めに従い、利用者が各社へ直接負担します。本アプリ内でAPI利用料の購入や決済は行いません。

プライバシー
録音は利用者が操作した時だけ開始します。通常のBYOK利用では、音声は利用者が選択した音声認識サービスへ、文字起こし後のテキストは選択した文章処理サービスへ端末から直接送信され、新義豊株式会社のサーバーを経由しません。初回録音前に送信先と処理内容をアプリ内で説明し、同意を取得します。APIキーはiOS Keychainに保存され、新義豊株式会社のサーバーへ送信されません。iOS版の録音ファイルは一時領域で処理し、読み込み後、録音の取消時、またはアプリがバックグラウンドへ移行した時に削除します。

医療・薬品・生技用プリセットについて
このプリセットは、用語の認識と表記を補助するためのものです。本アプリは診断、処方、治療方針の提示、医療判断または医療機器としての機能を提供しません。出力内容は必ず利用者自身で確認してください。適切な契約と組織内ルールがない限り、特定の患者を識別できる情報を入力しないでください。

利用要件
・iOSまたはiPadOS 17.0以降
・インターネット接続
・対応する第三者AIサービスのAPIキー

音声認識および翻訳結果の正確性・完全性は保証されません。重要な文章は利用者自身で確認してから使用してください。
```

- 上記Description本文：1,094 characters / UTF-8 2,958 bytes。Appleの4,000 characters上限内です。
- Evaluation AccessはApple審査専用の内部経路であり、一般利用者向けの公開Descriptionには記載しません。Review Notes、審査専用のアプリ内同意、Privacy Policyでのみ正確に説明します。

## 4. Keywords

App Store Connect入力値：

```text
文字起こし,ディクテーション,翻訳,多言語,議事録,文章作成,音声認識,BYOK
```

- 40 characters / UTF-8 98 bytes。Appleの100 bytes上限内で、各キーワードは2文字を超えています。
- App Name、会社名、他社アプリ名は重複登録しません。

## 5. URL

| 項目 | 入力値 | 状態・注意 |
|---|---|---|
| Support URL | `https://voice.shingihou.com/terms.html` | 現在の公開ページに会社所在地と問い合わせメールを掲載。専用Supportページ作成後は差し替えを推奨 |
| Privacy Policy URL | `https://voice.shingihou.com/privacy.html` | iOSのデータ経路、第三者AI、保存期間、削除方法、問い合わせ先を掲載 |
| Privacy Choices URL | `https://voice.shingihou.com/privacy.html` | 任意項目。端末内削除と外部AI側の削除方法を案内 |
| Marketing URL | `https://voice.shingihou.com/` | SGH Voice公式サイト |

提出直前に、未ログイン環境およびモバイル回線からHTTP 200、TLS証明書、言語切替、問い合わせ情報を確認してください。

## 6. App Privacy回答案

### 6.1 最初の質問

**Do you or your third-party partners collect data from this app?**

回答案：`Yes, we collect data from this app.`

理由：通常のBYOK経路で新義豊株式会社のサーバーへ保存しない場合でも、音声・テキストはアプリの主要機能として外部AIへ送信され、一部サービスでは不正利用監視等のため一定期間保持される場合があります。また、Evaluation Accessでは新義豊の分離された審査用proxyを経由します。「Data Not Collected」は選びません。

### 6.2 申告するデータタイプ

| App Store Connectのデータタイプ | Collect | Purpose | Linked to User | Tracking | 根拠 |
|---|---:|---|---:|---:|---|
| User Content > Audio Data | Yes | App Functionality | Yes | No | 録音音声をOpenAIまたはGroqのSTTへ送信 |
| User Content > Other User Content | Yes | App Functionality | Yes | No | 文字起こし結果、翻訳元テキスト、用語・シーンプロンプトを選択した外部AIへ送信 |
| Health & Fitness > Health | Yes | App Functionality | Yes | No | 医療・薬品・生技プリセットで、利用者が任意に話した医療情報を処理する可能性があるため保守的に申告 |

各データタイプについて、次を選択します。

- Third-Party Advertising：`No`
- Developer's Advertising or Marketing：`No`
- Analytics：`No`
- Product Personalization：`No`
- App Functionality：`Yes`
- Other Purposes：`No`
- Linked to the user's identity：`Yes`
- Used for tracking：`No`

「Linked」は、データが利用者自身のBYOKアカウントに紐づく可能性を踏まえた保守的回答です。新義豊株式会社が独自ユーザーアカウントを発行していることを意味しません。

### 6.3 現行iOS実装では申告しないデータタイプ

次の項目は、現行iOSコードに該当する取得処理がないため `No` とします。

- Contact Info
- Financial Info / Payment Info / Purchase History
- Location
- Contacts
- Photos or Videos
- Emails or Text Messages
- Browsing History / Search History
- Device ID
- Product Interaction / Advertising Data / Other Usage Data
- Crash Data / Performance Data / Other Diagnostic Data
- Environment Scanning / Hands / Head

### 6.4 提出直前の条件付き確認

`Identifiers > User ID` は、次の条件を確認して最終決定します。

- APIキーは認証ヘッダーとして送信されますが、現行アプリは新義豊のユーザーIDを発行・収集しません。
- 選択したプロバイダーがAPIキー、account IDまたは認証トークンをリクエストログへ保持し、アプリから収集したデータとして扱う場合は、`User ID / App Functionality / Linked / Not Tracking` を追加します。
- OpenAI、Groq、Anthropicの契約・管理画面・Data Controlsを提出時点で再確認し、Privacy ManifestとApp Privacyの回答を一致させます。

IPアドレスまたは接続メタデータをプロバイダーがリクエスト処理時間を超えて保持する場合も、Appleの定義に従って該当データタイプを追加してください。

Evaluation Accessについて、提出前に次を確定し、アプリ内説明、公開プライバシーポリシー、App Privacy回答、Review Notesを一致させます。

- 音声・文字起こし本文・処理用プロンプトが端末から新義豊のisolated review proxyを経由してproviderへ送られること。
- first-party access codeの有効期間、短時間session tokenの有効期間、利用上限、rate limit、監査メタデータの項目と保存期間。
- 音声および文字起こし本文をproxyで永続保存しない設計を実装・検証すること。保存する場合は、目的・保存期間・削除方法を明示し、App Privacy回答を修正すること。
- access codeは審査中およびAppleによる再審査の可能性がある期間を通して有効に保ち、session tokenだけを短時間で更新すること。
- 現在公開中のプライバシーポリシーは通常BYOKの直結経路を中心に記載しているため、Evaluation Accessを実装したBuildは、proxy経路の説明を公開ポリシーへ追加するまで提出しないこと。

### 6.5 第三者AIの保存期間を説明するための社内メモ

- OpenAI API：初期設定では学習に利用されませんが、abuse monitoring logsに内容が含まれ、通常は最長30日保持される場合があります。
- Groq：推論の入力・出力は初期設定では保持されませんが、信頼性または不正利用調査用ログが最長30日一時保持される場合があります。
- Anthropic Messages API：通常の会話内容は現在の標準条件では保持されません。ただし、`claude-fable-5` は30日保持が必須でZero Data Retention対象外です。

上記は公開プライバシーポリシーと一致させ、各社の条件変更時に更新してください。

## 7. Age Rating回答案

現行iOS版は利用者の発話を私的に文字化・整理・翻訳するツールであり、利用者間でコンテンツを公開・配信・共有する機能はありません。

### In-App Controls

| 質問 | 回答案 |
|---|---|
| Parental Controls | No |
| Age Assurance | No |

### Capabilities

| 質問 | 回答案 | 理由 |
|---|---|---|
| Unrestricted Web Access | No | プライバシーポリシーへの外部リンクのみで、アプリ内ブラウザは提供しない |
| User-Generated Content | No | 作成した文字を広範囲へ配信する機能がない |
| Social Media | No | フィード、投稿、検索、リアクション等がない |
| Messaging and Chat | No | 利用者間通信およびAIチャット機能がない |
| Advertising | No | 広告SDKおよび広告表示がない |

### Content Descriptors

| 区分 | 回答案 |
|---|---|
| Profanity or Crude Humor | None |
| Horror/Fear Themes | None |
| Alcohol, Tobacco, or Drug Use or References | None |
| Medical or Treatment Information | None |
| Health or Wellness Topics | None |
| Mature or Suggestive Themes | None |
| Sexual Content or Nudity | None |
| Graphic Sexual Content and Nudity | None |
| Cartoon or Fantasy Violence | None |
| Realistic Violence | None |
| Prolonged Graphic or Sadistic Realistic Violence | None |
| Guns or Other Weapons | None |
| Gambling | No |
| Simulated Gambling | None |
| Contests | None |
| Loot Boxes | No |

医療用語プリセットは用語認識の補助であり、診断、服薬指導、治療情報、セルフケア推奨を提供しないため、現行実装ではMedical / Wellnessを `None` とします。将来、医療情報の生成、健康助言、AIチャット、公開共有機能を追加した場合は必ず再回答してください。

- Made for Kids：`No / Not Applicable`
- Override to Higher Age Rating：`Not Applicable`
- 想定結果：`4+`。最終レーティングはApp Store Connectの自動計算結果に従います。
- Regulated Medical Device Status：現行機能では `No`。法務・薬事責任者による最終確認を行います。

## 8. App Review連絡先

App Store ConnectのApp Review Informationへ、実際に連絡可能な担当者を入力します。

| 項目 | 入力値 |
|---|---|
| First Name | `［提出前入力：名］` |
| Last Name | `［提出前入力：姓］` |
| Phone Number | `［提出前入力：国番号付き電話番号］` |
| Email | `［提出前入力：常時受信できる会社メール］` |

審査期間中は、電話とメールに日本時間外でも対応できる連絡体制を用意してください。

## 9. Review Notes

### 9.1 提出前に準備する審査用情報

2026年8月9日時点のiOSコードにはEvaluation AccessのUI / client / review proxyがまだ存在しません。以下を実装・検証し、公開プライバシーポリシーを更新するまで、このReview Notesを提出してはいけません。

- Appleへ提供するのは、新義豊が発行したfirst-party access codeのみとする。
- access codeを新義豊のisolated review proxyで検証し、アプリには短時間session tokenを発行する。
- provider API credentialはAppleへ提供せず、アプリ、バイナリ、Review Notes、リポジトリへ埋め込まない。
- access codeはApp Reviewおよび再審査の可能性がある期間を通して有効に保つ。短時間で失効・更新するのはsession tokenだけとする。
- proxyに費用上限、rate limit、利用停止手段、最小限の監査ログを設定する。音声・文字起こし本文の保存有無と削除時点は実装後の事実を記載する。

### 9.2 転記用Review Notes

以下の `［提出前入力］` を実装後の事実で置き換えてから、App Review InformationのNotes欄へ転記してください。**placeholderが1件でも残る状態では提出不可**です。完成稿はUTF-8で4,000 bytes以内にします。

```text
SGH Voiceをご審査いただき、ありがとうございます。

【概要】
本アプリは音声の文字起こし、文章整理、1〜4言語への翻訳を行います。質問・依頼を録音しても回答せず、発話の意味と語調を保った文字として処理します。新義豊の利用者アカウント、広告、アプリ内課金、定期購読はありません。

【Evaluation Access】
provider API keyは不要です。次の新義豊発行access codeをご利用ください。
Access code：［提出前入力：first-party review access code］
有効期間：［提出前入力：審査および再審査を含む期間］
利用上限：［提出前入力］
このcodeは審査・再審査期間中有効です。アプリはcodeを新義豊のisolated review proxyで検証し、短時間session tokenを取得します。provider credentialはAppleへ提供せず、アプリにも保存しません。

【確認手順】
1. アプリを起動し、右上の歯車ボタンから「設定」を開きます。
2. ［提出前入力：Evaluation Accessの実画面名］を選び、access codeを入力して［提出前入力：有効化ボタン名］をタップします。
3. 「完了」で戻り、「音声入力を開始」をタップします。外部処理の説明を確認して「同意して続ける」を選び、マイクを許可します。
4. 「来週の月曜日、午前十時に打ち合わせをお願いします」と話して停止します。「音声入力結果」、「元の認識テキストを表示」、コピーを確認できます。
5. 録音ボタンを長押しし、日本語とEnglishを選択します。「今天下午三點開會，請準備資料」と話して停止すると、2言語の翻訳が表示されます。

【審査時のデータ経路】
Evaluation Accessでは、音声・文字起こし本文・処理用プロンプトが端末から新義豊のisolated review proxyを経由して選択済みAI providerへ送信されます。proxyでの本文保持：［提出前入力：実装済みの保持・削除仕様］。監査メタデータ：［提出前入力：項目と保存期間］。録音の端末一時ファイルは読込後・取消時・バックグラウンド移行時に削除され、バックグラウンド録音は行いません。

通常利用のBYOK経路は利用者のAPI keyをKeychainに保存し、端末からproviderへ直接送信します。審査ではBYOKを使用しません。

プライバシーポリシー：https://voice.shingihou.com/privacy.html

【医療プリセット】
専門用語の認識補助のみです。診断、処方、治療・健康助言、医療判断、医療機器機能は提供しません。実在する患者情報は入力しないでください。

Evaluation Accessとaccess codeは審査および必要な再審査の期間中、利用可能な状態に維持します。
```

- 上記Review Notes本文：**UTF-8 2,967 bytes / 1,253 characters**（末尾改行を含む、placeholder置換前の実測値）。
- placeholder置換後にもUTF-8 byte数を再計測し、4,000 bytes以内であることを確認します。

## 10. TestFlight Beta Description

```text
SGH Voice iOS版は、利用者自身が選択した外部AIを使って音声を文字に変換し、文章整理と多言語翻訳を行うBYOK型アプリです。

今回のベータでは、録音から文字起こしまでの安定性、質問へ回答しない音声入力処理、1回の録音から最大4言語への翻訳、初回の外部AI処理同意、録音一時ファイルの削除、APIキーのKeychain保存、iPhone / iPad表示を重点的に確認します。

AppleのBeta App Review担当者は、provider API keyではなく新義豊発行のEvaluation Access codeを使用します。一般の外部テスターは、割り当てられたEvaluation Accessまたは自身が契約するOpenAI / Anthropic / GroqのAPIキーを使用します。実在する患者情報、機密情報、個人情報は入力しないでください。
```

上記Beta Description本文：391 characters / UTF-8 863 bytes。

## 11. What to Test

```text
次の項目をご確認ください。

1. 初回起動時、API設定がない状態から設定画面へ移動できること。
2. Apple審査用Buildでは、first-party Evaluation Access codeを入力し、短時間session tokenで主要機能を利用できること。provider API keyを審査担当者へ要求しないこと。
3. 通常のBYOKでは、OpenAIまたはGroqのSTTと、Anthropic・OpenAI・Groq・NoneのLLMを選択できること。
4. 初回録音前に、利用中の経路に即した音声・テキスト・用語情報の送信説明が表示され、同意または取消が選べること。
5. マイク権限を許可後、タップで録音を開始し、再タップで停止・処理できること。
6. 日本語、繁體中文、英語、および中日英が混在する短い発話を文字起こしできること。
7. 質問文・依頼文を話してもAIが回答せず、発話内容を文字として保持すること。
8. 長押しで翻訳先を1〜4言語選択し、1回の録音から各言語の結果を表示できること。
9. 翻訳APIが不正な形式または失敗を返した場合、原文を翻訳結果として表示しないこと。
10. 元の音声認識結果を開き、整理後の結果と比較できること。
11. コピーアイコンで現在の結果をクリップボードへコピーできること。
12. 録音中にアプリをバックグラウンドへ移すと録音が停止し、一時録音が削除されること。
13. 設定からクラウド処理同意を撤回できること。
14. 「APIキー、用語辞書、設定を削除」でKeychain内のAPIキーと端末設定を削除できること。
15. iPhoneとiPadの縦・横表示で、文字の切れ、重なり、操作不能がないこと。

不具合報告には、端末、OS、Build番号、選択したprovider / model、再現手順、エラーメッセージを記載してください。APIキー、発話本文、患者情報は添付しないでください。
```

上記What to Test本文：845 characters / UTF-8 2,037 bytes。

## 12. Reviewer用の逐次確認フロー

このフローは提出前の社内スモークテストにも使用します。

### A. 初期設定

1. 新規インストール状態で起動する。
2. メイン画面、ステータスカード、結果欄、録音ボタン、設定ボタンが表示されることを確認する。
3. 設定を開き、`［提出前入力：Evaluation Accessの実画面名］`を選択する。
4. 新義豊発行のfirst-party access codeを入力し、`［提出前入力：有効化ボタン名］`をタップする。provider API keyは入力しない。
5. 短時間session tokenが発行され、Evaluation Accessが利用可能と表示されることを確認する。
6. 「完了」で戻る。

### B. 同意とマイク権限

1. 録音ボタンをタップする。
2. 外部AI処理同意画面に、Evaluation Accessでは音声・文字・用語情報が新義豊のisolated review proxyを経由してproviderへ送信される説明があることを確認する。
3. プライバシーポリシーのリンクを開けることを確認する。
4. 「同意して続ける」をタップし、iOSのマイク権限を許可する。

### C. 音声入力

1. 「来週の月曜日、午前十時に打ち合わせをお願いします」と話す。
2. 停止後、処理完了まで待つ。
3. 発話の意味、日時、依頼の語調が保たれ、質問への回答や追加提案が生成されていないことを確認する。
4. 元の認識文字を開き、結果との差分を確認する。
5. コピーを実行する。

### D. 多言語翻訳

1. 録音ボタンを長押しする。
2. 日本語とEnglishを選択し、翻訳録音を開始する。
3. 「今天下午三點開會，請準備資料」と話して停止する。
4. 日本語とEnglishの見出し・翻訳が表示されることを確認する。
5. 翻訳が命令を実行した回答ではなく、原文の依頼を翻訳した内容であることを確認する。

### E. プライバシーと削除

1. 録音中にアプリをバックグラウンドへ移し、録音停止メッセージを確認する。
2. 設定でクラウド処理同意を撤回し、次回録音時に再度説明が表示されることを確認する。
3. 最後にローカルデータ削除を実行し、APIキー欄と設定が初期化されることを確認する。

## 13. スクリーンショット構成

Appleの現行仕様では1〜10枚を登録できます。iPhone対応では最大のiPhone表示枠、iPad対応を維持する場合は13インチiPad表示枠を準備します。端末フレーム、背景、キャプションを合成する場合も、画面内容は提出Buildの実装と一致させてください。

### 13.1 iPhone 6.9インチ — 推奨7枚

| 順番 | 実画面 | キャプション案 | 撮影条件 |
|---:|---|---|---|
| 1 | メイン画面・録音前 | `話すだけで、読みやすい文字に` | APIキーや個人情報を表示しない |
| 2 | 録音中 | `タップで録音、最長10分` | 赤い停止状態と録音中ステータスを表示 |
| 3 | 聴写結果と原文表示 | `原文を保ち、句読点と改行を整理` | 架空の一般業務文を使用 |
| 4 | 翻訳言語選択sheet | `1回の録音から最大4言語へ` | 繁體中文・日本語・English・한국어を表示 |
| 5 | 2言語以上の翻訳結果 | `翻訳結果をまとめて確認・コピー` | 実在の人物・患者・会社案件を使用しない |
| 6 | 外部AI処理同意 | `送信先とデータ経路を事前に表示` | 同意内容とPrivacy Policyリンクを表示 |
| 7 | 設定・プライバシー | `利用するAIを自分で選択` | SecureFieldは空欄または完全マスク。削除機能も見せる |

### 13.2 iPad 13インチ — 推奨6枚

| 順番 | 実画面 | キャプション案 | 撮影条件 |
|---:|---|---|---|
| 1 | 縦向きメイン画面 | `iPadでも、すぐに音声入力` | レイアウトの余白と中央カラムを確認 |
| 2 | 横向き録音中 | `大きなボタンで録音を開始・停止` | 横向きで重なりがないこと |
| 3 | 聴写結果 | `整理後と元の認識文字を確認` | 長文でもスクロール可能な状態 |
| 4 | 翻訳言語選択 | `4言語から必要な翻訳先を選択` | sheetの全選択肢を表示 |
| 5 | 多言語翻訳結果 | `複数言語の結果を一つの画面で` | 見出しと本文が読みやすいこと |
| 6 | 設定と同意 | `APIキーは端末のKeychainに保存` | APIキーを絶対に写さない |

### 13.3 スクリーンショット禁止事項

- 実在する患者名、病歴番号、症状、処方、連絡先、音声波形を載せない。
- APIキー、account ID、メールアドレス、通知内容、端末固有情報を載せない。
- 未実装のiOSキーボード拡張、システム全体への自動入力、ローカルAI、履歴、声紋、SOAPカルテ生成を示さない。
- 「完全オフライン」「データは端末外へ出ない」「100%正確」「医療対応済み」等を画像内へ記載しない。
- AndroidまたはmacOS画面をiOS App Store用スクリーンショットへ混在させない。

## 14. 使用してはならない主張

App Store metadata、スクリーンショット、Webサイト、Review Notesで、確認できない次の表現を使用しません。

- 「100%正確」「誤変換なし」「最高精度」「最速」
- 「完全無料」「使い放題」— 第三者API料金が発生するため
- 「完全オフライン」「すべて端末内処理」— iOS版は外部AIへ送信するため
- 「データを一切保存しない」「Zero Data Retention」— providerとmodelにより保持条件が異なるため
- 「匿名」「追跡不可能」— BYOKアカウントと紐づく可能性があるため
- 「HIPAA準拠」「GDPR完全準拠」「個人情報保護法完全準拠」
- 「医療機器」「診断支援」「処方支援」「治療提案」「医療判断」
- 「保険診療完全対応」「電子処方箋対応済」「治療効果を保証」
- 「医師監修」「正式ライセンス取得済」— 根拠と許諾を確認できないため
- 「患者情報を安全に入力できる」— 適切なBAA / DPA等をアプリが確認しないため
- 「バックグラウンド録音」「常時録音」— 現行iOS版は行わないため
- 「iOSキーボードとして全アプリへ直接入力」— 現行iOS版にKeyboard Extensionはないため
- 「ローカルWhisper / Ollama対応」— 現行iOS版はクラウド処理のみのため
- 「OpenRouter / ElevenLabs対応」— 現行iOS版の選択肢にないため
- 「発話履歴を保存・検索」「声紋認証」「SOAPカルテ自動生成」— 現行iOS版にないため
- 「AIアシスタント」「質問へ回答」— 現行iOS版は聴写・翻訳用途に限定しているため

## 15. 送信前チェックリスト

### 15.1 Apple Developer / App Store Connect

- [ ] SHINGIHOU CO., LTD.の法人登録が承認され、MembershipがActiveになっている。
- [ ] Account Holderが最新のApple Developer Program License Agreementを受諾している。
- [ ] 年会費、税務、銀行、契約ステータスに未処理項目がない。
- [ ] App Store ConnectでApp recordを作成し、Bundle IDが`com.shingihou.SGHVoice`と一致している。
- [ ] Primary Language、App Name、SKU、カテゴリを確定している。
- [ ] EUで配信する場合、Digital Services ActのTrader Statusと連絡先表示を完了している。

### 15.2 Build / Signing

- [ ] 完全版Xcode 26以降を使用し、iOS 26 SDK以降でArchiveしている。
- [ ] Release構成、Distribution certificate、Provisioning Profile、Teamを確認している。
- [ ] Version `2.7.0`、Build `8`がApp Store Connect上で重複していない。
- [ ] iOS 17.0の実機と最新iOS / iPadOSの実機またはSimulatorで確認している。
- [ ] `PrivacyInfo.xcprivacy`がArchiveへ含まれている。
- [ ] Required Reason APIのUserDefaults理由`CA92.1`が、アプリ自身の設定保存用途と一致している。
- [ ] `ITSAppUsesNonExemptEncryption = NO`がRelease Archiveへ反映されている。
- [ ] 標準のHTTPS / Keychain以外に独自暗号化または追加暗号ライブラリが含まれていないことを再確認している。
- [ ] OrganizerのValidate AppとUploadをエラーなしで完了している。

### 15.3 機能テスト

- [ ] 新規インストール、マイク許可、拒否後の復帰を確認している。
- [ ] OpenAI STT、Groq STTをそれぞれ実APIでスモークテストしている。
- [ ] Anthropic、OpenAI、Groq、Noneの各LLM経路を確認している。
- [ ] 音声入力で質問・依頼へ回答せず、発話として保持することを確認している。
- [ ] 翻訳1言語、2言語、4言語を確認している。
- [ ] API timeout、401、429、5xx、空応答、不正JSON時に誤った結果を表示しないことを確認している。
- [ ] 10分上限、バックグラウンド遷移、取消時に録音が停止・削除されることを確認している。
- [ ] コピー、原文表示、設定保存、同意撤回、ローカルデータ削除を確認している。
- [ ] iPhone / iPad、縦 / 横、Dynamic Type、VoiceOverで主要操作を確認している。

### 15.4 Metadata / Screenshots

- [ ] App Name、Subtitle、Promotional Text、Description、Keywordsを日本語localizationへ転記している。
- [ ] Keywordsが100 bytes以内で、会社名・App Name・無関係な商標を重複させていない。
- [ ] Support / Privacy / Marketing URLが公開状態で、ログイン不要、HTTP 200である。
- [ ] Support URLに実際の会社所在地と問い合わせ先がある。
- [ ] iPhone 6.9インチ用スクリーンショットを1〜10枚登録している。
- [ ] iPad対応を維持する場合、13インチiPad用スクリーンショットを1〜10枚登録している。
- [ ] スクリーンショットにAPIキー、個人情報、患者情報、未実装機能がない。
- [ ] App icon 1024×1024、透過なし、提出Buildと一致している。

### 15.5 Privacy / Compliance

- [ ] App PrivacyでAudio Data、Other User Content、HealthをApp Functionalityとして申告している。
- [ ] Linked to Userを`Yes`、Trackingを`No`としている。
- [ ] User ID、IPアドレス、providerの接続ログを提出時点の契約・Data Controlsで再確認している。
- [ ] Privacy Manifest、App Privacy、アプリ内同意、公開ポリシーでproviderとデータタイプが一致している。
- [ ] OpenAI、Groq、Anthropic、Fable 5の保存期間を公開ポリシーに記載している。
- [ ] アプリ内に同意撤回と端末内データ削除の導線がある。
- [ ] 広告、追跡、IDFA、分析SDKが追加されていない。
- [ ] 医療プリセットを診断・処方・治療または医療機器として説明していない。
- [ ] Age Rating回答を保存し、Appleの計算結果を確認している。
- [ ] Regulated Medical Device Statusを法務・薬事責任者と確認している。
- [ ] Export Complianceの質問をArchiveの実態に基づいて回答している。

### 15.6 TestFlight / App Review

- [ ] Internal TestFlightでproduction相当Buildを確認している。
- [ ] External TestFlight用のBeta Description、What to Test、Feedback Emailを入力している。
- [ ] 最初のExternal BuildがBeta App Review対象になる前提で準備している。
- [ ] Shingihou Evaluation AccessのUI、isolated review proxy、first-party access code、短時間session tokenを実装・検証している。
- [ ] 審査担当者が追加契約、個人APIキー、provider API credentialなしで主要機能を確認できる。
- [ ] access codeは審査および必要な再審査の期間を通して有効で、短時間session tokenだけが定期更新される。
- [ ] proxyに費用上限、rate limit、停止手段、最小限の監査ログを設定している。
- [ ] Evaluation Accessのデータ経路、本文・metadataの保存期間、削除方法をアプリ内説明と公開ポリシーへ反映している。
- [ ] Review Notes内の`［提出前入力］`をすべて置き換えている。
- [ ] placeholder置換後のReview NotesがUTF-8で4,000 bytes以内である。
- [ ] Review contactの電話・メールが審査期間中に応答可能である。
- [ ] 審査・再審査期間中、Evaluation Accessと必要なprovider接続が稼働している。
- [ ] access code、session token、provider credentialをリポジトリ、バイナリ、公開ページ、スクリーンショットへ含めていない。
- [ ] Apple側で再審査が不要になったことを確認した後にaccess codeを無効化する担当者と手順を決めている。

### 15.7 Model lifecycle

- [ ] `whisper-1`、`gpt-4o`、`whisper-large-v3-turbo`、`openai/gpt-oss-120b`の提供状況を再確認している。
- [ ] Anthropicの選択肢`claude-haiku-4-5-20251001`、`claude-sonnet-5`、`claude-opus-5`、`claude-opus-4-8`、`claude-fable-5`を再確認している。
- [ ] Haiku 4.5は2026年10月15日より前にはretireしないという現行予定を監視し、移行テスト日を設定している。
- [ ] Fable 5の30日保持をアプリ内表示、公開ポリシー、App Privacyへ反映している。
- [ ] model変更時は日本語・繁體中文・英語・混在文・翻訳のregression testを実施している。

## 16. 既知の提出リスク

| 優先度 | リスク | 対応 |
|---|---|---|
| Blocker | Apple Developer Program法人登録状況をリポジトリから確認できない | Account HolderがMembershipと契約画面を確認 |
| Blocker | 現行端末に完全版Xcodeがなく、Xcode 26 / iOS 26 SDK Archive未検証 | 正式版Xcodeを導入してArchive・Validate |
| Blocker | Shingihou Evaluation AccessのUI / proxy / access code / session tokenが現行iOSコードに未実装 | first-party review経路を実装し、provider API credentialなしで全主要機能を検証 |
| Blocker | 現行Privacy Policyは通常BYOKの直結経路を中心に記載し、Evaluation Accessの新義豊proxy経路を未反映 | proxyの本文・metadata保持仕様を確定し、アプリ内同意、Privacy Policy、App Privacy、Review Notesを同時更新 |
| Blocker | App Store用iPhone / iPadスクリーンショットが未作成 | 実Buildから撮影し、機密情報を除去 |
| High | BYOKのAPIキーがモバイルクライアントから各providerへ直接送られる | 中期的にscoped tokenまたは最小権限backendを検討。少なくともKeychain・費用上限・失効手順を維持 |
| High | App PrivacyのUser ID / IP metadata回答はproviderの提出時点設定に依存 | 契約・Data Controls・ログ保持設定を提出直前に再確認 |
| High | iPad targetを維持するとiPad表示品質と13インチ用素材が必須 | iPadで全フローを検証。対応しない場合は別変更としてtarget方針を決定 |
| High | 日本語・英語・繁體中文の主要UI localizationは追加済みだが、完全版Xcodeでのbundle inclusion・実画面・VoiceOverが未検証 | 日本語端末で全フロー、Dynamic Type、截字、VoiceOverを実機確認 |
| Medium | Webサイトの主訴求がAndroid / macOS中心 | iOS公開時はMarketing / SupportページにiOS操作と問い合わせ導線を追加 |
| Medium | Anthropic modelと保持条件が変動する | リリース前および定期的に公式lifecycleを確認 |

## 17. 公式参照先

### Apple

- Program enrollment：<https://developer.apple.com/help/account/membership/program-enrollment>
- D-U-N-S：<https://developer.apple.com/help/account/membership/D-U-N-S/>
- Upcoming Requirements：<https://developer.apple.com/news/upcoming-requirements/>
- App Review Guidelines：<https://developer.apple.com/app-store/review/guidelines/>
- App information：<https://developer.apple.com/help/app-store-connect/reference/app-information/app-information/>
- Platform version information：<https://developer.apple.com/help/app-store-connect/reference/app-information/platform-version-information>
- App Privacy Details：<https://developer.apple.com/app-store/app-privacy-details/>
- Manage App Privacy：<https://developer.apple.com/help/app-store-connect/manage-app-information/manage-app-privacy>
- Privacy manifests：<https://developer.apple.com/documentation/bundleresources/privacy-manifest-files>
- Required reason APIs：<https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api>
- Screenshot specifications：<https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/>
- TestFlight overview：<https://developer.apple.com/help/app-store-connect/test-a-beta-version/testflight-overview>
- Invite external testers：<https://developer.apple.com/help/app-store-connect/test-a-beta-version/invite-external-testers>
- Age ratings：<https://developer.apple.com/help/app-store-connect/manage-app-information/set-an-app-age-rating>
- Age rating definitions：<https://developer.apple.com/help/app-store-connect/reference/app-information/age-ratings-values-and-definitions>
- Export compliance：<https://developer.apple.com/documentation/security/complying-with-encryption-export-regulations>

### OpenAI

- Whisper model：<https://developers.openai.com/api/docs/models/whisper-1>
- GPT-4o model：<https://developers.openai.com/api/docs/models/gpt-4o>
- API deprecations：<https://developers.openai.com/api/docs/deprecations>
- API data controls：<https://platform.openai.com/docs/models/default-usage-policies-by-endpoint>
- API key safety：<https://help.openai.com/en/articles/5112595-best-practices-for-api-key>

### Anthropic

- Models overview：<https://platform.claude.com/docs/en/about-claude/models/overview>
- Model deprecations：<https://platform.claude.com/docs/en/about-claude/model-deprecations>
- Model IDs and versioning：<https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions>
- API and data retention：<https://platform.claude.com/docs/en/manage-claude/api-and-data-retention>

### Groq

- Supported models：<https://console.groq.com/docs/models>
- Model deprecations：<https://console.groq.com/docs/deprecations>
- Speech to Text：<https://console.groq.com/docs/speech-to-text>
- Your Data：<https://console.groq.com/docs/your-data>
