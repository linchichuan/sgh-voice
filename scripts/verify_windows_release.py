#!/usr/bin/env python3
"""Check build integrity without claiming real Windows acceptance or publishing."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]


def read_version(path: Path = ROOT / "config.py") -> str:
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "APP_VERSION" for target in node.targets
        ):
            version = ast.literal_eval(node.value)
            if isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version):
                return version
    raise ValueError("config.py must define a semantic APP_VERSION")


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path.name}")
    return data


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_pe(path: Path, *, app: bool = False) -> int:
    """Require a PE executable, including correct x64 app architecture."""
    with path.open("rb") as file:
        dos = file.read(64)
        if len(dos) < 64 or dos[:2] != b"MZ":
            raise ValueError(f"Not a Windows PE executable: {path.name}")
        offset = struct.unpack_from("<I", dos, 60)[0]
        if offset < 64 or offset > path.stat().st_size - 26:
            raise ValueError("PE header offset is outside the executable")
        file.seek(offset)
        header = file.read(26)
        if header[:4] != b"PE\0\0":
            raise ValueError("PE signature is missing")
        machine, sections = struct.unpack_from("<HH", header, 4)
        optional_size, characteristics, magic = struct.unpack_from("<HHH", header, 20)
        if machine not in ({0x8664} if app else {0x014C, 0x8664}):
            raise ValueError("Unexpected Windows executable architecture")
        expected_magic = 0x20B if machine == 0x8664 else 0x10B
        if not sections or optional_size < 96 or magic != expected_magic or not characteristics & 0x0002:
            raise ValueError("Invalid PE executable headers")
        if offset + 24 + optional_size + 40 * sections > path.stat().st_size:
            raise ValueError("Truncated PE sections")
        return machine


def verify_smoke(report: dict, version: str) -> None:
    if report.get("ok") is not True or report.get("errors") != []:
        raise ValueError("Frozen application self-test did not pass")
    if str(report.get("platform", "")).lower() not in {"windows", "win32"}:
        raise ValueError("Self-test was not run on Windows")
    if str(report.get("architecture", "")).lower() not in {"x64", "amd64", "x86_64"}:
        raise ValueError("Self-test did not identify x64 architecture")
    if report.get("version") != version:
        raise ValueError("Self-test version differs from source")
    checks = report.get("checks")
    if not isinstance(checks, dict) or not checks or any(value is not True for value in checks.values()):
        raise ValueError("Self-test checks are missing or failed")
    required = {"windows_native", "tk_ui", "wav_roundtrip", "credential_backend", "shared_core"}
    if not required.issubset(checks):
        raise ValueError("Required frozen application checks are missing")
    for flag in ("microphone_tested", "cloud_tested", "input_delivery_tested"):
        if report.get(flag) is not False:
            raise ValueError("Build self-test must explicitly exclude interactive / cloud acceptance")


def verify_public_manifest(manifest: dict, installer: Path, source_commit: str, root: Path = ROOT) -> None:
    """Optional final publication gate; an independent human writes acceptance."""
    version = read_version(root / "config.py")
    digest = sha256(installer)
    if manifest.get("schemaVersion") != 1 or manifest.get("status") != "available":
        raise ValueError("Public Windows manifest is not available")
    expected = {
        "version": version, "fileName": installer.name, "sizeBytes": installer.stat().st_size,
        "sha256": digest, "architecture": "x64", "installerScope": "per-user", "signing": "unsigned",
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Public manifest does not match the verified installer")
    build = manifest.get("build", {})
    if not isinstance(build, dict) or any(build.get(key) != value for key, value in {
        "status": "passed", "platform": "windows", "commit": source_commit,
    }.items()):
        raise ValueError("Public build evidence does not match")
    acceptance = manifest.get("acceptance", {})
    if not isinstance(acceptance, dict) or any(acceptance.get(key) != value for key, value in {
        "status": "passed", "platform": "windows", "sha256": digest,
    }.items()):
        raise ValueError("Windows acceptance has not passed for this installer")
    record = acceptance.get("record", "")
    if not isinstance(record, str) or not re.fullmatch(r"docs/windows-acceptance-[A-Za-z0-9._-]+\.md", record):
        raise ValueError("Windows acceptance record path is invalid")
    content = (root / record).read_text(encoding="utf-8")
    if digest not in content or source_commit not in content:
        raise ValueError("Acceptance record must name exact source commit and installer SHA256")
    required = ("installation", "microphone", "hotkey", "target-paste", "clipboard-fallback", "privacy", "uninstall")
    for criterion in required:
        if not re.search(rf"^\s*-\s+{re.escape(criterion)}:\s+PASS\s*$", content, re.M):
            raise ValueError(f"Acceptance criterion not recorded as PASS: {criterion}")


def verify_build(installer: Path, app: Path, smoke_path: Path, source_commit: str) -> dict:
    version = read_version()
    if not re.fullmatch(r"[a-f0-9]{40}", source_commit):
        raise ValueError("Expected a full immutable Git source commit")
    if installer.name != f"SGHVoice-Windows-{version}-x64-unsigned.exe":
        raise ValueError("Installer filename differs from source version / unsigned x64 target")
    verify_pe(installer)
    verify_pe(app, app=True)
    info = read_json(app.parent / "_internal" / "windows-build-info.json")
    expected = {"schemaVersion": 1, "version": version, "sourceCommit": source_commit,
                "platform": "windows", "architecture": "x64", "signing": "unsigned"}
    if any(info.get(key) != value for key, value in expected.items()):
        raise ValueError("Packaged source build metadata does not match")
    report = read_json(smoke_path)
    verify_smoke(report, version)
    return {
        **expected,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "installer": {"name": installer.name, "sizeBytes": installer.stat().st_size, "sha256": sha256(installer)},
        "application": {"name": app.name, "sha256": sha256(app)},
        "smokeReport": report,
        "windowsAcceptance": "not-run",
        "published": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", required=True, type=Path)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--smoke-report", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--write-manifest", type=Path)
    parser.add_argument("--public-manifest", type=Path)
    args = parser.parse_args()
    try:
        result = verify_build(args.installer, args.app, args.smoke_report, args.source_commit)
        if args.public_manifest:
            verify_public_manifest(read_json(args.public_manifest), args.installer, args.source_commit)
        if args.write_manifest:
            args.write_manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"PASS Windows artifact integrity: {result['installer']['sha256']}")
        print("This check does not establish microphone / hotkey / target-paste acceptance or publish files.")
        return 0
    except (OSError, ValueError, SyntaxError, StopIteration) as exc:
        print(f"FAIL Windows release verification: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
