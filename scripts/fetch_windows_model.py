#!/usr/bin/env python3
"""Build-time only: download the pinned speech model into the app bundle.

windows/build.ps1 runs this after PyInstaller so the installer contains the
model. It is never packaged. Only public, pinned Hugging Face URLs are
requested, without credentials; every file must match the manifest's size and
SHA-256 before the folder becomes active. Partial files never become active.
"""
from __future__ import annotations

import argparse
import hashlib
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


def fetch_model(destination_root, *, manifest=None, opener=None, log=print):
    manifest = manifest or MANIFEST
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
            if size != spec["size"] or digest.hexdigest() != spec["sha256"]:
                raise FetchError(f"{spec['name']} does not match the pinned size/SHA-256")
            log(f"verified {spec['name']} ({size} bytes)")
        stage.rename(destination)
        return verify_model_files(destination, manifest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path, help="models folder inside the app bundle")
    args = parser.parse_args(argv)
    try:
        path = fetch_model(args.dest)
    except (FetchError, OSError) as exc:
        print(f"FAIL model fetch: {exc}", file=sys.stderr)
        return 1
    print(f"PASS pinned model {MANIFEST['repository']}@{MANIFEST['revision']} "
          f"({TOTAL_BYTES} bytes) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
