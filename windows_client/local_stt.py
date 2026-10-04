"""Offline-only CPU dictation for the Windows client.

Model acquisition belongs to the explicit model setup flow. This module accepts
only an existing absolute local directory, never a Hub ID or model size. In
particular, tokenizer.json is mandatory: faster-whisper otherwise attempts to
fetch its tokenizer even when the model itself came from a local directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading


def enforce_offline_environment():
    """Set these before the first import of Hugging Face libraries."""
    for name in (
        "HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN", "HF_HUB_DISABLE_UPDATE_CHECK",
        "TRANSFORMERS_OFFLINE", "DO_NOT_TRACK",
    ):
        os.environ[name] = "1"


enforce_offline_environment()

REQUIRED_MODEL_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")
ENGINE = "faster-whisper-cpu-int8"


class LocalSTTError(RuntimeError):
    """A stable UI error code without audio, transcript or filesystem details."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _drive_is_remote(path):
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes
    get_type = ctypes.windll.kernel32.GetDriveTypeW
    get_type.argtypes = [wintypes.LPCWSTR]
    get_type.restype = wintypes.UINT
    return get_type(str(path.anchor)) == 4  # DRIVE_REMOTE


def _local_path(value, error):
    try:
        raw = os.fspath(value)
        if (not isinstance(raw, str) or not raw.strip() or "://" in raw
                or raw.startswith(("\\\\", "//"))):
            raise ValueError
        path = Path(raw)
        if not path.is_absolute():
            raise ValueError
        # Reject mapped network drives before resolving or probing their files.
        if _drive_is_remote(path):
            raise ValueError
        path = path.resolve(strict=True)
        if str(path).startswith(("\\\\", "//")) or _drive_is_remote(path):
            raise ValueError
        return path
    except (OSError, TypeError, ValueError, RuntimeError):
        raise LocalSTTError(error) from None


def validate_model_directory(value):
    """Check the complete local CT2 Whisper bundle before importing its engine.

    This validates readiness, not provenance. The model setup flow is responsible
    for verifying the pinned download hashes before making a directory active.
    """
    path = _local_path(value, "invalid_model_path")
    if not path.is_dir():
        raise LocalSTTError("model_not_ready")
    try:
        for name in REQUIRED_MODEL_FILES:
            file = path / name
            # Refuse cache links to files outside the selected model bundle.
            if (file.is_symlink() or not file.is_file() or file.resolve(strict=True).parent != path
                    or file.stat().st_size == 0):
                raise ValueError
        for name in ("config.json", "tokenizer.json"):
            with (path / name).open("r", encoding="utf-8") as stream:
                if not isinstance(json.load(stream), dict):
                    raise ValueError
        # Detect Git LFS pointer files instead of feeding one to native code.
        with (path / "model.bin").open("rb") as stream:
            if stream.read(128).startswith(b"version https://git-lfs.github.com/spec/"):
                raise ValueError
        optional = path / "preprocessor_config.json"
        if optional.is_symlink():
            raise ValueError
        if optional.exists():
            if optional.resolve(strict=True).parent != path:
                raise ValueError
            with optional.open("r", encoding="utf-8") as stream:
                if not isinstance(json.load(stream), dict):
                    raise ValueError
    except (OSError, ValueError, UnicodeError, RuntimeError):
        raise LocalSTTError("model_not_ready") from None
    return path


class LocalTranscriber:
    """Compatible with the Windows controller's transcriber factory.

    An instance retains its loaded model for successive recordings. The caller
    should replace the instance when its configuration changes. Cancellation is
    checked between decoder segments; a running native decoder call cannot be
    interrupted here, but cancelled speech is never returned.
    """

    def __init__(self, config, memory=None, *, model_factory=None):
        self.model_dir = validate_model_directory(config.get("windows_model_dir", ""))
        self.language = config.get("windows_language", "ja")
        if self.language not in ("auto", "ja", "zh", "en"):
            raise LocalSTTError("invalid_language")
        threads = config.get("windows_cpu_threads", min(4, os.cpu_count() or 1))
        if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 32:
            raise LocalSTTError("invalid_cpu_threads")
        self.cpu_threads = threads
        self._model_factory = model_factory
        self._model = None
        self._lock = threading.Lock()
        # No shared Transcriber, cloud SDK, LLM or memory/history implementation
        # is imported. History persistence is a separate controller decision.

    def _load_model(self):
        enforce_offline_environment()
        validate_model_directory(self.model_dir)
        if self._model is None:
            factory = self._model_factory
            if factory is None:
                try:
                    import onnxruntime
                    onnxruntime.disable_telemetry_events()
                    from windows_client._vendor.faster_whisper import WhisperModel
                except (ImportError, OSError):
                    raise LocalSTTError("local_runtime_missing") from None
                factory = WhisperModel
            try:
                self._model = factory(
                    str(self.model_dir), device="cpu", compute_type="int8",
                    cpu_threads=self.cpu_threads, num_workers=1,
                    local_files_only=True,
                )
            except Exception:
                raise LocalSTTError("local_model_load_failed") from None
        return self._model

    def transcribe(self, audio, duration=0, mode="dictate", *, should_cancel=None):
        """Return recognizer text verbatim, without prompting or LLM cleanup."""
        cancelled = should_cancel or (lambda: False)
        empty = {"raw": "", "final": "", "engine": ENGINE, "cancelled": True}
        if cancelled():
            return empty
        if mode != "dictate":
            raise LocalSTTError("invalid_mode")
        value = audio.get("path") if isinstance(audio, dict) else audio
        path = _local_path(value, "audio_unavailable")
        try:
            if not path.is_file() or path.stat().st_size == 0:
                raise LocalSTTError("audio_unavailable")
        except OSError:
            raise LocalSTTError("audio_unavailable") from None
        # The vendored WAV frontend checks the recorder's 16 kHz mono PCM16
        # contract. It has no general media decoder or implicit resampling.
        with self._lock:
            if cancelled():
                return empty
            model = self._load_model()
            if cancelled():
                return empty
            segments = None
            try:
                segments, info = model.transcribe(
                    str(path), language=None if self.language == "auto" else self.language,
                    task="transcribe", beam_size=5, temperature=0.0,
                    condition_on_previous_text=False, vad_filter=False,
                    initial_prompt=None, hotwords=None, log_progress=False,
                )
                texts = []
                for segment in segments:
                    if cancelled():
                        return empty
                    texts.append(segment.text)
                if cancelled():
                    return empty
                text = "".join(texts).strip()
                return {"raw": text, "final": text, "engine": ENGINE,
                        "language": info.language, "cancelled": False}
            except Exception:
                if cancelled():
                    return empty
                raise LocalSTTError("local_transcription_failed") from None
            finally:
                close = getattr(segments, "close", None)
                if close is not None:
                    try:
                        close()
                    except Exception:
                        pass  # Cleanup errors must not reveal decoder details.
