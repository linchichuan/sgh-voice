#!/usr/bin/env python3
"""Deterministic, local-only analysis of user-confirmed transcript edits.

The scheduled maintenance path must never export history text. This script
extracts only changed token spans, counts repeated candidates, and writes a
private review report. It never mutates the dictionary automatically.
"""

from __future__ import annotations

import argparse
from collections import Counter
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DATA_DIR


HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
REPORT_FILE = os.path.join(DATA_DIR, "auto_triage_report.md")
_TOKEN_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9_.+/-]*"
    r"|\d+(?:[.,]\d+)*"
    r"|[\u3400-\u9fff\u3040-\u30ff\u31f0-\u31ff\u1100-\u11ff"
    r"\u3130-\u318f\uac00-\ud7af]"
)


def _private_atomic_write(path: str, text: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        destination.parent.chmod(0o700)
    except OSError:
        pass

    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
        )
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, destination)
        temp_path = None
        os.chmod(destination, 0o600)
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text or "")


def _display_span(tokens: list[str]) -> str:
    return " ".join(tokens).strip()


def _candidate_pairs(raw: str, final: str):
    before = _tokens(raw)
    after = _tokens(final)
    matcher = SequenceMatcher(a=before, b=after, autojunk=False)
    for operation, i1, i2, j1, j2 in matcher.get_opcodes():
        if operation != "replace":
            continue
        wrong_tokens = before[i1:i2]
        right_tokens = after[j1:j2]
        if not wrong_tokens or not right_tokens:
            continue
        if len(wrong_tokens) > 8 or len(right_tokens) > 8:
            continue
        wrong = _display_span(wrong_tokens)
        right = _display_span(right_tokens)
        if not wrong or not right or wrong == right:
            continue
        if len(wrong) > 64 or len(right) > 64:
            continue
        yield wrong, right


def _safe_markdown(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|").replace("`", "ˋ")


def _load_history(path: str) -> list[dict]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def analyze_history(max_records: int = 2000) -> dict[str, int]:
    """Create a local review report and return non-sensitive summary counts."""
    history = _load_history(HISTORY_FILE)[-max(1, max_records):]
    edited = [
        item
        for item in history
        if item.get("edited") is True
        and isinstance(item.get("whisper_raw"), str)
        and isinstance(item.get("final_text"), str)
        and item.get("whisper_raw") != item.get("final_text")
    ]
    candidates: Counter[tuple[str, str]] = Counter()
    for item in edited:
        candidates.update(
            _candidate_pairs(item["whisper_raw"], item["final_text"])
        )

    lines = [
        "# 語音辨識本機候選報告",
        "",
        f"**產生時間**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "分析方式：deterministic local diff；未呼叫任何外部模型。",
        "本報告只列變更片段，不列完整逐字稿，也不會自動修改個人詞庫。",
        "",
        f"- 歷史筆數：{len(history)}",
        f"- 已確認編輯筆數：{len(edited)}",
        f"- 候選規則數：{len(candidates)}",
        "",
    ]
    if candidates:
        lines.extend(
            [
                "## 待人工審核候選",
                "",
                "| 原辨識片段 | 修正片段 | 次數 |",
                "|---|---|---:|",
            ]
        )
        for (wrong, right), count in candidates.most_common(100):
            lines.append(
                f"| {_safe_markdown(wrong)} | {_safe_markdown(right)} | {count} |"
            )
    else:
        lines.append("目前沒有可安全抽取的重複替換候選。")

    _private_atomic_write(REPORT_FILE, "\n".join(lines) + "\n")
    summary = {
        "history_records": len(history),
        "edited_records": len(edited),
        "candidate_rules": len(candidates),
    }
    print(
        "Local triage complete: "
        f"edited={summary['edited_records']} "
        f"candidates={summary['candidate_rules']}"
    )
    return summary


def main() -> int:
    global HISTORY_FILE, REPORT_FILE
    parser = argparse.ArgumentParser(
        description="Analyze confirmed transcript edits locally"
    )
    parser.add_argument("--history", default=HISTORY_FILE)
    parser.add_argument("--report", default=REPORT_FILE)
    parser.add_argument("--max-records", type=int, default=2000)
    args = parser.parse_args()

    HISTORY_FILE = args.history
    REPORT_FILE = args.report
    analyze_history(max_records=max(1, args.max_records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
