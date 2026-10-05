"""Windows-only wheel and CPU bundle invariants, without installing packages."""
import builtins
import json
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace

from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
import pytest


ROOT = Path(__file__).resolve().parents[1]


def lock_entries(filename):
    text = (ROOT / filename).read_text(encoding="utf-8")
    return re.findall(
        r"# Wheel: (\S+)\n# https://pypi.org/pypi/[^\n]+\n"
        r"([A-Za-z0-9_.-]+)==([^\s]+) \\\n    --hash=sha256:([a-f0-9]{64})",
        text,
    )


def test_every_windows_pin_has_exact_compatible_wheel_and_hash():
    allowed = set(cpython_tags((3, 12), abis=["cp312"], platforms=["win_amd64"]))
    allowed.update(compatible_tags((3, 12), interpreter="cp312", platforms=["win_amd64"]))
    seen = set()
    for filename in ("requirements-windows.txt", "requirements-windows-build.txt"):
        entries = lock_entries(filename)
        pins = re.findall(r"^([A-Za-z0-9_.-]+)==", (ROOT / filename).read_text(encoding="utf-8"), re.MULTILINE)
        assert len(entries) == len(pins) > 0
        for wheel, name, version, _ in entries:
            wheel_name, wheel_version, _, tags = parse_wheel_filename(wheel)
            assert wheel_name == canonicalize_name(name)
            assert str(wheel_version) == version
            assert tags & allowed, wheel
            assert name not in seen
            seen.add(name)


def test_runtime_reuses_http_stack_without_cloud_sdk_or_gpu_packages():
    packages = {name for _, name, _, _ in lock_entries("requirements-windows.txt")}
    assert {"ctranslate2", "tokenizers", "numpy", "onnxruntime", "keyring", "sounddevice", "soundfile",
            "httpx", "httpcore", "certifi", "anyio", "h11", "idna"} <= packages
    assert not packages & {"av", "faster-whisper", "openai", "anthropic", "torch", "torchaudio", "mlx", "onnxruntime-gpu"}
    assert not any(name.startswith(("nvidia-", "cuda-")) for name in packages)
    assert "--only-binary=:all:" in (ROOT / "requirements-windows.txt").read_text(encoding="utf-8")


def run_spec(monkeypatch, tmp_path, *, missing_dll=None, extra_data=None):
    hooks = ModuleType("PyInstaller.utils.hooks")
    hooks.collect_all = lambda package: ([], [], [package])
    hooks.collect_data_files = lambda package, **kwargs: [(package + "/LICENSE", package)]
    hooks.collect_submodules = lambda package: [package + ".transcribe"]
    copied = []
    hooks.copy_metadata = lambda distribution: copied.append(distribution) or [(distribution, distribution + ".dist-info")]
    hooks.collect_dynamic_libs = lambda package: (
        [("/site/ctranslate2/" + name, "ctranslate2") for name in ("ctranslate2.dll", "libiomp5md.dll", "cudnn64_9.dll")]
        if package == "ctranslate2" else []
    )
    monkeypatch.setitem(sys.modules, "PyInstaller", ModuleType("PyInstaller"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils", ModuleType("PyInstaller.utils"))
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooks)
    info = tmp_path / "windows-build-info.json"
    info.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SGH_WINDOWS_BUILD_INFO", str(info))
    fake_sys = SimpleNamespace(platform="win32", base_prefix=str(tmp_path))
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        return fake_sys if name == "sys" else original_import(name, *args, **kwargs)

    captured = {}

    def analysis(scripts, **kwargs):
        captured.update(kwargs)
        names = {"ctranslate2.dll", "libiomp5md.dll", "msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "cudnn64_9.dll"}
        if missing_dll:
            names.remove(missing_dll)
        return SimpleNamespace(
            binaries=[(name, "/site/" + name, "BINARY") for name in names],
            datas=[(extra_data, "/site/extra", "DATA")] if extra_data else [],
            pure=[], scripts=[],
        )

    namespace = {"__builtins__": dict(vars(builtins), __import__=import_module),
                 "SPECPATH": str(ROOT / "windows"), "Analysis": analysis,
                 "PYZ": lambda *args: None, "EXE": lambda *args, **kwargs: None,
                 "COLLECT": lambda *args, **kwargs: None}
    spec = ROOT / "windows/sghvoice.spec"
    exec(compile(spec.read_text(encoding="utf-8"), str(spec), "exec"), namespace)
    return namespace, captured, copied


def test_bundle_keeps_cloud_adapter_but_excludes_cloud_sdks_gpu_and_ffmpeg(monkeypatch, tmp_path):
    namespace, analysis, copied = run_spec(monkeypatch, tmp_path)
    assert set(copied) == {name for _, name, _, _ in lock_entries("requirements-windows.txt")}
    assert {"av", "faster_whisper", "transcriber", "anthropic", "openai", "torch"} <= set(analysis["excludes"])
    assert "windows_client._vendor.faster_whisper" in analysis["hiddenimports"]
    assert {"windows_client.cloud_stt", "httpx", "httpx._transports.default", "httpx._transports.mock", "httpcore"} <= set(analysis["hiddenimports"])
    assert not any("cudnn" in item[0].lower() for item in analysis["binaries"])
    assert not any("cudnn" in item[0].lower() for item in namespace["a"].binaries)
    assert (str(ROOT / "resources/windows"), "resources/windows") in analysis["datas"]


@pytest.mark.parametrize("dll", ["msvcp140.dll", "vcruntime140_1.dll", "ctranslate2.dll"])
def test_missing_native_dependency_blocks_bundle(monkeypatch, tmp_path, dll):
    with pytest.raises(SystemExit, match="Missing CPU runtime DLLs"):
        run_spec(monkeypatch, tmp_path, missing_dll=dll)


@pytest.mark.parametrize("path", ["av.libs/libx264.dll", "av/_core.pyd", "ffmpeg.exe", "nvidia/cudnn64_9.dll"])
def test_hooks_cannot_reintroduce_disallowed_libraries_as_data(monkeypatch, tmp_path, path):
    with pytest.raises(SystemExit, match="must not include"):
        run_spec(monkeypatch, tmp_path, extra_data=path)


def test_frozen_cloud_mock_exercises_adapter_without_profile_keys_or_network(isolated_data_dir, monkeypatch):
    import config
    import socket
    from windows_launcher import cloud_mock_check

    monkeypatch.setattr(config, "load_config", lambda: pytest.fail("Smoke must not load saved credentials"))
    monkeypatch.setenv("OPENAI_API_KEY", "unused-synthetic-environment-key")
    monkeypatch.setenv("HTTPS_PROXY", "https://unused-synthetic-proxy.invalid")
    original_connect = socket.socket.connect
    original_dns = socket.getaddrinfo
    evidence = {}
    cloud_mock_check(evidence)
    assert evidence == {"cloud_mock_python_network_guard": True,
                        "cloud_mock_python_network_attempts": 0}
    assert socket.socket.connect is original_connect
    assert socket.getaddrinfo is original_dns
    assert "synthetic-key" not in json.dumps(evidence)
    assert "api.openai.com" not in json.dumps(evidence)


def test_frozen_cloud_mock_blocks_network_regression_and_restores_sockets(isolated_data_dir, monkeypatch):
    import socket
    from windows_client.cloud_stt import CloudTranscriber
    from windows_launcher import cloud_mock_check

    def attempted_network(*args, **kwargs):
        socket.create_connection(("example.invalid", 443))

    monkeypatch.setattr(CloudTranscriber, "transcribe", attempted_network)
    original_connect = socket.socket.connect
    original_create = socket.create_connection
    original_dns = socket.getaddrinfo
    evidence = {}
    with pytest.raises(OSError, match="Network is disabled"):
        cloud_mock_check(evidence)
    assert evidence == {"cloud_mock_python_network_guard": True,
                        "cloud_mock_python_network_attempts": 1}
    assert socket.socket.connect is original_connect
    assert socket.create_connection is original_create
    assert socket.getaddrinfo is original_dns
