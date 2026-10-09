# macOS SOAP safety review — 2026-10-09

## Verdict

Local safety repair completed; **clinical production acceptance is not complete**.
SOAP remains an opt-in scene, now an **extractive draft requiring clinician review**.
No SOAP output is automatically pasted into the active application. No real patient
data, live microphone recording, paid provider request, signing key, or production
EHR was used during this review.

## Confirmed defect and red evidence

Baseline: integration checkout based on origin/main `b73c364`, not the older dirty
source checkout. SOAP used the generic `edit` adapter validator, which deliberately
permits rewriting. Eleven new synthetic pipeline tests failed before the repair:

- `5mg → 50mg`, `沒有藥物過敏 → 有藥物過敏`, changed drug, BP, diagnosis and frequency
  were returned as pasteable final text.
- Disabling polishing silently returned plain transcription as a successful SOAP result.
- Personal substitutions ran before SOAP; a spoken rewrite command could bypass
  the SOAP scene; retry did not retain a separate clinical safety contract.

Reproduction command (same Python environment as the existing packaging tooling):

```sh
/Volumes/Satechi_SSD/voice-input/source/venv-build312/bin/python -m pytest tests/test_medical_soap_safety.py -q
```

Initial result: **11 failed** on the real transcription orchestration with mocked
STT/provider responses. These are synthetic regression tests, not clinical quality evidence.

## Repair

- `medical_soap.py` checks the four exact `[S]`, `[O]`, `[A]`, `[P]` sections and
  requires the complete multiset of literal source sentences exactly once. Changes
  to wording, names, doses, signs, negation, omissions or additions fail closed.
  This does **not** establish correct S/O/A/P classification or correct STT.
- SOAP bypasses personal replacement, smart-replace and final OpenCC rewriting.
  It does not normalize clinical terms, Japanese spelling, numbers or units.
- A valid extractive result is retained in local History with an explicit
  `SOAP 草稿：需醫師逐項核對原始逐字稿` notice and `soap_status=review_required`.
  The returned `final` is always empty and `error=medical_soap_review_required`.
- A rejected/unavailable result retains the original transcription, not the unsafe
  model draft; `error=medical_soap_failed`. Polishing off follows the same boundary.
- Main, retry, continuous recording and CLI report an explicit SOAP status instead
  of claiming translation failure or silently appearing to succeed.
- Retry pins the SOAP flag even if the selected scene is later changed.
- History storage failure is reported honestly (`source_recoverable=false`);
  the last-STT cache remains in memory but is not a durable backup.
- Editing a clinical draft does not call dictionary learning. It records
  `medical_review_edited=true`, not the general `edited=true` training signal, so
  existing few-shot and legacy verified-history promotion do not learn from it.

## User workflow

Settings → Advanced → scene `看診紀錄（SOAP摘錄草稿・需醫師核對）` → record →
open History → expand the record → compare the original transcription and draft →
clinician corrects/classifies the content → manually copy only the reviewed content.
The visible warning is intentional. Editing History is not an approval workflow
and does not remove the warning or turn on automatic insertion.

## Tests

**35 SOAP tests passed**, covering changed clinical facts, Japanese/English source,
empty sections, duplicate/missing sentences, invalid headers, initial and retry
paths, scene changes, replacement bypass, history storage failure, history edits,
few-shot exclusion and actual App main/retry/continuous paste boundaries.

The initial repair passed **244 targeted Python tests** across:

```text
test_medical_soap_safety.py test_v250_optimizations.py
test_transcriber_validators.py test_transcriber_few_shot.py
test_transcriber_voice_command.py test_translation.py
test_translation_regression_corpus.py test_verified_promotion.py
test_paste_idempotency.py test_app_notifications.py test_hotkey_config.py
test_macos_release_contract.py test_memory.py
```

`git diff --check` passed. The older SOAP regression still verifies the edit route
and cached mode, but now explicitly expects its changed/omitted clinical text to
be rejected rather than asserting automatic paste success. Ordinary dictate,
general edit/email and translation expectations were not weakened.

## Mac update and distribution boundary

Read-only version check: installed `/Applications/SGH Voice.app` reports **2.6.0**;
the old source checkout's `dist/SGH Voice.app` reports **2.7.4**. Neither artifact
contains this patch. Parent integration is preparing **2.7.6** from newer main.

Formal release requires the existing `build.sh --release` gates: locked Python
3.12 environment, matching source version, clean tagged tree, Developer ID
Application identity, configured notary Keychain profile, secure timestamp,
notarization, stapling and Gatekeeper verification. Parent's read-only checks found
no Developer ID identity and no configured notary profile. Therefore a new artifact
can at most be explicitly labeled a local/test preview until those gates pass.
This review did not build, sign, install or publish a Mac artifact, and provides no
instructions to bypass Gatekeeper.

## Remaining limits

- This is not clinical decision support or EHR integration. SOAP classification,
  ambiguous speakers, omissions already present in STT and clinical correctness
  require clinician review. No claim of APPI/DPA or clinical certification.
- Exact extraction intentionally refuses normal paraphrases, abbreviation expansion,
  numerical normalization and summarization. Unpunctuated source may remain one
  long excerpt. English full stops are not split to avoid decimal/abbreviation damage.
- Existing cloud STT/LLM routing is unchanged; the patch adds no provider or upload
  path. Actual patient use still requires separate provider/data-processing consent,
  retention/access review and organizational approval. Only synthetic tests ran.
- No live provider or physical-device acceptance was performed. A test DMG is not
  a notarized production release; final artifact provenance is the parent release task.

## Changed files owned by this review

`medical_soap.py`, `transcriber.py`, `config.py` (SOAP scene only), `app.py`,
`dashboard.py` (clinical learning exclusion), `memory.py` (clinical edit flag),
`tests/test_medical_soap_safety.py`, `tests/test_v250_optimizations.py` (SOAP case),
and this report. Version/build/spec/release actions are owned by the parent task.

## Independent-review follow-up

Independent review found two remaining P1 defects. Both were reproduced before
the follow-up patch with `-k 'clipboard_observer or unpunctuated_middle'`:
**5 failed / 2 passed**. The two passing controls were ordinary dictate and
continuous clipboard learning, which must retain their existing behavior.

1. The actual clipboard observer still called dictionary learning on edited SOAP
   drafts. It now excludes the medical mode/pipeline before reading clipboard
   text, updating history or calling learning. Tests drive a real observer-loop
   iteration with a fake clipboard/thread; no real clipboard is read.
2. The original match-based sentence tokenizer skipped unpunctuated intermediate
   lines. Invented `改用藥物 50mg 每日兩次` or an omitted no-allergy line could
   disappear from comparison. It now splits at newlines/sentence boundaries,
   so every non-whitespace character participates, including standalone punctuation.

The expanded targeted regression set passed **252 tests in 5.58 seconds**; Python
compilation and `git diff --check` also passed. The first artifact
built before these follow-up repairs must not be distributed; the parent release
task must rebuild and verify that the packaged modules contain both fixes.
