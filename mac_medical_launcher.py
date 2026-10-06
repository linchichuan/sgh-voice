#!/usr/bin/env python3
"""macOS entry point of the offline Japanese medical edition.

Reuses the Windows edition's local-only pieces (controller, Tk UI, bundled
speech model, SOAP drafting, WAV/MP3 import) with small macOS adapters:
copying uses pbcopy, nothing is typed into other applications, and there are
no global shortcuts. Settings live in ~/Library/Application Support/SGHVoice
Medical, separate from the personal SGH Voice menu-bar app.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

DATA_DIR = Path.home() / "Library" / "Application Support" / "SGHVoice Medical"


class MacNative:
    """Clipboard only. Automatic input into other applications is not offered."""

    def capture_target(self):
        return None

    def send_text(self, target, text):
        from types import SimpleNamespace
        return SimpleNamespace(success=False, reason="Automatic input is not available on macOS; use Copy.")

    def copy_text(self, text):
        if not isinstance(text, str) or not text or "\x00" in text:
            raise ValueError("nothing to copy")
        subprocess.run(["/usr/bin/pbcopy"], input=text.encode("utf-8"), check=True,
                       env={"LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8", "PATH": "/usr/bin:/bin"})
        return True


class NoHotkeys:
    def __init__(self, **_callbacks):
        pass

    def start(self, *_keys):
        raise RuntimeError("global shortcuts are not available on macOS in this edition")

    def stop(self):
        pass


def self_test(report_path):
    """Frozen packaging smoke test. No microphone, network or user data."""
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

        def gui_check():
            import tkinter
            from windows_client.controller import Controller, WINDOWS_DEFAULTS
            from windows_client.models import MODEL_INFO
            from windows_client.soap import LLM_INFO
            from windows_client.ui import WindowsApp
            root = tkinter.Tk()
            root.withdraw()
            app = WindowsApp(root, {**WINDOWS_DEFAULTS, "ui_language": "ja"}, controller_factory=Controller,
                             native=MacNative(), hotkeys_factory=NoHotkeys, save_config=lambda settings: None,
                             model_info=MODEL_INFO, llm_info=LLM_INFO, hotkeys_available=False)
            root.update_idletasks()
            app.close()
            root.mainloop()

        def audio_check():
            import numpy as np
            import soundfile
            from recorder import Recorder
            path = Recorder({"sample_rate": 16000})._save(np.zeros(8000, dtype=np.float32))
            try:
                data, rate = soundfile.read(path)
                assert rate == 16000 and len(data) == 8000
            finally:
                os.remove(path)

        def core_check():
            import config
            from windows_client.local_stt import enforce_offline_environment
            enforce_offline_environment()
            import ctranslate2
            from windows_client._vendor import faster_whisper
            assert "int8" in ctranslate2.get_supported_compute_types("cpu")
            assert faster_whisper.WhisperModel
            assert str(config.DATA_DIR) == profile

        def bundled_model_check():
            from windows_client.local_stt import validate_model_directory
            from windows_client.models import MANIFEST, bundled_model_dir
            folder = validate_model_directory(bundled_model_dir())
            for spec in MANIFEST["files"]:
                if (folder / spec["name"]).stat().st_size != spec["size"]:
                    raise RuntimeError("bundled model size differs from manifest")

        def bundled_llm_check():
            from windows_client.soap import SoapDrafter
            SoapDrafter(cache_dir=profile).locate()

        def clipboard_check():
            MacNative()  # pbcopy is part of macOS; not invoked here to keep the clipboard untouched
            assert Path("/usr/bin/pbcopy").exists()

        check("tk_ui", gui_check)
        check("wav_roundtrip", audio_check)
        check("shared_core", core_check)
        check("bundled_model", bundled_model_check)
        check("bundled_llm", bundled_llm_check)
        check("clipboard", clipboard_check)
        from config import APP_VERSION
        report = {"ok": all(checks.values()), "platform": sys.platform, "architecture": platform.machine(),
                  "version": APP_VERSION, "checks": checks, "errors": errors,
                  "microphone_tested": False, "local_inference_tested": False, "soap_tested": False}
    Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def run():
    import tkinter as tk
    from tkinter import messagebox

    from config import load_config, save_config
    from windows_client.controller import Controller, WINDOWS_DEFAULTS
    from windows_client.models import MODEL_INFO
    from windows_client.soap import LLM_INFO
    from windows_client.ui import LABELS, WindowsApp

    root = tk.Tk()
    root.withdraw()
    try:
        config = {**WINDOWS_DEFAULTS, "ui_language": "ja", **load_config()}
        WindowsApp(root, config, controller_factory=Controller, native=MacNative(),
                   hotkeys_factory=NoHotkeys, save_config=save_config, model_info=MODEL_INFO,
                   llm_info=LLM_INFO, hotkeys_available=False)
    except Exception:
        messagebox.showerror("SGH Voice", LABELS["ja"]["startup_failed"], parent=root)
        root.destroy()
        return 1
    root.mainloop()
    return 0


def main(argv=None):
    for stream in ("stdout", "stderr"):
        if getattr(sys, stream) is None:
            setattr(sys, stream, open(os.devnull, "w", encoding="utf-8"))
    os.environ.setdefault("SGHVOICE_DATA_DIR", str(DATA_DIR))
    parser = argparse.ArgumentParser(description="SGH Voice macOS offline edition")
    parser.add_argument("--self-test", metavar="REPORT_JSON")
    parser.add_argument("--offline-self-test", nargs=2, metavar=("MODEL_DIR", "REPORT_JSON"))
    parser.add_argument("--speech-set", metavar="CLIPS_JSON")
    parser.add_argument("--max-cer", type=float)
    parser.add_argument("--soap-transcript", metavar="TEXT_FILE")
    args, _unknown = parser.parse_known_args(argv)  # Finder may pass -psn_* arguments
    if args.self_test:
        return self_test(args.self_test)
    if args.offline_self_test:
        from windows_launcher import offline_self_test
        return offline_self_test(*args.offline_self_test, speech_set=args.speech_set,
                                 max_cer=args.max_cer, soap_transcript=args.soap_transcript)
    if sys.platform != "darwin":
        print("This launcher is for macOS.", file=sys.stderr)
        return 2
    return run()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    raise SystemExit(main())
