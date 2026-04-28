// ===== SGH Voice i18n — full coverage (ja / zh-Hant / en) =====
// Each locale is fully self-contained — no language mixing.

const translations = {
    /* ============================================================
       日本語 (Default)
       ============================================================ */
    ja: {
        // Document <head>
        "meta.title": "SGH Voice — 話すだけで、プロ品質のテキストに。 v2.1.0",
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
        "hero.badge": "思考を言葉に · v2.1.0",
        "hero.title1": "話すだけで、",
        "hero.title2": "プロの文章に。",
        "hero.subtitle": "SGH Voice は、あなたの意図を汲み取る専属速記者のような存在です。単なる文字起こしではなく、無駄な言葉を削ぎ落とし、誤字を直し、完璧に整えます。中・日・英対応、データは 100% あなたの手元に。",
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
        "features.f7.title": "🏥 医療・製薬・バイオ 特化モード",
        "features.f7.desc": "医療従事者・MR・CRA・研究者向けの専用モード。処方薬名（アムロジピン、オプジーボ等）、診療科目、検査名（心電図、MRI、内視鏡）、バイオ用語（iPS 細胞、CAR-T、PD-1）を高精度で認識。カルテ記入、症例報告、論文ドラフトの音声入力を劇的に効率化します。",
        "features.f2.title": "意図を汲み取る AI 校正",
        "features.f2.desc": "「えーと」「あの」などの口癖を自動で取り除き、バラバラな話し言葉をそのまま使える洗練された書き言葉へと昇華させます。",
        "features.f3.title": "Breeze-ASR-25 搭載",
        "features.f3.desc": "MediaTek 製の繁体字中国語特化 ASR モデルを Apple Silicon 上でオフライン実行。Whisper-turbo 比 3.5 倍高速。0.8GB の 4bit 量子化モデルで、インターネット接続不要です。",
        "features.f4.title": "ハイブリッドモード",
        "features.f4.desc": "短い文はローカル AI、長文はクラウド AI へ自動振り分け。コスト最適化と応答速度を両立します。",
        "features.f5.title": "カスタム辞書",
        "features.f5.desc": "専門用語・固有名詞を登録して認識精度を大幅に向上。使えば使うほど賢くなります。",
        "features.f6.title": "Android IME 対応",
        "features.f6.desc": "Android のキーボードとして動作。どのアプリでも音声入力が可能です。",
        "features.f8.title": "🔐 声紋認証 (v1.3.0)",
        "features.f8.desc": "本人の声だけを識別し、周囲の雑音や他人の話し声を自動でフィルタリングします。",
        "features.f9.title": "止まらない、マルチクラウド (v1.5.1)",
        "features.f9.desc": "Groq と OpenRouter を統合。一つのサービスが混雑していても、最適なモデルへ自動で切り替え、あなたのインスピレーションを逃しません。",

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
        "pricing.pro.period": "API 料金込み・使い放題",
        "pricing.pro.unit": "/月",
        "pricing.pro.f1": "Free プランの全機能",
        "pricing.pro.f2": "API キー不要(サーバー提供)",
        "pricing.pro.f3": "優先サポート",
        "pricing.pro.f4": "新機能の先行体験",
        "pricing.pro.f5": "商用利用可",
        "pricing.pro.cta": "サブスクライブ",

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
        "download.macDesc": "Apple Silicon & Intel 対応",
        "download.macCta": "Apple Silicon (v2.1.0)",
        "download.macIntel": "Intel Mac",
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
        "meta.title": "SGH Voice — 隨口一說，即是專業文章。v2.1.0",
        "meta.description": "SGH Voice 是懂你的 AI 語音輸入助理。中、日、英自動辨識，將口語整理為流暢的書面文字。資料 100% 由你掌握。",

        "nav.features": "主要功能",
        "nav.howItWorks": "使用方式",
        "nav.pricing": "方案",
        "nav.download": "立即下載",
        "nav.beta": "Beta 申請",
        "nav.privacy": "隱私權",
        "nav.cta": "免費開始",

        "hero.badge": "讓想法流動 · v2.1.0",
        "hero.title1": "隨口一說，",
        "hero.title2": "即是專業文章。",
        "hero.subtitle": "SGH Voice 就像一位懂你的速記員。它不只是轉錄，更會自動過濾廢話、修正錯字、精確排版。支援中日英混合，資料 100% 掌握在你自己手中。",
        "hero.cta": "免費下載",
        "hero.ctaSecondary": "了解運作方式",
        "hero.stat1": "支援語言",
        "hero.stat2": "極速回應",
        "hero.stat3": "辨識精度",

        "features.label": "主要功能",
        "features.title": "一切交給 AI，<br>全新的語音輸入體驗",
        "features.f1.title": "三語混合辨識",
        "features.f1.desc": "中文(繁體)、日文、英文無縫混合說話，AI 也能自動精準轉寫。完全不需切換語言。",
        "features.f7.title": "🏥 醫療、製藥、生技 專屬模式",
        "features.f7.desc": "為醫療人員、MR、CRA、研究者打造的專用模式。處方藥名(脈優、保疾伏等)、診療科別、檢查名稱(心電圖、MRI、內視鏡)、生技術語(iPS 細胞、CAR-T、PD-1)高精度辨識。讓病歷書寫、病例報告、論文初稿的語音輸入效率倍增。",
        "features.f2.title": "懂你的 AI 校正",
        "features.f2.desc": "不只是轉文字，更能讀懂語境。自動移除「嗯」「啊」等口頭禪，將瑣碎的口語整理成得體的書面表達。",
        "features.f3.title": "搭載 Breeze-ASR-25",
        "features.f3.desc": "聯發科繁中專屬 ASR 模型，於 Apple Silicon 離線執行。比 Whisper-turbo 快 3.5 倍。4bit 量化僅 0.8GB，無需網路連線。",
        "features.f4.title": "混合運算模式",
        "features.f4.desc": "短句走本地 AI、長句自動轉雲端 AI。同時兼顧成本與回應速度。",
        "features.f5.title": "自訂辭典",
        "features.f5.desc": "登錄專業術語與專有名詞，大幅提升辨識精度。越用越聰明。",
        "features.f6.title": "Android IME 支援",
        "features.f6.desc": "化身 Android 鍵盤，任何 App 都能語音輸入。",
        "features.f8.title": "🔐 聲紋辨識 (v1.3.0)",
        "features.f8.desc": "只辨識本人聲音,自動過濾環境雜音與他人說話。",
        "features.f9.title": "多雲路由,穩定不斷線 (v1.5.1)",
        "features.f9.desc": "整合 Groq 極速推論與 OpenRouter 模型庫。即便某個服務忙碌,也能自動切換備援,確保你的靈感隨時被捕捉。",

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
        "pricing.pro.period": "含 API 用量,吃到飽",
        "pricing.pro.unit": "/月",
        "pricing.pro.f1": "Free 方案全部功能",
        "pricing.pro.f2": "免 API 金鑰(伺服器代管)",
        "pricing.pro.f3": "優先客服",
        "pricing.pro.f4": "新功能搶先體驗",
        "pricing.pro.f5": "可商業使用",
        "pricing.pro.cta": "訂閱",

        "subscribe.title": "訂閱最新消息",
        "subscribe.desc": "新功能上線、版本更新第一手通知。請留下你的 Email。",
        "subscribe.placeholder": "mail@example.com",
        "subscribe.cta": "立即訂閱",
        "subscribe.note": "我們不寄垃圾信,隨時可取消。",
        "subscribe.success": "訂閱成功,感謝!",
        "subscribe.error": "發生錯誤,請稍後再試。",

        "download.label": "立即下載",
        "download.title": "現在就開始",
        "download.macDesc": "支援 Apple Silicon 與 Intel",
        "download.macCta": "Apple Silicon (v2.1.0)",
        "download.macIntel": "Intel Mac",
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
        "meta.title": "SGH Voice — Just speak. Get professional text. v2.1.0",
        "meta.description": "SGH Voice is an AI voice-input assistant that understands you. Auto-detects Chinese, Japanese, and English, and turns spontaneous speech into polished prose. 100% private — your data stays with you.",

        "nav.features": "Features",
        "nav.howItWorks": "How It Works",
        "nav.pricing": "Pricing",
        "nav.download": "Download",
        "nav.beta": "Beta Access",
        "nav.privacy": "Privacy",
        "nav.cta": "Get Started Free",

        "hero.badge": "Flow your ideas · v2.1.0",
        "hero.title1": "Just speak —",
        "hero.title2": "get professional text.",
        "hero.subtitle": "SGH Voice is like an intuitive stenographer. Beyond mere transcription, it filters fillers, corrects typos, and formats perfectly. Trilingual (CN / JA / EN), private by design — 100% local data.",
        "hero.cta": "Free Download",
        "hero.ctaSecondary": "See How It Works",
        "hero.stat1": "Languages",
        "hero.stat2": "Fast Response",
        "hero.stat3": "Accuracy",

        "features.label": "Key Features",
        "features.title": "Let AI handle it all —<br>a new way to input by voice",
        "features.f1.title": "Trilingual Mixed Recognition",
        "features.f1.desc": "Mix Traditional Chinese, Japanese, and English freely — the AI auto-detects and transcribes accurately. No language switching needed.",
        "features.f7.title": "🏥 Medical, Pharma & Biotech Mode",
        "features.f7.desc": "A dedicated mode for clinicians, MRs, CRAs, and researchers. High-accuracy recognition of prescription drugs (amlodipine, Opdivo, etc.), specialties, exam names (ECG, MRI, endoscopy), and biotech terms (iPS cells, CAR-T, PD-1). Dramatically speeds up charting, case reports, and paper drafts.",
        "features.f2.title": "Context-Aware AI Polishing",
        "features.f2.desc": "Removes \"um\", \"uh\", and other fillers automatically — turns fragmented speech into ready-to-use professional writing.",
        "features.f3.title": "Breeze-ASR-25 Onboard",
        "features.f3.desc": "MediaTek's Traditional-Chinese-tuned ASR model, running offline on Apple Silicon. 3.5× faster than Whisper-turbo. Just 0.8GB (4-bit quantized) — no internet required.",
        "features.f4.title": "Hybrid Mode",
        "features.f4.desc": "Short utterances run on local AI, long ones route to cloud AI — balancing cost and response speed.",
        "features.f5.title": "Custom Dictionary",
        "features.f5.desc": "Add jargon and proper nouns to boost accuracy. The more you use it, the smarter it gets.",
        "features.f6.title": "Android IME",
        "features.f6.desc": "Acts as an Android keyboard — voice input in any app.",
        "features.f8.title": "🔐 Voiceprint Verification (v1.3.0)",
        "features.f8.desc": "Recognizes only your voice — automatically filters out background noise and other speakers.",
        "features.f9.title": "Multi-Cloud Reliability (v1.5.1)",
        "features.f9.desc": "Hybrid routing across Groq and OpenRouter. Even if one provider is busy, we switch over automatically — never miss an idea.",

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
        "pricing.pro.period": "API included · unlimited",
        "pricing.pro.unit": "/mo",
        "pricing.pro.f1": "All Free features",
        "pricing.pro.f2": "No API keys needed (we host)",
        "pricing.pro.f3": "Priority support",
        "pricing.pro.f4": "Early access to new features",
        "pricing.pro.f5": "Commercial use allowed",
        "pricing.pro.cta": "Subscribe",

        "subscribe.title": "Stay in the loop",
        "subscribe.desc": "Be the first to hear about new features and updates. Drop your email below.",
        "subscribe.placeholder": "mail@example.com",
        "subscribe.cta": "Subscribe",
        "subscribe.note": "No spam. Unsubscribe anytime.",
        "subscribe.success": "Thanks for subscribing!",
        "subscribe.error": "Something went wrong. Please try again.",

        "download.label": "Download",
        "download.title": "Get started now",
        "download.macDesc": "Apple Silicon & Intel",
        "download.macCta": "Apple Silicon (v2.1.0)",
        "download.macIntel": "Intel Mac",
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
