# -*- mode: python ; coding: utf-8 -*-
"""Windows x64 onedir bundle. Build from repository root on Windows only."""
import os
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

if sys.platform != "win32":
    raise SystemExit("Windows packaging requires a Windows builder; cross-compiling is unsupported.")

root = Path(SPECPATH).parent
datas = [(str(root / "medical_dictionary_seed"), "medical_dictionary_seed")]
binaries = []
hiddenimports = [
    "windows_client", "config", "hotkey_config", "recorder", "transcriber",
    "memory", "medical_dictionary", "multilingual", "dictation_cleanup",
    "translation", "event_ledger", "ollama_detector", "voiceprint",
    "tkinter", "tkinter.ttk", "tkinter.messagebox", "keyring.backends.Windows",
    "win32ctypes.pywin32.win32cred", "anyio._backends._asyncio",
]
for package in ("sounddevice", "soundfile", "opencc"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
datas += collect_data_files("certifi")
datas += copy_metadata("keyring")
build_info = os.environ.get("SGH_WINDOWS_BUILD_INFO")
if not build_info or not Path(build_info).is_file():
    raise SystemExit("Use windows/build.ps1 to provide verified source build metadata.")
datas.append((build_info, "."))

a = Analysis(
    [str(root / "windows_launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["rumps", "AppKit", "Foundation", "Quartz", "objc", "mlx",
              "mlx_whisper", "mlx_audio", "torch", "webview", "app",
              "dashboard", "overlay", "pytest", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="SGH Voice", debug=False, strip=False, upx=False, console=False,
    uac_admin=False, uac_uiaccess=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SGHVoice")
