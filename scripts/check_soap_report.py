#!/usr/bin/env python3
"""CI-only: check the frozen app's SOAP draft of the fictional consultation.

Reads windows-offline-test.json and applies the same fact checks as the model
benchmark: values that were said must appear, drugs/tests never said must not.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_windows_soap_llm import check  # noqa: E402


def main(argv=None):
    argv = argv or sys.argv[1:]
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    report = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    soap = report.get("soap") or {}
    text = soap.get("text", "")
    missing, invented, headings = check(text)
    print("===== SOAP draft (fictional consultation) =====\n" + text + "\n===== end =====")
    print("Check (not found in transcript): " + ", ".join(soap.get("unverified", [])))
    print(json.dumps({"seconds": soap.get("seconds"), "transcript_chars": soap.get("transcript_chars"),
                      "headings": headings, "missing": missing, "invented": invented}, ensure_ascii=False))
    if not report.get("soap_tested") or not headings or missing or invented:
        print("FAIL SOAP draft is missing required facts or contains items never said", file=sys.stderr)
        return 1
    print("PASS SOAP draft: headings present, required values kept, nothing invented from the check list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
