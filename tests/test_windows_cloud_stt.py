"""Cloud adapter contracts with synthetic PCM, dummy keys and no network."""
import io
import socket
import struct
import wave
from email import policy
from email.parser import BytesParser

import httpx
import pytest

from windows_client.cloud_stt import (
    CloudSTTError, CloudTranscriber, ENDPOINT, ENGINE, MAX_AUDIO_BYTES,
    MAX_FRAMES, MAX_RESPONSE_BYTES,
)


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must not open a network connection")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.fixture
def settings():
    return {
        "windows_recognition_mode": "openai-cloud",
        "windows_cloud_consent": True,
        "openai_api_key": "test-synthetic-key",
        "windows_language": "ja",
    }


def make_wav(path, *, channels=1, width=2, rate=16000, frames=160):
    with wave.open(str(path), "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(width)
        target.setframerate(rate)
        target.writeframes(b"\x00" * frames * channels * width)
    return path


@pytest.fixture
def wav(tmp_path):
    return make_wav(tmp_path / "synthetic-no-patient-data.wav")


def parts(request):
    message = BytesParser(policy=policy.default).parsebytes(
        ("Content-Type: " + request.headers["Content-Type"] + "\r\n\r\n").encode()
        + request.read()
    )
    return {part.get_param("name", header="content-disposition"): part
            for part in message.iter_parts()}


def test_fixed_endpoint_multipart_verbatim_and_no_glossary(settings, wav):
    seen = []
    transcript = "  セルトラリン 25 mg。自殺念慮は否定。疑いは残る。\n"
    settings.update(openai_base_url="https://untrusted.invalid", stt_engine="other",
                    llm_engine="anything", windows_lexicon_enabled=True,
                    initial_prompt="NEVER SEND THIS", groq_api_key="never-send")
    def handle(request):
        seen.append(request)
        assert request.method == "POST" and str(request.url) == ENDPOINT
        assert request.headers["Authorization"] == "Bearer test-synthetic-key"
        form = parts(request)
        assert set(form) == {"file", "model", "language", "response_format"}
        assert form["model"].get_payload(decode=True) == b"whisper-1"
        assert form["language"].get_payload(decode=True) == b"ja"
        assert form["response_format"].get_payload(decode=True) == b"json"
        assert form["file"].get_filename() == "recording.wav"
        assert form["file"].get_payload(decode=True) == wav.read_bytes()
        return httpx.Response(200, json={"text": transcript})
    result = CloudTranscriber(settings, transport=httpx.MockTransport(handle)).transcribe(
        {"path": str(wav)}, 0.01, "dictate"
    )
    assert result == {"raw": transcript, "final": transcript, "engine": ENGINE}
    assert len(seen) == 1


def test_metadata_is_never_uploaded(settings, wav):
    original = wav.read_bytes()
    wav.write_bytes(original + b"PRIVATE_METADATA_NOT_AUDIO")
    def handle(request):
        assert parts(request)["file"].get_payload(decode=True) == original
        return httpx.Response(200, json={"text": "synthetic"})
    CloudTranscriber(settings, transport=httpx.MockTransport(handle)).transcribe(wav)


def test_auto_language_omits_language(settings, wav):
    settings["windows_language"] = "auto"
    def handle(request):
        assert set(parts(request)) == {"file", "model", "response_format"}
        return httpx.Response(200, json={"text": "synthetic"})
    CloudTranscriber(settings, transport=httpx.MockTransport(handle)).transcribe(wav)


@pytest.mark.parametrize("consent", [None, False, 0, 1, "true", "false", [], {}])
def test_consent_requires_exact_true(settings, consent):
    settings["windows_cloud_consent"] = consent
    with pytest.raises(CloudSTTError, match="^cloud_consent_required$"):
        CloudTranscriber(settings)


@pytest.mark.parametrize("key", [None, "", 42, " leading", "trailing ", "secret\nheader", "キー", "sk-...", "****"])
def test_invalid_keys_never_build_transport(settings, key):
    settings["openai_api_key"] = key
    with pytest.raises(CloudSTTError, match="^cloud_key_required$"):
        CloudTranscriber(settings)


@pytest.mark.parametrize("mode", [None, "local", "openai", "", "groq"])
def test_explicit_cloud_mode_is_required(settings, mode):
    settings["windows_recognition_mode"] = mode
    with pytest.raises(CloudSTTError, match="^invalid_recognition_mode$"):
        CloudTranscriber(settings)


def test_settings_are_copied_and_language_validated(settings, wav):
    def handle(request):
        assert request.headers["Authorization"] == "Bearer test-synthetic-key"
        return httpx.Response(200, json={"text": "synthetic"})
    transcriber = CloudTranscriber(settings, transport=httpx.MockTransport(handle))
    settings["openai_api_key"] = "changed-after-snapshot"
    settings["windows_cloud_consent"] = False
    assert transcriber.transcribe(wav)["final"] == "synthetic"
    with pytest.raises(CloudSTTError, match="invalid_language"):
        CloudTranscriber({**settings, "windows_cloud_consent": True, "windows_language": "xx"})


@pytest.mark.parametrize("options", [
    {"channels": 2}, {"width": 1}, {"width": 4}, {"rate": 44100},
    {"frames": 0}, {"frames": MAX_FRAMES + 1},
])
def test_invalid_wav_contract_never_sends(settings, tmp_path, options):
    path = make_wav(tmp_path / "invalid.wav", **options)
    seen = []
    transcriber = CloudTranscriber(settings, transport=httpx.MockTransport(lambda request: seen.append(request)))
    with pytest.raises(CloudSTTError, match="^cloud_audio_invalid$"):
        transcriber.transcribe(path)
    assert seen == []


def test_truncated_pcm_and_oversize_file_rejected(settings, wav):
    transcriber = CloudTranscriber(settings)
    valid = wav.read_bytes()
    wav.write_bytes(valid[:-1])
    with pytest.raises(CloudSTTError, match="cloud_audio_invalid"):
        transcriber.transcribe(wav)
    wav.write_bytes(valid[:40] + struct.pack("<I", 3200) + valid[44:])
    with pytest.raises(CloudSTTError, match="cloud_audio_invalid"):
        transcriber.transcribe(wav)
    with wav.open("wb") as stream:
        stream.truncate(MAX_AUDIO_BYTES)
    with pytest.raises(CloudSTTError, match="cloud_audio_invalid"):
        transcriber.transcribe(wav)


@pytest.mark.parametrize("path", ["relative.wav", "https://untrusted.invalid/audio.wav", "//host/share/a.wav", None])
def test_nonlocal_or_missing_audio_rejected(settings, path):
    with pytest.raises(CloudSTTError, match="cloud_audio_invalid"):
        CloudTranscriber(settings).transcribe(path)


def test_client_security_options_and_no_retry(settings, wav, monkeypatch):
    original = httpx.Client
    options, requests = [], []
    def client(**kwargs):
        options.append(kwargs)
        return original(**kwargs)
    monkeypatch.setattr(httpx, "Client", client)
    def handle(request):
        requests.append(request)
        return httpx.Response(503, text="provider-secret-detail")
    with pytest.raises(CloudSTTError, match="^cloud_request_failed$"):
        CloudTranscriber(settings, transport=httpx.MockTransport(handle)).transcribe(wav)
    assert len(requests) == 1 and len(options) == 1
    assert options[0]["verify"] is True
    assert options[0]["trust_env"] is False
    assert options[0]["follow_redirects"] is False
    assert options[0]["timeout"].read == 90


@pytest.mark.parametrize("status,code", [
    (301, "cloud_request_failed"), (307, "cloud_request_failed"),
    (401, "cloud_auth_failed"), (403, "cloud_auth_failed"),
    (429, "cloud_rate_limited"), (500, "cloud_request_failed"),
])
def test_http_errors_are_sanitized_and_redirects_not_followed(settings, wav, status, code, caplog):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(status, text="private-patient-provider-body",
                              headers={"Location": "https://untrusted.invalid/steal"})
    with pytest.raises(CloudSTTError, match=f"^{code}$"):
        CloudTranscriber(settings, transport=httpx.MockTransport(handle)).transcribe(wav)
    assert len(requests) == 1
    assert "private-patient-provider-body" not in caplog.text
    assert settings["openai_api_key"] not in caplog.text


@pytest.mark.parametrize("error,code", [
    (httpx.ReadTimeout("private key and text"), "cloud_timeout"),
    (httpx.ConnectError("private key and text"), "cloud_request_failed"),
    (RuntimeError("private key and text"), "cloud_request_failed"),
])
def test_transport_errors_are_sanitized(settings, wav, error, code):
    attempts = []
    def handle(request):
        attempts.append(request)
        raise error
    with pytest.raises(CloudSTTError, match=f"^{code}$"):
        CloudTranscriber(settings, transport=httpx.MockTransport(handle)).transcribe(wav)
    assert len(attempts) == 1


@pytest.mark.parametrize("body", [b"not-json", b"[]", b"null", b'{}', b'{"text": null}', b'{"text": 123}', b'{"text":" "}', b'{"text":"bad\\u0000text"}', b"x" * (MAX_RESPONSE_BYTES + 1)])
def test_invalid_response_is_not_published(settings, wav, body):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    with pytest.raises(CloudSTTError, match="^cloud_invalid_response$"):
        CloudTranscriber(settings, transport=transport).transcribe(wav)


def test_cancel_before_start_or_after_wav_read_sends_nothing(settings, wav, monkeypatch):
    import windows_client.cloud_stt as cloud
    seen = []
    transcriber = CloudTranscriber(settings, transport=httpx.MockTransport(lambda request: seen.append(request)))
    assert transcriber.transcribe("missing", should_cancel=lambda: True) is None
    cancelled = False
    original = cloud._audio_bytes
    def read(value):
        nonlocal cancelled
        data = original(value)
        cancelled = True
        return data
    monkeypatch.setattr(cloud, "_audio_bytes", read)
    assert transcriber.transcribe(wav, should_cancel=lambda: cancelled) is None
    assert seen == []


def test_cancel_inflight_discards_response_and_never_retries(settings, wav):
    cancelled, attempts = False, []
    def handle(request):
        nonlocal cancelled
        attempts.append(request)
        cancelled = True
        return httpx.Response(200, json={"text": "must never be published"})
    transcriber = CloudTranscriber(settings, transport=httpx.MockTransport(handle))
    assert transcriber.transcribe(wav, should_cancel=lambda: cancelled) is None
    assert transcriber.transcribe(wav, should_cancel=lambda: cancelled) is None
    assert len(attempts) == 1


def test_cancel_while_reading_stream_closes_response(settings, wav):
    cancelled, closed = False, False
    class ResponseStream(httpx.SyncByteStream):
        def __iter__(self):
            nonlocal cancelled
            yield b'{"text":"'
            cancelled = True
            yield b'must not publish"}'
        def close(self):
            nonlocal closed
            closed = True
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=ResponseStream()))
    assert CloudTranscriber(settings, transport=transport).transcribe(wav, should_cancel=lambda: cancelled) is None
    assert closed


def test_maximum_duration_uses_wav_frames_not_caller_claim(settings, tmp_path):
    wav = make_wav(tmp_path / "limit.wav", frames=MAX_FRAMES)
    def handle(request):
        with wave.open(io.BytesIO(parts(request)["file"].get_payload(decode=True))) as source:
            assert source.getnframes() == MAX_FRAMES
        return httpx.Response(200, json={"text": "synthetic"})
    assert CloudTranscriber(settings, transport=httpx.MockTransport(handle)).transcribe(wav, duration=999)["final"] == "synthetic"
