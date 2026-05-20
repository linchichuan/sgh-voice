#!/usr/bin/env python3
"""
event_summary.py — 聚合 events.jsonl 給出 Codex 提的監控指標。

用法：
  python3 scripts/event_summary.py              # 過去 7 天
  python3 scripts/event_summary.py --days 30    # 過去 30 天
  python3 scripts/event_summary.py --tail 1000  # 最後 1000 筆
"""

import json
import os
import sys
import argparse
from collections import defaultdict, Counter
from datetime import datetime, timedelta

EVENTS_FILE = os.path.expanduser("~/.voice-input/events.jsonl")


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="只看過去 N 天（default 7）")
    ap.add_argument("--tail", type=int, default=0, help="只看最後 N 筆（覆蓋 --days）")
    ap.add_argument("--file", default=EVENTS_FILE)
    return ap.parse_args()


def load_events(path, days, tail):
    if not os.path.exists(path):
        print(f"⚠️  事件檔不存在：{path}")
        return []
    cutoff = (datetime.now() - timedelta(days=days)).isoformat() if days else None
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if cutoff and e.get("ts", "") < cutoff:
                continue
            events.append(e)
    if tail and tail > 0:
        events = events[-tail:]
    return events


def percentile(values, p):
    if not values:
        return 0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def fmt_ms(ms):
    return f"{ms / 1000:.2f}s" if ms >= 1000 else f"{int(ms)}ms"


def report(events):
    if not events:
        print("（無事件）")
        return

    print(f"\n📊 事件總數：{len(events)}")
    print(f"📅 時間範圍：{events[0]['ts'][:19]} ~ {events[-1]['ts'][:19]}")

    by_type = Counter(e.get("type") for e in events)
    print("\n=== 事件類型分布 ===")
    for t, n in by_type.most_common():
        print(f"  {n:6d}  {t}")

    # Latency percentiles
    pipelines = [e for e in events if e.get("type") == "pipeline_complete"]
    if pipelines:
        totals = [e["total_ms"] for e in pipelines]
        stts = [e["stt_ms"] for e in pipelines]
        llms = [e["llm_ms"] for e in pipelines]
        print(f"\n=== Latency（{len(pipelines)} 筆 pipeline_complete）===")
        print(f"  total  p50={fmt_ms(percentile(totals,.5)):>8}  p90={fmt_ms(percentile(totals,.9)):>8}  p95={fmt_ms(percentile(totals,.95)):>8}  p99={fmt_ms(percentile(totals,.99)):>8}")
        print(f"  STT    p50={fmt_ms(percentile(stts,.5)):>8}  p90={fmt_ms(percentile(stts,.9)):>8}  p95={fmt_ms(percentile(stts,.95)):>8}  p99={fmt_ms(percentile(stts,.99)):>8}")
        print(f"  LLM    p50={fmt_ms(percentile(llms,.5)):>8}  p90={fmt_ms(percentile(llms,.9)):>8}  p95={fmt_ms(percentile(llms,.95)):>8}  p99={fmt_ms(percentile(llms,.99)):>8}")
        slow = [e for e in pipelines if e["total_ms"] > 5000]
        if slow:
            print(f"\n  ⚠️  >5s 案例：{len(slow)} 筆")
            slow_by_src = Counter((e["stt_source"], e["llm_source"]) for e in slow)
            for (s, l), n in slow_by_src.most_common(5):
                print(f"     {n:3d}× stt={s} / llm={l}")

    # STT attempts
    sttas = [e for e in events if e.get("type") == "stt_attempt"]
    if sttas:
        print(f"\n=== STT Attempts（{len(sttas)} 次嘗試）===")
        by_src = defaultdict(list)
        for e in sttas:
            by_src[e["source"]].append(e)
        for src, lst in sorted(by_src.items(), key=lambda x: -len(x[1])):
            ok = sum(1 for e in lst if e.get("ok"))
            latencies = [e["latency_ms"] for e in lst if e.get("ok")]
            p50 = fmt_ms(percentile(latencies, .5)) if latencies else "—"
            p95 = fmt_ms(percentile(latencies, .95)) if latencies else "—"
            errors = Counter(e.get("error") for e in lst if not e.get("ok") and e.get("error"))
            err_str = " " + " ".join(f"{n}×{err}" for err, n in errors.most_common(3)) if errors else ""
            print(f"  {src:18s} {ok}/{len(lst)} ok  p50={p50:>7}  p95={p95:>7}{err_str}")

    # LLM attempts
    llmas = [e for e in events if e.get("type") == "llm_attempt"]
    if llmas:
        print(f"\n=== LLM Attempts（{len(llmas)} 次嘗試）===")
        by_src = defaultdict(list)
        for e in llmas:
            by_src[e["source"]].append(e)
        for src, lst in sorted(by_src.items(), key=lambda x: -len(x[1])):
            ok = sum(1 for e in lst if e.get("ok"))
            latencies = [e["latency_ms"] for e in lst if e.get("ok")]
            p50 = fmt_ms(percentile(latencies, .5)) if latencies else "—"
            p95 = fmt_ms(percentile(latencies, .95)) if latencies else "—"
            fb_max = max((e.get("fallback_index", 0) for e in lst), default=0)
            print(f"  {src:18s} {ok}/{len(lst)} ok  p50={p50:>7}  p95={p95:>7}  max_fallback_idx={fb_max}")

    # Silent failures
    silent_types = ["audio_gate_reject", "voiceprint_reject", "stt_all_failed", "llm_all_failed_fell_to_regex"]
    silent = {t: [e for e in events if e.get("type") == t] for t in silent_types}
    if any(silent.values()):
        print("\n=== Silent Failures ===")
        for t, lst in silent.items():
            if lst:
                print(f"  {t:30s} {len(lst)} 次")
                if t == "audio_gate_reject":
                    reasons = Counter(e.get("reason", "?") for e in lst)
                    for r, n in reasons.most_common(5):
                        print(f"     {n:3d}× {r}")
                elif t == "voiceprint_reject":
                    scores = [e.get("score", 0) for e in lst]
                    if scores:
                        print(f"     score range: {min(scores):.3f} ~ {max(scores):.3f} (threshold {lst[0].get('threshold')})")

    # Validator actions
    validators = [e for e in events if e.get("type") == "validator_action"]
    if validators:
        print(f"\n=== Validator Actions（{len(validators)} 次）===")
        by_action = Counter(e["action"] for e in validators)
        for action, n in by_action.most_common():
            pct = n / len(validators) * 100
            print(f"  {action:10s} {n:5d}  ({pct:.1f}%)")

    # Paste methods
    pastes = [e for e in events if e.get("type") == "paste_method"]
    if pastes:
        print(f"\n=== Paste Methods（{len(pastes)} 次）===")
        by_method = Counter(e["method"] for e in pastes)
        for m, n in by_method.most_common():
            ok_count = sum(1 for e in pastes if e["method"] == m and e.get("success"))
            print(f"  {m:18s} {n:5d}  ok={ok_count}")

    # User actions
    user_acts = [e for e in events if e.get("type") == "user_action"]
    if user_acts:
        print(f"\n=== User Actions（{len(user_acts)} 次）===")
        by_act = Counter((e["action"], e["phase"]) for e in user_acts)
        for (act, phase), n in by_act.most_common():
            print(f"  {act:8s} during {phase:12s} {n} 次")


if __name__ == "__main__":
    args = parse_args()
    events = load_events(args.file, args.days, args.tail)
    report(events)
