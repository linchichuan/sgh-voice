# Android 2.8.9 / macOS 2.7.6 release review

## Source and scope

- Integrates the Android work on current main `b73c364`, preserving its 2.8.8
  cleanup and Windows/platform website changes. Android integration: `5a0d48e`.
- The original dirty checkout's unrelated `build.sh` and old untracked APKs were
  left intact. No Google Play track, price, payment account or tester list changed.
- Android: 2.8.9 / versionCode 39, existing sideload channel only.
- Mac: 2.7.6 Apple Silicon **test prerelease**, not a notarized public release.

## Android changes

- Removes the pressed recording oval outline; retains soft audio-driven waves.
- Enlarges Zhuyin candidates, preserves remaining syllables after head selection,
  and provides bounded same-editor reselection without learning an immediate undo.
- Adds local emoji; allows direct kana confirmation; adds 45,371 English words
  and 32,005 Japanese candidates with bundled source/license attribution.
- Improves same-editor recording reconnection and recording-only screen-on handling.
- Long unpunctuated successful AI results may trigger at most one punctuation-only
  retry. It checks consent/cancellation, exact lexical content and existing guards.
  The additional request may incur provider cost; its transport has a 12 s deadline.
- This is not a claim of physical-device or real-provider accuracy acceptance.

## Verified local release artifact

- File: `sgh-voice-web/downloads/SGHVoice-Android-v2.8.9.apk`
- Bytes: `17891267` (17.9 MB decimal).
- SHA-256: `210c827807eec52432cb2108b8e88c568b5e7c9a5f32ebd413dadf75c725c504`.
- Package: `com.shingihou.sghvoice`; min SDK 26, target SDK 36; not debuggable.
- APK v2 signature, exactly one signer, same existing release certificate:
  `ABAC2DCDA0D728A3C15870E294B26AB1F45274225DD251672EC2A197DE82EDDB`.
- Built through the existing Keychain-backed release helper; no credentials exported
  to source, reports or web assets. `verify_mobile_rc.sh --artifact-only` passed.

## Validation

- Android: **485 tests passed**, no failures/errors/skips; Debug and Release lint
  and signed `assembleRelease` passed. Existing deprecation warnings remain.
- Offline dictionary generator: **7 tests passed**.
- Python: **666 tests passed**, including **35 SOAP safety tests**; release-critical
  Ruff and `git diff --check` passed.
- Firestore emulator registration rules: **19 tests passed**. Language-navigation
  regression: **4 tests passed**. Production dependency audit: zero vulnerabilities.
- Browser: homepage and update page, zh/ja/en at 320/390/1280 px (18 combinations),
  no horizontal overflow or broken images. Fixed query-language loss during navigation.
  Screenshots are in local `output/playwright/`, not committed.
- iOS repository-owned source/metadata preflight passed; no iOS release or upload.
- Actual device install, microphone, editor interoperability, overnight recording,
  live paid AI, and clinical acceptance were **not performed**.

## Mac SOAP boundary

See `2026-10-09-macos-soap-review.md`. Exact-source extraction is held in History
for clinician review; no SOAP auto-paste. Independent review additionally caught
unpunctuated-line omission and clipboard-learning bypass; both reproduced red,
were fixed, and are now regression-tested. The pre-repair trial bundle is not the
release artifact; the final test DMG must be rebuilt after these fixes.

No Developer ID Application identity or notary profile was available. Mac 2.6.0
remains the separately listed public release. The 2.7.6 download is explicitly a
test prerelease; it must not be called Apple-notarized or clinically validated.

## Publication contract

- Publish only a fast-forward main commit; CI must pass for that exact SHA before
  the existing Firebase workflow deploys. This document records local verification,
  not a future deployment result; verify workflow results and public bytes afterward.
- Public recruitment remains application → invitation → Google Play opt-in.
  The owner sideload update never counts toward 12 testers and never starts automatically.
- Expected Android update page: `https://voice.shingihou.com/android-update.html?lang=zh`.
- Verify full HTTP GET hash/size and Range support after Firebase deployment.
- Mac release notes must include its final DMG checksum and signing limitations.
