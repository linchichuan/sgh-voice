"""Windows orchestration checks with no microphone, API calls or user data."""
import threading
import time
from types import SimpleNamespace

import pytest

from windows_client.controller import Controller, runtime_config


def wait_for(predicate):
    deadline = time.monotonic() + 3
    while not predicate():
        assert time.monotonic() < deadline, "controller did not settle"
        time.sleep(0.005)


@pytest.fixture
def harness(tmp_path):
    events, calls = [], []
    wav = tmp_path / "synthetic.wav"
    started = threading.Event()
    finish_gate = threading.Event()
    finish_gate.set()

    class Recorder:
        is_recording = False
        def __init__(self, config):
            self.config = config
        def set_level_listener(self, callback):
            self.level = callback
        def start(self, **kwargs):
            self.is_recording = True
            started.set()
            return True
        def stop(self):
            self.is_recording = False
            wav.write_bytes(b"synthetic audio")
            return None, str(wav), 1.0

    class Transcriber:
        def __init__(self, config, memory):
            self.config = config
        def transcribe(self, audio, duration, mode, **kwargs):
            calls.append(self.config)
            finish_gate.wait(3)
            return {"final": "你好、Windows!"}

    class Native:
        def send_text(self, target, text):
            calls.append((target, text))
            return SimpleNamespace(success=False, reason="focus_changed")

    controller = Controller(
        {"windows_model_dir": str(tmp_path)},
        lambda *event: events.append(event), Native(), recorder_factory=Recorder,
        transcriber_factory=Transcriber, memory_factory=lambda *args: object(),
        model_validator=lambda path: path,
    )
    yield SimpleNamespace(controller=controller, events=events, calls=calls,
                          wav=wav, started=started, finish_gate=finish_gate)
    finish_gate.set()
    controller.close()
    wait_for(lambda: controller.state == "closed")


def test_missing_model_does_not_start_microphone(harness):
    c = harness.controller
    c._model_validator = None
    c.apply_config({"windows_model_dir": ""})
    assert not c.toggle()
    assert not harness.started.is_set()
    assert ("error", "invalid_model_path") in harness.events


def test_single_flight_result_and_cleanup(harness):
    c = harness.controller
    assert c.toggle()
    assert harness.started.wait(1)
    assert c.toggle()
    assert not c.toggle()
    wait_for(lambda: c.state == "idle")
    assert c.last_text == "你好、Windows!"
    assert not harness.wav.exists()
    assert len(harness.calls) == 1
    assert next(e[1] for e in harness.events if e[0] == "result")["insertion"]["reason"] == "preview_only"


def test_cancellation_discards_recording_without_inference(harness):
    c = harness.controller
    c.toggle()
    assert harness.started.wait(1)
    c.cancel()
    wait_for(lambda: c.state == "idle")
    assert not harness.calls
    assert not harness.wav.exists()
    assert not [e for e in harness.events if e[0] == "result"]


def test_cancellation_while_inference_inflight_never_inserts(harness):
    c = harness.controller
    harness.finish_gate.clear()
    c.toggle()
    assert harness.started.wait(1)
    c.toggle()
    wait_for(lambda: c.state == "processing")
    c.cancel()
    harness.finish_gate.set()
    wait_for(lambda: c.state == "idle")
    assert c.last_text == ""
    assert not [e for e in harness.events if e[0] == "result"]
    assert not harness.wav.exists()


def test_changed_target_preserves_result_for_manual_copy(harness):
    c = harness.controller
    c.apply_config({**c.config, "windows_auto_insert": True})
    c.toggle(target=123)
    assert harness.started.wait(1)
    c.toggle()
    wait_for(lambda: c.state == "idle")
    result = next(e[1] for e in harness.events if e[0] == "result")
    assert result["text"]
    assert result["insertion"] == {"success": False, "reason": "focus_changed"}
    assert len(harness.calls) == 2


def test_runtime_cannot_enable_cloud_even_with_migrated_settings():
    c = runtime_config({"windows_provider": "openai", "openai_api_key": "test-openai",
                        "groq_api_key": "test-groq", "anthropic_api_key": "test-other",
                        "windows_cloud_consent": True, "windows_polish": True,
                        "enable_hybrid_mode": True, "allow_cross_provider_llm_fallback": True,
                        "enable_fewshot": True, "enable_app_awareness": True})
    assert c["stt_engine"] == "faster-whisper-local"
    assert c["llm_engine"] == "disabled"
    assert not c["openai_api_key"] and not c["groq_api_key"] and not c["anthropic_api_key"]
    assert not c["windows_cloud_consent"] and not c["enable_claude_polish"]
    assert not c["allow_cross_provider_llm_fallback"]
    assert not c["enable_hybrid_mode"] and not c["enable_fewshot"]
    assert not c["enable_app_awareness"]


def test_settings_cannot_change_during_recording(harness):
    c = harness.controller
    c.toggle()
    with pytest.raises(RuntimeError, match="busy"):
        c.apply_config({})
    c.cancel()
    wait_for(lambda: c.state == "idle")


def test_recorder_wav_save_without_posix_fchmod(tmp_path, monkeypatch):
    import numpy as np
    import recorder
    monkeypatch.delattr(recorder.os, "fchmod", raising=False)
    monkeypatch.setattr(recorder.tempfile, "tempdir", str(tmp_path))
    path = recorder.Recorder({"sample_rate": 16000})._save(np.zeros(8000, dtype=np.float32))
    assert path
    import soundfile
    data, sample_rate = soundfile.read(path)
    assert len(data) == 8000 and sample_rate == 16000


def test_same_recorder_retains_guard_after_stuck_capture(harness):
    c = harness.controller
    c.toggle()
    assert harness.started.wait(1)
    recorder = c._recorder
    recorder._thread = SimpleNamespace(is_alive=lambda: True)
    calls = []
    def guarded_start(**kwargs):
        calls.append("guard checked")
        raise RuntimeError("previous capture still running")
    c.toggle()
    wait_for(lambda: c.state == "idle")
    assert not harness.calls  # Incomplete capture never reaches the provider.
    assert not harness.wav.exists()
    recorder.start = guarded_start
    c.toggle()
    wait_for(lambda: c.state == "idle")
    assert c._recorder is recorder
    assert calls == ["guard checked"]


def test_close_waits_for_processing_cleanup(harness):
    c = harness.controller
    harness.finish_gate.clear()
    c.toggle()
    assert harness.started.wait(1)
    c.toggle()
    wait_for(lambda: bool(harness.calls))
    assert harness.wav.exists()
    c.close()
    assert c.state != "closed"
    harness.finish_gate.set()
    wait_for(lambda: c.state == "closed")
    assert not harness.wav.exists()
    assert not [event for event in harness.events if event[0] == "result"]


def test_local_model_is_reused_between_recordings(harness):
    c = harness.controller
    for _ in range(2):
        c.toggle()
        wait_for(lambda: c._capture_open)
        c.toggle()
        wait_for(lambda: c.state == "idle")
        if _ == 0:
            first = c._transcriber
    assert c._transcriber is first
    assert len(harness.calls) == 2


def test_model_setup_cancel_drains_before_close(harness, monkeypatch):
    import windows_client.models as models
    entered = threading.Event()
    def prepare(**kwargs):
        entered.set()
        wait_for(kwargs["should_cancel"])
        raise models.ModelDownloadError("model_download_cancelled")
    monkeypatch.setattr(models, "prepare_model", prepare)
    c = harness.controller
    assert c.prepare_model()
    assert entered.wait(1)
    assert not c.toggle()
    c.close()
    wait_for(lambda: c.state == "closed")
    assert not [event for event in harness.events if event[0] == "model_ready"]
