"""macOS medical edition adapters: clipboard only, no global shortcuts, no network."""
import subprocess

import pytest

import mac_medical_launcher as mac


def test_copy_uses_pbcopy_with_utf8(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append((a, k)))
    assert mac.MacNative().copy_text("血圧 148/92") is True
    (args,), kwargs = calls[0]
    assert args == ["/usr/bin/pbcopy"] and kwargs["input"] == "血圧 148/92".encode("utf-8")
    assert kwargs["env"]["LANG"] == "en_US.UTF-8" and kwargs["check"] is True
    with pytest.raises(ValueError):
        mac.MacNative().copy_text("")


def test_no_typing_into_other_apps_and_no_shortcuts():
    native = mac.MacNative()
    assert native.capture_target() is None
    assert native.send_text(None, "text").success is False
    with pytest.raises(RuntimeError):
        mac.NoHotkeys(on_toggle=None).start("Ctrl+Alt+F9", "Ctrl+Alt+F10")


def test_settings_are_separate_from_the_personal_mac_app(monkeypatch):
    monkeypatch.delenv("SGHVOICE_DATA_DIR", raising=False)
    monkeypatch.setattr(mac.sys, "platform", "linux")
    assert mac.main(["-psn_0_12345"]) == 2  # Finder argument ignored; non-macOS refused
    assert mac.os.environ["SGHVOICE_DATA_DIR"].endswith("Application Support/SGHVoice Medical")
    assert ".voice-input" not in mac.os.environ["SGHVOICE_DATA_DIR"]


def test_bundle_base_on_macos_app(monkeypatch, tmp_path):
    from windows_client import models
    exe = tmp_path / "SGH Voice Medical.app" / "Contents" / "MacOS" / "SGH Voice"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setattr(models.sys, "frozen", True, raising=False)
    monkeypatch.setattr(models.sys, "executable", str(exe))
    monkeypatch.setattr(models.sys, "platform", "darwin")
    assert models.bundle_base() == (tmp_path / "SGH Voice Medical.app" / "Contents" / "Resources").resolve()
    monkeypatch.setattr(models.sys, "platform", "win32")
    assert models.bundle_base() == exe.parent.resolve()
