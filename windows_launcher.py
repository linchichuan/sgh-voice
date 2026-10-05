#!/usr/bin/env python3
"""Windows entry point; never imports the macOS menu-bar application."""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
from pathlib import Path


def cloud_mock_check(evidence):
    """Exercise the packaged HTTP adapter with synthetic data and blocked sockets.

    The MockTransport consumes a real multipart request in memory. No saved
    settings or credentials are loaded, and no provider endpoint is contacted.
    """
    import socket
    import ssl
    import wave
    from email import policy
    from email.parser import BytesParser

    attempts, requests = [], []
    guarded = [(socket.socket, "connect"), (socket.socket, "connect_ex"),
               (socket, "create_connection"), (socket, "getaddrinfo")]
    originals = [(owner, name, getattr(owner, name)) for owner, name in guarded]

    def denied(*args, **kwargs):
        attempts.append("blocked")
        raise OSError("Network is disabled during the cloud adapter mock test")

    try:
        for owner, name in guarded:
            setattr(owner, name, denied)
        evidence["cloud_mock_python_network_guard"] = True
        import certifi
        import httpx
        from windows_client.cloud_stt import CloudTranscriber

        # MockTransport itself does not exercise TLS; separately verify that the
        # frozen app can load its bundled public CA certificates without network IO.
        ssl.create_default_context(cafile=certifi.where())
        synthetic_key = "sghvoice-self-test-synthetic-key"
        text = "SGH Voice synthetic adapter test."
        with tempfile.TemporaryDirectory(prefix="sghvoice-cloud-mock-") as folder:
            wav = Path(folder) / "synthetic-silence.wav"
            with wave.open(str(wav), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\0\0" * 16000)
            wav_bytes = wav.read_bytes()

            def handle(request):
                assert request.method == "POST"
                assert str(request.url) == "https://api.openai.com/v1/audio/transcriptions"
                assert request.headers["authorization"] == "Bearer " + synthetic_key
                body = request.read()
                header = ("Content-Type: " + request.headers["content-type"] + "\r\n\r\n").encode("ascii")
                message = BytesParser(policy=policy.default).parsebytes(header + body)
                fields = {part.get_param("name", header="content-disposition"): part
                          for part in message.iter_parts()}
                assert fields["model"].get_payload(decode=True) == b"whisper-1"
                assert fields["file"].get_payload(decode=True) == wav_bytes
                assert synthetic_key.encode() not in body
                requests.append("mock")
                return httpx.Response(200, json={"text": text})

            decoder = CloudTranscriber({
                "windows_recognition_mode": "openai-cloud", "windows_cloud_consent": True,
                "openai_api_key": synthetic_key, "windows_language": "en",
            }, transport=httpx.MockTransport(handle))
            result = decoder.transcribe({"path": str(wav)}, duration=1.0)
            assert result["raw"] == result["final"] == text
            assert result["engine"] == "openai-whisper-1"
        if requests != ["mock"] or attempts:
            raise RuntimeError("Expected one mock request with zero Python network attempts")
    finally:
        for owner, name, original in originals:
            setattr(owner, name, original)
        evidence["cloud_mock_python_network_attempts"] = len(attempts)


def self_test(report_path):
    """Frozen packaging smoke test. No credentials, microphone or network IO."""
    checks, errors = {}, []
    cloud_evidence = {"cloud_mock_python_network_guard": False,
                      "cloud_mock_python_network_attempts": 0}
    with tempfile.TemporaryDirectory(prefix="sghvoice-smoke-") as profile:
        os.environ["SGHVOICE_DATA_DIR"] = profile
        def check(name, action):
            try:
                action()
                checks[name] = True
            except Exception as exc:
                checks[name] = False
                errors.append({"check": name, "error": type(exc).__name__})

        def native_check():
            if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
                raise RuntimeError("Windows x64 required")
            from windows_client.native import WindowsNative
            WindowsNative()

        def gui_check():
            import tkinter
            from windows_client.controller import Controller, WINDOWS_DEFAULTS
            from windows_client.hotkeys import GlobalHotkeys, Hotkey
            from windows_client.models import MODEL_DOWNLOAD_INFO
            from windows_client.native import WindowsNative
            from windows_client.ui import WindowsApp
            root = tkinter.Tk()
            root.withdraw()
            app = WindowsApp(root, {**WINDOWS_DEFAULTS, "ui_language": "en"},
                             controller_factory=Controller, native=WindowsNative(),
                             hotkeys_factory=GlobalHotkeys, save_config=lambda settings: None,
                             validate_hotkey=Hotkey.parse, model_info=MODEL_DOWNLOAD_INFO)
            root.update_idletasks()
            app.close()
            root.mainloop()

        def audio_check():
            import numpy as np
            from recorder import Recorder
            import soundfile
            recorder = Recorder({"sample_rate": 16000})
            path = recorder._save(np.zeros(8000, dtype=np.float32))
            if not path:
                raise RuntimeError("WAV could not be written")
            try:
                data, sr = soundfile.read(path)
                assert sr == 16000 and len(data) == 8000
            finally:
                os.remove(path)

        def credential_backend_check():
            import keyring
            from keyring.backends.Windows import WinVaultKeyring
            if not isinstance(keyring.get_keyring(), WinVaultKeyring):
                raise RuntimeError("Windows credential vault unavailable")

        def core_check():
            import config
            from memory import Memory
            from windows_client.controller import WINDOWS_DEFAULTS
            from windows_client.local_stt import enforce_offline_environment
            enforce_offline_environment()
            import ctranslate2
            import onnxruntime
            onnxruntime.disable_telemetry_events()
            from windows_client._vendor import faster_whisper
            from opencc import OpenCC
            assert OpenCC("s2twp").convert("语音") == "語音"
            assert "int8" in ctranslate2.get_supported_compute_types("cpu")
            assert faster_whisper.WhisperModel
            assert WINDOWS_DEFAULTS["windows_recognition_mode"] == "local"
            Memory()
            assert config.DATA_DIR == profile or str(config.DATA_DIR) == profile

        check("windows_native", native_check)
        check("tk_ui", gui_check)
        check("wav_roundtrip", audio_check)
        check("credential_backend", credential_backend_check)
        check("shared_core", core_check)
        check("cloud_mock", lambda: cloud_mock_check(cloud_evidence))
        from config import APP_VERSION
        report = {
            "ok": all(checks.values()), "platform": sys.platform,
            "architecture": platform.machine(), "version": APP_VERSION,
            "checks": checks, "errors": errors,
            "microphone_tested": False, "cloud_live_tested": False,
            "cloud_mock_tested": checks["cloud_mock"], **cloud_evidence,
            "input_delivery_tested": False, "local_inference_tested": False,
            "default_recognition_mode": "local",
            "available_recognition_modes": ["local", "openai-cloud"], "model_included": False,
        }
    Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def offline_self_test(model_directory, report_path):
    """Exercise the bundled CPU decoder on synthetic silence with Python IO denied.

    This is a runtime/network-guard check, never a speech accuracy benchmark.
    """
    import socket
    import time
    attempts = []
    original_connect, original_dns = socket.socket.connect, socket.getaddrinfo
    def denied(*args, **kwargs):
        attempts.append("blocked")
        raise OSError("Network is disabled during the offline runtime test")
    started = time.monotonic()
    report = {"ok": False, "kind": "synthetic-silence-offline-runtime",
              "platform": sys.platform, "architecture": platform.machine(),
              "microphone_tested": False, "accuracy_tested": False,
              "input_delivery_tested": False, "python_network_guard": True,
              "python_network_attempts": 0}
    try:
        socket.socket.connect, socket.getaddrinfo = denied, denied
        from windows_client.local_stt import LocalTranscriber
        import numpy as np
        import soundfile
        with tempfile.TemporaryDirectory(prefix="sghvoice-offline-") as folder:
            path = Path(folder) / "synthetic-silence.wav"
            soundfile.write(path, np.zeros(16000, dtype=np.float32), 16000, subtype="PCM_16")
            decoder = LocalTranscriber({"windows_model_dir": model_directory, "windows_language": "ja"})
            result = decoder.transcribe({"path": str(path)}, 1.0)
            report["local_inference_tested"] = True
            report["engine"] = result["engine"]
            report["ok"] = (result["raw"] == result["final"] and not attempts)
    except Exception as exc:
        report["error"] = type(exc).__name__
    finally:
        socket.socket.connect, socket.getaddrinfo = original_connect, original_dns
        report["python_network_attempts"] = len(attempts)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def main(argv=None):
    # The windowed bootloader supplies no streams, including during self-test.
    for stream in ("stdout", "stderr"):
        if getattr(sys, stream) is None:
            setattr(sys, stream, open(os.devnull, "w", encoding="utf-8"))
    parser = argparse.ArgumentParser(description="SGH Voice Windows preview")
    parser.add_argument("--self-test", metavar="REPORT_JSON")
    parser.add_argument("--offline-self-test", nargs=2, metavar=("MODEL_DIR", "REPORT_JSON"))
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test(args.self_test)
    if args.offline_self_test:
        return offline_self_test(*args.offline_self_test)
    if sys.platform != "win32":
        print("SGH Voice Windows requires Windows x64.", file=sys.stderr)
        return 2
    # PyInstaller's windowed bootloader sets stdout/stderr to None. Shared core
    # diagnostics are intentionally discarded, never persisted as raw logs.
    from windows_client.ui import run
    return run()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
