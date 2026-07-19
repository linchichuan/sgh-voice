#!/usr/bin/env python3
"""
benchmark_models.py — 模型精度批次測試
比較 Breeze-ASR-25 (4bit/fp16) vs Whisper Turbo 的辨識精度與速度。

用法：
    # 準備測試音檔（放到 test/audio/，對應正確答案放到 test/ground_truth/）
    python3 scripts/benchmark_models.py

    # 只測特定模型
    python3 scripts/benchmark_models.py --models breeze-asr-25-4bit,mlx-community/whisper-turbo

    # 指定所有音檔的語言（預設 auto 會依檔名 prefix 判斷）
    python3 scripts/benchmark_models.py --language ja

    # Claude Code /loop 用法
    # /loop "cd ~/voice-input && python3 scripts/benchmark_models.py && cat test/results/MODEL_BENCHMARK.md"

輸出：
    test/results/MODEL_BENCHMARK.md（Markdown 表格 + CER 統計）
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# 確保專案 root 在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import BREEZE_MODELS, LOCAL_MODEL_PATHS  # noqa: E402
from multilingual import script_profile  # noqa: E402

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

LANGUAGE_PROFILES = ("auto", "zh", "ja", "en")
_PROTECTED_TERM_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9_.+\-/]*"
    r"|[\u3040-\u30ff\u31f0-\u31ff]+"
    r"|[$¥€£]?\d(?:[\d,]*\d)?(?:\.\d+)*(?:%|[A-Za-z]{1,4})?"
)


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


def script_preservation_rate(reference: str, hypothesis: str) -> float:
    """Reference 中出現的 Han/Kana/Latin script 有多少仍存在於輸出。"""
    required = script_profile(reference)
    present = script_profile(hypothesis)
    indexes = [index for index, value in enumerate(required) if value]
    if not indexes:
        return 1.0
    return sum(1 for index in indexes if present[index]) / len(indexes)


def protected_term_recall(reference: str, hypothesis: str) -> float:
    """量測 Latin/Kana/數字專有 span 是否保留；不把中文 Han 當作可分詞 term。"""
    terms = _PROTECTED_TERM_RE.findall(reference or "")
    if not terms:
        return 1.0
    hypothesis_folded = (hypothesis or "").casefold()
    kept = 0
    for term in terms:
        candidate = term.casefold() if term.isascii() else term
        haystack = hypothesis_folded if term.isascii() else (hypothesis or "")
        if candidate in haystack:
            kept += 1
    return kept / len(terms)


def language_for_audio(audio_path: str | Path, override: str = "auto") -> str:
    """取得單一音檔的辨識語言 profile。

    auto 模式下依檔名 prefix 推導：zh_/ja_/en_ 會固定語言；
    mixed_/mix_ 或未知檔名保持 auto，讓模型自行偵測。
    """
    if override not in LANGUAGE_PROFILES:
        raise ValueError(f"Unsupported language profile: {override}")
    if override != "auto":
        return override

    stem = Path(audio_path).stem.lower()
    for prefix, language in (("zh_", "zh"), ("ja_", "ja"), ("en_", "en")):
        if stem.startswith(prefix):
            return language
    return "auto"


def transcribe_with_model(
    audio_path: str,
    model_name: str,
    language: str = "auto",
) -> tuple[str, float]:
    """用指定模型辨識音檔，回傳 (辨識結果, 耗時秒數)"""
    import mlx_whisper

    # 解析模型路徑
    model_path = LOCAL_MODEL_PATHS.get(model_name, model_name)
    is_breeze = model_name in BREEZE_MODELS
    fp16 = is_breeze  # Breeze 模型用 fp16

    start = time.perf_counter()
    transcribe_kwargs = {
        "path_or_hf_repo": model_path,
        "fp16": fp16,
    }
    if language != "auto":
        transcribe_kwargs["language"] = language

    result = mlx_whisper.transcribe(audio_path, **transcribe_kwargs)
    elapsed = time.perf_counter() - start
    text = result.get("text", "").strip()
    return text, elapsed


def run_benchmark(models: list[str], language: str = "auto") -> str:
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
    print(f"🌐 語言模式：{language}" + (" (依檔名推導)" if language == "auto" else " (全部覆寫)"))
    print()

    # 結果收集
    results = []  # [{file, model, text, cer, time}]

    for audio_file in audio_files:
        language_profile = language_for_audio(audio_file, language)
        gt_file = GROUND_TRUTH_DIR / f"{audio_file.stem}.txt"
        ground_truth = ""
        if gt_file.exists():
            ground_truth = gt_file.read_text(encoding="utf-8").strip()

        print(f"🎵 {audio_file.name} [{language_profile}]", end="")
        if ground_truth:
            print(f"  (正解: {ground_truth[:30]}...)" if len(ground_truth) > 30 else f"  (正解: {ground_truth})")
        else:
            print("  (無正解檔案，跳過 CER 計算)")

        for model in models:
            try:
                text, elapsed = transcribe_with_model(
                    str(audio_file),
                    model,
                    language=language_profile,
                )
                error_rate = cer(ground_truth, text) if ground_truth else -1
                script_rate = script_preservation_rate(ground_truth, text) if ground_truth else -1
                term_recall = protected_term_recall(ground_truth, text) if ground_truth else -1
                results.append({
                    "file": audio_file.name,
                    "language": language_profile,
                    "model": model,
                    "text": text,
                    "cer": error_rate,
                    "script_preservation": script_rate,
                    "protected_term_recall": term_recall,
                    "time": elapsed,
                })
                cer_str = f"CER={error_rate:.1%}" if error_rate >= 0 else "N/A"
                print(f"  ├─ {model}: {elapsed:.2f}s | {cer_str} | {text[:60]}")
            except Exception as e:
                print(f"  ├─ {model}: ❌ {e}")
                results.append({
                    "file": audio_file.name,
                    "language": language_profile,
                    "model": model,
                    "text": f"ERROR: {e}",
                    "cer": -1,
                    "script_preservation": -1,
                    "protected_term_recall": -1,
                    "time": -1,
                })
        print()

    # ─── 生成 Markdown 報告 ───────────────────────────
    report = generate_report(models, audio_files, results, language=language)

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


def generate_report(
    models: list[str],
    audio_files: list,
    results: list[dict],
    language: str = "auto",
) -> str:
    """生成 Markdown 格式的基準測試報告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# SGH Voice — 模型基準測試報告",
        "",
        f"> 測試時間：{now}",
        f"> 測試音檔數：{len(audio_files)}",
        f"> 測試模型：{', '.join(models)}",
        f"> 語言模式：{language}" + (" (依檔名推導)" if language == "auto" else " (全部覆寫)"),
        "",
        "## 總覽",
        "",
        "| 模型 | 平均 CER | Script 保留率 | 術語保留率 | 平均耗時 | 最快 | 最慢 |",
        "|------|---------|--------------|-----------|---------|------|------|",
    ]

    for model in models:
        model_results = [r for r in results if r["model"] == model and r["time"] > 0]
        if not model_results:
            lines.append(f"| {model} | N/A | N/A | N/A | N/A | N/A | N/A |")
            continue

        cer_vals = [r["cer"] for r in model_results if r["cer"] >= 0]
        script_vals = [r.get("script_preservation", -1) for r in model_results if r.get("script_preservation", -1) >= 0]
        term_vals = [r.get("protected_term_recall", -1) for r in model_results if r.get("protected_term_recall", -1) >= 0]
        times = [r["time"] for r in model_results]

        avg_cer = f"{sum(cer_vals)/len(cer_vals):.1%}" if cer_vals else "N/A"
        avg_script = f"{sum(script_vals)/len(script_vals):.1%}" if script_vals else "N/A"
        avg_terms = f"{sum(term_vals)/len(term_vals):.1%}" if term_vals else "N/A"
        avg_time = f"{sum(times)/len(times):.2f}s"
        min_time = f"{min(times):.2f}s"
        max_time = f"{max(times):.2f}s"
        lines.append(
            f"| {model} | {avg_cer} | {avg_script} | {avg_terms} | "
            f"{avg_time} | {min_time} | {max_time} |"
        )

    lines += [
        "",
        "## 詳細結果",
        "",
        "| 音檔 | 語言 profile | 模型 | CER | Script | 術語 | 耗時 | 辨識結果 |",
        "|------|-------------|------|-----|--------|------|------|---------|",
    ]

    for r in results:
        cer_str = f"{r['cer']:.1%}" if r["cer"] >= 0 else "N/A"
        script_str = f"{r.get('script_preservation', -1):.1%}" if r.get("script_preservation", -1) >= 0 else "N/A"
        term_str = f"{r.get('protected_term_recall', -1):.1%}" if r.get("protected_term_recall", -1) >= 0 else "N/A"
        time_str = f"{r['time']:.2f}s" if r["time"] > 0 else "ERR"
        text = r["text"][:50] + "..." if len(r["text"]) > 50 else r["text"]
        # 轉義 Markdown 表格中的 pipe
        text = text.replace("|", "\\|")
        lines.append(
            f"| {r['file']} | {r.get('language', 'auto')} | {r['model']} | "
            f"{cer_str} | {script_str} | {term_str} | {time_str} | {text} |"
        )

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
    parser.add_argument(
        "--language",
        choices=LANGUAGE_PROFILES,
        default="auto",
        help="語言 profile：auto 依檔名推導，或將所有音檔固定為 zh/ja/en",
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    run_benchmark(models, language=args.language)


if __name__ == "__main__":
    main()
