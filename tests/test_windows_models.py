"""Model acquisition tests use tiny synthetic bytes and never contact the network."""
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from windows_client import models


@pytest.fixture
def fixture(monkeypatch):
    data = b"synthetic model data"
    manifest = {"repository": "Systran/faster-whisper-base", "revision": "a" * 40,
                "files": [{"name": "model.bin", "size": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}]}
    monkeypatch.setattr(models, "MANIFEST", manifest)
    monkeypatch.setattr(models, "TOTAL_BYTES", len(data))
    calls = []
    class Response(io.BytesIO):
        def geturl(self):
            return "https://cas-bridge.xethub.hf.co/public-model"
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return Response(data)
    return SimpleNamespace(opener=Opener(), calls=calls, data=data, manifest=manifest)


def test_explicit_download_checks_hash_and_reuses_without_network(tmp_path, fixture):
    progress = []
    path = models.prepare_model(tmp_path, opener=fixture.opener, on_progress=progress.append)
    assert (path / "model.bin").read_bytes() == fixture.data
    assert progress[-1] == 100
    assert not fixture.calls[0].has_header("Authorization")
    assert "a" * 40 in fixture.calls[0].full_url
    assert models.prepare_model(tmp_path, opener=fixture.opener) == path
    assert len(fixture.calls) == 1
    assert not list(tmp_path.glob(".sgh-model-*"))


def test_hash_mismatch_never_activates_model(tmp_path, fixture):
    fixture.manifest["files"][0]["sha256"] = "0" * 64
    with pytest.raises(models.ModelDownloadError):
        models.prepare_model(tmp_path, opener=fixture.opener)
    assert list(tmp_path.iterdir()) == []


def test_cancel_leaves_no_partial_model(tmp_path, fixture):
    with pytest.raises(models.ModelDownloadError, match="model_download_cancelled"):
        models.prepare_model(tmp_path, opener=fixture.opener, should_cancel=lambda: True)
    assert not fixture.calls
    assert list(tmp_path.iterdir()) == []


def test_existing_unknown_folder_is_preserved(tmp_path, fixture):
    dest = tmp_path / ("whisper-base-" + "a" * 12)
    dest.mkdir()
    (dest / "user.txt").write_text("keep")
    with pytest.raises(models.ModelDownloadError, match="model_invalid"):
        models.prepare_model(tmp_path, opener=fixture.opener)
    assert (dest / "user.txt").read_text() == "keep"


@pytest.mark.parametrize("url", ["http://huggingface.co/a", "https://evil.test/a",
                                 "https://huggingface.co.evil.test/a", "https://user@huggingface.co/a"])
def test_redirect_never_downgrades_or_leaves_official_model_hosts(url):
    assert not models._allowed_url(url)


def test_pinned_metadata_is_bounded_and_has_no_dynamic_credentials():
    import json
    manifest = json.loads((models.RESOURCE_ROOT / "model-base-v1.json").read_text(encoding="utf-8"))
    assert len(manifest["revision"]) == 40
    assert {f["name"] for f in manifest["files"]} == {"config.json", "model.bin", "tokenizer.json", "vocabulary.txt"}
    assert sum(f["size"] for f in manifest["files"]) < 150_000_000
    assert all(len(f["sha256"]) == 64 for f in manifest["files"])
