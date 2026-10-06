"""Convert a user-chosen phone/recorder file (WAV or MP3) to the recognizer's
16 kHz mono PCM16 WAV contract, entirely on this computer.

Decoding uses the bundled libsndfile (via soundfile); no FFmpeg, codec download
or network access. Audio is processed in blocks so long recordings do not need
the whole decoded signal in memory. Errors are stable UI codes without paths
or audio content.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np

SUPPORTED_EXTENSIONS = {".wav": "WAV", ".mp3": "MP3"}
TARGET_RATE = 16000
MAX_SECONDS = 3 * 60 * 60          # 3 hours
MAX_BYTES = 2 * 1024 ** 3           # 2 GiB
BLOCK_SECONDS = 30
_TAPS = 129


class AudioImportError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _lowpass_kernel(source_rate):
    """Windowed-sinc low-pass just below the 8 kHz Nyquist of the 16 kHz target."""
    cutoff = 0.45 * TARGET_RATE / source_rate  # normalised to the source rate
    n = np.arange(_TAPS) - (_TAPS - 1) / 2
    kernel = 2 * cutoff * np.sinc(2 * cutoff * n) * np.hamming(_TAPS)
    return (kernel / kernel.sum()).astype(np.float32)


def inspect(path):
    """Validate the chosen file; return (soundfile info, duration seconds)."""
    try:
        path = Path(path)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise AudioImportError("audio_format_unsupported")
        if not path.is_file() or path.is_symlink():
            raise AudioImportError("audio_file_unreadable")
        size = path.stat().st_size
        if size == 0:
            raise AudioImportError("audio_file_empty")
        if size > MAX_BYTES:
            raise AudioImportError("audio_file_too_long")
        import soundfile
        info = soundfile.info(str(path))
    except AudioImportError:
        raise
    except Exception:
        raise AudioImportError("audio_file_unreadable") from None
    if info.format != SUPPORTED_EXTENSIONS[path.suffix.lower()] or info.samplerate <= 0 or info.channels <= 0:
        raise AudioImportError("audio_format_unsupported")
    duration = info.frames / info.samplerate if info.frames > 0 else 0.0
    if duration > MAX_SECONDS:
        raise AudioImportError("audio_file_too_long")
    return info, duration


def convert_to_pcm16k(path, destination, *, should_cancel=lambda: False, on_progress=lambda f: None):
    """Decode, mix down to mono, low-pass and resample to 16 kHz PCM16 WAV.

    Returns the converted duration in seconds. The destination is removed on
    any failure or cancellation, so partial audio never remains on disk.
    """
    import soundfile
    info, _duration = inspect(path)
    rate = info.samplerate
    destination = Path(destination)
    written = 0
    try:
        with soundfile.SoundFile(str(path)) as source, soundfile.SoundFile(
                str(destination), "x", samplerate=TARGET_RATE, channels=1,
                subtype="PCM_16", format="WAV") as target:
            kernel = _lowpass_kernel(rate) if rate > TARGET_RATE else None
            history = np.zeros(_TAPS - 1, dtype=np.float32)
            step = rate / TARGET_RATE
            position = 0.0              # next output sample, in source-sample units
            consumed = 0                # source samples before the current block
            previous = np.zeros(1, dtype=np.float32)
            for block in source.blocks(blocksize=int(rate * BLOCK_SECONDS), dtype="float32", always_2d=True):
                if should_cancel():
                    raise AudioImportError("cancelled")
                mono = block.mean(axis=1, dtype=np.float32)
                if kernel is not None:
                    padded = np.concatenate([history, mono])
                    history = padded[-(_TAPS - 1):]
                    mono = np.convolve(padded, kernel, mode="valid").astype(np.float32)
                # Linear interpolation across the block boundary (one sample of context).
                signal = np.concatenate([previous, mono])
                end = consumed + len(mono)
                count = int(math.floor((end - 1 - position) / step)) + 1 if end - 1 >= position else 0
                if count > 0:
                    points = position + step * np.arange(count) - (consumed - 1)
                    samples = np.interp(points, np.arange(len(signal)), signal).astype(np.float32)
                    target.write(np.clip(samples, -1.0, 1.0))
                    written += count
                    position += step * count
                previous = mono[-1:]
                consumed = end
                if info.frames > 0:
                    on_progress(min(1.0, consumed / info.frames))
        if written < TARGET_RATE // 10:
            raise AudioImportError("audio_file_empty")
        return written / TARGET_RATE
    except AudioImportError:
        _remove(destination)
        raise
    except Exception:
        _remove(destination)
        raise AudioImportError("audio_file_unreadable") from None


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
