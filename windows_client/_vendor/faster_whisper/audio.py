"""SGHVoice's PCM WAV frontend for the vendored MIT faster-whisper engine.

The Windows recorder produces 16 kHz, mono, signed PCM16 WAV. Decode only that
format with Python's wave module; compressed audio, other sample rates and other
channel layouts are deliberately rejected. There is no PyAV/FFmpeg backend and
no resampling. See PROVENANCE.md for the upstream version and local changes.
"""
import os
import wave

from typing import BinaryIO, Union

import numpy as np


def decode_audio(
    input_file: Union[str, BinaryIO],
    sampling_rate: int = 16000,
    split_stereo: bool = False,
):
    """Read the recorder's mono PCM16 WAV as normalized float32 samples.

    The signature is retained for the unmodified upstream transcription code.
    This restricted frontend intentionally does not implement upstream's general
    media decoding or stereo splitting. A mismatched format fails explicitly,
    instead of interpreting audio at the wrong rate or using another decoder.
    """
    if sampling_rate != 16000 or split_stereo:
        raise ValueError("Only 16 kHz mono PCM16 WAV decoding is supported")
    if isinstance(input_file, (str, os.PathLike)):
        input_file = os.fspath(input_file)
        if (not isinstance(input_file, str) or not os.path.isabs(input_file)
                or "://" in input_file or input_file.startswith((chr(92) * 2, "//"))):
            raise ValueError("A local absolute WAV path is required")
    with wave.open(input_file, "rb") as recording:
        if (recording.getnchannels() != 1 or recording.getsampwidth() != 2
                or recording.getframerate() != 16000
                or recording.getcomptype() != "NONE"):
            raise ValueError("Only 16 kHz mono PCM16 WAV recordings are supported")
        count = recording.getnframes()
        raw = recording.readframes(count)
        if count == 0 or len(raw) != count * 2:
            raise ValueError("The PCM WAV recording is empty or incomplete")
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / np.float32(32768.0)


def pad_or_trim(array, length: int = 3000, *, axis: int = -1):
    """
    Pad or trim the Mel features array to 3000, as expected by the encoder.
    """
    if array.shape[axis] > length:
        array = array.take(indices=range(length), axis=axis)

    if array.shape[axis] < length:
        pad_widths = [(0, 0)] * array.ndim
        pad_widths[axis] = (0, length - array.shape[axis])
        array = np.pad(array, pad_widths)

    return array
