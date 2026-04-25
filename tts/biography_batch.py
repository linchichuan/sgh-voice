#!/usr/bin/env python3
"""
biography_batch.py — deterministic batch runner for biography chapters.
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
GENERATE = SCRIPT_DIR / "generate.py"


def log_line(path, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", help="markdown chapters directory")
    parser.add_argument("output_dir", help="output wav directory")
    parser.add_argument(
        "--progress-log",
        default="/Volumes/Satechi_SSD/voice-input/tts-data/output/biography/progress.log",
        help="progress log path",
    )
    parser.add_argument("--start-at", help="start from chapter stem, e.g. 03_創業的手忙腳亂")
    parser.add_argument("--limit", type=int, help="only generate first N matched chapters")
    parser.add_argument("--skip-existing", action="store_true", help="skip chapters with existing wav")
    parser.add_argument("--reference-wav", help="override reference wav path")
    parser.add_argument("--reference-text", help="override reference text path")
    parser.add_argument("--skip-verify", action="store_true", help="disable voice verification")
    parser.add_argument("--keep-going", action="store_true", help="continue after a failed chapter")
    return parser.parse_args()


def main():
    args = parse_args()
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    progress_log = Path(args.progress_log)

    chapters = sorted(source_dir.glob("*.md"))
    if args.start_at:
        chapters = [chapter for chapter in chapters if chapter.stem >= args.start_at]
    if args.limit:
        chapters = chapters[: args.limit]
    if not chapters:
        raise SystemExit("no chapters matched")

    output_dir.mkdir(parents=True, exist_ok=True)
    log_line(progress_log, f"Batch start source={source_dir} output={output_dir}")

    for chapter in chapters:
        output_wav = output_dir / f"{chapter.stem}.wav"
        error_log = output_dir / f"{chapter.stem}.error.log"
        verify_log = output_dir / f"{chapter.stem}.wav.verify.json"

        if args.skip_existing and output_wav.exists() and verify_log.exists():
            log_line(progress_log, f"Skip existing {chapter.stem}")
            continue

        cmd = [sys.executable, str(GENERATE), str(chapter), "-o", str(output_wav)]
        if args.reference_wav:
            cmd.extend(["--reference-wav", args.reference_wav])
        if args.reference_text:
            cmd.extend(["--reference-text", args.reference_text])
        if args.skip_verify:
            cmd.append("--skip-verify")

        log_line(progress_log, f"Processing {chapter.stem}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and output_wav.exists():
            if error_log.exists():
                error_log.unlink()
            log_line(progress_log, f"Finished {chapter.stem}")
            continue

        error_log.write_text(
            "STDOUT:\n"
            + result.stdout
            + "\n\nSTDERR:\n"
            + result.stderr,
            encoding="utf-8",
        )
        log_line(progress_log, f"Failed {chapter.stem}; see {error_log}")
        if not args.keep_going:
            return 1

    log_line(progress_log, "Batch complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
