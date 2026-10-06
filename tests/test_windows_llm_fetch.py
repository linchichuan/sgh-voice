"""Build-time LLM runtime fetch: pinned hash, host allow-list, minimal extraction."""
import hashlib
import importlib.util
import io
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fetch_windows_llm", ROOT / "scripts/fetch_windows_llm.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def make_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("build/bin/llama-completion.exe", b"MZ completion")
        bundle.writestr("build/bin/ggml-cpu.dll", b"MZ dll")
        bundle.writestr("build/bin/llama-server.exe", b"MZ server")
        bundle.writestr("../../evil.dll", b"MZ outside")
        bundle.writestr("LICENSE", b"MIT")
    return buffer.getvalue()


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Opener:
    def __init__(self, data, url="https://release-assets.githubusercontent.com/x"):
        self.data, self.url, self.requests = data, url, []

    def open(self, request, timeout=None):
        self.requests.append(request.full_url)
        return Response(self.data, self.url)


def manifest(data):
    return {"runtime": {"project": "ggml-org/llama.cpp", "tag": "b1", "asset": "llama-b1-bin-win-cpu-x64.zip",
                        "sha256": hashlib.sha256(data).hexdigest(), "executable": "llama-completion.exe"}}


def test_runtime_is_verified_and_only_needed_files_are_extracted(tmp_path):
    data = make_zip()
    opener = Opener(data)
    target = fetch.fetch_runtime(tmp_path / "runtime", manifest=manifest(data), opener=opener, log=lambda *_: None)
    assert opener.requests == ["https://github.com/ggml-org/llama.cpp/releases/download/b1/llama-b1-bin-win-cpu-x64.zip"]
    names = sorted(p.name for p in target.iterdir())
    assert names == ["LICENSE", "evil.dll", "ggml-cpu.dll", "llama-completion.exe"]  # flattened, no server
    assert not (tmp_path.parent / "evil.dll").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["runtime"]  # staging removed


def test_hash_mismatch_or_foreign_host_leaves_nothing(tmp_path):
    data = make_zip()
    with pytest.raises(fetch.FetchError):
        fetch.fetch_runtime(tmp_path / "runtime", manifest=manifest(b"other"), opener=Opener(data), log=lambda *_: None)
    with pytest.raises(fetch.FetchError):
        fetch.fetch_runtime(tmp_path / "runtime", manifest=manifest(data),
                            opener=Opener(data, "https://example.com/x"), log=lambda *_: None)
    assert list(tmp_path.iterdir()) == []


def test_host_allow_list():
    assert fetch.allowed_runtime_url("https://github.com/ggml-org/llama.cpp/releases/download/b1/a.zip")
    for url in ("http://github.com/a", "https://github.com.evil.example/a", "https://user@github.com/a",
                "https://github.com:8443/a", "https://huggingface.co/a"):
        assert not fetch.allowed_runtime_url(url)
