# -*- mode: python ; coding: utf-8 -*-
"""Windows x64 onedir bundle. Build from repository root on Windows only."""
import os
from pathlib import Path
import re
import sys

from PyInstaller.utils.hooks import (
    collect_all, collect_data_files, collect_dynamic_libs, collect_submodules,
    copy_metadata,
)

if sys.platform != "win32":
    raise SystemExit("Windows packaging requires a Windows builder; cross-compiling is unsupported.")

root = Path(SPECPATH).parent
datas = [
    (str(root / "medical_dictionary_seed"), "medical_dictionary_seed"),
    (str(root / "resources" / "windows"), "resources/windows"),
]
binaries = []
hiddenimports = [
    "windows_client", "windows_client.local_stt", "windows_client.models",
    "windows_client.lexicon", "windows_client._vendor.faster_whisper",
    "config", "hotkey_config", "recorder",
    "memory", "medical_dictionary", "multilingual", "dictation_cleanup",
    "event_ledger",
    "tkinter", "tkinter.ttk", "tkinter.messagebox", "keyring.backends.Windows",
    "win32ctypes.pywin32.win32cred", "anyio._backends._asyncio",
    "ctranslate2._ext", "ctranslate2.models", "tokenizers.tokenizers",
    "onnxruntime.capi.onnxruntime_pybind11_state",
]
for package in ("sounddevice", "soundfile", "opencc"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
datas += collect_data_files("certifi")
# Retain the fork's VAD data, full MIT/Silero license and provenance records.
# It decodes our PCM16 WAV files directly and does not import PyAV/FFmpeg.
datas += collect_data_files("windows_client._vendor.faster_whisper")
hiddenimports += collect_submodules("windows_client._vendor.faster_whisper")


def is_gpu_library(path):
    normalized = str(path).replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    return (name.startswith(("cudnn", "cublas", "cudart", "cuda", "nvrtc", "nvjitlink", "hip", "rocblas"))
            or any(part in {"nvidia", "cupy", "_rocm_sdk_core", "_rocm_sdk_libraries_custom"}
                   for part in normalized.split("/")))


def is_ffmpeg_library(path):
    normalized = str(path).replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    return (name.startswith(("avcodec", "avdevice", "avfilter", "avformat", "avutil", "swresample", "swscale", "libx264", "libx265", "ffmpeg"))
            or any(part in {"av", "av.libs"} for part in normalized.split("/")))


# The official CT2 4.8.2 wheel includes optional cudnn64_9.dll. Static inspection
# of its x64 PE normal/delay imports confirms the CPU DLL does not depend on it.
# Keep CT2's CPU DLL + Intel OpenMP, and let PyInstaller resolve their VC runtime.
for package in ("ctranslate2", "tokenizers", "onnxruntime"):
    binaries += [item for item in collect_dynamic_libs(package) if not is_gpu_library(item[0])]
datas += collect_data_files("onnxruntime", includes=["LICENSE", "ThirdPartyNotices.txt"])

# Distribution metadata directories contain upstream LICENSE/NOTICE files as
# well as versions needed by importlib.metadata. Include every runtime pin,
# never build/test-tool metadata. No recursive collection of optional extras.
runtime_lock = (root / "requirements-windows.txt").read_text(encoding="utf-8")
for distribution in re.findall(r"^([A-Za-z0-9_.-]+)==", runtime_lock, re.MULTILINE):
    datas += copy_metadata(distribution)
for relative in ("LICENSE.txt", "tcl/tcl8.6/license.terms", "tcl/tk8.6/license.terms"):
    license_path = Path(sys.base_prefix) / relative
    if license_path.is_file():
        datas.append((str(license_path), "licenses/python/" + str(Path(relative).parent)))
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
              "mlx_whisper", "mlx_audio", "torch", "torchaudio", "transformers",
              "ctranslate2.converters", "ctranslate2.specs", "av", "faster_whisper",
              "openai", "anthropic", "transcriber", "translation", "ollama_detector",
              "nvidia", "cupy", "_rocm_sdk_core", "_rocm_sdk_libraries_custom",
              "webview", "app", "dashboard", "overlay", "pytest", "ruff"],
    noarchive=False,
)
# Hooks/binary analysis must not reintroduce optional GPU libraries. No system
# redistributable installation is performed; missing CPU/VC DLLs fail the build.
a.binaries = [item for item in a.binaries if not is_gpu_library(item[0])]
packaged_names = {Path(item[0]).name.lower() for item in a.binaries}
required_cpu_dlls = {"ctranslate2.dll", "libiomp5md.dll", "msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"}
missing_cpu_dlls = required_cpu_dlls - packaged_names
if missing_cpu_dlls:
    raise SystemExit("Missing CPU runtime DLLs: " + ", ".join(sorted(missing_cpu_dlls)))
if any(is_ffmpeg_library(name) or is_gpu_library(name) for name, _, _ in a.binaries + a.datas):
    raise SystemExit("The PCM-WAV-only Windows bundle must not include PyAV/FFmpeg codecs.")
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="SGH Voice", debug=False, strip=False, upx=False, console=False,
    uac_admin=False, uac_uiaccess=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SGHVoice")
