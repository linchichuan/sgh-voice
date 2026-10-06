"""Windows orchestration checks with no microphone, API calls or user data."""
import threading
import time
from pathlib import Path
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
        {}, lambda *event: events.append(event), Native(), recorder_factory=Recorder,
        transcriber_factory=Transcriber, memory_factory=lambda *args: object(),
        model_locator=lambda: tmp_path,
    )
    wait_for(lambda: controller.state == "idle")
    yield SimpleNamespace(controller=controller, events=events, calls=calls,
                          wav=wav, started=started, finish_gate=finish_gate)
    finish_gate.set()
    controller.close()
    wait_for(lambda: controller.state == "closed")


@pytest.mark.parametrize("code", ["model_missing", "model_invalid"])
def test_unverified_model_never_starts_microphone(code):
    from windows_client.models import ModelIntegrityError
    events, started = [], []

    def locator():
        raise ModelIntegrityError(code)

    c = Controller({}, lambda *event: events.append(event), None,
                   recorder_factory=lambda config: started.append(config), model_locator=locator)
    wait_for(lambda: c.state == "idle")
    assert not c.model_ready
    assert not c.toggle()
    assert not started
    assert events.count(("error", code)) == 2  # once at verification, once on record
    c.close()
    wait_for(lambda: c.state == "closed")


def test_recording_waits_for_model_verification():
    gate = __import__("threading").Event()
    c = Controller({}, lambda *event: None, None, model_locator=lambda: gate.wait(3) and "C:/model")
    assert c.state == "verifying_model"
    assert not c.toggle()
    gate.set()
    wait_for(lambda: c.state == "idle")
    assert c.model_ready
    c.close()
    wait_for(lambda: c.state == "closed")


def test_snapshot_uses_bundled_model_and_forces_japanese(harness):
    c = harness.controller
    c.apply_config({"windows_language": "en", "windows_model_dir": "C:/old-download"})
    c.toggle()
    wait_for(lambda: c._capture_open)
    assert c._snapshot["windows_language"] == "ja"
    assert c._snapshot["windows_model_dir"] != "C:/old-download"
    c.cancel()
    wait_for(lambda: c.state == "idle")


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


def _write_tone(path, rate, seconds, channels=1, fmt="WAV", subtype="PCM_16"):
    import numpy as np
    import soundfile
    samples = 0.2 * np.sin(2 * np.pi * 440 * np.arange(int(rate * seconds)) / rate).astype("float32")
    if channels > 1:
        samples = np.stack([samples] * channels, axis=1)
    soundfile.write(str(path), samples, rate, format=fmt, subtype=subtype)
    return path


def test_import_file_converts_transcribes_in_file_mode_and_cleans_up(tmp_path):
    import soundfile
    events, seen = [], []

    class Transcriber:
        def __init__(self, config, memory):
            self.config = config
        def transcribe(self, audio, duration, mode, should_cancel=None, on_progress=None):
            info = soundfile.info(audio["path"])
            seen.append((mode, info.samplerate, info.channels, info.subtype, round(duration, 1), audio["path"]))
            on_progress(0.5)
            return {"final": "一行目\n二行目"}

    source = _write_tone(tmp_path / "phone.mp3", 44100, 3, channels=2, fmt="MP3", subtype="MPEG_LAYER_III")
    c = Controller({}, lambda *event: events.append(event), None, transcriber_factory=Transcriber,
                   model_locator=lambda: tmp_path)
    wait_for(lambda: c.state == "idle")
    assert c.import_file(source)
    wait_for(lambda: any(e[0] == "result" for e in events) and c.state == "idle")
    assert seen[0][:5] == ("file", 16000, 1, "PCM_16", 3.0)
    assert not Path(seen[0][5]).exists()  # temporary conversion removed
    assert source.exists()                # original never modified or removed
    result = next(e[1] for e in events if e[0] == "result")
    assert result["source"] == "file" and result["insertion"]["reason"] == "preview_only"
    percents = [e[1]["percent"] for e in events if e[0] == "file_progress"]
    assert percents == sorted(percents) and percents[-1] == 100
    c.close()
    wait_for(lambda: c.state == "closed")


def test_import_rejects_unsupported_format_without_transcribing(tmp_path):
    events, calls = [], []
    source = tmp_path / "voice.m4a"
    source.write_bytes(b"not decoded")
    c = Controller({}, lambda *event: events.append(event), None,
                   transcriber_factory=lambda *a: calls.append(a), model_locator=lambda: tmp_path)
    wait_for(lambda: c.state == "idle")
    assert c.import_file(source)
    wait_for(lambda: ("error", "audio_format_unsupported") in events and c.state == "idle")
    assert not calls
    c.close()
    wait_for(lambda: c.state == "closed")


def test_import_cancel_produces_no_result(tmp_path):
    events = []
    gate = threading.Event()

    class Transcriber:
        def __init__(self, config, memory):
            pass
        def transcribe(self, audio, duration, mode, should_cancel=None, on_progress=None):
            gate.set()
            wait_for(should_cancel)
            return {"final": "should be dropped"}

    source = _write_tone(tmp_path / "rec.wav", 48000, 2)
    c = Controller({}, lambda *event: events.append(event), None, transcriber_factory=Transcriber,
                   model_locator=lambda: tmp_path)
    wait_for(lambda: c.state == "idle")
    assert c.import_file(source)
    assert gate.wait(3)
    c.cancel()
    wait_for(lambda: c.state == "idle")
    assert not [e for e in events if e[0] == "result"]
    c.close()
    wait_for(lambda: c.state == "closed")


def test_runtime_config_allows_a_whole_consultation():
    snapshot = runtime_config({"max_recording_duration": 180, "ptt_silence_autostop_seconds": 30})
    assert snapshot["max_recording_duration"] == 60 * 60
    assert snapshot["ptt_silence_autostop_seconds"] == 10 * 60


@pytest.mark.parametrize("duration,mode,long,limit", [
    (12.0, "dictate", False, False),
    (25 * 60.0, "file", True, False),
    (60 * 60.0, "file", True, True),
])
def test_long_recordings_decode_like_files_with_progress(tmp_path, duration, mode, long, limit):
    events, calls = [], []
    wav = tmp_path / "long.wav"

    class Recorder:
        is_recording = False
        def __init__(self, config):
            self.config = config
        def set_level_listener(self, callback):
            pass
        def start(self, **kwargs):
            self.is_recording = True
            return True
        def stop(self):
            self.is_recording = False
            wav.write_bytes(b"synthetic audio")
            return object(), str(wav), duration

    class Transcriber:
        def __init__(self, config, memory):
            pass
        def transcribe(self, audio, seconds, decode_mode, *, should_cancel=None, on_progress=None):
            calls.append((audio, seconds, decode_mode))
            if on_progress:
                on_progress(0.5)
            return {"final": "一行目\n二行目"}

    c = Controller({}, lambda *event: events.append(event), None, recorder_factory=Recorder,
                   transcriber_factory=Transcriber, memory_factory=lambda *args: None,
                   model_locator=lambda: tmp_path)
    wait_for(lambda: c.state == "idle")
    c.toggle()
    wait_for(lambda: c._capture_open)
    c.toggle()
    wait_for(lambda: c.state == "idle" and any(e[0] == "result" for e in events))
    # Only the WAV path is handed over; the in-memory array is released.
    assert calls == [({"path": str(wav)}, duration, mode)]
    result = next(e[1] for e in events if e[0] == "result")
    assert (result["long"], result["limit_reached"]) == (long, limit)
    assert result["text"] == "一行目\n二行目"
    assert (("file_progress", {"percent": 50}) in events) == long
    assert not wav.exists()
    c.close()
    wait_for(lambda: c.state == "closed")


class FakeSoap:
    def __init__(self, text="S（主観的情報）:\n-\nO（客観的情報）:\n-\nA（評価）:\n-\nP（計画）:\n-", error=None, gate=None):
        self.text, self.error, self.gate, self.calls = text, error, gate, []

    def __call__(self):
        return self

    def locate(self):
        return "llama-completion.exe"

    def draft(self, transcript, *, should_cancel, on_progress):
        self.calls.append(transcript)
        on_progress(3)
        if self.gate is not None:
            while not self.gate.wait(0.01):
                if should_cancel():
                    from windows_client.soap import SoapError
                    raise SoapError("cancelled")
        if self.error:
            from windows_client.soap import SoapError
            raise SoapError(self.error)
        return {"text": self.text, "unverified": [], "seconds": 3}


def soap_controller(tmp_path, soap, duration=120.0, auto=True):
    events, inserted = [], []
    wav = tmp_path / "consult.wav"

    class Recorder:
        is_recording = False
        def __init__(self, config):
            self.config = config
        def set_level_listener(self, callback):
            pass
        def start(self, **kwargs):
            self.is_recording = True
            return True
        def stop(self):
            self.is_recording = False
            wav.write_bytes(b"synthetic audio")
            return None, str(wav), duration

    class Transcriber:
        def __init__(self, config, memory):
            pass
        def transcribe(self, audio, seconds, mode, **kwargs):
            return {"final": "架空の診察の文字起こし"}

    class Native:
        def send_text(self, target, text):
            inserted.append(text)
            return SimpleNamespace(success=True, reason="sent")

    c = Controller({"windows_auto_insert": True, "windows_soap_auto": auto},
                   lambda *event: events.append(event), Native(), recorder_factory=Recorder,
                   transcriber_factory=Transcriber, memory_factory=lambda *args: None,
                   model_locator=lambda: tmp_path, soap_factory=soap)
    wait_for(lambda: c.state == "idle")
    return c, events, inserted, wav


def finish_recording(c, events, target="EHR"):
    c.toggle(target=target)
    wait_for(lambda: c._capture_open)
    c.toggle()


def test_long_recording_drafts_soap_and_inserts_only_the_draft(tmp_path):
    soap = FakeSoap()
    c, events, inserted, wav = soap_controller(tmp_path, soap)
    assert c.soap_ready
    finish_recording(c, events)
    wait_for(lambda: c.state == "idle" and any(e[0] == "soap_result" for e in events))
    result = next(e[1] for e in events if e[0] == "result")
    assert result["soap_follows"] and result["insertion"]["reason"] == "preview_only"
    soap_result = next(e[1] for e in events if e[0] == "soap_result")
    assert soap.calls == ["架空の診察の文字起こし"]
    assert soap_result["transcript"] == "架空の診察の文字起こし"
    assert inserted == [soap.text] and soap_result["insertion"]["success"]
    assert ("status", "drafting_soap") in events and ("soap_progress", {"seconds": 3}) in events
    assert c.last_soap == soap.text and not wav.exists()
    c.close()
    wait_for(lambda: c.state == "closed")


@pytest.mark.parametrize("duration,auto", [(10.0, True), (120.0, False)])
def test_short_dictation_or_disabled_setting_skips_soap(tmp_path, duration, auto):
    soap = FakeSoap()
    c, events, inserted, _wav = soap_controller(tmp_path, soap, duration=duration, auto=auto)
    finish_recording(c, events)
    wait_for(lambda: c.state == "idle" and any(e[0] == "result" for e in events))
    assert soap.calls == [] and not any(e[0] == "soap_result" for e in events)
    assert inserted == ["架空の診察の文字起こし"]  # previous dictation behaviour
    c.close()
    wait_for(lambda: c.state == "closed")


def test_soap_failure_keeps_transcript_and_reports_code(tmp_path):
    c, events, inserted, _wav = soap_controller(tmp_path, FakeSoap(error="soap_failed"))
    finish_recording(c, events)
    wait_for(lambda: c.state == "idle" and ("error", "soap_failed") in events)
    assert c.last_text == "架空の診察の文字起こし" and inserted == []
    c.close()
    wait_for(lambda: c.state == "closed")


def test_cancel_during_soap_discards_draft(tmp_path):
    gate = threading.Event()
    c, events, inserted, _wav = soap_controller(tmp_path, FakeSoap(gate=gate))
    finish_recording(c, events)
    wait_for(lambda: c.state == "drafting_soap")
    c.cancel()
    wait_for(lambda: c.state == "idle")
    assert not any(e[0] == "soap_result" for e in events) and inserted == []
    assert not any(e == ("error", "cancelled") for e in events)
    c.close()
    wait_for(lambda: c.state == "closed")


def test_manual_draft_and_missing_model(tmp_path):
    soap = FakeSoap()
    c, events, inserted, _wav = soap_controller(tmp_path, soap)
    assert not c.draft_soap("   ")
    assert c.draft_soap("編集した文字起こし")
    wait_for(lambda: c.state == "idle" and any(e[0] == "soap_result" for e in events))
    assert soap.calls == ["編集した文字起こし"] and inserted == []  # manual drafts are never inserted
    c.close()
    wait_for(lambda: c.state == "closed")

    def missing():
        from windows_client.soap import SoapError
        raise SoapError("soap_unavailable")
    events2 = []
    c2 = Controller({}, lambda *event: events2.append(event), None, model_locator=lambda: tmp_path,
                    soap_factory=lambda: SimpleNamespace(locate=missing))
    wait_for(lambda: c2.state == "idle")
    assert not c2.soap_ready and ("soap_status", "soap_unavailable") in events2
    assert not c2.draft_soap("text")
    c2.close()
    wait_for(lambda: c2.state == "closed")
