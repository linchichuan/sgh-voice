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


def self_test(report_path):
    """Frozen packaging smoke test. No credentials, microphone or network IO."""
    checks, errors = {}, []
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
            from windows_client.models import MODEL_INFO
            from windows_client.native import WindowsNative
            from windows_client.ui import WindowsApp
            root = tkinter.Tk()
            root.withdraw()
            app = WindowsApp(root, {**WINDOWS_DEFAULTS, "ui_language": "en"},
                             controller_factory=Controller, native=WindowsNative(),
                             hotkeys_factory=GlobalHotkeys, save_config=lambda settings: None,
                             validate_hotkey=Hotkey.parse, model_info=MODEL_INFO)
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
            Memory()
            assert config.DATA_DIR == profile or str(config.DATA_DIR) == profile

        def bundled_model_check():
            # Presence and pinned sizes only; offline-test.ps1 performs full hashing.
            from windows_client.models import MANIFEST, bundled_model_dir
            from windows_client.local_stt import validate_model_directory
            folder = validate_model_directory(bundled_model_dir())
            for spec in MANIFEST["files"]:
                if (folder / spec["name"]).stat().st_size != spec["size"]:
                    raise RuntimeError("bundled model size differs from manifest")

        check("windows_native", native_check)
        check("tk_ui", gui_check)
        check("wav_roundtrip", audio_check)
        check("credential_backend", credential_backend_check)
        check("shared_core", core_check)
        def bundled_llm_check():
            # Full SHA-256 of the pinned GGUF (cached in this throwaway profile) and runtime presence.
            from windows_client.soap import SoapDrafter
            SoapDrafter(cache_dir=profile).locate()

        check("bundled_model", bundled_model_check)
        check("bundled_llm", bundled_llm_check)
        from config import APP_VERSION
        report = {
            "ok": all(checks.values()), "platform": sys.platform,
            "architecture": platform.machine(), "version": APP_VERSION,
            "checks": checks, "errors": errors,
            "microphone_tested": False, "cloud_tested": False,
            "input_delivery_tested": False, "local_inference_tested": False,
            "recognition_mode": "local-only", "model_included": checks.get("bundled_model") is True,
            "llm_included": checks.get("bundled_llm") is True, "soap_tested": False,
        }
    Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def _normalized(text):
    import unicodedata
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(ch for ch in text
                   if not ch.isspace() and unicodedata.category(ch)[0] not in "PSZ")


def _edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def offline_self_test(model_directory, report_path, speech_set=None, max_cer=None, soap_transcript=None):
    """Exercise the bundled CPU decoder with Python network IO denied.

    MODEL_DIR "bundled" uses the installed model after a full SHA-256 check.
    Synthetic silence checks the runtime; an optional speech set (public,
    non-clinical WAV clips with reference text) checks Japanese recognition
    against a character-error-rate ceiling. Neither is a clinical accuracy claim.
    """
    import socket
    import time
    attempts = []
    original_connect, original_dns = socket.socket.connect, socket.getaddrinfo
    def denied(*args, **kwargs):
        attempts.append("blocked")
        raise OSError("Network is disabled during the offline runtime test")
    started = time.monotonic()
    report = {"ok": False, "kind": "offline-runtime" + ("+speech" if speech_set else ""),
              "platform": sys.platform, "architecture": platform.machine(),
              "microphone_tested": False, "accuracy_tested": bool(speech_set),
              "input_delivery_tested": False, "python_network_guard": True,
              "python_network_attempts": 0}
    try:
        socket.socket.connect, socket.getaddrinfo = denied, denied
        from windows_client.local_stt import LocalTranscriber
        from windows_client.models import MANIFEST, verified_model_dir
        import numpy as np
        import soundfile
        with tempfile.TemporaryDirectory(prefix="sghvoice-offline-") as folder:
            if model_directory == "bundled":
                hashed = time.monotonic()
                model_directory = str(verified_model_dir(cache_dir=folder))
                report["model_verified"] = MANIFEST["revision"]
                report["model_hash_seconds"] = round(time.monotonic() - hashed, 2)
            path = Path(folder) / "synthetic-silence.wav"
            soundfile.write(path, np.zeros(16000, dtype=np.float32), 16000, subtype="PCM_16")
            decoder = LocalTranscriber({"windows_model_dir": model_directory, "windows_language": "ja",
                                        "windows_decode_options": MANIFEST.get("decode", {})})
            loaded = time.monotonic()
            result = decoder.transcribe({"path": str(path)}, 1.0)
            report["first_inference_seconds"] = round(time.monotonic() - loaded, 2)
            report["local_inference_tested"] = True
            report["engine"] = result["engine"]
            ok = result["raw"] == result["final"]
            if speech_set:
                clips = json.loads(Path(speech_set).read_text(encoding="utf-8"))
                errors = characters = 0
                report["speech"] = []
                for clip in clips:
                    began = time.monotonic()
                    if clip.get("import"):
                        from windows_client.audio_import import convert_to_pcm16k
                        converted = Path(folder) / "imported.wav"
                        length = convert_to_pcm16k(Path(clip["wav"]).resolve(), converted)
                        text = decoder.transcribe({"path": str(converted)}, length, "file")["final"]
                        converted.unlink()
                    else:
                        text = decoder.transcribe({"path": str(Path(clip["wav"]).resolve())}, 0)["final"]
                    reference = _normalized(clip["reference"])
                    distance = _edit_distance(reference, _normalized(text))
                    errors += distance
                    characters += len(reference)
                    report["speech"].append({"reference": clip["reference"], "hypothesis": text,
                                             "imported": bool(clip.get("import")),
                                             "format": clip.get("format", "WAV"),
                                             "cer": round(distance / max(1, len(reference)), 4),
                                             "seconds": round(time.monotonic() - began, 2)})
                report["cer"] = round(errors / max(1, characters), 4)
                report["max_cer"] = max_cer
                ok = ok and bool(clips) and max_cer is not None and report["cer"] <= max_cer
            if soap_transcript:
                # The bundled llama.cpp child process drafts SOAP from a fictional transcript.
                from windows_client.soap import SoapDrafter, has_soap_headings
                transcript = Path(soap_transcript).read_text(encoding="utf-8")
                drafted = SoapDrafter(cache_dir=folder).draft(transcript)
                report["soap"] = {"text": drafted["text"], "unverified": drafted["unverified"],
                                  "seconds": drafted["seconds"], "transcript_chars": len(transcript),
                                  "headings": has_soap_headings(drafted["text"])}
                report["soap_tested"] = True
                ok = ok and report["soap"]["headings"]
            report["ok"] = ok and not attempts
    except Exception as exc:
        report["error"] = type(exc).__name__
        if getattr(exc, "code", None):
            report["error_code"] = exc.code
    finally:
        socket.socket.connect, socket.getaddrinfo = original_connect, original_dns
        report["python_network_attempts"] = len(attempts)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if report["ok"] else 1


def main(argv=None):
    # The windowed bootloader supplies no streams, including during self-test.
    for stream in ("stdout", "stderr"):
        if getattr(sys, stream) is None:
            setattr(sys, stream, open(os.devnull, "w", encoding="utf-8"))
    parser = argparse.ArgumentParser(description="SGH Voice Windows preview")
    parser.add_argument("--self-test", metavar="REPORT_JSON")
    parser.add_argument("--offline-self-test", nargs=2, metavar=("MODEL_DIR", "REPORT_JSON"))
    parser.add_argument("--speech-set", metavar="CLIPS_JSON")
    parser.add_argument("--max-cer", type=float)
    parser.add_argument("--soap-transcript", metavar="TEXT_FILE")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test(args.self_test)
    if args.offline_self_test:
        return offline_self_test(*args.offline_self_test, speech_set=args.speech_set, max_cer=args.max_cer,
                                 soap_transcript=args.soap_transcript)
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
