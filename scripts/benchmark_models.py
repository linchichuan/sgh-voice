#!/usr/bin/env python3
"""
benchmark_models.py — 模型精度批次測試
比較 Breeze-ASR-25 (4bit/fp16) vs Whisper Turbo 的辨識精度與速度。

用法：
    # 準備測試音檔（放到 test/audio/，對應正確答案放到 test/ground_truth/）
    python3 scripts/benchmark_models.py

    # 只測特定模型
    python3 scripts/benchmark_models.py --models breeze-asr-25-4bit,mlx-community/whisper-turbo

    # Claude Code /loop 用法
    # /loop "cd ~/voice-input && python3 scripts/benchmark_models.py && cat test/results/MODEL_BENCHMARK.md"

輸出：
    test/results/MODEL_BENCHMARK.md（Markdown 表格 + CER 統計）
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 確保專案 root 在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import LOCAL_MODEL_PATHS, BREEZE_MODELS

# ─── 設定 ───────────────────────────────────────────────
TEST_DIR = PROJECT_ROOT / "test"
AUDIO_DIR = TEST_DIR / "audio"
GROUND_TRUTH_DIR = TEST_DIR / "ground_truth"
RESULTS_DIR = TEST_DIR / "results"

# 預設測試模型
DEFAULT_MODELS = [
    "breeze-asr-25-4bit",
    "breeze-asr-25",
    "mlx-community/whisper-turbo",
]


def cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate（字元錯誤率）— 基於編輯距離"""
    ref = list(reference.replace(" ", ""))
    hyp = list(hypothesis.replace(" ", ""))
    if not ref:
        return 0.0 if not hyp else 1.0

    # 動態規劃計算編輯距離
    d = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        d[i][0] = i
    for j in range(len(hyp) + 1):
        d[0][j] = j
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)

    return d[len(ref)][len(hyp)] / len(ref)


def transcribe_with_model(audio_path: str, model_name: str) -> tuple[str, float]:
    """用指定模型辨識音檔，回傳 (辨識結果, 耗時秒數)"""
    import mlx_whisper

    # 解析模型路徑
    model_path = LOCAL_MODEL_PATHS.get(model_name, model_name)
    is_breeze = model_name in BREEZE_MODELS
    fp16 = is_breeze  # Breeze 模型用 fp16

    start = time.perf_counter()
    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=model_path,
        fp16=fp16,
        language="zh",
    )
    elapsed = time.perf_counter() - start
    text = result.get("text", "").strip()
    return text, elapsed


def run_benchmark(models: list[str]) -> str:
    """執行基準測試，回傳 Markdown 報告"""
    # 確認目錄存在
    if not AUDIO_DIR.exists():
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        print(f"⚠️  請將測試音檔放到 {AUDIO_DIR}/")
        print("   檔名範例：zh_01.wav, ja_01.wav, mix_zhen_01.wav, medical_01.wav")
        print(f"   對應正確答案放到 {GROUND_TRUTH_DIR}/")
        print("   檔名範例：zh_01.txt, ja_01.txt（與音檔同名，副檔名改 .txt）")
        return ""

    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 找所有測試音檔
    audio_files = sorted(
        f for f in AUDIO_DIR.iterdir()
        if f.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
    )
    if not audio_files:
        print(f"⚠️  {AUDIO_DIR}/ 內沒有音檔，請先準備測試資料")
        return ""

    print(f"📋 找到 {len(audio_files)} 個測試音檔")
    print(f"🤖 測試模型：{', '.join(models)}")
    print()

    # 結果收集
    results = []  # [{file, model, text, cer, time}]

    for audio_file in audio_files:
        gt_file = GROUND_TRUTH_DIR / f"{audio_file.stem}.txt"
        ground_truth = ""
        if gt_file.exists():
            ground_truth = gt_file.read_text(encoding="utf-8").strip()

        print(f"🎵 {audio_file.name}", end="")
        if ground_truth:
            print(f"  (正解: {ground_truth[:30]}...)" if len(ground_truth) > 30 else f"  (正解: {ground_truth})")
        else:
            print(f"  (無正解檔案，跳過 CER 計算)")

        for model in models:
            try:
                text, elapsed = transcribe_with_model(str(audio_file), model)
                error_rate = cer(ground_truth, text) if ground_truth else -1
                results.append({
                    "file": audio_file.name,
                    "model": model,
                    "text": text,
                    "cer": error_rate,
                    "time": elapsed,
                })
                cer_str = f"CER={error_rate:.1%}" if error_rate >= 0 else "N/A"
                print(f"  ├─ {model}: {elapsed:.2f}s | {cer_str} | {text[:60]}")
            except Exception as e:
                print(f"  ├─ {model}: ❌ {e}")
                results.append({
                    "file": audio_file.name,
                    "model": model,
                    "text": f"ERROR: {e}",
                    "cer": -1,
                    "time": -1,
                })
        print()

    # ─── 生成 Markdown 報告 ───────────────────────────
    report = generate_report(models, audio_files, results)

    # 儲存
    report_path = RESULTS_DIR / "MODEL_BENCHMARK.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"✅ 報告已儲存：{report_path}")

    # 同時儲存 JSON 原始資料（方便後續分析）
    json_path = RESULTS_DIR / "benchmark_raw.json"
    json_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return report


def generate_report(models: list[str], audio_files: list, results: list[dict]) -> str:
    """生成 Markdown 格式的基準測試報告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# SGH Voice — 模型基準測試報告",
        f"",
        f"> 測試時間：{now}",
        f"> 測試音檔數：{len(audio_files)}",
        f"> 測試模型：{', '.join(models)}",
        f"",
        f"## 總覽",
        f"",
        f"| 模型 | 平均 CER | 平均耗時 | 最快 | 最慢 |",
        f"|------|---------|---------|------|------|",
    ]

    for model in models:
        model_results = [r for r in results if r["model"] == model and r["time"] > 0]
        if not model_results:
            lines.append(f"| {model} | N/A | N/A | N/A | N/A |")
            continue

        cer_vals = [r["cer"] for r in model_results if r["cer"] >= 0]
        times = [r["time"] for r in model_results]

        avg_cer = f"{sum(cer_vals)/len(cer_vals):.1%}" if cer_vals else "N/A"
        avg_time = f"{sum(times)/len(times):.2f}s"
        min_time = f"{min(times):.2f}s"
        max_time = f"{max(times):.2f}s"
        lines.append(f"| {model} | {avg_cer} | {avg_time} | {min_time} | {max_time} |")

    lines += [
        "",
        "## 詳細結果",
        "",
        "| 音檔 | 模型 | CER | 耗時 | 辨識結果 |",
        "|------|------|-----|------|---------|",
    ]

    for r in results:
        cer_str = f"{r['cer']:.1%}" if r["cer"] >= 0 else "N/A"
        time_str = f"{r['time']:.2f}s" if r["time"] > 0 else "ERR"
        text = r["text"][:50] + "..." if len(r["text"]) > 50 else r["text"]
        # 轉義 Markdown 表格中的 pipe
        text = text.replace("|", "\\|")
        lines.append(f"| {r['file']} | {r['model']} | {cer_str} | {time_str} | {text} |")

    # 勝者分析
    lines += ["", "## 勝者分析", ""]
    for audio_file in audio_files:
        file_results = [r for r in results if r["file"] == audio_file.name and r["cer"] >= 0]
        if len(file_results) >= 2:
            best = min(file_results, key=lambda r: r["cer"])
            lines.append(f"- **{audio_file.name}**: {best['model']} 勝出 (CER {best['cer']:.1%})")

    lines += [
        "",
        "---",
        f"*Generated by SGH Voice benchmark_models.py @ {now}*",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="SGH Voice 模型精度批次測試")
    parser.add_argument(
        "--models",
        type=str,
        default=",".join(DEFAULT_MODELS),
        help="逗號分隔的模型名稱列表",
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    run_benchmark(models)


if __name__ == "__main__":
    main()
