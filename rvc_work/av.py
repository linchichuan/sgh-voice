"""Minimal PyAV stub for RVC training paths that only use ffmpeg-based loading.

The local RVC code imports ``av`` for optional conversion helpers, but the
training pipeline used here calls ``load_audio()``, which decodes through the
ffmpeg CLI. Keeping this stub avoids installing PyAV just to pass that import.
"""


def open(*_args, **_kwargs):
    raise RuntimeError("PyAV is not available in this local RVC training workspace")
