#!/usr/bin/env python3
"""
generate.py — Reliable BreezyVoice generation with verification.
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from voiceprint import VoiceprintManager, DEFAULT_SR  # noqa: E402


CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_VOICEPRINT_CACHE = "/tmp/lin_tts_voiceprint.npy"


def load_config():
    return json.loads(CONFIG_PATH.read_text())


def load_lexicon(path):
    if not os.path.exists(path):
        return {}
    raw = json.loads(Path(path).read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, str)}


def apply_lexicon(text, lexicon):
    sorted_keys = sorted(lexicon.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in text:
            text = text.replace(key, lexicon[key])
    return text


def clean_markdown_text(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.M)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("---", "").replace("###", "").replace("##", "").replace("#", "")

    cleaned_lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            cleaned_lines.append(line)
        elif cleaned_lines and cleaned_lines[-1] != "":
            cleaned_lines.append("")

    cleaned = "\n".join(cleaned_lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def chunk_text(text, max_chars=180):
    parts = re.split(r"([。！？!?；;\n])", text)
    chunks = []
    current = ""
    for i in range(0, len(parts), 2):
        sentence = parts[i]
        punctuation = parts[i + 1] if i + 1 < len(parts) else ""
        piece = f"{sentence}{punctuation}"
        if not piece.strip():
            continue
        if len(current) + len(piece) > max_chars and current.strip():
            chunks.append(current.strip())
            current = piece
        else:
            current += piece
    if current.strip():
        chunks.append(current.strip())
    return chunks


def build_voiceprint_manager(cfg):
    ref_dir = cfg.get("voiceprint_reference_dir")
    if not ref_dir:
        return None

    cache_path = cfg.get("voiceprint_cache_path", DEFAULT_VOICEPRINT_CACHE)
    mgr = VoiceprintManager(voiceprint_path=cache_path)
    if not mgr.is_enrolled:
        mgr.enroll_from_directory(ref_dir)
    return mgr


def resample_simple(audio, sr_in, sr_out=DEFAULT_SR):
    if sr_in == sr_out:
        return audio.astype(np.float32)
    ratio = sr_in / sr_out
    indices = np.round(np.arange(0, len(audio), ratio)).astype(int)
    indices = indices[indices < len(audio)]
    return audio[indices].astype(np.float32)


def estimate_pitch(audio, sr):
    if len(audio) < sr:
        return None

    frame_len = int(0.04 * sr)
    hop = int(0.02 * sr)
    min_f0, max_f0 = 70.0, 300.0
    min_lag = int(sr / max_f0)
    max_lag = int(sr / min_f0)
    f0_values = []

    for start in range(0, len(audio) - frame_len, hop):
        frame = audio[start : start + frame_len]
        frame = frame - np.mean(frame)
        rms = np.sqrt(np.mean(frame**2))
        if rms < 0.01:
            continue

        corr = np.correlate(frame, frame, mode="full")[frame_len - 1 :]
        if corr[0] <= 0:
            continue

        search = corr[min_lag:max_lag]
        if len(search) == 0:
            continue

        lag = int(np.argmax(search)) + min_lag
        strength = corr[lag] / (corr[0] + 1e-9)
        if strength < 0.25:
            continue

        f0 = sr / lag
        if min_f0 <= f0 <= max_f0:
            f0_values.append(f0)

    if not f0_values:
        return None

    arr = np.array(f0_values)
    return {
        "median_hz": float(np.median(arr)),
        "mean_hz": float(np.mean(arr)),
        "p10_hz": float(np.percentile(arr, 10)),
        "p90_hz": float(np.percentile(arr, 90)),
        "frames": int(len(arr)),
    }


def verify_output(cfg, output_path):
    verification = {"output_path": output_path}
    voice_mgr = build_voiceprint_manager(cfg)

    audio, sr = sf.read(output_path)
    if getattr(audio, "ndim", 1) > 1:
        audio = audio[:, 0]
    mono = resample_simple(audio, sr, DEFAULT_SR)

    if voice_mgr is not None:
        score = voice_mgr.verify(mono, DEFAULT_SR)
        verification["voiceprint_score"] = float(score)
        threshold = float(cfg.get("voiceprint_threshold", 0.93))
        verification["voiceprint_threshold"] = threshold
        verification["voiceprint_ok"] = score >= threshold
    else:
        verification["voiceprint_score"] = None
        verification["voiceprint_threshold"] = None
        verification["voiceprint_ok"] = True

    pitch = estimate_pitch(mono, DEFAULT_SR)
    verification["pitch"] = pitch
    if pitch is None:
        verification["male_pitch_ok"] = False
    else:
        min_hz = float(cfg.get("male_pitch_min_hz", 70.0))
        max_hz = float(cfg.get("male_pitch_max_hz", 165.0))
        verification["male_pitch_range_hz"] = [min_hz, max_hz]
        verification["male_pitch_ok"] = min_hz <= pitch["median_hz"] <= max_hz

    verification["ok"] = bool(
        verification["voiceprint_ok"] and verification["male_pitch_ok"]
    )
    return verification


def inference_python(cfg):
    explicit = cfg.get("breezyvoice_python")
    if explicit:
        return explicit
    return str(Path(cfg["venv"]) / "bin" / "python")


async def synthesize_chunk_async(
    cfg,
    content,
    chunk_idx,
    total,
    out_dir,
    reference_wav,
    reference_text,
):
    repo = cfg["breezyvoice_repo"]
    model = cfg["breezyvoice_model"]
    python_bin = inference_python(cfg)
    chunk_out = os.path.abspath(os.path.join(out_dir, f"chunk_{chunk_idx:03d}.wav"))

    cmd = [
        python_bin,
        os.path.join(repo, "single_inference.py"),
        "--content_to_synthesize",
        content,
        "--speaker_prompt_text_transcription",
        reference_text,
        "--speaker_prompt_audio_path",
        reference_wav,
        "--output_path",
        chunk_out,
        "--model_path",
        model,
    ]

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["CUDA_VISIBLE_DEVICES"] = "-1"

    print(f"  [{chunk_idx + 1}/{total}] 合成中...", flush=True)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"chunk {chunk_idx:03d} failed\nSTDOUT:\n{result.stdout[-1200:]}\nSTDERR:\n{result.stderr[-1200:]}"
        )
    if not os.path.exists(chunk_out):
        raise RuntimeError(f"chunk {chunk_idx:03d} finished without output file")
    return chunk_out


def synthesize_chunk(cfg, content, chunk_idx, total, out_dir, reference_wav, reference_text):
    return asyncio.run(
        synthesize_chunk_async(
            cfg,
            content,
            chunk_idx,
            total,
            out_dir,
            reference_wav,
            reference_text,
        )
    )


def merge_wavs(wav_paths, output_path):
    if not wav_paths:
        raise RuntimeError("no chunk wavs to merge")

    list_file = output_path + ".list.txt"
    with open(list_file, "w", encoding="utf-8") as handle:
        for wav_path in wav_paths:
            handle.write(f"file '{os.path.abspath(wav_path)}'\n")

    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output_path],
        capture_output=True,
        text=True,
    )
    if os.path.exists(list_file):
        os.remove(list_file)
    if result.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"ffmpeg merge failed: {result.stderr[-1200:]}")


def write_verification_report(output_path, report):
    report_path = Path(output_path).with_suffix(Path(output_path).suffix + ".verify.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("article", help="文章檔")
    parser.add_argument("-o", "--output", help="輸出路徑")
    parser.add_argument("--reference-wav", help="override reference wav path")
    parser.add_argument("--reference-text", help="override reference text path")
    parser.add_argument("--chunk-chars", type=int, help="override chunk size")
    parser.add_argument("--skip-clean", action="store_true", help="disable markdown cleanup")
    parser.add_argument("--skip-verify", action="store_true", help="disable voice/pitch verification")
    parser.add_argument("--keep-chunks", action="store_true", help="keep intermediate chunk wavs")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = load_config()

    article_path = Path(args.article)
    if not article_path.exists():
        raise FileNotFoundError(f"找不到文章: {article_path}")

    reference_wav = args.reference_wav or cfg["reference_wav"]
    reference_text_path = Path(args.reference_text or cfg["reference_text"])
    if not Path(reference_wav).exists():
        raise FileNotFoundError(f"找不到 reference 音檔: {reference_wav}")
    if not reference_text_path.exists():
        raise FileNotFoundError(f"找不到 reference 文字稿: {reference_text_path}")
    reference_text = reference_text_path.read_text().strip()

    raw_text = article_path.read_text()
    text = raw_text if args.skip_clean else clean_markdown_text(raw_text)
    text = apply_lexicon(text, load_lexicon(cfg["lexicon_path"]))
    if not text.strip():
        raise ValueError("清理後文章為空")

    if not args.output:
        stem = article_path.stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(cfg["output_dir"], f"{stem}_{timestamp}.wav")

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    chunk_chars = args.chunk_chars or int(cfg.get("chunk_chars", 180))
    chunks = chunk_text(text, max_chars=chunk_chars)
    if not chunks:
        raise ValueError("文章切 chunk 後為空")

    tmp_dir = os.path.join(cfg["output_dir"], "_chunks", Path(output_path).stem)
    os.makedirs(tmp_dir, exist_ok=True)
    for old in Path(tmp_dir).glob("*.wav"):
        old.unlink()

    chunk_wavs = []
    try:
        for idx, chunk in enumerate(chunks):
            wav = synthesize_chunk(
                cfg,
                chunk,
                idx,
                len(chunks),
                tmp_dir,
                reference_wav,
                reference_text,
            )
            chunk_wavs.append(wav)

        print("📦 正在合併...", flush=True)
        merge_wavs(chunk_wavs, output_path)

        report = {"ok": True, "skipped": bool(args.skip_verify)}
        if not args.skip_verify:
            report = verify_output(cfg, output_path)
            write_verification_report(output_path, report)
            if not report["ok"]:
                raise RuntimeError(
                    "輸出驗證失敗: "
                    f"voiceprint={report.get('voiceprint_score')} "
                    f"pitch={report.get('pitch', {}).get('median_hz') if report.get('pitch') else None}"
                )

        print(f"✅ 完成: {output_path}", flush=True)
        if report.get("voiceprint_score") is not None:
            print(
                f"   voiceprint={report['voiceprint_score']:.4f} "
                f"pitch={report.get('pitch', {}).get('median_hz', 'n/a')}",
                flush=True,
            )
        return 0
    finally:
        if not args.keep_chunks:
            for wav in chunk_wavs:
                try:
                    os.remove(wav)
                except OSError:
                    pass


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1)
