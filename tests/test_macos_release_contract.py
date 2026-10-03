"""Static release-safety contract for the macOS packaging entrypoint."""

from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "build.sh"
PUBLISH_SCRIPT = ROOT / "scripts" / "publish_macos_release.sh"
PYINSTALLER_SPEC = ROOT / "voiceinput.spec"


def _script() -> str:
    return BUILD_SCRIPT.read_text(encoding="utf-8")


def test_build_help_documents_local_and_release_modes():
    result = subprocess.run(
        ["bash", str(BUILD_SCRIPT), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--release" in result.stdout
    assert "NOTARY_KEYCHAIN_PROFILE" in result.stdout


def test_build_does_not_mutate_sources_or_install_dependencies():
    script = _script()

    assert "sed -i" not in script
    assert "pip install" not in script


def test_preflight_uses_canonical_version_with_dynamic_dashboard(tmp_path, monkeypatch):
    """Exercise the real version gate with harmless, offline packaging stubs."""
    script = tmp_path / "build.sh"
    script.write_text(_script())
    (tmp_path / "config.py").write_text('APP_VERSION = "2.7.5"\n')
    (tmp_path / "app.py").write_text('        self.version = APP_VERSION\n')
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "index.html").write_text('<span id="app-version"></span>\n')
    (tmp_path / "requirements-dev.lock").touch()
    venv = tmp_path / "venv"
    binaries = venv / "bin"
    binaries.mkdir(parents=True)
    (binaries / "activate").write_text(f'export PATH="{binaries}:$PATH"\n')
    for name, output in {
        "python": "3.12", "pyinstaller": "6.19.0", "pyi-archive_viewer": "",
        "hdiutil": "", "codesign": "", "ditto": "", "shasum": "", "security": "",
    }.items():
        command = binaries / name
        command.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\n")
        command.chmod(0o700)
    monkeypatch.setenv("SGH_BUILD_VENV", str(venv))
    monkeypatch.delenv("CODE_SIGN_IDENTITY", raising=False)
    result = subprocess.run(
        ["bash", str(script), "--version", "2.7.5", "--preflight"],
        cwd=tmp_path, env=os.environ.copy(), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Preflight 完成" in result.stdout
    assert not (tmp_path / "dist").exists()
    mismatch = subprocess.run(
        ["bash", str(script), "--version", "2.7.6", "--preflight"],
        cwd=tmp_path, env=os.environ.copy(), capture_output=True, text=True,
    )
    assert mismatch.returncode != 0
    assert "config.py APP_VERSION" in mismatch.stderr


def test_build_requires_the_locked_python_minor_version():
    script = _script()

    assert "SGH_BUILD_VENV" in script
    assert "3.12" in script
    assert "requirements-dev.lock" in script


def test_build_braces_variables_adjacent_to_cjk_punctuation():
    """Newer Bash versions may treat non-ASCII identifier characters as part
    of an unbraced expansion.  Release diagnostics must remain executable
    under `set -u` in a UTF-8 locale."""
    script = _script()

    assert "${PYTHON_MINOR}（" in script
    assert "${BUILD_VENV}）" in script
    assert "$PYTHON_MINOR（" not in script
    assert "$BUILD_VENV）" not in script


def test_release_requires_developer_id_and_secure_timestamp():
    script = _script()

    assert "Developer ID Application:" in script
    assert "--timestamp=none" not in script
    assert "--options runtime --timestamp" in script
    assert "release_require_developer_id" in script


def test_release_is_notarized_stapled_and_gatekeeper_verified():
    script = _script()

    assert "xcrun notarytool submit" in script
    assert "--keychain-profile" in script
    assert "xcrun stapler staple" in script
    assert "xcrun stapler validate" in script
    assert "spctl --assess" in script


def test_download_staging_copy_is_verified_before_image_creation():
    script = _script()
    verification = 'codesign --verify --deep --strict --verbose=1 "$DMG_STAGE/${APP_NAME}.app"'
    assert verification in script
    assert script.index(verification) < script.index("hdiutil create")


def test_packaged_runtime_modules_are_explicitly_gated():
    script = _script()

    assert "pyi-archive_viewer" in script
    assert "REQUIRED_PYTHON_MODULES" in script
    assert "translation" in script
    assert "medical_dictionary" in script
    assert "dictation_cleanup" in script
    assert "mlx_whisper" in script
    assert "mlx_audio" in script
    assert "mlx_audio.stt.models.qwen3_asr.qwen3_asr" in script
    assert "mlx.core" in script
    assert 'grep -Eq "^[[:space:]]*${required_module}$" <<< "$ARCHIVE_LIST"' in script


def test_pyinstaller_includes_medical_seed_and_qwen_runtime():
    spec = PYINSTALLER_SPEC.read_text(encoding="utf-8")

    assert "('medical_dictionary_seed', 'medical_dictionary_seed')" in spec
    assert "'medical_dictionary'" in spec
    assert "'dictation_cleanup'" in spec
    assert "'mlx_audio'" in spec
    assert "'mlx_audio.stt'" in spec
    assert "'mlx_audio.stt.models.qwen3_asr.qwen3_asr'" in spec


def test_build_validates_packaged_medical_seed_contents():
    script = _script()

    assert "MEDICAL_SEED_DIR" in script
    assert "EXPECTED_MEDICAL_SEED_BUNDLES=3" in script
    assert "EXPECTED_MEDICAL_SEED_TERMS=39" in script


def test_locked_runtime_declares_local_whisper_for_apple_silicon():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    constraints = (ROOT / "constraints.txt").read_text(encoding="utf-8")

    assert "mlx-whisper" in requirements
    assert "mlx-whisper==" in constraints
    assert "mlx==" in constraints


def test_build_never_overwrites_an_existing_remote_release_asset():
    script = _script()

    assert "--clobber" not in script
    assert "gh release upload" not in script


def test_publish_is_a_separate_approval_gated_immutable_step():
    script = PUBLISH_SCRIPT.read_text(encoding="utf-8")

    assert "--execute" in script
    assert "gh release create" not in script
    assert "--clobber" not in script
    assert "existing remote asset" in script
    assert "gh release upload" in script
    assert "isDraft" in script
    assert "git ls-remote --tags origin" in script
    assert "remote tag" in script.lower()
