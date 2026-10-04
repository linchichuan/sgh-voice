"""Offline STT contracts using synthetic files and a fake native decoder.

These tests do not download a model or assert recognition accuracy. Native
Windows decoding and microphone acceptance remain separate release checks.
"""
import ast
import builtins
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import wave

import pytest

from windows_client.local_stt import (
    ENGINE, REQUIRED_MODEL_FILES, LocalSTTError, LocalTranscriber,
    validate_model_directory,
)


@pytest.fixture
def model_dir(tmp_path):
    path = tmp_path / "local-model"
    path.mkdir()
    (path / "model.bin").write_bytes(b"synthetic CT2 weights")
    (path / "config.json").write_text("{}", encoding="utf-8")
    (path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (path / "vocabulary.txt").write_text("synthetic", encoding="utf-8")
    return path


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "synthetic.wav"
    path.write_bytes(b"synthetic WAV: the fake decoder does not decode it")
    return path


@pytest.fixture
def backend():
    loads, decodes = [], []

    class Model:
        def __init__(self, path, **kwargs):
            loads.append((path, kwargs))

        def transcribe(self, path, **kwargs):
            decodes.append((path, kwargs))
            return iter([SimpleNamespace(text=" 薬は 0.5 mg、"),
                         SimpleNamespace(text="一日 2 回。 Windows! ")]), SimpleNamespace(language="ja")

    return SimpleNamespace(factory=Model, loads=loads, decodes=decodes)


def test_complete_local_bundle_validates(model_dir):
    assert validate_model_directory(model_dir) == model_dir.resolve()


@pytest.mark.parametrize("name", REQUIRED_MODEL_FILES)
def test_missing_model_files_block_before_engine(model_dir, name):
    (model_dir / name).unlink()
    with pytest.raises(LocalSTTError, match="^model_not_ready$"):
        LocalTranscriber({"windows_model_dir": str(model_dir)},
                         model_factory=lambda *a, **kw: pytest.fail("engine loaded"))


@pytest.mark.parametrize("name, contents", [
    ("model.bin", b""),
    ("model.bin", b"version https://git-lfs.github.com/spec/v1\noid sha256:fake"),
    ("config.json", b"not-json"),
    ("config.json", b"[]"),
    ("tokenizer.json", b"{broken"),
    ("preprocessor_config.json", b"{broken"),
])
def test_incomplete_or_corrupt_bundle_rejected(model_dir, name, contents):
    (model_dir / name).write_bytes(contents)
    with pytest.raises(LocalSTTError, match="^model_not_ready$"):
        validate_model_directory(model_dir)


@pytest.mark.parametrize("value", [
    "", None, "base", "Systran/faster-whisper-base", "./models/base",
    "https://huggingface.co/Systran/faster-whisper-base", "file:///models/base",
    r"\\server\private\model", "//server/private/model", r"C:relative-model",
])
def test_remote_ids_urls_and_relative_paths_rejected_without_filesystem_probe(monkeypatch, value):
    monkeypatch.setattr(Path, "resolve", lambda *a, **kw: pytest.fail("unexpected path probe"))
    with pytest.raises(LocalSTTError, match="^invalid_model_path$"):
        validate_model_directory(value)


def test_model_files_must_stay_inside_bundle(model_dir, tmp_path):
    target = tmp_path / "outside.json"
    target.write_text("{}", encoding="utf-8")
    (model_dir / "tokenizer.json").unlink()
    try:
        (model_dir / "tokenizer.json").symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable without additional OS privileges")
    with pytest.raises(LocalSTTError, match="^model_not_ready$"):
        validate_model_directory(model_dir)


def test_mapped_network_drive_rejected_before_resolving(monkeypatch, model_dir):
    from windows_client import local_stt
    monkeypatch.setattr(local_stt, "_drive_is_remote", lambda path: True)
    monkeypatch.setattr(Path, "resolve", lambda *a, **kw: pytest.fail("remote filesystem probed"))
    with pytest.raises(LocalSTTError, match="^invalid_model_path$"):
        validate_model_directory(model_dir)


def test_cpu_int8_local_only_model_cached_and_text_preserved(model_dir, wav, backend, monkeypatch):
    for name in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.setenv(name, "0")
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir),
                                   "windows_cpu_threads": 2}, model_factory=backend.factory)
    result = transcriber.transcribe({"array": object(), "path": str(wav)}, 1.0, "dictate")
    assert result == {"raw": "薬は 0.5 mg、一日 2 回。 Windows!",
                      "final": "薬は 0.5 mg、一日 2 回。 Windows!",
                      "language": "ja", "engine": ENGINE, "cancelled": False}
    assert backend.loads == [(str(model_dir), {"device": "cpu", "compute_type": "int8",
        "cpu_threads": 2, "num_workers": 1, "local_files_only": True})]
    assert backend.decodes[0] == (str(wav), {
        "language": "ja", "task": "transcribe", "beam_size": 5, "temperature": 0.0,
        "condition_on_previous_text": False, "vad_filter": False,
        "initial_prompt": None, "hotwords": None, "log_progress": False,
    })
    assert all(os.environ[name] == "1" for name in (
        "HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"))
    transcriber.transcribe(wav)
    assert len(backend.loads) == 1


@pytest.mark.parametrize("language, expected", [("auto", None), ("ja", "ja"), ("zh", "zh"), ("en", "en")])
def test_explicit_language_and_auto_detection(model_dir, wav, backend, language, expected):
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir),
                                   "windows_language": language}, model_factory=backend.factory)
    transcriber.transcribe(wav)
    assert backend.decodes[0][1]["language"] == expected


@pytest.mark.parametrize("config, code", [
    ({"windows_language": "invalid"}, "invalid_language"),
    ({"windows_cpu_threads": True}, "invalid_cpu_threads"),
    ({"windows_cpu_threads": 0}, "invalid_cpu_threads"),
    ({"windows_cpu_threads": 33}, "invalid_cpu_threads"),
    ({"windows_cpu_threads": "4"}, "invalid_cpu_threads"),
])
def test_invalid_options_fail_before_engine(model_dir, config, code):
    with pytest.raises(LocalSTTError, match=f"^{code}$"):
        LocalTranscriber({"windows_model_dir": str(model_dir), **config})


def test_no_cloud_or_shared_transcriber_imported(model_dir, wav, backend, monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"transcriber", "openai", "anthropic", "groq", "memory"}:
            pytest.fail(f"unexpected cloud/shared pipeline import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    telemetry_disabled = []
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(
        disable_telemetry_events=lambda: telemetry_disabled.append(True)))
    monkeypatch.setitem(sys.modules, "windows_client._vendor.faster_whisper",
                        SimpleNamespace(WhisperModel=backend.factory))
    result = LocalTranscriber({"windows_model_dir": str(model_dir),
                               "groq_api_key": "must-not-be-used"}).transcribe(wav)
    assert result["final"]
    assert telemetry_disabled == [True]


def test_missing_runtime_reports_stable_code_without_fallback(model_dir, wav, monkeypatch):
    monkeypatch.setitem(sys.modules, "onnxruntime", None)
    with pytest.raises(LocalSTTError, match="^local_runtime_missing$"):
        LocalTranscriber({"windows_model_dir": str(model_dir)}).transcribe(wav)


def test_bundle_revalidated_before_lazy_load(model_dir, wav, backend):
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir)}, model_factory=backend.factory)
    (model_dir / "tokenizer.json").unlink()
    with pytest.raises(LocalSTTError, match="^model_not_ready$"):
        transcriber.transcribe(wav)
    assert not backend.loads


@pytest.mark.parametrize("audio", [None, {}, "https://example.com/private.wav", r"\\server\audio.wav", "relative.wav"])
def test_audio_is_local_file_and_never_url(model_dir, backend, audio):
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir)}, model_factory=backend.factory)
    with pytest.raises(LocalSTTError, match="^audio_unavailable$"):
        transcriber.transcribe(audio)
    assert not backend.loads


def test_translate_mode_is_not_available(model_dir, wav, backend):
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir)}, model_factory=backend.factory)
    with pytest.raises(LocalSTTError, match="^invalid_mode$"):
        transcriber.transcribe(wav, mode="translate")
    assert not backend.loads


def test_cancel_before_start_does_not_load_or_read_audio(model_dir, backend):
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir)}, model_factory=backend.factory)
    assert transcriber.transcribe(None, should_cancel=lambda: True)["cancelled"]
    assert not backend.loads


def test_cancel_during_segment_iteration_discards_partial_text_and_closes(model_dir, wav):
    state = {"cancelled": False, "closed": False}

    def segments():
        try:
            yield SimpleNamespace(text="must not escape")
            state["cancelled"] = True
            yield SimpleNamespace(text="or this")
        finally:
            state["closed"] = True

    model = SimpleNamespace(transcribe=lambda *a, **kw: (segments(), SimpleNamespace(language="en")))
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir)}, model_factory=lambda *a, **kw: model)
    result = transcriber.transcribe(wav, should_cancel=lambda: state["cancelled"])
    assert result["cancelled"] and result["final"] == result["raw"] == ""
    assert state["closed"]


@pytest.mark.parametrize("fail_during_load", [True, False])
def test_backend_errors_are_sanitized_and_no_fallback(model_dir, wav, fail_during_load):
    def failure(*args, **kwargs):
        raise RuntimeError("sensitive transcript /private/audio.wav secret-key")

    factory = failure if fail_during_load else lambda *a, **kw: SimpleNamespace(transcribe=failure)
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir)}, model_factory=factory)
    with pytest.raises(LocalSTTError) as error:
        transcriber.transcribe(wav)
    expected = "local_model_load_failed" if fail_during_load else "local_transcription_failed"
    assert str(error.value) == error.value.code == expected


def test_lazy_decoder_failure_discards_partial_text(model_dir, wav):
    def segments():
        yield SimpleNamespace(text="must not escape")
        raise RuntimeError("private transcript and audio path")

    model = SimpleNamespace(transcribe=lambda *a, **kw: (segments(), SimpleNamespace(language="ja")))
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir)}, model_factory=lambda *a, **kw: model)
    with pytest.raises(LocalSTTError, match="^local_transcription_failed$"):
        transcriber.transcribe(wav)


def test_cleanup_error_does_not_leak_on_cancellation(model_dir, wav):
    state = {"cancelled": False}

    class Segments:
        def __iter__(self):
            state["cancelled"] = True
            yield SimpleNamespace(text="private transcript")
        def close(self):
            raise RuntimeError("private decoder details")

    model = SimpleNamespace(transcribe=lambda *a, **kw: (Segments(), SimpleNamespace(language="ja")))
    transcriber = LocalTranscriber({"windows_model_dir": str(model_dir)}, model_factory=lambda *a, **kw: model)
    assert transcriber.transcribe(wav, should_cancel=lambda: state["cancelled"])["final"] == ""


@pytest.fixture
def pcm_frontend():
    # Exercise the actual frontend independently of uninstalled native CT2/ORT.
    path = Path(__file__).resolve().parents[1] / "windows_client/_vendor/faster_whisper/audio.py"
    spec = importlib.util.spec_from_file_location("sghvoice_test_pcm_frontend", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pcm_wave(samples, *, rate=16000, channels=1, width=2):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as recording:
        recording.setnchannels(channels)
        recording.setsampwidth(width)
        recording.setframerate(rate)
        recording.writeframes(samples)
    stream.seek(0)
    return stream


def test_real_pcm_wav_decoder_normalizes_samples_and_preserves_order(pcm_frontend):
    import numpy as np
    values = np.array([-32768, -16384, 0, 16384, 32767], dtype="<i2")
    decoded = pcm_frontend.decode_audio(pcm_wave(values.tobytes()))
    assert decoded.dtype == np.float32
    np.testing.assert_array_equal(decoded, values.astype(np.float32) / 32768.0)


def test_recorder_soundfile_default_format_is_supported(pcm_frontend, tmp_path):
    import numpy as np
    import soundfile
    path = tmp_path / "recorded.wav"
    soundfile.write(str(path), np.zeros(16000, dtype=np.float32), 16000)
    assert soundfile.info(str(path)).subtype == "PCM_16"
    decoded = pcm_frontend.decode_audio(path)
    assert decoded.shape == (16000,) and not decoded.any()


@pytest.mark.parametrize("options", [
    {"rate": 8000}, {"rate": 48000}, {"channels": 2}, {"width": 1}, {"width": 3},
])
def test_wav_decoder_rejects_unimplemented_formats_without_resampling(pcm_frontend, options):
    with pytest.raises(ValueError, match="Only 16 kHz mono PCM16"):
        pcm_frontend.decode_audio(pcm_wave(b"\0" * 12, **options))


@pytest.mark.parametrize("content", [b"#EXTM3U\nhttps://example.invalid/audio.mp3", b"OggS", b"not audio"])
def test_wav_decoder_cannot_open_general_media_or_playlist(pcm_frontend, content):
    with pytest.raises((wave.Error, EOFError)):
        pcm_frontend.decode_audio(io.BytesIO(content))


def test_wav_decoder_rejects_empty_and_truncated_recordings(pcm_frontend):
    with pytest.raises(ValueError, match="empty or incomplete"):
        pcm_frontend.decode_audio(pcm_wave(b""))
    stream = pcm_wave(b"\0" * 100)
    with pytest.raises(ValueError, match="empty or incomplete"):
        pcm_frontend.decode_audio(io.BytesIO(stream.getvalue()[:-1]))


def test_wav_decoder_rejects_external_paths_before_open(pcm_frontend, monkeypatch):
    monkeypatch.setattr(pcm_frontend.wave, "open", lambda *a, **kw: pytest.fail("media opened"))
    for value in ("https://example.invalid/audio.wav", r"\\server\audio.wav", "audio.wav"):
        with pytest.raises(ValueError, match="local absolute"):
            pcm_frontend.decode_audio(value)


def test_wav_decoder_rejects_unimplemented_output_options(pcm_frontend):
    for options in ({"sampling_rate": 8000}, {"split_stereo": True}):
        with pytest.raises(ValueError, match="Only 16 kHz mono PCM16"):
            pcm_frontend.decode_audio(pcm_wave(b"\0" * 10), **options)


def test_vendored_files_match_recorded_provenance_and_only_expected_patches():
    root = Path(__file__).resolve().parents[1] / "windows_client/_vendor/faster_whisper"
    manifest = json.loads((root / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert manifest["commit"] == "65882eee9f5cdbeeb2d877f1131d48cf241b327d"
    patched = set()
    for entry in manifest["files"]:
        content = (root / entry["path"]).read_bytes()
        current = hashlib.sha256(content).hexdigest()
        assert current == entry["vendored_sha256"], entry["path"]
        if current != entry["upstream_sha256"]:
            patched.add(entry["path"])
        if entry["path"].endswith(".py"):
            for node in ast.walk(ast.parse(content)):
                if isinstance(node, ast.Import):
                    assert all(n.name.split(".")[0] != "av" for n in node.names)
                elif isinstance(node, ast.ImportFrom):
                    assert (node.module or "").split(".")[0] != "av"
            assert b"from faster_whisper." not in content
    assert patched == {"__init__.py", "audio.py", "transcribe.py", "utils.py", "vad.py"}
    assert (root / "assets/silero_vad_v6.onnx").stat().st_size == 1245151
    assert "Copyright (c) 2023 SYSTRAN" in (root / "LICENSE").read_text(encoding="utf-8")
    assert "Copyright (c) 2020-present Silero Team" in (root / "LICENSE.silero-vad").read_text(encoding="utf-8")


def test_vendored_implicit_model_download_is_disabled():
    path = Path(__file__).resolve().parents[1] / "windows_client/_vendor/faster_whisper/utils.py"
    spec = importlib.util.spec_from_file_location("sghvoice_test_offline_utils", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for value in ("base", "Systran/faster-whisper-base", "/missing/local/model"):
        with pytest.raises(RuntimeError, match="^SGHVoice model setup required$"):
            module.download_model(value, local_files_only=False)
    source = path.with_name("transcribe.py").read_text(encoding="utf-8")
    assert "Tokenizer.from_pretrained" not in source
    assert 'raise RuntimeError("SGHVoice local tokenizer.json required")' in source


def test_actual_vendor_import_and_missing_tokenizer_guard_without_av(tmp_path):
    # Isolate imported modules: use real Python/tokenizers/NumPy source and a
    # test-only CT2 boundary, never a fake av module or a shipped runtime shim.
    script = r'''
import builtins
import socket
import sys
from types import SimpleNamespace

def denied(*args, **kwargs):
    raise AssertionError("network activity attempted")
socket.create_connection = denied
socket.socket.connect = denied
real_import = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split(".")[0] in {"av", "faster_whisper"}:
        raise AssertionError("external decoder package imported")
    return real_import(name, *args, **kwargs)
builtins.__import__ = guarded
sys.modules["ctranslate2"] = SimpleNamespace(
    StorageView=type("StorageView", (), {}),
    models=SimpleNamespace(
        Whisper=lambda *args, **kwargs: SimpleNamespace(is_multilingual=True),
        WhisperGenerationResult=type("WhisperGenerationResult", (), {}),
    ),
)
from windows_client._vendor.faster_whisper import WhisperModel
for path, expected in [
    ("base", "SGHVoice model setup required"),
    (sys.argv[1], "SGHVoice local tokenizer.json required"),
]:
    try:
        WhisperModel(path, device="cpu", compute_type="int8", local_files_only=True)
    except RuntimeError as error:
        assert str(error) == expected
    else:
        raise AssertionError("incomplete model unexpectedly accepted")
print("vendor import and fail-closed guards passed")
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[1],
                            text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "fail-closed guards passed" in result.stdout
