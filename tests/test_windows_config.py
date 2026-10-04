"""Windows persistence contracts, using temporary profiles and an in-memory vault."""

import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import types

import pytest


class WinVaultKeyring:
    __module__ = "keyring.backends.Windows"

    def __init__(self):
        self.values = {}
        self.fail_writes = False

    def get_password(self, service, account):
        return self.values.get((service, account))

    def set_password(self, service, account, password):
        if self.fail_writes:
            raise RuntimeError("vault unavailable")
        self.values[(service, account)] = password

    def delete_password(self, service, account):
        self.values.pop((service, account), None)


@pytest.fixture
def windows_config(tmp_path, monkeypatch):
    """Import a separate config module without touching the real home or vault."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))
    monkeypatch.delenv("SGHVOICE_DATA_DIR", raising=False)
    monkeypatch.setattr(
        os, "symlink",
        lambda *_args, **_kwargs: pytest.fail("Windows must not create a symlink"),
    )
    vault = WinVaultKeyring()
    keyring = types.ModuleType("keyring")
    keyring.get_keyring = lambda: vault
    keyring.get_password = vault.get_password
    keyring.set_password = vault.set_password
    keyring.delete_password = vault.delete_password
    errors = types.ModuleType("keyring.errors")
    errors.NoKeyringError = RuntimeError
    keyring.errors = errors
    monkeypatch.setitem(sys.modules, "keyring", keyring)
    monkeypatch.setitem(sys.modules, "keyring.errors", errors)
    spec = importlib.util.spec_from_file_location(
        "_isolated_windows_config", Path(__file__).resolve().parents[1] / "config.py"
    )
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg, vault


def test_windows_bootstrap_uses_local_app_data(windows_config, tmp_path):
    cfg, _ = windows_config
    expected = tmp_path / "local-app-data" / "SGHVoice"
    assert Path(cfg.DATA_DIR) == expected
    assert expected.is_dir()
    assert Path(cfg.CONFIG_FILE).parent == expected
    assert not expected.is_symlink()


def test_windows_missing_local_app_data_uses_user_profile(windows_config, monkeypatch, tmp_path):
    cfg, _ = windows_config
    monkeypatch.delenv("LOCALAPPDATA")
    monkeypatch.setattr(cfg.os.path, "expanduser", lambda _value: str(tmp_path / "profile"))
    assert cfg._default_data_dir() == str(tmp_path / "profile" / "AppData" / "Local" / "SGHVoice")


@pytest.mark.parametrize("windows", [True, False])
def test_explicit_profile_override_bypasses_all_legacy_bootstrap(
    windows_config, monkeypatch, tmp_path, windows
):
    cfg, _ = windows_config
    expected = tmp_path / "isolated-self-test"
    monkeypatch.setattr(cfg, "_IS_WINDOWS", windows)
    monkeypatch.setenv("SGHVOICE_DATA_DIR", str(expected))
    cfg._ensure_data_dir()
    assert cfg._default_data_dir() == str(expected)
    assert expected.is_dir()


def test_windows_json_save_works_without_posix_fchmod(windows_config, monkeypatch):
    cfg, _ = windows_config
    monkeypatch.delattr(os, "fchmod", raising=False)
    cfg.save_config({"ui_language": "zh-TW"})
    assert cfg.load_config()["ui_language"] == "zh-TW"
    assert not list(Path(cfg.DATA_DIR).glob("*.tmp"))


def test_windows_key_roundtrip_uses_vault_only(windows_config):
    cfg, vault = windows_config
    credential = "sk-windows-unit-test-credential"
    cfg.save_config({"openai_api_key": credential, "ui_language": "ja"})
    payload = Path(cfg.CONFIG_FILE).read_text(encoding="utf-8")
    assert credential not in payload
    assert json.loads(payload)["openai_api_key"] == ""
    assert vault.get_password(cfg.KEYCHAIN_SERVICE, "openai") == credential
    assert cfg.load_config()["openai_api_key"] == credential


@pytest.mark.parametrize("module_name,class_name", [
    ("keyrings.alt.file", "PlaintextKeyring"),
    ("keyring.backends.null", "Keyring"),
    ("keyring.backends.chainer", "ChainerBackend"),
    ("keyring.backends.Windows", "UnknownBackend"),
])
def test_windows_rejects_non_native_vault(windows_config, monkeypatch, module_name, class_name):
    cfg, _ = windows_config
    backend = type(class_name, (), {"__module__": module_name})()
    monkeypatch.setattr(sys.modules["keyring"], "get_keyring", lambda: backend)
    assert not cfg._keychain_available()
    with pytest.raises(cfg.ConfigSaveError, match="plaintext"):
        cfg.save_config({"groq_api_key": "gsk-unit-test-credential"})
    assert not Path(cfg.CONFIG_FILE).exists()


def test_windows_vault_unavailable_still_saves_nonsecret_settings(windows_config, monkeypatch):
    cfg, _ = windows_config
    monkeypatch.setattr(cfg, "_keychain_available", lambda: False)
    cfg.save_config({"ui_language": "en", "openai_api_key": "sk-...masked"})
    disk = json.loads(Path(cfg.CONFIG_FILE).read_text(encoding="utf-8"))
    assert disk["ui_language"] == "en"
    assert all(disk[key] == "" for key in cfg.KEYCHAIN_KEYS)


def test_windows_vault_write_failure_preserves_existing_config(windows_config):
    cfg, vault = windows_config
    cfg.save_config({"openai_api_key": "sk-original-test-key"})
    original = Path(cfg.CONFIG_FILE).read_bytes()
    vault.fail_writes = True
    with pytest.raises(cfg.ConfigSaveError, match="Windows Credential Manager"):
        cfg.save_config({"openai_api_key": "sk-replacement-test-key"})
    assert Path(cfg.CONFIG_FILE).read_bytes() == original
    assert vault.get_password(cfg.KEYCHAIN_SERVICE, "openai") == "sk-original-test-key"


def test_windows_imported_current_schema_key_migrates_to_vault(windows_config):
    cfg, vault = windows_config
    credential = "sk-imported-test-credential"
    Path(cfg.CONFIG_FILE).write_text(json.dumps({
        "config_version": cfg.CONFIG_VERSION,
        "openai_api_key": credential,
    }), encoding="utf-8")
    assert cfg.load_config()["openai_api_key"] == credential
    assert vault.get_password(cfg.KEYCHAIN_SERVICE, "openai") == credential
    assert credential not in Path(cfg.CONFIG_FILE).read_text(encoding="utf-8")


def test_windows_imported_key_fails_closed_without_vault(windows_config, monkeypatch):
    cfg, _ = windows_config
    original = json.dumps({"openai_api_key": "sk-imported-test-key"})
    Path(cfg.CONFIG_FILE).write_text(original, encoding="utf-8")
    monkeypatch.setattr(cfg, "_keychain_available", lambda: False)
    with pytest.raises(cfg.ConfigSaveError, match="plaintext persistence is disabled"):
        cfg.load_config()
    assert Path(cfg.CONFIG_FILE).read_text(encoding="utf-8") == original


def test_windows_settings_survive_reload_and_reject_wrong_types(windows_config):
    cfg, _ = windows_config
    settings = {
        "windows_cloud_consent": True,
        "windows_provider": "openai",
        "windows_polish": False,
        "windows_save_history": False,
        "windows_auto_insert": True,
        "windows_toggle_hotkey": "ctrl+shift+f9",
        "windows_cancel_hotkey": "ctrl+shift+f10",
    }
    cfg.save_config(settings)
    loaded = cfg.load_config()
    assert {field: loaded[field] for field in settings} == settings
    assert cfg._sanitize_saved_config({"windows_cloud_consent": "true"}) == {}
    with pytest.raises(cfg.ConfigValidationError):
        cfg.validate_config_update({"windows_secret_unknown": True})
