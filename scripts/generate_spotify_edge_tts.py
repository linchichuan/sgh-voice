#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import edge_tts


CLEANED_TEXT = Path("/Volumes/Satechi_SSD/voice-input/tts-data/cleaned_text")
OUT_ROOT = Path("/Users/lin/voice-input/tts/output/spotify_final")
WORK_ROOT = OUT_ROOT / "_work"
LEXICON_PATH = Path("/Users/lin/voice-input/tts/lexicon.json")
LOG_PATH = OUT_ROOT / "spotify_tts.log"

VOICE_BY_LANG = {
    "zh": "zh-TW-YunJheNeural",
    "en": "en-US-BrianNeural",
    "jp": "ja-JP-KeitaNeural",
}

MAX_CHARS_BY_LANG = {
    "zh": 850,
    "en": 1200,
    "jp": 850,
}

PUNCT_RE = re.compile(r"([。！？!?；;：:\n]+|(?<=[.!?])\s+)")
ANNOTATION_RE = re.compile(r"\[:[^\]]+\]")

TRAD_NORMALIZE = str.maketrans(
    {
        "豊": "豐",
        "薬": "藥",
        "医": "醫",
        "処": "處",
        "労": "勞",
        "関": "關",
        "駅": "驛",
        "稲": "稻",
        "会": "會",
    }
)


@dataclass(frozen=True)
class Job:
    lang: str
    text_path: Path
    final_path: Path
    voice: str


def log(message: str) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def run(cmd: list[str]) -> None:
    import shlex

    log("$ " + shlex.join(cmd))
    start = time.monotonic()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        if proc.stdout:
            fh.write(proc.stdout)
    elapsed = time.monotonic() - start
    log(f"command finished rc={proc.returncode} elapsed={elapsed:.1f}s")
    if proc.returncode != 0:
        raise RuntimeError(f"command failed rc={proc.returncode}: {' '.join(cmd)}")


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


def valid_audio(path: Path, min_duration: float = 1.0) -> bool:
    duration = ffprobe_duration(path)
    return duration is not None and duration >= min_duration


def load_lexicon() -> list[tuple[str, str]]:
    if not LEXICON_PATH.exists():
        return []
    raw = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    for key, value in raw.items():
        if key.startswith("_") or not isinstance(value, str):
            continue
        clean_value = ANNOTATION_RE.sub("", value).translate(TRAD_NORMALIZE)
        pairs.append((key, clean_value))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


def apply_lexicon(text: str, pairs: list[tuple[str, str]]) -> str:
    for src, dst in pairs:
        text = text.replace(src, dst)
    return text


def clean_text(text: str, *, lang: str, lexicon: list[tuple[str, str]]) -> str:
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if lang == "zh":
        text = apply_lexicon(text, lexicon)
    return text


def split_text(text: str, *, max_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    tokens = PUNCT_RE.split(text)
    for token in tokens:
        if token is None or token == "":
            continue
        if len(current) + len(token) > max_chars and current.strip():
            pieces.append(current.strip())
            current = token
        else:
            current += token
    if current.strip():
        pieces.append(current.strip())

    final: list[str] = []
    for piece in pieces:
        if len(piece) <= max_chars:
            final.append(piece)
            continue
        for start in range(0, len(piece), max_chars):
            chunk = piece[start : start + max_chars].strip()
            if chunk:
                final.append(chunk)
    return final


async def synthesize_edge(text: str, voice: str, out_mp3: Path, retries: int) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice)
            await communicate.save(str(out_mp3))
            if out_mp3.exists() and out_mp3.stat().st_size > 1024:
                return
            raise RuntimeError(f"empty media output: {out_mp3}")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log(f"edge-tts retry {attempt}/{retries}: {type(exc).__name__}: {exc}")
            await asyncio.sleep(min(10, 2 * attempt))
    raise RuntimeError(f"edge-tts failed after {retries} attempts: {last_error}")


def convert_mp3_to_wav(mp3_path: Path, wav_path: Path) -> None:
    run(["ffmpeg", "-y", "-i", str(mp3_path), "-ar", "48000", "-ac", "1", str(wav_path)])
    if not valid_audio(wav_path):
        raise RuntimeError(f"invalid wav chunk: {wav_path}")


def concat_wavs(chunk_wavs: list[Path], final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    concat_txt = final_path.with_suffix(".concat.txt")
    tmp_path = final_path.with_suffix(".tmp.wav")
    with concat_txt.open("w", encoding="utf-8") as fh:
        for chunk in chunk_wavs:
            fh.write(f"file '{chunk}'\n")
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-af",
            "loudnorm=I=-18:TP=-1.5:LRA=11",
            "-ar",
            "48000",
            "-ac",
            "1",
            str(tmp_path),
        ]
    )
    if not valid_audio(tmp_path):
        raise RuntimeError(f"invalid final wav: {tmp_path}")
    tmp_path.replace(final_path)
    concat_txt.unlink(missing_ok=True)


async def process_job(job: Job, *, force: bool, keep_work: bool, retries: int, lexicon: list[tuple[str, str]]) -> None:
    if not force and valid_audio(job.final_path):
        log(f"{job.lang}/{job.text_path.stem}: final exists, skip")
        return

    text = clean_text(job.text_path.read_text(encoding="utf-8"), lang=job.lang, lexicon=lexicon)
    chunks = split_text(text, max_chars=MAX_CHARS_BY_LANG[job.lang])
    if not chunks:
        raise RuntimeError(f"empty text after cleaning: {job.text_path}")

    work_dir = WORK_ROOT / job.lang / job.text_path.stem
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    log(f"{job.lang}/{job.text_path.stem}: start voice={job.voice} chunks={len(chunks)} chars={len(text)}")
    wav_chunks: list[Path] = []
    for idx, chunk in enumerate(chunks, start=1):
        mp3_path = work_dir / f"chunk_{idx:04d}.mp3"
        wav_path = work_dir / f"chunk_{idx:04d}.wav"
        log(f"{job.lang}/{job.text_path.stem}: synth chunk {idx}/{len(chunks)} chars={len(chunk)}")
        await synthesize_edge(chunk, job.voice, mp3_path, retries)
        convert_mp3_to_wav(mp3_path, wav_path)
        wav_chunks.append(wav_path)

    concat_wavs(wav_chunks, job.final_path)
    duration = ffprobe_duration(job.final_path) or 0
    log(f"{job.lang}/{job.text_path.stem}: finished -> {job.final_path} duration={duration:.1f}s")
    if not keep_work:
        shutil.rmtree(work_dir, ignore_errors=True)


def text_files(lang: str) -> list[Path]:
    if lang == "zh":
        return sorted((CLEANED_TEXT / "tts").glob("ch[0-9][0-9].txt"))
    if lang == "en":
        return sorted(p for p in (CLEANED_TEXT / "tts_en").glob("*.txt") if not p.name.startswith("_"))
    if lang == "jp":
        return sorted(p for p in (CLEANED_TEXT / "tts_jp").glob("*.txt") if not p.name.startswith("_"))
    raise ValueError(lang)


def build_jobs(langs: list[str]) -> list[Job]:
    if "all" in langs:
        langs = ["zh", "en", "jp"]
    jobs: list[Job] = []
    for lang in langs:
        for path in text_files(lang):
            jobs.append(
                Job(
                    lang=lang,
                    text_path=path,
                    final_path=OUT_ROOT / lang / f"{path.stem}.wav",
                    voice=VOICE_BY_LANG[lang],
                )
            )
    return jobs


def select_jobs(jobs: list[Job], args: argparse.Namespace) -> list[Job]:
    selected = jobs
    if args.only:
        only = set(args.only)
        selected = [job for job in selected if job.text_path.stem in only or f"{job.lang}/{job.text_path.stem}" in only]
    if args.start:
        for idx, job in enumerate(selected):
            if job.text_path.stem == args.start or f"{job.lang}/{job.text_path.stem}" == args.start:
                selected = selected[idx:]
                break
        else:
            raise SystemExit(f"--start not found: {args.start}")
    if args.limit:
        selected = selected[: args.limit]
    return selected


async def amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--langs", nargs="+", default=["all"], choices=["zh", "en", "jp", "all"])
    parser.add_argument("--only", action="append")
    parser.add_argument("--start")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--keep-work", action="store_true")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lexicon = load_lexicon()
    jobs = select_jobs(build_jobs(args.langs), args)
    log("selected jobs: " + ", ".join(f"{job.lang}/{job.text_path.stem}" for job in jobs))
    if args.dry_run:
        for job in jobs:
            state = "done" if valid_audio(job.final_path) else "pending"
            log(f"dry-run {state}: {job.lang}/{job.text_path.stem} -> {job.final_path}")
        return 0

    for job in jobs:
        try:
            await process_job(job, force=args.force, keep_work=args.keep_work, retries=args.retries, lexicon=lexicon)
        except Exception as exc:  # noqa: BLE001
            log(f"ERROR {job.lang}/{job.text_path.stem}: {type(exc).__name__}: {exc}")
            return 1
    log("queue completed")
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
