"""Compare candidate Japanese CPU STT models for the Windows offline edition.

CI-only evaluation tool. It downloads public, pinned model snapshots and a small
public Japanese speech sample (Google FLEURS ja_jp dev split, CC-BY 4.0), then
runs each model through the same vendored faster-whisper engine and decoding
parameters as windows_client.local_stt. Nothing here ships in the application.

Metrics are a model-selection signal, not a clinical accuracy claim: FLEURS is
read Wikipedia text, not medical dictation.

Usage (Windows CI):
    python scripts/benchmark_windows_ja_stt.py --work-dir <dir> [--clips 40]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tarfile
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]

CANDIDATES = {  # most decision-relevant first: a deadline cut drops the tail
    "kotoba-v2.0": {"repo": "kotoba-tech/kotoba-whisper-v2.0-faster", "label": "kotoba-whisper v2.0 (Japanese)"},
    "large-v3-turbo": {"repo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo", "label": "Whisper large-v3-turbo"},
    "small": {"repo": "Systran/faster-whisper-small", "label": "Whisper small"},
    "base": {"repo": "Systran/faster-whisper-base", "label": "Whisper base (current preview)"},
}
MODEL_FILES = ["config.json", "model.bin", "tokenizer.json", "preprocessor_config.json",
               "vocabulary.txt", "vocabulary.json"]
FLEURS_REPO = "google/fleurs"
FLEURS_TSV = "data/ja_jp/dev.tsv"
FLEURS_AUDIO = "data/ja_jp/audio/dev.tar.gz"
LONG_FORM = ("kotoba-tech/kotoba-whisper-v1.0-ggml", "sample_ja_speech.wav")
# Same decoding contract as windows_client.local_stt.LocalTranscriber.transcribe.
DECODE = dict(language="ja", task="transcribe", beam_size=5, temperature=0.0,
              condition_on_previous_text=False, vad_filter=False,
              initial_prompt=None, hotwords=None, log_progress=False)


def normalize(text):
    """NFKC, drop whitespace/punctuation/symbols: CER compares characters only."""
    text = unicodedata.normalize("NFKC", text).lower()
    return "".join(ch for ch in text
                   if not ch.isspace() and unicodedata.category(ch)[0] not in "PSZ")


def edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def load_pcm16k(path):
    import numpy as np
    import soundfile
    audio, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if rate != 16000:
        target = np.arange(0, len(audio) * 16000 / rate) * rate / 16000
        audio = np.interp(target, np.arange(len(audio)), audio).astype("float32")
    return audio


def prepare(work, clips):
    from huggingface_hub import HfApi, hf_hub_download, snapshot_download
    api = HfApi()
    models = {}
    for key, spec in CANDIDATES.items():
        info = api.model_info(spec["repo"], files_metadata=True)
        names = {s.rfilename: s.size for s in info.siblings}
        allow = [name for name in MODEL_FILES if name in names]
        path = snapshot_download(spec["repo"], revision=info.sha, allow_patterns=allow,
                                 local_dir=str(work / "models" / key))
        files = []
        for name in allow:
            digest = hashlib.sha256()
            with open(Path(path) / name, "rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            files.append({"name": name, "size": names[name], "sha256": digest.hexdigest()})
        models[key] = {**spec, "revision": info.sha, "path": path, "files": files,
                       "bytes": sum(names[n] for n in allow)}
        print("MODEL_PIN " + json.dumps({"key": key, "repository": spec["repo"], "revision": info.sha,
                                         "license": getattr(info.card_data, "license", None) if info.card_data else None,
                                         "files": files}))
    tsv = Path(hf_hub_download(FLEURS_REPO, FLEURS_TSV, repo_type="dataset"))
    seen, chosen = set(), {}
    for line in tsv.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if len(cols) < 3 or cols[0] in seen:
            continue
        seen.add(cols[0])
        chosen[cols[1]] = cols[2]
        if len(chosen) >= clips:
            break
    archive = hf_hub_download(FLEURS_REPO, FLEURS_AUDIO, repo_type="dataset")
    audio_dir = work / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = Path(member.name).name
            if member.isfile() and name in chosen:
                (audio_dir / name).write_bytes(tar.extractfile(member).read())
    dataset = [{"file": str(audio_dir / n), "reference": t}
               for n, t in chosen.items() if (audio_dir / n).is_file()]
    long_form = hf_hub_download(LONG_FORM[0], LONG_FORM[1])
    manifest = {"models": models, "dataset": dataset, "long_form": long_form,
                "dataset_source": f"{FLEURS_REPO} ja_jp dev (CC-BY 4.0)"}
    (work / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def peak_memory_mb():
    try:
        import psutil
        info = psutil.Process().memory_info()
        return round(getattr(info, "peak_wset", info.rss) / 1e6)
    except Exception:
        return None


def run_one(work, key, threads, long_form=False):
    """Child process: one model, so peak memory is attributable to it."""
    sys.path.insert(0, str(ROOT))
    from windows_client.local_stt import enforce_offline_environment
    enforce_offline_environment()
    from windows_client._vendor.faster_whisper import WhisperModel
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    model_info = manifest["models"][key]
    started = time.perf_counter()
    model = WhisperModel(model_info["path"], device="cpu", compute_type="int8",
                         cpu_threads=threads, num_workers=1, local_files_only=True)
    load_s = time.perf_counter() - started
    rows, errors, ref_chars = [], 0, 0
    for item in manifest["dataset"]:
        audio = load_pcm16k(item["file"])
        started = time.perf_counter()
        segments, _info = model.transcribe(audio, **DECODE)
        hypothesis = "".join(segment.text for segment in segments).strip()
        elapsed = time.perf_counter() - started
        ref, hyp = normalize(item["reference"]), normalize(hypothesis)
        distance = edit_distance(ref, hyp)
        errors += distance
        ref_chars += len(ref)
        rows.append({"audio_s": round(len(audio) / 16000, 2), "decode_s": round(elapsed, 2),
                     "cer": round(distance / max(1, len(ref)), 4), "punctuated": any(c in hypothesis for c in "、。"),
                     "reference": item["reference"], "hypothesis": hypothesis})
    long_audio, long_text, long_s = [], "", 0.0
    if long_form:
        long_audio = load_pcm16k(manifest["long_form"])
        started = time.perf_counter()
        segments, _info = model.transcribe(long_audio, **DECODE)
        long_text = "".join(segment.text for segment in segments).strip()
        long_s = time.perf_counter() - started
    audio_total = sum(r["audio_s"] for r in rows)
    decode_total = sum(r["decode_s"] for r in rows)
    latencies = sorted(r["decode_s"] for r in rows)
    result = {
        "key": key, "label": model_info["label"], "repo": model_info["repo"],
        "revision": model_info["revision"], "model_mb": round(model_info["bytes"] / 1e6),
        "threads": threads, "load_s": round(load_s, 1), "clips": len(rows),
        "cer": round(errors / max(1, ref_chars), 4),
        "rtf": round(decode_total / max(0.01, audio_total), 3),
        "latency_p50_s": round(statistics.median(latencies), 2),
        "latency_p90_s": round(latencies[int(len(latencies) * 0.9) - 1], 2),
        "first_clip_s": rows[0]["decode_s"],
        "punctuated_ratio": round(sum(r["punctuated"] for r in rows) / max(1, len(rows)), 2),
        "long_form_audio_s": round(len(long_audio) / 16000, 1), "long_form_decode_s": round(long_s, 1),
        "long_form_excerpt": long_text[:200], "peak_mb": peak_memory_mb(), "rows": rows,
    }
    (work / f"result-{key}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {k: v for k, v in result.items() if k not in ("rows", "long_form_excerpt")}
    print("BENCHMARK_RESULT " + json.dumps(summary), flush=True)


def report(work):
    results = [json.loads((work / f"result-{k}.json").read_text(encoding="utf-8"))
               for k in CANDIDATES if (work / f"result-{k}.json").is_file()]
    lines = ["## Japanese CPU STT benchmark (int8, Windows CI runner)", "",
             "| model | size MB | CER | RTF | p50 s | p90 s | load s | peak MB | 句読点 | long-form s (audio s) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['label']} | {r['model_mb']} | {r['cer']:.1%} | {r['rtf']} | {r['latency_p50_s']} | "
                     f"{r['latency_p90_s']} | {r['load_s']} | {r['peak_mb']} | {r['punctuated_ratio']:.0%} | "
                     f"{r['long_form_decode_s']} ({r['long_form_audio_s']}) |")
    lines += ["", f"Clips: {results[0]['clips'] if results else 0} from FLEURS ja_jp dev (read speech, CC-BY 4.0). "
              "CER ignores punctuation/whitespace after NFKC. Not a medical-accuracy result.", ""]
    for r in results:
        lines += [f"### {r['label']} — `{r['repo']}@{r['revision']}`", ""]
        for row in r["rows"][:8]:
            lines += [f"- REF: {row['reference']}", f"  HYP: {row['hypothesis']} (CER {row['cer']:.0%}, {row['decode_s']}s)"]
        lines += [f"- LONG: {r['long_form_excerpt']}", ""]
    text = "\n".join(lines)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(text + "\n")
    print("BENCHMARK_JSON " + json.dumps([{k: v for k, v in r.items() if k != "rows"} for r in results],
                                         ensure_ascii=False))


def main():
    # Windows CI consoles default to cp1252; Japanese report text must not crash.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--clips", type=int, default=40)
    parser.add_argument("--threads", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--long-form", action="store_true", help="also time a ~3.5 min recording")
    parser.add_argument("--deadline", type=float, default=0, help="total seconds; later models are skipped")
    parser.add_argument("--only", help=argparse.SUPPRESS)
    args = parser.parse_args()
    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    if args.only:
        run_one(work, args.only, args.threads, args.long_form)
        return
    started = time.monotonic()
    prepare(work, args.clips)
    for key in CANDIDATES:
        remaining = args.deadline - (time.monotonic() - started) if args.deadline else None
        if remaining is not None and remaining < 60:
            print(f"::warning::{key} skipped: benchmark deadline reached")
            continue
        command = [sys.executable, __file__, "--work-dir", str(work), "--threads", str(args.threads), "--only", key]
        if args.long_form:
            command.append("--long-form")
        try:
            completed = subprocess.run(command, timeout=remaining)
            if completed.returncode != 0:
                print(f"::warning::{key} benchmark failed with exit code {completed.returncode}")
        except subprocess.TimeoutExpired:
            print(f"::warning::{key} stopped at the benchmark deadline")
    report(work)


if __name__ == "__main__":
    main()
