"""Run unchanged pytest assertions with durable progress and fatal hang traces.

The startup timer covers imports/collection; each test timer covers setup,
call and teardown. A separate PowerShell process supervises total wall time.
No plugin dependency, recording, credential lookup or network call is added.
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import os
from pathlib import Path
import sys
import time


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--case-timeout", type=float, default=30)
    parser.add_argument("--startup-timeout", type=float, default=30)
    args, pytest_args = parser.parse_known_args(argv)
    if not 0 < args.case_timeout <= 60 or not 0 < args.startup_timeout <= 60:
        parser.error("Watchdog limits must be greater than zero and at most 60 seconds")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    with (args.evidence_dir / "progress.jsonl").open("a", encoding="utf-8", buffering=1) as progress, \
            (args.evidence_dir / "hang-trace.txt").open("w", encoding="utf-8") as trace:
        def record(phase, **fields):
            line = json.dumps({"phase": phase, "elapsed": round(time.monotonic() - started, 3),
                               **fields}, ensure_ascii=True)
            progress.write(line + "\n")
            progress.flush()
            os.fsync(progress.fileno())
            print(line, flush=True)

        def arm(seconds):
            faulthandler.cancel_dump_traceback_later()
            faulthandler.dump_traceback_later(seconds, file=trace, exit=True)

        started = time.monotonic()
        faulthandler.enable(file=trace, all_threads=True)
        arm(args.startup_timeout)
        record("pytest_import")
        try:
            import pytest

            class Progress:
                def pytest_sessionstart(self, session):
                    record("collection")

                def pytest_collection_finish(self, session):
                    record("collected", tests=len(session.items))

                @pytest.hookimpl(hookwrapper=True, tryfirst=True)
                def pytest_runtest_protocol(self, item, nextitem):
                    record("case_start", nodeid=item.nodeid)
                    arm(args.case_timeout)
                    try:
                        yield
                    finally:
                        record("case_end", nodeid=item.nodeid)
                        arm(args.startup_timeout)

                def pytest_runtest_logreport(self, report):
                    record("case_report", nodeid=report.nodeid, stage=report.when,
                           outcome=report.outcome)

                def pytest_sessionfinish(self, session, exitstatus):
                    record("session_finish", exitstatus=int(exitstatus))

            record("pytest_ready", version=pytest.__version__)
            status = int(pytest.main([*pytest_args, "-o", "addopts=", "-p", "no:faulthandler"],
                                     plugins=[Progress()]))
            record("process_exit", exitstatus=status)
            return status
        finally:
            faulthandler.cancel_dump_traceback_later()
            faulthandler.disable()


if __name__ == "__main__":
    raise SystemExit(main())
