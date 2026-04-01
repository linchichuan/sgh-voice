"""
transcriber.py — 語音辨識管線
Whisper API → 詞庫修正 → Claude 潤稿/去填充詞/自我修正偵測
模仿 Typeless 的智慧後處理
"""
import re
import time
import threading
import numpy as np
from datetime import datetime
import openai
import anthropic
from config import load_smart_replace, SCENE_PRESETS, DEFAULT_APP_STYLES, detect_app_style, LOCAL_MODEL_PATHS, BREEZE_MODELS
from ollama_detector import get_detector, OllamaStatus
from voiceprint import VoiceprintManager
import os

# ─── 系統語言偵測 ─────────────────────────────────────────
def _get_sys_lang():
    try:
        lang = os.environ.get('LANG', '')
        if not lang:
            import locale
            lang, _ = locale.getdefaultlocale()
    except Exception:
        lang = 'en_US'
    if not lang: lang = 'en_US'
    lang = lang.lower()
    if 'ja' in lang: return 'ja'
    if 'zh' in lang: return 'zh'
    return 'en'

_LANG = _get_sys_lang()

def _t(zh, ja, en):
    if _LANG == 'ja': return ja
    if _LANG == 'zh': return zh
    return en


class Transcriber:
    # Metal GPU 鎖：序列化所有 mlx-whisper 呼叫，避免與 AppKit 的 Metal 渲染衝突
    _metal_lock = threading.Lock()

    def __init__(self, config, memory):
        self.config = config
        self.memory = memory
        # 繁中三層防護第三層：OpenCC s2twp（簡體→繁體台灣用語）
        try:
            from opencc import OpenCC
            self._opencc = OpenCC('s2twp')
        except ImportError:
            print(" ⚠️ opencc-python-reimplemented 未安裝，跳過繁中轉換")
            self._opencc = None
        # 預編譯填充詞正則，加速匹配
        self._filler_pattern = self._compile_filler_pattern()
        # Ollama timeout 退避
        self._ollama_backoff_until = 0.0
        self._ollama_fail_count = 0
        # 聲紋驗證器
        self._voiceprint_mgr = VoiceprintManager()
        self._ollama_last_warn = 0.0

    def reset_clients(self):
        """與 app.py 的 reload_config 連動，清除快取的 client"""
        # 現在我們改用呼叫時動態建立 Client，此方法留作相容性介面
        pass

    @property
    def ollama_detector(self):
        return get_detector()

    def warmup(self):
        """序列預熱 mlx-whisper 模型和 Ollama Qwen，避免 Metal GPU 衝突"""
        def _warmup_whisper():
            try:
                import time as _time
                _time.sleep(3) # 等待 UI 初始化

                import mlx_whisper
                import tempfile
                import soundfile as sf
                silence = np.zeros(1600, dtype=np.float32)  # 0.1s
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, silence, 16000)
                tmp.close()

                warmup_model_name = self.config.get("local_whisper_model", "mlx-community/whisper-turbo")
                warmup_model_path = LOCAL_MODEL_PATHS.get(warmup_model_name, warmup_model_name)
                warmup_kwargs = {"path_or_hf_repo": warmup_model_path, "language": "en"}
                if warmup_model_name in BREEZE_MODELS:
                    warmup_kwargs["fp16"] = True
                with Transcriber._metal_lock:
                    mlx_whisper.transcribe(tmp.name, **warmup_kwargs)
                os.unlink(tmp.name)
                print(" " + _t("✅ mlx-whisper 模型預熱完成", "✅ mlx-whisper モデルの準備が完了しました", "✅ mlx-whisper model warmed up"))
            except Exception as e:
                print(" " + _t(f"⚠️ mlx-whisper 預熱失敗: {e}", f"⚠️ mlx-whisper 予熱失敗: {e}", f"⚠️ mlx-whisper warmup failed: {e}"))

        def _warmup_ollama():
            detector = self.ollama_detector
            status = detector.detect(force=True)
            if status != OllamaStatus.CONNECTED:
                return
            try:
                warmup_client = openai.OpenAI(
                    base_url=detector.base_url or "http://127.0.0.1:11434/v1",
                    api_key="ollama",
                    timeout=30.0,
                )
                warmup_client.chat.completions.create(
                    model=self.config.get("local_llm_model", "qwen3.5:latest"),
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
                models = detector.available_models
                model_str = ", ".join(models[:5]) if models else "unknown"
                print(" " + _t(f"✅ Ollama 預熱完成 (可用模型: {model_str})", f"✅ Ollama 予熱完了 (利用可能なモデル: {model_str})", f"✅ Ollama warmup completed (Available models: {model_str})"))
            except Exception as e:
                print(" " + _t(f"⚠️ Ollama 預熱失敗: {e}", f"⚠️ Ollama 予熱失敗: {e}", f"⚠️ Ollama warmup failed: {e}"))

        threading.Thread(target=lambda: (_warmup_ollama(), _warmup_whisper()), daemon=True).start()

    def transcribe(self, audio_source, audio_duration=0, mode="dictate", edit_context=""):
        t0 = time.time()
        is_hybrid = self.config.get("enable_hybrid_mode", True)
        stt_source = "none"
        llm_source = "none"

        # Step 0: 音訊能量檢查
        if isinstance(audio_source, np.ndarray):
            rms = np.sqrt(np.mean(audio_source ** 2))
            if rms < 0.003:
                print(f" 🔇 音訊能量過低 (RMS={rms:.5f})，跳過辨識")
                return None

        # Step 0.5: 聲紋驗證
        if isinstance(audio_source, np.ndarray) and self.config.get("enable_voiceprint", False):
            if self._voiceprint_mgr.is_enrolled:
                vp_threshold = self.config.get("voiceprint_threshold", 0.97)
                vp_score = self._voiceprint_mgr.verify(audio_source)
                if vp_score < vp_threshold:
                    print(" " + _t(f"🔇 聲紋不符 (score={vp_score:.4f} < {vp_threshold})", f"🔇 声紋不一致 (score={vp_score:.4f} < {vp_threshold})", f"🔇 Voiceprint mismatch"))
                    return None
                print(" " + _t(f"🔐 聲紋驗證通過 (score={vp_score:.4f})", f"🔐 声紋認証に合格しました", f"🔐 Voiceprint verified"))

        # Step 1: STT 路由
        raw = None
        stt_engine = self.config.get("stt_engine", "mlx-whisper")

        if stt_engine == "groq":
            raw = self._groq_stt(audio_source)
            if raw: stt_source = "groq"
        elif stt_engine != "cloud-only" and is_hybrid:
            if isinstance(audio_source, np.ndarray) or audio_duration <= self.config.get("hybrid_audio_threshold", 15):
                raw = self._local_stt(audio_source)
                if raw: stt_source = "local"

        if not raw and stt_engine != "groq" and self.config.get("groq_api_key"):
            raw = self._groq_stt(audio_source)
            if raw: stt_source = "groq"

        if not raw and self.config.get("openai_api_key"):
            # OpenAI Whisper Final Fallback
            raw = self._whisper_api_fallback(audio_source)
            if raw: stt_source = "cloud"
            
        if not raw or not raw.strip(): return None

        # Step 2 & 3: 詞庫修正 & Smart Replace
        scene = self.config.get("active_scene", "general")
        scene_data = SCENE_PRESETS.get(scene, {})
        corrected = self.memory.apply_corrections(raw, scene_data.get("corrections"))
        corrected = self._apply_smart_replace(corrected)

        # Step 4: App 場景
        app_style = detect_app_style(self.config)
        if app_style["style"] != "default":
            print(f" 🎯 [App Style] {app_style['app_name']} → {app_style['style']}")

        # Step 5: LLM 路由
        final = None
        skip_llm = False
        if mode == "dictate" and len(corrected) <= 20 and not self._has_filler_words(corrected):
            final = corrected
            llm_source = "skip"
            print(" ⚡ [短句跳過 LLM 後處理，極速模式]")
            skip_llm = True

        if not skip_llm and self.config.get("enable_claude_polish"):
            pref_engine = self.config.get("llm_engine", "ollama")
            
            def try_groq(): return self._groq_llm_process(corrected, mode, edit_context), "groq"
            def try_or(): return self._openrouter_process(corrected, mode, edit_context), "openrouter"
            def try_claude(): return self._claude_process(corrected, mode, edit_context), "claude"
            def try_openai(): return self._openai_process(corrected, mode, edit_context), "openai"
            def try_ollama():
                if is_hybrid and mode == "dictate":
                    return self._local_llm_process(corrected), "local"
                return None, None

            routes_map = {
                "groq": [try_groq, try_or, try_claude, try_openai, try_ollama],
                "openrouter": [try_or, try_groq, try_claude, try_openai, try_ollama],
                "claude": [try_claude, try_groq, try_or, try_openai, try_ollama],
                "openai": [try_openai, try_groq, try_or, try_claude, try_ollama],
                "ollama": [try_ollama, try_groq, try_or, try_claude, try_openai],
            }
            routes = routes_map.get(pref_engine, routes_map["ollama"])

            for route in routes:
                res, source = route()
                if res:
                    final = res
                    llm_source = source
                    break

        if final is None:
            final = self._local_filler_removal(corrected) if self.config.get("enable_filler_removal") else corrected
            llm_source = "regex"

        if self._opencc and final: final = self._opencc.convert(final)

        process_time = time.time() - t0
        entry = {
            "timestamp": datetime.now().isoformat(),
            "whisper_raw": raw, "corrected": corrected, "final_text": final,
            "mode": mode, "audio_duration": round(audio_duration, 1),
            "process_time": round(process_time, 2), "stt_source": stt_source, "llm_source": llm_source,
        }
        self.memory.add_to_history(entry)
        if mode == "dictate": self._async_extract_keywords(final)

        return {"raw": raw, "corrected": corrected, "final": final, "process_time": process_time, "entry": entry}

    # ─── LLM 處理核心 (完全動態化，與 Dashboard 設定連動) ───

    def _get_system_prompt(self):
        """獲取完整組裝的 System Prompt"""
        base = self.config.get("claude_system_prompt") or self._DICTATE_SYSTEM
        scene = self.config.get("active_scene", "general")
        scene_extra = SCENE_PRESETS.get(scene, {}).get("system_prompt_extra", "")
        app_prompt = detect_app_style(self.config).get("prompt", "")
        full = base
        if scene_extra: full += "\n" + scene_extra
        if app_prompt: full += "\n" + app_prompt
        return full

    def _groq_llm_process(self, text, mode, edit_context):
        api_key = self.config.get("groq_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=8.0)
            model = self.config.get("groq_model", "llama-3.3-70b-versatile")
            system = "根據語音指令修改文字。只輸出修改結果。" if mode == "edit" else self._get_system_prompt()
            user_msg = self._build_edit_prompt(text, edit_context) if mode == "edit" else text
            
            print(" " + _t(f"🤖 [Groq LLM] 啟動: {model}", f"🤖 [Groq LLM] 起動中: {model}", f"🤖 [Groq LLM] Launching: {model}"))
            t0 = time.time()
            resp = client.chat.completions.create(
                model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                temperature=0.3, max_tokens=2048
            )
            res = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', resp.choices[0].message.content).strip()
            self._track_usage(resp, "groq")
            print(" " + _t(f"⚡ [Groq LLM] 完成 ({time.time()-t0:.2f}s)", f"⚡ [Groq LLM] 完了", f"⚡ [Groq LLM] Done"))
            return res if not self._is_llm_hallucination(res, text) else text
        except Exception as e:
            print(f" ⚠️ Groq 錯誤: {e}"); return None

    def _openrouter_process(self, text, mode, edit_context):
        api_key = self.config.get("openrouter_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, timeout=15.0)
            model = self.config.get("openrouter_model", "qwen/qwen-2.5-72b-instruct")
            system = "根據語音指令修改文字。" if mode == "edit" else self._get_system_prompt()
            user_msg = self._build_edit_prompt(text, edit_context) if mode == "edit" else text
            
            print(" " + _t(f"🌐 [OpenRouter] 啟動: {model}", f"🌐 [OpenRouter] 起動中: {model}", f"🌐 [OpenRouter] Launching: {model}"))
            t0 = time.time()
            resp = client.chat.completions.create(
                model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                temperature=0.3, max_tokens=2048, extra_headers={"HTTP-Referer": "https://shingihou.com", "X-Title": "SGH Voice"}
            )
            res = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', resp.choices[0].message.content).strip()
            self._track_usage(resp, "openai") # OR uses OAI format
            print(" " + _t(f"✅ [OpenRouter] 完成 ({time.time()-t0:.2f}s)", f"✅ [OpenRouter] 完了", f"✅ [OpenRouter] Done"))
            return res if not self._is_llm_hallucination(res, text) else text
        except Exception as e:
            print(f" ⚠️ OpenRouter 錯誤: {e}"); return None

    def _claude_process(self, text, mode, edit_context):
        api_key = self.config.get("anthropic_api_key")
        if not api_key: return None
        try:
            client = anthropic.Anthropic(api_key=api_key, timeout=10.0)
            model = self.config.get("claude_model", "claude-3-5-haiku-20241022")
            system = self._get_system_prompt()
            user_msg = self._build_edit_prompt(text, edit_context) if mode == "edit" else text
            
            print(" " + _t(f"☁️ [Claude] 啟動: {model}", f"☁️ [Claude] 起動中: {model}", f"☁️ [Claude] Launching: {model}"))
            t0 = time.time()
            resp = client.messages.create(
                model=model, system=system, messages=[{"role": "user", "content": user_msg}],
                max_tokens=2048, temperature=0.3
            )
            res = resp.content[0].text.strip()
            self._track_usage(resp, "claude")
            print(" " + _t(f"⚡ [Claude] 完成 ({time.time()-t0:.2f}s)", f"⚡ [Claude] 完了", f"⚡ [Claude] Done"))
            return res if not self._is_llm_hallucination(res, text) else text
        except Exception as e:
            print(f" ⚠️ Claude 錯誤: {e}"); return None

    def _openai_process(self, text, mode, edit_context):
        api_key = self.config.get("openai_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(api_key=api_key, timeout=10.0)
            model = self.config.get("openai_model", "gpt-4o")
            system = self._get_system_prompt()
            user_msg = self._build_edit_prompt(text, edit_context) if mode == "edit" else text
            
            print(" " + _t(f"🤖 [OpenAI] 啟動: {model}", f"🤖 [OpenAI] 起動中: {model}", f"🤖 [OpenAI] Launching: {model}"))
            t0 = time.time()
            resp = client.chat.completions.create(
                model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                temperature=0.3, max_tokens=2048
            )
            res = resp.choices[0].message.content.strip()
            self._track_usage(resp, "openai")
            print(" " + _t(f"⚡ [OpenAI] 完成 ({time.time()-t0:.2f}s)", f"⚡ [OpenAI] 完了", f"⚡ [OpenAI] Done"))
            return res if not self._is_llm_hallucination(res, text) else text
        except Exception as e:
            print(f" ⚠️ OpenAI 錯誤: {e}"); return None

    def _local_llm_process(self, text):
        if time.time() < self._ollama_backoff_until: return None
        detector = self.ollama_detector
        if detector.status != OllamaStatus.CONNECTED: return None
        try:
            t0 = time.time()
            resp = self.local_llm.chat.completions.create(
                model=self.config.get("local_llm_model", "qwen3.5:latest"),
                messages=[{"role": "system", "content": self._get_system_prompt()}, {"role": "user", "content": text}],
                temperature=0.1, max_tokens=1024
            )
            res = resp.choices[0].message.content.strip()
            print(f" 💻 [Local Ollama] 完成 ({time.time()-t0:.2f}s)")
            return res
        except Exception as e:
            self._ollama_fail_count += 1
            self._ollama_backoff_until = time.time() + min(120, 5 * (2 ** self._ollama_fail_count))
            print(f" ⚠️ Local LLM 錯誤: {e}"); return None

    # ─── STT / Whisper 核心 ───

    def _groq_stt(self, audio_source):
        api_key = self.config.get("groq_api_key")
        if not api_key: return None
        try:
            import tempfile, soundfile as sf
            audio_path = audio_source
            is_temp = False
            if isinstance(audio_source, np.ndarray):
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, audio_source, self.config.get("sample_rate", 16000))
                tmp.close(); audio_path = tmp.name; is_temp = True
            
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=10.0)
            with open(audio_path, "rb") as f:
                prompt = self.memory.build_whisper_prompt(self.config.get("custom_words", []))
                resp = client.audio.transcriptions.create(
                    model=self.config.get("groq_whisper_model", "whisper-large-v3-turbo"),
                    file=f, prompt=prompt, language=self.config.get("language", "auto") if self.config.get("language") != "auto" else None
                )
            if is_temp: os.unlink(audio_path)
            return resp.text
        except Exception: return None

    def _local_stt(self, audio_source):
        engine = self.config.get("stt_engine", "mlx-whisper")
        if engine == "qwen3-asr": return self._qwen3_asr(audio_source)
        return self._local_whisper(audio_source)

    def _local_whisper(self, audio_source):
        try:
            import mlx_whisper
            model_name = self.config.get("local_whisper_model", "mlx-community/whisper-turbo")
            model_path = LOCAL_MODEL_PATHS.get(model_name, model_name)
            kwargs = {"path_or_hf_repo": model_path, "temperature": 0.0, "condition_on_previous_text": False}
            if model_name in BREEZE_MODELS: kwargs["fp16"] = True
            
            prompt = self.memory.build_whisper_prompt(self.config.get("custom_words", []))
            kwargs["initial_prompt"] = f"繁體中文、日本語、English mixed conversation。{prompt}"
            
            with Transcriber._metal_lock:
                result = mlx_whisper.transcribe(audio_source, **kwargs)
            return result.get("text", "")
        except Exception: return None

    def _whisper_api_fallback(self, audio_source):
        api_key = self.config.get("openai_api_key")
        if not api_key: return None
        try:
            import tempfile, soundfile as sf
            audio_path = audio_source
            is_temp = False
            if isinstance(audio_source, np.ndarray):
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, audio_source, self.config.get("sample_rate", 16000))
                tmp.close(); audio_path = tmp.name; is_temp = True
            
            client = openai.OpenAI(api_key=api_key)
            with open(audio_path, "rb") as f:
                resp = client.audio.transcriptions.create(model="whisper-1", file=f)
            if is_temp: os.unlink(audio_path)
            return resp.text
        except Exception: return None

    # ─── 其他工具方法 ───

    _DICTATE_SYSTEM = (
        "你是一個專業的語音辨識後處理助手。請移除填充詞、修正同音錯字，並加上正確標點與分段。只輸出最終文字。"
    )

    def _apply_smart_replace(self, text):
        rules = load_smart_replace()
        for trigger, replacement in rules.items():
            if trigger in text: text = text.replace(trigger, replacement)
        return text

    def _compile_filler_pattern(self):
        filler_words = self.config.get("filler_words", {})
        all_fillers = []
        for l in filler_words.values(): all_fillers.extend(l)
        if not all_fillers: return None
        all_fillers.sort(key=len, reverse=True)
        return re.compile("|".join(re.escape(f) for f in all_fillers))

    def _has_filler_words(self, text):
        return bool(self._filler_pattern.search(text)) if self._filler_pattern else False

    def _local_filler_removal(self, text):
        filler_words = self.config.get("filler_words", {})
        result = text
        for lang_fillers in filler_words.values():
            for filler in lang_fillers:
                pattern = r'(?<=[，。、！？\s])' + re.escape(filler) + r'(?=[，。、！？\s])'
                result = re.sub(pattern, '', result)
                if result.startswith(filler): result = result[len(filler):].lstrip("，、 ")
        return re.sub(r'\s+', ' ', result).strip()

    def _is_llm_hallucination(self, result, original_text):
        startswith_markers = ["好的", "沒問題", "了解", "為您", "以下是", "I appreciate", "Sure"]
        if any(result.startswith(m) for m in startswith_markers): return True
        if len(result) > len(original_text) * 3 and len(original_text) > 10: return True
        return False

    def _build_edit_prompt(self, cmd, original):
        return f"原文：「{original}」\n指令：{cmd}\n請直接輸出修改後的結果。"

    def _async_extract_keywords(self, text):
        def task():
            words = re.findall(r'[A-Za-z][A-Za-z0-9\-]{2,}', text)
            for kw in set(words): self.memory.add_auto_word(kw)
        threading.Thread(target=task, daemon=True).start()

    def _track_usage(self, response, source):
        try:
            from config import load_stats, save_stats
            from datetime import date
            it = getattr(response.usage, 'input_tokens', getattr(response.usage, 'prompt_tokens', 0))
            ot = getattr(response.usage, 'output_tokens', getattr(response.usage, 'completion_tokens', 0))
            stats = load_stats(); month = date.today().strftime("%Y-%m")
            if "usage" not in stats: stats["usage"] = {}
            if month not in stats["usage"]: stats["usage"][month] = {"claude_input_tokens":0, "claude_output_tokens":0, "openai_input_tokens":0, "openai_output_tokens":0}
            m = stats["usage"][month]
            if source == "claude": m["claude_input_tokens"]+=it; m["claude_output_tokens"]+=ot
            else: m["openai_input_tokens"]+=it; m["openai_output_tokens"]+=ot
            save_stats(stats)
        except Exception: pass
