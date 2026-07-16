"""
dashboard.py — Web Dashboard (Flask)
模仿 Typeless 的本地 Dashboard UI
"""
import os
import sys
import json
from flask import Flask, request, jsonify, send_from_directory, Response
from config import ConfigSaveError, load_config, save_config, load_stats, update_stats, load_smart_replace, save_smart_replace, DEFAULT_APP_STYLES, BASE_CORRECTIONS as BASE_CORRECTIONS_REF, KEYCHAIN_KEYS, _keychain_available, _keychain_delete
from memory import Memory
from multilingual import (
    convert_traditional_preserving_japanese,
    resolve_output_language_hint,
)
from hotkey_config import (
    HOTKEY_FIELDS,
    HotkeyValidationError,
    validate_hotkey_config,
    validate_hotkey_mode,
)
import anthropic


def _get_static_folder():
    """frozen .app bundle 模式下從 bundle 內取得 static 路徑"""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "static")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


app = Flask(__name__, static_folder=_get_static_folder())
memory = Memory()


def set_memory(shared_memory):
    """讓 app.py 傳入共享的 memory 實例，與 VoiceEngine 同步"""
    global memory
    memory = shared_memory


# ─── v2.4.0 安全：CSRF + Origin 保護 ─────────────────────────────
# Dashboard 跑在 localhost:7865，原本所有 mutating endpoint 沒任何保護。
# 威脅模型：使用者瀏覽惡意網站 → 該網站 fetch('http://127.0.0.1:7865/api/...', {method:'POST'}) →
#   可以觸發改設定 / 刪歷史 / 啟動錄音 等動作。
# 防護方式：對所有非 GET 請求檢查 Origin header 必須來自本機 Dashboard 原點。
_ALLOWED_ORIGINS = {
    "http://127.0.0.1:7865", "http://localhost:7865",
    "http://127.0.0.1:7860", "http://localhost:7860",  # 萬一改 port
}

@app.before_request
def _enforce_same_origin():
    """v2.4.0 同源強制。Codex review round 1 修正：
    原本「origin truthy 才 block」會讓「無 Origin + 惡意 Referer」靜默放行。
    新邏輯：明確區分三種情境並分別判定。"""
    # GET / HEAD / OPTIONS 不檢查（讀取 / preflight 不會改狀態）
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    origin = request.headers.get("Origin", "")
    referer = request.headers.get("Referer", "")
    # 三種情境：
    # A. 兩者皆空 → 本機 curl / Python requests / 同 process / Electron — 不擋
    # B. 至少有一個有值 → 必須白名單通過才放行
    if not origin and not referer:
        return None
    origin_ok = origin in _ALLOWED_ORIGINS if origin else True  # 若 origin 為空，不用 origin 判定
    referer_ok = any(referer.startswith(o + "/") for o in _ALLOWED_ORIGINS) if referer else True
    # 兩個 header 都必須通過（任一不通過就拒絕）
    if not (origin_ok and referer_ok):
        # referer host 解析防禦：畸形值（如 "evil.com/x"）不能讓 403 變 500
        try:
            referer_host = referer.split("/")[2] if referer.startswith(("http://", "https://")) else ""
        except IndexError:
            referer_host = ""
        return jsonify({"error": "cross-origin request blocked",
                        "origin": origin, "referer_host": referer_host}), 403
    return None


@app.after_request
def _security_headers(response):
    """v2.4.0：baseline security headers。Codex round 1 修正 CSP：必須允許
    Tailwind CDN + Lucide CDN，否則新 SPA 在瀏覽器完全壞掉。"""
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # CSP：明確允許 Tailwind CDN（cdn.tailwindcss.com）+ Lucide CDN（unpkg.com）
    # + Google Fonts（fonts.googleapis.com / fonts.gstatic.com）
    # 'unsafe-inline' for script 用於 Tailwind config 與 lucide.createIcons 呼叫；style 用於 Tailwind runtime
    # 下版（v2.5.0）改用 SRI hash + 自 host CDN bundle 收緊
    response.headers.setdefault("Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'")
    return response


@app.route("/")
def index():
    return send_from_directory(_get_static_folder(), "index.html")


@app.route("/css/<path:filename>")
def static_css(filename):
    return send_from_directory(os.path.join(_get_static_folder(), "css"), filename)


@app.route("/js/<path:filename>")
def static_js(filename):
    return send_from_directory(os.path.join(_get_static_folder(), "js"), filename)


@app.route("/assets/<path:filename>")
def static_assets(filename):
    return send_from_directory(os.path.join(_get_static_folder(), "assets"), filename)


@app.route("/api/stats")
def api_stats():
    stats = load_stats()
    config = load_config()
    personalization = memory.get_personalization_score()
    return jsonify({
        "stats": stats,
        "personalization": personalization,
        "typing_speed_cpm": config.get("typing_speed_cpm", 50),
    })


import secrets, time as _time
# v2.4.0：wipe nonce 機制（Codex round 1 修正：原本 client-side 固定字串可被 JS 攻擊者直接 bypass）
_WIPE_TOKEN_STORE = {}  # token → expiry_unix_ts


@app.route("/api/wipe_all/token", methods=["POST"])
def api_wipe_token():
    """產生一次性 wipe 確認 token。Client 必須在使用者 UI 互動（typed DELETE）後才能取得，
    然後在 5 分鐘內 POST 到 /api/wipe_all 完成刪除。Token 用過即廢、過期自動丟。"""
    token = secrets.token_urlsafe(32)
    _WIPE_TOKEN_STORE[token] = _time.time() + 300  # 5 分鐘有效
    # 同時清理過期 token（amortized）
    now = _time.time()
    for t in list(_WIPE_TOKEN_STORE.keys()):
        if _WIPE_TOKEN_STORE[t] < now:
            del _WIPE_TOKEN_STORE[t]
    return jsonify({"token": token, "expires_in": 300})


@app.route("/api/wipe_all", methods=["POST"])
def api_wipe_all():
    """v2.4.0：右消去 / GDPR Art. 17 / 一鍵刪除所有本機資料。
    需要 client 先 POST /api/wipe_all/token 拿 nonce、再帶 nonce 來這支才執行。
    被刪除：history.json / events.jsonl / dictionary.json / voiceprint.npy /
            audio_backup/ / stats.json / audit.log / smart_replace.json"""
    body = request.get_json(silent=True) or {}
    token = body.get("token", "")
    confirm = body.get("confirm", "")
    # 雙重守門：必須帶 token + confirm phrase
    if confirm != "DELETE_ALL_MY_DATA":
        return jsonify({"error": "missing confirm phrase",
                        "hint": "POST {token, confirm: 'DELETE_ALL_MY_DATA'}"}), 400
    if not token or token not in _WIPE_TOKEN_STORE:
        return jsonify({"error": "invalid or expired wipe token",
                        "hint": "POST /api/wipe_all/token first"}), 400
    if _WIPE_TOKEN_STORE[token] < _time.time():
        del _WIPE_TOKEN_STORE[token]
        return jsonify({"error": "wipe token expired", "hint": "request new token"}), 400
    # Token 用過即廢
    del _WIPE_TOKEN_STORE[token]

    import shutil, glob
    data_dir = os.path.expanduser("~/.voice-input")
    targets = [
        ("history.json", "file"),
        ("events.jsonl", "file"),
        ("events.jsonl.1", "file"),
        ("dictionary.json", "file"),
        ("voiceprint.npy", "file"),
        ("stats.json", "file"),
        ("smart_replace.json", "file"),
        ("audit.log", "file"),                # Codex round 1 補：之前漏掉，audit log 也是 PII
        ("audio_backup", "dir"),
    ]
    deleted = []
    failed = []
    for name, kind in targets:
        path = os.path.join(data_dir, name)
        if not os.path.exists(path):
            continue
        try:
            if kind == "file":
                os.remove(path)
            else:
                shutil.rmtree(path)
            deleted.append(name)
        except Exception as e:
            failed.append({"name": name, "error": str(e)[:120]})

    # 同步從外接 SSD 備份目錄清掉（如果 config 有指定）
    cfg = load_config()
    ssd_dir = cfg.get("backup_audio_dir", "")
    if ssd_dir and os.path.isdir(ssd_dir):
        wav_files = glob.glob(os.path.join(ssd_dir, "*.wav"))
        for f in wav_files:
            try: os.remove(f); deleted.append(f"backup_audio_dir/{os.path.basename(f)}")
            except Exception as e: failed.append({"name": f, "error": str(e)[:120]})

    # ⚠️ Codex round 1：清 in-memory state — 不清的話 process 內 Memory 物件還持有
    # 已刪資料，下次 add_to_history / save 又會把資料寫回磁碟，GDPR 沒落地。
    try:
        if hasattr(memory, "clear_all_in_memory"):
            memory.clear_all_in_memory()
        else:
            # Fallback：直接重置 memory 物件
            from memory import Memory
            globals()["memory"] = Memory()
            if _engine and hasattr(_engine, "memory"):
                _engine.memory = globals()["memory"]
    except Exception as e:
        failed.append({"name": "in_memory_state", "error": str(e)[:120]})

    return jsonify({"deleted": deleted, "failed": failed,
                    "note": "API キーは Keychain / config.json 內、需要時請從設定頁手動清除（或用 /api/keychain/delete/<key>）。"})


def _resolve_ui_language(ui_lang):
    """auto → 從 macOS 系統語言判斷，預設日文"""
    if ui_lang and ui_lang != "auto":
        return ui_lang
    try:
        import subprocess
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleLanguages"],
            capture_output=True, text=True, timeout=2
        )
        out = result.stdout.lower()
        if "zh-hant" in out or "zh_tw" in out or "zh-tw" in out:
            return "zh-TW"
        if "en" in out and "ja" not in out:
            return "en"
    except Exception:
        pass
    return "ja"  # 預設日文（目標市場：日本醫療機構）


@app.route("/api/config", methods=["GET"])
def api_get_config():
    config = load_config()
    # 隱藏 API key 的中間部分
    safe = config.copy()
    safe["app_styles"] = config.get("app_styles", DEFAULT_APP_STYLES)
    for key in ["openai_api_key", "anthropic_api_key", "elevenlabs_api_key", "groq_api_key", "openrouter_api_key"]:
        v = safe.get(key, "")
        if len(v) > 12:
            safe[key] = v[:6] + "..." + v[-4:]
    # 解析 ui_language auto
    safe["ui_language"] = _resolve_ui_language(safe.get("ui_language", "auto"))
    return jsonify(safe)


_API_KEY_FORMATS = {
    "openai_api_key":      ("sk-",    10),
    "anthropic_api_key":   ("sk-ant-", 10),
    "groq_api_key":        ("gsk_",   10),
    "openrouter_api_key":  ("sk-or-", 10),
    "elevenlabs_api_key":  ("sk_",    10),
}


@app.route("/api/config", methods=["POST"])
def api_save_config():
    config = load_config()
    data = request.json
    if not isinstance(data, dict):
        return jsonify({"error": "invalid data"}), 400
    # 只接受 DEFAULT_CONFIG 中已定義的欄位（防止注入未知欄位）
    from config import DEFAULT_CONFIG
    allowed_keys = set(DEFAULT_CONFIG.keys())
    data = {k: v for k, v in data.items() if k in allowed_keys}
    # 只更新非空的 API key（避免覆蓋隱藏的 key）
    warnings = []
    for key in list(_API_KEY_FORMATS.keys()):
        val = data.get(key, "")
        if not val or "..." in str(val):
            data.pop(key, None)  # 不更新被遮蔽或空的 key
            continue
        prefix, min_len = _API_KEY_FORMATS[key]
        if not str(val).startswith(prefix) or len(val) < min_len:
            warnings.append(f"{key} 格式可能有誤（應以 {prefix} 開頭）")

    # Hotkey 由 Dashboard 與所有 runtime listener 共用同一套 parser。
    # 未知 token、系統保留鍵、重複或 prefix collision 一律拒絕；不可像舊版
    # 一樣默默忽略部分 token，最後 fallback 回正好與 Codex 衝突的 right_cmd。
    changed_hotkey_fields = set(data).intersection(HOTKEY_FIELDS)
    hotkey_behavior_changed = bool(changed_hotkey_fields) or "hotkey_mode" in data
    if "hotkey_mode" in data:
        try:
            data["hotkey_mode"] = validate_hotkey_mode(data["hotkey_mode"])
        except HotkeyValidationError as exc:
            return jsonify({
                "error": str(exc),
                "field": exc.field,
                "code": "invalid_hotkey_mode",
            }), 400
    if changed_hotkey_fields:
        candidate = {**config, **data}
        try:
            normalized_hotkeys = validate_hotkey_config(
                candidate,
                allow_legacy_recording=(
                    config.get("hotkey")
                    if "hotkey" not in changed_hotkey_fields
                    else None
                ),
            )
        except HotkeyValidationError as exc:
            return jsonify({
                "error": str(exc),
                "field": exc.field,
                "code": "invalid_hotkey",
            }), 400
        for field in changed_hotkey_fields:
            data[field] = normalized_hotkeys[field]
        if normalized_hotkeys["hotkey"] == "right_cmd":
            warnings.append(
                "right_cmd may conflict with Codex voice input; "
                "right_option+right_shift is recommended"
            )

    config.update(data)
    try:
        save_config(config)
    except ConfigSaveError as exc:
        return jsonify({
            "error": str(exc),
            "code": "config_save_failed",
        }), 503
    # 即時重新載入設定到引擎（免重啟）
    hotkeys_applied = False
    if _engine and hasattr(_engine, 'reload_config'):
        _engine.reload_config()
        hotkeys_applied = hotkey_behavior_changed
    return jsonify({
        "ok": True,
        "warnings": warnings,
        "hotkeys_applied": hotkeys_applied,
    })


@app.route("/api/history")
def api_history():
    search = request.args.get("search", "")
    n = int(request.args.get("n", 100))
    items = memory.get_history(n=n, search=search if search else None)
    return jsonify(items)


@app.route("/api/history/<path:timestamp>", methods=["PATCH"])
def api_update_history(timestamp):
    """更新歷史紀錄的 final_text，並自動學習修正規則"""
    data = request.json
    new_text = data.get("final_text", "")
    old_text = memory.update_history_item(timestamp, new_text)
    if old_text is None:
        return jsonify({"error": "not found"}), 404

    # 自動學習：比對修改前後的差異
    learned = []
    if old_text != new_text:
        learned = memory.learn_correction(old_text, new_text, source="manual")

    return jsonify({"ok": True, "learned": learned})


@app.route("/api/history/<timestamp>", methods=["DELETE"])
def api_delete_history(timestamp):
    memory.delete_history_item(timestamp)
    return jsonify({"ok": True})


@app.route("/api/history/clear", methods=["POST"])
def api_clear_history():
    memory.clear_history()
    return jsonify({"ok": True})


@app.route("/api/dictionary")
def api_dictionary():
    """支援 ?layer=global|scene:medical|app:com.apple.mail 切換檢視。
    預設回傳 global + 所有層級摘要。"""
    layer = request.args.get("layer", "global")
    if layer.startswith("scene:"):
        scene_key = layer.split(":", 1)[1]
        return jsonify({
            "layer": layer,
            "corrections": memory.get_scene_corrections(scene_key),
            "custom_words": memory.get_dictionary_words(),
            "style_profile": memory.get_style_profile(),
        })
    if layer.startswith("app:"):
        app_id = layer.split(":", 1)[1]
        return jsonify({
            "layer": layer,
            "corrections": memory.get_app_corrections(app_id),
            "custom_words": memory.get_dictionary_words(),
            "style_profile": memory.get_style_profile(),
        })
    # default: global
    return jsonify({
        "layer": "global",
        "corrections": memory.get_all_corrections(),
        "custom_words": memory.get_dictionary_words(),
        "style_profile": memory.get_style_profile(),
        "scene_keys": list(memory.get_scene_corrections().keys()),
        "app_ids": list(memory.get_app_corrections().keys()),
    })


@app.route("/api/dictionary/scene_correction", methods=["POST", "DELETE"])
def api_scene_correction():
    """手動管理場景級 corrections。⚠️ 不開放給自動學習路徑。"""
    body = request.get_json(force=True, silent=True) or {}
    scene = body.get("scene", "").strip()
    wrong = body.get("wrong", "").strip()
    if not scene or not wrong:
        return jsonify({"ok": False, "error": "scene 與 wrong 必填"}), 400
    if request.method == "DELETE":
        ok = memory.remove_scene_correction(scene, wrong)
        return jsonify({"ok": ok})
    right = body.get("right", "").strip()
    if not right:
        return jsonify({"ok": False, "error": "right 必填"}), 400
    ok = memory.add_scene_correction(scene, wrong, right)
    return jsonify({"ok": ok, "rejected_by_filter": not ok})


@app.route("/api/dictionary/app_correction", methods=["POST", "DELETE"])
def api_app_correction():
    body = request.get_json(force=True, silent=True) or {}
    app_id = body.get("app_id", "").strip()
    wrong = body.get("wrong", "").strip()
    if not app_id or not wrong:
        return jsonify({"ok": False, "error": "app_id 與 wrong 必填"}), 400
    if request.method == "DELETE":
        ok = memory.remove_app_correction(app_id, wrong)
        return jsonify({"ok": ok})
    right = body.get("right", "").strip()
    if not right:
        return jsonify({"ok": False, "error": "right 必填"}), 400
    ok = memory.add_app_correction(app_id, wrong, right)
    return jsonify({"ok": ok, "rejected_by_filter": not ok})


@app.route("/api/dictionary/word", methods=["POST"])
def api_add_word():
    word = request.json.get("word", "").strip()
    if word:
        memory.add_custom_word(word)
    return jsonify({"ok": True})


@app.route("/api/dictionary/word", methods=["DELETE"])
def api_remove_word():
    word = request.json.get("word", "").strip()
    if word:
        memory.remove_custom_word(word)
    return jsonify({"ok": True})


@app.route("/api/dictionary/correction", methods=["POST"])
def api_add_correction():
    """新增 correction 規則。所有 UI 路徑都過守門員，防止亂加標點/單字偽規則。"""
    wrong = request.json.get("wrong", "").strip()
    right = request.json.get("right", "").strip()
    if not wrong or not right:
        return jsonify({"ok": False, "error": "wrong 和 right 必填"}), 400
    ok = memory.add_correction(wrong, right)
    if not ok:
        return jsonify({
            "ok": False,
            "rejected": True,
            "error": "被守門員拒絕：可能是純標點對應、單字↔多字、長度差異過大或跨語意 paraphrase。",
        }), 400
    return jsonify({"ok": True})


@app.route("/api/dictionary/correction", methods=["DELETE"])
def api_remove_correction():
    # 不做 strip，避免 key 含合法前後空白時找不到
    wrong = request.json.get("wrong", "")
    if wrong:
        memory.remove_correction(wrong)
    return jsonify({"ok": True})


@app.route("/api/dictionary/cleanup", methods=["POST"])
def api_cleanup_corrections():
    """清理 dictionary 中不符合品質規則的修正規則（標點對應、含換行、跨語意 paraphrase 等）。"""
    removed = memory.cleanup_bad_corrections()
    return jsonify({"ok": True, "removed_count": len(removed), "removed": removed})


@app.route("/api/style_profile/regenerate", methods=["POST"])
def api_regenerate_style_profile():
    """從最近 N 筆 history.final_text 重新生成使用者語氣 profile，寫入 dictionary.style_profile。
    ⚠️ 不影響 dictionary corrections — 只更新 style_profile 文字欄位。
    body: {n?: int=100, apply?: bool=true}（預設直接套用因為純文字、不會污染管線）"""
    body = request.get_json(force=True, silent=True) or {}
    n = int(body.get("n", 100))
    do_apply = body.get("apply", True)

    samples = []
    for h in reversed(memory.history):
        text = (h.get("final_text") or "").strip()
        if len(text) < 15:
            continue
        samples.append(text)
        if len(samples) >= n:
            break
    if len(samples) < 10:
        return jsonify({"ok": False, "error": f"樣本不足（{len(samples)} 筆，需 ≥10）"}), 400

    # 重用腳本邏輯：呼叫 LLM 分析
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_style_profile",
        os.path.join(os.path.dirname(__file__), "scripts", "update_style_profile.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cfg = load_config()
    sample_text = "\n".join(f"- {s}" for s in samples)
    profile, engine = mod._call_llm(cfg, mod._PROFILE_PROMPT, sample_text)
    if not profile:
        return jsonify({"ok": False, "error": "LLM 全部失敗（檢查 API key）"}), 500

    profile = profile.strip().strip('"').strip("'")
    old_profile = memory.get_style_profile()
    if do_apply:
        memory.update_style_profile(profile)
    return jsonify({
        "ok": True,
        "applied": bool(do_apply),
        "engine": engine,
        "samples": len(samples),
        "old_profile": old_profile,
        "new_profile": profile,
    })


@app.route("/api/dictionary/promote_from_history", methods=["POST"])
def api_promote_from_history():
    """從歷史 raw→final 高頻差異中升級 dictionary 規則。
    body: {min_freq?: int=5, source?: "auto"|"edited"|"both"=both, apply?: bool=false}
    回傳：{promoted: [{wrong, right, freq}], skipped: {...}}（apply=False 為預覽）"""
    from collections import Counter
    import difflib, re
    body = request.get_json(force=True, silent=True) or {}
    min_freq = int(body.get("min_freq", 5))
    source = body.get("source", "both")
    do_apply = bool(body.get("apply", False))

    try:
        from opencc import OpenCC
        opencc_inst = OpenCC("s2twp")
    except Exception:
        opencc_inst = None

    def _tokenize(t):
        return re.findall(r"[a-zA-Z0-9_'-]+|\s+|[^\sa-zA-Z0-9_'-]", t or "")

    def _is_substring_relation(a, b):
        return bool(a) and bool(b) and a != b and (a in b or b in a)

    def _opencc_handled(w, r):
        if not opencc_inst:
            return False
        try:
            return opencc_inst.convert(w) == r
        except Exception:
            return False

    counter = Counter()
    for h in memory.history:
        if source == "edited" and not h.get("edited"):
            continue
        if source == "auto" and h.get("edited"):
            continue
        raw = (h.get("whisper_raw") or "").strip()
        fin = (h.get("final_text") or "").strip()
        if not raw or not fin or raw == fin:
            continue
        a, b = _tokenize(raw), _tokenize(fin)
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
            if op != "replace":
                continue
            w = "".join(a[i1:i2]).strip()
            r = "".join(b[j1:j2]).strip()
            if w and r and w != r:
                counter[(w, r)] += 1

    base_keys = {k.lower() for k in BASE_CORRECTIONS_REF.keys()}
    existing = set(memory.dictionary.get("corrections", {}).keys())
    promoted, sk_substr, sk_opencc, sk_filter, sk_base = [], [], [], [], []
    for (w, r), f in counter.most_common():
        if f < min_freq:
            break
        if w.lower() in base_keys or w in existing:
            sk_base.append({"wrong": w, "right": r, "freq": f}); continue
        if _is_substring_relation(w, r):
            sk_substr.append({"wrong": w, "right": r, "freq": f}); continue
        if _opencc_handled(w, r):
            sk_opencc.append({"wrong": w, "right": r, "freq": f}); continue
        if not memory._is_meaningful_correction(w, r, source="auto-promote"):
            sk_filter.append({"wrong": w, "right": r, "freq": f}); continue
        promoted.append({"wrong": w, "right": r, "freq": f})

    if do_apply and promoted:
        corr = memory.dictionary.setdefault("corrections", {})
        freq_d = memory.dictionary.setdefault("frequency", {})
        for p in promoted:
            corr[p["wrong"]] = p["right"]
            freq_d[p["wrong"]] = freq_d.get(p["wrong"], 0) + p["freq"]
        from config import save_dictionary
        save_dictionary(memory.dictionary)

    return jsonify({
        "ok": True,
        "applied": do_apply,
        "min_freq": min_freq,
        "source": source,
        "edited_count": sum(1 for h in memory.history if h.get("edited")),
        "promoted": promoted,
        "skipped": {
            "existing": sk_base[:30],
            "substring_relation": sk_substr[:30],
            "opencc_handled": sk_opencc[:30],
            "filter_rejected": sk_filter[:30],
        },
        "skipped_counts": {
            "existing": len(sk_base),
            "substring_relation": len(sk_substr),
            "opencc_handled": len(sk_opencc),
            "filter_rejected": len(sk_filter),
        },
    })


@app.route("/api/rewrite", methods=["POST"])
def api_rewrite():
    """改寫 API：將文字以指定風格改寫"""
    data = request.json
    text = data.get("text", "").strip()
    style = data.get("style", "concise")  # concise, formal, translate
    if not text:
        return jsonify({"error": "no text"}), 400

    config = load_config()
    api_key = config.get("anthropic_api_key", "")
    if not api_key:
        return jsonify({"error": "no API key"}), 400

    # v2.5.0：風格 prompt 統一收斂到 config.REWRITE_STYLE_DIRECTIVES（與
    # transcriber._STYLE_DIRECTIVES / Quick-Rewrite 同源），並補上原本獨缺的
    # system prompt（含 <command>/<text> injection 防護 + 繁中規則）與 OpenCC 終層。
    from config import REWRITE_STYLE_DIRECTIVES, EDIT_SYSTEM_PROMPT
    directive = REWRITE_STYLE_DIRECTIVES.get(style, REWRITE_STYLE_DIRECTIVES["concise"])

    try:
        client = anthropic.Anthropic(api_key=api_key, max_retries=0)
        resp = client.messages.create(
            model=config.get("claude_model", "claude-haiku-4-5-20251001"),
            max_tokens=1024,
            system=EDIT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"<command>{directive}</command>\n<text>{text}</text>"}],
        )
        result = resp.content[0].text.strip()
        # 繁中終層防護；多語 helper 會保留日文新字體與假名 clause。
        if style != "translate_ja":
            try:
                from opencc import OpenCC
                result = convert_traditional_preserving_japanese(
                    result,
                    OpenCC("s2twp"),
                    language_hint=resolve_output_language_hint(
                        style, config.get("language"),
                    ),
                )
            except Exception:
                pass
        # 追蹤 token 用量
        _track_usage(resp, "rewrite")
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/history/export")
def api_export_history():
    """匯出歷史紀錄為 TXT 或 CSV"""
    from flask import Response
    fmt = request.args.get("format", "txt")  # txt or csv
    search = request.args.get("search", "")
    items = memory.get_history(n=2000, search=search if search else None)

    if fmt == "csv":
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["時間", "模式", "原始辨識", "最終文字", "耗時(s)"])
        for h in items:
            writer.writerow([
                h.get("timestamp", ""),
                h.get("mode", "dictate"),
                h.get("whisper_raw", ""),
                h.get("final_text", ""),
                h.get("process_time", 0),
            ])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=voice-input-history.csv"}
        )
    else:
        lines = []
        for h in items:
            ts = h.get("timestamp", "")[:19].replace("T", " ")
            text = h.get("final_text", "")
            lines.append(f"[{ts}] {text}")
        return Response(
            "\n".join(lines),
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment;filename=voice-input-history.txt"}
        )


@app.route("/api/smart_replace", methods=["GET"])
def api_get_smart_replace():
    return jsonify(load_smart_replace())


@app.route("/api/smart_replace", methods=["POST"])
def api_save_smart_replace():
    # 驗證：必須是 {str: str} dict — 壞 payload 寫進 smart_replace.json 後，
    # 每次轉寫都會在 _apply_smart_replace 炸掉，整條聽寫管線失效
    rules = request.json
    if not isinstance(rules, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in rules.items()
    ):
        return jsonify({"error": "rules must be a dict of string→string"}), 400
    save_smart_replace(rules)
    return jsonify({"ok": True})


@app.route("/api/usage")
def api_usage():
    """本月 API 用量與費用估算"""
    stats = load_stats()
    usage = stats.get("usage", {})
    return jsonify(usage)


@app.route("/api/audit-log")
def api_audit_log():
    """API 呼叫稽核日誌：最近 100 筆（元數據，不含文字內容）"""
    try:
        from config import AUDIT_LOG_FILE
        if not os.path.exists(AUDIT_LOG_FILE):
            return jsonify([])
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        n = int(request.args.get("n", 100))
        entries = []
        for line in reversed(lines[-n:]):
            try:
                entries.append(json.loads(line.strip()))
            except Exception:
                pass
        return jsonify(entries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/test-llm", methods=["POST"])
def api_test_llm():
    """測試 LLM 引擎連線：發送簡短測試訊息驗證 API Key + 模型可用性"""
    import time as _time
    data = request.json or {}
    engine = data.get("engine", "groq")
    config = load_config()
    test_msg = "Hello"
    t0 = _time.time()

    try:
        if engine == "groq":
            import openai as openai_lib
            key = config.get("groq_api_key")
            if not key: return jsonify({"ok": False, "error": "No Groq API Key"}), 200
            client = openai_lib.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key, timeout=10.0)
            model = config.get("groq_model", "llama-3.3-70b-versatile")
            client.chat.completions.create(model=model, messages=[{"role": "user", "content": test_msg}], max_tokens=5)

        elif engine == "openrouter":
            import openai as openai_lib
            key = config.get("openrouter_api_key")
            if not key: return jsonify({"ok": False, "error": "No OpenRouter API Key"}), 200
            client = openai_lib.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, timeout=15.0)
            model = config.get("openrouter_model", "qwen/qwen3-30b-a3b:free")
            client.chat.completions.create(model=model, messages=[{"role": "user", "content": test_msg}], max_tokens=5,
                                           extra_headers={"HTTP-Referer": "https://github.com/sgh-voice", "X-Title": "SGH Voice"})

        elif engine == "claude":
            key = config.get("anthropic_api_key")
            if not key: return jsonify({"ok": False, "error": "No Anthropic API Key"}), 200
            client = anthropic.Anthropic(api_key=key, timeout=10.0)
            model = config.get("claude_model", "claude-3-5-haiku-20241022")
            client.messages.create(model=model, messages=[{"role": "user", "content": test_msg}], max_tokens=5)

        elif engine == "openai":
            import openai as openai_lib
            key = config.get("openai_api_key")
            if not key: return jsonify({"ok": False, "error": "No OpenAI API Key"}), 200
            client = openai_lib.OpenAI(api_key=key, timeout=10.0)
            model = config.get("openai_model", "gpt-4o")
            client.chat.completions.create(model=model, messages=[{"role": "user", "content": test_msg}], max_tokens=5)

        elif engine == "ollama":
            import openai as openai_lib
            client = openai_lib.OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama", timeout=8.0)
            model = config.get("local_llm_model", "qwen2.5:3b")
            client.chat.completions.create(model=model, messages=[{"role": "user", "content": test_msg}], max_tokens=5)

        else:
            return jsonify({"ok": False, "error": f"Unknown engine: {engine}"}), 200

        latency = round(_time.time() - t0, 2)
        return jsonify({"ok": True, "engine": engine, "model": model, "latency": latency})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 200


@app.route("/api/service-status")
def api_service_status():
    """服務狀態：Ollama / Cloud API 連線情況（供狀態燈使用）"""
    if _engine and hasattr(_engine, 'transcriber'):
        return jsonify(_engine.transcriber.get_service_status())
    # 沒有 engine 時，直接用偵測器
    from ollama_detector import get_detector
    detector = get_detector()
    detector.detect()
    config = load_config()
    return jsonify({
        **detector.get_status_dict(),
        "has_openai_key": bool(config.get("openai_api_key")),
        "has_anthropic_key": bool(config.get("anthropic_api_key")),
        "has_groq_key": bool(config.get("groq_api_key")),
        "has_openrouter_key": bool(config.get("openrouter_api_key")),
        "hybrid_mode": config.get("enable_hybrid_mode", True),
        "local_model": config.get("local_llm_model", "qwen2.5:3b"),
    })


@app.route("/api/ollama/detect", methods=["POST"])
def api_ollama_detect():
    """手動觸發 Ollama 重新偵測"""
    from ollama_detector import get_detector
    detector = get_detector()
    status = detector.detect(force=True)
    env_check = detector.check_environment()
    return jsonify({
        **detector.get_status_dict(),
        "environment": env_check,
    })


# ─── 模型下載管理 ──────────────────────────────────────

# 模型下載狀態（全域，供 SSE 輪詢）
_download_status = {"active": False, "progress": 0, "total": 0, "message": "", "done": False, "error": ""}

# 模型 repo 對照表
_MODEL_REPOS = {
    "qwen3-asr": "Qwen/Qwen3-ASR-0.6B",
    "whisper-large-v3": "mlx-community/whisper-large-v3-mlx",
    # v2.4.0：補上 Models 頁實際展示的 mlx-whisper / Breeze 系列
    "whisper-turbo": "mlx-community/whisper-turbo",
    # Breeze 模型不在 HF cache，用本機路徑檢查（見 LOCAL_MODEL_PATHS）
    "breeze-asr-25-4bit": "__LOCAL_PATH__",
    "breeze-asr-25": "__LOCAL_PATH__",
}


def _model_disk_size(path):
    """計算目錄遞迴大小 (bytes)。"""
    if os.path.isfile(path):
        try: return os.path.getsize(path)
        except OSError: return 0
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try: total += os.path.getsize(os.path.join(root, f))
            except OSError: pass
    return total


@app.route("/api/model/status/<model_key>")
def api_model_status(model_key):
    """檢查模型是否已下載 — 支援 HF cache 與本機路徑兩種來源。"""
    from config import LOCAL_MODEL_PATHS
    # 先檢查本機路徑（Breeze 等）
    if model_key in LOCAL_MODEL_PATHS:
        path = LOCAL_MODEL_PATHS[model_key]
        downloaded = os.path.isdir(path) and os.listdir(path)
        size = _model_disk_size(path) if downloaded else 0
        return jsonify({"model": model_key, "path": path, "downloaded": bool(downloaded), "size_bytes": size})
    # 否則檢查 HF cache
    repo_id = _MODEL_REPOS.get(model_key)
    if not repo_id or repo_id == "__LOCAL_PATH__":
        return jsonify({"error": "unknown model"}), 400
    cache_name = f"models--{repo_id.replace('/', '--')}"
    hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    model_dir = os.path.join(hf_home, "hub", cache_name)
    snapshots = os.path.join(model_dir, "snapshots")
    downloaded = os.path.isdir(snapshots) and len(os.listdir(snapshots)) > 0
    size = _model_disk_size(model_dir) if downloaded else 0
    return jsonify({"model": model_key, "repo": repo_id, "downloaded": downloaded, "size_bytes": size})


@app.route("/api/model/download/<model_key>", methods=["POST"])
def api_model_download(model_key):
    """觸發模型下載（背景執行）"""
    global _download_status
    repo_id = _MODEL_REPOS.get(model_key)
    if not repo_id:
        return jsonify({"error": "unknown model"}), 400
    if _download_status["active"]:
        return jsonify({"error": "already downloading"}), 409

    import threading

    def _do_download():
        global _download_status
        _download_status = {"active": True, "progress": 0, "total": 0, "message": f"正在下載 {repo_id}...", "done": False, "error": ""}
        try:
            from huggingface_hub import snapshot_download
            from tqdm import tqdm

            # 自訂 tqdm 類，攔截進度資訊（接受 huggingface_hub 傳入的額外 kwargs）
            class ProgressTracker(tqdm):
                def __init__(self, *args, **kwargs):
                    # huggingface_hub 會傳 name= 等額外參數，tqdm 不認識，先過濾掉
                    kwargs.pop("name", None)
                    super().__init__(*args, **kwargs)

                def update(self, n=1):
                    super().update(n)
                    _download_status["progress"] = self.n
                    _download_status["total"] = self.total or 0

            snapshot_download(
                repo_id,
                tqdm_class=ProgressTracker,
            )
            _download_status["done"] = True
            _download_status["message"] = f"{repo_id} 下載完成"
        except Exception as e:
            _download_status["error"] = str(e)
            _download_status["message"] = f"下載失敗: {e}"
        finally:
            _download_status["active"] = False

    t = threading.Thread(target=_do_download, daemon=True)
    t.start()
    return jsonify({"status": "started", "repo": repo_id})


@app.route("/api/model/download-progress")
def api_model_download_progress():
    """SSE 串流下載進度"""
    def generate():
        import time
        while True:
            pct = 0
            if _download_status["total"] > 0:
                pct = round(_download_status["progress"] / _download_status["total"] * 100, 1)
            data = json.dumps({
                "active": _download_status["active"],
                "progress": _download_status["progress"],
                "total": _download_status["total"],
                "percent": pct,
                "message": _download_status["message"],
                "done": _download_status["done"],
                "error": _download_status["error"],
            })
            yield f"data: {data}\n\n"
            if _download_status["done"] or _download_status["error"]:
                break
            time.sleep(0.5)
    return Response(generate(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─── Voiceprint Management ───────────────────────────────

@app.route("/api/keychain/delete/<key_name>", methods=["POST"])
def api_keychain_delete(key_name):
    """v2.4.0：明確刪除某一支 Keychain 內的 API key（Settings 頁用）。
    回傳 {ok, key, keychain_available}。"""
    if key_name not in KEYCHAIN_KEYS:
        return jsonify({"ok": False, "error": f"unknown key: {key_name}",
                        "allowed": list(KEYCHAIN_KEYS.keys())}), 400
    available = _keychain_available()
    if not available:
        # 沒 keyring 也要清掉 config.json 內的明文（fallback 路徑）
        config = load_config()
        config[key_name] = ""
        save_config(config)
        return jsonify({"ok": True, "key": key_name, "keychain_available": False,
                        "note": "keyring 不可用，已清除 config.json fallback 值"})
    ok = _keychain_delete(key_name)
    # 同時把 config.json 內可能殘留的明文清掉（防舊資料殘留）
    try:
        config = load_config()
        config[key_name] = ""
        save_config(config)
    except Exception:
        pass
    return jsonify({"ok": ok, "key": key_name, "keychain_available": True})


@app.route("/api/voiceprint/status")
def api_voiceprint_status():
    """聲紋狀態"""
    from voiceprint import VoiceprintManager
    mgr = VoiceprintManager()
    config = load_config()
    info = mgr.get_info()
    info["enabled"] = config.get("enable_voiceprint", False)
    info["threshold"] = config.get("voiceprint_threshold", 0.97)
    return jsonify(info)


@app.route("/api/voiceprint/enroll", methods=["POST"])
def api_voiceprint_enroll():
    """建立聲紋（從指定目錄的 WAV 檔）"""
    from voiceprint import VoiceprintManager
    data = request.json or {}
    wav_dir = data.get("wav_dir", "/Volumes/Satechi_SSD/voice-input/voice-data-lin")
    mgr = VoiceprintManager()
    try:
        result = mgr.enroll_from_directory(wav_dir)
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/voiceprint/delete", methods=["POST"])
def api_voiceprint_delete():
    """刪除聲紋"""
    from voiceprint import VoiceprintManager
    mgr = VoiceprintManager()
    mgr.delete_voiceprint()
    return jsonify({"ok": True})


# ─── Recording Control from Dashboard ───────────────────
_engine = None  # Will be set by set_engine()


def set_engine(engine):
    """讓 app.py 傳入共享的 VoiceEngine 實例"""
    global _engine
    _engine = engine


@app.route("/api/recording/status")
def api_recording_status():
    """取得錄音狀態"""
    if _engine is None:
        return jsonify({"available": False, "recording": False})
    return jsonify({"available": True, "recording": _engine.is_recording})


@app.route("/api/recording/start", methods=["POST"])
def api_start_recording():
    """從 Dashboard 開始錄音"""
    if _engine is None:
        return jsonify({"error": "Engine not available"}), 503
    if _engine.is_recording:
        return jsonify({"error": "Already recording"}), 400
    _engine.start_recording()
    return jsonify({"ok": True, "status": "recording"})


@app.route("/api/recording/stop", methods=["POST"])
def api_stop_recording():
    """從 Dashboard 停止錄音並處理"""
    if _engine is None:
        return jsonify({"error": "Engine not available"}), 503
    if not _engine.is_recording:
        return jsonify({"error": "Not recording"}), 400
    import threading
    def _process():
        result = _engine.stop_and_process()
        # result 會自動透過 VoiceEngine 處理並儲存到 history
    threading.Thread(target=_process, daemon=True).start()
    return jsonify({"ok": True, "status": "processing"})


def _track_usage(response, source="anthropic"):
    """追蹤 rewrite API 用量（atomic，與 update_stats 共用同一把鎖避免覆寫 daily/total）"""
    try:
        from config import update_stats_atomic
        from datetime import date, datetime
        input_tokens = getattr(response.usage, 'input_tokens', getattr(response.usage, 'prompt_tokens', 0))
        output_tokens = getattr(response.usage, 'output_tokens', getattr(response.usage, 'completion_tokens', 0))
        model = getattr(response, 'model', 'unknown')
        month_key = date.today().strftime("%Y-%m")

        def _mutate(stats):
            if "usage" not in stats: stats["usage"] = {}
            if month_key not in stats["usage"]:
                stats["usage"][month_key] = {
                    "openai_input_tokens": 0, "openai_output_tokens": 0, "openai_whisper_seconds": 0,
                    "anthropic_input_tokens": 0, "anthropic_output_tokens": 0,
                    "groq_input_tokens": 0, "groq_output_tokens": 0, "groq_whisper_seconds": 0,
                    "openrouter_input_tokens": 0, "openrouter_output_tokens": 0,
                    "details": []
                }
            m = stats["usage"][month_key]
            for f in ["openai_input_tokens", "openai_output_tokens", "openai_whisper_seconds",
                      "anthropic_input_tokens", "anthropic_output_tokens",
                      "groq_input_tokens", "groq_output_tokens", "groq_whisper_seconds",
                      "openrouter_input_tokens", "openrouter_output_tokens"]:
                if f not in m: m[f] = 0
            if "details" not in m: m["details"] = []
            if source == "anthropic":
                m["anthropic_input_tokens"] += input_tokens
                m["anthropic_output_tokens"] += output_tokens
            elif source == "openai":
                m["openai_input_tokens"] += input_tokens
                m["openai_output_tokens"] += output_tokens
            m["details"].append({
                "t": datetime.now().isoformat(),
                "s": source, "m": model, "i": input_tokens, "o": output_tokens, "sec": 0, "type": "rewrite"
            })
            if len(m["details"]) > 100: m["details"] = m["details"][-100:]

        update_stats_atomic(_mutate)
    except Exception:
        pass


def run_dashboard(port=7865, host="127.0.0.1"):
    """v2.4.0：明確強制 host=127.0.0.1，拒絕 LAN 曝光。
    傳入非 loopback host 會被 reject — 防誤觸 0.0.0.0 暴露 API key 給整個 LAN。"""
    # 強制 loopback：常見誤用是 host="0.0.0.0" 上線 API key + 錄音控制權
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(
            f"Dashboard 拒絕綁定到 {host!r}：必須是 127.0.0.1（loopback only）。"
            "Dashboard 含 API key / 錄音控制 / 歷史資料，曝露到 LAN 等同所有資料外流。"
        )
    # 把實際使用的 port 加進同源白名單 — 7865 被占用時 _find_free_port 會 fallback
    # 到 7866+，若白名單只認 7865/7860，Dashboard 自己的 POST/PATCH/DELETE 會被
    # 自家 CSRF 防護 403，設定頁全部存不了。
    _ALLOWED_ORIGINS.update({f"http://127.0.0.1:{port}", f"http://localhost:{port}"})
    print(f"📊 Dashboard: http://{host}:{port}")
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)
