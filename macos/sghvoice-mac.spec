# -*- mode: python ; coding: utf-8 -*-
"""macOS arm64 .app for the offline Japanese medical edition. Build with macos/build-medical.sh."""
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, collect_submodules

if sys.platform != "darwin":
    raise SystemExit("macOS packaging requires a macOS builder.")

root = Path(SPECPATH).parent
datas = [
    (str(root / "medical_dictionary_seed"), "medical_dictionary_seed"),
    (str(root / "resources" / "windows"), "resources/windows"),
]
binaries = []
hiddenimports = [
    "windows_client", "windows_client.local_stt", "windows_client.models", "windows_client.audio_import",
    "windows_client.soap", "windows_client.controller", "windows_client.ui", "windows_client.lexicon",
    "windows_client._vendor.faster_whisper", "windows_launcher",
    "config", "hotkey_config", "recorder", "memory", "medical_dictionary", "multilingual",
    "dictation_cleanup", "event_ledger", "tkinter", "tkinter.ttk", "tkinter.messagebox",
    "tkinter.filedialog", "ctranslate2._ext", "ctranslate2.models", "tokenizers.tokenizers",
]
for package in ("sounddevice", "soundfile"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
datas += collect_data_files("windows_client._vendor.faster_whisper")
hiddenimports += collect_submodules("windows_client._vendor.faster_whisper")
for package in ("ctranslate2", "tokenizers", "onnxruntime"):
    binaries += collect_dynamic_libs(package)
datas += collect_data_files("onnxruntime", includes=["LICENSE", "ThirdPartyNotices.txt"])

a = Analysis(
    [str(root / "mac_medical_launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["rumps", "AppKit", "Foundation", "Quartz", "objc", "mlx", "mlx_whisper", "mlx_audio",
              "torch", "torchaudio", "transformers", "av", "faster_whisper", "openai", "anthropic",
              "groq", "transcriber", "translation", "ollama_detector", "webview", "app", "dashboard",
              "overlay", "keyring", "pytest", "ruff", "ctranslate2.converters", "ctranslate2.specs"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SGH Voice", debug=False, strip=False,
          upx=False, console=False, argv_emulation=False, target_arch="arm64")
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SGHVoice")
app = BUNDLE(
    coll,
    name="SGH Voice Medical.app",
    bundle_identifier="com.shingihou.sghvoice.medical",
    info_plist={
        "CFBundleName": "SGH Voice Medical",
        "CFBundleDisplayName": "SGH Voice Medical",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "診察中の会話をこの Mac の中だけで文字起こしするためにマイクを使用します。音声は外部に送信されません。",
    },
)
