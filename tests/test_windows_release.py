"""Release gates must reject renamed non-PE files and unverified downloads."""
import copy
import importlib.util
import json
from pathlib import Path
import struct

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_windows_release", ROOT / "scripts/verify_windows_release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def write_pe(path, *, machine=0x8664):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HH", data, 132, machine, 1)
    struct.pack_into("<HHH", data, 148, 112, 2, 0x20B if machine == 0x8664 else 0x10B)
    path.write_bytes(data)
    return path


def test_pe_rejects_fake_exe(tmp_path):
    file = tmp_path / "renamed.exe"
    file.write_text("not a Windows binary", encoding="utf-8")
    with pytest.raises(ValueError, match="PE executable"):
        release.verify_pe(file)


def test_installer_allows_x86_bootstrap_but_app_requires_x64(tmp_path):
    file = write_pe(tmp_path / "app.exe", machine=0x14C)
    assert release.verify_pe(file) == 0x14C
    with pytest.raises(ValueError, match="architecture"):
        release.verify_pe(file, app=True)


def test_truncated_pe_fails(tmp_path):
    file = write_pe(tmp_path / "app.exe")
    file.write_bytes(file.read_bytes()[:160])
    with pytest.raises(ValueError, match="Truncated"):
        release.verify_pe(file)


@pytest.fixture
def artifacts(tmp_path):
    version = release.read_version()
    commit = "a" * 40
    installer = write_pe(tmp_path / f"SGHVoice-Windows-{version}-x64-unsigned.exe", machine=0x14C)
    app = write_pe(tmp_path / "SGH Voice.exe")
    info_dir = tmp_path / "_internal"
    info_dir.mkdir()
    (info_dir / "windows-build-info.json").write_text(json.dumps({
        "schemaVersion": 1, "version": version, "sourceCommit": commit,
        "platform": "windows", "architecture": "x64", "signing": "unsigned",
    }), encoding="utf-8")
    smoke = tmp_path / "smoke.json"
    smoke.write_text(json.dumps({
        "ok": True, "platform": "win32", "architecture": "AMD64", "version": version,
        "checks": {key: True for key in ("windows_native", "tk_ui", "wav_roundtrip", "credential_backend", "shared_core", "bundled_model")},
        "errors": [], "microphone_tested": False, "cloud_tested": False, "input_delivery_tested": False, "recognition_mode": "local-only",
        "model_included": True, "local_inference_tested": False,
    }), encoding="utf-8")
    return installer, app, smoke, commit


def test_manifest_binds_exact_source_and_bytes_without_acceptance(artifacts):
    installer, app, smoke, commit = artifacts
    result = release.verify_build(installer, app, smoke, commit)
    assert result["installer"]["sha256"] == release.sha256(installer)
    assert result["sourceCommit"] == commit
    assert result["windowsAcceptance"] == "not-run"
    assert result["published"] is False


def test_wrong_source_commit_fails(artifacts):
    installer, app, smoke, _ = artifacts
    with pytest.raises(ValueError, match="metadata"):
        release.verify_build(installer, app, smoke, "b" * 40)


@pytest.mark.parametrize("patch", [
    {"platform": "darwin"}, {"ok": False}, {"checks": {}},
    {"checks": {"tk": "true"}}, {"errors": ["failed"]}, {"version": "0.0.0"},
    {"checks": {"tk": True}}, {"microphone_tested": True},
])
def test_selftest_rejects_incomplete_or_nonwindows_claims(artifacts, patch):
    _, _, smoke, _ = artifacts
    report = release.read_json(smoke)
    report.update(patch)
    with pytest.raises(ValueError):
        release.verify_smoke(report, release.read_version())


def test_public_gate_requires_exact_acceptance_record(artifacts, tmp_path):
    installer, _, _, commit = artifacts
    (tmp_path / "config.py").write_text(f'APP_VERSION = "{release.read_version()}"\n', encoding="utf-8")
    digest = release.sha256(installer)
    manifest = {
        "schemaVersion": 1, "status": "available", "version": release.read_version(),
        "fileName": installer.name, "sizeBytes": installer.stat().st_size, "sha256": digest,
        "architecture": "x64", "installerScope": "per-machine", "signing": "unsigned",
        "build": {"status": "passed", "platform": "windows", "commit": commit},
        "acceptance": {"status": "passed", "platform": "windows", "sha256": digest,
                       "record": "docs/windows-acceptance-test.md"},
    }
    (tmp_path / "docs").mkdir()
    record = tmp_path / manifest["acceptance"]["record"]
    record.write_text(f"{digest}\n{commit}\n" + "\n".join(
        f"- {name}: PASS" for name in
        ("installation", "microphone", "hotkey", "target-paste", "clipboard-fallback", "privacy", "uninstall")
    ), encoding="utf-8")
    release.verify_public_manifest(manifest, installer, commit, tmp_path)
    stale = copy.deepcopy(manifest)
    stale["acceptance"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="acceptance"):
        release.verify_public_manifest(stale, installer, commit, tmp_path)
    record.write_text(f"{digest}\n{commit}\n- installation: PASS\n", encoding="utf-8")
    with pytest.raises(ValueError, match="microphone"):
        release.verify_public_manifest(manifest, installer, commit, tmp_path)


def test_no_automatic_windows_workflow_or_publication():
    import yaml
    workflow = (ROOT / ".github/workflows/windows-build.yml").read_text(encoding="utf-8")
    parsed = yaml.load(workflow, Loader=yaml.BaseLoader)
    assert set(parsed["on"]) == {"workflow_dispatch"}
    assert "workflow_dispatch:" in workflow
    assert "  push:" not in workflow
    assert "  pull_request:" not in workflow
    assert "runs-on: windows-2022" in workflow
    assert "timeout-minutes: 25" in workflow
    assert "upload-artifact" not in workflow
    assert "windows/install-test.ps1" in workflow
    assert "windows/offline-test.ps1" in workflow
    assert "contents: write" not in workflow
    assert "gh release" not in workflow


def test_installer_is_per_machine_with_bundled_model_and_no_profile_deletion():
    installer = (ROOT / "windows/installer.iss").read_text(encoding="utf-8")
    assert "PrivilegesRequired=admin" in installer
    assert "DefaultDirName={autopf}\\SGHVoice" in installer
    assert 'Source: "{#SourceDir}\\models\\*"; DestDir: "{app}\\models"' in installer
    assert "nocompression" in installer
    assert "[UninstallDelete]" not in installer


def test_smoke_without_bundled_model_is_rejected(artifacts, tmp_path):
    installer, app, smoke, commit = artifacts
    report = json.loads(smoke.read_text(encoding="utf-8"))
    report["model_included"] = False
    smoke.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="bundled"):
        release.verify_build(installer, app, smoke, commit)
