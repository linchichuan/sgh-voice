"""Tests for config.py — schema migration, save/load roundtrip, SCENE_PRESETS shape."""
import json
import os
import platform
import stat

import pytest


def test_load_config_returns_default_with_version(isolated_data_dir, monkeypatch):
    """初次載入（無 config.json）→ 包含 DEFAULT_CONFIG + 當前 CONFIG_VERSION。"""
    import config as cfg
    loaded = cfg.load_config()
    assert loaded.get("config_version") == cfg.CONFIG_VERSION
    # 抽幾個 default 欄位驗證
    assert "openai_api_key" in loaded
    assert "claude_model" in loaded
    assert loaded.get("enable_fewshot") is False  # v2.4.0 預設關
    assert loaded.get("enable_app_awareness") is False  # v2.4.0 預設關


def test_save_config_persists_version(isolated_data_dir):
    """save_config 寫入 config.json，read back 含 config_version。"""
    import config as cfg
    cfg.save_config({"openai_api_key": "test-key"})
    with open(cfg.CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    assert raw.get("config_version") == cfg.CONFIG_VERSION
    assert raw.get("openai_api_key") == "test-key"


def test_migrate_config_v1_to_v2_fixes_qwen_models(isolated_data_dir):
    """_migrate_config: v1 schema 有壞 qwen 模型名 → 自動修正。"""
    import config as cfg
    legacy = {
        "local_llm_model": "qwen3.5:latest",
        "openrouter_model": "qwen/qwen3.6-plus",
        # 沒有 config_version → 視為 v1
    }
    migrated, did = cfg._migrate_config(legacy)
    assert did is True
    assert migrated["local_llm_model"] == "qwen3:latest"
    assert migrated["openrouter_model"] == "qwen/qwen3-30b-a3b:free"
    assert migrated["config_version"] == 2


def test_migrate_config_is_idempotent_on_v2(isolated_data_dir):
    """已經是 v2 → _migrate_config 應該 no-op（did_migrate=False）。"""
    import config as cfg
    already_v2 = {
        "config_version": 2,
        "local_llm_model": "qwen3:latest",
    }
    migrated, did = cfg._migrate_config(already_v2)
    assert did is False
    assert migrated["local_llm_model"] == "qwen3:latest"


def test_save_config_sets_0600_permissions(isolated_data_dir):
    """save_config 強制 config.json 為 0600（含 API key 安全）。Unix-only。"""
    if platform.system() == "Windows":
        pytest.skip("POSIX 權限不適用 Windows")
    import config as cfg
    cfg.save_config({"anthropic_api_key": "sk-secret"})
    mode = stat.S_IMODE(os.stat(cfg.CONFIG_FILE).st_mode)
    # 應該只有 owner read/write（0o600）
    assert mode & 0o077 == 0, f"config.json mode {oct(mode)} 給了其他人權限"


def test_scene_presets_medical_has_required_keys():
    """SCENE_PRESETS['medical'] 應該有 custom_words / corrections / system_prompt_extra。"""
    import config as cfg
    med = cfg.SCENE_PRESETS.get("medical")
    assert med is not None
    assert "custom_words" in med and isinstance(med["custom_words"], list)
    assert "corrections" in med and isinstance(med["corrections"], dict)
    assert "system_prompt_extra" in med
    # custom_words 應該非空（醫療場景至少要塞一些詞）
    assert len(med["custom_words"]) > 0
