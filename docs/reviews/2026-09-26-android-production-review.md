# Android 2.8.1 Production Review

Date: 2026-09-26. Release type: signed, personal sideload test build, not Google Play Production approval.

## Scope and baseline

Reviewed the Android and public-web changes from deployed `da3eb223488ec99c15c371fad024ad56f37160c8` (2.7.9), including the 2.8.0 beta. Standards and user-spec reviews were performed independently, followed by integrated fixes and validation. Pre-existing `build.sh` edits and untracked 2.7.0/2.7.1 APKs are excluded.

## Findings and fixes

| Finding | Fix |
|---|---|
| Consent could be withdrawn during STT while a preserved handoff subsequently started an LLM request | Check consent before STT, after STT, at each follow-up stage and immediately before HTTP dispatch; consent withdrawal cannot become a successful dictation fallback |
| Malformed AI JSON could place a private draft in an exception cause/log | Fixed-classification errors; no raw response/parser cause in Compose, translation or STT errors; IME logs fixed messages |
| A failed editor-switch handoff could erase audio without a terminal status | Single bounded memory-only retry capture, explicit Retry/Discard, visible no-speech/failure/consent result; never auto-insert across editors |
| Generated writing was inserted before review in compatible editors | Always hold the generated draft for preview and explicit insertion; existing notes remain available after generation failure |
| Notes were invisible and clearing was easy to trigger accidentally | Scrollable content preview; two-tap Clear confirmation within four seconds |
| Japanese phone keys inherited QWERTY staggering | Equal 3-column kana grid plus a consistent utility rail and switchable romaji layout |
| Recording surface was too dark | Light mint default with thin outline; six named light palettes saved independently of API keys/consent, visible checkmark selection and minimum text contrast tests |
| Landing page registration fields were oversized and copy repetitive | Compact registration form, concise feature overview and progressive disclosure for detailed explanations |
| Small or landscape windows could clip controls | Bounded middle content area, fixed mode/footer controls, compact landscape arrangement, scroll fallback |
| Translation selection left an empty circular outline | Hide the entire capture area during translation selection |
| Hosting published development files | Exclude logs, tests, package manifests and unrelated untracked APKs; release metadata uses revalidation rather than immutable caching |
| A rules-first deployment could break cached old download pages | Accept only exact new 2.8.1 and previous 2.7.9 version/file tuples; reject mismatches and unconsented registrations |

## Verification

- Android unit regression: 208 tests, zero failures/errors (includes consent, private error payload, retry bounds, writing parser, kana layout and palette contrast). Signed release build passed; debug/release lint have zero errors (99/70 warnings respectively).
- Firestore Emulator: 4 tests passed; no production registration writes used for testing.
- JavaScript syntax, release-critical Ruff, and iOS source-only preflight passed. No iOS upload or provider account activation performed.
- Production npm dependency audit: zero vulnerabilities. Development dependency audit is not represented by this result.
- Python full suite: 537 passed. Immutable artifact gate passed after packaging: version 2.8.1 (31), 17,401,709 bytes, SHA-256 `9d85915609f34d98181a32dfe4141280fde7d6c2fba98060c48915415f0cafa0`; signer SHA-256 matches the previous official sideload release.
- UI validation uses synthetic text/audio-level fixtures only. Portrait, landscape, narrow windows, larger fonts, notes, preview, retry, Zhuyin and Japanese phone layout are checked in an emulator. Website responsive checks do not submit personal data.
- Final light palette selection was exercised in the native picker and visually inspected. The final 72%-height landscape recapture was blocked by an emulator cold-boot failure after a system-server crash; earlier landscape checks do not certify this final adjustment. Final landscape and pending-preview runtime acceptance remain required on the target phone unless later evidence is recorded in the release receipt.
- Website browser checks: all three languages at 320/390/768/1440px have no horizontal overflow; name/email inputs measure exactly 46px high and the form never exceeds 680px. Browser console has zero errors/warnings. Mobile/desktop screenshots were visually inspected; consent and invalid-email download gating were checked without submitting a registration.

## Runtime and privacy boundaries

- No new provider, server relay or telemetry destination. Existing BYOK providers and consent version 3 remain.
- Help me write is a distinct opt-in action: transcribe notes, explicitly generate, preview, explicitly insert. It never sends a message or posts content.
- The microphone stops when the input method loses focus. This release **does not implement continuous background recording**.
- Notes (8,000 characters), pending drafts (12,000 characters) and at most one retry buffer (125 seconds PCM capacity, including a watchdog tail) are memory-only. They are not durable: service/process termination or restart loses them.
- Retry uploads require a fresh explicit user action and current cloud consent. Audio is cleared on completion, discard, detected consent withdrawal, or destruction; there is no automatic replay.
- Password/sensitive fields do not expose draft text or offer voice actions. A result completing after an editor change requires manual insertion.
- Japanese 12-key input uses tap cycling/long-press choice, not flick gestures. Phrase conversion remains Phase 1.

## Physical-device acceptance still required

1. Install over the existing official sideload version, without uninstalling; confirm API keys and vocabulary remain. Google Play installations must use their original channel because the signer may differ.
2. Dictate synthetic mixed-language text including GitHub Actions, CI/CD, git push, numbers and negations; verify no assistant reply is inserted.
3. Record, switch apps/fields, return and explicitly insert; verify no wrong-field automatic insertion. Interrupt the network, retry, discard, and withdraw cloud consent during STT.
4. Use Help me write with several segments; review notes and draft, verify clear confirmation and single insertion.
5. Test portrait/landscape, split screen, larger fonts, Zhuyin candidates and Japanese 12-key/romaji switching in the actual target apps.

The existing 38-case hardware checklist remains pending. Automated/emulator checks authorize a controlled personal test release, not a claim of complete device acceptance or guaranteed transcription accuracy.

## Release provenance

Canonical metadata: `sgh-voice-web/downloads/android-release.json`. Canonical installation page: <https://voice.shingihou.com/#android-download>.

Final commit, GitHub CI/Hosting runs, live APK SHA-256/byte parity and exposed-file 404 checks are recorded after deployment in the workspace `release-output/android-2.8.1/RELEASE_RECEIPT.md`. Prior immutable artifacts are not overwritten.
