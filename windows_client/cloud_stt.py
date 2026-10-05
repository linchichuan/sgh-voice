"""Explicit, single-provider Windows dictation through OpenAI's audio REST API.

No SDK, LLM cleanup, vocabulary prompt, retries or provider fallback is used.
Cancellation can prevent a request or discard its response; it cannot recall
audio already sent to the provider. Callers own history and temporary files.
"""
from __future__ import annotations

import io
import json
import wave

ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
MODEL = "whisper-1"
ENGINE = "openai-whisper-1"
MAX_AUDIO_BYTES = 25_000_000
MAX_FRAMES = 180 * 16000
MAX_RESPONSE_BYTES = 1_000_000


class CloudSTTError(RuntimeError):
    """Stable UI code; never include provider bodies, keys, paths or speech."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def validate_cloud_settings(settings):
    """Validate explicit cloud selection without network or credential lookup."""
    if settings.get("windows_recognition_mode", "local") != "openai-cloud":
        raise CloudSTTError("invalid_recognition_mode")
    if settings.get("windows_cloud_consent") is not True:
        raise CloudSTTError("cloud_consent_required")
    key = settings.get("openai_api_key", "")
    # Header-safe keys only. Do not silently trim or accept a masked placeholder.
    if (not isinstance(key, str) or not key or not key.isascii()
            or any(not 33 <= ord(char) <= 126 for char in key)
            or "*" in key or "..." in key):
        raise CloudSTTError("cloud_key_required")
    if settings.get("windows_language", "ja") not in ("auto", "ja", "zh", "en"):
        raise CloudSTTError("invalid_language")


def _audio_bytes(value):
    """Accept bounded local PCM16 mono 16k WAV and drop all ancillary metadata."""
    from windows_client.local_stt import LocalSTTError, _local_path

    try:
        path = _local_path(value, "cloud_audio_invalid")
        if not path.is_file() or not 44 < path.stat().st_size < MAX_AUDIO_BYTES:
            raise ValueError
        with path.open("rb") as stream:
            data = stream.read(MAX_AUDIO_BYTES)
        if len(data) >= MAX_AUDIO_BYTES:
            raise ValueError
        with wave.open(io.BytesIO(data), "rb") as source:
            frames = source.getnframes()
            if (source.getnchannels() != 1 or source.getsampwidth() != 2
                    or source.getframerate() != 16000 or source.getcomptype() != "NONE"
                    or not 0 < frames <= MAX_FRAMES):
                raise ValueError
            pcm = source.readframes(frames + 1)
            if len(pcm) != frames * 2:
                raise ValueError
        output = io.BytesIO()
        with wave.open(output, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(16000)
            target.writeframes(pcm)
        return output.getvalue()
    except (LocalSTTError, OSError, EOFError, ValueError, TypeError, wave.Error):
        raise CloudSTTError("cloud_audio_invalid") from None


class CloudTranscriber:
    """Controller-compatible adapter; ``transport`` is a mock injection point.

    Settings are copied, then revalidated for each call. Nothing is read from
    environment variables, the shared provider router or a credential store.
    """

    def __init__(self, settings, memory=None, *, transport=None):
        validate_cloud_settings(settings)
        self._settings = {
            name: settings.get(name) for name in (
                "windows_recognition_mode", "windows_cloud_consent", "openai_api_key"
            )
        }
        self._settings["windows_language"] = settings.get("windows_language", "ja")
        self._transport = transport

    def transcribe(self, audio, duration=0, mode="dictate", *, should_cancel=None):
        """Return recognizer text verbatim, or None when cancellation is observed."""
        cancelled = should_cancel or (lambda: False)
        if cancelled():
            return None
        validate_cloud_settings(self._settings)
        if mode != "dictate":
            raise CloudSTTError("invalid_mode")
        wav = _audio_bytes(audio.get("path") if isinstance(audio, dict) else audio)
        if cancelled():
            return None

        import httpx

        form = {"model": MODEL, "response_format": "json"}
        language = self._settings["windows_language"]
        if language != "auto":
            form["language"] = language
        try:
            # httpx's default transport has zero retries. Explicit client options
            # disable environment proxies/custom CAs and all redirect following.
            with httpx.Client(
                timeout=httpx.Timeout(90.0, connect=10.0, write=30.0, pool=10.0),
                verify=True, trust_env=False, follow_redirects=False,
                transport=self._transport,
            ) as client:
                if cancelled():
                    return None
                with client.stream(
                    "POST", ENDPOINT,
                    headers={"Authorization": "Bearer " + self._settings["openai_api_key"]},
                    files={"file": ("recording.wav", wav, "audio/wav")}, data=form,
                ) as response:
                    if cancelled():
                        return None
                    if response.status_code in (401, 403):
                        raise CloudSTTError("cloud_auth_failed")
                    if response.status_code == 429:
                        raise CloudSTTError("cloud_rate_limited")
                    if response.status_code != 200:
                        raise CloudSTTError("cloud_request_failed")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if cancelled():
                            return None
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise CloudSTTError("cloud_invalid_response")
            if cancelled():
                return None
            try:
                result = json.loads(body)
                text = result.get("text") if isinstance(result, dict) else None
                if not isinstance(text, str) or not text.strip() or "\x00" in text:
                    raise ValueError
            except (ValueError, UnicodeError):
                raise CloudSTTError("cloud_invalid_response") from None
            return {"raw": text, "final": text, "engine": ENGINE}
        except CloudSTTError:
            if cancelled():
                return None
            raise
        except httpx.TimeoutException:
            if cancelled():
                return None
            raise CloudSTTError("cloud_timeout") from None
        except Exception:
            if cancelled():
                return None
            raise CloudSTTError("cloud_request_failed") from None
