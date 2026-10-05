# Windows 2.7.6: local recognition and optional OpenAI transcription

The 2.7.5 installer published on 2026-10-04 only supports local recognition.
These changes require a new 2.7.6 installer; editing the website does not add
cloud support to an existing installation. Build and release evidence belongs
to the exact new source commit and installer digest.

## User choices

Local recognition is the default. It uses the prepared Whisper base model on
the computer's CPU, requires no API key and incurs no speech API charge.
The explicit first-time model download is approximately 148 MB. Recognition
does not upload recordings or transcripts, and errors never trigger cloud
fallback. The Windows application is provided free of charge.

The optional cloud choice is **OpenAI / whisper-1** only. The user supplies their
own API key and confirms the data route before using it. API service charges
are separate from the free Windows application and depend on the user's
provider account. The application does not create or fund an API account.

Cloud mode sends the recorded WAV, selected speech language and model name
directly over HTTPS to `https://api.openai.com/v1/audio/transcriptions` with the
user's key. It does not send transcript history, local term candidates or a
cleanup prompt. There is no LLM rewriting or cross-provider fallback. The key
is saved through Windows Credential Manager; plaintext fallback is refused.

The interface displays the selected mode. Cloud consent is reset on each
application launch and revoked when the recognition mode changes. Saving
settings and choosing Record are explicit actions. Missing consent or a key
prevents cloud recording. Switching to cloud does not require a local model.

The cloud adapter uses the existing pinned `httpx` package. It has a fixed
endpoint/model, TLS verification, no redirects, no environment proxy routing,
no automatic retries, bounded request/response sizes and connection/read/write
timeouts. A read timeout is an inactivity limit, not a total request deadline.
Only the application's PCM16,
mono, 16 kHz WAV format is accepted, with a three-minute recording limit and
an upload-size check below the provider's 25 MB limit. Errors use short codes;
provider responses and credentials are not copied into logs or UI errors.

Cancel prevents further result delivery, history writing or insertion. An
already transmitted request cannot be recalled and may still be billed by the
provider. Recordings are temporary and removed after processing or cancellation.
Transcript history and automatic insertion remain off by default.

Review the transcript before use; professional work needs the user's review.
This is not a claim of clinical certification or a blanket liability waiver.

## Verification boundaries

Automated cloud tests use generated non-sensitive WAV fixtures, fake keys and
`httpx.MockTransport`. The frozen Windows self-test also exercises the cloud
adapter without making a real API request. Local CPU inference retains its
separate synthetic-silence test with a Python socket guard.

No owner credential is inspected, configured or sent by the development task.
No real paid API call or patient recording is used. Live cloud transcription
and physical Windows microphone/target-input checks remain separate acceptance
steps, performed by the owner with their own account and non-sensitive audio.
An unsigned test installer does not establish those checks as complete.

## Provider references checked 2026-10-05

- [OpenAI transcription API: endpoint, model and multipart fields](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create)
- [Speech-to-text: supported formats and upload limits](https://developers.openai.com/api/docs/guides/speech-to-text)
- [OpenAI API pricing](https://openai.com/api/pricing/)
- [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data)

Provider processing and retention follow that service's current terms and
account settings. The application does not promise a particular region,
retention arrangement, zero-cost allowance or exemption from those terms.
