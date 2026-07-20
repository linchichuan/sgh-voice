const translations = {
    ja: {
        "meta.title": "SGH Voice — 中・日・英が混ざっても、文章は乱れない。",
        "meta.description": "SGH Voice は、繁體中文・日本語・English の混ざった会話を整え、カーソル位置へ直接入力する macOS 音声入力ツールです。元のクリップボードを保持し、ローカル処理と BYOK に対応。",

        "nav.proof": "入力例",
        "nav.features": "機能",
        "nav.howItWorks": "使い方",
        "nav.privacy": "処理方法",
        "nav.download": "ダウンロード",
        "nav.cta": "macOS 版を入手",

        "hero.eyebrow": "macOS 音声入力 · v2.6.0",
        "hero.title": "<span class=\"hero-line hero-line-primary\">言葉を混ぜても、</span><span class=\"hero-line hero-line-accent\">文章は乱れない。</span>",
        "hero.subtitle": "繁體中文、日本語、English を切り替えずに話す。SGH Voice が意図と用語を保ちながら整え、カーソル位置へ直接入力します。",
        "hero.cta": "v2.6.0 をダウンロード",
        "hero.secondary": "変換例を見る",
        "hero.note": "Apple Silicon · アプリ本体無料 · BYOK / ローカル処理対応",
        "hero.mock.listening": "Listening · 3 languages detected",
        "hero.mock.rawLabel": "話した内容",
        "hero.mock.rawText": "那 landing page の content form、SEO 跟 GEO も一起重新整理一下。",
        "hero.mock.process": "意図・表記・専門語を整理",
        "hero.mock.target": "カーソル位置",
        "hero.mock.inserted": "入力済み",
        "hero.mock.resultText": "Landing page の content form を見直し、SEO と GEO もあわせて最適化してください。",
        "hero.mock.clipboard": "元のクリップボードを復元",
        "hero.mock.shortcut": "ショートカット変更可",

        "trust.intro": "混合言語の仕事に必要なものを、一つに。",
        "trust.item1": "三言語を自動判別",
        "trust.item2": "直接入力",
        "trust.item3": "クリップボード保持",
        "trust.item4": "検証済み学習",

        "proof.kicker": "VOICE → READY TO USE",
        "proof.title": "文字起こしで終わらない。<br>そのまま使える文章へ。",
        "proof.subtitle": "言い直し、フィラー、言語の切り替わりを読み取り、文字体系と専門用語を守りながら整えます。",
        "proof.before": "話したまま",
        "proof.after": "SGH Voice",
        "proof.ex1.title": "中・日・英の混ざった指示",
        "proof.ex1.tag": "Language mix",
        "proof.ex1.before": "這個 contact form の CTA、もう少し clear にして、あと mobile 版も確認。",
        "proof.ex1.after": "Contact form の CTA をより明確にし、モバイル版の表示も確認してください。",
        "proof.ex2.title": "表記を壊さない",
        "proof.ex2.tag": "Script guard",
        "proof.ex2.before": "ひらがな、カタカナ、API route 跟 TypeScript 的 type 都不要改錯。",
        "proof.ex2.after": "ひらがな、カタカナ、API route、TypeScript の type を誤って変更しないでください。",
        "proof.ex3.title": "専門語をそのまま保持",
        "proof.ex3.tag": "Terminology",
        "proof.ex3.before": "SEO、GEO、canonical 跟 structured data 這幾個都一起檢查。",
        "proof.ex3.after": "SEO、GEO、canonical、structured data をまとめて確認してください。",
        "proof.disclaimer": "表示例です。結果は選択したモデル、辞書、設定、音声環境によって異なります。",

        "features.kicker": "BUILT FOR CODE-SWITCHING",
        "features.title": "混ぜて話す人のために、<br>入力の最後まで設計。",
        "features.f1.title": "言語と文字体系を守る",
        "features.f1.desc": "繁體中文、日本語、英語の切り替わりを前提に処理。Latin、かな、カタカナ、URL、コード、略語を不用意に置き換えません。",
        "features.f2.title": "確認した修正だけを学習",
        "features.f2.desc": "あなたが実際に編集した履歴から、選んだ候補だけを辞書へ反映。誤認識を無条件に覚え込ませません。",
        "features.f3.title": "貼り付け作業をなくす",
        "features.f3.desc": "処理後の文字をアクティブなカーソル位置へ直接入力。一時利用したクリップボードは元の内容へ戻します。",
        "features.f4.title": "仕事に合わせて操作を選ぶ",
        "features.f4.desc": "ショートカット、push-to-talk、言語プロファイル、STT / LLM、辞書をダッシュボードから調整できます。",

        "workflow.kicker": "ONE CONTINUOUS FLOW",
        "workflow.title": "話し終えたら、<br>もう入力は完了。",
        "workflow.subtitle": "文字起こし画面を開いてコピーする必要はありません。普段のアプリを離れずに使えます。",
        "workflow.s1.title": "カーソルを置く",
        "workflow.s1.desc": "Mail、Notion、Slack、ブラウザなど、入力したい場所を選びます。",
        "workflow.s2.title": "ショートカットを押して話す",
        "workflow.s2.desc": "言語を選び直さず、普段どおり混ぜて話します。ショートカットは変更できます。",
        "workflow.s3.title": "整った文章が入る",
        "workflow.s3.desc": "文字がカーソル位置へ入り、もともとコピーしていた内容もそのまま残ります。",

        "privacy.kicker": "YOU CHOOSE THE ROUTE",
        "privacy.title": "処理方法まで、<br>自分で選べる。",
        "privacy.subtitle": "「全部クラウド」でも「全部ローカル」でもありません。目的、端末、精度に合わせて処理先を選べます。",
        "privacy.local.badge": "ON DEVICE",
        "privacy.local.title": "ローカル音声認識",
        "privacy.local.desc": "対応モデルを端末上で実行。音声をクラウドへ送らずに処理したい場面で選べます。",
        "privacy.local.item1": "Apple Silicon 対応",
        "privacy.local.item2": "辞書・設定は端末で管理",
        "privacy.cloud.badge": "YOUR PROVIDER",
        "privacy.cloud.title": "BYOK クラウド処理",
        "privacy.cloud.desc": "自分で設定した AI プロバイダーを利用。選択時のみ、そのプロバイダーへ音声または文字を送信します。",
        "privacy.cloud.item1": "API キーはユーザーが管理",
        "privacy.cloud.item2": "新義豊の中継サーバーに音声を保存しない",
        "privacy.note": "クラウド利用時のデータ取り扱いは、選択した各プロバイダーの規約・プライバシーポリシーに従います。",

        "pricing.kicker": "SIMPLE BY DESIGN",
        "pricing.title": "アプリ本体は無料。<br>使う AI は自分で選ぶ。",
        "pricing.subtitle": "不明確な「無制限プラン」は設けず、クラウド利用料は選んだプロバイダーへ直接支払う BYOK 方式です。",
        "pricing.plan": "SGH Voice for macOS",
        "pricing.f1": "アプリの全機能",
        "pricing.f2": "カスタム辞書と検証済み学習",
        "pricing.f3": "ローカル処理オプション",
        "pricing.f4": "自分の API キーを利用",
        "pricing.note": "※ クラウド AI の利用料は各プロバイダーから別途請求されます。",

        "download.title": "混ぜて話す。<br>整った文章で届く。",
        "download.subtitle": "現在の公開インストーラは macOS Apple Silicon 向けです。",
        "download.cta": "Apple Silicon 版をダウンロード",
        "download.notes": "リリースノート",

        "faq.title": "導入前に知っておきたいこと。",
        "faq.q1": "中国語・日本語・英語を混ぜて話せますか？",
        "faq.a1": "はい。繁體中文・日本語・English が混ざる発話を想定しています。固有名詞や独自表記は辞書へ追加できます。",
        "faq.q2": "入力するとクリップボードは上書きされますか？",
        "faq.a2": "v2.6.0 では一時利用後に元の内容を復元するため、通常のコピー内容を引き続き使えます。",
        "faq.q3": "音声データはどこで処理されますか？",
        "faq.a3": "ローカル認識を選ぶと端末上で処理されます。クラウドを選ぶ場合は、設定したプロバイダーへ送信されます。新義豊の中継サーバーには音声を保存しません。",
        "faq.q4": "Intel Mac、iPhone、Android でも使えますか？",
        "faq.a4": "現在の公開インストーラは Apple Silicon Mac 向けです。その他のプラットフォームは公開状況を Release ページで案内します。",
        "faq.q5": "医療や技術用語にも使えますか？",
        "faq.a5": "辞書と文書モードで入力を補助できます。ただし医療判断や内容の正確性を保証するものではなく、最終確認は利用者が行ってください。",

        "beta.kicker": "MOBILE PREVIEW",
        "beta.title": "Android 版の先行テストに参加。",
        "beta.subtitle": "モバイル版は開発中です。Android のテストに参加したい方は、利用端末をお知らせください。",
        "beta.form.name": "お名前 / ニックネーム",
        "beta.form.email": "Google Play 用 Gmail",
        "beta.form.device": "Android 端末",
        "beta.form.devicePlaceholder": "例：Pixel 9、Galaxy S25",
        "beta.form.submit": "先行テストに申し込む",
        "beta.form.submitting": "送信中…",
        "beta.form.success": "ありがとうございます。次のステップをメールでご案内します。",
        "beta.form.error": "送信に失敗しました。もう一度お試しください。",
        "beta.form.retry": "再送信",

        "footer.desc": "新義豊株式会社が開発する、多言語 AI 音声入力ツール。",
        "footer.product": "Product",
        "footer.legal": "Legal",
        "footer.company": "Company",
        "footer.privacy": "プライバシーポリシー",
        "footer.terms": "利用規約",
        "footer.note": "Made for multilingual work."
    },

    zh: {
        "meta.title": "SGH Voice — 語言可以混著說，文字不必跟著亂。",
        "meta.description": "SGH Voice 是為繁體中文、日文與英文混合口述設計的 macOS 語音輸入工具。整理語意後直接輸入游標位置，並保留原本的剪貼簿內容，支援本機處理與 BYOK。",

        "nav.proof": "實際效果",
        "nav.features": "主要功能",
        "nav.howItWorks": "使用方式",
        "nav.privacy": "處理方式",
        "nav.download": "立即下載",
        "nav.cta": "取得 macOS 版",

        "hero.eyebrow": "macOS 語音輸入 · v2.6.0",
        "hero.title": "<span class=\"hero-line hero-line-primary\">語言可以混著說，</span><span class=\"hero-line hero-line-accent\">文字不必跟著亂。</span>",
        "hero.subtitle": "繁體中文、日本語、English 不必來回切換。SGH Voice 會保留你的意思與專有名詞，整理後直接輸入游標位置。",
        "hero.cta": "下載 v2.6.0",
        "hero.secondary": "看看實際效果",
        "hero.note": "Apple Silicon · 應用程式免費 · 支援 BYOK / 本機處理",
        "hero.mock.listening": "正在聆聽 · 偵測到 3 種語言",
        "hero.mock.rawLabel": "原始口述",
        "hero.mock.rawText": "那 landing page の content form、SEO 跟 GEO も一起重新整理一下。",
        "hero.mock.process": "整理語意、文字系統與專有名詞",
        "hero.mock.target": "目前游標位置",
        "hero.mock.inserted": "已輸入",
        "hero.mock.resultText": "重新檢視 landing page 的 content form，並同步最佳化 SEO 與 GEO。",
        "hero.mock.clipboard": "原有剪貼簿已復原",
        "hero.mock.shortcut": "快捷鍵可自訂",

        "trust.intro": "多語工作真正需要的功能，一次到位。",
        "trust.item1": "三語自動辨識",
        "trust.item2": "直接輸入",
        "trust.item3": "保留剪貼簿",
        "trust.item4": "經確認才學習",

        "proof.kicker": "VOICE → READY TO USE",
        "proof.title": "不只把聲音變成字。<br>而是變成能直接使用的內容。",
        "proof.subtitle": "辨識改口、贅字與語言切換，同時保護文字系統和專有名詞，讓結果更接近你真正想寫的內容。",
        "proof.before": "原始口述",
        "proof.after": "SGH Voice",
        "proof.ex1.title": "中文、日文、英文混合指令",
        "proof.ex1.tag": "Language mix",
        "proof.ex1.before": "這個 contact form の CTA、もう少し clear にして、あと mobile 版も確認。",
        "proof.ex1.after": "請讓 contact form 的 CTA 更清楚，並確認行動版顯示。",
        "proof.ex2.title": "不破壞原本的文字系統",
        "proof.ex2.tag": "Script guard",
        "proof.ex2.before": "ひらがな、カタカナ、API route 跟 TypeScript 的 type 都不要改錯。",
        "proof.ex2.after": "平假名、片假名、API route 與 TypeScript 的 type 都不要改錯。",
        "proof.ex3.title": "保留專業用語",
        "proof.ex3.tag": "Terminology",
        "proof.ex3.before": "SEO、GEO、canonical 跟 structured data 這幾個都一起檢查。",
        "proof.ex3.after": "請一併檢查 SEO、GEO、canonical 與 structured data。",
        "proof.disclaimer": "以上為呈現效果的示例。實際結果會依模型、詞庫、設定與收音環境而異。",

        "features.kicker": "BUILT FOR CODE-SWITCHING",
        "features.title": "專為混語使用者設計，<br>一路處理到輸入完成。",
        "features.f1.title": "保護語言與文字系統",
        "features.f1.desc": "以繁體中文、日文與英文交錯為前提。避免任意改動 Latin 字母、平假名、片假名、URL、程式碼與縮寫。",
        "features.f2.title": "只學習你確認過的修正",
        "features.f2.desc": "從你實際編輯過的紀錄中，將選定的候選詞加入詞庫；不會把每一次誤辨識都無條件學起來。",
        "features.f3.title": "不必再手動貼上",
        "features.f3.desc": "處理完成後直接輸入目前游標位置；暫時使用的剪貼簿會恢復成原本內容。",
        "features.f4.title": "依工作方式調整操作",
        "features.f4.desc": "可從 Dashboard 調整快捷鍵、push-to-talk、語言 profile、STT / LLM 與自訂詞庫。",

        "workflow.kicker": "ONE CONTINUOUS FLOW",
        "workflow.title": "話完的同時，<br>輸入也完成。",
        "workflow.subtitle": "不必打開逐字稿畫面再複製。整個過程都留在你原本使用的 App 裡。",
        "workflow.s1.title": "把游標放在要輸入的位置",
        "workflow.s1.desc": "Mail、Notion、Slack、瀏覽器或任何可輸入文字的地方。",
        "workflow.s2.title": "按快捷鍵，自然說話",
        "workflow.s2.desc": "不用重新選擇語言，照平常方式混著說；快捷鍵也可以自行設定。",
        "workflow.s3.title": "整理後的文字直接出現",
        "workflow.s3.desc": "內容進入游標位置，原本複製的資料也保持不變，可以繼續貼上使用。",

        "privacy.kicker": "YOU CHOOSE THE ROUTE",
        "privacy.title": "連處理方式，<br>也由你決定。",
        "privacy.subtitle": "不是只能全部上雲，也不是只能完全離線。你可以依目的、裝置與準確度需求選擇處理路徑。",
        "privacy.local.badge": "ON DEVICE",
        "privacy.local.title": "本機語音辨識",
        "privacy.local.desc": "在支援的裝置上執行本機模型。適合不希望將語音送往雲端的使用情境。",
        "privacy.local.item1": "支援 Apple Silicon",
        "privacy.local.item2": "詞庫與設定保存在裝置上",
        "privacy.cloud.badge": "YOUR PROVIDER",
        "privacy.cloud.title": "BYOK 雲端處理",
        "privacy.cloud.desc": "使用你自行設定的 AI 供應商。只有選擇雲端處理時，語音或文字才會送往該供應商。",
        "privacy.cloud.item1": "API 金鑰由使用者管理",
        "privacy.cloud.item2": "新義豊中繼伺服器不保存語音",
        "privacy.note": "使用雲端服務時，資料處理方式依你所選供應商的條款與隱私權政策為準。",

        "pricing.kicker": "SIMPLE BY DESIGN",
        "pricing.title": "應用程式免費。<br>使用哪個 AI，由你選擇。",
        "pricing.subtitle": "不販售內容不清楚的「無限方案」。採 BYOK 模式，雲端用量直接向你選擇的供應商支付。",
        "pricing.plan": "SGH Voice for macOS",
        "pricing.f1": "應用程式全部功能",
        "pricing.f2": "自訂詞庫與經確認的學習",
        "pricing.f3": "本機處理選項",
        "pricing.f4": "使用自己的 API 金鑰",
        "pricing.note": "※ 雲端 AI 用量將由各供應商另外計費。",

        "download.title": "混著說，<br>用整理好的文字送出。",
        "download.subtitle": "目前公開的安裝程式支援 macOS Apple Silicon。",
        "download.cta": "下載 Apple Silicon 版",
        "download.notes": "版本說明",

        "faq.title": "安裝之前，你可能想先知道。",
        "faq.q1": "可以同時混說中文、日文和英文嗎？",
        "faq.a1": "可以。SGH Voice 以繁體中文、日本語與 English 混合口述為設計前提；人名、品牌與固定寫法也能加入自訂詞庫。",
        "faq.q2": "輸入文字時會覆蓋剪貼簿嗎？",
        "faq.a2": "v2.6.0 會在暫時使用剪貼簿後恢復原內容，所以你原本複製的資料仍能繼續貼上。",
        "faq.q3": "語音資料會在哪裡處理？",
        "faq.a3": "選擇本機辨識時，會在裝置上處理。選擇雲端時，資料會傳送至你設定的供應商；新義豊的中繼伺服器不保存語音。",
        "faq.q4": "Intel Mac、iPhone 和 Android 可以使用嗎？",
        "faq.a4": "目前公開的安裝程式是 Apple Silicon Mac 版。其他平台的公開狀態會在 GitHub Release 頁面公告。",
        "faq.q5": "醫療或技術用語也能使用嗎？",
        "faq.a5": "可以透過自訂詞庫與文件模式輔助輸入，但不取代醫療判斷，也不保證內容絕對正確；送出前仍需由使用者確認。",

        "beta.kicker": "MOBILE PREVIEW",
        "beta.title": "加入 Android 版先行測試。",
        "beta.subtitle": "行動版仍在開發中。如果你希望參加 Android 測試，請告訴我們使用的裝置。",
        "beta.form.name": "姓名 / 暱稱",
        "beta.form.email": "Google Play 使用的 Gmail",
        "beta.form.device": "Android 裝置",
        "beta.form.devicePlaceholder": "例如：Pixel 9、Galaxy S25",
        "beta.form.submit": "申請先行測試",
        "beta.form.submitting": "傳送中…",
        "beta.form.success": "謝謝你。我們會用 Email 說明下一步。",
        "beta.form.error": "傳送失敗，請再試一次。",
        "beta.form.retry": "重新傳送",

        "footer.desc": "新義豊株式會社開發的多語 AI 語音輸入工具。",
        "footer.product": "產品",
        "footer.legal": "法律資訊",
        "footer.company": "公司資訊",
        "footer.privacy": "隱私權政策",
        "footer.terms": "使用條款",
        "footer.note": "為多語工作而生。"
    },

    en: {
        "meta.title": "SGH Voice — Mix languages. Keep the writing clear.",
        "meta.description": "SGH Voice is a macOS voice-input tool built for mixed Traditional Chinese, Japanese, and English. It cleans up speech, inserts text at your cursor, restores your clipboard, and supports local processing and BYOK.",

        "nav.proof": "Examples",
        "nav.features": "Features",
        "nav.howItWorks": "How it works",
        "nav.privacy": "Processing",
        "nav.download": "Download",
        "nav.cta": "Get the macOS app",

        "hero.eyebrow": "Voice input for macOS · v2.6.0",
        "hero.title": "<span class=\"hero-line hero-line-primary\">Mix your languages.</span><span class=\"hero-line hero-line-accent\">Keep your writing clear.</span>",
        "hero.subtitle": "Speak in Traditional Chinese, Japanese, and English without switching modes. SGH Voice preserves intent and terminology, then inserts polished text right at your cursor.",
        "hero.cta": "Download v2.6.0",
        "hero.secondary": "See real examples",
        "hero.note": "Apple Silicon · Free app · BYOK / local processing",
        "hero.mock.listening": "Listening · 3 languages detected",
        "hero.mock.rawLabel": "What you said",
        "hero.mock.rawText": "この landing page 的 content form needs work, and SEO 跟 GEO too.",
        "hero.mock.process": "Organizing intent, scripts, and terms",
        "hero.mock.target": "Active cursor",
        "hero.mock.inserted": "Inserted",
        "hero.mock.resultText": "Review the landing page content form and optimize SEO and GEO at the same time.",
        "hero.mock.clipboard": "Original clipboard restored",
        "hero.mock.shortcut": "Custom shortcut",

        "trust.intro": "Everything multilingual work actually needs.",
        "trust.item1": "Three-language detection",
        "trust.item2": "Direct insertion",
        "trust.item3": "Clipboard preserved",
        "trust.item4": "Verified learning",

        "proof.kicker": "VOICE → READY TO USE",
        "proof.title": "More than a transcript.<br>Text you can use right away.",
        "proof.subtitle": "SGH Voice resolves restarts, filler words, and language switches while protecting scripts and specialist terminology.",
        "proof.before": "As spoken",
        "proof.after": "SGH Voice",
        "proof.ex1.title": "A mixed-language instruction",
        "proof.ex1.tag": "Language mix",
        "proof.ex1.before": "這個 contact form の CTA should be more clear，あと mobile 版も確認。",
        "proof.ex1.after": "Make the contact form CTA clearer and check the mobile layout as well.",
        "proof.ex2.title": "Scripts stay intact",
        "proof.ex2.tag": "Script guard",
        "proof.ex2.before": "Don't mess up ひらがな、カタカナ、the API route，還有 TypeScript type。",
        "proof.ex2.after": "Preserve ひらがな, カタカナ, the API route, and the TypeScript type.",
        "proof.ex3.title": "Specialist terms stay precise",
        "proof.ex3.tag": "Terminology",
        "proof.ex3.before": "SEO、GEO、canonical 跟 structured data，全部一起 check。",
        "proof.ex3.after": "Check SEO, GEO, canonical, and structured data together.",
        "proof.disclaimer": "Examples are illustrative. Results vary with the selected model, dictionary, settings, and recording environment.",

        "features.kicker": "BUILT FOR CODE-SWITCHING",
        "features.title": "Designed for people who mix languages,<br>all the way through insertion.",
        "features.f1.title": "Protect languages and scripts",
        "features.f1.desc": "Built around Traditional Chinese, Japanese, and English code-switching. Latin text, kana, URLs, code, numbers, and abbreviations are protected from careless replacement.",
        "features.f2.title": "Learn only from verified edits",
        "features.f2.desc": "Promote only the corrections you select from text you actually edited. SGH Voice does not blindly learn every recognition error.",
        "features.f3.title": "Remove the paste step",
        "features.f3.desc": "Processed text goes directly to the active cursor. The clipboard used during insertion is restored to its original content.",
        "features.f4.title": "Fit the controls to your work",
        "features.f4.desc": "Configure shortcuts, push-to-talk, language profiles, STT / LLM routing, and dictionaries from the dashboard.",

        "workflow.kicker": "ONE CONTINUOUS FLOW",
        "workflow.title": "When you finish speaking,<br>the typing is done.",
        "workflow.subtitle": "No transcript window to open and no text to copy. Stay inside the app where you are already working.",
        "workflow.s1.title": "Place your cursor",
        "workflow.s1.desc": "Use Mail, Notion, Slack, a browser, or anywhere else you can enter text.",
        "workflow.s2.title": "Hold a shortcut and speak",
        "workflow.s2.desc": "Mix languages naturally without choosing a new mode. The shortcut is configurable.",
        "workflow.s3.title": "Polished text appears",
        "workflow.s3.desc": "The result lands at your cursor, while the content you copied earlier remains available.",

        "privacy.kicker": "YOU CHOOSE THE ROUTE",
        "privacy.title": "Choose how your input<br>is processed.",
        "privacy.subtitle": "You are not locked into all-cloud or all-local processing. Choose the route that fits the task, device, and accuracy you need.",
        "privacy.local.badge": "ON DEVICE",
        "privacy.local.title": "Local speech recognition",
        "privacy.local.desc": "Run a supported model on your Mac when you want to keep audio away from cloud speech services.",
        "privacy.local.item1": "Designed for Apple Silicon",
        "privacy.local.item2": "Dictionary and settings stay on device",
        "privacy.cloud.badge": "YOUR PROVIDER",
        "privacy.cloud.title": "BYOK cloud processing",
        "privacy.cloud.desc": "Use the AI provider you configure. Audio or text is sent to that provider only when you select a cloud engine.",
        "privacy.cloud.item1": "You manage your API keys",
        "privacy.cloud.item2": "No audio stored on a Shingihou relay server",
        "privacy.note": "When you use a cloud service, data handling is governed by the terms and privacy policy of the provider you select.",

        "pricing.kicker": "SIMPLE BY DESIGN",
        "pricing.title": "The app is free.<br>You choose the AI.",
        "pricing.subtitle": "No vague “unlimited” plan. SGH Voice uses BYOK, so cloud usage is billed directly by the provider you select.",
        "pricing.plan": "SGH Voice for macOS",
        "pricing.f1": "All app features",
        "pricing.f2": "Custom dictionary and verified learning",
        "pricing.f3": "Local processing option",
        "pricing.f4": "Use your own API keys",
        "pricing.note": "Cloud AI usage is billed separately by each provider.",

        "download.title": "Speak in the mix.<br>Send polished text.",
        "download.subtitle": "The current public installer is for Apple Silicon Macs.",
        "download.cta": "Download for Apple Silicon",
        "download.notes": "Release notes",

        "faq.title": "What to know before installing.",
        "faq.q1": "Can I mix Chinese, Japanese, and English?",
        "faq.a1": "Yes. SGH Voice is designed around mixed Traditional Chinese, Japanese, and English speech. Add names, brands, and preferred spellings to your dictionary.",
        "faq.q2": "Does insertion overwrite my clipboard?",
        "faq.a2": "In v2.6.0, SGH Voice restores the original clipboard after using it temporarily, so your previous copy remains available.",
        "faq.q3": "Where is my audio processed?",
        "faq.a3": "A local engine processes audio on device. A cloud engine sends it to the provider you configure. Audio is not stored on a Shingihou relay server.",
        "faq.q4": "Does it work on Intel Mac, iPhone, or Android?",
        "faq.a4": "The current public installer is for Apple Silicon Macs. Availability for other platforms will be announced on the GitHub Releases page.",
        "faq.q5": "Can it handle medical or technical terminology?",
        "faq.a5": "Dictionaries and document modes can assist with specialist input, but they do not replace medical judgment or guarantee accuracy. Review important text before sending it.",

        "beta.kicker": "MOBILE PREVIEW",
        "beta.title": "Join the Android preview.",
        "beta.subtitle": "The mobile version is still in development. Tell us which Android device you use if you want to join testing.",
        "beta.form.name": "Name / nickname",
        "beta.form.email": "Gmail used for Google Play",
        "beta.form.device": "Android device",
        "beta.form.devicePlaceholder": "e.g. Pixel 9, Galaxy S25",
        "beta.form.submit": "Apply for preview access",
        "beta.form.submitting": "Sending…",
        "beta.form.success": "Thank you. We will email you with the next step.",
        "beta.form.error": "Could not send. Please try again.",
        "beta.form.retry": "Try again",

        "footer.desc": "A multilingual AI voice-input tool by Shingihou Co., Ltd.",
        "footer.product": "Product",
        "footer.legal": "Legal",
        "footer.company": "Company",
        "footer.privacy": "Privacy Policy",
        "footer.terms": "Terms of Service",
        "footer.note": "Made for multilingual work."
    }
};

const HTML_LANG = { ja: "ja", zh: "zh-Hant", en: "en" };
const LANG_DISPLAY = { ja: "日本語", zh: "繁體中文", en: "English" };
const META_LOCALE = { ja: "ja_JP", zh: "zh_TW", en: "en_US" };

function setLanguage(lang) {
    const normalized = translations[lang] ? lang : "ja";
    localStorage.setItem("sgh_lang", normalized);

    const url = new URL(window.location.href);
    url.searchParams.set("lang", normalized);
    window.history.replaceState({}, "", url);
    applyLanguage(normalized);
}

function applyLanguage(lang) {
    const normalized = translations[lang] ? lang : "ja";
    const data = translations[normalized];

    document.querySelectorAll("[data-i18n]").forEach((element) => {
        const key = element.getAttribute("data-i18n");
        if (Object.prototype.hasOwnProperty.call(data, key)) {
            element.innerHTML = data[key];
        }
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
        const key = element.getAttribute("data-i18n-placeholder");
        if (Object.prototype.hasOwnProperty.call(data, key)) {
            element.setAttribute("placeholder", data[key]);
        }
    });

    document.documentElement.lang = HTML_LANG[normalized] || "ja";
    document.title = data["meta.title"];
    setMeta("name", "description", data["meta.description"]);
    setMeta("property", "og:title", data["meta.title"]);
    setMeta("property", "og:description", data["meta.description"]);
    setMeta("property", "og:locale", META_LOCALE[normalized]);
    setMeta("name", "twitter:title", data["meta.title"]);
    setMeta("name", "twitter:description", data["meta.description"]);

    const currentLanguage = document.getElementById("currentLang");
    if (currentLanguage) {
        currentLanguage.textContent = LANG_DISPLAY[normalized];
    }

    document.querySelectorAll(".lang-option").forEach((option) => {
        option.classList.toggle("active", option.getAttribute("data-lang") === normalized);
    });

    window.SGH_I18N = data;
    window.SGH_LANG = normalized;
}

function setMeta(attribute, name, value) {
    if (!value) return;
    let element = document.querySelector('meta[' + attribute + '="' + name + '"]');
    if (!element) {
        element = document.createElement("meta");
        element.setAttribute(attribute, name);
        document.head.appendChild(element);
    }
    element.setAttribute("content", value);
}

function detectInitialLang() {
    const queryLanguage = new URLSearchParams(window.location.search).get("lang");
    if (queryLanguage && translations[queryLanguage]) return queryLanguage;

    const savedLanguage = localStorage.getItem("sgh_lang");
    if (savedLanguage && translations[savedLanguage]) return savedLanguage;

    const browserLanguage = (navigator.language || "en").toLowerCase();
    if (browserLanguage.startsWith("ja")) return "ja";
    if (browserLanguage.startsWith("zh")) return "zh";
    return "en";
}

document.addEventListener("DOMContentLoaded", () => {
    applyLanguage(detectInitialLang());
});
