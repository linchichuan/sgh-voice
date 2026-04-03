"""
transcriber.py — 語音辨識管線
Whisper API → 詞庫修正 → LLM 訊號萃取與商務編輯 (v1.7.0)
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
    # Metal GPU 鎖
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
        self._ollama_last_warn = 0.0

    def reset_clients(self):
        pass

    @property
    def ollama_detector(self):
        return get_detector()

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
                print(" " + _t("✅ mlx-whisper 模型預熱完成", "✅ mlx-whisper 予熱完了", "✅ mlx-whisper warmed up"))
            except Exception: pass

        def _warmup_ollama():
            if self.ollama_detector.detect(force=True) != OllamaStatus.CONNECTED: return
            try:
                self.local_llm.chat.completions.create(model=self.config.get("local_llm_model", "qwen3.5:latest"), messages=[{"role": "user", "content": "hi"}], max_tokens=1)
                print(" " + _t(f"✅ Ollama 預熱完成", f"✅ Ollama 予熱完了", f"✅ Ollama warmed up"))
            except Exception: pass

        threading.Thread(target=lambda: (_warmup_ollama(), _warmup_whisper()), daemon=True).start()

    def transcribe(self, audio_source, audio_duration=0, mode="dictate", edit_context=""):
        t0 = time.time()
        is_hybrid = self.config.get("enable_hybrid_mode", True)
        stt_source, llm_source = "none", "none"

        if isinstance(audio_source, np.ndarray):
            rms = np.sqrt(np.mean(audio_source ** 2))
            if rms < 0.003: return None

        if isinstance(audio_source, np.ndarray) and self.config.get("enable_voiceprint", False):
            if self._voiceprint_mgr.is_enrolled:
                vp_score = self._voiceprint_mgr.verify(audio_source)
                if vp_score < self.config.get("voiceprint_threshold", 0.97): return None

        # STT 路由
        raw = None
        stt_engine = self.config.get("stt_engine", "mlx-whisper")
        if stt_engine == "groq":
            raw = self._groq_stt(audio_source)
            if raw: stt_source = "groq"
        elif stt_engine != "cloud-only" and is_hybrid:
            if isinstance(audio_source, np.ndarray) or audio_duration <= self.config.get("hybrid_audio_threshold", 15):
                raw = self._local_stt(audio_source)
                if raw: stt_source = "local"

        if not raw and self.config.get("groq_api_key"):
            raw = self._groq_stt(audio_source)
            if raw: stt_source = "groq"
        
        if not raw and self.config.get("openai_api_key"):
            raw = self._whisper_api_fallback(audio_source)
            if raw: stt_source = "cloud"
            
        if not raw or not raw.strip(): return None

        scene = self.config.get("active_scene", "general")
        corrected = self.memory.apply_corrections(raw, SCENE_PRESETS.get(scene, {}).get("corrections"))
        corrected = self._apply_smart_replace(corrected)

        # LLM 智慧編輯
        final = None
        skip_llm = (mode == "dictate" and len(corrected) <= 20 and not self._has_filler_words(corrected))
        if skip_llm:
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
        entry = {
            "timestamp": datetime.now().isoformat(), "whisper_raw": raw, "final_text": final,
            "mode": mode, "process_time": round(process_time, 2), "stt_source": stt_source, "llm_source": llm_source,
        }
        self.memory.add_to_history(entry)
        if mode == "dictate": self._async_extract_keywords(final)
        return {"raw": raw, "final": final, "process_time": process_time, "entry": entry}

    # ─── LLM 處理核心 (訊號與雜訊分離策略) ───

    _DICTATE_SYSTEM = (
        "你是一位資深的商務通訊編輯（Executive Editor）。你的任務是將混亂、瑣碎的語音對話整理為「專業、邏輯清晰」的書面訊息。\n\n"
        "【第一步：雜訊清除】\n"
        "- 徹底刪除：語助詞（嗯、啊、呃、えーと、あの）、口頭禪（那個、就是說、Basically）、說錯話的自我修正（例：一箱不對是五箱 -> 直接留五箱）。\n"
        "- 過濾無關內容：刪除視訊對話中與核心意圖無關的背景雜音描述或操作語（例：我找一下文件、有聽到嗎）。\n\n"
        "【第二步：核心訊號保留 (Crucial Facts)】\n"
        "- 絕對保留：所有人名、產品名 (VIZZ)、數量、日期、預算、特定要求、冷藏/物流條件。\n"
        "- 邏輯修正：將音近但邏輯錯誤的詞依語境修正（例：クルーボックス -> クールボックス）。\n\n"
        "【第三步：結構重組與優化】\n"
        "- 商務化：將口語轉換為專業語體，補上得體的問候與敬語。\n"
        "- 結構化：若涉及多項內容或複雜邏輯，請主動使用【標題】與條列式排版，使其可直接用於 LINE/Email 傳送。\n\n"
        "【輸出限制】\n"
        "只輸出編輯後的最終文字，嚴禁任何解釋。"
    )

    def _get_system_prompt(self):
        base = self.config.get("claude_system_prompt") or self._DICTATE_SYSTEM
        user_style = self.memory.get_style_profile()
        style_instruction = f"\n【使用者偏好風格】\n{user_style}"
        scene_extra = SCENE_PRESETS.get(self.config.get("active_scene", "general"), {}).get("system_prompt_extra", "")
        app_prompt = detect_app_style(self.config).get("prompt", "")
        return f"{base}\n{style_instruction}\n{scene_extra}\n{app_prompt}".strip()

    def _groq_llm_process(self, text, mode, edit_context):
        api_key = self.config.get("groq_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=8.0)
            model = self.config.get("groq_model", "llama-3.3-70b-versatile")
            system = "根據指令修改文字。" if mode == "edit" else self._get_system_prompt()
            print(" " + _t(f"🤖 [Groq LLM] 啟動: {model}", f"🤖 [Groq LLM] 起動中: {model}", f"🤖 [Groq LLM] Launching: {model}"))
            t0 = time.time()
            resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": text}], temperature=0.3, max_tokens=2048)
            res = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', resp.choices[0].message.content).strip()
            print(" " + _t(f"⚡ [Groq LLM] 完成 ({time.time()-t0:.2f}s)", f"⚡ [Groq LLM] 完了", f"⚡ [Groq LLM] Done"))
            return res if not self._is_llm_hallucination(res, text) else text
        except Exception: return None

    def _openrouter_process(self, text, mode, edit_context):
        api_key = self.config.get("openrouter_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, timeout=15.0)
            model = self.config.get("openrouter_model", "qwen/qwen-2.5-72b-instruct")
            system = "根據指令修改文字。" if mode == "edit" else self._get_system_prompt()
            print(" " + _t(f"🌐 [OpenRouter] 啟動: {model}", f"🌐 [OpenRouter] 起動中: {model}", f"🌐 [OpenRouter] Launching: {model}"))
            t0 = time.time()
            resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": text}], temperature=0.3, max_tokens=2048, extra_headers={"HTTP-Referer": "https://shingihou.com", "X-Title": "SGH Voice"})
            res = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', resp.choices[0].message.content).strip()
            print(" " + _t(f"✅ [OpenRouter] 完成 ({time.time()-t0:.2f}s)", f"✅ [OpenRouter] 完了", f"✅ [OpenRouter] Done"))
            return res if not self._is_llm_hallucination(res, text) else text
        except Exception: return None

    def _claude_process(self, text, mode, edit_context):
        api_key = self.config.get("anthropic_api_key")
        if not api_key: return None
        try:
            client = anthropic.Anthropic(api_key=api_key, timeout=10.0)
            model = self.config.get("claude_model", "claude-3-5-haiku-20241022")
            resp = client.messages.create(model=model, system=self._get_system_prompt(), messages=[{"role": "user", "content": text}], max_tokens=2048, temperature=0.3)
            res = resp.content[0].text.strip()
            print(" " + _t(f"⚡ [Claude] 完成", f"⚡ [Claude] 完了", f"⚡ [Claude] Done"))
            return res if not self._is_llm_hallucination(res, text) else text
        except Exception: return None

    def _openai_process(self, text, mode, edit_context):
        api_key = self.config.get("openai_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(api_key=api_key, timeout=10.0)
            model = self.config.get("openai_model", "gpt-4o")
            resp = client.chat.completions.create(model=model, messages=[{"role": "system", "content": self._get_system_prompt()}, {"role": "user", "content": text}], temperature=0.3, max_tokens=2048)
            res = resp.choices[0].message.content.strip()
            print(" " + _t(f"⚡ [OpenAI] 完成", f"⚡ [OpenAI] 完了", f"⚡ [OpenAI] Done"))
            return res if not self._is_llm_hallucination(res, text) else text
        except Exception: return None

    def _local_llm_process(self, text):
        if time.time() < self._ollama_backoff_until: return None
        if self.ollama_detector.status != OllamaStatus.CONNECTED: return None
        try:
            t0 = time.time()
            resp = self.local_llm.chat.completions.create(model=self.config.get("local_llm_model", "qwen3.5:latest"), messages=[{"role": "system", "content": self._get_system_prompt()}, {"role": "user", "content": text}], temperature=0.1, max_tokens=1024)
            print(f" 💻 [Local Ollama] 完成")
            return resp.choices[0].message.content.strip()
        except Exception:
            self._ollama_fail_count += 1
            self._ollama_backoff_until = time.time() + min(120, 5 * (2 ** self._ollama_fail_count))
            return None

    def _groq_stt(self, audio_source):
        api_key = self.config.get("groq_api_key")
        if not api_key: return None
        try:
            import tempfile, soundfile as sf
            sr = self.config.get("sample_rate", 16000)
            if isinstance(audio_source, np.ndarray):
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, audio_source, sr); tmp.close()
                audio_path = tmp.name; is_temp = True
            else: audio_path = audio_source; is_temp = False
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=10.0)
            with open(audio_path, "rb") as f:
                prompt = self.memory.build_whisper_prompt(self.config.get("custom_words", []))
                resp = client.audio.transcriptions.create(model=self.config.get("groq_whisper_model", "whisper-large-v3-turbo"), file=f, prompt=prompt, language=self.config.get("language", "auto") if self.config.get("language") != "auto" else None)
            if is_temp: os.unlink(audio_path)
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

    def _whisper_api_fallback(self, audio_source):
        api_key = self.config.get("openai_api_key")
        if not api_key: return None
        try:
            import tempfile, soundfile as sf
            if isinstance(audio_source, np.ndarray):
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, audio_source, 16000); tmp.close(); audio_path = tmp.name; is_temp = True
            else: audio_path = audio_source; is_temp = False
            client = openai.OpenAI(api_key=api_key)
            with open(audio_path, "rb") as f: resp = client.audio.transcriptions.create(model="whisper-1", file=f)
            if is_temp: os.unlink(audio_path)
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
        if any(result.startswith(m) for m in ["好的", "沒問題", "了解", "為您", "以下是", "I appreciate"]): return True
        return len(result) > len(original_text) * 4 and len(original_text) > 10

    def _build_edit_prompt(self, cmd, original):
        return f"原文：「{original}」\n指令：{cmd}\n請直接輸出修改後的結果。"

    def _async_extract_keywords(self, text):
        def task():
            words = re.findall(r'[A-Za-z][A-Za-z0-9\-]{2,}', text)
            for kw in set(words): self.memory.add_auto_word(kw)
        threading.Thread(target=task, daemon=True).start()
