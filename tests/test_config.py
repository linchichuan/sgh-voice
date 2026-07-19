"""Tests for config.py — schema migration, save/load roundtrip, SCENE_PRESETS shape."""
import json
import os
import platform
import stat

import pytest


def test_ensure_dir_skips_chmod_when_permissions_are_already_secure(
    monkeypatch, tmp_path
):
    import config as cfg

    data_dir = tmp_path / "voice-data"
    data_dir.mkdir(mode=0o700)
    data_dir.chmod(0o700)
    monkeypatch.setattr(cfg, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        cfg.os,
        "chmod",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("secure directory must not be chmod'ed again")
        ),
    )

    cfg._ensure_dir()


def test_ensure_dir_hardens_insecure_permissions(monkeypatch, tmp_path):
    import config as cfg

    data_dir = tmp_path / "voice-data"
    data_dir.mkdir(mode=0o755)
    data_dir.chmod(0o755)
    real_chmod = os.chmod
    calls = []

    def recording_chmod(path, mode):
        calls.append((path, mode))
        real_chmod(path, mode)

    monkeypatch.setattr(cfg, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(cfg.os, "chmod", recording_chmod)

    cfg._ensure_dir()

    assert calls == [(str(data_dir), 0o700)]
    assert stat.S_IMODE(os.stat(data_dir).st_mode) == 0o700


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
    assert loaded.get("enable_model_warmup") is False  # 降低 idle 記憶體，使用者可手動開啟
    assert loaded.get("continuous_max_pending_segments") == 2


def test_save_config_persists_version(isolated_data_dir):
    """save_config 寫入 config.json，read back 含 config_version。
    注意：API key 欄位會被 Keychain 整合搬走，所以用非敏感欄位 (claude_model) 驗證。"""
    import config as cfg
    cfg.save_config({"claude_model": "test-model-id"})
    with open(cfg.CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    assert raw.get("config_version") == cfg.CONFIG_VERSION
    assert raw.get("claude_model") == "test-model-id"


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


def test_normalize_known_stale_model_ids_without_touching_custom_values():
    import config as cfg

    saved = {
        "config_version": cfg.CONFIG_VERSION,
        "local_whisper_model": "mlx-community/whisper-turbo",
        "openrouter_model": "qwen/qwen3.6-plus-preview:free",
        "groq_model": "user-chosen-model",
    }
    normalized, did = cfg._normalize_known_stale_model_ids(saved)
    assert did is True
    assert normalized["local_whisper_model"] == "whisper-turbo"
    assert normalized["openrouter_model"] == "qwen/qwen3-30b-a3b:free"
    assert normalized["groq_model"] == "user-chosen-model"

    unchanged, did = cfg._normalize_known_stale_model_ids({
        "openrouter_model": "vendor/custom-current-model",
    })
    assert did is False
    assert unchanged["openrouter_model"] == "vendor/custom-current-model"


def test_dashboard_rejects_unknown_stt_language_profile(monkeypatch):
    import dashboard

    monkeypatch.setattr(dashboard, "load_config", lambda: {})
    response = dashboard.app.test_client().post(
        "/api/config", json={"language": "mixed-magic"},
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "invalid_language_profile"


def test_migrate_hotkeys_v5_replaces_only_known_legacy_defaults():
    import config as cfg
    from hotkey_config import (
        RECOMMENDED_ACTION_HOTKEYS,
        RECOMMENDED_RECORD_HOTKEY,
    )

    legacy = {
        "config_version": 3,
        "hotkey": "right_cmd",
        "rewrite_hotkey": "right_option+r",
        "retry_hotkey": "right_option+y",
        "cancel_hotkey": "right_option+x",
        "continuous_hotkey": "right_ctrl+f12",  # Custom: preserve it.
    }

    migrated, did = cfg._migrate_hotkeys_v5(legacy)

    assert did is True
    assert migrated["config_version"] == cfg.CONFIG_VERSION == 5
    assert migrated["hotkey_config_version"] == cfg.HOTKEY_CONFIG_VERSION
    assert migrated["hotkey"] == RECOMMENDED_RECORD_HOTKEY
    assert migrated["rewrite_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["rewrite_hotkey"]
    assert migrated["retry_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["retry_hotkey"]
    assert migrated["cancel_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["cancel_hotkey"]
    assert migrated["continuous_hotkey"] == "right_ctrl+f12"


def test_load_config_persists_v5_hotkey_migration(isolated_data_dir, monkeypatch):
    import config as cfg
    from hotkey_config import (
        RECOMMENDED_ACTION_HOTKEYS,
        RECOMMENDED_RECORD_HOTKEY,
    )

    legacy = {
        "config_version": 3,
        "hotkey": "right_cmd",
        "rewrite_hotkey": "right_option+r",
        "retry_hotkey": "right_option+y",
        "cancel_hotkey": "right_option+x",
    }
    with open(cfg.CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(legacy, handle)
    monkeypatch.setattr(cfg, "_keychain_available", lambda: False)

    loaded = cfg.load_config()

    assert loaded["config_version"] == cfg.CONFIG_VERSION == 5
    assert loaded["hotkey"] == RECOMMENDED_RECORD_HOTKEY
    assert loaded["rewrite_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["rewrite_hotkey"]
    assert loaded["retry_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["retry_hotkey"]
    assert loaded["cancel_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["cancel_hotkey"]
    with open(cfg.CONFIG_FILE, "r", encoding="utf-8") as handle:
        persisted = json.load(handle)
    assert persisted["config_version"] == 5
    assert persisted["hotkey"] == RECOMMENDED_RECORD_HOTKEY


def test_v2_without_keychain_still_migrates_unsafe_hotkeys(
    isolated_data_dir, monkeypatch
):
    import config as cfg
    from hotkey_config import (
        RECOMMENDED_ACTION_HOTKEYS,
        RECOMMENDED_RECORD_HOTKEY,
    )

    legacy = {
        "config_version": 2,
        "hotkey": "right_cmd",
        "rewrite_hotkey": "right_option+r",
        "retry_hotkey": "right_option+y",
        "cancel_hotkey": "right_option+x",
    }
    with open(cfg.CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(legacy, handle)
    monkeypatch.setattr(cfg, "_keychain_available", lambda: False)

    loaded = cfg.load_config()

    # Keep v2 so Keychain migration can retry later, but fix hotkeys now.
    assert loaded["config_version"] == 2
    assert loaded["hotkey_config_version"] == cfg.HOTKEY_CONFIG_VERSION
    assert loaded["hotkey"] == RECOMMENDED_RECORD_HOTKEY
    assert loaded["rewrite_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["rewrite_hotkey"]
    assert loaded["retry_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["retry_hotkey"]
    assert loaded["cancel_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["cancel_hotkey"]


def test_v4_interim_function_keys_migrate_to_modifier_only_chords():
    import config as cfg
    from hotkey_config import (
        INTERIM_V4_ACTION_HOTKEYS,
        RECOMMENDED_ACTION_HOTKEYS,
    )

    interim = {
        "config_version": 4,
        **INTERIM_V4_ACTION_HOTKEYS,
    }

    migrated, did = cfg._migrate_hotkeys_v5(interim)

    assert did is True
    assert migrated["config_version"] == cfg.CONFIG_VERSION == 5
    for field, value in RECOMMENDED_ACTION_HOTKEYS.items():
        if field != "continuous_hotkey":
            assert migrated[field] == value


def test_hotkey_marker_v1_migrates_unavailable_and_same_family_defaults():
    import config as cfg
    from hotkey_config import (
        PREVIOUS_V1_ACTION_HOTKEYS,
        RECOMMENDED_ACTION_HOTKEYS,
        RECOMMENDED_RECORD_HOTKEY,
    )

    candidate = {
        "config_version": cfg.CONFIG_VERSION,
        "hotkey_config_version": 1,
        "hotkey": RECOMMENDED_RECORD_HOTKEY,
        **PREVIOUS_V1_ACTION_HOTKEYS,
        "continuous_hotkey": "",
    }

    migrated, did = cfg._migrate_hotkeys_v5(candidate)

    assert did is True
    assert migrated["hotkey_config_version"] == cfg.HOTKEY_CONFIG_VERSION == 3
    for field, value in RECOMMENDED_ACTION_HOTKEYS.items():
        assert migrated[field] == value


def test_hotkey_marker_v2_moves_cancel_off_ptt_modifier_families():
    import config as cfg
    from hotkey_config import (
        PREVIOUS_V2_ACTION_HOTKEYS,
        RECOMMENDED_ACTION_HOTKEYS,
        RECOMMENDED_RECORD_HOTKEY,
    )

    candidate = {
        "config_version": cfg.CONFIG_VERSION,
        "hotkey_config_version": 2,
        "hotkey": RECOMMENDED_RECORD_HOTKEY,
        **PREVIOUS_V2_ACTION_HOTKEYS,
        "continuous_hotkey": "",
    }

    migrated, did = cfg._migrate_hotkeys_v5(candidate)

    assert did is True
    assert migrated["hotkey_config_version"] == cfg.HOTKEY_CONFIG_VERSION == 3
    assert migrated["cancel_hotkey"] == RECOMMENDED_ACTION_HOTKEYS["cancel_hotkey"]


def test_save_config_preserves_v2_until_keychain_can_retry(isolated_data_dir):
    import config as cfg

    cfg.save_config({"config_version": 2, "claude_model": "test-model"})

    with open(cfg.CONFIG_FILE, "r", encoding="utf-8") as handle:
        persisted = json.load(handle)
    assert persisted["config_version"] == 2
    assert persisted["hotkey_config_version"] == cfg.HOTKEY_CONFIG_VERSION


def test_save_config_sets_0600_permissions(isolated_data_dir):
    """save_config 強制 config.json 為 0600（含 API key 安全）。Unix-only。"""
    if platform.system() == "Windows":
        pytest.skip("POSIX 權限不適用 Windows")
    import config as cfg
    cfg.save_config({"claude_model": "x"})
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


def test_update_stats_tracks_japanese_and_mixed_separately(isolated_data_dir):
    import config as cfg

    cfg.update_stats("来週確認します", 1.0, {"typing_speed_cpm": 50})
    cfg.update_stats("来週 supplier と確認します", 1.0, {"typing_speed_cpm": 50})
    stats = cfg.load_stats()
    assert stats["languages_detected"]["ja"] == 1
    assert stats["languages_detected"]["mixed"] == 1
