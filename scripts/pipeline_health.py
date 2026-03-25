#!/usr/bin/env python3
"""
pipeline_health.py — 管線自我診斷與優化閉環
每天自動掃描歷史數據，輸出健康報告 + 自動建議優化動作。

5 大分析模組：
  1. 修正規則品質審計（Correction Quality Audit）
  2. Whisper 錯誤模式挖掘（Error Pattern Mining）
  3. LLM 品質監控（LLM Quality Monitor）
  4. Whisper Prompt 最佳化建議（Prompt Optimization）
  5. 處理速度異常偵測（Speed Anomaly Detection）

用法：
    python3 scripts/pipeline_health.py              # 完整報告
    python3 scripts/pipeline_health.py --auto-fix   # 自動修正明確問題
    python3 scripts/pipeline_health.py --module 1   # 只跑指定模組
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# 確保專案 root 在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = Path.home() / ".voice-input"
DICT_FILE = DATA_DIR / "dictionary.json"
HISTORY_FILE = DATA_DIR / "history.json"
STATS_FILE = DATA_DIR / "stats.json"
REPORT_DIR = DATA_DIR / "reports"


# ─── 工具函數 ──────────────────────────────────────────────

def load_json(path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def notify(title, body):
    """macOS 原生通知"""
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


def similarity_ratio(a, b):
    """簡易字元相似度（0~1）"""
    if not a or not b:
        return 0.0
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


# ─── 模組 1: 修正規則品質審計 ─────────────────────────────

def audit_corrections(history, dictionary, auto_fix=False):
    """
    掃描 corrections 規則，找出：
    - 衝突規則（A→B 且 B→C 形成連鎖）
    - 過短/過度通用規則（key ≤ 1 字元）
    - 從未命中的規則（歷史中從未觸發）
    - 反向衝突（A→B 但也有 B→A）
    """
    corrections = dictionary.get("corrections", {})
    issues = []
    auto_fixed = []

    if not corrections:
        return {"status": "ok", "message": "無修正規則", "issues": [], "auto_fixed": []}

    # 合併所有 whisper_raw 文字，用於計算命中率
    all_raw = " ".join(h.get("whisper_raw", "") for h in history)

    # 0. 自我指向規則偵測（key == value，完全無效的規則）
    self_pointing = [k for k, v in corrections.items() if k == v]
    if self_pointing:
        issues.append({
            "type": "self_pointing",
            "severity": "warning",
            "count": len(self_pointing),
            "samples": self_pointing[:10],
            "suggestion": f"{len(self_pointing)} 條規則 key==value（無效），建議刪除",
        })
        if auto_fix:
            for k in self_pointing:
                del corrections[k]
            auto_fixed.append(f"刪除 {len(self_pointing)} 條自我指向規則")

    # 1. 連鎖規則偵測（排除自我指向的）
    for wrong, right in list(corrections.items()):
        if wrong == right:
            continue  # 已在上面處理
        if right in corrections and corrections[right] != right:
            chain_target = corrections[right]
            issues.append({
                "type": "chain",
                "severity": "warning",
                "rule": f"{wrong} → {right} → {chain_target}",
                "suggestion": f"建議合併為 {wrong} → {chain_target}",
            })
            if auto_fix:
                corrections[wrong] = chain_target
                auto_fixed.append(f"合併連鎖：{wrong} → {chain_target}")

    # 2. 反向衝突偵測（排除自我指向的）
    seen_pairs = set()
    for wrong, right in list(corrections.items()):
        if wrong == right:
            continue
        if right in corrections and corrections[right] == wrong:
            pair = tuple(sorted([wrong, right]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                issues.append({
                    "type": "reverse_conflict",
                    "severity": "error",
                    "rule": f"{wrong} ↔ {right}（互相替換）",
                    "suggestion": "需手動決定保留哪個方向",
                })

    # 3. 過短規則（≤1 字元的 key 容易誤傷）
    for wrong, right in corrections.items():
        if len(wrong) <= 1:
            issues.append({
                "type": "too_short",
                "severity": "warning",
                "rule": f"'{wrong}' → '{right}'",
                "suggestion": f"單字元規則容易誤傷，建議刪除或加長前後文",
            })

    # 4. 同音同義規則（wrong 和 right 幾乎一樣）
    for wrong, right in corrections.items():
        if wrong != right and similarity_ratio(wrong, right) > 0.85 and len(wrong) > 3:
            issues.append({
                "type": "near_duplicate",
                "severity": "info",
                "rule": f"'{wrong}' → '{right}'（相似度 {similarity_ratio(wrong, right):.0%}）",
                "suggestion": "可能只是標點/空格差異，考慮是否需要",
            })

    # 5. 從未命中的規則
    never_hit = []
    for wrong in corrections:
        if wrong not in all_raw and len(wrong) > 1:
            never_hit.append(wrong)

    if never_hit:
        issues.append({
            "type": "never_hit",
            "severity": "info",
            "count": len(never_hit),
            "samples": never_hit[:10],
            "suggestion": f"{len(never_hit)} 條規則從未在歷史中命中，可能是模型改善後不再需要",
        })

    # 自動修正：移除反向衝突中的一方（保留更長的 key）
    if auto_fix:
        save_json(DICT_FILE, dictionary)

    return {
        "status": "warning" if any(i["severity"] == "error" for i in issues) else "ok",
        "total_rules": len(corrections),
        "issues": issues,
        "auto_fixed": auto_fixed,
        "never_hit_count": len(never_hit),
    }


# ─── 模組 2: Whisper 錯誤模式挖掘 ─────────────────────────

def mine_error_patterns(history, dictionary):
    """
    分析 whisper_raw → corrected/final_text 的差異，
    找出 Whisper 重複犯的錯誤（尚未被 corrections 覆蓋的）。
    """
    corrections = dictionary.get("corrections", {})
    error_counter = Counter()  # {(wrong, right): count}
    pattern_examples = defaultdict(list)  # {(wrong, right): [timestamps]}

    import difflib

    def tokenize(text):
        return re.findall(r'[a-zA-Z0-9_\'-]+|\s+|[^\sa-zA-Z0-9_\'-]', text)

    for h in history:
        raw = h.get("whisper_raw", "")
        final = h.get("final_text", "")
        ts = h.get("timestamp", "")

        if not raw or not final or raw == final:
            continue

        raw_tokens = tokenize(raw)
        final_tokens = tokenize(final)
        matcher = difflib.SequenceMatcher(None, raw_tokens, final_tokens)

        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "replace":
                wrong = "".join(raw_tokens[i1:i2]).strip()
                right = "".join(final_tokens[j1:j2]).strip()
                if wrong and right and wrong != right and len(wrong) > 1:
                    error_counter[(wrong, right)] += 1
                    if len(pattern_examples[(wrong, right)]) < 3:
                        pattern_examples[(wrong, right)].append(ts)

    # 找出重複 ≥2 次且尚未被 corrections 覆蓋的錯誤
    uncovered = []
    already_covered = []
    for (wrong, right), count in error_counter.most_common(50):
        if count < 2:
            break
        if wrong in corrections:
            already_covered.append({"wrong": wrong, "right": right, "count": count})
        else:
            uncovered.append({
                "wrong": wrong,
                "right": right,
                "count": count,
                "examples": pattern_examples[(wrong, right)],
            })

    # 建議新規則
    suggested_rules = []
    for item in uncovered[:20]:
        # 排除純粹的 LLM 潤飾差異（例如句子重組）
        if len(item["wrong"]) > 20 or len(item["right"]) > 20:
            continue
        # 排除只是標點差異
        if re.sub(r'[，。！？、：；]', '', item["wrong"]) == re.sub(r'[，。！？、：；]', '', item["right"]):
            continue
        suggested_rules.append(item)

    return {
        "total_patterns": len(error_counter),
        "recurring_errors": len([c for c in error_counter.values() if c >= 2]),
        "already_covered": len(already_covered),
        "uncovered": suggested_rules,
        "top_covered": already_covered[:5],
    }


# ─── 模組 3: LLM 品質監控 ──────────────────────────────────

def monitor_llm_quality(history):
    """
    分析 LLM 後處理品質：
    - 幻覺偵測（final 比 raw 長很多）
    - 過度刪減（final 比 raw 短太多）
    - 各 LLM 來源的品質差異
    - 品質趨勢（按日）
    """
    issues = []
    hallucinations = []
    over_trims = []
    source_stats = defaultdict(lambda: {"count": 0, "good": 0, "halluc": 0, "trim": 0, "total_ratio": 0.0})
    daily_quality = defaultdict(lambda: {"count": 0, "issues": 0})

    for h in history:
        raw = h.get("whisper_raw", "")
        final = h.get("final_text", "")
        llm_source = h.get("llm_source", "unknown")
        ts = h.get("timestamp", "")
        day = ts[:10] if ts else ""

        if not raw or not final:
            continue

        ratio = len(final) / max(len(raw), 1)
        source_stats[llm_source]["count"] += 1
        source_stats[llm_source]["total_ratio"] += ratio

        if day:
            daily_quality[day]["count"] += 1

        # 幻覺：final 比 raw 長 50% 以上（排除很短的 raw）
        if ratio > 1.5 and len(raw) > 10:
            hallucinations.append({
                "timestamp": ts,
                "raw_len": len(raw),
                "final_len": len(final),
                "ratio": round(ratio, 2),
                "llm_source": llm_source,
                "raw_preview": raw[:80],
                "final_preview": final[:80],
            })
            source_stats[llm_source]["halluc"] += 1
            if day:
                daily_quality[day]["issues"] += 1

        # 過度刪減：final 不到 raw 的 30%（排除很短的 raw）
        elif ratio < 0.3 and len(raw) > 20:
            over_trims.append({
                "timestamp": ts,
                "raw_len": len(raw),
                "final_len": len(final),
                "ratio": round(ratio, 2),
                "llm_source": llm_source,
                "raw_preview": raw[:80],
                "final_preview": final[:80],
            })
            source_stats[llm_source]["trim"] += 1
            if day:
                daily_quality[day]["issues"] += 1
        else:
            source_stats[llm_source]["good"] += 1

    # 各來源品質比較
    source_comparison = {}
    for source, stats in source_stats.items():
        count = stats["count"]
        if count == 0:
            continue
        source_comparison[source] = {
            "count": count,
            "good_rate": round(stats["good"] / count * 100, 1),
            "halluc_rate": round(stats["halluc"] / count * 100, 1),
            "trim_rate": round(stats["trim"] / count * 100, 1),
            "avg_ratio": round(stats["total_ratio"] / count, 2),
        }

    # 品質趨勢（最近 14 天）
    cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    trend = []
    for day in sorted(daily_quality.keys()):
        if day >= cutoff:
            dq = daily_quality[day]
            trend.append({
                "date": day,
                "count": dq["count"],
                "issues": dq["issues"],
                "issue_rate": round(dq["issues"] / max(dq["count"], 1) * 100, 1),
            })

    return {
        "total_analyzed": len(history),
        "hallucinations": len(hallucinations),
        "over_trims": len(over_trims),
        "hallucination_samples": hallucinations[:5],
        "over_trim_samples": over_trims[:5],
        "source_comparison": source_comparison,
        "trend_14d": trend,
    }


# ─── 模組 4: Whisper Prompt 最佳化 ─────────────────────────

def optimize_whisper_prompt(history, dictionary):
    """
    分析哪些 custom_words 實際出現在辨識結果中，
    找出浪費 prompt 空間的詞彙，建議動態調整優先順序。
    """
    from config import BASE_CUSTOM_WORDS, DEFAULT_CONFIG

    # 收集所有 prompt 候選詞
    auto_added = dictionary.get("auto_added", [])
    manual_added = dictionary.get("manual_added", [])
    config_words = DEFAULT_CONFIG.get("custom_words", [])

    all_candidates = set(BASE_CUSTOM_WORDS + auto_added + manual_added + config_words)

    # 統計每個詞在 whisper_raw + final_text 中的出現次數
    all_text = " ".join(
        h.get("whisper_raw", "") + " " + h.get("final_text", "")
        for h in history
    )

    word_hits = {}
    for word in all_candidates:
        if not word:
            continue
        count = all_text.count(word)
        word_hits[word] = count

    # 分類
    never_used = [w for w, c in word_hits.items() if c == 0]
    rarely_used = [w for w, c in word_hits.items() if 0 < c <= 2]
    frequently_used = sorted(
        [(w, c) for w, c in word_hits.items() if c > 2],
        key=lambda x: -x[1]
    )

    # 推薦 top 20 prompt 詞彙（按出現頻率）
    recommended_top20 = [w for w, _ in frequently_used[:20]]

    # 目前 prompt 會用到的詞彙（按 build_whisper_prompt 邏輯）
    current_prompt_words = list(config_words)[:20]  # 簡化版

    return {
        "total_candidates": len(all_candidates),
        "never_used": never_used,
        "never_used_count": len(never_used),
        "rarely_used": rarely_used[:10],
        "rarely_used_count": len(rarely_used),
        "top_frequent": frequently_used[:20],
        "recommended_top20": recommended_top20,
        "current_prompt_words": current_prompt_words,
    }


# ─── 模組 5: 處理速度異常偵測 ──────────────────────────────

def detect_speed_anomalies(history):
    """
    分析處理時間，找出異常慢的紀錄，
    按模型/來源組合分析平均延遲。
    """
    records = []
    combo_stats = defaultdict(lambda: {"times": [], "durations": []})

    for h in history:
        pt = h.get("process_time", 0)
        ad = h.get("audio_duration", 0)
        stt = h.get("stt_source", "unknown")
        llm = h.get("llm_source", "unknown")
        ts = h.get("timestamp", "")

        if pt <= 0:
            continue

        combo = f"{stt}+{llm}"
        combo_stats[combo]["times"].append(pt)
        combo_stats[combo]["durations"].append(ad)
        records.append({"ts": ts, "process_time": pt, "audio_duration": ad, "combo": combo})

    if not records:
        return {"status": "no_data", "message": "無處理時間紀錄"}

    # 全域統計
    all_times = [r["process_time"] for r in records]
    mean_time = sum(all_times) / len(all_times)
    sorted_times = sorted(all_times)
    p50 = sorted_times[len(sorted_times) // 2]
    p95 = sorted_times[int(len(sorted_times) * 0.95)]

    # 異常偵測：> p95 * 2 或 > 60 秒
    threshold = max(p95 * 2, 60)
    anomalies = [r for r in records if r["process_time"] > threshold]

    # 各組合平均
    combo_summary = {}
    for combo, data in combo_stats.items():
        times = data["times"]
        durations = data["durations"]
        combo_summary[combo] = {
            "count": len(times),
            "avg_process": round(sum(times) / len(times), 2),
            "p50_process": round(sorted(times)[len(times) // 2], 2),
            "avg_audio_duration": round(sum(durations) / max(len(durations), 1), 1),
            "realtime_factor": round(
                sum(times) / max(sum(durations), 0.1), 2
            ),  # 處理時間 / 音訊長度
        }

    # 按日趨勢
    daily_speed = defaultdict(lambda: {"times": []})
    for r in records:
        day = r["ts"][:10]
        if day:
            daily_speed[day]["times"].append(r["process_time"])

    cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    speed_trend = []
    for day in sorted(daily_speed.keys()):
        if day >= cutoff:
            times = daily_speed[day]["times"]
            speed_trend.append({
                "date": day,
                "count": len(times),
                "avg": round(sum(times) / len(times), 2),
                "max": round(max(times), 2),
            })

    return {
        "total_records": len(records),
        "mean": round(mean_time, 2),
        "p50": round(p50, 2),
        "p95": round(p95, 2),
        "anomaly_threshold": round(threshold, 2),
        "anomalies": len(anomalies),
        "anomaly_samples": [
            {"ts": a["ts"], "time": round(a["process_time"], 2), "combo": a["combo"]}
            for a in anomalies[:5]
        ],
        "combo_summary": combo_summary,
        "speed_trend_14d": speed_trend,
    }


# ─── 報告生成 ──────────────────────────────────────────────

def generate_report(results, auto_fix=False, history_count=0):
    """生成 Markdown 報告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 🔬 管線健康報告",
        f"> 生成時間：{now}",
        f"> 自動修正：{'✅ 啟用' if auto_fix else '❌ 停用'}",
        "",
    ]

    # 總覽
    lines.append("## 📊 總覽")
    lines.append("")
    lines.append("| 模組 | 狀態 | 關鍵指標 |")
    lines.append("|------|------|----------|")

    r1 = results.get("corrections", {})
    r2 = results.get("error_patterns", {})
    r3 = results.get("llm_quality", {})
    r4 = results.get("prompt_opt", {})
    r5 = results.get("speed", {})

    issue_count_1 = len(r1.get("issues", []))
    lines.append(f"| 修正規則審計 | {'⚠️' if issue_count_1 > 0 else '✅'} | {r1.get('total_rules', 0)} 條規則，{issue_count_1} 個問題 |")
    lines.append(f"| 錯誤模式挖掘 | {'⚠️' if r2.get('uncovered') else '✅'} | {r2.get('recurring_errors', 0)} 個重複錯誤，{len(r2.get('uncovered', []))} 個未覆蓋 |")
    lines.append(f"| LLM 品質 | {'⚠️' if r3.get('hallucinations', 0) > 3 else '✅'} | 幻覺 {r3.get('hallucinations', 0)}，過度刪減 {r3.get('over_trims', 0)} |")
    lines.append(f"| Prompt 最佳化 | {'⚠️' if r4.get('never_used_count', 0) > 10 else '✅'} | {r4.get('never_used_count', 0)} 個從未使用的詞 |")
    lines.append(f"| 處理速度 | {'⚠️' if r5.get('anomalies', 0) > 3 else '✅'} | P50={r5.get('p50', 0)}s，P95={r5.get('p95', 0)}s，異常 {r5.get('anomalies', 0)} 筆 |")
    lines.append("")

    # 模組 1
    lines.append("---")
    lines.append("## 1️⃣ 修正規則品質審計")
    lines.append("")
    if r1.get("issues"):
        for issue in r1["issues"]:
            icon = "🔴" if issue.get("severity") == "error" else "🟡" if issue.get("severity") == "warning" else "ℹ️"
            lines.append(f"- {icon} **{issue.get('type', '')}**: {issue.get('rule', issue.get('suggestion', ''))}")
            if "suggestion" in issue and "rule" in issue:
                lines.append(f"  - 建議：{issue['suggestion']}")
            if "samples" in issue:
                lines.append(f"  - 範例：{', '.join(issue['samples'][:5])}")
    else:
        lines.append("✅ 所有規則正常")

    if r1.get("auto_fixed"):
        lines.append("")
        lines.append("**自動修正：**")
        for fix in r1["auto_fixed"]:
            lines.append(f"- ✅ {fix}")

    lines.append(f"\n> 從未命中的規則數：{r1.get('never_hit_count', 0)}")
    lines.append("")

    # 模組 2
    lines.append("---")
    lines.append("## 2️⃣ Whisper 錯誤模式挖掘")
    lines.append("")
    if r2.get("uncovered"):
        lines.append("**建議新增的修正規則：**")
        lines.append("")
        lines.append("| 錯誤 | 正確 | 出現次數 |")
        lines.append("|------|------|----------|")
        for item in r2["uncovered"][:15]:
            lines.append(f"| {item['wrong']} | {item['right']} | {item['count']} |")
    else:
        lines.append("✅ 所有重複錯誤已被 corrections 覆蓋")

    if r2.get("top_covered"):
        lines.append("")
        lines.append("**已覆蓋的高頻錯誤（corrections 有效）：**")
        for item in r2["top_covered"]:
            lines.append(f"- ✅ {item['wrong']} → {item['right']}（{item['count']}次）")
    lines.append("")

    # 模組 3
    lines.append("---")
    lines.append("## 3️⃣ LLM 品質監控")
    lines.append("")
    if r3.get("source_comparison"):
        lines.append("**各來源品質比較：**")
        lines.append("")
        lines.append("| 來源 | 筆數 | 正常率 | 幻覺率 | 過刪率 | 平均長度比 |")
        lines.append("|------|------|--------|--------|--------|-----------|")
        for source, stats in r3["source_comparison"].items():
            lines.append(
                f"| {source} | {stats['count']} | {stats['good_rate']}% | "
                f"{stats['halluc_rate']}% | {stats['trim_rate']}% | {stats['avg_ratio']} |"
            )

    if r3.get("hallucination_samples"):
        lines.append("")
        lines.append("**幻覺樣本（final 遠長於 raw）：**")
        for s in r3["hallucination_samples"][:3]:
            lines.append(f"- [{s['timestamp'][:16]}] ratio={s['ratio']} ({s['llm_source']})")
            lines.append(f"  - raw: {s['raw_preview']}")
            lines.append(f"  - final: {s['final_preview']}")

    if r3.get("over_trim_samples"):
        lines.append("")
        lines.append("**過度刪減樣本（final 遠短於 raw）：**")
        for s in r3["over_trim_samples"][:3]:
            lines.append(f"- [{s['timestamp'][:16]}] ratio={s['ratio']} ({s['llm_source']})")
            lines.append(f"  - raw: {s['raw_preview']}")
            lines.append(f"  - final: {s['final_preview']}")

    if r3.get("trend_14d"):
        lines.append("")
        lines.append("**近 14 天品質趨勢：**")
        lines.append("")
        for t in r3["trend_14d"]:
            bar = "█" * t["issues"] + "░" * max(0, 5 - t["issues"])
            lines.append(f"  {t['date']} | {bar} {t['issues']}/{t['count']} ({t['issue_rate']}%)")
    lines.append("")

    # 模組 4
    lines.append("---")
    lines.append("## 4️⃣ Whisper Prompt 最佳化")
    lines.append("")
    if r4.get("top_frequent"):
        lines.append("**最常出現的詞彙（建議優先放入 prompt）：**")
        lines.append("")
        for word, count in r4["top_frequent"][:15]:
            bar = "█" * min(count // 2, 20)
            lines.append(f"  {bar} {word}（{count}次）")

    if r4.get("never_used"):
        lines.append("")
        lines.append(f"**從未出現在辨識結果中的詞彙（{r4['never_used_count']} 個，建議移除）：**")
        for w in r4["never_used"][:15]:
            lines.append(f"  - ❌ {w}")
        if r4["never_used_count"] > 15:
            lines.append(f"  - ...還有 {r4['never_used_count'] - 15} 個")

    if r4.get("recommended_top20"):
        lines.append("")
        lines.append("**建議的 Top 20 Prompt 詞彙：**")
        lines.append(f"```\n{', '.join(r4['recommended_top20'])}\n```")
    lines.append("")

    # 模組 5
    lines.append("---")
    lines.append("## 5️⃣ 處理速度分析")
    lines.append("")
    if r5.get("combo_summary"):
        lines.append("**各模型組合效能：**")
        lines.append("")
        lines.append("| 組合 | 筆數 | 平均(s) | P50(s) | 即時因子 |")
        lines.append("|------|------|---------|--------|----------|")
        for combo, stats in sorted(r5["combo_summary"].items(), key=lambda x: -x[1]["count"]):
            rtf = stats["realtime_factor"]
            rtf_icon = "🟢" if rtf < 0.5 else "🟡" if rtf < 1.0 else "🔴"
            lines.append(
                f"| {combo} | {stats['count']} | {stats['avg_process']} | "
                f"{stats['p50_process']} | {rtf_icon} {rtf}x |"
            )

    if r5.get("anomaly_samples"):
        lines.append("")
        lines.append(f"**速度異常（>{r5.get('anomaly_threshold', 60)}s）：**")
        for a in r5["anomaly_samples"]:
            lines.append(f"- [{a['ts'][:16]}] {a['time']}s ({a['combo']})")

    if r5.get("speed_trend_14d"):
        lines.append("")
        lines.append("**近 14 天速度趨勢：**")
        lines.append("")
        for t in r5["speed_trend_14d"]:
            bar_len = min(int(t["avg"]), 30)
            bar = "█" * bar_len
            lines.append(f"  {t['date']} | {bar} avg={t['avg']}s max={t['max']}s ({t['count']}筆)")
    lines.append("")

    # 行動建議
    lines.append("---")
    lines.append("## 🎯 建議行動")
    lines.append("")
    actions = []

    if r2.get("uncovered"):
        n = len(r2["uncovered"])
        actions.append(f"📝 新增 {n} 條修正規則（模組 2 建議）→ 可用 `--auto-fix` 自動加入")

    if r4.get("never_used_count", 0) > 5:
        actions.append(f"🧹 清理 {r4['never_used_count']} 個從未使用的詞庫詞彙")

    if r3.get("hallucinations", 0) > 5:
        worst_source = max(
            r3.get("source_comparison", {}).items(),
            key=lambda x: x[1].get("halluc_rate", 0),
            default=("", {}),
        )
        if worst_source[0]:
            actions.append(f"🔍 檢視 {worst_source[0]} 的幻覺率（{worst_source[1].get('halluc_rate', 0)}%），考慮調整 LLM prompt 或更換模型")

    if r5.get("anomalies", 0) > 3:
        actions.append(f"⚡ {r5['anomalies']} 筆處理超時，檢查網路或模型載入狀態")

    if issue_count_1 > 0:
        actions.append(f"🔧 修正 {issue_count_1} 個規則問題（模組 1）→ 可用 `--auto-fix` 自動處理連鎖")

    if not actions:
        actions.append("✅ 管線狀態良好，無需額外處理")

    for i, action in enumerate(actions, 1):
        lines.append(f"{i}. {action}")

    lines.append("")
    lines.append("---")
    lines.append(f"*報告由 `pipeline_health.py` 自動生成 | 歷史筆數：{history_count}*")

    return "\n".join(lines)


# ─── Auto-fix: 自動套用建議的修正規則 ──────────────────────

def auto_apply_corrections(error_patterns, dictionary):
    """將模組 2 挖掘出的高頻錯誤自動加入 corrections"""
    uncovered = error_patterns.get("uncovered", [])
    if not uncovered:
        return 0

    corrections = dictionary.setdefault("corrections", {})
    added = 0
    for item in uncovered:
        wrong = item["wrong"]
        right = item["right"]
        count = item["count"]
        # 只自動加入出現 ≥3 次的（更保守）
        if count >= 3 and wrong not in corrections:
            corrections[wrong] = right
            added += 1

    if added:
        save_json(DICT_FILE, dictionary)

    return added


# ─── 主程式 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SGH Voice 管線健康診斷")
    parser.add_argument("--auto-fix", action="store_true", help="自動修正明確問題（連鎖規則、高頻新規則）")
    parser.add_argument("--module", type=int, choices=[1, 2, 3, 4, 5], help="只執行指定模組")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 格式（供其他程式讀取）")
    parser.add_argument("--quiet", action="store_true", help="靜默模式（只在有問題時通知）")
    args = parser.parse_args()

    # 載入資料
    history = load_json(HISTORY_FILE)
    if isinstance(history, dict):
        history = []
    dictionary = load_json(DICT_FILE)

    if not history:
        print("⚠️ 無歷史紀錄，無法進行分析")
        return

    if not args.quiet:
        print(f"🔬 SGH Voice 管線健康診斷")
        print(f"   歷史筆數：{len(history)}")
        print(f"   修正規則：{len(dictionary.get('corrections', {}))}")
        print()

    results = {}

    # 執行各模組
    modules = [args.module] if args.module else [1, 2, 3, 4, 5]

    if 1 in modules:
        if not args.quiet:
            print("[1/5] 修正規則品質審計...")
        results["corrections"] = audit_corrections(history, dictionary, auto_fix=args.auto_fix)

    if 2 in modules:
        if not args.quiet:
            print("[2/5] Whisper 錯誤模式挖掘...")
        results["error_patterns"] = mine_error_patterns(history, dictionary)

    if 3 in modules:
        if not args.quiet:
            print("[3/5] LLM 品質監控...")
        results["llm_quality"] = monitor_llm_quality(history)

    if 4 in modules:
        if not args.quiet:
            print("[4/5] Whisper Prompt 最佳化...")
        results["prompt_opt"] = optimize_whisper_prompt(history, dictionary)

    if 5 in modules:
        if not args.quiet:
            print("[5/5] 處理速度異常偵測...")
        results["speed"] = detect_speed_anomalies(history)

    # Auto-fix: 套用模組 2 建議
    if args.auto_fix and "error_patterns" in results:
        added = auto_apply_corrections(results["error_patterns"], dictionary)
        if added:
            results["auto_fix_new_rules"] = added
            if not args.quiet:
                print(f"\n✅ 自動新增 {added} 條修正規則")

    # 輸出
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        report = generate_report(results, auto_fix=args.auto_fix, history_count=len(history))

        # 儲存報告
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        report_file = REPORT_DIR / f"health_{today}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        # 也保存一份 latest
        latest_file = REPORT_DIR / "health_latest.md"
        with open(latest_file, "w", encoding="utf-8") as f:
            f.write(report)

        if not args.quiet:
            print(f"\n{report}")
            print(f"\n📄 報告已儲存：{report_file}")

    # 通知（有問題時）
    total_issues = (
        len(results.get("corrections", {}).get("issues", []))
        + len(results.get("error_patterns", {}).get("uncovered", []))
        + results.get("llm_quality", {}).get("hallucinations", 0)
        + results.get("speed", {}).get("anomalies", 0)
    )

    if total_issues > 0:
        notify(
            "🔬 SGH Voice 管線診斷",
            f"發現 {total_issues} 個待處理項目，詳見報告"
        )
    elif not args.quiet:
        notify("🔬 SGH Voice 管線診斷", "✅ 管線狀態良好")


if __name__ == "__main__":
    main()
