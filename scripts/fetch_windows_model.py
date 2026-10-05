#!/usr/bin/env python3
"""Build-time only: download the pinned speech model into the app bundle.

windows/build.ps1 runs this after PyInstaller so the installer contains the
model. It is never packaged. Only public, pinned Hugging Face URLs are
requested, without credentials; every file must match the manifest's size and
SHA-256 before the folder becomes active. Partial files never become active.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from windows_client.models import MANIFEST, TOTAL_BYTES, ModelIntegrityError, verify_model_files  # noqa: E402


class FetchError(RuntimeError):
    pass


def allowed_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in (None, 443)
            and (host == "huggingface.co" or host.endswith(".huggingface.co")
                 or host == "hf.co" or host.endswith(".hf.co")))


class _PinnedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise FetchError("redirect outside the official model host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def is_pinned(manifest):
    return (bool(re.fullmatch(r"[0-9a-f]{40}", manifest.get("revision", "")))
            and all(re.fullmatch(r"[0-9a-f]{64}", f.get("sha256", "")) for f in manifest["files"]))


def resolve_revision(repository):
    """Lock mode only: the commit Hugging Face currently serves for main."""
    from huggingface_hub import HfApi
    return HfApi().model_info(repository).sha


def fetch_model(destination_root, *, manifest=None, opener=None, log=print, lock=False):
    """Download and verify; lock=True instead records revision + SHA-256.

    Lock mode exists to pin a new model version. It returns the locked manifest
    so it can be reviewed and committed; release builds use strict mode only.
    """
    manifest = copy.deepcopy(manifest or MANIFEST)
    if lock:
        manifest["revision"] = resolve_revision(manifest["repository"])
    elif not is_pinned(manifest):
        raise FetchError("model manifest is not pinned; use --lock-unpinned only for a test build")
    root = Path(destination_root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / manifest["id"]
    if destination.exists():
        try:
            return verify_model_files(destination, manifest)
        except ModelIntegrityError:
            raise FetchError("existing model folder is incomplete; remove it and retry") from None
    total = sum(spec["size"] for spec in manifest["files"])
    if shutil.disk_usage(root).free < total * 2 + 100 * 1024 * 1024:
        raise FetchError("not enough free disk space")
    stage = Path(tempfile.mkdtemp(prefix=".sgh-model-", dir=root))
    opener = opener or build_opener(_PinnedRedirect())
    try:
        for spec in manifest["files"]:
            url = (f"https://huggingface.co/{manifest['repository']}/resolve/"
                   f"{manifest['revision']}/{spec['name']}")
            request = Request(url, headers={"User-Agent": "SGHVoice-build/1", "Accept-Encoding": "identity"})
            digest, size = hashlib.sha256(), 0
            with opener.open(request, timeout=60) as response, (stage / spec["name"]).open("xb") as output:
                if not allowed_url(response.geturl()):
                    raise FetchError("response outside the official model host")
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    size += len(block)
                    if size > spec["size"]:
                        raise FetchError(f"{spec['name']} is larger than pinned")
                    digest.update(block)
                    output.write(block)
            if lock and size == spec["size"]:
                spec["sha256"] = digest.hexdigest()
            if size != spec["size"] or digest.hexdigest() != spec["sha256"]:
                raise FetchError(f"{spec['name']} does not match the pinned size/SHA-256")
            log(f"verified {spec['name']} ({size} bytes)")
        stage.rename(destination)
        path = verify_model_files(destination, manifest)
        return (path, manifest) if lock else path
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path, help="models folder inside the app bundle")
    parser.add_argument("--lock-unpinned", action="store_true",
                        help="TEST BUILDS ONLY: pin an unpinned manifest from what the Hub serves now")
    parser.add_argument("--write-manifest", type=Path, action="append", default=[],
                        help="with --lock-unpinned: write the locked manifest here")
    args = parser.parse_args(argv)
    lock = args.lock_unpinned and not is_pinned(MANIFEST)
    try:
        result = fetch_model(args.dest, lock=lock)
    except (FetchError, OSError) as exc:
        print(f"FAIL model fetch: {exc}", file=sys.stderr)
        return 1
    if lock:
        path, locked = result
        text = json.dumps(locked, ensure_ascii=False, indent=2) + "\n"
        for target in args.write_manifest:
            target.write_text(text, encoding="utf-8")
        print("::warning::UNPINNED TEST BUILD - model pinned from the Hub at build time")
        print("MODEL_LOCK " + json.dumps(locked, ensure_ascii=False))
        print(f"PASS locked model {locked['repository']}@{locked['revision']} -> {path}")
        return 0
    print(f"PASS pinned model {MANIFEST['repository']}@{MANIFEST['revision']} "
          f"({TOTAL_BYTES} bytes) -> {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
