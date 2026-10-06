"""Offline WAV/MP3 import conversion: synthetic tones only, no network."""
import numpy as np
import pytest
import soundfile

from windows_client import audio_import
from windows_client.audio_import import AudioImportError, convert_to_pcm16k, inspect


def tone(path, rate, seconds, freq=1000.0, channels=1, fmt="WAV", subtype="PCM_16"):
    samples = 0.3 * np.sin(2 * np.pi * freq * np.arange(int(rate * seconds)) / rate).astype("float32")
    if channels > 1:
        samples = np.stack([samples] * channels, axis=1)
    soundfile.write(str(path), samples, rate, format=fmt, subtype=subtype)
    return path


@pytest.mark.parametrize("name,rate,channels,fmt,subtype", [
    ("phone.mp3", 44100, 2, "MP3", "MPEG_LAYER_III"),
    ("recorder.wav", 48000, 1, "WAV", "PCM_16"),
    ("call.wav", 8000, 1, "WAV", "PCM_16"),
    ("float.wav", 22050, 2, "WAV", "FLOAT"),
])
def test_conversion_to_16k_mono_pcm16_preserves_duration_and_pitch(tmp_path, name, rate, channels, fmt, subtype):
    source = tone(tmp_path / name, rate, 65, channels=channels, fmt=fmt, subtype=subtype)
    target = tmp_path / "out.wav"
    progress = []
    duration = convert_to_pcm16k(source, target, on_progress=progress.append)
    info = soundfile.info(str(target))
    assert (info.samplerate, info.channels, info.subtype, info.format) == (16000, 1, "PCM_16", "WAV")
    assert abs(duration - 65) < 0.01
    audio, _ = soundfile.read(str(target))
    spectrum = np.abs(np.fft.rfft(audio[16000:32000]))
    assert int(np.argmax(spectrum)) == 1000
    assert progress[-1] == 1.0 and progress == sorted(progress)


def test_frequencies_above_target_nyquist_are_filtered_not_aliased(tmp_path):
    source = tone(tmp_path / "hf.wav", 48000, 5, freq=12000)
    target = tmp_path / "out.wav"
    convert_to_pcm16k(source, target)
    audio, _ = soundfile.read(str(target))
    assert float(np.sqrt(np.mean(audio[1600:-1600] ** 2))) < 0.003  # ~ -40 dB below the 0.21 rms input


@pytest.mark.parametrize("name,content,code", [
    ("voice.m4a", b"x", "audio_format_unsupported"),
    ("empty.wav", b"", "audio_file_empty"),
    ("broken.mp3", b"ID3 not really audio", "audio_file_unreadable"),
    ("fake.wav", b"RIFF....not a wav", "audio_file_unreadable"),
])
def test_unsupported_or_damaged_files_raise_stable_codes(tmp_path, name, content, code):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(AudioImportError, match=code):
        convert_to_pcm16k(path, tmp_path / "out.wav")
    assert not (tmp_path / "out.wav").exists()


def test_mp3_named_wav_is_rejected_as_format_mismatch(tmp_path):
    source = tone(tmp_path / "real.mp3", 44100, 1, fmt="MP3", subtype="MPEG_LAYER_III")
    renamed = source.rename(tmp_path / "renamed.wav")
    with pytest.raises(AudioImportError, match="audio_format_unsupported"):
        inspect(renamed)


def test_too_long_recordings_are_refused_before_decoding(tmp_path, monkeypatch):
    source = tone(tmp_path / "long.wav", 16000, 3)
    monkeypatch.setattr(audio_import, "MAX_SECONDS", 2)
    with pytest.raises(AudioImportError, match="audio_file_too_long"):
        convert_to_pcm16k(source, tmp_path / "out.wav")


def test_cancel_removes_partial_output(tmp_path):
    source = tone(tmp_path / "rec.wav", 48000, 70)
    target = tmp_path / "out.wav"
    with pytest.raises(AudioImportError, match="cancelled"):
        convert_to_pcm16k(source, target, should_cancel=lambda: True)
    assert not target.exists()


def test_module_has_no_network_or_external_decoder():
    source = (audio_import.__file__ and open(audio_import.__file__, encoding="utf-8").read())
    for forbidden in ("urllib", "socket", "subprocess", "ffmpeg", "av."):
        assert forbidden not in source
