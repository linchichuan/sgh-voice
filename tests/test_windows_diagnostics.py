"""Prove diagnostic subprocesses retain failures and terminate synthetic hangs."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_diagnostic(tmp_path, body, *, startup=10, case=0.5):
    sample = tmp_path / "test_synthetic_diagnostic.py"
    sample.write_text(body, encoding="utf-8")
    evidence = tmp_path / "evidence"
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([
        sys.executable, "-u", str(ROOT / "scripts/diagnose_windows_tests.py"),
        "--evidence-dir", str(evidence), "--startup-timeout", str(startup),
        "--case-timeout", str(case), str(sample), "-q",
    ], cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)
    progress = [json.loads(line) for line in (evidence / "progress.jsonl").read_text().splitlines()]
    trace = (evidence / "hang-trace.txt").read_text()
    return result, progress, trace


@pytest.mark.parametrize("body,code,outcome", [
    ("def test_result():\n    assert 2 + 2 == 4\n", 0, "passed"),
    ("def test_result():\n    assert False, 'synthetic failure must remain a failure'\n", 1, "failed"),
])
def test_diagnostic_preserves_assertion_exit_status(tmp_path, body, code, outcome):
    result, progress, trace = run_diagnostic(tmp_path, body)
    assert result.returncode == code, result.stdout + result.stderr
    assert progress[-1]["phase"] == "process_exit" and progress[-1]["exitstatus"] == code
    assert any(p.get("stage") == "call" and p.get("outcome") == outcome for p in progress)
    assert trace == ""


@pytest.mark.parametrize("stage", ["setup", "call", "teardown"])
def test_diagnostic_kills_hung_case_and_names_the_active_test(tmp_path, stage):
    body = {
        "setup": "import pytest, threading\n@pytest.fixture\ndef blocked():\n    threading.Event().wait()\ndef test_stuck(blocked):\n    assert True\n",
        "call": "import threading\ndef test_stuck():\n    threading.Event().wait()\n",
        "teardown": "import pytest, threading\n@pytest.fixture\ndef blocked():\n    yield\n    threading.Event().wait()\ndef test_stuck(blocked):\n    assert True\n",
    }[stage]
    result, progress, trace = run_diagnostic(tmp_path, body)
    assert result.returncode == 1
    active = [p for p in progress if p["phase"] == "case_start"][-1]
    assert active["nodeid"].endswith("::test_stuck")
    assert "Timeout" in trace and "test_synthetic_diagnostic.py" in trace
    assert not any(p["phase"] == "process_exit" for p in progress)


def test_diagnostic_also_covers_collection_hangs(tmp_path):
    result, progress, trace = run_diagnostic(tmp_path, "import threading\nthreading.Event().wait()\n", startup=5)
    assert result.returncode == 1
    assert any(p["phase"] == "collection" for p in progress)
    assert not any(p["phase"] == "case_start" for p in progress)
    assert "Timeout" in trace and "test_synthetic_diagnostic.py" in trace
