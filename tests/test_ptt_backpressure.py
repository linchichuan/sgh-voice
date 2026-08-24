"""Bounded push-to-talk processing and cooperative cancellation."""

import threading
import types


def test_start_recording_refuses_before_opening_microphone_when_pipeline_is_full():
    import app

    recorder_starts = []
    engine = object.__new__(app.VoiceEngine)
    engine._state_lock = threading.RLock()
    engine._recorder_transition_lock = threading.RLock()
    engine._data_wipe_in_progress = False
    engine.is_recording = False
    engine.is_processing = True
    engine._inflight_transcriptions = 2
    engine._record_start_ts = None
    engine._active_recording_tokens = {1.0, 2.0}
    engine._cancelled_recording_tokens = set()
    engine._processing_recording_tokens = [1.0, 2.0]
    engine._recording_context_by_token = {}
    engine._on_status_change = None
    engine.config = {"ptt_max_inflight_transcriptions": 2}
    engine.recorder = types.SimpleNamespace(
        start=lambda **_kwargs: recorder_starts.append(True) or True
    )

    assert engine.start_recording(from_hotkey=True) is False
    assert recorder_starts == []
    assert engine.is_recording is False


def test_cancelled_transcription_stops_before_cloud_fallback_and_history(
    mock_transcriber, monkeypatch
):
    cancelled = threading.Event()
    fallback_calls = []
    mock_transcriber.config.update(
        {
            "stt_engine": "groq",
            "groq_api_key": "synthetic-groq",
            "openai_api_key": "synthetic-openai",
            "enable_hybrid_mode": False,
        }
    )

    def first_attempt(_audio, duration=0):
        cancelled.set()
        return None

    monkeypatch.setattr(mock_transcriber, "_groq_stt", first_attempt)
    monkeypatch.setattr(
        mock_transcriber,
        "_whisper_api_fallback",
        lambda *_args, **_kwargs: fallback_calls.append(True) or {
            "text": "must not run",
            "language": "en",
        },
    )
    history_before = list(mock_transcriber.memory.history)

    result = mock_transcriber.transcribe(
        "synthetic.wav",
        audio_duration=1.0,
        should_cancel=cancelled.is_set,
    )

    assert result is None
    assert fallback_calls == []
    assert mock_transcriber.memory.history == history_before
