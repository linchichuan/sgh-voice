// ===== SGH Voice i18n — 人性化文案優化版 =====
const translations = {
    ja: {
        "nav.features": "機能",
        "nav.howItWorks": "使い方",
        "nav.pricing": "料金",
        "nav.download": "ダウンロード",
        "nav.privacy": "プライバシー",
        "nav.cta": "無料で始める",
        "hero.badge": "思考を言葉に · v1.9.8",
        "hero.title1": "話すだけで、",
        "hero.title2": "プロの文章に。",
        "hero.subtitle": "SGH Voiceは、あなたの意図を汲み取る専属速記者のようです。単なる文字起こしではなく、無駄な言葉を削ぎ落とし、誤字を直し、完璧に整えます。中・日・英対応。データは100%あなたの手元に。",
        "hero.cta": "無料ダウンロード",
        "hero.ctaSecondary": "使い方を見る",
        "features.f2.title": "意図を汲み取るAI校正",
        "features.f2.desc": "「えーと」「あの」などの口癖を自動で取り除き、バラバラな話し言葉を、そのまま使える洗練された書き言葉へと昇華させます。",
        "features.f9.title": "止まらない、マルチクラウド",
        "features.f9.desc": "GroqとOpenRouterを統合。一つのサービスが混雑していても、最適なモデルへ自動で切り替え、あなたのインスピレーションを逃しません。",
        "download.macDesc": "Apple Silicon (M1/M2/M3/M4) 専用",
        "beta.label": "Android テスト募集",
        "beta.title": "Android版 先行テスト (NPP)",
        "beta.subtitle": "Android版のリリースに向けて、テストユーザーを募集しています。いち早く未来の入力を体験してください。"
    },
    zh: {
        "nav.features": "主要功能",
        "nav.howItWorks": "使用方式",
        "nav.pricing": "方案",
        "nav.download": "立即下載",
        "nav.privacy": "隱私權",
        "nav.cta": "免費開始",
        "hero.badge": "讓想法流動 · v1.9.8",
        "hero.title1": "隨口一說，",
        "hero.title2": "即是專業文章。",
        "hero.subtitle": "SGH Voice 就像一個懂你的速記員。它不只是轉錄，更會自動過濾廢話、修正錯字、精確排版。支援中日英混合，資料 100% 掌握在你自己手中。",
        "hero.cta": "免費下載",
        "hero.ctaSecondary": "了解運作方式",
        "features.f2.title": "懂你的 AI 校正",
        "features.f2.desc": "不只是轉文字，更能讀懂語境。自動移除「嗯、啊」等口頭禪，將瑣碎的口語整理成得體的書面表達。",
        "features.f9.title": "多雲路由，穩定不斷線",
        "features.f9.desc": "整合 Groq 極速推論與 OpenRouter 廣大模型庫。即便某個服務忙碌，也能自動切換備援，確保你的靈感隨時都能被捕捉。",
        "download.macDesc": "Apple Silicon (M1/M2/M3/M4) 專用",
        "beta.label": "Android 測試招募",
        "beta.title": "Android 封測計畫 (NPP)",
        "beta.subtitle": "我們正在招募 20 位以上的外部測試者。加入封測，搶先體驗 Android 智慧語音輸入！"
    },
    en: {
        "nav.features": "Features",
        "nav.howItWorks": "Workflow",
        "nav.pricing": "Pricing",
        "nav.download": "Download",
        "nav.privacy": "Privacy",
        "nav.cta": "Get Started",
        "hero.badge": "Flow your ideas · v1.9.8",
        "hero.title1": "Just speak,",
        "hero.title2": "get professional text.",
        "hero.subtitle": "SGH Voice is like an intuitive stenographer. Beyond mere transcription, it filters fillers, corrects typos, and formats perfectly. Private by design, 100% local data.",
        "hero.cta": "Free Download",
        "hero.ctaSecondary": "See How It Works",
        "features.f2.title": "Context-Aware Polishing",
        "features.f2.desc": "Filters out 'um' and 'uh' automatically, transforming fragmented speech into professional, ready-to-use writing.",
        "features.f9.title": "Multi-Cloud Reliability",
        "features.f9.desc": "Hybrid routing between Groq and OpenRouter. Never miss a beat even if one provider is down.",
        "download.macDesc": "Optimized for Apple Silicon (M1-M4)",
        "beta.label": "Android Testing",
        "beta.title": "Android Closed Beta (NPP)",
        "beta.subtitle": "Help us shape the future of Android voice input. Join our testing program and get early access."
    }
};

function setLanguage(lang) {
    localStorage.setItem('sgh_lang', lang);
    applyLanguage(lang);
}

function applyLanguage(lang) {
    const data = translations[lang] || translations['en'];
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (data[key]) {
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                el.placeholder = data[key];
            } else {
                el.innerHTML = data[key];
            }
        }
    });
    document.getElementById('currentLang').innerText = 
        lang === 'ja' ? '日本語' : lang === 'zh' ? '繁體中文' : 'English';
    
    // Update active state in dropdown
    document.querySelectorAll('.lang-option').forEach(opt => {
        opt.classList.toggle('active', opt.getAttribute('data-lang') === lang);
    });
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('sgh_lang') || (navigator.language.startsWith('ja') ? 'ja' : navigator.language.startsWith('zh') ? 'zh' : 'en');
    applyLanguage(saved);
});
