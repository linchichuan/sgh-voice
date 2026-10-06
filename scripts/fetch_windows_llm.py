#!/usr/bin/env python3
"""Build-time only: place the pinned llama.cpp CPU runtime and SOAP model in the bundle.

windows/build.ps1 runs this after PyInstaller. It is never packaged. The
runtime zip comes from the official ggml-org/llama.cpp GitHub release named in
resources/windows/llm-ja-v1.json and must match its SHA-256; only the
completion executable, its DLLs and license files are extracted. The GGUF must
match the pinned size and SHA-256 (downloaded with the same host checks as the
speech model). Nothing becomes active unless every check passes.
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
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fetch_windows_model import FetchError, fetch_model  # noqa: E402
from windows_client.soap import LLM_MANIFEST  # noqa: E402

GITHUB_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")


def allowed_runtime_url(url):
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in (None, 443) and host in GITHUB_HOSTS)


class _GitHubRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_runtime_url(newurl):
            raise FetchError("redirect outside GitHub release hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def wanted_member(name):
    base = Path(name).name.lower()
    return (base == LLM_MANIFEST["runtime"]["executable"].lower() or base.endswith(".dll")
            or base.startswith("license"))


def fetch_runtime(destination, *, manifest=None, opener=None, log=print):
    runtime = (manifest or LLM_MANIFEST)["runtime"]
    destination = Path(destination)
    if destination.exists():
        raise FetchError("runtime folder already exists; remove it and retry")
    url = f"https://github.com/{runtime['project']}/releases/download/{runtime['tag']}/{runtime['asset']}"
    opener = opener or build_opener(_GitHubRedirect())
    stage = Path(tempfile.mkdtemp(prefix=".sgh-llm-", dir=destination.parent))
    try:
        archive = stage / runtime["asset"]
        digest = hashlib.sha256()
        request = Request(url, headers={"User-Agent": "SGHVoice-build/1", "Accept-Encoding": "identity"})
        with opener.open(request, timeout=120) as response, archive.open("xb") as output:
            if not allowed_runtime_url(response.geturl()):
                raise FetchError("response outside GitHub release hosts")
            for block in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != runtime["sha256"]:
            raise FetchError("llama.cpp runtime does not match the pinned SHA-256")
        extracted = stage / "runtime"
        extracted.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if member.is_dir() or not wanted_member(member.filename):
                    continue
                target = extracted / Path(member.filename).name  # flatten; no path traversal
                with bundle.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
        if not (extracted / runtime["executable"]).is_file():
            raise FetchError("pinned runtime does not contain " + runtime["executable"])
        extracted.rename(destination)
        log(f"verified llama.cpp {runtime['tag']} ({runtime['asset']}) -> {destination}")
        return destination
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path, help="llm folder inside the app bundle")
    args = parser.parse_args(argv)
    args.dest.mkdir(parents=True, exist_ok=True)
    manifest = LLM_MANIFEST
    try:
        fetch_runtime(args.dest / "runtime")
        # The GGUF is pinned by size + SHA-256; "main" only names where to fetch it.
        model = fetch_model(args.dest, manifest=manifest, content_pinned=True)
    except (FetchError, OSError) as exc:
        print(f"FAIL LLM fetch: {exc}", file=sys.stderr)
        return 1
    print(f"PASS pinned SOAP model {manifest['repository']} ({manifest['files'][0]['size']} bytes) -> {model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
