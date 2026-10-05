"""The speech model shipped inside the installer: manifest, location, integrity.

The application never downloads a model and contains no network client. Build
tooling (scripts/fetch_windows_model.py) places the pinned files next to the
executable before the installer is compiled. At runtime this module only finds
those files and checks them against the pinned manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "resources" / "windows"
MANIFEST_FILE = "model-ja-v1.json"
MANIFEST = json.loads((RESOURCE_ROOT / MANIFEST_FILE).read_text(encoding="utf-8"))
TOTAL_BYTES = sum(file["size"] for file in MANIFEST["files"])
MODEL_INFO = {
    "name": MANIFEST["name"], "repository": MANIFEST["repository"],
    "revision": MANIFEST["revision"], "license": MANIFEST["license"],
    "size_label": f"{TOTAL_BYTES / 1_000_000_000:.2f} GB", "size_bytes": TOTAL_BYTES,
}
VERIFIED_CACHE = "model-verified.json"


class ModelIntegrityError(RuntimeError):
    """A stable UI error code; never carries paths or file contents."""

    def __init__(self, code="model_invalid"):
        self.code = code
        super().__init__(code)


def bundled_model_dir():
    """Install-relative model folder: <app>\\models\\<id>.

    SGHVOICE_MODEL_DIR exists for source checkouts and tests only; the
    installed application has no UI or setting that changes this location.
    """
    override = os.environ.get("SGHVOICE_MODEL_DIR")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[1] / "build" / "windows"
    return base / "models" / MANIFEST["id"]


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _model_file(directory, spec):
    path = Path(directory) / spec["name"]
    if path.is_symlink() or not path.is_file() or path.stat().st_size != spec["size"]:
        raise ModelIntegrityError("model_invalid")
    return path


SAMPLE_BYTES = 1024 * 1024


def _edge_digest(path):
    """SHA-256 of the first and last MiB: cheap, catches rewrites that keep the
    size and land within the filesystem's timestamp resolution."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        digest.update(stream.read(SAMPLE_BYTES))
        size = stream.seek(0, 2)
        stream.seek(max(0, size - SAMPLE_BYTES))
        digest.update(stream.read(SAMPLE_BYTES))
    return digest.hexdigest()


def _fingerprint(directory, manifest):
    files = []
    for spec in manifest["files"]:
        path = _model_file(directory, spec)
        stat = path.stat()
        files.append([spec["name"], stat.st_size, stat.st_mtime_ns, _edge_digest(path)])
    return {"revision": manifest["revision"], "directory": str(directory), "files": files}


def verify_model_files(directory, manifest=None):
    """Full SHA-256 check of every pinned file. Raises ModelIntegrityError."""
    manifest = manifest or MANIFEST
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ModelIntegrityError("model_missing")
    for spec in manifest["files"]:
        if file_sha256(_model_file(directory, spec)) != spec["sha256"]:
            raise ModelIntegrityError("model_invalid")
    return directory.resolve()


def verified_model_dir(directory=None, *, cache_dir=None, manifest=None):
    """Return the bundled model folder after integrity verification.

    The first launch hashes every file (seconds on an SSD). The result is cached
    per user, keyed by revision, sizes, modification times and the first/last
    MiB of each file, so later launches stay fast. Any detected change to the
    installed files forces a full check.
    """
    manifest = manifest or MANIFEST
    directory = Path(directory) if directory is not None else bundled_model_dir()
    if not directory.is_dir() or directory.is_symlink():
        raise ModelIntegrityError("model_missing")
    if cache_dir is None:
        from config import DATA_DIR
        cache_dir = DATA_DIR
    cache = Path(cache_dir) / VERIFIED_CACHE
    fingerprint = _fingerprint(directory, manifest)
    try:
        if json.loads(cache.read_text(encoding="utf-8")) == fingerprint:
            return directory.resolve()
    except (OSError, ValueError):
        pass
    verify_model_files(directory, manifest)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(fingerprint), encoding="utf-8")
    except OSError:
        pass  # Verification still succeeded; the next launch re-hashes.
    return directory.resolve()
