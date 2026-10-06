#!/usr/bin/env python3
"""CI-only: compare small local LLMs for Japanese SOAP drafting on a Windows CPU.

Input is a fictional consultation transcript (no patient data) written like
the recognizer's output: no speaker labels, one segment per line. Each
candidate GGUF runs under the official llama.cpp Windows CPU build, started on
127.0.0.1 inside the CI runner only. The script records the llama.cpp release
and file hashes, speed (prompt and generation tokens/s), peak memory, and
simple fact checks (values that must appear, items that were never said).
Outputs are printed in full for human review. Never packaged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
import zipfile

TRANSCRIPT = Path(__file__).resolve().parent / "fixtures" / "consultation-ja-fictional.txt"

CANDIDATES = [
    # id, repo, file, context, license
    ("qwen3-4b-2507", "unsloth/Qwen3-4B-Instruct-2507-GGUF", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf", 16384, "Apache-2.0"),
    ("qwen3.5-4b", "unsloth/Qwen3.5-4B-GGUF", "Qwen3.5-4B-Q4_K_M.gguf", 16384, "Apache-2.0"),
    ("sarashina2.2-3b", "mmnga/sarashina2.2-3b-instruct-v0.1-gguf", "sarashina2.2-3b-instruct-v0.1-Q4_K_M.gguf", 8192, "MIT"),
    ("qwen3.5-2b", "unsloth/Qwen3.5-2B-GGUF", "Qwen3.5-2B-Q4_K_M.gguf", 16384, "Apache-2.0"),
]

SYSTEM = """あなたは日本の医療機関で使われる診療記録の下書き作成を補助します。
入力は、医師と患者の診察中の会話を音声認識で文字にしたものです。話者の区別はなく、誤認識を含むことがあります。
この会話から、医師が確認・修正するための SOAP 形式の下書きを日本語で作成してください。

規則:
- 会話の中で明示された情報だけを書く。推測、一般論、会話にない診断名・検査・薬剤を追加しない。
- 数値、単位、薬剤名、用量、回数は会話のとおりに書く。
- 「ない」「していない」など否定された症状は、否定であることがわかるように書く。
- 会話に該当する情報がない項目は「記載なし」と書く。
- 出力は次の 4 つの見出しと箇条書きのみ。前置きや結びの文は書かない。
S（主観的情報）:
O（客観的情報）:
A（評価）:
P（計画）:"""

# Values that were said and must survive; items that were never said.
REQUIRED = {
    "BP 148/92": [r"148\s*/\s*92", r"148.{0,3}92"],
    "HbA1c 7.8": [r"7\.8"],
    "previous HbA1c 7.1": [r"7\.1"],
    "fasting glucose 162": [r"162"],
    "eGFR 68": [r"68"],
    "metformin 750 mg": [r"メトホルミン.{0,30}750", r"750.{0,30}メトホルミン"],
    "penicillin allergy": [r"ペニシリン"],
    "follow-up 4 weeks": [r"4\s*週", r"４週"],
    "home BP": [r"家庭血圧|自宅.{0,6}血圧|家.{0,6}血圧"],
}
FORBIDDEN = {
    "insulin": r"インスリン",
    "amlodipine": r"アムロジピン",
    "SGLT2/DPP-4": r"SGLT|DPP",
    "MRI/CT": r"MRI|ＭＲＩ|CT検査|頭部CT",
    "ECG": r"心電図",
    "antihypertensive started": r"降圧薬.{0,10}(開始|処方し|追加し)",
}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_llama(work, tag=None):
    api = "https://api.github.com/repos/ggml-org/llama.cpp/releases/" + (f"tags/{tag}" if tag else "latest")
    release = json.load(urllib.request.urlopen(api, timeout=60))
    asset = next(a for a in release["assets"] if re.fullmatch(r"llama-.*-bin-win-cpu-x64\.zip", a["name"]))
    archive = work / asset["name"]
    if not archive.exists():
        urllib.request.urlretrieve(asset["browser_download_url"], archive)
    folder = work / ("llama-" + release["tag_name"])
    if not folder.exists():
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(folder)
    server = next(folder.rglob("llama-server.exe"))
    print(f"LLAMA_PIN tag={release['tag_name']} asset={asset['name']} sha256={sha256(archive)}", flush=True)
    print("LLAMA_EXES " + " ".join(sorted(p.name for p in server.parent.glob("*.exe"))), flush=True)
    return server


def post(url, body, timeout):
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(request, timeout=timeout))


def check(text):
    missing = [name for name, patterns in REQUIRED.items() if not any(re.search(p, text) for p in patterns)]
    invented = [name for name, pattern in FORBIDDEN.items() if re.search(pattern, text)]
    headings = all(re.search(rf"(^|\n)\s*[#*]*\s*{h}", text) for h in "SOAP")
    return missing, invented, headings


def run(server, model, context, threads, transcript, timeout):
    port = 18089
    log = open(model.with_suffix(".server.log"), "w", encoding="utf-8", errors="replace")
    began = time.monotonic()
    process = subprocess.Popen([str(server), "-m", str(model), "-c", str(context), "-t", str(threads),
                                "--host", "127.0.0.1", "--port", str(port), "-np", "1"],
                               stdout=log, stderr=subprocess.STDOUT)
    peak = 0
    try:
        import psutil
        watched = psutil.Process(process.pid)
    except Exception:
        watched = None
    try:
        while True:
            if process.poll() is not None:
                raise RuntimeError(f"server exited {process.returncode}")
            try:
                if json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5)).get("status") == "ok":
                    break
            except Exception:
                pass
            if time.monotonic() - began > 600:
                raise RuntimeError("server did not become ready")
            time.sleep(1)
        load_seconds = time.monotonic() - began
        started = time.monotonic()
        body = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": transcript}],
                "temperature": 0.2, "top_p": 0.9, "max_tokens": 1500,
                "chat_template_kwargs": {"enable_thinking": False}}
        reply = post(f"http://127.0.0.1:{port}/v1/chat/completions", body, timeout)
        seconds = time.monotonic() - started
        if watched is not None:
            try:
                peak = watched.memory_info().peak_wset if hasattr(watched.memory_info(), "peak_wset") else watched.memory_info().rss
            except Exception:
                peak = 0
        text = reply["choices"][0]["message"].get("content") or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        timings = reply.get("timings", {})
        return text, load_seconds, seconds, timings, reply.get("usage", {}), peak
    finally:
        process.terminate()
        try:
            process.wait(30)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--llama-tag")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--deadline", type=float, default=2400)
    args = parser.parse_args(argv)
    from huggingface_hub import hf_hub_download
    deadline = time.monotonic() + args.deadline
    args.work_dir.mkdir(parents=True, exist_ok=True)
    server = fetch_llama(args.work_dir, args.llama_tag)
    transcript = TRANSCRIPT.read_text(encoding="utf-8")
    threads = max(1, os.cpu_count() or 1)
    print(f"TRANSCRIPT chars={len(transcript)} threads={threads}", flush=True)
    for name, repo, filename, context, license_name in CANDIDATES:
        if args.only and name not in args.only:
            continue
        remaining = deadline - time.monotonic()
        if remaining < 300:
            print(f"SKIP {name}: deadline", flush=True)
            continue
        try:
            path = Path(hf_hub_download(repo, filename))
            text, load_s, total_s, timings, usage, peak = run(server, path, context, threads, transcript, remaining - 60)
        except Exception as exc:
            print(f"BENCHMARK_RESULT {json.dumps({'model': name, 'error': type(exc).__name__ + ': ' + str(exc)[:300]})}", flush=True)
            continue
        missing, invented, headings = check(text)
        result = {
            "model": name, "repo": repo, "file": filename, "license": license_name,
            "file_gb": round(path.stat().st_size / 1e9, 2), "sha256": sha256(path),
            "load_s": round(load_s, 1), "total_s": round(total_s, 1),
            "prompt_tokens": timings.get("prompt_n", usage.get("prompt_tokens")),
            "prompt_tok_s": round(timings.get("prompt_per_second", 0), 1),
            "output_tokens": timings.get("predicted_n", usage.get("completion_tokens")),
            "gen_tok_s": round(timings.get("predicted_per_second", 0), 1),
            "peak_mem_gb": round(peak / 1e9, 2) if peak else None,
            "soap_headings": headings, "missing": missing, "invented": invented,
        }
        print(f"===== {name} output =====\n{text}\n===== end {name} =====", flush=True)
        print(f"BENCHMARK_RESULT {json.dumps(result, ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
