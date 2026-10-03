# Android OpenAI transcription contract — 2026-10-03

Status: local implementation and synthetic contract verification. No provider account/key was inspected, no real recording was uploaded, and live accuracy/latency/access have not been verified. Release remains subject to the user's preview approval.

## Official references checked

- [File transcription](https://developers.openai.com/api/docs/guides/speech-to-text): `gpt-transcribe`; multipart `keywords[]`, `languages[]`; `languages` replaces singular `language`; keywords must not contain angle brackets or CR/LF. Whisper's prompt window is 224 tokens.
- [GPT-Transcribe model](https://developers.openai.com/api/docs/models/gpt-transcribe): current file transcription model; listed audio-duration price $0.0045/minute on the verification date. Actual account access and billing were not exercised.
- [OpenAI Whisper implementation](https://github.com/openai/whisper/blob/main/whisper/transcribe.py): context/prompt tail retention motivates placing high-priority vocabulary last. Hosted API tokenization was not reproduced locally.
- [Data controls](https://developers.openai.com/api/docs/guides/your-data): account-specific region and retention controls require separate verification. The application does not assert Japanese processing or zero retention.

## Fit and scope

| Dimension | Decision / limitation |
| --- | --- |
| Role | Selectable primary OpenAI file transcription model; fresh-install default. |
| Language | Auto sends expected `zh`, `ja`, `en`; explicit language sends only that language, including existing Korean selection. |
| Transport | Existing Android BYOK HTTPS adapter, WAV multipart upload, JSON response with string `text`. No provider SDK enters IME UI. |
| Reliability | Existing 30-second connect/read/write timeouts and coroutine cancellation; no application-level retry or on-error provider/model fallback. |
| Cost | One request per attempted transcription; no newly introduced retry amplification. No monetary account cap is enforced by this client. |
| Privacy | Existing local encrypted user credentials and cloud-consent gates retained. No company key embedded in APK, no audio or provider payload logging. |
| Governance | Synthetic tests only. No new medical-data approval, DPA/region/training-use claim, or production-data validation. |
| Rollback | Select `whisper-1`, `gpt-4o-transcribe`, or existing Groq configuration in settings. |

This repository is already a personal BYOK client. This change preserves that user-approved architecture rather than introducing a company credential or a new server proxy. The reusable integration skill's server-only-company-secret pattern therefore does not describe this existing BYOK credential owner. User credentials remain encrypted locally and are sent only to the configured transcription endpoint.

## Model settings and upgrade behavior

- Fresh installations default to `gpt-transcribe`.
- Existing explicit model selections are preserved.
- Previously configured installations with no saved model keep their previous implicit `whisper-1` default.
- **Updating the APK does not silently switch an existing user's Whisper model.** Select `gpt-transcribe` under the OpenAI speech-recognition model setting to try it.
- OpenAI missing-key + configured Groq-key routing retains the pre-existing behavior; the request uses Groq's model and legacy fields. HTTP failures do not trigger an additional provider upload.

## Request contract

All models send `file=recording.wav`, their selected `model`, and `response_format=json`.

| Model/provider | Additional fields |
| --- | --- |
| OpenAI `gpt-transcribe` | Repeated `keywords[]` entries and repeated `languages[]`; no `language`, no dictionary-as-instructions `prompt`. |
| OpenAI Whisper / GPT-4o transcription | Existing spelling-reference `prompt`; explicit singular `language`, omitted for Auto. |
| Groq | Existing spelling-reference `prompt`; explicit singular `language`, omitted for Auto. No OpenAI-only arrays. |

Dictionary selection still prioritizes custom words, confirmed learned words, technical words, scene words, then base words. It selects up to 50 whole terms within the existing 800-character payload bound, then reverses the retained list for the legacy prompt so the most important words occur at its tail. **800 characters is not 224 tokens**, and no exact hosted-tokenizer fit is claimed. On `gpt-transcribe`, the adapter restores priority order and revalidates the spelling list as literal keywords. Invalid/control/instruction-shaped entries are omitted; terms are never split mid-word. This retains the existing per-field personalization gate.

Response handling accepts only a string `text`, closes the response, and returns sanitized HTTP/network errors. Cancellation closes a late response and cancels the underlying call. It does not turn failure into a successful empty transcript.

## Verification

Targeted tests cover priority-tail regression, selection bounds, model defaults/upgrades, multipart fields, mixed/explicit language, invalid keywords, legacy-model compatibility, invalid JSON/text shape, HTTP 400/401/403/404/429/503, timeout, consent, cancellation and existing missing-key Groq routing. Responses and keys in these tests are synthetic; OkHttp interceptors prevent provider network access.

Before implementation, the model availability/default and three vocabulary-tail assertions failed as expected. Test execution results are recorded in the task handoff after the final run. The existing transcription pipeline tests also verify cancellation/consent and refinement fallback independently.

Remaining live acceptance: an approved synthetic speech fixture and separately provisioned development key are required to verify provider access and actual response shape; user audio must then be evaluated with permission before making recognition-quality claims.
