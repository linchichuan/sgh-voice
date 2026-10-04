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
            root = tkinter.Tk()
            root.withdraw()
            root.update_idletasks()
            root.destroy()

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
            from transcriber import Transcriber
            from opencc import OpenCC
            assert OpenCC("s2twp").convert("语音") == "語音"
            Transcriber(config.DEFAULT_CONFIG.copy(), Memory())

        check("windows_native", native_check)
        check("tk_ui", gui_check)
        check("wav_roundtrip", audio_check)
        check("credential_backend", credential_backend_check)
        check("shared_core", core_check)
        from config import APP_VERSION
        report = {
            "ok": all(checks.values()), "platform": sys.platform,
            "architecture": platform.machine(), "version": APP_VERSION,
            "checks": checks, "errors": errors,
            "microphone_tested": False, "cloud_tested": False,
            "input_delivery_tested": False,
        }
    Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def main(argv=None):
    # The windowed bootloader supplies no streams, including during self-test.
    for stream in ("stdout", "stderr"):
        if getattr(sys, stream) is None:
            setattr(sys, stream, open(os.devnull, "w", encoding="utf-8"))
    parser = argparse.ArgumentParser(description="SGH Voice Windows preview")
    parser.add_argument("--self-test", metavar="REPORT_JSON")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test(args.self_test)
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
