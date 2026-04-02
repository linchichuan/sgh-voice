#!/usr/bin/env python3
"""
benchmark_openrouter.py — OpenRouter 免費模型延遲與品質基準測試

效能工程師自動化腳本：
- 測試多個 OpenRouter 免費模型的回應延遲
- 用 3 種語言樣本（中/日/英混合短句、純日文、純中文）驗證品質
- 輸出 Markdown 報告到 test/results/OPENROUTER_BENCHMARK.md

用法：
  python3 scripts/benchmark_openrouter.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import load_config

# ─── 測試模型清單 ───

MODELS = [
    # 極速 MoE
    {"id": "qwen/qwen3-30b-a3b:free", "label": "Qwen 3 30B MoE", "category": "極速"},
    {"id": "nvidia/nemotron-3-nano-30b-a3b:free", "label": "Nemotron 3 Nano 30B", "category": "極速"},
    {"id": "stepfun/step-3.5-flash:free", "label": "Step 3.5 Flash", "category": "極速"},
    # 旗艦
    {"id": "qwen/qwen3.6-plus-preview:free", "label": "Qwen 3.6 Plus Preview", "category": "旗艦"},
    {"id": "deepseek/deepseek-chat-v3-0324:free", "label": "DeepSeek V3 0324", "category": "旗艦"},
    {"id": "google/gemini-2.5-flash-preview:free", "label": "Gemini 2.5 Flash", "category": "旗艦"},
]

# ─── 測試樣本（模擬真實語音後處理場景）───

SAMPLES = [
    {
        "id": "mixed_short",
        "label": "中日英混合短句",
        "input": "えーと林さん、那個KusuriJapanのorder確認一下shipping dateは来週の水曜日ですか",
    },
    {
        "id": "ja_business",
        "label": "日文商務",
        "input": "えーとあのですね、来月の東京出張の件で、15日から18日まで、ホテルの予約をお願いしたいんですけど",
    },
    {
        "id": "zh_multipoint",
        "label": "中文多重點",
        "input": "那個就是我整理一下今天會議的重點，第一個是網站更新，第二個是物流安排，第三個是出差日程確認",
    },
]

# ─── 品質快速檢查 ───

FILLER_WORDS = ["えーと", "あの", "那個", "就是", "ですね", "んですけど"]


def quick_quality_check(output, sample_input):
    """快速品質檢查：填充詞是否清除、是否有多餘解釋"""
    issues = []
    for f in FILLER_WORDS:
        if f in output:
            issues.append(f"殘留填充詞「{f}」")
    # 幻覺開頭
    hallucination_starts = ["好的", "沒問題", "了解", "以下是", "承知しました"]
    for h in hallucination_starts:
        if output.startswith(h):
            issues.append(f"幻覺前綴「{h}」")
            break
    # 長度異常
    if len(output) > len(sample_input) * 3:
        issues.append("輸出過長")
    return issues


def call_openrouter(api_key, model_id, system_prompt, user_text):
    """呼叫 OpenRouter API"""
    import openai as openai_lib
    client = openai_lib.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=30.0,
    )
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.3,
        max_tokens=512,
        extra_headers={"HTTP-Referer": "https://shingihou.com", "X-Title": "SGH Voice"},
    )
    latency = time.time() - t0
    raw = (resp.choices[0].message.content or "").strip()
    # 清除 <think> 標籤
    result = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', raw).strip()
    return result, latency


def run_benchmark():
    config = load_config()
    api_key = config.get("openrouter_api_key")
    if not api_key:
        print("❌ 沒有 OpenRouter API Key，請先在 Dashboard 設定")
        sys.exit(1)

    # 取得 system prompt
    from transcriber import Transcriber
    system_prompt = Transcriber._DICTATE_SYSTEM

    print(f"⚡ OpenRouter 免費模型基準測試")
    print(f"   模型數: {len(MODELS)}")
    print(f"   樣本數: {len(SAMPLES)}")
    print(f"   System Prompt: {len(system_prompt)} 字元")
    print("=" * 70)

    results = []  # [{model, category, sample_id, latency, output, issues}]

    for model in MODELS:
        print(f"\n🔧 測試: {model['label']} ({model['id']})")
        model_results = []

        for sample in SAMPLES:
            try:
                output, latency = call_openrouter(api_key, model["id"], system_prompt, sample["input"])
                issues = quick_quality_check(output, sample["input"])
                status = "✅" if not issues else "⚠️"
                print(f"   {status} [{sample['id']}] {latency:.2f}s | {output[:50]}...")

                model_results.append({
                    "model_id": model["id"],
                    "model_label": model["label"],
                    "category": model["category"],
                    "sample_id": sample["id"],
                    "sample_label": sample["label"],
                    "latency": latency,
                    "output": output,
                    "issues": issues,
                    "error": None,
                })
            except Exception as e:
                print(f"   ❌ [{sample['id']}] 錯誤: {e}")
                model_results.append({
                    "model_id": model["id"],
                    "model_label": model["label"],
                    "category": model["category"],
                    "sample_id": sample["id"],
                    "sample_label": sample["label"],
                    "latency": 0,
                    "output": "",
                    "issues": [],
                    "error": str(e)[:150],
                })

            # 避免 rate limit
            time.sleep(1)

        results.extend(model_results)

    generate_report(results, system_prompt)
    return results


def generate_report(results, system_prompt):
    """產生 Markdown 報告"""
    report_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test", "results")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "OPENROUTER_BENCHMARK.md")

    # 統計
    model_stats = {}
    for r in results:
        mid = r["model_id"]
        if mid not in model_stats:
            model_stats[mid] = {"label": r["model_label"], "category": r["category"],
                                "latencies": [], "issues": 0, "errors": 0, "total": 0}
        s = model_stats[mid]
        s["total"] += 1
        if r["error"]:
            s["errors"] += 1
        else:
            s["latencies"].append(r["latency"])
            if r["issues"]:
                s["issues"] += 1

    lines = [
        "# OpenRouter 免費模型基準測試報告",
        "",
        f"- **測試時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **模型數**: {len(model_stats)}",
        f"- **樣本數/模型**: {len(SAMPLES)}",
        f"- **System Prompt**: {len(system_prompt)} 字元",
        "",
        "## 排名（按平均延遲）",
        "",
        "| # | 模型 | 類別 | 平均延遲 | 最快 | 最慢 | 品質問題 | 錯誤 |",
        "|---|------|------|----------|------|------|----------|------|",
    ]

    # 排序
    ranked = []
    for mid, s in model_stats.items():
        avg = sum(s["latencies"]) / len(s["latencies"]) if s["latencies"] else 999
        mn = min(s["latencies"]) if s["latencies"] else 0
        mx = max(s["latencies"]) if s["latencies"] else 0
        ranked.append((mid, s, avg, mn, mx))
    ranked.sort(key=lambda x: x[2])

    for i, (mid, s, avg, mn, mx) in enumerate(ranked):
        medal = "🥇" if i == 0 else ("🥈" if i == 1 else ("🥉" if i == 2 else f"{i+1}"))
        issues_str = f"{s['issues']}/{s['total']}" if s["issues"] else "0"
        errors_str = str(s["errors"]) if s["errors"] else "0"
        lines.append(f"| {medal} | {s['label']} | {s['category']} | {avg:.2f}s | {mn:.2f}s | {mx:.2f}s | {issues_str} | {errors_str} |")

    # 推薦
    if ranked:
        best = ranked[0]
        lines.extend([
            "",
            f"## 推薦",
            "",
            f"**語音後處理最佳選擇**: `{best[0]}`（{best[1]['label']}）",
            f"- 平均延遲 {best[2]:.2f}s，類別：{best[1]['category']}",
            "",
        ])

    # 詳細結果
    lines.extend(["## 詳細結果", ""])

    current_model = None
    for r in results:
        if r["model_id"] != current_model:
            current_model = r["model_id"]
            lines.append(f"### {r['model_label']} (`{r['model_id']}`)")
            lines.append("")

        if r["error"]:
            lines.append(f"- **{r['sample_label']}**: ❌ 錯誤 — {r['error']}")
        else:
            issue_str = f" ⚠️ {', '.join(r['issues'])}" if r["issues"] else ""
            lines.append(f"- **{r['sample_label']}** ({r['latency']:.2f}s){issue_str}")
            lines.append(f"  ```")
            lines.append(f"  {r['output'][:200]}")
            lines.append(f"  ```")
        lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n{'='*70}")
    print(f"📊 報告已產生: {report_path}")
    print(f"\n🏆 排名:")
    for i, (mid, s, avg, mn, mx) in enumerate(ranked):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
        print(f"   {medal} {s['label']}: {avg:.2f}s (品質問題 {s['issues']}/{s['total']})")


if __name__ == "__main__":
    run_benchmark()
