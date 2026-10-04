"""Explicit model-only download; recording and inference never call this module's IO.

Only public, pinned model URLs are requested, without authentication or user text.
The downloaded files are data, never executed. Partial files never become active.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "resources" / "windows"
MANIFEST = json.loads((RESOURCE_ROOT / "model-base-v1.json").read_text(encoding="utf-8"))
TOTAL_BYTES = sum(file["size"] for file in MANIFEST["files"])
MODEL_DOWNLOAD_INFO = {
    "name": MANIFEST["name"], "source_url": MANIFEST["source_url"],
    "size_label": f"{TOTAL_BYTES / 1_000_000:.1f} MB", "size_bytes": TOTAL_BYTES,
}


class ModelDownloadError(RuntimeError):
    def __init__(self, code="model_download_failed"):
        self.code = code
        super().__init__(code)


def _allowed_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and (host == "huggingface.co" or host.endswith(".huggingface.co")
                 or host == "hf.co" or host.endswith(".hf.co")))


class _ModelRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed_url(newurl):
            raise ModelDownloadError()
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _valid_file(path, spec):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != spec["size"]:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest() == spec["sha256"]


def prepare_model(destination_root=None, *, should_cancel=lambda: False,
                  on_progress=lambda percent: None, opener=None):
    """Download only after an explicit UI action; no import/startup auto-download."""
    if destination_root is None:
        from config import DATA_DIR
        destination_root = Path(DATA_DIR) / "models"
    root = Path(destination_root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / ("whisper-base-" + MANIFEST["revision"][:12])
    if destination.exists():
        if not destination.is_symlink() and all(_valid_file(destination / f["name"], f) for f in MANIFEST["files"]):
            on_progress(100)
            return destination.resolve()
        # Preserve any existing incomplete/custom folder for user inspection.
        raise ModelDownloadError("model_invalid")
    if shutil.disk_usage(root).free < TOTAL_BYTES * 2 + 100 * 1024 * 1024:
        raise ModelDownloadError("model_disk_space")
    stage = Path(tempfile.mkdtemp(prefix=".sgh-model-", dir=root))
    opener = opener or build_opener(_ModelRedirect())
    completed = 0
    try:
        for spec in MANIFEST["files"]:
            if should_cancel():
                raise ModelDownloadError("model_download_cancelled")
            url = f"https://huggingface.co/{MANIFEST['repository']}/resolve/{MANIFEST['revision']}/{spec['name']}"
            request = Request(url, headers={"User-Agent": "SGHVoice-model-setup/1", "Accept-Encoding": "identity"})
            digest, size = hashlib.sha256(), 0
            with opener.open(request, timeout=30) as response, (stage / spec["name"]).open("xb") as output:
                if not _allowed_url(response.geturl()):
                    raise ModelDownloadError()
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    if should_cancel():
                        raise ModelDownloadError("model_download_cancelled")
                    size += len(block)
                    if size > spec["size"]:
                        raise ModelDownloadError()
                    digest.update(block)
                    output.write(block)
                    on_progress(int((completed + size) * 100 / TOTAL_BYTES))
            if size != spec["size"] or digest.hexdigest() != spec["sha256"]:
                raise ModelDownloadError()
            completed += size
        if should_cancel():
            raise ModelDownloadError("model_download_cancelled")
        stage.rename(destination)
        on_progress(100)
        return destination.resolve()
    except ModelDownloadError:
        raise
    except Exception:
        raise ModelDownloadError() from None
    finally:
        if stage.exists():
            shutil.rmtree(stage)
