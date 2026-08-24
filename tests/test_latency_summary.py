"""Tests for GET /api/latency_summary (dashboard.py) — pipeline latency baseline.

驗證重點：
1. 空/不存在的 events.jsonl → 空結構，不報 500（新安裝場景）
2. percentile 數字與 scripts/event_summary.py 對同一份假資料算出的結果一致
   （同一條解析路徑：event_summary.load_events() + event_summary.percentile()）
"""
import json
import random

import pytest


def _write_events(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _pipeline_event(ts, total_ms, stt_ms, llm_ms):
    return {
        "ts": ts,
        "type": "pipeline_complete",
        "session": "s1",
        "total_ms": total_ms,
        "stt_ms": stt_ms,
        "llm_ms": llm_ms,
        "stt_source": "groq",
        "llm_source": "claude",
        "mode": "dictate",
        "chars_out": 42,
    }


def _recent_iso(days_ago=0):
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=days_ago, hours=1)).isoformat(timespec="milliseconds")


def test_missing_events_file_returns_empty_structure_not_error(isolated_data_dir):
    import dashboard
    import event_ledger as el

    assert not __import__("os").path.exists(el.EVENTS_FILE)
    client = dashboard.app.test_client()
    res = client.get("/api/latency_summary")
    assert res.status_code == 200
    body = res.get_json()
    for window in ("7d", "30d"):
        assert body[window]["sample_count"] == 0
        assert body[window]["pipeline_p50_ms"] == 0
        assert body[window]["stt_avg_ms"] == 0
        assert body[window]["llm_avg_ms"] == 0


def test_empty_events_file_returns_empty_structure_not_error(isolated_data_dir):
    import dashboard
    import event_ledger as el
    from pathlib import Path

    Path(el.EVENTS_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(el.EVENTS_FILE).write_text("", encoding="utf-8")

    client = dashboard.app.test_client()
    res = client.get("/api/latency_summary")
    assert res.status_code == 200
    body = res.get_json()
    assert body["7d"]["sample_count"] == 0
    assert body["30d"]["sample_count"] == 0


def test_percentiles_match_event_summary_reference_calculation(isolated_data_dir):
    """endpoint 的 p50/p90/p95/p99 與 scripts/event_summary.py 對同一份假資料算出的
    結果一致（同一個 percentile() 函式、同一條 load_events() 解析路徑）。"""
    import dashboard
    import event_ledger as el
    from scripts import event_summary
    from pathlib import Path

    random.seed(42)
    events = []
    totals, stts, llms = [], [], []
    for i in range(50):
        total_ms = random.randint(300, 6000)
        stt_ms = random.randint(100, total_ms // 2)
        llm_ms = total_ms - stt_ms
        events.append(_pipeline_event(_recent_iso(days_ago=1), total_ms, stt_ms, llm_ms))
        totals.append(total_ms)
        stts.append(stt_ms)
        llms.append(llm_ms)
    # A couple of noise events of other types (should be ignored).
    events.append({"ts": _recent_iso(1), "type": "stt_attempt", "source": "groq",
                    "audio_sec": 3.0, "latency_ms": 900, "ok": True})
    events.append({"ts": _recent_iso(1), "type": "user_action", "action": "cancel", "phase": "recording"})

    Path(el.EVENTS_FILE).parent.mkdir(parents=True, exist_ok=True)
    _write_events(Path(el.EVENTS_FILE), events)

    # Reference calculation, straight from the read-only script — same functions
    # the endpoint is required to reuse (not a rewritten third copy).
    expected_p50 = round(event_summary.percentile(totals, 0.5), 1)
    expected_p90 = round(event_summary.percentile(totals, 0.9), 1)
    expected_p95 = round(event_summary.percentile(totals, 0.95), 1)
    expected_p99 = round(event_summary.percentile(totals, 0.99), 1)
    expected_stt_avg = round(sum(stts) / len(stts), 1)
    expected_llm_avg = round(sum(llms) / len(llms), 1)

    client = dashboard.app.test_client()
    res = client.get("/api/latency_summary")
    assert res.status_code == 200
    body = res.get_json()
    w = body["7d"]

    assert w["sample_count"] == 50
    assert w["pipeline_p50_ms"] == expected_p50
    assert w["pipeline_p90_ms"] == expected_p90
    assert w["pipeline_p95_ms"] == expected_p95
    assert w["pipeline_p99_ms"] == expected_p99
    assert w["stt_avg_ms"] == expected_stt_avg
    assert w["llm_avg_ms"] == expected_llm_avg


def test_7d_and_30d_windows_filter_by_age_independently(isolated_data_dir):
    import dashboard
    import event_ledger as el
    from pathlib import Path

    events = [
        _pipeline_event(_recent_iso(days_ago=2), 1000, 400, 600),   # in both windows
        _pipeline_event(_recent_iso(days_ago=20), 2000, 800, 1200),  # only in 30d
        _pipeline_event(_recent_iso(days_ago=40), 9000, 4000, 5000),  # in neither
    ]
    Path(el.EVENTS_FILE).parent.mkdir(parents=True, exist_ok=True)
    _write_events(Path(el.EVENTS_FILE), events)

    client = dashboard.app.test_client()
    body = client.get("/api/latency_summary").get_json()

    assert body["7d"]["sample_count"] == 1
    assert body["30d"]["sample_count"] == 2


def test_response_shape_has_both_windows_and_required_fields(isolated_data_dir):
    import dashboard

    client = dashboard.app.test_client()
    body = client.get("/api/latency_summary").get_json()
    for window in ("7d", "30d"):
        for key in (
            "sample_count", "pipeline_p50_ms", "pipeline_p90_ms",
            "pipeline_p95_ms", "pipeline_p99_ms", "stt_avg_ms", "llm_avg_ms",
        ):
            assert key in body[window], f"missing {key} in {window}"
