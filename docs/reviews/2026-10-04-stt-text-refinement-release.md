# Dictation cleanup: macOS 2.7.5 / Android 2.8.8

## Behavior and scope

Unpunctuated short desktop dictations now reach text refinement, including retries. Explicit Ollama selection works with Hybrid disabled. The shared dictation contract requests natural punctuation and paragraphing, bounded hesitation/stutter removal, and no invented ellipses or missing words. Model output remains inert dictated content, not instructions to execute.

Desktop content validation preserves ordered substantive wording after confirmed dictionary/script normalization and bounded disfluency comparison. Android comparison now accepts narrowly defined hesitation/restart cleanup while preserving lexical terms such as 呃逆, meaningful chronology, medical negation/doses, identifiers, and intentional ellipsis placement. Local fallback preserves paragraph breaks and uses conservative standalone hesitation removal. Disabled, unavailable, or rejected AI output retains source content; these paths do not claim to infer arbitrary sentence punctuation.

Synthetic mocked examples:

| Source | Accepted refinement |
| --- | --- |
| 明天我會回覆 | 明天我會回覆。 |
| um I, I think we should wait | I think we should wait. |
| 我想…呃，我明天回覆 | 我想…我明天回覆。 |
| 嗯，啊，我我今天先檢查 GitHub Actions，然後，呃，然後再跑測試。 | 我今天先檢查 GitHub Actions，然後再跑測試。 |

Single ambiguous 然後/like/あの and meaningful repetition are preserved conservatively. The model still chooses punctuation; returning an unchanged unpunctuated source can pass validation. Mocked tests establish routing and validation behavior, not live model accuracy.

## Artifacts

- Android package `com.shingihou.sghvoice`, version **2.8.8**, versionCode **38**.
- Public APK: `sgh-voice-web/downloads/SGHVoice-Android-v2.8.8.apk`, **17,583,696 bytes**.
- APK SHA-256: `a392f44e948961e7092922efca2c04816d88deb555b49aa056a2b1eb5c0c276b`.
- APK v2 signature, one signer, existing certificate SHA-256 `ABAC2DCDA0D728A3C15870E294B26AB1F45274225DD251672EC2A197DE82EDDB`; non-debuggable and no debug preview Activity.
- macOS **2.7.5**, Apple Silicon arm64, **ad-hoc signed, unnotarized test prerelease**. No available Developer ID Application identity or configured notary profile was found. This is not represented as a Gatekeeper-approved production release.
- DMG: `SGH.Voice-2.7.5-apple-silicon.dmg`, **155,011,516 bytes**.
- DMG SHA-256: `19fc8565964979d6558075889ad32a8bba18b6c44370f2d538228a8a22c68233`.
- The read-only mounted DMG app passed deep/strict signature verification and version/architecture checks. Its packaged cleanup/transcriber code was compared to the source without executing the app.

Builds used existing locked Python dependencies, Android SDK/Gradle caches, and signing material. No model downloads, paid provider requests, new credentials, application installation, or security-setting bypass were used. Source was built before the release commit; no commit SHA is claimed as embedded artifact metadata.

## Release safeguards

The macOS version gate now reads canonical `config.APP_VERSION`, verifies the app's shared version reference and dynamic dashboard badge, and explicitly checks the packaged cleanup helper. A staging-copy signature gate checks the exact app entering the DMG; Finder metadata on an exposed build directory does not establish the downloaded artifact's signature status.

Android release metadata, version assertions, and three-language update copy agree with the signed APK. Old APK URLs and the actual 2.8.7 UI preview remain unchanged. The macOS stable website entry remains 2.6.0; this test DMG is delivered separately as a prerelease. Registration, Play opt-in behavior, Firebase rules, providers, pricing, and Windows/iOS code are unchanged.

The user explicitly authorized integration, Git push, the existing release workflow, and downloadable artifacts. Work is isolated from the original checkout's uncommitted `build.sh` and old untracked APKs. Main is refreshed before a normal fast-forward push; no force push is used. Existing CI must finish successfully before the existing Firebase workflow deploys the exact tested main commit. Publication is verified separately by remote SHA, terminal workflow results, and downloaded artifact hashes.

## Verification boundaries

The full desktop suite passed **631 tests**; Android passed **431 tests** across 52 suites, with no failures/errors/skips. Android `lintRelease assembleRelease` and `testDebugUnitTest lintDebug assembleDebug` completed successfully using cached dependencies offline. Release lint has 0 errors and 82 warnings; debug lint has 0 errors and 100 warnings. The artifact-only RC gate, 32 website/release Python checks, 9 JavaScript recruitment/i18n tests, 14 macOS release-contract tests, release-critical Ruff checks, and whitespace checks passed. Independent review found no introduced blockers. Tests use synthetic text and mocked providers, including Traditional Chinese, Japanese, English/mixed language, literal/ellipsis protection, negation/dose preservation, and local/cloud/STT-only routing.

Physical-device microphone/keyboard behavior, actual provider accuracy, Gatekeeper approval/notarization, and application installation are not claimed. Final CI URLs and public HTTP/hash verification belong to the post-publication delivery report; a successful push alone is not release verification.
