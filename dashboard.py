"""
dashboard.py — Web Dashboard (Flask)
模仿 Typeless 的本地 Dashboard UI
"""
import os
import sys
import json
from flask import Flask, request, jsonify, send_from_directory, Response
from config import load_config, save_config, load_stats, update_stats, load_smart_replace, save_smart_replace, DEFAULT_APP_STYLES
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
        "typing_speed_cpm": config.get("typing_speed_cpm", 50),
    })


@app.route("/api/config", methods=["GET"])
def api_get_config():
    config = load_config()
    # 隱藏 API key 的中間部分
    safe = config.copy()
    safe["app_styles"] = config.get("app_styles", DEFAULT_APP_STYLES)
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
        learned = memory.learn_correction(old_text, new_text)

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
    return jsonify({
        "corrections": memory.get_all_corrections(),
        "custom_words": memory.get_dictionary_words(),
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
}


@app.route("/api/model/status/<model_key>")
def api_model_status(model_key):
    """檢查模型是否已下載"""
    repo_id = _MODEL_REPOS.get(model_key)
    if not repo_id:
        return jsonify({"error": "unknown model"}), 400
    # 檢查 HF 快取
    cache_name = f"models--{repo_id.replace('/', '--')}"
    hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    model_dir = os.path.join(hf_home, "hub", cache_name)
    snapshots = os.path.join(model_dir, "snapshots")
    downloaded = os.path.isdir(snapshots) and len(os.listdir(snapshots)) > 0
    return jsonify({"model": model_key, "repo": repo_id, "downloaded": downloaded})


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
