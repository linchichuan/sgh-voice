// ===== SGH Voice i18n — full coverage (ja / zh-Hant / en) =====
// Each locale is fully self-contained — no language mixing.

const translations = {
    /* ============================================================
       日本語 (Default)
       ============================================================ */
    ja: {
        // Document <head>
        "meta.title": "SGH Voice — 話すだけで、プロ品質のテキストに。 v2.5.4",
        "meta.description": "SGH Voice は、あなたの意図を汲み取る AI 音声入力アシスタント。中国語・日本語・英語を自動認識し、口語を洗練された書き言葉へ整えます。データは 100% あなたの手元に。",

        // Nav
        "nav.features": "機能",
        "nav.howItWorks": "使い方",
        "nav.pricing": "料金",
        "nav.download": "ダウンロード",
        "nav.beta": "Beta 申込",
        "nav.privacy": "プライバシー",
        "nav.cta": "無料で始める",

        // Hero
        "hero.badge": "Fn／地球儀ホットキー対応 · v2.5.4",
        "hero.title1": "話すだけで、",
        "hero.title2": "プロの文章に。",
        "hero.subtitle": "あなたの意図を汲み取る、AI 専属速記者。<br>中・日・英対応 · データは 100% あなたの手元に。",
        "hero.chip1": "✦ Prompt 精度を改善",
        "hero.chip2": "✦ Quick-Rewrite 強化",
        "hero.chip3": "✦ 長文処理を安定化",
        "hero.cta": "無料ダウンロード",
        "hero.ctaSecondary": "使い方を見る",
        "hero.stat1": "対応言語",
        "hero.stat2": "高速応答",
        "hero.stat3": "認識精度",

        // Features
        "features.label": "主要機能",
        "features.title": "すべてを AI に任せる、<br>新しい音声入力体験",
        "features.f1.title": "3 言語混合認識",
        "features.f1.desc": "中国語（繁体字）・日本語・英語をシームレスに混ぜて話しても、AI が自動で正確に文字起こしします。言語切替は不要です。",
        "features.f7.title": "🏥 SOAP・医療文書モード",
        "features.f7.desc": "医療・製薬・バイオ分野の用語を保持しながら、看診メモや相談内容を SOAP 形式などの構造化文書へ整理できます。医療内容の判断は行わず、入力補助として利用します。",
        "features.f2.title": "v2.5 Prompt Engine",
        "features.f2.desc": "逐字入力・翻訳・Email・技術文書などの指示を構造化し、選択テキスト内の指示文に引きずられにくい安全な後処理に改善しました。",
        "features.f3.title": "Breeze-ASR-25 搭載",
        "features.f3.desc": "MediaTek 製の繁体字中国語特化 ASR モデルを Apple Silicon 上でオフライン実行。Whisper-turbo 比 3.5 倍高速。0.8GB の 4bit 量子化モデルで、インターネット接続不要です。",
        "features.f4.title": "高速フェイルオーバー",
        "features.f4.desc": "STT / LLM のタイムアウトとリトライを見直し、混雑時も次の候補へ素早く切り替えます。長い録音でも処理待ちを抑えます。",
        "features.f5.title": "辞書・置換ルールの安全化",
        "features.f5.desc": "カスタム辞書、スマート置換、固有名詞補正の保存処理を堅牢化。誤置換や破損に強い運用を目指しました。",
        "features.f6.title": "Android IME 対応",
        "features.f6.desc": "Android のキーボードとして動作。どのアプリでも音声入力が可能です。",
        "features.f8.title": "🔐 声紋認証 (v1.3.0)",
        "features.f8.desc": "本人の声だけを識別し、周囲の雑音や他人の話し声を自動でフィルタリングします。",
        "features.f9.title": "連続録音の安定性向上",
        "features.f9.desc": "pre-roll、最終セグメント flush、マイク切断時の復旧を改善。会話中の語頭欠けや最後の一文の取りこぼしを減らします。",
        "features.f10.title": "🔐 データは 100% あなたの手元に",
        "features.f10.desc": "音声・APIキー・辞書はすべて端末内で暗号化保存。当社のサーバーに音声データは一切送られません。利用する AI プロバイダーはユーザーが選択・管理します。",

        // How it works
        "howItWorks.label": "使い方",
        "howItWorks.title": "3 ステップで音声入力",
        "howItWorks.s1.title": "話す",
        "howItWorks.s1.desc": "ホットキーを押しながら、マイクに向かって自由に話しかけます。中国語・日本語・英語を混ぜても OK。",
        "howItWorks.s2.title": "AI が処理",
        "howItWorks.s2.desc": "Whisper が音声を認識し、Claude AI が自動で校正・フォーマット。口語表現を書き言葉に変換します。",
        "howItWorks.s3.title": "自動入力",
        "howItWorks.s3.desc": "処理結果がカーソル位置に自動ペースト。メール、チャット、ドキュメント — どこでもすぐに使えます。",

        // Pricing
        "pricing.label": "料金プラン",
        "pricing.title": "シンプルな料金体系",
        "pricing.subtitle": "アプリ本体は無料。AI 処理は各サービスの API 利用料のみ。",
        "pricing.free.name": "Free プラン",
        "pricing.free.period": "永久無料",
        "pricing.free.f1": "アプリ本体の全機能",
        "pricing.free.f2": "Web ダッシュボード",
        "pricing.free.f3": "カスタム辞書",
        "pricing.free.f4": "自動繁体字変換",
        "pricing.free.f5": "API キー自己管理",
        "pricing.free.cta": "ダウンロード",
        "pricing.pro.badge": "おすすめ",
        "pricing.pro.name": "Pro プラン",
        "pricing.pro.period": "準備中 · リリース時に詳細をご案内",
        "pricing.pro.unit": "/月",
        "pricing.pro.f1": "Free プランの全機能",
        "pricing.pro.f2": "API キー不要(サーバー提供 · 通常利用範囲内)",
        "pricing.pro.f3": "優先サポート",
        "pricing.pro.f4": "新機能の先行体験",
        "pricing.pro.f5": "商用利用可",
        "pricing.pro.cta": "リリース通知を受け取る",

        // Subscribe
        "subscribe.title": "最新情報をお届けします",
        "subscribe.desc": "新機能のリリース情報やアップデートをいち早くお届けします。メールアドレスをご登録ください。",
        "subscribe.placeholder": "mail@example.com",
        "subscribe.cta": "登録する",
        "subscribe.note": "スパムは送りません。いつでも解除可能です。",
        "subscribe.success": "登録ありがとうございます！",
        "subscribe.error": "エラーが発生しました。もう一度お試しください。",

        // Download
        "download.label": "ダウンロード",
        "download.title": "今すぐ始めましょう",
        "download.macDesc": "v2.5.4 インストーラ公開中 · Apple Silicon 版（Intel は別途配布予定）",
        "download.macCta": "Apple Silicon",
        "download.macIntel": "Intel",
        "download.macIntelCta": "Intel 版（要件確認）",
        "download.iosDesc": "iPhone / iPad (iOS 16+)",
        "download.iosCta": "リリースページ",
        "download.androidDesc": "Android 8.0+ (Google Play 審査中)",
        "download.androidCta": "リリースページ",

        // Beta / NPP
        "beta.label": "Android テスト募集",
        "beta.title": "Android 先行テストプログラム (NPP)",
        "beta.subtitle": "Android 版のリリースに向けて 20 名以上のテスターを募集中。いち早く未来の入力体験を。",
        "beta.form.name": "お名前 / ニックネーム",
        "beta.form.email": "Gmail (Google Play で必須)",
        "beta.form.device": "Android 端末モデル",
        "beta.form.devicePlaceholder": "例: Pixel 8、Galaxy S24…",
        "beta.form.submit": "Android 先行テストに申し込む",
        "beta.form.submitting": "送信中…",
        "beta.form.success": "ご応募ありがとうございます！テストアカウントに追加し、次のステップをご案内します。",
        "beta.form.error": "送信に失敗しました。もう一度お試しください。",
        "beta.form.retry": "再送信",

        // Footer
        "footer.desc": "新義豊株式会社が開発する AI 音声入力アシスタント",
        "footer.product": "製品",
        "footer.legal": "法的事項",
        "footer.terms": "利用規約",
        "footer.company": "会社情報",
        "footer.privacyFull": "プライバシーポリシー"
    },

    /* ============================================================
       繁體中文(台灣)
       ============================================================ */
    zh: {
        "meta.title": "SGH Voice — 隨口一說，即是專業文章。v2.5.4",
        "meta.description": "SGH Voice 是懂你的 AI 語音輸入助理。中、日、英自動辨識，將口語整理為流暢的書面文字。資料 100% 由你掌握。",

        "nav.features": "主要功能",
        "nav.howItWorks": "使用方式",
        "nav.pricing": "方案",
        "nav.download": "立即下載",
        "nav.beta": "Beta 申請",
        "nav.privacy": "隱私權",
        "nav.cta": "免費開始",

        "hero.badge": "Fn／地球鍵快捷鍵修正 · v2.5.4",
        "hero.title1": "隨口一說，",
        "hero.title2": "即是專業文章。",
        "hero.subtitle": "懂你意圖的 AI 專屬速記員。<br>中・日・英混合辨識 · 資料 100% 在你手中。",
        "hero.chip1": "✦ Prompt 精度改善",
        "hero.chip2": "✦ Quick-Rewrite 強化",
        "hero.chip3": "✦ 長文處理更穩定",
        "hero.cta": "免費下載",
        "hero.ctaSecondary": "了解運作方式",
        "hero.stat1": "支援語言",
        "hero.stat2": "極速回應",
        "hero.stat3": "辨識精度",

        "features.label": "主要功能",
        "features.title": "一切交給 AI，<br>全新的語音輸入體驗",
        "features.f1.title": "三語混合辨識",
        "features.f1.desc": "中文(繁體)、日文、英文無縫混合說話，AI 也能自動精準轉寫。完全不需切換語言。",
        "features.f7.title": "🏥 SOAP 與醫療文件模式",
        "features.f7.desc": "保留醫療、製藥、生技用語，將看診筆記或諮詢內容整理為 SOAP 等結構化文件。此功能用於輸入輔助，不取代醫療判斷。",
        "features.f2.title": "v2.5 Prompt Engine",
        "features.f2.desc": "將逐字輸入、翻譯、Email、技術文件等指令結構化，降低選取文字中的指令干擾，讓後處理更穩定。",
        "features.f3.title": "搭載 Breeze-ASR-25",
        "features.f3.desc": "聯發科繁中專屬 ASR 模型，於 Apple Silicon 離線執行。比 Whisper-turbo 快 3.5 倍。4bit 量化僅 0.8GB，無需網路連線。",
        "features.f4.title": "快速備援切換",
        "features.f4.desc": "重新調整 STT / LLM timeout 與 retry，服務忙碌時更快切到下一個候選，減少長錄音等待。",
        "features.f5.title": "辭典與替換規則安全化",
        "features.f5.desc": "強化自訂辭典、smart replace、專有名詞修正的保存與防呆，降低誤替換與資料破損風險。",
        "features.f6.title": "Android IME 支援",
        "features.f6.desc": "化身 Android 鍵盤，任何 App 都能語音輸入。",
        "features.f8.title": "🔐 聲紋辨識 (v1.3.0)",
        "features.f8.desc": "只辨識本人聲音,自動過濾環境雜音與他人說話。",
        "features.f9.title": "連續錄音穩定性提升",
        "features.f9.desc": "改善 pre-roll、最後片段 flush 與麥克風中斷復原，降低句首被裁掉或最後一句遺失的情況。",
        "features.f10.title": "🔐 資料 100% 在你手中",
        "features.f10.desc": "語音、API 金鑰、詞庫全部在裝置內加密儲存。本公司伺服器不會接收任何語音資料,使用哪家 AI 服務商完全由你決定。",

        "howItWorks.label": "使用方式",
        "howItWorks.title": "三步驟完成語音輸入",
        "howItWorks.s1.title": "開口說",
        "howItWorks.s1.desc": "按住快捷鍵,對著麥克風自由說話。中、日、英混說都 OK。",
        "howItWorks.s2.title": "AI 處理",
        "howItWorks.s2.desc": "Whisper 辨識語音,Claude AI 自動校正、排版,將口語轉為書面文字。",
        "howItWorks.s3.title": "自動輸入",
        "howItWorks.s3.desc": "處理結果自動貼到游標位置。郵件、聊天、文件 — 隨處可用。",

        "pricing.label": "方案",
        "pricing.title": "簡單透明的方案",
        "pricing.subtitle": "應用本體免費,AI 處理僅收取各服務的 API 費用。",
        "pricing.free.name": "Free 方案",
        "pricing.free.period": "永久免費",
        "pricing.free.f1": "應用本體全部功能",
        "pricing.free.f2": "Web Dashboard",
        "pricing.free.f3": "自訂辭典",
        "pricing.free.f4": "自動繁體中文化",
        "pricing.free.f5": "自備 API 金鑰",
        "pricing.free.cta": "下載",
        "pricing.pro.badge": "推薦",
        "pricing.pro.name": "Pro 方案",
        "pricing.pro.period": "規劃中 · 上線時將提供詳細資訊",
        "pricing.pro.unit": "/月",
        "pricing.pro.f1": "Free 方案全部功能",
        "pricing.pro.f2": "免 API 金鑰(伺服器代管 · 一般使用範圍內)",
        "pricing.pro.f3": "優先客服",
        "pricing.pro.f4": "新功能搶先體驗",
        "pricing.pro.f5": "可商業使用",
        "pricing.pro.cta": "搶先收到上線通知",

        "subscribe.title": "訂閱最新消息",
        "subscribe.desc": "新功能上線、版本更新第一手通知。請留下你的 Email。",
        "subscribe.placeholder": "mail@example.com",
        "subscribe.cta": "立即訂閱",
        "subscribe.note": "我們不寄垃圾信,隨時可取消。",
        "subscribe.success": "訂閱成功,感謝!",
        "subscribe.error": "發生錯誤,請稍後再試。",

        "download.label": "立即下載",
        "download.title": "現在就開始",
        "download.macDesc": "v2.5.4 安裝包已上線 · 先提供 Apple Silicon 版（Intel 版本將另行提供）",
        "download.macCta": "Apple Silicon",
        "download.macIntel": "Intel",
        "download.macIntelCta": "Intel 版（Release 頁）",
        "download.iosDesc": "iPhone / iPad (iOS 16+)",
        "download.iosCta": "前往發行頁",
        "download.androidDesc": "Android 8.0+ (Google Play 審核中)",
        "download.androidCta": "前往發行頁",

        "beta.label": "Android 測試招募",
        "beta.title": "Android 封測計畫 (NPP)",
        "beta.subtitle": "正在招募 20 位以上外部測試者。加入封測,搶先體驗 Android 智慧語音輸入!",
        "beta.form.name": "姓名 / 暱稱",
        "beta.form.email": "Gmail (Google Play 必要)",
        "beta.form.device": "Android 手機型號",
        "beta.form.devicePlaceholder": "例如:Pixel 8、Galaxy S24…",
        "beta.form.submit": "申請加入 Android 封測",
        "beta.form.submitting": "傳送中…",
        "beta.form.success": "感謝參與!我們會將您的帳號加入測試名單,並通知您下一步。",
        "beta.form.error": "傳送失敗,請稍後再試。",
        "beta.form.retry": "重新傳送",

        "footer.desc": "由新義豊株式會社開發的 AI 語音輸入助理",
        "footer.product": "產品",
        "footer.legal": "法律資訊",
        "footer.terms": "使用條款",
        "footer.company": "公司資訊",
        "footer.privacyFull": "隱私權政策"
    },

    /* ============================================================
       English
       ============================================================ */
    en: {
        "meta.title": "SGH Voice — Just speak. Get professional text. v2.5.4",
        "meta.description": "SGH Voice is an AI voice-input assistant that understands you. Auto-detects Chinese, Japanese, and English, and turns spontaneous speech into polished prose. 100% private — your data stays with you.",

        "nav.features": "Features",
        "nav.howItWorks": "How It Works",
        "nav.pricing": "Pricing",
        "nav.download": "Download",
        "nav.beta": "Beta Access",
        "nav.privacy": "Privacy",
        "nav.cta": "Get Started Free",

        "hero.badge": "Fn/Globe hotkey support · v2.5.4",
        "hero.title1": "Just speak —",
        "hero.title2": "get professional text.",
        "hero.subtitle": "Your personal AI stenographer.<br>Trilingual (CN · JA · EN) · Your data, 100% under your control.",
        "hero.chip1": "✦ Prompt accuracy improved",
        "hero.chip2": "✦ Quick-Rewrite upgraded",
        "hero.chip3": "✦ Long-form flow stabilized",
        "hero.cta": "Free Download",
        "hero.ctaSecondary": "See How It Works",
        "hero.stat1": "Languages",
        "hero.stat2": "Fast Response",
        "hero.stat3": "Accuracy",

        "features.label": "Key Features",
        "features.title": "Let AI handle it all —<br>a new way to input by voice",
        "features.f1.title": "Trilingual Mixed Recognition",
        "features.f1.desc": "Mix Traditional Chinese, Japanese, and English freely — the AI auto-detects and transcribes accurately. No language switching needed.",
        "features.f7.title": "🏥 SOAP and Medical Notes Mode",
        "features.f7.desc": "Keeps medical, pharma, and biotech terminology while organizing consultation notes into structured formats such as SOAP. It is an input aid and does not replace clinical judgment.",
        "features.f2.title": "v2.5 Prompt Engine",
        "features.f2.desc": "Dictation, translation, email, and technical rewrite commands are now structured, reducing accidental instruction-following from selected text.",
        "features.f3.title": "Breeze-ASR-25 Onboard",
        "features.f3.desc": "MediaTek's Traditional-Chinese-tuned ASR model, running offline on Apple Silicon. 3.5× faster than Whisper-turbo. Just 0.8GB (4-bit quantized) — no internet required.",
        "features.f4.title": "Faster failover",
        "features.f4.desc": "STT and LLM timeouts and retries were tightened so busy providers hand off faster, especially for long recordings.",
        "features.f5.title": "Safer dictionary rules",
        "features.f5.desc": "Custom dictionary and smart-replace storage are more defensive, reducing bad replacements and file-corruption risk.",
        "features.f6.title": "Android IME",
        "features.f6.desc": "Acts as an Android keyboard — voice input in any app.",
        "features.f8.title": "🔐 Voiceprint Verification (v1.3.0)",
        "features.f8.desc": "Recognizes only your voice — automatically filters out background noise and other speakers.",
        "features.f9.title": "Continuous recording stability",
        "features.f9.desc": "Pre-roll, final-segment flushing, and microphone recovery were improved to reduce clipped starts and missing final sentences.",
        "features.f10.title": "🔐 Your data stays with you",
        "features.f10.desc": "Audio, API keys, and dictionaries are all encrypted and stored on-device. Audio is never sent to our servers — you choose and manage your AI providers.",

        "howItWorks.label": "How It Works",
        "howItWorks.title": "Voice input in 3 steps",
        "howItWorks.s1.title": "Speak",
        "howItWorks.s1.desc": "Hold the hotkey and speak freely into the mic. Mix Chinese, Japanese, and English as you like.",
        "howItWorks.s2.title": "AI Processes",
        "howItWorks.s2.desc": "Whisper transcribes, Claude AI polishes and formats — turning casual speech into clean writing.",
        "howItWorks.s3.title": "Auto-Insert",
        "howItWorks.s3.desc": "The result auto-pastes at your cursor. Email, chat, docs — works everywhere.",

        "pricing.label": "Pricing",
        "pricing.title": "Simple, transparent pricing",
        "pricing.subtitle": "The app itself is free. AI processing only costs the API fees from each provider.",
        "pricing.free.name": "Free",
        "pricing.free.period": "Free forever",
        "pricing.free.f1": "All app features",
        "pricing.free.f2": "Web Dashboard",
        "pricing.free.f3": "Custom dictionary",
        "pricing.free.f4": "Auto Traditional Chinese",
        "pricing.free.f5": "Bring your own API keys",
        "pricing.free.cta": "Download",
        "pricing.pro.badge": "Recommended",
        "pricing.pro.name": "Pro",
        "pricing.pro.period": "Coming soon · Details on launch",
        "pricing.pro.unit": "/mo",
        "pricing.pro.f1": "All Free features",
        "pricing.pro.f2": "No API keys needed (we host · fair-use)",
        "pricing.pro.f3": "Priority support",
        "pricing.pro.f4": "Early access to new features",
        "pricing.pro.f5": "Commercial use allowed",
        "pricing.pro.cta": "Notify me on launch",

        "subscribe.title": "Stay in the loop",
        "subscribe.desc": "Be the first to hear about new features and updates. Drop your email below.",
        "subscribe.placeholder": "mail@example.com",
        "subscribe.cta": "Subscribe",
        "subscribe.note": "No spam. Unsubscribe anytime.",
        "subscribe.success": "Thanks for subscribing!",
        "subscribe.error": "Something went wrong. Please try again.",

        "download.label": "Download",
        "download.title": "Get started now",
        "download.macDesc": "v2.5.4 installer available on Releases · Apple Silicon build first",
        "download.macCta": "Apple Silicon",
        "download.macIntel": "Intel",
        "download.macIntelCta": "Intel (Release page)",
        "download.iosDesc": "iPhone / iPad (iOS 16+)",
        "download.iosCta": "Release page",
        "download.androidDesc": "Android 8.0+ (Google Play in review)",
        "download.androidCta": "Release page",

        "beta.label": "Android Tester Wanted",
        "beta.title": "Android Closed Beta (NPP)",
        "beta.subtitle": "We're recruiting 20+ external testers. Join the closed beta and try Android voice input first.",
        "beta.form.name": "Name / Nickname",
        "beta.form.email": "Gmail (required for Google Play)",
        "beta.form.device": "Your Android device model",
        "beta.form.devicePlaceholder": "e.g. Pixel 8, Galaxy S24…",
        "beta.form.submit": "Apply for Android Beta",
        "beta.form.submitting": "Sending…",
        "beta.form.success": "Thanks for joining! We'll add your account to the tester list and follow up with next steps.",
        "beta.form.error": "Failed to send. Please try again.",
        "beta.form.retry": "Retry",

        "footer.desc": "AI voice-input assistant by Shingihou Co., Ltd.",
        "footer.product": "Product",
        "footer.legal": "Legal",
        "footer.terms": "Terms of Service",
        "footer.company": "Company",
        "footer.privacyFull": "Privacy Policy"
    }
};

// HTML lang attribute mapping (for accessibility / SEO)
const HTML_LANG = { ja: "ja", zh: "zh-Hant", en: "en" };

// Display name shown in the language switcher button
const LANG_DISPLAY = { ja: "日本語", zh: "繁體中文", en: "English" };

function setLanguage(lang) {
    if (!translations[lang]) lang = "ja";
    localStorage.setItem("sgh_lang", lang);
    applyLanguage(lang);
}

function applyLanguage(lang) {
    if (!translations[lang]) lang = "ja";
    const data = translations[lang];

    // Text content
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (data[key]) el.innerHTML = data[key];
    });

    // Placeholder attribute
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
        const key = el.getAttribute("data-i18n-placeholder");
        if (data[key]) el.setAttribute("placeholder", data[key]);
    });

    // <html lang>
    document.documentElement.lang = HTML_LANG[lang] || "ja";

    // <title> + meta description + og:*
    if (data["meta.title"]) document.title = data["meta.title"];
    setMeta("name", "description", data["meta.description"]);
    setMeta("property", "og:title", data["meta.title"]);
    setMeta("property", "og:description", data["meta.description"]);
    setMeta("property", "og:locale", { ja: "ja_JP", zh: "zh_TW", en: "en_US" }[lang]);

    // Switcher label + active dropdown state
    const cur = document.getElementById("currentLang");
    if (cur) cur.innerText = LANG_DISPLAY[lang] || "日本語";
    document.querySelectorAll(".lang-option").forEach(opt => {
        opt.classList.toggle("active", opt.getAttribute("data-lang") === lang);
    });

    // Expose globally so inline scripts (e.g., NPP form) can read translations
    window.SGH_I18N = data;
    window.SGH_LANG = lang;
}

function setMeta(attr, name, value) {
    if (!value) return;
    let el = document.querySelector(`meta[${attr}="${name}"]`);
    if (!el) {
        el = document.createElement("meta");
        el.setAttribute(attr, name);
        document.head.appendChild(el);
    }
    el.setAttribute("content", value);
}

function detectInitialLang() {
    const saved = localStorage.getItem("sgh_lang");
    if (saved && translations[saved]) return saved;
    const nav = (navigator.language || "en").toLowerCase();
    if (nav.startsWith("ja")) return "ja";
    if (nav.startsWith("zh")) return "zh";
    return "en";
}

document.addEventListener("DOMContentLoaded", () => {
    applyLanguage(detectInitialLang());
});
