"""
config.py — 設定與資料持久化層
所有本地資料都存在 ~/.voice-input/
"""
import json
import os
import time
from datetime import datetime, date

# ─── 內部基礎詞庫（不在 Dashboard UI 顯示，但辨識時使用）────────
BASE_CUSTOM_WORDS = [
    "新義豊", "Shingihou", "KusuriJapan", "MedicalSupporter",
    "SGH Phone", "林紀全", "薬機法", "PMD Act", "個人輸入",
    "Ultravox", "Twilio", "n8n", "LINE Bot",
    "福岡", "博多", "代表取締役",
    "Haiku", "Sonnet", "OpenCC", "Gatekeeper", "PyInstaller",
    "Groq", "FastAPI", "Hono", "Zeabur",
    "InputMethodService", "OkHttp", "Coroutine",
]

BASE_CORRECTIONS = {
    "新義豐": "新義豊",
    "新义丰": "新義豊",
    "醫療supporter": "Medical Supporter",
    "medicalsupporter": "Medical Supporter",
    "薬日本": "kusurijapan",
    "林紀泉": "林紀全",
    "林記全": "林紀全",
    # Claude 常被 Whisper 辨識為 cloud/Cloud/CLOUD（發音相似）
    "cloud code": "Claude Code",
    "cloud AI": "Claude AI",
    "cloud haiku": "Claude Haiku",
    "cloud sonnet": "Claude Sonnet",
    "cloud opus": "Claude Opus",
    "cloud API": "Claude API",
    "cloud desktop": "Claude Desktop",
    "cloud": "Claude",  # 獨立的 cloud → Claude（最後匹配，長詞優先）
}

# 不分大小寫的修正規則（key 全部小寫，匹配時做 case-insensitive 替換）
# 適用於 Whisper 輸出大小寫不穩定的情況（如 CLOUD、Cloud、cloud 都應修正為 Claude）
CASE_INSENSITIVE_CORRECTIONS = True

# ─── 使用場景預設（醫療、一般等）────────────────────────
SCENE_PRESETS = {
    "general": {
        "label": "一般",
        "custom_words": [],
        "corrections": {},
        "system_prompt_extra": "",
    },
    "medical": {
        "label": "醫療・藥品・生技",
        "custom_words": [
            # 日文醫療（診療科目・檢查）
            "心電図", "CT", "MRI", "エコー", "内視鏡", "カルテ", "レントゲン",
            "血液検査", "尿検査", "病理検査", "生検", "処方箋",
            "收縮壓", "舒張壓", "血氧飽和度", "SpO2", "HbA1c",
            # 診療科目
            "内科", "外科", "整形外科", "皮膚科", "眼科", "耳鼻咽喉科",
            "産婦人科", "小児科", "精神科", "循環器内科", "消化器内科",
            # 藥品（日本常用處方藥）
            "アムロジピン", "メトホルミン", "ランソプラゾール", "ロキソニン",
            "アジスロマイシン", "プレドニゾロン", "ワーファリン", "インスリン",
            "オプジーボ", "キイトルーダ", "アバスチン", "ハーセプチン",
            "リリカ", "デパス", "マイスリー",
            # 生技・再生醫療
            "幹細胞", "iPS細胞", "CAR-T", "免疫チェックポイント",
            "PD-1", "PD-L1", "抗体医薬", "バイオシミラー",
            "再生医療", "遺伝子治療", "エクソソーム", "NK細胞",
            # 臺灣醫療中文
            "電腦斷層", "核磁共振", "超音波", "胃鏡", "大腸鏡",
            "處方籤", "轉診單", "病歷", "掛號", "健保",
        ],
        "corrections": {
            "心電図": "心電図", "处方笺": "處方箋", "处方签": "處方籤",
            "干细胞": "幹細胞", "免疫检查点": "免疫チェックポイント",
        },
        "system_prompt_extra": (
            "8. 醫療場景專用：保留所有醫療術語、藥品名、檢查名稱的原文，不得簡化或改寫。"
            "日文醫療術語（カルテ、処方箋等）保持原樣。"
            "藥品名稱保持原文拼寫（アムロジピン、Opdivo 等）。"
        ),
    },
    "medical_consultation": {
        "label": "看診紀錄（SOAP病歷摘要）",
        "custom_words": [
            "BP", "DM", "HTN", "SOB", "URI", "Appt", "Sx", "Tx", "Dx", "Hx",
            "心電図", "CT", "MRI", "エコー", "カルテ", "レントゲン"
        ],
        "corrections": {
            "逼批": "BP", "低欸姆": "DM", "逼低": "BD",
        },
        "system_prompt_extra": (
            "\n【⚠️看診紀錄特別指令：強行覆寫上述格式】\n"
            "這是一場「醫生與病患/家屬的看診對話」。請扮演專業醫療助理，忽略前述『商務短文』的排版要求，將對話直接轉寫並整理為一份專業的「醫療看診摘要 (Medical Summary)」。\n"
            "格式請採用 SOAP 架構或結構化的臨床病歷筆記：\n"
            "- [S] 主觀陳述 (Subjective, 病患症狀感)\n"
            "- [O] 客觀發現 (Objective, 醫生觀察/檢查)\n"
            "- [A] 評估 diagnoses (Assessment)\n"
            "- [P] 計畫 (Plan, 處置/用藥)\n"
            "請將對話中的症狀與醫療縮寫保留（若有需要，可自動展開以便醫生閱讀），此份摘要將直接讓醫生貼入電子病歷系統中。"
        ),
    },
}

# ─── App 感知場景風格（偵測前景 App 自動切換 prompt）─────────
# App 感知風格：根據前景 App 自動調整輸出格式
# 核心原則：語言由口述內容的主要語言決定，不由 App 強制指定
_LANG_RULE = "語言規則：根據口述內容的主要語言輸出，不強制指定語言。中文必須是繁體中文。"
DEFAULT_APP_STYLES = {
    "chat": {
        "label": "通訊 💬",
        "apps": [
            "jp.naver.line.mac",
            "net.whatsapp.WhatsApp", "net.whatsapp.WhatsApp.mac",
            "com.tinyspeck.slackmacgap",     # Slack
            "com.hnc.Discord",               # Discord
            "org.telegram.Telegram",         # Telegram
            "com.facebook.archon",           # Messenger
        ],
        "prompt": f"聊天訊息風格：口語、簡潔、短句。{_LANG_RULE}",
    },
    "email": {
        "label": "信件 📧",
        "apps": [
            "com.apple.mail",
            "com.google.Gmail",
            "com.microsoft.Outlook",
        ],
        "prompt": f"商務信件風格：段落分明、語氣得體。{_LANG_RULE}",
    },
    "notes": {
        "label": "筆記 📝",
        "apps": [
            "notion.id",
            "md.obsidian",
            "net.shinyfrog.bear",
            "com.apple.Notes",
            "com.evernote.Evernote",
        ],
        "prompt": f"筆記風格：善用條列式、簡潔扼要。{_LANG_RULE}",
    },
    "code": {
        "label": "開發 💻",
        "apps": [
            "com.microsoft.VSCode",
            "com.apple.dt.Xcode",
            "com.todesktop.230313mzl4w4u92",  # Cursor
            "dev.warp.Warp-Stable",
            "com.googlecode.iterm2",
            "com.apple.Terminal",
        ],
        "prompt": (
            "開發環境：保留所有技術用語原始寫法（Repo, API, GitHub, Claude, REPL, Docker 等），"
            f"不加多餘標點。{_LANG_RULE}"
        ),
    },
    "ai_chat": {
        "label": "AI 對話 ✨",
        "apps": [
            "com.openai.chat",                # ChatGPT
            "com.anthropic.claudefordesktop",  # Claude Desktop
        ],
        "prompt": f"AI 對話：整理成完整的問題或指示。{_LANG_RULE}",
    },
    "search": {
        "label": "搜尋 🔍",
        "apps": [
            "com.apple.Safari",
            "com.google.Chrome",
            "org.mozilla.firefox",
            "company.thebrowser.Browser",     # Arc
        ],
        "prompt": "搜尋模式：轉為簡短搜尋關鍵字，最少標點。",
    },
    "social": {
        "label": "社群 👥",
        "apps": [
            "com.atebits.Tweetie2",    # X (Twitter)
            "com.facebook.Facebook",
            "com.burbn.instagram",
        ],
        "prompt": f"社群貼文風格：親切自然、適度換行。{_LANG_RULE}",
    },
    "default": {
        "label": "一般",
        "apps": [],
        "prompt": "",
    },
}

def detect_app_style(config):
    """前景 App の Bundle ID から場景スタイルを判定（macOS 専用，套用使用者自訂）"""
    app_styles = config.get("app_styles", DEFAULT_APP_STYLES)
    app_style_lookup = {}
    for style_key, style_data in app_styles.items():
        for bundle_id in style_data.get("apps", []):
            app_style_lookup[bundle_id] = style_key

    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        bundle_id = app.bundleIdentifier() or ""
        app_name = app.localizedName() or ""
        style_key = app_style_lookup.get(bundle_id, "default")
        return {
            "bundle_id": bundle_id,
            "app_name": app_name,
            "style": style_key,
            "prompt": app_styles.get(style_key, {}).get("prompt", ""),
        }
    except Exception:
        return {"bundle_id": "", "app_name": "", "style": "default", "prompt": ""}

DATA_DIR = os.path.expanduser("~/.voice-input")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
DICTIONARY_FILE = os.path.join(DATA_DIR, "dictionary.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
SMART_REPLACE_FILE = os.path.join(DATA_DIR, "smart_replace.json")

# ─── 本地模型路徑映射（短名稱 → 實際路徑）────────────────
LOCAL_MODEL_PATHS = {
    "breeze-asr-25-4bit": "/Volumes/Satechi_SSD/huggingface/hub/breeze-asr-25-mlx-4bit",
    "breeze-asr-25": "/Volumes/Satechi_SSD/huggingface/hub/breeze-asr-25-mlx",
}

# Breeze-ASR-25 基於 whisper-large-v2（80 mel bins），需要特殊處理
BREEZE_MODELS = {"breeze-asr-25-4bit", "breeze-asr-25"}

DEFAULT_CONFIG = {
    "openai_api_key": "",
    "anthropic_api_key": "",
    "elevenlabs_api_key": "",
    "groq_api_key": "",
    "whisper_model": "whisper-1",
    "claude_model": "claude-haiku-4-5-20251001",
    "hotkey_mode": "push_to_talk",          # push_to_talk | toggle
    "hotkey": "right_cmd",                  # right_cmd, ctrl+shift+space, etc.
    "language": "auto",                     # auto, zh, ja, en
    "target_language": "",                  # 翻譯目標語言（空 = 不翻譯）
    "enable_claude_polish": True,           # Claude 後處理潤稿
    "enable_auto_learn": True,              # 自動學習修正
    "enable_filler_removal": True,          # 移除填充詞
    "enable_auto_format": True,             # 自動格式化
    "enable_self_correction": True,         # 偵測口語修正
    "enable_hybrid_mode": True,             # 混合模式開關 (Local + Cloud)，Apple Silicon 預設開啟
    "hybrid_audio_threshold": 15,           # 錄音小於 15 秒用 Local Whisper
    "hybrid_text_threshold": 30,            # 句子小於 30 字用 Local LLM (Qwen)
    "stt_engine": "mlx-whisper",                           # mlx-whisper | qwen3-asr | cloud-only
    "local_whisper_model": "breeze-asr-25-4bit",           # 本地 Whisper 模型（Breeze-ASR-25 繁中最強）
    "local_llm_model": "qwen3.5:latest",    # Ollama 上的本地模型名稱 (使用 2026 最新 Qwen 3.5)
    "groq_model": "llama-3.3-70b-versatile",      # Groq LLM 模型 (目前的旗艦穩定版)
    "groq_whisper_model": "whisper-large-v3-turbo",  # Groq STT 模型
    "local_llm_timeout_sec": 6.0,           # 本地 Ollama 超時秒數（避免 1.5 秒過短造成頻繁 fallback）
    "backup_audio_dir": "",                  # 音訊備份目錄（空字串=不備份）
    "enable_voiceprint": False,              # 聲紋驗證開關
    "voiceprint_threshold": 0.97,            # 聲紋相似度閾值（0.95~0.99）
    "sample_rate": 16000,
    "silence_threshold": 0.001,
    "silence_duration": 2.0,
    "max_recording_duration": 360,          # 6 分鐘 (同 Typeless)
    "auto_paste": True,
    "show_notification": True,
    "typing_speed_cpm": 50,                 # 用戶打字速度（每分鐘字元數，中文約 30-60）
    "custom_words": [
        "繁體中文", "輸入法",
        "Repo", "Repository", "GitHub", "branch", "Release", "DMG",
        "API", "Android", "Kotlin", "Whisper",
        "Docker", "Google Play", "IME", "WebSocket",
        "Push-to-Talk", "Toggle", "PCM", "WAV",
        "OpenCC", "PyInstaller",
    ],
    "filler_words": {
        "zh": ["嗯", "啊", "那個", "就是", "然後", "對", "欸"],
        "ja": ["えーと", "あの", "えー", "まあ", "なんか", "ちょっと"],
        "en": ["um", "uh", "like", "you know", "basically", "actually", "so yeah"],
    },
    "claude_system_prompt": (
        "你是語音轉文字後處理與文法助手。\n"
        "請只做以下處理：修正明顯錯別字與文法錯誤、補上基本標點、移除少量口語填充詞、優化語氣（Grammar & Tone）使其聽起來流暢自然。\n"
        "【絕對不要翻譯！】自動判斷原文是中文、日文還是英文，保持講者的語言。多語混合時也保持原狀。\n"
        "只輸出修正後文字。"
    ),
    "active_scene": "general",
    "dashboard_port": 7865,
}


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


# ─── Config ──────────────────────────────────────────────

def load_config():
    _ensure_dir()
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return {**DEFAULT_CONFIG, **saved}
    return DEFAULT_CONFIG.copy()


def save_config(config):
    _ensure_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ─── Dictionary ──────────────────────────────────────────

def load_dictionary():
    _ensure_dir()
    if os.path.exists(DICTIONARY_FILE):
        with open(DICTIONARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"corrections": {}, "frequency": {}, "auto_added": []}


def save_dictionary(d):
    _ensure_dir()
    with open(DICTIONARY_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ─── History ─────────────────────────────────────────────

def load_history():
    _ensure_dir()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history):
    _ensure_dir()
    history = history[-2000:]  # 保留最近 2000 筆
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ─── Stats ───────────────────────────────────────────────

def load_stats():
    _ensure_dir()
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "total_dictations": 0,
        "total_words": 0,
        "total_characters": 0,
        "total_seconds_saved": 0.0,
        "total_audio_seconds": 0.0,
        "daily": {},               # { "2026-02-20": { words, chars, dictations, seconds_saved } }
        "languages_detected": {},  # { "zh": count, "ja": count, "en": count }
        "corrections_applied": 0,
        "first_use_date": "",
        "streak_days": 0,
        "last_use_date": "",
    }


def save_stats(stats):
    _ensure_dir()
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


# ─── Smart Replace ──────────────────────────────────────

DEFAULT_SMART_REPLACE = {
    "@mail": "your@email.com",
    "@phone": "+00-000-000-0000",
    "@company": "Your Company",
    "@site": "https://example.com",
    "@greeting": "您好，",
}


def load_smart_replace():
    _ensure_dir()
    if os.path.exists(SMART_REPLACE_FILE):
        with open(SMART_REPLACE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_SMART_REPLACE.copy()


def save_smart_replace(rules):
    _ensure_dir()
    with open(SMART_REPLACE_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def update_stats(text, audio_duration, config):
    """Update stats after a successful dictation."""
    stats = load_stats()
    today = date.today().isoformat()

    # Word/char count
    words = len(text.split())
    chars = len(text)

    # 節省時間：打字所需時間 - 語音錄製時間
    typing_speed_cpm = config.get("typing_speed_cpm", 50)  # 每分鐘字元數（中文約 30-60）
    typing_time = (chars / typing_speed_cpm) * 60 if typing_speed_cpm > 0 else 0
    time_saved = max(0, typing_time - audio_duration)

    # Update totals
    stats["total_dictations"] += 1
    stats["total_words"] += words
    stats["total_characters"] += chars
    stats["total_seconds_saved"] += time_saved
    stats["total_audio_seconds"] += audio_duration

    # Daily stats
    if today not in stats["daily"]:
        stats["daily"][today] = {"words": 0, "chars": 0, "dictations": 0, "seconds_saved": 0, "audio_seconds": 0}
    day = stats["daily"][today]
    day["words"] += words
    day["chars"] += chars
    day["dictations"] += 1
    day["seconds_saved"] += time_saved
    day["audio_seconds"] = day.get("audio_seconds", 0) + audio_duration

    # First use
    if not stats["first_use_date"]:
        stats["first_use_date"] = today

    # Streak
    from datetime import timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if stats["last_use_date"] == today:
        pass  # same day
    elif stats["last_use_date"] == yesterday:
        stats["streak_days"] += 1
    else:
        stats["streak_days"] = 1
    stats["last_use_date"] = today

    # Keep only last 90 days of daily stats
    sorted_days = sorted(stats["daily"].keys())
    if len(sorted_days) > 90:
        for old_day in sorted_days[:-90]:
            del stats["daily"][old_day]

    save_stats(stats)
    return stats
