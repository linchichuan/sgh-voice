"""
transcriber.py — 語音辨識管線
Whisper API → 詞庫修正 → 機械式純文字精修 (v1.9.0)
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
    _metal_lock = threading.Lock()

    def __init__(self, config, memory):
        self.config = config
        self.memory = memory
        try:
            from opencc import OpenCC
            self._opencc = OpenCC('s2twp')
        except ImportError:
            self._opencc = None
        self._filler_pattern = self._compile_filler_pattern()
        self._ollama_backoff_until = 0.0
        self._ollama_fail_count = 0
        self._voiceprint_mgr = VoiceprintManager()

    def reset_clients(self): pass

    @property
    def ollama_detector(self): return get_detector()

    @property
    def local_llm(self):
        detector = self.ollama_detector
        base_url = detector.base_url or "http://127.0.0.1:11434/v1"
        return openai.OpenAI(base_url=base_url, api_key="ollama", timeout=self.config.get("local_llm_timeout_sec", 6.0))

    def warmup(self):
        def _warmup_whisper():
            try:
                import time as _time
                _time.sleep(3)
                import mlx_whisper, tempfile, soundfile as sf
                silence = np.zeros(1600, dtype=np.float32)
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, silence, 16000); tmp.close()
                model_name = self.config.get("local_whisper_model", "mlx-community/whisper-turbo")
                model_path = LOCAL_MODEL_PATHS.get(model_name, model_name)
                kwargs = {"path_or_hf_repo": model_path, "language": "en"}
                if model_name in BREEZE_MODELS: kwargs["fp16"] = True
                with Transcriber._metal_lock: mlx_whisper.transcribe(tmp.name, **kwargs)
                os.unlink(tmp.name)
                print(" " + _t("✅ mlx-whisper 預熱完成", "✅ mlx-whisper 準備完了", "✅ mlx-whisper ready"))
            except Exception: pass

        def _warmup_ollama():
            if self.ollama_detector.detect(force=True) != OllamaStatus.CONNECTED: return
            try:
                self.local_llm.chat.completions.create(model=self.config.get("local_llm_model", "qwen3.5:latest"), messages=[{"role": "user", "content": "hi"}], max_tokens=1)
                print(" " + _t(f"✅ Ollama 預熱完成", f"✅ Ollama 準備完了", f"✅ Ollama ready"))
            except Exception: pass

        threading.Thread(target=lambda: (_warmup_ollama(), _warmup_whisper()), daemon=True).start()

    def transcribe(self, audio_source, audio_duration=0, mode="dictate", edit_context=""):
        t0 = time.time()
        is_hybrid = self.config.get("enable_hybrid_mode", True)
        stt_source, llm_source = "none", "none"

        if isinstance(audio_source, np.ndarray):
            rms = np.sqrt(np.mean(audio_source ** 2))
            if rms < 0.003: return None

        # 聲紋驗證（靜默）
        if isinstance(audio_source, np.ndarray) and self.config.get("enable_voiceprint", False):
            if self._voiceprint_mgr.is_enrolled:
                vp_score = self._voiceprint_mgr.verify(audio_source)
                if vp_score < self.config.get("voiceprint_threshold", 0.97): return None

        # Step 1: STT
        raw = None
        stt_engine = self.config.get("stt_engine", "mlx-whisper")
        if stt_engine == "groq":
            raw = self._groq_stt(audio_source, duration=audio_duration)
            if raw: stt_source = "groq"
        elif stt_engine != "cloud-only" and is_hybrid:
            if isinstance(audio_source, np.ndarray) or audio_duration <= self.config.get("hybrid_audio_threshold", 15):
                raw = self._local_stt(audio_source)
                if raw: stt_source = "local"

        if not raw and self.config.get("groq_api_key"):
            raw = self._groq_stt(audio_source, duration=audio_duration)
            if raw: stt_source = "groq"
        
        if not raw and self.config.get("openai_api_key"):
            raw = self._whisper_api_fallback(audio_source, duration=audio_duration)
            if raw: stt_source = "cloud"
            
        if not raw or not raw.strip(): return None

        # Step 2: 詞庫修正
        corrected = self.memory.apply_corrections(raw, SCENE_PRESETS.get(self.config.get("active_scene", "general"), {}).get("corrections"))
        corrected = self._apply_smart_replace(corrected)

        # Step 3: LLM 智慧精修
        final = None
        # 短句跳過 (極速)
        if mode == "dictate" and len(corrected) <= 20 and not self._has_filler_words(corrected):
            final, llm_source = corrected, "skip"
        elif self.config.get("enable_claude_polish"):
            pref_engine = self.config.get("llm_engine", "ollama")
            def try_groq(): return self._groq_llm_process(corrected, mode, edit_context), "groq"
            def try_or(): return self._openrouter_process(corrected, mode, edit_context), "openrouter"
            def try_claude(): return self._claude_process(corrected, mode, edit_context), "claude"
            def try_openai(): return self._openai_process(corrected, mode, edit_context), "openai"
            def try_ollama():
                if is_hybrid and mode == "dictate": return self._local_llm_process(corrected), "local"
                return None, None

            routes_map = {
                "groq": [try_groq, try_or, try_claude, try_openai, try_ollama],
                "openrouter": [try_or, try_groq, try_claude, try_openai, try_ollama],
                "claude": [try_claude, try_groq, try_or, try_openai, try_ollama],
                "openai": [try_openai, try_groq, try_or, try_claude, try_ollama],
                "ollama": [try_ollama, try_groq, try_or, try_claude, try_openai],
            }
            for route in routes_map.get(pref_engine, routes_map["ollama"]):
                res, source = route()
                if res: final, llm_source = res, source; break

        if final is None:
            final = self._local_filler_removal(corrected) if self.config.get("enable_filler_removal") else corrected
            llm_source = "regex"

        if self._opencc and final: final = self._opencc.convert(final)

        process_time = time.time() - t0
        # 紀錄歷史
        self.memory.add_to_history({
            "timestamp": datetime.now().isoformat(), "whisper_raw": raw, "final_text": final,
            "mode": mode, "process_time": round(process_time, 2), "stt_source": stt_source, "llm_source": llm_source,
        })
        if mode == "dictate": self._async_extract_keywords(final)
        return {"raw": raw, "final": final, "process_time": process_time}

    # ─── LLM 核心 (Transcoder 模式：嚴禁回答，嚴禁對話) ───

    _DICTATE_SYSTEM = (
        "你是一個機械式的文字轉碼器。唯一任務：將語音草稿轉化為排版正確、無贅字的文章。\n"
        "【絕對指令】\n"
        "1. 嚴禁對話：禁止回答問題。如果使用者問『你是誰』，你就輸出『你是誰』並加標點。禁止自我介紹。\n"
        "2. 嚴禁解釋：禁止說『好的』、『以下是修正結果』。只輸出結果文字。\n"
        "3. 嚴禁翻譯：禁止擅自將一種語言轉為另一種語言。\n"
        "4. 100% 保留細節：除非是語助詞，否則禁止刪減任何名詞或數據。"
    )

    def _get_system_prompt(self):
        base = self.config.get("claude_system_prompt") or self._DICTATE_SYSTEM
        user_style = self.memory.get_style_profile()
        scene_extra = SCENE_PRESETS.get(self.config.get("active_scene", "general"), {}).get("system_prompt_extra", "")
        return f"{base}\n【User Style】\n{user_style}\n{scene_extra}".strip()

    def _groq_llm_process(self, text, mode, edit_context):
        api_key = self.config.get("groq_api_key")
        if not api_key: 
            print(" ⚠️ Groq API Key 缺失"); return None
        try:
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=6.0)
            model = self.config.get("groq_model", "llama-3.3-70b-versatile")
            system = self._EDIT_SYSTEM if mode == "edit" else self._get_system_prompt()
            t0 = time.time()
            resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": text}], temperature=0.0, max_tokens=2048)
            res = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', resp.choices[0].message.content).strip()
            self._track_usage("groq", model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
            
            if self._is_llm_hallucination(res, text):
                print(f" ⚠️ [Groq] 偵測到對話幻覺，已捨棄：{res[:20]}..."); return None
                
            print(" " + _t(f"⚡ [Groq] 完成 ({time.time()-t0:.2f}s)", f"⚡ [Groq] 完了", f"⚡ [Groq] Done"))
            return res
        except Exception as e:
            print(f" ⚠️ Groq 請求失敗: {e}"); return None

    def _openrouter_process(self, text, mode, edit_context):
        api_key = self.config.get("openrouter_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, timeout=10.0)
            model = self.config.get("openrouter_model", "qwen/qwen-2.5-72b-instruct")
            system = self._EDIT_SYSTEM if mode == "edit" else self._get_system_prompt()
            t0 = time.time()
            resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": text}], temperature=0.0, max_tokens=2048, extra_headers={"HTTP-Referer": "https://shingihou.com", "X-Title": "SGH Voice"})
            res = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', resp.choices[0].message.content).strip()
            self._track_usage("openrouter", model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
            
            if self._is_llm_hallucination(res, text):
                print(f" ⚠️ [OpenRouter] 偵測到對話幻覺，已捨棄"); return None
                
            print(" " + _t(f"✅ [OpenRouter] 完成 ({time.time()-t0:.2f}s)", f"✅ [OpenRouter] 完了", f"✅ [OpenRouter] Done"))
            return res
        except Exception as e:
            print(f" ⚠️ OpenRouter 請求失敗: {e}"); return None

    def _claude_process(self, text, mode, edit_context):
        api_key = self.config.get("anthropic_api_key")
        if not api_key: return None
        try:
            client = anthropic.Anthropic(api_key=api_key, timeout=8.0)
            model = self.config.get("claude_model", "claude-3-5-haiku-20241022")
            system = self._EDIT_SYSTEM if mode == "edit" else self._get_system_prompt()
            t0 = time.time()
            resp = client.messages.create(model=model, system=system, messages=[{"role": "user", "content": text}], max_tokens=2048, temperature=0.0)
            res = resp.content[0].text.strip()
            self._track_usage("anthropic", model, resp.usage.input_tokens, resp.usage.output_tokens)
            if self._is_llm_hallucination(res, text): return None
            print(" " + _t(f"☁️ [Claude] 完成", f"☁️ [Claude] 完了", f"☁️ [Claude] Done"))
            return res
        except Exception: return None

    def _openai_process(self, text, mode, edit_context):
        api_key = self.config.get("openai_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(api_key=api_key, timeout=8.0)
            model = self.config.get("openai_model", "gpt-4o")
            system = self._EDIT_SYSTEM if mode == "edit" else self._get_system_prompt()
            t0 = time.time()
            resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": text}], temperature=0.0, max_tokens=2048)
            res = resp.choices[0].message.content.strip()
            self._track_usage("openai", model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
            if self._is_llm_hallucination(res, text): return None
            print(" " + _t(f"🤖 [OpenAI] 完成", f"🤖 [OpenAI] 完了", f"🤖 [OpenAI] Done"))
            return res
        except Exception: return None

    def _local_llm_process(self, text):
        if time.time() < self._ollama_backoff_until: return None
        if self.ollama_detector.status != OllamaStatus.CONNECTED: return None
        try:
            resp = self.local_llm.chat.completions.create(model=self.config.get("local_llm_model", "qwen3.5:latest"), messages=[{"role": "system", "content": self._get_system_prompt()}, {"role": "user", "content": text}], temperature=0.0, max_tokens=1024)
            return resp.choices[0].message.content.strip()
        except Exception:
            self._ollama_fail_count += 1
            self._ollama_backoff_until = time.time() + min(120, 5 * (2 ** self._ollama_fail_count))
            return None

    def _groq_stt(self, audio_source, duration=0):
        api_key = self.config.get("groq_api_key")
        if not api_key: return None
        try:
            import tempfile, soundfile as sf
            sr = self.config.get("sample_rate", 16000)
            if isinstance(audio_source, np.ndarray):
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, audio_source, sr); tmp.close(); audio_path = tmp.name; is_temp = True
                if duration == 0: duration = len(audio_source) / sr
            else: audio_path = audio_source; is_temp = False
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=10.0)
            with open(audio_path, "rb") as f:
                prompt = self.memory.build_whisper_prompt(self.config.get("custom_words", []))
                model = self.config.get("groq_whisper_model", "whisper-large-v3-turbo")
                resp = client.audio.transcriptions.create(model=model, file=f, prompt=prompt, language=self.config.get("language", "auto") if self.config.get("language") != "auto" else None)
            if is_temp: os.unlink(audio_path)
            self._track_usage("groq", model, seconds=duration)
            return resp.text
        except Exception: return None

    def _local_stt(self, audio_source):
        try:
            import mlx_whisper
            model_path = LOCAL_MODEL_PATHS.get(self.config.get("local_whisper_model"), self.config.get("local_whisper_model", "mlx-community/whisper-turbo"))
            kwargs = {"path_or_hf_repo": model_path, "temperature": 0.0, "condition_on_previous_text": False}
            if "breeze" in str(model_path).lower(): kwargs["fp16"] = True
            with Transcriber._metal_lock: result = mlx_whisper.transcribe(audio_source, **kwargs)
            return result.get("text", "")
        except Exception: return None

    def _whisper_api_fallback(self, audio_source, duration=0):
        api_key = self.config.get("openai_api_key")
        if not api_key: return None
        try:
            import tempfile, soundfile as sf
            if isinstance(audio_source, np.ndarray):
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, audio_source, 16000); tmp.close(); audio_path = tmp.name; is_temp = True
                if duration == 0: duration = len(audio_source) / 16000
            else: audio_path = audio_source; is_temp = False
            client = openai.OpenAI(api_key=api_key)
            with open(audio_path, "rb") as f: resp = client.audio.transcriptions.create(model="whisper-1", file=f)
            if is_temp: os.unlink(audio_path)
            self._track_usage("openai", "whisper-1", seconds=duration)
            return resp.text
        except Exception: return None

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
        conv_markers = ["好的", "沒問題", "了解", "為您", "以下是", "I appreciate", "您目前", "這是一個", "Sure"]
        if any(result.startswith(m) for m in conv_markers): return True
        return len(result) > len(original_text) * 4 and len(original_text) > 10

    _EDIT_SYSTEM = (
        "你是一個精準的文字編輯器。規則：1. 最小更動原文。2. 嚴禁解釋或問候。3. 只輸出修改後的純文字。"
    )

    def _build_edit_prompt(self, cmd, original):
        return f"<original>{original}</original>\n<command>{cmd}</command>\nOutput only the resulting text:"

    def _async_extract_keywords(self, text):
        def task():
            words = re.findall(r'[A-Za-z][A-Za-z0-9\-]{2,}', text)
            for kw in set(words): self.memory.add_auto_word(kw)
        threading.Thread(target=task, daemon=True).start()

    def _track_usage(self, source, model, input_tokens=0, output_tokens=0, seconds=0):
        try:
            from config import load_stats, save_stats
            from datetime import date
            stats = load_stats(); month_key = date.today().strftime("%Y-%m")
            if "usage" not in stats: stats["usage"] = {}
            if month_key not in stats["usage"]:
                stats["usage"][month_key] = {"openai_input_tokens":0, "openai_output_tokens":0, "openai_whisper_seconds":0, "anthropic_input_tokens":0, "anthropic_output_tokens":0, "groq_input_tokens":0, "groq_output_tokens":0, "groq_whisper_seconds":0, "openrouter_input_tokens":0, "openrouter_output_tokens":0}
            m = stats["usage"][month_key]
            if source == "openai": m["openai_input_tokens"]+=input_tokens; m["openai_output_tokens"]+=output_tokens; m["openai_whisper_seconds"]+=seconds
            elif source == "anthropic": m["anthropic_input_tokens"]+=input_tokens; m["anthropic_output_tokens"]+=output_tokens
            elif source == "groq": m["groq_input_tokens"]+=input_tokens; m["groq_output_tokens"]+=output_tokens; m["groq_whisper_seconds"]+=seconds
            elif source == "openrouter": m["openrouter_input_tokens"]+=input_tokens; m["openrouter_output_tokens"]+=output_tokens
            save_stats(stats)
        except Exception: pass

    def get_service_status(self) -> dict:
        detector = self.ollama_detector
        if detector.status == OllamaStatus.UNKNOWN: detector.detect()
        return { **detector.get_status_dict(), "has_openai_key": bool(self.config.get("openai_api_key")), "has_anthropic_key": bool(self.config.get("anthropic_api_key")), "has_groq_key": bool(self.config.get("groq_api_key")), "has_openrouter_key": bool(self.config.get("openrouter_api_key")), "local_model": self.config.get("local_llm_model", "qwen3.5:latest"), "stt_engine": self.config.get("stt_engine", "mlx-whisper") }
