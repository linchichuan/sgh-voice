"""
tests/test_keychain_migration.py — Keychain integration & migration tests

Run: pytest tests/test_keychain_migration.py -v

Each test isolates state with:
  - a temp DATA_DIR (monkeypatched on the config module)
  - an in-memory fake keyring backend (monkeypatched onto keyring.set_keyring)
"""
import json
import os
import sys

import pytest


# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ─── Fake keyring backend ────────────────────────────────────

from keyring.backend import KeyringBackend


class _InMemoryKeyring(KeyringBackend):
    """Pretend to be a working keyring backend (passes _keychain_available check)."""
    priority = 1  # type: ignore[assignment]

    def __init__(self):
        super().__init__()
        self._store = {}

    def get_password(self, service, account):
        return self._store.get((service, account))

    def set_password(self, service, account, password):
        self._store[(service, account)] = password

    def delete_password(self, service, account):
        if (service, account) in self._store:
            del self._store[(service, account)]
        else:
            from keyring.errors import PasswordDeleteError
            raise PasswordDeleteError(f"no such entry: {account}")


def _install_fake_keyring():
    import keyring
    fake = _InMemoryKeyring()
    keyring.set_keyring(fake)
    return fake


def _install_failing_keyring():
    """Use keyring.backends.fail.Keyring so _keychain_available returns False."""
    import keyring
    from keyring.backends import fail
    keyring.set_keyring(fail.Keyring())


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Each test gets a fresh temp DATA_DIR with no config.json yet."""
    import config as cfg_mod

    data_dir = tmp_path / "voice-input-test"
    data_dir.mkdir()
    config_file = data_dir / "config.json"

    monkeypatch.setattr(cfg_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", str(config_file))
    # Reset the one-shot warn flag so each test logs independently
    monkeypatch.setattr(cfg_mod, "_keychain_warned", False, raising=False)

    return cfg_mod, str(config_file)


@pytest.fixture
def fake_keychain():
    """Install in-memory keyring, yield, then leave it (next test fixture will replace)."""
    return _install_fake_keyring()


@pytest.fixture
def no_keychain():
    """Install the fail backend → _keychain_available returns False."""
    _install_failing_keyring()
    yield


# ─── Tests ───────────────────────────────────────────────────

def test_fresh_install_no_config(isolated_config, fake_keychain):
    """No config.json + Keychain available → defaults, no keys, no crash."""
    cfg_mod, _ = isolated_config
    config = cfg_mod.load_config()
    assert config["anthropic_api_key"] == ""
    assert config["openai_api_key"] == ""
    assert config["config_version"] == cfg_mod.CONFIG_VERSION


def test_legacy_config_migrates_to_keychain(isolated_config, fake_keychain):
    """Legacy config.json with plaintext keys + keyring available → migrates correctly."""
    cfg_mod, config_file = isolated_config

    # Pre-seed legacy config (no config_version, plaintext keys)
    legacy = {
        "anthropic_api_key": "sk-ant-abc123def456ghi789jkl",
        "openai_api_key": "sk-proj-realkeyvalue1234567890",
        "groq_api_key": "gsk_fakegroqkey1234567890",
        "openrouter_api_key": "",
        "elevenlabs_api_key": "",
        "claude_model": "claude-haiku-4-5-20251001",
    }
    with open(config_file, "w") as f:
        json.dump(legacy, f)

    config = cfg_mod.load_config()

    # Keys should still be accessible via the returned dict (de-masked from Keychain)
    assert config["anthropic_api_key"] == "sk-ant-abc123def456ghi789jkl"
    assert config["openai_api_key"] == "sk-proj-realkeyvalue1234567890"
    assert config["groq_api_key"] == "gsk_fakegroqkey1234567890"
    assert config["config_version"] == cfg_mod.CONFIG_VERSION == 5

    # And they should be GONE from config.json on disk
    with open(config_file) as f:
        disk = json.load(f)
    assert disk["anthropic_api_key"] == ""
    assert disk["openai_api_key"] == ""
    assert disk["groq_api_key"] == ""
    assert disk["config_version"] == cfg_mod.CONFIG_VERSION == 5

    # And they should be in the fake keychain
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "anthropic") == "sk-ant-abc123def456ghi789jkl"
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "openai") == "sk-proj-realkeyvalue1234567890"
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "groq") == "gsk_fakegroqkey1234567890"


def test_migration_is_idempotent(isolated_config, fake_keychain):
    """Running load_config twice on legacy → second run is a no-op."""
    cfg_mod, config_file = isolated_config
    legacy = {
        "anthropic_api_key": "sk-ant-aaaaaaaaaaaaaaaaaaaa",
    }
    with open(config_file, "w") as f:
        json.dump(legacy, f)

    cfg1 = cfg_mod.load_config()
    assert cfg1["anthropic_api_key"] == "sk-ant-aaaaaaaaaaaaaaaaaaaa"
    cfg2 = cfg_mod.load_config()
    assert cfg2["anthropic_api_key"] == "sk-ant-aaaaaaaaaaaaaaaaaaaa"
    assert cfg2["config_version"] == cfg_mod.CONFIG_VERSION == 5


def test_legacy_config_without_keyring_fallback(isolated_config, no_keychain):
    """Legacy config + no keyring → fallback works, no crash, keys stay in JSON."""
    cfg_mod, config_file = isolated_config
    legacy = {
        "anthropic_api_key": "sk-ant-fallback-key-1234567890",
        "openai_api_key": "sk-fallback-openai-1234567890",
    }
    with open(config_file, "w") as f:
        json.dump(legacy, f)

    config = cfg_mod.load_config()
    # Still readable
    assert config["anthropic_api_key"] == "sk-ant-fallback-key-1234567890"
    assert config["openai_api_key"] == "sk-fallback-openai-1234567890"

    # Should still be in JSON (no Keychain to move to). config_version stays < 3 because
    # Keychain migration is gated on availability.
    with open(config_file) as f:
        disk = json.load(f)
    assert disk["anthropic_api_key"] == "sk-ant-fallback-key-1234567890"


def test_save_config_with_masked_key_preserves_keychain(isolated_config, fake_keychain):
    """save_config with masked key value (sk-ant-...xxxx) → Keychain value untouched."""
    cfg_mod, _ = isolated_config

    # Pre-set a key in Keychain via initial save
    cfg_mod.save_config({"anthropic_api_key": "sk-ant-real-key-abc1234567890"})
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "anthropic") == "sk-ant-real-key-abc1234567890"

    # Now "save" again with the masked placeholder (mimics Dashboard GET→edit→POST round-trip)
    cfg_mod.save_config({
        "anthropic_api_key": "sk-ant-...7890",  # masked
        "claude_model": "claude-haiku-4-5-20251001",
    })

    # Keychain value should be unchanged
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "anthropic") == "sk-ant-real-key-abc1234567890"


def test_save_config_writes_new_key_to_keychain_not_json(isolated_config, fake_keychain):
    """save_config with fresh key → goes to Keychain, JSON stays clean."""
    cfg_mod, config_file = isolated_config

    cfg_mod.save_config({
        "anthropic_api_key": "sk-ant-brand-new-key-1234567890",
        "claude_model": "claude-haiku-4-5-20251001",
    })

    # Keychain has it
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "anthropic") == "sk-ant-brand-new-key-1234567890"
    # JSON does NOT have it
    with open(config_file) as f:
        disk = json.load(f)
    assert disk["anthropic_api_key"] == ""
    assert disk["claude_model"] == "claude-haiku-4-5-20251001"


def test_save_config_fails_closed_when_keychain_rejects_new_value(
    isolated_config, fake_keychain, monkeypatch
):
    """A stale Keychain value must never make a rejected replacement look saved."""
    cfg_mod, config_file = isolated_config
    old_value = "sk-ant-existing-key-1234567890"
    cfg_mod.save_config({"anthropic_api_key": old_value, "language": "ja"})
    with open(config_file) as handle:
        disk_before = json.load(handle)

    monkeypatch.setattr(cfg_mod, "_keychain_set", lambda key, value: False)
    with pytest.raises(cfg_mod.ConfigSaveError, match="anthropic_api_key"):
        cfg_mod.save_config(
            {
                "anthropic_api_key": "sk-ant-replacement-key-1234567890",
                "language": "en",
            }
        )

    assert (
        fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "anthropic")
        == old_value
    )
    with open(config_file) as handle:
        assert json.load(handle) == disk_before


def test_save_config_empty_string_skipped(isolated_config, fake_keychain):
    """save_config with empty-string key → Keychain value preserved (empty = unchanged)."""
    cfg_mod, _ = isolated_config
    cfg_mod.save_config({"openai_api_key": "sk-existing-openai-key-1234567890"})
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "openai") == "sk-existing-openai-key-1234567890"

    # Saving with empty string should NOT clear it (matches existing Dashboard semantics)
    cfg_mod.save_config({"openai_api_key": "", "claude_model": "claude-haiku-4-5-20251001"})
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "openai") == "sk-existing-openai-key-1234567890"


def test_keychain_delete_helper(isolated_config, fake_keychain):
    """_keychain_delete removes the entry."""
    cfg_mod, _ = isolated_config
    cfg_mod._keychain_set("groq_api_key", "gsk_to-be-deleted-1234567890")
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "groq") == "gsk_to-be-deleted-1234567890"

    assert cfg_mod._keychain_delete("groq_api_key") is True
    assert fake_keychain.get_password(cfg_mod.KEYCHAIN_SERVICE, "groq") is None


def test_keychain_unavailable_helpers_return_none(isolated_config, no_keychain):
    """When keyring is the fail backend, _keychain_get returns None gracefully."""
    cfg_mod, _ = isolated_config
    assert cfg_mod._keychain_get("anthropic_api_key") is None
    # set / delete return False, do not raise
    assert cfg_mod._keychain_set("anthropic_api_key", "sk-ant-whatever") is False
    assert cfg_mod._keychain_delete("anthropic_api_key") is False


def test_non_keychain_config_unchanged_on_save(isolated_config, fake_keychain):
    """Non-API-key fields write to JSON normally."""
    cfg_mod, config_file = isolated_config
    cfg_mod.save_config({
        "anthropic_api_key": "sk-ant-secret-1234567890",
        "claude_model": "custom-model",
        "language": "ja",
        "active_scene": "medical",
    })
    with open(config_file) as f:
        disk = json.load(f)
    assert disk["claude_model"] == "custom-model"
    assert disk["language"] == "ja"
    assert disk["active_scene"] == "medical"
    # And API key still NOT in JSON
    assert disk["anthropic_api_key"] == ""
