import hashlib
import json
import re
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1] / "sgh-voice-web"


def read_web_file(name: str) -> str:
    return (WEB_ROOT / name).read_text(encoding="utf-8")


def test_download_links_start_locked_behind_registration():
    html = read_web_file("index.html")

    assert 'id="downloadRegistrationForm"' in html
    assert 'id="downloadName"' in html
    assert 'id="downloadEmail"' in html
    assert 'id="downloadPrivacyConsent"' in html
    assert 'id="apkDownloadButton"' in html
    assert 'id="macDownloadButton"' in html
    assert html.count('download-button disabled') == 2
    assert not re.search(
        r'<a\b[^>]*\shref="/downloads/SGHVoice-Android-v2\.7\.3\.apk"',
        html,
    )
    assert not re.search(
        r'<a\b[^>]*\shref="https://github\.com/linchichuan/sgh-voice/releases/download/v2\.6\.0/',
        html,
    )


def test_download_starts_only_after_firestore_registration():
    javascript = read_web_file("main.js")

    save_position = javascript.index("await firestore.addDoc")
    download_position = javascript.rindex("startFileDownload(button)")

    assert '"sgh-voice-downloads"' in javascript
    assert save_position < download_position
    assert 'translate("download.registration.error"' in javascript
    assert "consentVersion: 2" in javascript
    assert "riskAcknowledged:" in javascript


def test_hosting_does_not_publish_release_tooling_or_emulator_logs():
    hosting = json.loads(read_web_file("firebase.json"))["hosting"]
    assert {"**/*.log", "tests/**", "package*.json", "**/node_modules/**"} <= set(hosting["ignore"])
    assert "downloads/SGHVoice-Android-v2.8.1.apk" in hosting["ignore"]  # Superseded before Firebase release.
    manifest_header = next(
        header for header in hosting["headers"]
        if header["source"] == "/downloads/android-release.json"
    )
    assert "no-cache" in manifest_header["headers"][0]["value"]


def test_privacy_discloses_memory_only_retry_and_explicit_writing():
    privacy = read_web_file("privacy.html")
    for disclosure in ("最大約125秒", "最多約 125 秒", "125 seconds",
                       "筆記與成稿不寫入歷史檔", "There is no automatic resend"):
        assert disclosure in privacy


def test_firestore_download_records_are_create_only():
    rules = read_web_file("firestore.rules")
    block_start = rules.index("match /sgh-voice-downloads/{docId}")
    block = rules[block_start:]

    assert "allow create:" in block
    assert "request.resource.data.keys().hasOnly" in block
    assert "request.resource.data.createdAt == request.time" in block
    assert "request.resource.data.consentVersion == 2" in block
    assert "request.resource.data.riskAcknowledged is bool" in block
    assert "request.resource.data.platform == 'macos'" in block
    assert "SGHVoice-Android" not in block
    assert "allow read, update, delete: if false;" in block


def test_privacy_policy_discloses_download_registration_in_all_languages():
    privacy = read_web_file("privacy.html")

    assert "2.5 Android テスト申請と macOS ダウンロード登録" in privacy
    assert "2.5 Android 測試申請與 macOS 下載登記" in privacy
    assert "2.5 Android Test Applications and macOS Download Registration" in privacy


def test_legal_pages_publish_canonical_and_language_alternates():
    sitemap = read_web_file("sitemap.xml")

    for page in ("privacy.html", "terms.html"):
        html = read_web_file(page)
        canonical = f"https://voice.shingihou.com/{page}"

        assert f'<link rel="canonical" href="{canonical}">' in html
        assert f'hreflang="ja" href="{canonical}?lang=ja"' in html
        assert f'hreflang="zh-Hant" href="{canonical}?lang=zh"' in html
        assert f'hreflang="en" href="{canonical}?lang=en"' in html
        assert f'<loc>{canonical}</loc>' in sitemap
        assert f'hreflang="x-default" href="{canonical}"' in sitemap

    assert sitemap.count("<lastmod>2026-10-03</lastmod>") == 1
    assert sitemap.count("<lastmod>2026-09-26</lastmod>") == 1
    assert sitemap.count("<lastmod>2026-08-30</lastmod>") == 1


def test_android_recruitment_does_not_offer_sideload_as_play_testing():
    html = read_web_file("index.html")
    translations = read_web_file("i18n.js")
    terms = read_web_file("terms.html")

    assert "封閉" in html and "14" in html
    assert "Google Play" in translations
    assert not re.search(r'(?:href|data-download-href)="[^"]*\.apk"', html)
    assert "責任範圍依第 6 條辦理" in terms


def test_no_personalization_copy_distinguishes_learning_from_cloud_voice():
    translations = read_web_file("i18n.js")

    assert "密碼欄位會停用語音與學習；禁止個人化欄位只停用學習" in translations
    assert "パスワード欄では音声入力と学習を無効にし、パーソナライズ禁止欄では学習だけを無効にします" in translations
    assert "Password fields disable voice and learning; no-personalization fields disable learning only" in translations


def test_registration_copy_does_not_claim_invitation_or_eligibility():
    html = read_web_file("index.html")
    translations = read_web_file("i18n.js")

    assert "目前沒有自動寄信" in html
    assert "download.android.success" in translations
    assert "Google Play のテスト資格はまだ付与されておらず" in translations
    assert "status: \"pending\"" in read_web_file("main.js")


def test_feature_illustration_is_not_presented_as_a_verified_release_screenshot():
    html = read_web_file("index.html")
    translations = read_web_file("i18n.js")

    assert "android-translate-v270.webp" not in html
    assert "android-zhuyin-v250.webp" not in html
    assert "android-translation-ui.webp" not in html
    assert "android-zhuyin-ui.webp" not in html
    assert "2.8.10 介面預覽 · 非實機收音驗證" in html
    assert "2.8.10 UI preview · not a real-device recording test" in translations
    assert 'assets/generated/android-2.8.10-voice.png' in html
    for unsupported_claim in (
        "ACTUAL ANDROID BUILD",
        "これが v2.8.2 の実画面です",
        "這就是 v2.8.2 的實際鍵盤",
        "This is the actual v2.8.2 keyboard",
        "これが v2.8.3 の実画面です",
        "這就是 v2.8.3 的實際鍵盤",
        "This is the actual v2.8.3 keyboard",
    ):
        assert unsupported_claim not in html
        assert unsupported_claim not in translations


def test_privacy_discloses_android_cloud_processing_in_all_languages():
    privacy = read_web_file("privacy.html")

    assert "Android版でも、プリセット語彙、ユーザーが追加した語彙および選択中のシーンに関するプロンプト" in privacy
    assert "Android 版也會將預載詞彙、使用者新增詞彙及所選場景提示" in privacy
    assert "The Android version also sends built-in vocabulary, user-added vocabulary, and the selected scene prompt" in privacy


def test_privacy_discloses_current_anthropic_model_specific_retention_terms():
    privacy = read_web_file("privacy.html")
    preflight = (
        WEB_ROOT.parent / "scripts" / "verify_ios_app_store_preflight.sh"
    ).read_text(encoding="utf-8")

    assert "Claude Fable 5" in privacy
    assert "Claude Fable 5" in preflight
    assert "2026年9月11日" in privacy
    assert "2026 年 9 月 11 日" in privacy
    assert "September 11, 2026" in privacy
    assert "requires 30-day data retention" in privacy
    assert "platform.claude.com/docs/en/manage-claude/api-and-data-retention" in privacy
    assert "2026年9月11日" in preflight


def test_android_release_manifest_matches_public_artifact_and_copy():
    release = json.loads(read_web_file("downloads/android-release.json"))
    artifact = WEB_ROOT / "downloads" / release["fileName"]
    index = read_web_file("index.html")
    llms = read_web_file("llms.txt")

    assert release["versionName"] == "2.8.10"
    assert release["versionCode"] == 40
    assert re.fullmatch(r"[0-9a-f]{64}", release["sha256"])
    assert re.fullmatch(r"[0-9A-F]{64}", release["certificateSha256"])
    assert artifact.is_file()
    assert artifact.stat().st_size == release["sizeBytes"]
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == release["sha256"]
    # Owner sideload artifacts remain verifiable but are not recruitment CTAs.
    assert release["fileName"] not in index
    assert release["fileName"] not in llms
    assert 'i18n.js?v=20261009-android2810' in index
    assert 'main.js?v=20260930-alpha' in index


def test_sideload_update_is_separate_from_recruitment_and_matches_artifact():
    release = json.loads(read_web_file("downloads/android-release.json"))
    update = read_web_file("android-update.html")
    index = read_web_file("index.html")
    assert 'android-update.html' in index
    assert f'href="/downloads/{release["fileName"]}"' in update
    assert release["versionName"] in update
    assert re.search(r'<meta\s+name="robots"\s+content="noindex[^\"]*"', update)
    assert 'firebase.js' not in update
    assert 'downloadRegistrationForm' not in update
    assert 'Google Play' in update


def test_apk_headers_support_a_real_file_download():
    hosting = json.loads(read_web_file("firebase.json"))["hosting"]
    headers = next(entry["headers"] for entry in hosting["headers"]
                   if entry["source"] == "/downloads/*.apk")
    headers = {header["key"]: header["value"] for header in headers}
    assert headers["Content-Disposition"] == "attachment"
    assert headers["Content-Type"] == "application/vnd.android.package-archive"
    assert headers["X-Content-Type-Options"] == "nosniff"
