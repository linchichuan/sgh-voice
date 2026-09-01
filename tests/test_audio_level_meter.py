"""Live microphone level feedback contracts shared by the desktop waveform."""

import threading

import numpy as np
import pytest

import app
import recorder as recorder_module


def test_audio_level_normalization_keeps_silence_flat_and_speech_visible():
    normalize = recorder_module.normalize_audio_level

    assert normalize(0.0) == 0.0
    assert normalize(0.001) == 0.0
    assert 0.0 < normalize(0.01) < normalize(0.05) < 1.0
    assert normalize(0.2) == 1.0


@pytest.mark.skipif(
    recorder_module.sd is None,
    reason="sounddevice is required for the recorder loop contract",
)
def test_recorder_reports_each_chunk_level_and_resets_to_flat(monkeypatch):
    recorder = recorder_module.Recorder(
        {
            "sample_rate": 16_000,
            "max_recording_duration": 0.2,
            "hotkey_mode": "push_to_talk",
        }
    )
    chunks = [
        np.zeros((1_600, 1), dtype=np.float32),
        np.full((1_600, 1), 0.05, dtype=np.float32),
    ]

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _chunk):
            return chunks.pop(0), False

    levels = []
    recorder.set_level_listener(levels.append)
    monkeypatch.setattr(recorder, "_open_input_stream", lambda _sr, _chunk: Stream())

    recorder.is_recording = True
    recorder._record_loop()

    assert levels[0] == 0.0
    assert levels[1] > 0.0
    assert levels[-1] == 0.0


def test_engine_forwards_only_the_current_recording_level():
    current_token = 101.0
    received = []
    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = threading.RLock()
    engine.is_recording = True
    engine._record_start_ts = current_token
    engine._active_recording_tokens = {current_token}
    engine.overlay = type(
        "Overlay",
        (),
        {"update_audio_level": lambda _self, level: received.append(level)},
    )()

    engine._on_recording_level(0.7, current_token)
    engine._on_recording_level(0.9, current_token - 1)
    engine.is_recording = False
    engine._on_recording_level(0.8, current_token)

    assert received == [0.7]
