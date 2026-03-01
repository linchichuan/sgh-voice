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
    # Claude 常被 Whisper 辨識為 cloud/Cloud
    "cloud code": "Claude Code",
    "Cloud Code": "Claude Code",
    "cloud AI": "Claude AI",
    "Cloud AI": "Claude AI",
    "cloud haiku": "Claude Haiku",
    "Cloud Haiku": "Claude Haiku",
    "cloud sonnet": "Claude Sonnet",
    "Cloud Sonnet": "Claude Sonnet",
}

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
}

DATA_DIR = os.path.expanduser("~/.voice-input")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
DICTIONARY_FILE = os.path.join(DATA_DIR, "dictionary.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
SMART_REPLACE_FILE = os.path.join(DATA_DIR, "smart_replace.json")

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
    "local_whisper_model": "mlx-community/whisper-turbo",  # 本地 Whisper 模型
    "local_llm_model": "qwen2.5:3b",        # Ollama 上的本地模型名稱
    "backup_audio_dir": "",                  # 音訊備份目錄（空字串=不備份）
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
        "你是專業的語音辨識後處理助手。你的任務：\n"
        "1. 修正語音辨識中的錯字和專業術語\n"
        "2. 移除口語填充詞（嗯、啊、那個、えーと、um 等）\n"
        "3. 偵測說話者的自我修正，只保留最終意圖\n"
        "4. 將口語組織成清晰的書面文字\n"
        "5. 保持原文語言，不要翻譯\n"
        "6. 保留說話者的個人風格和語氣\n"
        "只輸出修正後的文字，不要任何說明。"
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
