"""
conftest.py — Shared fixtures for SGH Voice tests.

關鍵設計：所有測試都用 tmp_path 取代真實的 ~/.voice-input/，避免污染 user data。
- `isolated_data_dir` monkeypatches config.DATA_DIR + 相關 file path constants
- `mock_config` / `empty_memory` / `populated_memory` 提供常用 setup
- 全程 mock 掉 openai / anthropic / mlx_whisper，never make real API calls
"""
import importlib
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 把 repo root 加入 sys.path（讓 `import config` etc. 在 tests/ 下成功）
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """把 config 內部所有 ~/.voice-input/ 路徑常數重定向到 tmp_path。
    Yields 該 isolated data dir 路徑（Path）。"""
    import config as cfg

    data_dir = tmp_path / ".voice-input"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cfg, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(cfg, "CONFIG_FILE", str(data_dir / "config.json"))
    monkeypatch.setattr(cfg, "DICTIONARY_FILE", str(data_dir / "dictionary.json"))
    monkeypatch.setattr(cfg, "HISTORY_FILE", str(data_dir / "history.json"))
    monkeypatch.setattr(cfg, "STATS_FILE", str(data_dir / "stats.json"))
    monkeypatch.setattr(cfg, "SMART_REPLACE_FILE", str(data_dir / "smart_replace.json"))
    monkeypatch.setattr(cfg, "AUDIT_LOG_FILE", str(data_dir / "audit.log"))

    # event_ledger 也吃 ~/.voice-input/events.jsonl
    try:
        import event_ledger as el
        monkeypatch.setattr(el, "EVENTS_FILE", str(data_dir / "events.jsonl"))
    except ImportError:
        pass

    return data_dir


@pytest.fixture
def mock_config():
    """A minimal, in-memory config dict（不寫檔，給 Transcriber 直接用）。"""
    return {
        "enable_fewshot": True,
        "fewshot_count": 3,
        "fewshot_min_input_chars": 8,
        "enable_voice_commands": True,
        "enable_app_awareness": False,
        "enable_filler_removal": True,
        "enable_claude_polish": False,  # 測試裡預設關掉避免摸雲端
        "enable_hybrid_mode": False,
        "active_scene": "general",
        "filler_words": {
            "zh": ["嗯", "啊", "那個", "就是", "然後"],
            "ja": ["えーと", "あの"],
            "en": ["um", "uh", "like"],
        },
        "claude_system_prompt": "",
        "custom_words": [],
        "llm_engine": "claude",
        "anthropic_api_key": "",
        "openai_api_key": "",
        "groq_api_key": "",
        "openrouter_api_key": "",
        "llm_timeout_sec": 5.0,
        "stt_timeout_base_sec": 15.0,
        "stt_timeout_factor": 0.5,
        "stt_timeout_max_sec": 90.0,
    }


@pytest.fixture
def empty_memory(isolated_data_dir, monkeypatch):
    """Memory 實體（dictionary / history 都是空的）。"""
    # 確保 import 順序：config 已經被 patch
    import importlib
    import memory as mem_mod
    importlib.reload(mem_mod)
    m = mem_mod.Memory()
    # Memory.__init__ 會呼叫 cleanup_bad_corrections；空字典時無作用
    return m


@pytest.fixture
def populated_memory(isolated_data_dir):
    """Memory with sample history + corrections（給 few-shot / update_history 測試用）。"""
    import importlib
    import memory as mem_mod
    importlib.reload(mem_mod)
    m = mem_mod.Memory()
    # 樣本 history：3 筆有 raw≠final 隱性正例，2 筆是 edited=True 明示正例
    m.history = [
        {
            "timestamp": "2026-01-01T10:00:00",
            "whisper_raw": "今天天氣很好我們去散步",
            "final_text": "今天天氣很好，我們去散步。",
            "mode": "dictate",
        },
        {
            "timestamp": "2026-01-02T10:00:00",
            "whisper_raw": "cloud code 真的很強",
            "final_text": "Claude Code 真的很強。",
            "mode": "dictate",
            "edited": True,
        },
        {
            "timestamp": "2026-01-03T10:00:00",
            "whisper_raw": "shorty",  # < 12 字（min_chars=12）會被 filter 掉
            "final_text": "Shorty.",
            "mode": "dictate",
        },
        {
            "timestamp": "2026-01-04T10:00:00",
            "whisper_raw": "我在使用 ultra vox 整合 twilio",
            "final_text": "我在使用 Ultravox 整合 Twilio。",
            "mode": "dictate",
            "edited": True,
        },
    ]
    return m


@pytest.fixture
def mock_transcriber(mock_config, populated_memory, monkeypatch):
    """Transcriber 實體，所有外部依賴已 mock。"""
    # 避免 import-time 依賴（voiceprint / ollama_detector 可能拉 numpy 大物件）
    import transcriber as tr_mod

    # patch 掉建構子內會初始化的外部 IO
    monkeypatch.setattr(tr_mod, "VoiceprintManager", lambda *a, **kw: MagicMock(is_enrolled=False))
    monkeypatch.setattr(tr_mod, "get_detector", lambda: MagicMock())

    t = tr_mod.Transcriber(mock_config, populated_memory)
    return t
