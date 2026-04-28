"""
transcriber.py — 語音辨識管線
Whisper API → 詞庫修正 → 機械式純文字精修 (v1.9.8)
"""
import re
import time
import sys
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
            ok, reason = self._audio_quality_check(audio_source)
            if not ok:
                print(f" 🚫 [audio gate] 跳過：{reason}")
                return None

        if isinstance(audio_source, np.ndarray) and self.config.get("enable_voiceprint", False):
            if self._voiceprint_mgr.is_enrolled:
                vp_score = self._voiceprint_mgr.verify(audio_source)
                if vp_score < self.config.get("voiceprint_threshold", 0.97): return None

        # ── STT 階段 ─────────────────────────────────────
        t_stt0 = time.time()
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
        t_stt = time.time() - t_stt0

        # 句尾 meta-command 偵測：「...以上翻成英文」「改正式」等 → 切換 mode
        if mode == "dictate":
            stripped, override_style = self._detect_voice_command(raw)
            if override_style:
                raw = stripped
                mode = "edit"
                edit_context = override_style
                print(f" 🎙→✏️ [voice command] 偵測到句尾指令，切換為 rewrite 模式：{override_style}")

        scene_key = self.config.get("active_scene", "general")
        app_id = None
        try:
            from AppKit import NSWorkspace
            curr_app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if curr_app:
                app_id = curr_app.bundleIdentifier()
        except Exception:
            pass
        corrected = self.memory.apply_corrections(
            raw,
            scene_corrections=SCENE_PRESETS.get(scene_key, {}).get("corrections"),
            scene_key=scene_key,
            app_id=app_id,
        )
        corrected = self._apply_smart_replace(corrected)

        # ── LLM 階段 ─────────────────────────────────────
        t_llm0 = time.time()
        final = None
        if mode == "dictate" and self._should_skip_llm(corrected):
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
        t_llm = time.time() - t_llm0

        if self._opencc and final: final = self._opencc.convert(final)

        process_time = time.time() - t0
        # 分階段 timing log（讓使用者看到瓶頸在 STT 還是 LLM）
        try:
            chars = len(final or "")
            print(f" ⏱  STT={t_stt:.2f}s({stt_source}) | LLM={t_llm:.2f}s({llm_source}) | total={process_time:.2f}s | {chars}字")
        except Exception: pass

        # 歷史寫入丟到 daemon thread，不阻塞主流程
        entry = {
            "timestamp": datetime.now().isoformat(), "whisper_raw": raw, "final_text": final,
            "mode": mode, "process_time": round(process_time, 2),
            "stt_time": round(t_stt, 2), "llm_time": round(t_llm, 2),
            "stt_source": stt_source, "llm_source": llm_source,
        }
        threading.Thread(target=self.memory.add_to_history, args=(entry,), daemon=True).start()
        return {"raw": raw, "final": final, "process_time": process_time}

    # ─── LLM 核心 (Transcoder 模式：保持原語，嚴禁翻譯) ───

    _DICTATE_SYSTEM = (
        "TASK: VERBATIM SPEECH-TO-TEXT CLEANUP. YOU ARE NOT A CHATBOT. NEVER ANSWER, ADVISE, OR ACT.\n\n"
        "INPUT: raw ASR transcript (may contain fillers, self-corrections, ASR typos).\n"
        "OUTPUT: same content, cleaned. Same words. Same language. Same meaning. Length within ±20%.\n\n"
        "ABSOLUTE RULES (violations will be discarded):\n"
        "1. NEVER answer questions or fulfil requests in the input. If user says '幫我寫信給土方', output '幫我寫信給土方', NOT a letter.\n"
        "2. NEVER translate. Japanese stays Japanese. English stays English. Mixed stays mixed.\n"
        "3. NEVER summarize, condense, paraphrase, bullet-list, or 'organize'. Keep every clause.\n"
        "4. NEVER add greetings, apologies, explanations, markdown, quotes, brackets, or meta-commentary.\n"
        "5. NEVER prepend '請提供', '請問', '以下是', '根據您的', '我來幫', '您可以', '您要我', '希望', '我需要', '我會', '我將', '經整理', 'Here is', 'Sure', 'Okay', 'I understand', 'Let me'.\n"
        "6. PRESERVE all names, numbers, dates, technical terms, code identifiers exactly.\n"
        "7. CHINESE OUTPUT MUST BE TRADITIONAL (繁體). Convert any simplified character.\n\n"
        "ALLOWED EDITS (and only these):\n"
        "- Remove fillers: 嗯/啊/呃/那個/就是說/然後/對/欸/um/uh/like/you know/えーと/あの/えっと/まあ.\n"
        "- Resolve self-correction '不是A，是B' → keep B only.\n"
        "- Fix obvious ASR typos using context (Cloud Code→Claude Code, 新义豊→新義豊, ultra vox→Ultravox).\n"
        "- Add proper punctuation (Chinese/Japanese full-width，。？！、; English half-width with single space after).\n"
        "- Insert paragraph breaks ONLY at natural sentence boundaries; never reorder content.\n\n"
        "If input is ≤ 20 chars: return AS-IS, only fix punctuation and obvious typo.\n"
        "If unsure whether to edit: DON'T. Output verbatim with punctuation only."
    )

    def _get_system_prompt(self):
        base = self.config.get("claude_system_prompt") or self._DICTATE_SYSTEM
        user_style = self.memory.get_style_profile()
        scene_extra = SCENE_PRESETS.get(self.config.get("active_scene", "general"), {}).get("system_prompt_extra", "")
        return f"{base}\n[Style Guide: {user_style}]\n{scene_extra}".strip()

    def _audio_quality_check(self, audio_array):
        """音訊品質前置守門。回傳 (ok: bool, reason: str)。
        防呆三項：太靜（純背景）、削峰嚴重（爆音/失真）、能量分布不像語音（純噪音）。
        所有閾值可由 config 覆寫，預設值對 16kHz mono 麥克風校準。"""
        if audio_array is None or len(audio_array) == 0:
            return False, "empty"
        if not self.config.get("enable_audio_gate", True):
            return True, ""

        # 1) RMS 太低 → 純靜音/背景音（沿用原本 0.003 但可調）
        rms_min = float(self.config.get("audio_gate_rms_min", 0.003))
        rms = float(np.sqrt(np.mean(audio_array.astype(np.float32) ** 2)))
        if rms < rms_min:
            return False, f"rms={rms:.4f} < {rms_min}"

        # 2) Clipping 比例過高 → 削峰失真，Whisper 會幻覺
        clip_max = float(self.config.get("audio_gate_clipping_max", 0.05))
        peak_thresh = 0.98
        clip_ratio = float(np.mean(np.abs(audio_array) > peak_thresh))
        if clip_ratio > clip_max:
            return False, f"clipping={clip_ratio:.2%} > {clip_max:.2%}"

        # 3) Crest factor（峰值/RMS）過低 → 平頂雜訊；過高 → 單一爆音
        peak = float(np.max(np.abs(audio_array)))
        if peak > 1e-6:
            crest = peak / max(rms, 1e-9)
            crest_min = float(self.config.get("audio_gate_crest_min", 1.8))
            crest_max = float(self.config.get("audio_gate_crest_max", 60.0))
            if crest < crest_min:
                return False, f"crest={crest:.1f} < {crest_min}（疑似純噪音）"
            if crest > crest_max:
                return False, f"crest={crest:.1f} > {crest_max}（疑似單一爆音）"

        return True, ""

    def _few_shot_pairs(self, mode=None):
        """產生個人化 few-shot user/assistant 訊息對。
        edit 模式（rewrite API）不注入；enable_fewshot 為 False 時不注入。"""
        if mode == "edit":
            return []
        if not self.config.get("enable_fewshot", True):
            return []
        n = int(self.config.get("fewshot_count", 3))
        if n <= 0:
            return []
        try:
            examples = self.memory.get_few_shot_examples(n=n)
        except Exception:
            return []
        pairs = []
        for raw, fin in examples:
            pairs.append({"role": "user", "content": raw})
            pairs.append({"role": "assistant", "content": fin})
        return pairs

    def _dynamic_max_tokens(self, text):
        """依輸入長度動態決定 max_tokens 上限：短句不分配 2048 budget，回應更快。
        經驗值：output ≈ input × 1.4，再加 20% safety margin。"""
        n = len(text or "")
        if n <= 80: return 256
        if n <= 200: return 512
        if n <= 500: return 1024
        return 2048

    def _llm_timeout(self):
        """雲端 LLM 呼叫的 timeout（秒）。預設 5 秒，超時 fallback 下一個引擎。"""
        return float(self.config.get("llm_timeout_sec", 5.0))

    def _wrap_edit_text(self, text, edit_context):
        """edit 模式時把風格指令包進 user 訊息。edit_context 既支援 style key 也支援自訂指令。"""
        if not edit_context:
            return text
        directive = self._STYLE_DIRECTIVES.get(edit_context, edit_context)
        return f"{directive}\n\n{text}"

    def _groq_llm_process(self, text, mode, edit_context):
        api_key = self.config.get("groq_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=self._llm_timeout())
            model = self.config.get("groq_model", "llama-3.3-70b-versatile")
            system = self._EDIT_SYSTEM if mode == "edit" else self._get_system_prompt()
            user_text = self._wrap_edit_text(text, edit_context) if mode == "edit" else text
            t0 = time.time()
            messages = [{"role": "system", "content": system}, *self._few_shot_pairs(mode), {"role": "user", "content": user_text}]
            resp = client.chat.completions.create(model=model, messages=messages, temperature=0.0, max_tokens=self._dynamic_max_tokens(text))
            res = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', resp.choices[0].message.content).strip()
            self._track_usage("groq", model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
            if self._is_llm_hallucination(res, text):
                print(f" ⚠️ [Groq] 偵測到幻覺，已捨棄: {res[:20]}..."); return None
            print(" " + _t(f"⚡ [Groq] 完成 ({time.time()-t0:.2f}s)", f"⚡ [Groq] 完了", f"⚡ [Groq] Done"))
            return res
        except Exception as e:
            print(f" ⚠️ Groq 失敗/超時: {e}"); return None

    def _openrouter_process(self, text, mode, edit_context):
        api_key = self.config.get("openrouter_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, timeout=self._llm_timeout())
            model = self.config.get("openrouter_model", "qwen/qwen3.6-plus")
            system = self._EDIT_SYSTEM if mode == "edit" else self._get_system_prompt()
            t0 = time.time()
            messages = [{"role": "system", "content": system}, *self._few_shot_pairs(mode), {"role": "user", "content": self._wrap_edit_text(text, edit_context) if mode == "edit" else text}]
            resp = client.chat.completions.create(model=model, messages=messages, temperature=0.0, max_tokens=self._dynamic_max_tokens(text), extra_headers={"HTTP-Referer": "https://shingihou.com", "X-Title": "SGH Voice"})
            res = re.sub(r'<think>[\s\S]*?</think>|<think>[\s\S]*$', '', resp.choices[0].message.content).strip()
            self._track_usage("openrouter", model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
            if self._is_llm_hallucination(res, text):
                print(f" ⚠️ [OpenRouter] 偵測到幻覺，已捨棄"); return None
            print(" " + _t(f"✅ [OpenRouter] 完成 ({time.time()-t0:.2f}s)", f"✅ [OpenRouter] 完了", f"✅ [OpenRouter] Done"))
            return res
        except Exception as e:
            print(f" ⚠️ OpenRouter 失敗/超時: {e}"); return None

    def _claude_process(self, text, mode, edit_context):
        api_key = self.config.get("anthropic_api_key")
        if not api_key: return None
        try:
            client = anthropic.Anthropic(api_key=api_key, timeout=self._llm_timeout())
            model = self.config.get("claude_model", "claude-haiku-4-5-20251001")
            system = self._EDIT_SYSTEM if mode == "edit" else self._get_system_prompt()
            t0 = time.time()
            messages = [*self._few_shot_pairs(mode), {"role": "user", "content": self._wrap_edit_text(text, edit_context) if mode == "edit" else text}]
            resp = client.messages.create(model=model, system=system, messages=messages, max_tokens=self._dynamic_max_tokens(text), temperature=0.0)
            res = resp.content[0].text.strip()
            self._track_usage("anthropic", model, resp.usage.input_tokens, resp.usage.output_tokens)
            if self._is_llm_hallucination(res, text):
                print(f" ⚠️ [Claude] 偵測到幻覺，已捨棄: {res[:20]}..."); return None
            print(" " + _t(f"☁️ [Claude] 完成 ({time.time()-t0:.2f}s)", f"☁️ [Claude] 完了", f"☁️ [Claude] Done"))
            return res
        except Exception as e:
            print(f" ⚠️ Claude 失敗/超時: {e}"); return None

    def _openai_process(self, text, mode, edit_context):
        api_key = self.config.get("openai_api_key")
        if not api_key: return None
        try:
            client = openai.OpenAI(api_key=api_key, timeout=self._llm_timeout())
            model = self.config.get("openai_model", "gpt-4o")
            system = self._EDIT_SYSTEM if mode == "edit" else self._get_system_prompt()
            t0 = time.time()
            messages = [{"role": "system", "content": system}, *self._few_shot_pairs(mode), {"role": "user", "content": self._wrap_edit_text(text, edit_context) if mode == "edit" else text}]
            resp = client.chat.completions.create(model=model, messages=messages, temperature=0.0, max_tokens=self._dynamic_max_tokens(text))
            res = resp.choices[0].message.content.strip()
            self._track_usage("openai", model, resp.usage.prompt_tokens, resp.usage.completion_tokens)
            if self._is_llm_hallucination(res, text):
                print(f" ⚠️ [OpenAI] 偵測到對話幻覺，已捨棄"); return None
            print(" " + _t(f"🤖 [OpenAI] 完成", f"🤖 [OpenAI] 完了", f"🤖 [OpenAI] Done"))
            return res
        except Exception: return None

    def _local_llm_process(self, text):
        if time.time() < self._ollama_backoff_until: return None
        if self.ollama_detector.status != OllamaStatus.CONNECTED: return None
        try:
            messages = [{"role": "system", "content": self._get_system_prompt()}, *self._few_shot_pairs(), {"role": "user", "content": text}]
            resp = self.local_llm.chat.completions.create(model=self.config.get("local_llm_model", "qwen3.5:latest"), messages=messages, temperature=0.0, max_tokens=1024)
            return resp.choices[0].message.content.strip()
        except Exception:
            self._ollama_fail_count += 1
            self._ollama_backoff_until = time.time() + min(120, 5 * (2 ** self._ollama_fail_count))
            return None

    # ─── STT Prompt 建構（注入使用者詞庫 + 場景詞）──────
    _LANG_HINT = "繁體中文, 日本語, English mixed."

    def _build_stt_prompt(self):
        """注入 custom_words + 當前場景詞彙 + BASE_CUSTOM_WORDS（去重，≤20 詞 / ≤200 字）。"""
        try:
            custom = self.config.get("custom_words", []) or []
            scene_key = self.config.get("active_scene", "general")
            scene_words = SCENE_PRESETS.get(scene_key, {}).get("custom_words", [])
            vocab = self.memory.build_whisper_prompt(custom, scene_words)
        except Exception:
            vocab = ""
        return f"{self._LANG_HINT} Keep original language. Vocabulary: {vocab}" if vocab else f"{self._LANG_HINT} Keep original language."

    # ─── Whisper 重複幻覺 sanitizer ─────────────────────
    _REP_PATTERN = re.compile(r'(.{1,15}?)\1{4,}')

    def _sanitize_repetition(self, text):
        """連續同一片段重複 ≥5 次 → 截到第一次出現（Whisper / Groq Whisper 共通幻覺）。"""
        if not text or len(text) < 20: return text
        m = self._REP_PATTERN.search(text)
        if not m: return text
        cut = m.start() + len(m.group(1))
        cleaned = text[:cut].rstrip('，。、！？ \n\t')
        try:
            print(f" ⚠️ [Whisper] 重複幻覺已截斷: ...{m.group(1)[:8]}x{(m.end()-m.start())//max(1,len(m.group(1)))}+")
        except Exception: pass
        return cleaned

    def _groq_stt(self, audio_source, duration=0):
        api_key = self.config.get("groq_api_key")
        if not api_key: return None
        try:
            import io, soundfile as sf
            sr = self.config.get("sample_rate", 16000)
            if isinstance(audio_source, np.ndarray):
                buf = io.BytesIO()
                sf.write(buf, audio_source, sr, format="WAV"); buf.seek(0); buf.name = "audio.wav"
                file_obj = buf
                if duration == 0: duration = len(audio_source) / sr
            else:
                file_obj = open(audio_source, "rb")
            client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key, timeout=10.0)
            try:
                prompt = self._build_stt_prompt()
                model = self.config.get("groq_whisper_model", "whisper-large-v3-turbo")
                resp = client.audio.transcriptions.create(model=model, file=file_obj, prompt=prompt, language=self.config.get("language", "auto") if self.config.get("language") != "auto" else None)
            finally:
                if not isinstance(audio_source, np.ndarray): file_obj.close()
            self._track_usage("groq", model, seconds=duration)
            return self._sanitize_repetition(resp.text)
        except Exception: return None

    def _local_stt(self, audio_source):
        try:
            import mlx_whisper
            model_path = LOCAL_MODEL_PATHS.get(self.config.get("local_whisper_model"), self.config.get("local_whisper_model", "mlx-community/whisper-turbo"))
            kwargs = {"path_or_hf_repo": model_path, "temperature": 0.0, "condition_on_previous_text": False}
            if "breeze" in str(model_path).lower(): kwargs["fp16"] = True
            kwargs["initial_prompt"] = self._build_stt_prompt()
            with Transcriber._metal_lock: result = mlx_whisper.transcribe(audio_source, **kwargs)
            return self._sanitize_repetition(result.get("text", ""))
        except Exception: return None

    def _whisper_api_fallback(self, audio_source, duration=0):
        api_key = self.config.get("openai_api_key")
        if not api_key: return None
        try:
            import io, soundfile as sf
            if isinstance(audio_source, np.ndarray):
                buf = io.BytesIO()
                sf.write(buf, audio_source, 16000, format="WAV"); buf.seek(0); buf.name = "audio.wav"
                file_obj = buf
                if duration == 0: duration = len(audio_source) / 16000
            else:
                file_obj = open(audio_source, "rb")
            client = openai.OpenAI(api_key=api_key)
            try:
                prompt = self._build_stt_prompt()
                resp = client.audio.transcriptions.create(model="whisper-1", file=file_obj, prompt=prompt)
            finally:
                if not isinstance(audio_source, np.ndarray): file_obj.close()
            self._track_usage("openai", "whisper-1", seconds=duration)
            return self._sanitize_repetition(resp.text)
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

    def _has_filler_words(self, text): return bool(self._filler_pattern.search(text)) if self._filler_pattern else False

    # 中文動作詞 / 指令詞：短句出現這些 → LLM 容易誤判為對話
    _ACTION_PATTERN = re.compile(r'(請繼續|繼續|請幫|幫我|你幫|麻煩你?|拜託|你能不能|你可不可以|請問|執行|處理一下|搞定|懂嗎|知道嗎|好不好|可以嗎|對吧|是嗎)')
    _CJK_ONLY = re.compile(r'^[\s\u3000-\u303f\uff00-\uffef\u4e00-\u9fa5\u3040-\u30ff，。、！？；：「」『』（）【】0-9]+$')

    def _should_skip_llm(self, text):
        """決定是否跳過 LLM 後處理：
        - ≤20 字且無填充詞 → skip（原規則）
        - ≤60 字 + 中/日文 + 含動作詞 + 無填充詞 → skip（避免對話幻覺）
        """
        if not text: return True
        t = text.strip()
        if not t: return True
        has_filler = self._has_filler_words(t)
        if len(t) <= 20 and not has_filler:
            return True
        if (len(t) <= 60 and not has_filler
                and self._CJK_ONLY.match(t)
                and self._ACTION_PATTERN.search(t)):
            return True
        return False

    def _local_filler_removal(self, text):
        filler_words = self.config.get("filler_words", {})
        result = text
        for lang_fillers in filler_words.values():
            for filler in lang_fillers:
                pattern = r'(?<=[，。、！？\s])' + re.escape(filler) + r'(?=[，。、！？\s])'
                result = re.sub(pattern, '', result)
                if result.startswith(filler): result = result[len(filler):].lstrip("，、 ")
        return re.sub(r'\s+', ' ', result).strip()

    _CONV_MARKERS = (
        "好的", "沒問題", "了解", "為您", "以下是", "您目前", "這是一個", "這段文字",
        "根據您的", "如果您", "我會幫您", "我已經", "我明白", "明白了",
        "請提供", "請問", "請告訴", "請您", "請繼續處理", "您可以", "您要我", "您能",
        "希望我", "希望您", "我可以幫", "我來幫", "我會根據", "我會幫", "我需要更多",
        "我需要您", "我需要你", "我將", "我會將", "我來協助", "讓我",
        "經整理", "整理後", "改寫後", "修正後", "原文如下", "此段", "經修正",
        "確認所有", "建議您", "如您所見", "為了協助", "為了幫助",
        "Sure", "Okay", "Certainly", "I understand", "Hello", "I appreciate",
        "Here is", "Here are", "Please provide", "I cannot", "I don't",
        "I'd be happy", "Let me", "I'll help", "I can help", "Of course",
        "Thank you", "Thanks for", "I'll need",
    )

    # 標點 / 空白：bigram 重疊率計算時略過
    _SKIP_CHARS = set('，。、！？；：「」『』（）【】〈〉《》 \t\n\r　,.!?;:()[]{}"\'')

    def _bigram_overlap(self, raw, final):
        """字元 bigram 重疊率：raw 的 bigram 在 final 中出現的比例。
        對「保留原句小修飾」友善（>70%），對「重新生成」嚴格（<30%）。"""
        if len(raw) < 4 or len(final) < 2: return 1.0
        bigrams = []
        for i in range(len(raw) - 1):
            a, b = raw[i], raw[i + 1]
            if a in self._SKIP_CHARS or b in self._SKIP_CHARS: continue
            bigrams.append(a + b)
        if not bigrams: return 1.0
        kept = sum(1 for bg in bigrams if bg in final)
        return kept / len(bigrams)

    # 助理句型「中段」特徵（非起始也會出現）
    _MIDWAY_MARKERS = (
        "請提供", "請您提供", "請告訴我", "我會根據", "我將根據", "以便我進行",
        "Please provide", "let me know", "I'll need more",
    )

    def _is_llm_hallucination(self, result, original_text):
        if not result or not original_text: return False
        r = result.strip(); o = original_text.strip()
        # 1. 助理對話起手詞
        for m in self._CONV_MARKERS:
            if r.startswith(m): return True
        # 2. 助理句型中段（如「…，請提供…」出現但原文沒說）
        for m in self._MIDWAY_MARKERS:
            if m in r and m not in o: return True
        # 3. 過度擴張（>2.5 倍且原文 ≥10 字）
        if len(o) >= 10 and len(r) > len(o) * 2.5: return True
        # 4. 內容重疊率（≥30 字才判定）
        if len(o) >= 30:
            overlap = self._bigram_overlap(o, r)
            # 嚴重重生（< 30%）→ 必為幻覺
            if overlap < 0.30: return True
            # 中度改寫（< 50%）+ 明顯縮減（< 70% 長度）→ 摘要型幻覺
            if overlap < 0.50 and len(r) < len(o) * 0.7: return True
            # 大量擴寫（> 120%）+ 低重疊（< 55%）→ 補寫型幻覺
            if overlap < 0.55 and len(r) > len(o) * 1.2: return True
        return False

    _EDIT_SYSTEM = (
        "TASK: PURE TEXT EDITING.\n"
        "RULES: 1. Modify ONLY per command. 2. Preserve original formatting. 3. NO CHAT. NO EXPLANATION."
    )

    # 風格指令對照表（與 app.py:VoiceEngine._REWRITE_STYLE_PROMPTS 同義；用於語音控制詞偵測後的 LLM 包裝）
    _STYLE_DIRECTIVES = {
        "concise":     "請將以下文字精簡改寫，去除冗詞贅字，保持原意。只輸出改寫結果，不要任何前後綴。",
        "formal":      "請將以下文字改寫為正式書面語氣。只輸出改寫結果。",
        "casual":      "請將以下文字改寫為輕鬆口語風格。只輸出改寫結果。",
        "email":       "請將以下內容改寫為一封得體的 Email 草稿。只輸出 Email 內容。",
        "technical":   "請將以下內容改寫為技術文件風格，用詞精確。只輸出改寫結果。",
        "translate_en":"請將以下文字翻譯為英文。只輸出翻譯結果。",
        "translate_ja":"請將以下文字翻譯為日文。只輸出翻譯結果。",
        "translate_zh":"請將以下文字翻譯為繁體中文。只輸出翻譯結果。",
    }

    # 句尾語音控制詞 patterns。每個 pattern 寬鬆匹配（涵蓋常見口語表達），
    # 命中後切除尾段、改 mode='edit' + edit_context=<style>。
    _VOICE_COMMAND_PATTERNS = [
        # 翻譯類
        (re.compile(r"[，。、,.\s]*(以上|前面這段|這段)?[\s,]*(請[幫請])?[，。、,.\s]*(翻譯|翻成|改成|寫成|轉成)[\s]*(英文|英語)[\s。，！]*$"), "translate_en"),
        (re.compile(r"[，。、,.\s]*(以上|前面這段|這段)?[\s,]*(翻譯|翻成|改成|寫成)[\s]*(日文|日語|日本語)[\s。，！]*$"), "translate_ja"),
        (re.compile(r"[，。、,.\s]*(以上|前面這段|這段)?[\s,]*(翻譯|翻成|改成)[\s]*(繁中|繁體中文|中文)[\s。，！]*$"), "translate_zh"),
        # 風格改寫類
        (re.compile(r"[，。、,.\s]*(以上|前面這段|這段)?[\s,]*(改|改成|改為|寫成)[\s]*(正式|書面|商務)[\s。，！]*$"), "formal"),
        (re.compile(r"[，。、,.\s]*(以上|前面這段|這段)?[\s,]*(改|改成|改為|寫成)[\s]*(口語|輕鬆|休閒)[\s。，！]*$"), "casual"),
        (re.compile(r"[，。、,.\s]*(以上|前面這段|這段)?[\s,]*(精簡一下|改精簡|精簡|精簡點)[\s。，！]*$"), "concise"),
        (re.compile(r"[，。、,.\s]*(以上|前面這段|這段)?[\s,]*(寫成|改成)[\s]*(email|Email|郵件|電子郵件)[\s。，！]*$"), "email"),
        (re.compile(r"[，。、,.\s]*(以上|前面這段|這段)?[\s,]*(寫成|改成)[\s]*(技術文件|技術風格)[\s。，！]*$"), "technical"),
    ]

    def _detect_voice_command(self, text):
        """偵測句尾 meta-command。命中時回傳 (前段文字, style_key)；否則 (text, None)。
        ⚠️ 安全策略：要求前段文字 ≥ 8 字，避免「翻成英文」這 4 字當主內容時誤觸。"""
        if not self.config.get("enable_voice_commands", True):
            return text, None
        for pattern, style in self._VOICE_COMMAND_PATTERNS:
            m = pattern.search(text)
            if m:
                stripped = text[: m.start()].rstrip(" ，。、,.！？!?")
                if len(stripped) >= 8:
                    return stripped, style
        return text, None

    def _build_edit_prompt(self, cmd, original):
        return f"<original>{original}</original>\n<command>{cmd}</command>\nResult:"

    def _track_usage(self, source, model, input_tokens=0, output_tokens=0, seconds=0):
        # 統計寫檔丟到 daemon thread + 走 update_stats_atomic（與 update_stats 共用同一把鎖，不再 race）
        def _write():
            try:
                from config import update_stats_atomic
                from datetime import date
                month_key = date.today().strftime("%Y-%m")
                def _mutate(stats):
                    if "usage" not in stats: stats["usage"] = {}
                    if month_key not in stats["usage"]:
                        stats["usage"][month_key] = {"openai_input_tokens":0, "openai_output_tokens":0, "openai_whisper_seconds":0, "anthropic_input_tokens":0, "anthropic_output_tokens":0, "groq_input_tokens":0, "groq_output_tokens":0, "groq_whisper_seconds":0, "openrouter_input_tokens":0, "openrouter_output_tokens":0}
                    m = stats["usage"][month_key]
                    for f in ["openai_input_tokens", "openai_output_tokens", "openai_whisper_seconds", "anthropic_input_tokens", "anthropic_output_tokens", "groq_input_tokens", "groq_output_tokens", "groq_whisper_seconds", "openrouter_input_tokens", "openrouter_output_tokens"]:
                        if f not in m: m[f] = 0
                    if source == "openai": m["openai_input_tokens"]+=input_tokens; m["openai_output_tokens"]+=output_tokens; m["openai_whisper_seconds"]+=seconds
                    elif source == "anthropic": m["anthropic_input_tokens"]+=input_tokens; m["anthropic_output_tokens"]+=output_tokens
                    elif source == "groq": m["groq_input_tokens"]+=input_tokens; m["groq_output_tokens"]+=output_tokens; m["groq_whisper_seconds"]+=seconds
                    elif source == "openrouter": m["openrouter_input_tokens"]+=input_tokens; m["openrouter_output_tokens"]+=output_tokens
                update_stats_atomic(_mutate)
            except Exception: pass
        threading.Thread(target=_write, daemon=True).start()

    def get_service_status(self) -> dict:
        detector = self.ollama_detector
        if detector.status == OllamaStatus.UNKNOWN: detector.detect()
        return { **detector.get_status_dict(), "has_openai_key": bool(self.config.get("openai_api_key")), "has_anthropic_key": bool(self.config.get("anthropic_api_key")), "has_groq_key": bool(self.config.get("groq_api_key")), "has_openrouter_key": bool(self.config.get("openrouter_api_key")), "local_model": self.config.get("local_llm_model", "qwen3.5:latest"), "stt_engine": self.config.get("stt_engine", "mlx-whisper") }
