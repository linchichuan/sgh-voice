"""Tests for event_ledger.py — session lifecycle, TLS fallback, overlapping sessions.
這個檔案曾在 v2.4 連續 round 4-7 反覆出問題（_active_list / TLS 行為），是測試覆蓋的高槓桿區。"""
import threading
import pytest


@pytest.fixture(autouse=True)
def reset_ledger_state(isolated_data_dir):
    """每個 test 前重置 event_ledger 全域狀態。"""
    import event_ledger as el
    # 清掉 TLS + active list（不同 thread 的 TLS 不會互相干擾，但保險起見）
    with el._active_lock:
        el._active_list.clear()
    if hasattr(el._tls, "session_id"):
        delattr(el._tls, "session_id")
    yield
    with el._active_lock:
        el._active_list.clear()
    if hasattr(el._tls, "session_id"):
        delattr(el._tls, "session_id")


def test_new_session_returns_string_id_and_adds_to_active(isolated_data_dir):
    """new_session() 回傳非空 string + 進入 _active_list。"""
    import event_ledger as el
    sid = el.new_session()
    assert isinstance(sid, str) and len(sid) > 0
    with el._active_lock:
        assert sid in el._active_list


def test_end_session_removes_from_active_list(isolated_data_dir):
    """end_session() 從 _active_list 移除（但 TLS 保留，給 paste correlation）。"""
    import event_ledger as el
    sid = el.new_session()
    el.end_session()
    with el._active_lock:
        assert sid not in el._active_list


def test_resolve_session_falls_back_to_active_when_tls_empty(isolated_data_dir):
    """另一 thread 開了 session，UI thread (TLS 無) 呼叫 log → 應 fallback 到最新 active。"""
    import event_ledger as el

    pipeline_sid = []

    def pipeline_thread():
        sid = el.new_session()
        pipeline_sid.append(sid)
        # 不 end，模擬正在跑

    t = threading.Thread(target=pipeline_thread)
    t.start()
    t.join()

    # 此時 main thread (我們在的這個) 沒 TLS session
    # 但 _active_list 還有 pipeline_thread 寫入的 sid
    resolved = el._resolve_session()
    assert resolved == pipeline_sid[0]


def test_overlapping_sessions_end_a_keeps_b_resolvable(isolated_data_dir):
    """A 開 → B 開 → A 結束 → 仍能 resolve 到 B（不被誤清掉）。"""
    import event_ledger as el
    results = {}

    def session_a():
        sid_a = el.new_session()
        results["a"] = sid_a

    def session_b():
        sid_b = el.new_session()
        results["b"] = sid_b
        # 故意不 end B，模擬 B 還在跑

    ta = threading.Thread(target=session_a); ta.start(); ta.join()
    tb = threading.Thread(target=session_b); tb.start(); tb.join()

    # A 透過獨立 thread end（模擬 A pipeline 結束）
    def end_a():
        # 重新讓 TLS 載入 A 的 sid（在新 thread 不行；用直接操作 _active_list 模擬）
        import event_ledger as _el
        with _el._active_lock:
            if results["a"] in _el._active_list:
                _el._active_list.remove(results["a"])

    end_a()

    # 現在 _active_list 應該還有 B
    with el._active_lock:
        assert results["b"] in el._active_list
        assert results["a"] not in el._active_list

    # _resolve_session (從沒有 TLS 的 thread 呼叫) 應該回 B
    resolved = el._resolve_session()
    assert resolved == results["b"]


def test_log_safe_with_no_active_session(isolated_data_dir):
    """完全沒 session 時 log() 仍能寫，session 欄位為 None。不該 raise。"""
    import event_ledger as el
    import json
    el.log("test_event", foo="bar")

    # 讀回 events.jsonl 看內容
    assert el.EVENTS_FILE.endswith("events.jsonl")
    with open(el.EVENTS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) >= 1
    entry = json.loads(lines[-1])
    assert entry["type"] == "test_event"
    assert entry["session"] is None
    assert entry["foo"] == "bar"
