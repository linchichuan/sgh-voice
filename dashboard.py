"""
dashboard.py — Web Dashboard (Flask)
模仿 Typeless 的本地 Dashboard UI
"""
import os
import sys
import json
from flask import Flask, request, jsonify, send_from_directory
from config import load_config, save_config, load_stats, update_stats, load_smart_replace, save_smart_replace
from memory import Memory
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


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/stats")
def api_stats():
    stats = load_stats()
    config = load_config()
    personalization = memory.get_personalization_score()
    return jsonify({
        "stats": stats,
        "personalization": personalization,
        "typing_speed_wpm": config.get("typing_speed_wpm", 40),
    })


@app.route("/api/config", methods=["GET"])
def api_get_config():
    config = load_config()
    # 隱藏 API key 的中間部分
    safe = config.copy()
    for key in ["openai_api_key", "anthropic_api_key", "elevenlabs_api_key", "groq_api_key"]:
        v = safe.get(key, "")
        if len(v) > 12:
            safe[key] = v[:6] + "..." + v[-4:]
    return jsonify(safe)


@app.route("/api/config", methods=["POST"])
def api_save_config():
    config = load_config()
    data = request.json
    # 只更新非空的 API key（避免覆蓋隱藏的 key）
    for key in ["openai_api_key", "anthropic_api_key", "elevenlabs_api_key", "groq_api_key"]:
        if key in data and "..." in str(data[key]):
            data.pop(key)  # 不更新被遮蔽的 key
    config.update(data)
    save_config(config)
    return jsonify({"ok": True})


@app.route("/api/history")
def api_history():
    search = request.args.get("search", "")
    n = int(request.args.get("n", 100))
    items = memory.get_history(n=n, search=search if search else None)
    return jsonify(items)


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
    return jsonify({
        "corrections": memory.get_all_corrections(),
        "custom_words": memory.get_all_custom_words(),
    })


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
    wrong = request.json.get("wrong", "").strip()
    right = request.json.get("right", "").strip()
    if wrong and right:
        memory.add_correction(wrong, right)
    return jsonify({"ok": True})


@app.route("/api/dictionary/correction", methods=["DELETE"])
def api_remove_correction():
    wrong = request.json.get("wrong", "").strip()
    if wrong:
        memory.remove_correction(wrong)
    return jsonify({"ok": True})


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

    style_prompts = {
        # 基本改寫
        "concise": "請將以下文字精簡改寫，去除冗詞贅字，保持原意。只輸出改寫結果：",
        "formal": "請將以下文字改寫為正式書面語氣。只輸出改寫結果：",
        # 情境改寫（對標 Purri）
        "meeting": "請將以下語音內容整理為會議記錄格式，包含重點摘要和行動項目。只輸出整理結果：",
        "email": "請將以下內容改寫為一封得體的 Email 草稿，包含問候語和結尾。只輸出 Email 內容：",
        "technical": "請將以下內容改寫為技術文件風格，用詞精確、結構清晰。只輸出改寫結果：",
        "casual": "請將以下文字改寫為輕鬆口語風格，適合聊天或社群貼文。只輸出改寫結果：",
        # 翻譯
        "translate_en": "請將以下文字翻譯為英文。只輸出翻譯結果：",
        "translate_ja": "請將以下文字翻譯為日文。只輸出翻譯結果：",
        "translate_zh": "請將以下文字翻譯為繁體中文。只輸出翻譯結果：",
    }
    prompt = style_prompts.get(style, style_prompts["concise"])

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=config.get("claude_model", "claude-haiku-4-5-20251001"),
            max_tokens=1024,
            messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}],
        )
        result = resp.content[0].text.strip()
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
    rules = request.json
    save_smart_replace(rules)
    return jsonify({"ok": True})


@app.route("/api/usage")
def api_usage():
    """本月 API 用量與費用估算"""
    stats = load_stats()
    usage = stats.get("usage", {})
    return jsonify(usage)


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


def _track_usage(response, source="polish"):
    """追蹤 Claude API token 用量"""
    try:
        input_tokens = getattr(response.usage, 'input_tokens', 0)
        output_tokens = getattr(response.usage, 'output_tokens', 0)
        stats = load_stats()
        if "usage" not in stats:
            stats["usage"] = {}
        from datetime import date
        month_key = date.today().strftime("%Y-%m")
        if month_key not in stats["usage"]:
            stats["usage"][month_key] = {
                "claude_input_tokens": 0,
                "claude_output_tokens": 0,
                "claude_calls": 0,
                "whisper_seconds": 0,
            }
        m = stats["usage"][month_key]
        m["claude_input_tokens"] += input_tokens
        m["claude_output_tokens"] += output_tokens
        m["claude_calls"] += 1
        from config import save_stats
        save_stats(stats)
    except Exception:
        pass


def run_dashboard(port=7865):
    print(f"📊 Dashboard: http://localhost:{port}")
    # 抑制 Flask development server 警告（本地 Dashboard 不需要 production WSGI）
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
