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


class Transcriber:
    # Metal GPU 鎖：序列化所有 mlx-whisper 呼叫，避免與 AppKit 的 Metal 渲染衝突
    _metal_lock = threading.Lock()

    def __init__(self, config, memory):
        self.config = config
        self.memory = memory
        self._openai = None
        self._anthropic = None
        # 繁中三層防護第三層：OpenCC s2twp（簡體→繁體台灣用語）
        try:
            from opencc import OpenCC
            self._opencc = OpenCC('s2twp')
        except ImportError:
            print(" ⚠️ opencc-python-reimplemented 未安裝，跳過繁中轉換")
            self._opencc = None
        # 預編譯填充詞正則，加速匹配
        self._filler_pattern = self._compile_filler_pattern()
        # Ollama timeout 退避：避免連續超時時每次都卡住並重複洗版 warning
        self._ollama_backoff_until = 0.0
        self._ollama_fail_count = 0
        # 聲紋驗證器
        self._voiceprint_mgr = VoiceprintManager()
        self._ollama_last_warn = 0.0

    def reset_clients(self):
        self._openai = None
        self._anthropic = None

    @property
    def oai(self):
        if self._openai is None:
            self._openai = openai.OpenAI(api_key=self.config.get("openai_api_key", "dummy"))
        return self._openai

    @property
    def claude(self):
        if self._anthropic is None:
            self._anthropic = anthropic.Anthropic(api_key=self.config.get("anthropic_api_key", "dummy"))
        return self._anthropic

    @property
    def ollama_detector(self):
        return get_detector()

    @property
    def local_llm(self):
        """Ollama 提供與 OpenAI 相容的 API 格式，URL 由偵測器決定"""
        detector = self.ollama_detector
        base_url = detector.base_url or "http://127.0.0.1:11434/v1"
        try:
            llm_timeout = float(self.config.get("local_llm_timeout_sec", 6.0))
        except (TypeError, ValueError):
            llm_timeout = 6.0
        llm_timeout = max(1.0, llm_timeout)

        # 如果 URL 變了（偵測器切換了位址），重建 client
        cached_url = getattr(self, '_local_llm_url', None)
        if not hasattr(self, '_local_llm_client') or self._local_llm_client is None or cached_url != base_url:
            self._local_llm_client = openai.OpenAI(
                base_url=base_url,
                api_key="ollama",  # 必須有值但會被忽略
                timeout=llm_timeout,
            )
            self._local_llm_url = base_url
        return self._local_llm_client

    def warmup(self):
        """序列預熱 mlx-whisper 模型和 Ollama Qwen，避免 Metal GPU 衝突"""
        def _warmup_whisper():
            try:
                # 等待 AppKit UI 完成初始化（NSVisualEffectView 使用 Metal GPU 渲染）
                # 避免與 mlx-whisper 的 Metal GPU inference 衝突導致：
                # AGXG14GFamilyCommandBuffer: A command encoder is already encoding
                import time as _time
                _time.sleep(3)

                import mlx_whisper
                # 產生 0.1 秒靜音音檔
                import tempfile
                import soundfile as sf
                silence = np.zeros(1600, dtype=np.float32)  # 0.1s @ 16kHz
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, silence, 16000)
                tmp.close()

                warmup_model_name = self.config.get("local_whisper_model", "mlx-community/whisper-turbo")
                warmup_model_path = LOCAL_MODEL_PATHS.get(warmup_model_name, warmup_model_name)
                warmup_kwargs = {
                    "path_or_hf_repo": warmup_model_path,
                    "language": "en",
                }
                if warmup_model_name in BREEZE_MODELS:
                    warmup_kwargs["fp16"] = True
                with Transcriber._metal_lock:
                    mlx_whisper.transcribe(tmp.name, **warmup_kwargs)
                import os
                os.unlink(tmp.name)
                print(" ✅ mlx-whisper 模型預熱完成")
            except Exception as e:
                print(f" ⚠️ mlx-whisper 預熱失敗: {e}")

        def _warmup_ollama():
            # Step 1: 偵測 Ollama 服務
            detector = self.ollama_detector
            status = detector.detect(force=True)

            if status != OllamaStatus.CONNECTED:
                env_info = detector.check_environment()
                print(f" ⚠️ Ollama 狀態: {status}")
                if env_info["issues"]:
                    for issue in env_info["issues"]:
                        print(f"    → {issue}")
                print(f"    → 將自動使用雲端 API 作為 LLM 後處理")
                return

            # Step 2: 偵測成功，預熱模型（首次載入模型需要較長時間）
            try:
                warmup_client = openai.OpenAI(
                    base_url=detector.base_url or "http://127.0.0.1:11434/v1",
                    api_key="ollama",
                    timeout=30.0,  # 模型首次載入可能需 5-15 秒
                )
                warmup_client.chat.completions.create(
                    model=self.config.get("local_llm_model", "qwen2.5:3b"),
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
                models = detector.available_models
                model_str = ", ".join(models[:5]) if models else "unknown"
                print(f" ✅ Ollama 預熱完成 (可用模型: {model_str})")
            except Exception as e:
                print(f" ⚠️ Ollama 預熱失敗: {e}")

        def _sequential_warmup():
            """序列執行：先偵測+預熱 Ollama（不用 GPU），再 Whisper（Metal GPU）"""
            _warmup_ollama()
            _warmup_whisper()

        t = threading.Thread(target=_sequential_warmup, daemon=True)
        t.start()
        # 不阻塞，讓預熱在背景完成

    def transcribe(self, audio_source, audio_duration=0, mode="dictate", edit_context=""):
        """
        完整處理管線。
        audio_source: 檔案路徑 (str) 或 音訊陣列 (np.ndarray)
        mode: dictate (一般輸入), edit (語音編輯), translate (翻譯)
        edit_context: 語音編輯時，被選取的原文
        """
        t0 = time.time()
        is_hybrid = self.config.get("enable_hybrid_mode", True) # 預設開啟 hybrid 以提升速度

        # Source tracking for Dashboard display
        stt_source = "none"   # "local" | "cloud" | "none"
        llm_source = "none"   # "local" | "cloud" | "skip" | "none"

        # Step 0: 音訊能量檢查（防止靜音送入 Whisper 產生幻覺）
        if isinstance(audio_source, np.ndarray):
            rms = np.sqrt(np.mean(audio_source ** 2))
            if rms < 0.003:  # 靜音閾值（Webcam 麥克風背景噪音約 0.001，正常說話 > 0.01）
                print(f" 🔇 音訊能量過低 (RMS={rms:.5f})，跳過辨識")
                return None

        # Step 0.5: 聲紋驗證（只接受已註冊聲紋的語音）
        if isinstance(audio_source, np.ndarray) and self.config.get("enable_voiceprint", False):
            if self._voiceprint_mgr.is_enrolled:
                vp_threshold = self.config.get("voiceprint_threshold", 0.97)
                vp_score = self._voiceprint_mgr.verify(audio_source)
                if vp_score < vp_threshold:
                    print(f" 🔇 聲紋不符 (score={vp_score:.4f} < {vp_threshold})，跳過辨識")
                    return None
                print(f" 🔐 聲紋驗證通過 (score={vp_score:.4f})")

        # Step 1: Whisper STT (Hybrid Routing)
        raw = None
        # 如果是 numpy 陣列或檔案路徑，優先嘗試 Local Whisper
        if is_hybrid and (isinstance(audio_source, np.ndarray) or audio_duration <= self.config.get("hybrid_audio_threshold", 15)):
            raw = self._local_stt(audio_source)
            if raw:
                stt_source = "local"
                print(f" ⚡ [Local Whisper 處理成功] 耗時: {time.time()-t0:.2f}s")
        
        # 若 Hybrid 失敗或音訊太長，Fallback 回 OpenAI API
        if not raw:
            # 如果 audio_source 是 numpy 陣列，先存成臨時 WAV 以供 OpenAI API 使用
            api_audio_path = audio_source if isinstance(audio_source, str) else None
            is_temp_file = False
            if api_audio_path is None and isinstance(audio_source, np.ndarray):
                try:
                    import tempfile
                    import soundfile as sf
                    sr = self.config.get("sample_rate", 16000)
                    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    sf.write(tmp.name, audio_source, sr)
                    tmp.close()
                    api_audio_path = tmp.name
                    is_temp_file = True
                except Exception as e:
                    print(f" ⚠️ 無法建立臨時音訊檔: {e}")
            
            if api_audio_path:
                raw = self._whisper(api_audio_path)
                if raw:
                    stt_source = "cloud"
                # 清理臨時檔
                if is_temp_file:
                    try:
                        import os
                        os.unlink(api_audio_path)
                    except Exception:
                        pass
            
        if not raw or not raw.strip():
            return None

        # 幻覺偵測：Whisper 靜音時容易產生重複文字
        raw_stripped = raw.strip()
        if len(raw_stripped) > 10:
            # 1) 單字元重複偵測：同一個字佔全文 70% 以上（如「整整整整整整整整...」）
            from collections import Counter
            char_counts = Counter(raw_stripped.replace(' ', ''))
            if char_counts:
                most_common_char, most_common_count = char_counts.most_common(1)[0]
                total_chars = sum(char_counts.values())
                if total_chars > 5 and most_common_count / total_chars > 0.7:
                    print(f" 🔇 偵測到 Whisper 幻覺（「{most_common_char}」重複 {most_common_count}/{total_chars} 次），跳過")
                    return None

            # 2) 逗號分隔重複偵測（如「嗯, 嗯, 嗯, 嗯, 嗯」）
            if len(raw_stripped) > 30:
                words = raw_stripped.replace('，', ',').replace('、', ',').split(',')
                words = [w.strip() for w in words if w.strip()]
                if len(words) >= 5:
                    unique = set(words)
                    if len(unique) <= 3:  # 5+ 個詞但只有 ≤3 種，明顯是幻覺
                        print(f" 🔇 偵測到 Whisper 幻覺（重複 {len(words)} 次），跳過")
                        return None

        # Step 2: 本地詞庫修正（含場景修正）
        scene = self.config.get("active_scene", "general")
        scene_data = SCENE_PRESETS.get(scene, {})
        corrected = self.memory.apply_corrections(raw, scene_data.get("corrections"))

        # Step 3: Smart Replace（觸發詞展開）
        corrected = self._apply_smart_replace(corrected)

        # Step 4: 偵測前景 App 場景風格
        app_style = detect_app_style(self.config)
        app_style_prompt = app_style.get("prompt", "")
        if app_style["style"] != "default":
            print(f" 🎯 [App Style] {app_style['app_name']} → {app_style['style']}")

        # Step 5: 後處理（潤稿/去填充詞/自我修正偵測/翻譯）
        final = None

        # 短句跳過 LLM：≤20 字且無填充詞，直接用詞庫修正結果，極速貼上
        skip_llm = False
        if mode == "dictate" and len(corrected) <= 20:
            skip_llm = not self._has_filler_words(corrected)
            if skip_llm:
                final = corrected
                llm_source = "skip"
                print(" ⚡ [短句跳過 LLM 後處理，極速模式]")

        if not skip_llm:
            # ──── LLM 路由：Local Ollama 優先 → Cloud Fallback ────
            # 有 Ollama 就先用（省 API 費用），1.5 秒超時後無感切換雲端
            has_anthropic = bool(self.config.get("anthropic_api_key"))
            has_openai = bool(self.config.get("openai_api_key"))

            should_polish = (
                self.config.get("enable_claude_polish")
                and (len(corrected) > 2 or mode in ("edit", "translate"))
            )

            if should_polish:
                # ── 優先順序 A: 本地 Ollama（1.5 秒超時）──
                if is_hybrid and mode == "dictate":
                    local_res = self._local_llm_process(corrected)
                    if local_res:
                        final = local_res
                        llm_source = "local"

                # ── 優先順序 B: Cloud Fallback（Local 失敗或不可用時）──
                if final is None and has_anthropic:
                    final = self._claude_process(corrected, mode, edit_context)
                    if final:
                        llm_source = "claude"
                    else:
                        print(" ⚠️ Claude 失敗，嘗試下一個 fallback")

                if final is None and has_openai:
                    final = self._openai_process(corrected, mode, edit_context)
                    if final:
                        llm_source = "openai"
                    else:
                        print(" ⚠️ OpenAI 失敗")

            # ── 最終 Fallback: 本地正則去填充詞 ──
            if final is None:
                final = corrected
                if self.config.get("enable_filler_removal"):
                    final = self._local_filler_removal(corrected)
                    llm_source = "regex"

        # 繁中三層防護第三層：OpenCC s2twp 轉換
        if self._opencc and final:
            final = self._opencc.convert(final)

        process_time = time.time() - t0

        # Build history entry
        entry = {
            "timestamp": datetime.now().isoformat(),
            "whisper_raw": raw,
            "corrected": corrected,
            "final_text": final,
            "mode": mode,
            "audio_duration": round(audio_duration, 1),
            "process_time": round(process_time, 2),
            "word_count": len(final.split()),
            "char_count": len(final),
            "stt_source": stt_source,    # "local" | "cloud"
            "llm_source": llm_source,    # "local" | "cloud" | "skip"
        }
        self.memory.add_to_history(entry)

        # 異步執行自動新詞萃取 (模仿 Typeless)
        if mode == "dictate":
            self._async_extract_keywords(final)

        return {
            "raw": raw,
            "corrected": corrected,
            "final": final,
            "process_time": process_time,
            "entry": entry,
        }

    def _async_extract_keywords(self, text):
        """非同步背景提取專有名詞與外文，加入自動詞庫。"""
        def task():
            try:
                if len(text) < 5: return
                import re
                # 提取長度 3 以上且包含字母的單字 (e.g. Firebase, Sendgrid, Genostar, stripe)
                words = re.findall(r'[A-Za-z][A-Za-z0-9\-]{2,}', text)
                
                # 常見的非關鍵字排除名單
                common = {
                    "the", "and", "that", "this", "with", "from", "your", "have", "you",
                    "for", "not", "are", "but", "all", "can", "out", "our", "has", "who", "get"
                }
                
                keywords = [w for w in set(words) if w.lower() not in common]
                
                for kw in keywords:
                    self.memory.add_auto_word(kw)
            except Exception as e:
                print(f" Keyword extraction failed: {e}")
                
        threading.Thread(target=task, daemon=True).start()

    def _whisper(self, audio_path):
        """Whisper API 語音轉文字 — 使用 custom_words prompt 提升三語辨識"""
        if not self.config.get("openai_api_key"):
            return None
        with open(audio_path, "rb") as f:
            kwargs = {
                "model": self.config.get("whisper_model", "whisper-1"),
                "file": f,
            }
            lang = self.config.get("language", "auto")
            if lang != "auto":
                kwargs["language"] = lang
            # 注入 custom_words + 場景詞彙 prompt 提升專有名詞辨識準確度
            scene = self.config.get("active_scene", "general")
            scene_words = SCENE_PRESETS.get(scene, {}).get("custom_words")
            prompt = self.memory.build_whisper_prompt(
                self.config.get("custom_words", []), scene_words=scene_words
            )
            if prompt:
                kwargs["prompt"] = prompt
            try:
                # Add timeout to avoid hanging on unstable network
                resp = self.oai.audio.transcriptions.create(**kwargs, timeout=10.0)
                # 追蹤 Whisper API 用量（按檔案估算秒數）
                try:
                    import os
                    file_size = os.path.getsize(audio_path)
                    # 粗估：16kHz mono 16bit WAV ≈ 32KB/s
                    est_seconds = file_size / 32000
                    self._track_whisper_usage(est_seconds)
                except Exception:
                    pass
                return resp.text
            except Exception as e:
                print(f"Whisper API error (timeout/network): {e}")
                return None

    def _local_stt(self, audio_source):
        """統一本地 STT 入口，根據 stt_engine 路由"""
        engine = self.config.get("stt_engine", "mlx-whisper")
        if engine == "cloud-only":
            return None  # 跳過本地 STT，直接用雲端 API
        if engine == "qwen3-asr":
            return self._qwen3_asr(audio_source)
        return self._local_whisper(audio_source)  # 預設 mlx-whisper

    def _qwen3_asr(self, audio_source):
        """Qwen3-ASR MLX 推論"""
        try:
            from mlx_qwen3_asr import transcribe as qwen3_transcribe
        except ImportError:
            print(" ⚠️ mlx-qwen3-asr 未安裝，fallback 到 mlx-whisper")
            print("    安裝方式：pip install mlx-qwen3-asr")
            return self._local_whisper(audio_source)
        try:
            # 如果 audio_source 是 numpy 陣列，先存成臨時 WAV
            audio_path = audio_source
            is_temp = False
            if isinstance(audio_source, np.ndarray):
                import tempfile
                import soundfile as sf
                sr = self.config.get("sample_rate", 16000)
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(tmp.name, audio_source, sr)
                tmp.close()
                audio_path = tmp.name
                is_temp = True

            with Transcriber._metal_lock:
                result = qwen3_transcribe(audio_path, model="Qwen/Qwen3-ASR-0.6B")

            # 清理臨時檔
            if is_temp:
                import os
                os.unlink(audio_path)

            # TranscriptionResult dataclass，.text 是轉錄文字
            return result.text
        except Exception as e:
            print(f" ⚠️ Qwen3-ASR 錯誤: {e}，fallback 到 mlx-whisper")
            return self._local_whisper(audio_source)

    def _local_whisper(self, audio_source):
        """使用 Mac 本地 mlx-whisper，支援傳入 numpy 陣列或路徑"""
        try:
            import mlx_whisper
            model_name = self.config.get("local_whisper_model", "mlx-community/whisper-turbo")
            # 解析模型路徑：短名稱 → 實際路徑
            model_path = LOCAL_MODEL_PATHS.get(model_name, model_name)
            is_breeze = model_name in BREEZE_MODELS

            kwargs = {
                "path_or_hf_repo": model_path,
                "temperature": 0.0,                     # 確定性輸出，greedy decoding
                "condition_on_previous_text": False,    # 不需要上下文，減少計算量
            }

            # Breeze-ASR-25 基於 whisper-large-v2（80 mel bins, fp16 推理）
            if is_breeze:
                kwargs["fp16"] = True

            lang = self.config.get("language", "auto")
            if lang != "auto":
                kwargs["language"] = lang
            # 三語引導前綴 + memory 的 custom_words/auto_added + 場景詞彙
            scene = self.config.get("active_scene", "general")
            scene_words = SCENE_PRESETS.get(scene, {}).get("custom_words")
            whisper_prompt = self.memory.build_whisper_prompt(
                self.config.get("custom_words", []), scene_words=scene_words
            )
            prefix = "繁體中文、日本語、English mixed conversation。"
            kwargs["initial_prompt"] = f"{prefix}{whisper_prompt}" if whisper_prompt else prefix

            # 使用 Metal GPU 鎖，序列化 GPU 存取避免 AppKit 衝突
            with Transcriber._metal_lock:
                result = mlx_whisper.transcribe(audio_source, **kwargs)
            return result.get("text", "")
        except ImportError:
            print(" ⚠️ mlx-whisper 未安裝，自動退回 OpenAI API")
            return None
        except Exception as e:
            print(f" ⚠️ Local Whisper 發生錯誤: {e}")
            return None

    def _local_llm_process(self, text):
        """使用本地 Ollama (Qwen) 進行去填充詞與潤稿（失敗時無感切換雲端）"""
        if not text.strip():
            return text
        # 近期已連續 timeout 時，暫停本地重試，直接走 fallback
        if time.time() < self._ollama_backoff_until:
            return None

        # 先確認 Ollama 是否可用（有快取，不會每次都偵測）
        detector = self.ollama_detector
        if detector.status == OllamaStatus.NOT_RUNNING:
            # 已知不可用，跳過嘗試直接回傳 None 觸發雲端 fallback
            return None

        # 如果狀態未知，快速偵測一次
        if detector.status == OllamaStatus.UNKNOWN:
            detector.detect()
            if detector.status != OllamaStatus.CONNECTED:
                return None

        system = (
            "語音辨識後處理。修正錯字、移除填充詞（嗯、啊、那個、えーと、um 等），"
            "務必加上標點符號：中文用全形（，。？！、：），日文用全形，英文用半形且後面空一格。"
            "長段落適當分段。只輸出修正後的文字，不加解釋。所有中文必須是繁體中文。"
        )
        # 注入場景額外 prompt
        scene = self.config.get("active_scene", "general")
        scene_extra = SCENE_PRESETS.get(scene, {}).get("system_prompt_extra", "")
        if scene_extra:
            system = system + "\n" + scene_extra
        # 注入 App 感知風格 prompt
        app_prompt = detect_app_style(self.config).get("prompt", "")
        if app_prompt:
            system = system + "\n" + app_prompt

        try:
            t0 = time.time()
            resp = self.local_llm.chat.completions.create(
                model=self.config.get("local_llm_model", "qwen2.5:3b"),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text}
                ],
                max_tokens=min(300, max(100, len(text) * 2)),
                temperature=0.1,
            )
            elapsed = time.time() - t0
            result = resp.choices[0].message.content.strip()
            self._ollama_fail_count = 0
            self._ollama_backoff_until = 0.0
            print(f" ⚡ [Local Ollama] 完成 ({elapsed:.2f}s)")
            return result
        except Exception as e:
            err_str = str(e).lower()
            if "connection" in err_str or "refused" in err_str or "timeout" in err_str or "timed out" in err_str:
                # 連線問題：退避一段時間，避免每次都卡 timeout
                self._ollama_fail_count = min(self._ollama_fail_count + 1, 6)
                cooldown = min(120, 5 * (2 ** (self._ollama_fail_count - 1)))
                self._ollama_backoff_until = time.time() + cooldown
                detector._last_check = 0  # 清除快取，下次觸發重新偵測
                now = time.time()
                if now - self._ollama_last_warn > 15:
                    print(f" ⚠️ Ollama 連線失敗，{cooldown}s 內改走雲端 API: {e}")
                    self._ollama_last_warn = now
            else:
                print(f" ⚠️ Local LLM 錯誤: {e}")
            return None

    # 固定的高效 system prompt（不從 config 讀取，避免使用者破壞品質）
    _DICTATE_SYSTEM = (
        "你是一個語音辨識後處理與文法檢查助手。規則：\n"
        "1. 語言判斷：自動判斷原文是中文、日文還是英文。絕對不要翻譯（例如英文不要翻成中文，日文不要翻成中文）。保持講者的原語言！\n"
        "2. 文法與語氣（Grammar & Tone）：修正明顯的文法錯誤、錯別字、不通順的語句，並優化語氣使其聽起來像母語人士的書面語或流暢口語。\n"
        "3. 刪除所有填充詞：嗯、啊、那個、就是、然後、對、欸、所以說、基本上、えーと、あの、えー、まあ、um、uh、like、you know、basically、actually 等\n"
        "4. 口語自我修正→只保留最終版本（例：不是A啦，我的意思是B→只留B）\n"
        "5. 標點符號必加：中文用全形標點（，。？！、：；），日文用全形標點，英文用半形標點且後面空一格。長篇大論適當分段，提升閱讀性。\n"
        "6. 多語混合時保持混合狀態，不要翻譯。\n"
        "7. 只輸出結果，不加任何解釋。"
    )

    def _openai_process(self, text, mode, edit_context=""):
        """OpenAI (GPT-4o) 後處理：介面與 _claude_process 相容"""
        if not text.strip():
            return text

        # 根據模式選擇 system prompt 和 user message
        if mode == "edit":
            system = "根據語音指令修改文字。只輸出修改結果。"
            user_msg = self._build_edit_prompt(text, edit_context)
        elif mode == "translate":
            system = "翻譯助手。只輸出翻譯結果。"
            user_msg = self._build_translate_prompt(text)
        else:
            system = self.config.get("claude_system_prompt", self._DICTATE_SYSTEM)
            # 注入場景額外 prompt
            scene = self.config.get("active_scene", "general")
            scene_extra = SCENE_PRESETS.get(scene, {}).get("system_prompt_extra", "")
            if scene_extra:
                system = system + "\n" + scene_extra
            # 注入 App 感知風格 prompt
            app_prompt = detect_app_style(self.config).get("prompt", "")
            if app_prompt:
                system = system + "\n" + app_prompt
            user_msg = f"[語音轉錄原文，請修正後直接輸出]\n{text}"

        try:
            resp = self.oai.chat.completions.create(
                model=self.config.get("openai_model", "gpt-4o"), # 預設使用 GPT-4o
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=min(2048, max(256, len(text) * 3)), # 長篇講話需要足夠空間加標點分段
                temperature=0.3,
                timeout=4.0  # Fast timeout for fallback
            )
            # 追蹤 TOKEN
            self._track_usage(resp, "openai")
            
            result = resp.choices[0].message.content.strip()

            # 安全檢查：偵測 LLM 自我介紹/回答模式
            if mode == "dictate" and self._is_llm_hallucination(result, text):
                print(f" ⚠️ LLM 回覆疑似自我介紹，改用原文")
                return text

            # 安全檢查：若回傳遠超原文（3倍以上），可能是 LLM 加了解釋
            if len(result) > len(text) * 3 and mode == "dictate":
                # 只取到合理長度的段落
                lines = result.split('\n')
                trimmed = []
                total = 0
                for line in lines:
                    total += len(line)
                    trimmed.append(line)
                    if total > len(text) * 2:
                        break
                return '\n'.join(trimmed).strip()
            return result
        except Exception as e:
            print(f"OpenAI Polish error: {e}")
            return None # Return None to trigger fallback

    def _claude_process(self, text, mode, edit_context=""):
        """Claude 後處理：去填充詞 + 自我修正偵測"""
        if not text.strip():
            return text

        # 根據模式選擇 system prompt 和 user message
        if mode == "edit":
            system = "根據語音指令修改文字。只輸出修改結果。"
            user_msg = self._build_edit_prompt(text, edit_context)
        elif mode == "translate":
            system = "翻譯助手。只輸出翻譯結果。"
            user_msg = self._build_translate_prompt(text)
        else:
            system = self.config.get("claude_system_prompt", self._DICTATE_SYSTEM)
            # 注入場景額外 prompt
            scene = self.config.get("active_scene", "general")
            scene_extra = SCENE_PRESETS.get(scene, {}).get("system_prompt_extra", "")
            if scene_extra:
                system = system + "\n" + scene_extra
            # 注入 App 感知風格 prompt
            app_prompt = detect_app_style(self.config).get("prompt", "")
            if app_prompt:
                system = system + "\n" + app_prompt
            user_msg = f"[語音轉錄原文，請修正後直接輸出]\n{text}"

        try:
            # max_tokens 按輸入長度給（加標點分段後可能比原文長，需足夠空間）
            estimated_tokens = min(2048, max(256, len(text) * 3))
            resp = self.claude.messages.create(
                model=self.config.get("claude_model", "claude-haiku-4-5-20251001"),
                max_tokens=estimated_tokens,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                timeout=4.0 # Fast timeout for fallback
            )
            self._track_usage(resp, "claude")
            result = resp.content[0].text.strip()

            # 安全檢查：偵測 LLM 自我介紹/回答模式（而非編輯模式）
            if mode == "dictate" and self._is_llm_hallucination(result, text):
                print(f" ⚠️ LLM 回覆疑似自我介紹，改用原文")
                return text

            # 安全檢查：若回傳遠超原文（3倍以上），可能加了解釋
            if len(result) > len(text) * 3 and mode == "dictate":
                lines = result.split('\n')
                trimmed = []
                total = 0
                for line in lines:
                    total += len(line)
                    trimmed.append(line)
                    if total > len(text) * 2:
                        break
                return '\n'.join(trimmed).strip()
            return result
        except Exception as e:
            print(f"Claude error: {e}")
            return None # Return None to trigger fallback

    # LLM 自我介紹/回答模式的特徵詞
    _HALLUCINATION_MARKERS = [
        "我已準備好", "我已经准备好", "我會幫您", "我来帮您",
        "以下是", "以下为", "請提供", "请提供",
        "我將按照", "我将按照", "確保：", "确保：",
        "為您修改如下", "为您修改如下",
        "I'm ready", "I'll help", "Here is", "Sure,",
        "I'm Claude", "I am Claude", "I'm an AI", "I am an AI",
        "as an AI", "AI assistant", "language model",
        "I appreciate your", "I should clarify",
        "お手伝い", "承知しました",
        "我是 Claude", "我是Claude", "作為 AI", "作為AI",
        "身為 AI", "身為AI", "語言模型",
    ]

    def _is_llm_hallucination(self, result, original_text):
        """偵測 LLM 是否進入「回答」模式而非「編輯/濃縮」模式"""
        # 1. 檢查開頭特徵詞（問候語/解釋語）
        startswith_markers = [
            "好的", "沒問題", "沒問題，", "了解", "了解，",
            "為您", "為您修改", "以下是", "已為您", "當然，", "沒錯", "沒錯，",
            "I appreciate", "I should clarify", "Thank you for",
            "As an AI", "As a language model",
        ]
        if any(result.startswith(m) for m in startswith_markers):
            return True

        # 2. 全文搜尋 AI 自我介紹特徵（這些不可能出現在正常口述中）
        ai_identity_markers = [
            "I'm Claude", "I am Claude", "I'm an AI", "I am an AI",
            "AI assistant made by", "language model",
            "我是 Claude", "我是Claude", "作為 AI", "身為 AI",
            "Anthropic", "OpenAI 開發",
        ]
        result_lower = result.lower()
        if any(m.lower() in result_lower for m in ai_identity_markers):
            return True

        # 3. 回覆比原文長 3 倍以上，可能是加了過多解釋
        if len(result) > len(original_text) * 3 and len(original_text) > 10:
            return True

        return False

    def _build_dictate_prompt(self, text):
        """一般聽寫模式 prompt — 精簡高效，減少 token 消耗"""
        # 只送必要的上下文，不送歷史和修正規則（浪費 token 且幫助不大）
        return text

    def _build_edit_prompt(self, spoken_command, original_text):
        """語音編輯模式 prompt（Typeless 的 Speak to Edit）"""
        return (
            f"使用者選取了以下文字：\n\n"
            f"「{original_text}」\n\n"
            f"使用者的語音指令：{spoken_command}\n\n"
            f"請根據語音指令修改選取的文字。只輸出修改後的結果。"
        )

    def _build_translate_prompt(self, text):
        """翻譯模式 prompt"""
        target = self.config.get("target_language", "en")
        lang_map = {
            "zh": "繁體中文", "ja": "日文", "en": "英文",
            "ko": "韓文", "fr": "法文", "de": "德文",
            "th": "泰文", "vi": "越南文", "id": "印尼文",
        }
        target_name = lang_map.get(target, target)
        return (
            f"請將以下語音辨識文字翻譯為{target_name}。\n"
            f"翻譯要自然流暢，像母語者寫的一樣。\n"
            f"只輸出翻譯結果，不要任何說明。\n\n"
            f"原文：{text}"
        )

    def _track_usage(self, response, source="claude"):
        """追蹤 API token 用量到 stats.json"""
        try:
            from config import load_stats, save_stats
            from datetime import date
            
            input_tokens = 0
            output_tokens = 0
            
            if source == "claude":
                input_tokens = getattr(response.usage, 'input_tokens', 0)
                output_tokens = getattr(response.usage, 'output_tokens', 0)
            elif source == "openai":
                input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                output_tokens = getattr(response.usage, 'completion_tokens', 0)

            stats = load_stats()
            if "usage" not in stats:
                stats["usage"] = {}
            month_key = date.today().strftime("%Y-%m")
            if month_key not in stats["usage"]:
                stats["usage"][month_key] = {
                    "claude_input_tokens": 0,
                    "claude_output_tokens": 0,
                    "claude_calls": 0,
                    "openai_input_tokens": 0,
                    "openai_output_tokens": 0,
                    "openai_calls": 0,
                    "whisper_seconds": 0,
                }
            m = stats["usage"][month_key]
            
            if source == "claude":
                m["claude_input_tokens"] += input_tokens
                m["claude_output_tokens"] += output_tokens
                m["claude_calls"] += 1
            elif source == "openai":
                if "openai_input_tokens" not in m: m["openai_input_tokens"] = 0
                if "openai_output_tokens" not in m: m["openai_output_tokens"] = 0
                if "openai_calls" not in m: m["openai_calls"] = 0
                m["openai_input_tokens"] += input_tokens
                m["openai_output_tokens"] += output_tokens
                m["openai_calls"] += 1

            save_stats(stats)
        except Exception:
            pass

    def _track_whisper_usage(self, audio_duration):
        """追蹤 Whisper API 使用秒數"""
        try:
            from config import load_stats, save_stats
            from datetime import date
            stats = load_stats()
            if "usage" not in stats:
                stats["usage"] = {}
            month_key = date.today().strftime("%Y-%m")
            if month_key not in stats["usage"]:
                stats["usage"][month_key] = {
                    "claude_input_tokens": 0,
                    "claude_output_tokens": 0,
                    "claude_calls": 0,
                    "whisper_seconds": 0,
                }
            stats["usage"][month_key]["whisper_seconds"] += audio_duration
            save_stats(stats)
        except Exception:
            pass

    def get_service_status(self) -> dict:
        """回傳當前各服務的狀態（供 Dashboard 狀態燈使用）"""
        detector = self.ollama_detector
        if detector.status == OllamaStatus.UNKNOWN:
            detector.detect()
        # 偵測 Qwen3-ASR 安裝狀態
        try:
            import mlx_qwen3_asr
            qwen3_installed = True
        except ImportError:
            qwen3_installed = False

        return {
            **detector.get_status_dict(),
            "has_openai_key": bool(self.config.get("openai_api_key")),
            "has_anthropic_key": bool(self.config.get("anthropic_api_key")),
            "hybrid_mode": self.config.get("enable_hybrid_mode", True),
            "local_model": self.config.get("local_llm_model", "qwen2.5:3b"),
            "stt_engine": self.config.get("stt_engine", "mlx-whisper"),
            "qwen3_asr_installed": qwen3_installed,
        }

    def _apply_smart_replace(self, text):
        """Layer 3: Smart Replace — 觸發詞展開（@mail→email 等）"""
        rules = load_smart_replace()
        for trigger, replacement in rules.items():
            if trigger in text:
                text = text.replace(trigger, replacement)
        return text

    def _compile_filler_pattern(self):
        """預編譯所有填充詞為單一正則表達式"""
        filler_words = self.config.get("filler_words", {})
        all_fillers = []
        for lang_fillers in filler_words.values():
            all_fillers.extend(lang_fillers)
        if not all_fillers:
            return None
        # 按長度降序排列，確保長詞優先匹配
        all_fillers.sort(key=len, reverse=True)
        pattern = "|".join(re.escape(f) for f in all_fillers)
        return re.compile(pattern)

    def _has_filler_words(self, text):
        """檢查文字中是否包含填充詞（使用預編譯正則）"""
        if self._filler_pattern is None:
            return False
        return bool(self._filler_pattern.search(text))

    def _local_filler_removal(self, text):
        """本地簡易去填充詞（不用 API 的 fallback）"""
        filler_words = self.config.get("filler_words", {})
        result = text
        for lang_fillers in filler_words.values():
            for filler in lang_fillers:
                # 移除獨立的填充詞（前後是空格或標點）
                pattern = r'(?<=[，。、！？\s])' + re.escape(filler) + r'(?=[，。、！？\s])'
                result = re.sub(pattern, '', result)
                # 移除句首填充詞
                if result.startswith(filler):
                    result = result[len(filler):].lstrip("，、 ")
        # 清理多餘空格
        result = re.sub(r'\s+', ' ', result).strip()
        result = re.sub(r'[，、]{2,}', '，', result)
        return result
