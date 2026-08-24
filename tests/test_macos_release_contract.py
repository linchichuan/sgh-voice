"""Static release-safety contract for the macOS packaging entrypoint."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "build.sh"
PUBLISH_SCRIPT = ROOT / "scripts" / "publish_macos_release.sh"


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


def test_build_requires_the_locked_python_minor_version():
    script = _script()

    assert "SGH_BUILD_VENV" in script
    assert "3.12" in script
    assert "requirements-dev.lock" in script


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


def test_packaged_runtime_modules_are_explicitly_gated():
    script = _script()

    assert "pyi-archive_viewer" in script
    assert "REQUIRED_PYTHON_MODULES" in script
    assert "translation" in script
    assert "mlx_whisper" in script
    assert "mlx.core" in script
    assert 'grep -Eq "^[[:space:]]*${required_module}$" <<< "$ARCHIVE_LIST"' in script


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
