"""Bundled-model integrity and build-time fetch tests: synthetic bytes, no network."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from windows_client import models

ROOT = Path(__file__).resolve().parents[1]


def load_fetch_script():
    spec = importlib.util.spec_from_file_location("fetch_windows_model", ROOT / "scripts/fetch_windows_model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def synthetic():
    data = b"synthetic model data"
    manifest = {"id": "synthetic-model", "repository": "kotoba-tech/kotoba-whisper-v2.0-faster",
                "revision": "a" * 40,
                "files": [{"name": "model.bin", "size": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}]}
    return SimpleNamespace(data=data, manifest=manifest)


def write_model(folder, data):
    folder.mkdir(parents=True)
    (folder / "model.bin").write_bytes(data)
    return folder


def test_verification_accepts_exact_files_and_caches_by_fingerprint(tmp_path, synthetic, monkeypatch):
    folder = write_model(tmp_path / "model", synthetic.data)
    cache = tmp_path / "profile"
    assert models.verified_model_dir(folder, cache_dir=cache, manifest=synthetic.manifest) == folder.resolve()
    hashed = []
    monkeypatch.setattr(models, "file_sha256", lambda path: hashed.append(path) or "never")
    # Unchanged sizes/mtimes: later launches skip the full hash.
    assert models.verified_model_dir(folder, cache_dir=cache, manifest=synthetic.manifest) == folder.resolve()
    assert hashed == []


def test_modified_model_is_rehashed_and_rejected(tmp_path, synthetic):
    folder = write_model(tmp_path / "model", synthetic.data)
    cache = tmp_path / "profile"
    models.verified_model_dir(folder, cache_dir=cache, manifest=synthetic.manifest)
    # Same size, and on Windows often the same mtime tick: the edge digest differs.
    stat = (folder / "model.bin").stat()
    (folder / "model.bin").write_bytes(b"X" * len(synthetic.data))
    os.utime(folder / "model.bin", ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises(models.ModelIntegrityError, match="model_invalid"):
        models.verified_model_dir(folder, cache_dir=cache, manifest=synthetic.manifest)


@pytest.mark.parametrize("mutate,code", [
    (lambda folder: (folder / "model.bin").unlink(), "model_invalid"),
    (lambda folder: (folder / "model.bin").write_bytes(b"short"), "model_invalid"),
])
def test_missing_or_truncated_files_never_verify(tmp_path, synthetic, mutate, code):
    folder = write_model(tmp_path / "model", synthetic.data)
    mutate(folder)
    with pytest.raises(models.ModelIntegrityError, match=code):
        models.verified_model_dir(folder, cache_dir=tmp_path / "profile", manifest=synthetic.manifest)


def test_absent_bundle_reports_reinstall_code(tmp_path, synthetic):
    with pytest.raises(models.ModelIntegrityError, match="model_missing"):
        models.verified_model_dir(tmp_path / "absent", cache_dir=tmp_path, manifest=synthetic.manifest)


def test_frozen_location_is_beside_the_executable(tmp_path, monkeypatch):
    monkeypatch.delenv("SGHVOICE_MODEL_DIR", raising=False)
    monkeypatch.setattr(models.sys, "frozen", True, raising=False)
    monkeypatch.setattr(models.sys, "executable", str(tmp_path / "SGH Voice.exe"))
    assert models.bundled_model_dir() == tmp_path.resolve() / "models" / models.MANIFEST["id"]


def test_application_module_has_no_network_client():
    source = (ROOT / "windows_client/models.py").read_text(encoding="utf-8")
    for forbidden in ("urllib", "http.client", "socket", "requests", "httpx", "huggingface_hub"):
        assert forbidden not in source


def test_build_fetch_checks_hash_and_reuses_without_network(tmp_path, synthetic):
    fetch = load_fetch_script()
    calls = []

    class Response(io.BytesIO):
        def geturl(self):
            return "https://cas-bridge.xethub.hf.co/public-model"

    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return Response(synthetic.data)

    path = fetch.fetch_model(tmp_path, manifest=synthetic.manifest, opener=Opener(), log=lambda *_: None)
    assert (path / "model.bin").read_bytes() == synthetic.data
    assert not calls[0].has_header("Authorization")
    assert "a" * 40 in calls[0].full_url
    assert fetch.fetch_model(tmp_path, manifest=synthetic.manifest, opener=Opener()) == path
    assert len(calls) == 1
    assert not list(tmp_path.glob(".sgh-model-*"))


def test_build_fetch_hash_mismatch_never_activates(tmp_path, synthetic):
    fetch = load_fetch_script()
    synthetic.manifest["files"][0]["sha256"] = "0" * 64

    class Opener:
        def open(self, request, timeout):
            response = io.BytesIO(synthetic.data)
            response.geturl = lambda: "https://huggingface.co/x"
            return response

    with pytest.raises(fetch.FetchError):
        fetch.fetch_model(tmp_path, manifest=synthetic.manifest, opener=Opener(), log=lambda *_: None)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("url", ["http://huggingface.co/a", "https://evil.test/a",
                                 "https://huggingface.co.evil.test/a", "https://user@huggingface.co/a"])
def test_build_fetch_never_leaves_official_model_hosts(url):
    assert not load_fetch_script().allowed_url(url)


def test_build_lock_mode_records_revision_and_hashes(tmp_path, synthetic, monkeypatch):
    fetch = load_fetch_script()
    unpinned = {**synthetic.manifest, "revision": "PENDING_REVISION",
                "files": [{**synthetic.manifest["files"][0], "sha256": "PENDING"}]}
    monkeypatch.setattr(fetch, "resolve_revision", lambda repository: "b" * 40)

    class Opener:
        def open(self, request, timeout):
            assert "b" * 40 in request.full_url
            response = io.BytesIO(synthetic.data)
            response.geturl = lambda: "https://huggingface.co/x"
            return response

    with pytest.raises(fetch.FetchError, match="not pinned"):
        fetch.fetch_model(tmp_path / "strict", manifest=unpinned, opener=Opener())
    path, locked = fetch.fetch_model(tmp_path / "lock", manifest=unpinned, opener=Opener(),
                                     log=lambda *_: None, lock=True)
    assert locked["revision"] == "b" * 40
    assert locked["files"][0]["sha256"] == hashlib.sha256(synthetic.data).hexdigest()
    assert fetch.is_pinned(locked) and not fetch.is_pinned(unpinned)
    assert unpinned["revision"] == "PENDING_REVISION"  # input manifest not mutated
    assert models.verify_model_files(path, locked) == path


def test_pinned_manifest_is_complete_japanese_and_below_setup_limit():
    manifest = json.loads((models.RESOURCE_ROOT / models.MANIFEST_FILE).read_text(encoding="utf-8"))
    assert manifest["languages"] == ["ja"]
    if manifest["revision"] == "PENDING_REVISION":
        # Only before the first locked Windows build; release builds refuse it.
        assert all(f["sha256"] == "PENDING" for f in manifest["files"])
        pytest.skip("model pins pending the first locked Windows build")
    assert len(manifest["revision"]) == 40 and int(manifest["revision"], 16) >= 0
    names = {f["name"] for f in manifest["files"]}
    assert {"config.json", "model.bin", "tokenizer.json"} <= names
    assert len(names & {"vocabulary.txt", "vocabulary.json"}) == 1
    assert all(len(f["sha256"]) == 64 and int(f["sha256"], 16) >= 0 for f in manifest["files"])
    # Inno Setup builds a single setup.exe only below 2 GB (no disk spanning).
    assert sum(f["size"] for f in manifest["files"]) < 1_900_000_000
    assert set(manifest.get("decode", {})) <= {"chunk_length"}
