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
        r'<a\b[^>]*\shref="/downloads/SGHVoice-Android-v2\.7\.2\.apk"',
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


def test_firestore_download_records_are_create_only():
    rules = read_web_file("firestore.rules")
    block_start = rules.index("match /sgh-voice-downloads/{docId}")
    block = rules[block_start:]

    assert "allow create:" in block
    assert "request.resource.data.keys().hasOnly" in block
    assert "request.resource.data.createdAt == request.time" in block
    assert "request.resource.data.consentVersion == 2" in block
    assert "request.resource.data.riskAcknowledged is bool" in block
    assert "SGHVoice-Android-v2.7.2.apk" in block
    assert "allow read, update, delete: if false;" in block


def test_privacy_policy_discloses_download_registration_in_all_languages():
    privacy = read_web_file("privacy.html")

    assert "2.5 ウェブサイトでのダウンロード登録" in privacy
    assert "2.5 網站下載登記" in privacy
    assert "2.5 Website Download Registration" in privacy


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

    assert sitemap.count("<lastmod>2026-08-24</lastmod>") == 3


def test_android_test_build_notice_preserves_platform_security_controls():
    html = read_web_file("index.html")
    translations = read_web_file("i18n.js")
    terms = read_web_file("terms.html")

    assert "尚未經 Google Play 審核或認證" in html
    assert "請勿關閉 Google Play Protect" in html
    assert "悪意のあるアプリとして検出された場合" in translations
    assert "Stop the installation if Android identifies the file as malicious" in translations
    assert "責任範圍依第 6 條辦理" in terms


def test_no_personalization_copy_distinguishes_learning_from_cloud_voice():
    translations = read_web_file("i18n.js")

    assert "密碼欄位會停用語音與學習；禁止個人化欄位只停用學習" in translations
    assert "パスワード欄では音声入力と学習を無効にし、パーソナライズ禁止欄では学習だけを無効にします" in translations
    assert "Password fields disable voice and learning; no-personalization fields disable learning only" in translations


def test_registration_copy_does_not_claim_access_control():
    html = read_web_file("index.html")
    translations = read_web_file("i18n.js")

    assert "此登記不是下載檔案的存取控制" in html
    assert "この登録はファイルへのアクセス制御ではありません" in translations
    assert "This registration is not access control for the public release files" in translations


def test_generated_feature_images_are_not_presented_as_verified_release_screenshots():
    html = read_web_file("index.html")
    translations = read_web_file("i18n.js")

    assert "android-translate-v270.webp" not in html
    assert "android-zhuyin-v250.webp" not in html
    assert "android-translation-ui.webp" in html
    assert "android-zhuyin-ui.webp" in html
    for unsupported_claim in (
        "ACTUAL ANDROID BUILD",
        "これが v2.7.2 の実画面です",
        "這就是 v2.7.2 的實際鍵盤",
        "This is the actual v2.7.2 keyboard",
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
    assert "2026年8月24日" in privacy
    assert "2026 年 8 月 24 日" in privacy
    assert "August 24, 2026" in privacy
    assert "requires 30-day data retention" in privacy
    assert "platform.claude.com/docs/en/manage-claude/api-and-data-retention" in privacy
    assert "2026年8月24日" in preflight


def test_android_release_manifest_matches_public_artifact_and_copy():
    release = json.loads(read_web_file("downloads/android-release.json"))
    artifact = WEB_ROOT / "downloads" / release["fileName"]
    index = read_web_file("index.html")
    llms = read_web_file("llms.txt")

    assert release["versionName"] == "2.7.2"
    assert release["versionCode"] == 22
    assert re.fullmatch(r"[0-9a-f]{64}", release["sha256"])
    assert re.fullmatch(r"[0-9A-F]{64}", release["certificateSha256"])
    assert artifact.is_file()
    assert artifact.stat().st_size == release["sizeBytes"]
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == release["sha256"]
    assert release["fileName"] in index
    assert release["sha256"] in index
    assert f'{release["versionName"]} ({release["versionCode"]})' in index
    assert release["fileName"] in llms
    assert release["sha256"] in llms
