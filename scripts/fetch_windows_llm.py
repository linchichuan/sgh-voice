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

GITHUB_HOSTS = ("github.com", "api.github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")


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


def wanted_member(name, executable=None):
    base = Path(name).name.lower()
    executable = (executable or LLM_MANIFEST["runtime"]["executable"]).lower()
    return base == executable or base.endswith(".dll") or base.startswith("license")


def _safe_relative(name):
    parts = [part for part in Path(name.replace("\\", "/")).parts if part not in ("", ".")]
    if not parts or Path(name).is_absolute() or ".." in parts:
        return None
    return Path(*parts)


def _resolve_pending(runtime, opener):
    """Lock mode (test builds only): find the asset by keywords and record its SHA-256."""
    import json
    url = f"https://api.github.com/repos/{runtime['project']}/releases/tags/{runtime['tag']}"
    with opener.open(Request(url, headers={"User-Agent": "SGHVoice-build/1"}), timeout=60) as response:
        release = json.load(response)
    for asset in release.get("assets", []):
        name = asset["name"].lower()
        if "macos" in name and "arm64" in name and name.endswith(".zip"):
            return {**runtime, "asset": asset["name"]}
    raise FetchError("no macOS arm64 zip in llama.cpp " + runtime["tag"])


def fetch_runtime(destination, *, manifest=None, opener=None, log=print, platform="windows"):
    manifest = manifest or LLM_MANIFEST
    runtime = dict(manifest["runtime_macos"] if platform == "macos" else manifest["runtime"])
    destination = Path(destination)
    if destination.exists():
        raise FetchError("runtime folder already exists; remove it and retry")
    opener = opener or build_opener(_GitHubRedirect())
    pending = runtime["sha256"] == "PENDING"
    if pending:
        runtime = _resolve_pending(runtime, opener)
    url = f"https://github.com/{runtime['project']}/releases/download/{runtime['tag']}/{runtime['asset']}"
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
        if pending:
            runtime["sha256"] = digest.hexdigest()
            print("::warning::UNPINNED llama.cpp runtime for " + platform + " - pinned at build time")
            print("LLM_RUNTIME_LOCK " + json_dumps(runtime))
        elif digest.hexdigest() != runtime["sha256"]:
            raise FetchError("llama.cpp runtime does not match the pinned SHA-256")
        extracted = stage / "runtime"
        extracted.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if member.is_dir():
                    continue
                if platform == "windows":
                    if not wanted_member(member.filename, runtime["executable"]):
                        continue
                    target = extracted / Path(member.filename).name  # flatten; no path traversal
                else:
                    # macOS: keep the archive layout (dylib rpaths), refuse unsafe paths.
                    relative = _safe_relative(member.filename)
                    if relative is None:
                        raise FetchError("unsafe path in runtime archive")
                    target = extracted / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    mode = member.external_attr >> 16
                    if mode & 0o170000 == 0o120000:  # symlink (dylib aliases)
                        link = bundle.read(member).decode("utf-8")
                        if Path(link).is_absolute() or ".." in Path(link).parts:
                            raise FetchError("unsafe symlink in runtime archive")
                        target.symlink_to(link)
                        continue
                with bundle.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                if platform == "macos":
                    target.chmod(0o755 if (member.external_attr >> 16) & 0o111 else 0o644)
        found = [p for p in extracted.rglob(runtime["executable"]) if p.is_file()]
        if not found:
            raise FetchError("pinned runtime does not contain " + runtime["executable"])
        if found[0].parent != extracted:
            (extracted / "runtime.json").write_text(json_dumps(
                {"executable": found[0].relative_to(extracted).as_posix()}), encoding="utf-8")
        if platform == "macos":
            found[0].chmod(0o755)
        extracted.rename(destination)
        log(f"verified llama.cpp {runtime['tag']} ({runtime['asset']}) -> {destination}")
        return destination
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def json_dumps(value):
    import json
    return json.dumps(value, ensure_ascii=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", required=True, type=Path, help="llm folder inside the app bundle")
    parser.add_argument("--platform", choices=("windows", "macos"), default="windows")
    args = parser.parse_args(argv)
    args.dest.mkdir(parents=True, exist_ok=True)
    manifest = LLM_MANIFEST
    try:
        fetch_runtime(args.dest / "runtime", platform=args.platform)
        # The GGUF is pinned by size + SHA-256; "main" only names where to fetch it.
        model = fetch_model(args.dest, manifest=manifest, content_pinned=True)
    except (FetchError, OSError) as exc:
        print(f"FAIL LLM fetch: {exc}", file=sys.stderr)
        return 1
    print(f"PASS pinned SOAP model {manifest['repository']} ({manifest['files'][0]['size']} bytes) -> {model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
