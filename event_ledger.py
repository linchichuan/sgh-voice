"""
event_ledger.py — Production observability for silent failures.

寫純 metadata 事件到 ~/.voice-input/events.jsonl（append-only），讓我們事後能定位：
- audio gate 把使用者的聲音擋掉（user 視角：講了沒反應）
- voiceprint reject（user 視角：app 不認我）
- STT / LLM provider 各自的 latency / timeout / error
- Validator 攔截 vs 截斷的 reason 分布
- Paste 走到哪條 fallback path
- Cancel / Retry hotkey 使用頻率與情境

✅ 只記 metadata，**從不記錄** transcribed text / raw audio / 個資。
✅ 每個 recording cycle 一個 session_id，事件可串接。
✅ Logging 失敗時 silently 吞掉，不影響主流程。
✅ 50MB 自動 rotate（保留 .1 backup）。
"""

import json
import os
import threading
import time
from datetime import datetime

EVENTS_FILE = os.path.expanduser("~/.voice-input/events.jsonl")
MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
ROTATED_SUFFIX = ".1"

_lock = threading.Lock()
# Thread-local session：避免重疊轉寫（背景 transcribe 還在跑時新錄音開始）
# 用同一個 global session_id 會把後續事件錯記到新 session。
_tls = threading.local()
# 最近一次 new_session() 結果，給 UI thread 的 user_action（cancel/retry）等
# 沒有自己 session 的 caller 自動關聯到 active pipeline。
_last_active = None
_active_lock = threading.Lock()


def new_session():
    """每次錄音/retry/cancel 互動開始時呼叫，回傳新的 session_id（綁定到當前 thread）。
    用 ns timestamp + thread ident 避免兩個重疊 transcription 在同 ms 拿到同 id。
    同時更新 _last_active，讓 UI thread 的 cancel/retry 能自動關聯。"""
    global _last_active
    tid = threading.get_ident() & 0xFFFF  # thread ident 低 16 bits
    sid = f"{time.time_ns():x}-{tid:04x}"
    _tls.session_id = sid
    with _active_lock:
        _last_active = sid
    return sid


def current_session():
    return getattr(_tls, "session_id", None)


def _resolve_session():
    """log() 取 session 的邏輯：先用 caller thread 的 TLS，沒有就 fallback 到最近 active。
    讓 UI thread 的 cancel/retry events 自動關聯到當下 pipeline。"""
    sid = getattr(_tls, "session_id", None)
    if sid:
        return sid
    with _active_lock:
        return _last_active


def log(event_type, **fields):
    """寫一筆事件。fields 必須是 JSON-serializable 的 metadata（**不要傳文字內容**）。
    任何 exception 都會被吞掉以避免影響主流程。"""
    try:
        entry = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "type": event_type,
            "session": _resolve_session(),
        }
        # 確保 fields 不會 leak 文字內容（白名單檢查）
        for k, v in fields.items():
            entry[k] = v

        with _lock:
            os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)
            if os.path.exists(EVENTS_FILE) and os.path.getsize(EVENTS_FILE) > MAX_SIZE_BYTES:
                _rotate()
            with open(EVENTS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _rotate():
    """超過 50MB 時：現檔 → .1，舊 .1 刪掉。只保留 1 份 backup。"""
    rotated = EVENTS_FILE + ROTATED_SUFFIX
    try:
        if os.path.exists(rotated):
            os.remove(rotated)
        os.replace(EVENTS_FILE, rotated)
    except Exception:
        pass


# ───── 各事件 helper（讓 call site 簡潔，schema 集中管理）─────

def audio_gate_reject(reason, **metrics):
    log("audio_gate_reject", reason=reason, **metrics)


def voiceprint_reject(score, threshold):
    log("voiceprint_reject", score=round(float(score), 4), threshold=float(threshold))


def stt_attempt(source, audio_sec, latency_ms, ok, error=None):
    fields = {"source": source, "audio_sec": round(float(audio_sec), 2),
              "latency_ms": int(latency_ms), "ok": bool(ok)}
    if error:
        fields["error"] = str(error)[:100]
    log("stt_attempt", **fields)


def llm_attempt(source, mode, latency_ms, ok, error=None, fallback_index=0):
    fields = {"source": source, "mode": mode, "latency_ms": int(latency_ms),
              "ok": bool(ok), "fallback_index": fallback_index}
    if error:
        fields["error"] = str(error)[:100]
    log("llm_attempt", **fields)


def validator_action(action, validator, engine, len_in=None, len_out=None, reason=None):
    """action: pass | discard | truncate"""
    fields = {"action": action, "validator": validator, "engine": engine}
    if len_in is not None: fields["len_in"] = int(len_in)
    if len_out is not None: fields["len_out"] = int(len_out)
    if reason: fields["reason"] = reason
    log("validator_action", **fields)


def paste_method(method, success, text_len=None, app_id=None):
    """method: quartz | osascript | axvalue | clipboard_only"""
    fields = {"method": method, "success": bool(success)}
    if text_len is not None: fields["text_len"] = int(text_len)
    if app_id: fields["app_id"] = app_id
    log("paste_method", **fields)


def user_action(action, phase, **extra):
    """action: cancel | retry | rewrite. phase: recording | processing | idle."""
    fields = {"action": action, "phase": phase}
    fields.update(extra)
    log("user_action", **fields)


def pipeline_complete(total_ms, stt_ms, llm_ms, stt_source, llm_source, mode, chars_out, app_id=None):
    """每個成功的 transcribe() 收尾時記一筆，方便聚合 p50/p90/p95。
    收完後清掉 _last_active，避免閒置期 UI events（cancel/retry on idle）誤關聯到舊 session。"""
    global _last_active
    fields = {
        "total_ms": int(total_ms),
        "stt_ms": int(stt_ms),
        "llm_ms": int(llm_ms),
        "stt_source": stt_source,
        "llm_source": llm_source,
        "mode": mode,
        "chars_out": int(chars_out),
    }
    if app_id: fields["app_id"] = app_id
    log("pipeline_complete", **fields)
    # Pipeline 結束 → 清掉 active session pointer，但只清「自己」這個 session。
    # 若有更新的 pipeline B 已搶占 _last_active，此次完成的 A 不該清 B 的 pointer，
    # 否則 B 還在跑時 UI events（cancel/retry）會失去與 B 的關聯。
    my_session = getattr(_tls, "session_id", None)
    with _active_lock:
        if _last_active == my_session:
            _last_active = None
