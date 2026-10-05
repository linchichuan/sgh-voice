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


def test_legacy_provider_and_consent_do_not_enable_new_cloud_mode():
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
    assert c["windows_recognition_mode"] == "local"


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


def cloud_settings(**overrides):
    return {"windows_recognition_mode": "openai-cloud", "windows_cloud_consent": True,
            "openai_api_key": "test-synthetic-key", "windows_language": "ja", **overrides}


@pytest.mark.parametrize("settings,code", [
    ({"windows_recognition_mode": "unknown"}, "invalid_recognition_mode"),
    (cloud_settings(windows_cloud_consent=False), "cloud_consent_required"),
    (cloud_settings(windows_cloud_consent=1), "cloud_consent_required"),
    (cloud_settings(windows_cloud_consent="true"), "cloud_consent_required"),
    (cloud_settings(openai_api_key=""), "cloud_key_required"),
    (cloud_settings(openai_api_key="secret\nheader"), "cloud_key_required"),
])
def test_cloud_preflight_blocks_microphone(harness, settings, code):
    c = harness.controller
    c.apply_config(settings)
    assert not c.toggle()
    assert c.state == "idle"
    assert not harness.started.is_set() and not harness.calls
    assert ("error", code) in harness.events


def test_cloud_runtime_has_only_selected_key_and_no_llm():
    source = cloud_settings(groq_api_key="test-groq", anthropic_api_key="test-anthropic",
                            openrouter_api_key="test-router", elevenlabs_api_key="test-eleven",
                            llm_engine="enabled", enable_claude_polish=True,
                            enable_hybrid_mode=True, allow_cross_provider_llm_fallback=True)
    result = runtime_config(source)
    assert result["openai_api_key"] == "test-synthetic-key"
    assert all(result[name + "_api_key"] == "" for name in ("groq", "anthropic", "openrouter", "elevenlabs"))
    assert result["windows_cloud_consent"] is True
    assert result["stt_engine"] == "openai-whisper-1" and result["llm_engine"] == "disabled"
    assert not result["enable_claude_polish"] and not result["enable_hybrid_mode"]
    assert not result["allow_cross_provider_llm_fallback"]
    assert result["backup_audio_dir"] == "" and result["max_recording_duration"] == 180
    assert source["groq_api_key"] == "test-groq"  # Never mutate the caller's settings.


def test_cloud_needs_no_local_model_and_recording_keeps_snapshot(harness):
    c = harness.controller
    c._model_validator = lambda _: pytest.fail("cloud must not validate/load a local model")
    c.apply_config(cloud_settings())
    assert c.toggle()
    assert harness.started.wait(1)
    # Direct caller mutation is not the supported apply_config path; the active
    # recording must still retain its authorized settings snapshot.
    c.config["windows_recognition_mode"] = "local"
    c.config["openai_api_key"] = "changed-mid-recording"
    c.toggle()
    wait_for(lambda: c.state == "idle")
    assert harness.calls[0]["windows_recognition_mode"] == "openai-cloud"
    assert harness.calls[0]["openai_api_key"] == "test-synthetic-key"
    assert next(value for event, value in harness.events if event == "result")["engine"] == "openai-whisper-1"


def complete_recording(c):
    assert c.toggle()
    wait_for(lambda: c._capture_open)
    assert c.toggle()
    wait_for(lambda: c.state == "idle")


def test_mode_and_key_changes_invalidate_transcriber_cache(harness):
    c = harness.controller
    complete_recording(c)
    local = c._transcriber
    c.apply_config(cloud_settings())
    assert c._transcriber is None
    complete_recording(c)
    cloud = c._transcriber
    assert cloud is not local
    complete_recording(c)
    assert c._transcriber is cloud
    c.apply_config(cloud_settings(openai_api_key="second-synthetic-key"))
    complete_recording(c)
    assert c._transcriber is not cloud
    assert harness.calls[-1]["openai_api_key"] == "second-synthetic-key"
    c.apply_config({"windows_recognition_mode": "local", "windows_model_dir": "synthetic"})
    complete_recording(c)
    assert harness.calls[-1]["openai_api_key"] == ""


def test_default_factories_follow_mode_without_provider_fallback(harness, monkeypatch):
    import windows_client.cloud_stt as cloud
    import windows_client.local_stt as local
    calls, history = [], []
    def factory(engine):
        class Fake:
            def __init__(self, config, memory):
                calls.append(engine)
            def transcribe(self, *args, **kwargs):
                return {"raw": "synthetic", "final": "synthetic", "engine": engine}
        return Fake
    monkeypatch.setattr(local, "LocalTranscriber", factory("faster-whisper-cpu-int8"))
    monkeypatch.setattr(cloud, "CloudTranscriber", factory("openai-whisper-1"))
    c = harness.controller
    c._transcriber_factory = None
    c._memory_factory = lambda *args: SimpleNamespace(add_to_history=history.append)
    c.apply_config({"windows_model_dir": "synthetic", "windows_save_history": True})
    complete_recording(c)
    c.apply_config(cloud_settings(windows_save_history=True))
    complete_recording(c)
    assert calls == ["faster-whisper-cpu-int8", "openai-whisper-1"]
    assert [entry["stt_engine"] for entry in history] == calls
    assert all(entry["llm_source"] is None for entry in history)


def test_cloud_request_failure_cleans_up_once_without_fallback(harness, monkeypatch):
    import windows_client.cloud_stt as cloud
    import windows_client.local_stt as local
    calls = []
    class FailedCloud:
        def __init__(self, config, memory):
            pass
        def transcribe(self, *args, **kwargs):
            calls.append("request")
            raise cloud.CloudSTTError("cloud_rate_limited")
    monkeypatch.setattr(cloud, "CloudTranscriber", FailedCloud)
    monkeypatch.setattr(local, "LocalTranscriber", lambda *args: pytest.fail("no fallback"))
    c = harness.controller
    c._transcriber_factory = None
    c.apply_config(cloud_settings())
    complete_recording(c)
    assert calls == ["request"]
    assert ("error", "cloud_rate_limited") in harness.events
    assert not [event for event in harness.events if event[0] == "result"]
    assert not harness.wav.exists()
    error_position = harness.events.index(("error", "cloud_rate_limited"))
    assert harness.events.index(("status", "idle")) > error_position


def test_cancelled_cloud_never_saves_history_or_inserts(harness):
    history = []
    c = harness.controller
    c._memory_factory = lambda *args: SimpleNamespace(add_to_history=history.append)
    c.apply_config(cloud_settings(windows_save_history=True, windows_auto_insert=True))
    harness.finish_gate.clear()
    c.toggle(target=123)
    assert harness.started.wait(1)
    c.toggle()
    wait_for(lambda: bool(harness.calls))
    c.cancel()
    harness.finish_gate.set()
    wait_for(lambda: c.state == "idle")
    assert c.last_text == "" and history == []
    assert len(harness.calls) == 1  # The second native input call never happens.
    assert not [event for event in harness.events if event[0] == "result"]
    assert not harness.wav.exists()


def test_failed_session_cleanup_cannot_discard_new_recording(harness):
    from windows_client.cloud_stt import CloudSTTError
    c = harness.controller
    class FailedCloud:
        def __init__(self, config, memory):
            pass
        def transcribe(self, *args, **kwargs):
            raise CloudSTTError("cloud_request_failed")
    c._transcriber_factory = FailedCloud
    c.apply_config(cloud_settings())
    restarted = []
    def callback(event, value):
        harness.events.append((event, value))
        if event == "status" and value == "idle" and not restarted:
            restarted.append(c.toggle())
    c._emit_callback = callback
    c.toggle()
    assert harness.started.wait(1)
    c.toggle()
    wait_for(lambda: restarted and c._capture_open)
    assert restarted == [True]
    assert c.state == "recording"
    assert harness.events.index(("error", "cloud_request_failed")) < harness.events.index(("status", "idle"))
    c.cancel()
    wait_for(lambda: c.state == "idle")


def test_controller_real_cloud_adapter_uses_mock_transport_only(harness, monkeypatch):
    import httpx
    import wave
    import windows_client.cloud_stt as cloud
    calls = []
    original = cloud.CloudTranscriber
    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"text": "合成例。否定は変えない。"})
    monkeypatch.setattr(cloud, "CloudTranscriber",
                        lambda config, memory: original(config, memory, transport=httpx.MockTransport(handle)))
    c = harness.controller
    c._transcriber_factory = None
    c.apply_config(cloud_settings())
    c.toggle()
    assert harness.started.wait(1)
    stop = c._recorder.stop
    def wav_stop():
        audio, path, duration = stop()
        with wave.open(path, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(16000)
            target.writeframes(b"\x00" * 320)
        return audio, path, duration
    c._recorder.stop = wav_stop
    c.toggle()
    wait_for(lambda: c.state == "idle")
    assert calls == [cloud.ENDPOINT]
    result = next(value for event, value in harness.events if event == "result")
    assert result["engine"] == cloud.ENGINE and result["text"] == "合成例。否定は変えない。"
    assert not harness.wav.exists()
