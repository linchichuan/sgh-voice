import json
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ANDROID_ROOT = REPO_ROOT / "android" / "SGHVoice"
PUBLIC_APK = (
    REPO_ROOT
    / "sgh-voice-web"
    / "downloads"
    / "SGHVoice-Android-v2.7.2.apk"
)


def test_private_android_signing_material_is_not_tracked():
    tracked = subprocess.run(
        ["git", "ls-files", "--", "android/SGHVoice"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    forbidden = {
        path
        for path in tracked
        if path.endswith((".jks", ".keystore"))
        or Path(path).name == "keystore.properties"
    }
    assert forbidden == set()


def test_release_build_has_no_inline_signing_credentials():
    build_script = (ANDROID_ROOT / "app" / "build.gradle.kts").read_text(
        encoding="utf-8"
    )

    assert not re.search(r"(?:storePassword|keyPassword)\s*=\s*\"", build_script)
    assert "SGH_RELEASE_STORE_PASSWORD" in build_script
    assert "SGH_RELEASE_KEY_PASSWORD" in build_script
    assert "verifyReleaseSigningConfig" in build_script
    assert "KeyStore.getInstance" in build_script
    assert 'MessageDigest.getInstance("SHA-256")' in build_script
    assert "does not match the expected certificate fingerprint" in build_script


def test_public_apk_does_not_package_signing_material():
    with zipfile.ZipFile(PUBLIC_APK) as archive:
        packaged_names = {name.lower() for name in archive.namelist()}

    assert not any(
        name.endswith((".jks", ".keystore", "keystore.properties"))
        for name in packaged_names
    )


def test_mobile_rc_cli_documents_artifact_only_and_partial_modes():
    completed = subprocess.run(
        [str(REPO_ROOT / "scripts" / "verify_mobile_rc.sh"), "--help"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--artifact-only" in completed.stdout
    assert "PARTIAL and exits 3" in completed.stdout


def test_mobile_rc_fingerprint_normalization_is_locale_independent():
    script = (REPO_ROOT / "scripts" / "verify_mobile_rc.sh").read_text(
        encoding="utf-8"
    )

    assert "[^0-9A-Fa-f]" in script
    assert "[:xdigit:]" not in script
    assert "--print-certs-pem" in script
    assert "openssl x509 -outform DER" in script
    assert "certificate SHA-256 digest: //p" not in script


def test_mobile_and_web_localization_keys_remain_in_parity():
    android_resource_roots = [
        ANDROID_ROOT / "app" / "src" / "main" / "res" / folder / "strings.xml"
        for folder in ("values", "values-ja", "values-en")
    ]
    android_keys = [
        {element.attrib["name"] for element in ET.parse(path).getroot()}
        for path in android_resource_roots
    ]
    assert android_keys[0] == android_keys[1] == android_keys[2]

    ios_app = REPO_ROOT / "ios" / "SGHVoice" / "SGHVoice"
    ios_keys = []
    for locale in ("en", "ja", "zh-Hant"):
        contents = (ios_app / f"{locale}.lproj" / "Localizable.strings").read_text(
            encoding="utf-8"
        )
        ios_keys.append(set(re.findall(r'^"([^"]+)"\s*=', contents, re.MULTILINE)))
    assert ios_keys[0] == ios_keys[1] == ios_keys[2]

    web_root = REPO_ROOT / "sgh-voice-web"
    web_i18n = (web_root / "i18n.js").read_text(encoding="utf-8")
    language_starts = {
        language: web_i18n.index(f"    {language}: {{")
        for language in ("ja", "zh", "en")
    }
    language_order = ("ja", "zh", "en")
    web_keys = []
    for index, language in enumerate(language_order):
        start = language_starts[language]
        end = (
            language_starts[language_order[index + 1]]
            if index + 1 < len(language_order)
            else web_i18n.index("\n};", start)
        )
        web_keys.append(
            set(re.findall(r'^\s*"([^"]+)"\s*:', web_i18n[start:end], re.MULTILINE))
        )
    assert web_keys[0] == web_keys[1] == web_keys[2]

    html = (web_root / "index.html").read_text(encoding="utf-8")
    html_keys = set(re.findall(r'data-i18n="([^"]+)"', html))
    assert html_keys <= web_keys[0]


def test_ci_release_gates_are_fail_closed():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "actions/checkout@v7" in workflow
    assert "actions/setup-python@v7" in workflow
    assert "actions/setup-node@v7" in workflow
    assert "android-actions/setup-android@40fd30fb8d7440372e1316f5d1809ec01dcd3699" in workflow
    assert "actions/setup-node@v6" not in workflow
    assert "--require-hashes -r requirements-dev.lock" in workflow
    assert "ruff check . --select E9,F63,F7,F82" in workflow
    assert "|| true" not in workflow
    assert "testDebugUnitTest lintDebug assembleDebug" in workflow
    assert "verify_mobile_rc.sh --artifact-only" in workflow
    assert "verify_ios_app_store_preflight.sh --source-only" in workflow
    assert "npm audit --omit=dev --audit-level=high" in workflow
    assert "npm run test:rules" in workflow


def test_firebase_live_deploy_uses_the_successful_ci_sha_and_deploys_tested_rules():
    workflow = (
        REPO_ROOT / ".github" / "workflows" / "firebase-hosting.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_run:" in workflow
    assert 'workflows: ["CI"]' in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.event == 'push'" in workflow
    assert "github.event.workflow_run.head_branch == 'main'" in workflow
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in workflow
    assert "github.event.workflow_run.head_sha" in workflow
    assert "git rev-parse origin/main" in workflow
    assert "npm run test:rules" in workflow
    assert "firebase deploy --only firestore:rules" in workflow
    assert "FirebaseExtended/action-hosting-deploy@v0.11.0" in workflow
    assert "actions/setup-node@v7" in workflow
    assert "actions/setup-node@v6" not in workflow
    assert workflow.index("npm run test:rules") < workflow.index(
        "firebase deploy --only firestore:rules"
    )
    assert workflow.index("firebase deploy --only firestore:rules") < workflow.index(
        "FirebaseExtended/action-hosting-deploy@v0.11.0"
    )


def test_web_tooling_and_emulator_logs_are_ignored():
    ignore_file = REPO_ROOT / "sgh-voice-web" / ".gitignore"
    contents = ignore_file.read_text(encoding="utf-8")

    assert "/node_modules/" in contents
    assert "firebase-debug.log" in contents
    assert "firestore-debug.log" in contents
    assert "/.firebase/" in contents


def test_privacy_page_remains_compatible_with_macos_runner_tidy():
    """The macOS runner still ships an HTML4-era tidy that reports HTML5
    semantic header/footer elements as hard errors instead of warnings."""
    privacy_html = (REPO_ROOT / "sgh-voice-web" / "privacy.html").read_text(
        encoding="utf-8"
    )

    assert "<header" not in privacy_html
    assert "<footer" not in privacy_html
    assert 'class="legal-header" role="banner"' in privacy_html
    assert 'class="legal-footer" role="contentinfo"' in privacy_html


def test_mobile_rechecks_cloud_consent_at_the_upload_boundary():
    android_ime = (
        ANDROID_ROOT
        / "app"
        / "src"
        / "main"
        / "java"
        / "com"
        / "shingihou"
        / "sghvoice"
        / "ime"
        / "VoiceInputIME.kt"
    ).read_text(encoding="utf-8")
    ios_view_model = (
        REPO_ROOT / "ios" / "SGHVoice" / "SGHVoice" / "UI" / "MainViewModel.swift"
    ).read_text(encoding="utf-8")

    android_boundary = android_ime.index("private fun transcribeAndCommit")
    android_upload = android_ime.index("activePipeline.process", android_boundary)
    android_guard = android_ime.index("hasCloudProcessingConsent", android_boundary)
    assert android_guard < android_upload

    ios_boundary = ios_view_model.index("private func stopActiveRecording")
    ios_upload = ios_view_model.index("pipeline.process", ios_boundary)
    ios_guard = ios_view_model.index("hasCloudProcessingConsent", ios_boundary)
    assert ios_guard < ios_upload


def test_generated_firebase_hosting_cache_is_not_tracked():
    tracked = subprocess.run(
        ["git", "ls-files", "--", "sgh-voice-web/.firebase"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert tracked == []


def test_android_rc_acceptance_tracks_the_next_source_candidate():
    build_script = (ANDROID_ROOT / "app" / "build.gradle.kts").read_text(
        encoding="utf-8"
    )
    public_release = json.loads(
        (
            REPO_ROOT / "sgh-voice-web" / "downloads" / "android-release.json"
        ).read_text(encoding="utf-8")
    )
    acceptance = (REPO_ROOT / "docs" / "ANDROID_RC_ACCEPTANCE.md").read_text(
        encoding="utf-8"
    )

    source_name = re.search(r'versionName\s*=\s*"([^"]+)"', build_script)
    source_code = re.search(r"versionCode\s*=\s*(\d+)", build_script)
    assert source_name is not None
    assert source_code is not None
    assert public_release["versionName"] == "2.7.2"
    assert public_release["versionCode"] == 22
    assert source_name.group(1) == "2.7.3"
    assert int(source_code.group(1)) == 23
    assert int(source_code.group(1)) > public_release["versionCode"]
    assert "Android 2.7.3（versionCode 23）" in acceptance
