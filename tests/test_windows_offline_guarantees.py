"""Static zero-network guarantees for the Windows offline edition's own code.

The vendored faster-whisper copy is covered by its provenance tests; its
download entry point is disabled there. Runtime denial of Python sockets is
exercised on Windows by windows/offline-test.ps1.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLICATION = sorted(p for p in (ROOT / "windows_client").glob("*.py")) + [ROOT / "windows_launcher.py"]
NETWORK_MODULES = {"urllib.request", "http", "http.client", "requests", "httpx", "aiohttp",
                   "huggingface_hub", "openai", "anthropic", "groq", "webbrowser", "ftplib",
                   "smtplib", "ssl", "socketserver"}


def imported_modules(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_application_code_imports_no_network_client():
    for path in APPLICATION:
        modules = imported_modules(path)
        assert not {m for m in modules if m in NETWORK_MODULES or m.split(".")[0] in NETWORK_MODULES}, path.name
        if path.name != "windows_launcher.py":
            # Only the offline self-test imports socket, to deny connections.
            assert "socket" not in modules, path.name


def test_model_download_tooling_is_build_time_only():
    spec = (ROOT / "windows/sghvoice.spec").read_text(encoding="utf-8")
    assert "fetch_windows_model" not in spec
    assert "benchmark_windows_ja_stt" not in spec
    assert "prepare_windows_speech_fixture" not in spec
    build = (ROOT / "windows/build.ps1").read_text(encoding="utf-8")
    assert "@('scripts/fetch_windows_model.py', '--dest', (Join-Path $AppDirectory 'models'))" in build
    assert "if ($LockUnpinnedModel)" in build  # lock mode is opt-in only
    assert build.index("fetch_windows_model.py") < build.index("--self-test")


def test_runtime_forces_offline_hub_environment_before_engine_import():
    source = (ROOT / "windows_client/local_stt.py").read_text(encoding="utf-8")
    assert source.index("enforce_offline_environment()\n") < source.index("class LocalTranscriber")
    for name in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        assert name in source
