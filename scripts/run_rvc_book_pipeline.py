#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path("/Users/lin/voice-input")
CLEANED_TEXT = Path("/Volumes/Satechi_SSD/voice-input/tts-data/cleaned_text")
OUT_ROOT = ROOT / "tts" / "output"
RVC_ROOT = ROOT / "rvc_work"
RVC_PYTHON = Path("/Volumes/Satechi_SSD/voice-input/tts-data/venv/bin/python")

FINAL_ROOT = OUT_ROOT / "rvc_books"
BASE_ROOT = OUT_ROOT / "book_base"
WORK_ROOT = OUT_ROOT / "rvc_pipeline_work"
LOG_PATH = FINAL_ROOT / "pipeline.log"

MODEL_NAME = "lin_male_v2_48k.pth"
CHUNK_SECONDS = 20


@dataclass(frozen=True)
class Job:
    lang: str
    slug: str
    text_path: Path | None
    base_path: Path | None
    generated_base_path: Path
    final_path: Path
    voice: str
    copy_final_from: Path | None = None


def log(message: str) -> None:
    FINAL_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    import shlex

    log("$ " + shlex.join(cmd))
    start = time.monotonic()
    with subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as proc:
        assert proc.stdout is not None
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            for line in proc.stdout:
                fh.write(line)
                fh.flush()
        rc = proc.wait()
    elapsed = time.monotonic() - start
    log(f"command finished rc={rc} elapsed={elapsed:.1f}s")
    if rc != 0:
        raise RuntimeError(f"command failed with rc={rc}: {' '.join(cmd)}")


def run_with_input(cmd: list[str], input_text: str) -> None:
    import shlex

    log("$ " + shlex.join(cmd) + " < text")
    start = time.monotonic()
    proc = subprocess.run(
        cmd,
        input=input_text,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        if proc.stdout:
            fh.write(proc.stdout)
    elapsed = time.monotonic() - start
    log(f"command finished rc={proc.returncode} elapsed={elapsed:.1f}s")
    if proc.returncode != 0:
        raise RuntimeError(f"command failed with rc={proc.returncode}: {' '.join(cmd)}")


def ffprobe_duration(path: Path) -> float | None:
    if not path.exists() or path.stat().st_size <= 1024:
        return None
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def valid_wav(path: Path, min_duration: float = 1.0) -> bool:
    duration = ffprobe_duration(path)
    return duration is not None and duration >= min_duration


def require_paths() -> None:
    missing = [
        path
        for path in [
            CLEANED_TEXT,
            RVC_ROOT,
            RVC_PYTHON,
            RVC_ROOT / "tools" / "infer_batch_rvc.py",
            RVC_ROOT / "assets" / "weights" / MODEL_NAME,
        ]
        if not path.exists()
    ]
    if missing:
        raise SystemExit("Missing required paths:\n" + "\n".join(str(path) for path in missing))


def sorted_txts(path: Path) -> list[Path]:
    return sorted(p for p in path.glob("*.txt") if not p.name.startswith("_"))


def build_jobs() -> list[Job]:
    jobs: list[Job] = []

    zh_legacy_bases = {
        "ch00": OUT_ROOT / "自傳_00_序章.wav",
        "ch01": OUT_ROOT / "ch01_system_base.wav",
        "ch10": OUT_ROOT / "ch10_base.wav",
    }
    zh_existing_final = OUT_ROOT / "rvc_lin" / "自傳_00_序章_HD降噪版.wav"
    for text_path in sorted((CLEANED_TEXT / "tts").glob("ch[0-9][0-9].txt")):
        slug = text_path.stem
        jobs.append(
            Job(
                lang="zh",
                slug=slug,
                text_path=text_path,
                base_path=zh_legacy_bases.get(slug),
                generated_base_path=BASE_ROOT / "zh" / f"{slug}_base.wav",
                final_path=FINAL_ROOT / "zh" / f"{slug}_LIN_HD.wav",
                voice="Meijia",
                copy_final_from=zh_existing_final if slug == "ch00" and valid_wav(zh_existing_final) else None,
            )
        )

    for text_path in sorted_txts(CLEANED_TEXT / "tts_jp"):
        slug = text_path.stem
        jobs.append(
            Job(
                lang="jp",
                slug=slug,
                text_path=text_path,
                base_path=OUT_ROOT / "jp_base" / f"{slug}_base.wav",
                generated_base_path=BASE_ROOT / "jp" / f"{slug}_base.wav",
                final_path=FINAL_ROOT / "jp" / f"{slug}_LIN_HD.wav",
                voice="Kyoko",
            )
        )

    for text_path in sorted_txts(CLEANED_TEXT / "tts_en"):
        slug = text_path.stem
        jobs.append(
            Job(
                lang="en",
                slug=slug,
                text_path=text_path,
                base_path=OUT_ROOT / "en_base" / f"{slug}_base.wav",
                generated_base_path=BASE_ROOT / "en" / f"{slug}_base.wav",
                final_path=FINAL_ROOT / "en" / f"{slug}_LIN_HD.wav",
                voice="Daniel",
            )
        )

    return jobs


def generate_base(job: Job) -> Path:
    if job.base_path and valid_wav(job.base_path):
        return job.base_path
    if valid_wav(job.generated_base_path):
        return job.generated_base_path
    if not job.text_path:
        raise RuntimeError(f"{job.lang}/{job.slug}: no base wav and no text source")

    job.generated_base_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_aiff = job.generated_base_path.with_suffix(".aiff")
    log(f"{job.lang}/{job.slug}: generating base with macOS say voice={job.voice}")
    try:
        text = job.text_path.read_text(encoding="utf-8")
        run_with_input(["say", "-v", job.voice, "-o", str(tmp_aiff)], text)
        run(["ffmpeg", "-y", "-i", str(tmp_aiff), "-ar", "48000", "-ac", "1", str(job.generated_base_path)])
    finally:
        tmp_aiff.unlink(missing_ok=True)

    if not valid_wav(job.generated_base_path):
        raise RuntimeError(f"{job.lang}/{job.slug}: generated base is invalid")
    return job.generated_base_path


def rvc_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(RVC_ROOT),
            "NUMBA_CACHE_DIR": "/tmp/numba_cache",
            "weight_root": str(RVC_ROOT / "assets" / "weights"),
            "index_root": str(RVC_ROOT / "logs"),
            "outside_index_root": str(RVC_ROOT / "assets" / "indices"),
            "rmvpe_root": str(RVC_ROOT / "assets" / "rmvpe"),
        }
    )
    return env


def split_audio(base_path: Path, chunks_in: Path) -> None:
    chunks_in.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(base_path),
            "-ar",
            "48000",
            "-ac",
            "1",
            "-f",
            "segment",
            "-segment_time",
            str(CHUNK_SECONDS),
            "-reset_timestamps",
            "1",
            str(chunks_in / "chunk_%04d.wav"),
        ]
    )


def convert_chunks(chunks_in: Path, chunks_out: Path) -> None:
    chunks_out.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(RVC_PYTHON),
            "tools/infer_batch_rvc.py",
            "--input_path",
            str(chunks_in),
            "--model_name",
            MODEL_NAME,
            "--index_path",
            "",
            "--f0method",
            "pm",
            "--opt_path",
            str(chunks_out),
            "--index_rate",
            "0",
            "--filter_radius",
            "0",
            "--resample_sr",
            "48000",
            "--rms_mix_rate",
            "0.25",
            "--protect",
            "0.33",
            "--device",
            "cpu",
        ],
        cwd=RVC_ROOT,
        env=rvc_env(),
    )


def concat_chunks(chunks_out: Path, converted_path: Path) -> None:
    chunk_paths = sorted(chunks_out.glob("chunk_*.wav"))
    if not chunk_paths:
        raise RuntimeError(f"no converted chunks in {chunks_out}")
    concat_txt = converted_path.with_suffix(".concat.txt")
    with concat_txt.open("w", encoding="utf-8") as fh:
        for chunk in chunk_paths:
            fh.write(f"file '{chunk}'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(converted_path)])


def hd_filter(converted_path: Path, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_final = final_path.with_suffix(".tmp.wav")
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(converted_path),
            "-af",
            "highpass=f=80,afftdn=nf=-25,loudnorm=I=-23:TP=-1.5:LRA=11",
            str(tmp_final),
        ]
    )
    if not valid_wav(tmp_final):
        raise RuntimeError(f"HD output invalid: {tmp_final}")
    tmp_final.replace(final_path)


def process_job(job: Job, *, force: bool, keep_work: bool) -> None:
    if job.copy_final_from and not force and valid_wav(job.copy_final_from):
        if not valid_wav(job.final_path):
            job.final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(job.copy_final_from, job.final_path)
            log(f"{job.lang}/{job.slug}: copied existing final sample -> {job.final_path}")
        else:
            log(f"{job.lang}/{job.slug}: final already exists, skip")
        return

    if not force and valid_wav(job.final_path):
        log(f"{job.lang}/{job.slug}: final already exists, skip")
        return

    base_path = generate_base(job)
    base_duration = ffprobe_duration(base_path) or 0.0
    log(f"{job.lang}/{job.slug}: start RVC, base_duration={base_duration:.1f}s")

    work_dir = WORK_ROOT / job.lang / job.slug
    chunks_in = work_dir / "chunks_in"
    chunks_out = work_dir / "chunks_out"
    converted_path = work_dir / f"{job.slug}_LIN_raw.wav"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    chunks_in.mkdir(parents=True, exist_ok=True)

    split_audio(base_path, chunks_in)
    convert_chunks(chunks_in, chunks_out)
    concat_chunks(chunks_out, converted_path)
    hd_filter(converted_path, job.final_path)

    final_duration = ffprobe_duration(job.final_path) or 0.0
    log(f"{job.lang}/{job.slug}: finished -> {job.final_path} duration={final_duration:.1f}s")
    if not keep_work:
        shutil.rmtree(work_dir, ignore_errors=True)


def select_jobs(jobs: list[Job], args: argparse.Namespace) -> list[Job]:
    langs = set(args.langs)
    if "all" in langs:
        langs = {"zh", "jp", "en"}
    selected = [job for job in jobs if job.lang in langs]
    if args.only:
        only = set(args.only)
        selected = [job for job in selected if job.slug in only or f"{job.lang}/{job.slug}" in only]
    if args.start:
        start_key = args.start
        for idx, job in enumerate(selected):
            if job.slug == start_key or f"{job.lang}/{job.slug}" == start_key:
                selected = selected[idx:]
                break
        else:
            raise SystemExit(f"--start target not found: {start_key}")
    if args.limit:
        selected = selected[: args.limit]
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", nargs="+", default=["zh"], choices=["zh", "jp", "en", "all"])
    parser.add_argument("--only", action="append", help="Run only a slug, e.g. ch01 or jp/03_...")
    parser.add_argument("--start", help="Start from a slug within the selected queue")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    require_paths()
    jobs = select_jobs(build_jobs(), args)
    if not jobs:
        log("no jobs selected")
        return 0

    log("selected jobs: " + ", ".join(f"{job.lang}/{job.slug}" for job in jobs))
    if args.dry_run:
        for job in jobs:
            base = job.base_path if job.base_path and valid_wav(job.base_path) else job.generated_base_path
            state = "done" if valid_wav(job.final_path) else "pending"
            log(f"dry-run {state}: {job.lang}/{job.slug} base={base} final={job.final_path}")
        return 0

    failures = 0
    for job in jobs:
        try:
            process_job(job, force=args.force, keep_work=args.keep_work)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            log(f"ERROR {job.lang}/{job.slug}: {exc}")
            break
    if failures:
        return 1
    log("queue completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
