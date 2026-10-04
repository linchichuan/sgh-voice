from windows_client._vendor.faster_whisper.audio import decode_audio
from windows_client._vendor.faster_whisper.transcribe import BatchedInferencePipeline, WhisperModel
from windows_client._vendor.faster_whisper.utils import available_models, download_model, format_timestamp
from windows_client._vendor.faster_whisper.version import __version__

__all__ = [
    "available_models",
    "decode_audio",
    "WhisperModel",
    "BatchedInferencePipeline",
    "download_model",
    "format_timestamp",
    "__version__",
]
