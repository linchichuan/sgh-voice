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
from config import load_smart_replace


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
    def local_llm(self):
        """Ollama 提供與 OpenAI 相容的 API 格式"""
        if not hasattr(self, '_local_llm_client') or self._local_llm_client is None:
            self._local_llm_client = openai.OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama"  # 必須有值但會被忽略
            )
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

                with Transcriber._metal_lock:
                    mlx_whisper.transcribe(
                        tmp.name,
                        path_or_hf_repo="mlx-community/whisper-turbo",
                        language="en",
                    )
                import os
                os.unlink(tmp.name)
                print(" ✅ mlx-whisper 模型預熱完成")
            except Exception as e:
                print(f" ⚠️ mlx-whisper 預熱失敗: {e}")

        def _warmup_ollama():
            try:
                # 發送簡單請求讓 Ollama 載入模型到記憶體
                self.local_llm.chat.completions.create(
                    model=self.config.get("local_llm_model", "qwen2.5:3b"),
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
                print(" ✅ Ollama Qwen 模型預熱完成")
            except Exception as e:
                print(f" ⚠️ Ollama 預熱失敗 (可忽略如未安裝): {e}")

        def _sequential_warmup():
            """序列執行：先 Ollama（不用 GPU），再 Whisper（Metal GPU）"""
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
            if rms < 0.005:  # 靜音閾值
                print(f" 🔇 音訊能量過低 (RMS={rms:.5f})，跳過辨識")
                return None

        # Step 1: Whisper STT (Hybrid Routing)
        raw = None
        # 如果是 numpy 陣列或檔案路徑，優先嘗試 Local Whisper
        if is_hybrid and (isinstance(audio_source, np.ndarray) or audio_duration <= self.config.get("hybrid_audio_threshold", 15)):
            raw = self._local_whisper(audio_source)
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
        if len(raw_stripped) > 30:
            # 檢查是否有連續重複片段（典型幻覺模式）
            words = raw_stripped.replace('，', ',').replace('、', ',').split(',')
            words = [w.strip() for w in words if w.strip()]
            if len(words) >= 5:
                unique = set(words)
                if len(unique) <= 3:  # 5+ 個詞但只有 ≤3 種，明顯是幻覺
                    print(f" 🔇 偵測到 Whisper 幻覺（重複 {len(words)} 次），跳過")
                    return None

        # Step 2: 本地詞庫修正
        corrected = self.memory.apply_corrections(raw)

        # Step 3: Smart Replace（觸發詞展開）
        corrected = self._apply_smart_replace(corrected)

        # Step 4: 後處理（潤稿/去填充詞/自我修正偵測/翻譯）
        final = corrected

        # 短句跳過 LLM：≤20 字且無填充詞，直接用詞庫修正結果，極速貼上
        skip_llm = False
        if mode == "dictate" and len(corrected) <= 20:
            skip_llm = not self._has_filler_words(corrected)
            if skip_llm:
                llm_source = "skip"
                print(" ⚡ [短句跳過 LLM 後處理，極速模式]")

        if not skip_llm:
            # 優先順序：Claude (~1.5s) > Local Qwen (fallback) > 本地正則
            # Claude 比 Qwen 快 7 倍且品質更好，所以 Claude 優先
            # 優先順序：Claude > OpenAI > Local Qwen > 本地正則
            # 如果使用者只設定了 OpenAI Key，則自動切換為 OpenAI 處理
            has_anthropic = bool(self.config.get("anthropic_api_key"))
            has_openai = bool(self.config.get("openai_api_key"))
            
            should_polish = (
                self.config.get("enable_claude_polish") # 沿用此開關作為 "是否啟用 AI 潤稿"
                and (len(corrected) > 2 or mode in ("edit", "translate"))
            )

            if should_polish and has_anthropic:
                final = self._claude_process(corrected, mode, edit_context)
                llm_source = "claude"
                if final is None:  # Fallback if Claude fails/times out
                    print(" ⚠️ Claude timeout/error, switching to Local Fallback")
                    final = None # Reset to trigger local logic below
                    llm_source = "none"

            elif should_polish and has_openai:
                final = self._openai_process(corrected, mode, edit_context)
                llm_source = "openai"
                if final is None:
                    print(" ⚠️ OpenAI timeout/error, switching to Local Fallback")
                    final = None
                    llm_source = "none"

            # Fallback Logic: If cloud failed (final is None) or wasn't tried, and hybrid/local is enabled
            if final is None: 
                # Reset final to corrected text before trying local
                final = corrected
                if is_hybrid:
                    # API 均不可用或失敗時，fallback 到本地 Qwen
                    local_res = self._local_llm_process(corrected)
                    if local_res:
                        final = local_res
                        llm_source = "local"
                        print(" ⚡ [Local Qwen fallback 處理成功]")
                    elif self.config.get("enable_filler_removal"):
                        final = self._local_filler_removal(corrected)
                        llm_source = "local"
                elif self.config.get("enable_filler_removal"):
                    final = self._local_filler_removal(corrected)
                    llm_source = "local"

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

        return {
            "raw": raw,
            "corrected": corrected,
            "final": final,
            "process_time": process_time,
            "entry": entry,
        }

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
            # 注入 custom_words prompt 提升專有名詞辨識準確度
            prompt = self.memory.build_whisper_prompt(
                self.config.get("custom_words", [])
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

    def _local_whisper(self, audio_source):
        """使用 Mac 本地 mlx-whisper，支援傳入 numpy 陣列或路徑"""
        try:
            import mlx_whisper
            kwargs = {
                "path_or_hf_repo": self.config.get("local_whisper_model", "mlx-community/whisper-turbo"),
                "temperature": 0.0,                     # 確定性輸出，greedy decoding
                "condition_on_previous_text": False,    # 不需要上下文，減少計算量
            }
            lang = self.config.get("language", "auto")
            if lang != "auto":
                kwargs["language"] = lang
            # 三語引導前綴 + memory 的 custom_words/auto_added
            whisper_prompt = self.memory.build_whisper_prompt(
                self.config.get("custom_words", [])
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
        """使用本地 Ollama (Qwen) 進行簡易去填充詞與潤稿"""
        if not text.strip():
            return text
        
        system = (
            "你是語音辨識文字修正助手。請修正錯字、移除口語填充詞（嗯、啊、那個等），"
            "並只輸出修正後的最終文字，絕不加入任何解釋或問候語。"
        )
        
        user_msg = f"請修正這段語音辨識文字：\n{text}"
        
        try:
            resp = self.local_llm.chat.completions.create(
                model=self.config.get("local_llm_model", "qwen2.5:3b"),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg}
                ],
                max_tokens=150,
                temperature=0.1
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f" ⚠️ Local LLM 發生錯誤 (確認 Ollama 是否開啟): {e}")
            return None

    # 固定的高效 system prompt（不從 config 讀取，避免使用者破壞品質）
    _DICTATE_SYSTEM = (
        "語音辨識後處理。規則：\n"
        "1. 刪除所有填充詞：嗯、啊、那個、就是、然後、對、欸、所以說、基本上、えーと、あの、えー、まあ、um、uh、like、you know、basically、actually、so yeah、I mean\n"
        "2. 刪除冗餘詞：這個、那個（非必要指代時）、就是說、我想說一下\n"
        "3. 口語自我修正→只保留最終版本（例：不是A啦，我的意思是B→只留B）\n"
        "4. 標點與段落：請務必加上正確的標點符號（逗號、句號、問號等），並將長篇大論適當分段，提升閱讀性。\n"
        "5. 不要改寫核心句子結構，保持講者的原意與語氣\n"
        "6. 多語混合保持原樣\n"
        "7. 只輸出結果，不加任何解釋"
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
            # 優先使用 config 中的 claude_system_prompt (其實是通用的 system prompt)
            system = self.config.get("claude_system_prompt", self._DICTATE_SYSTEM)
            user_msg = text

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
            # 讀取 config 中的 prompt
            system = self.config.get("claude_system_prompt", self._DICTATE_SYSTEM)
            user_msg = text  # 直接送原文

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
        "お手伝い", "承知しました",
    ]

    def _is_llm_hallucination(self, result, original_text):
        """偵測 LLM 是否進入「回答」模式而非「編輯/濃縮」模式"""
        # 檢查特徵詞：只檢查字串「開頭」是否有明顯的問候語或解釋語。
        # 不使用全句 in 搜尋，避免誤殺正常的濃縮總結。
        startswith_markers = [
            "好的", "沒問題", "沒問題，", "了解", "了解，",
            "為您", "為您修改", "以下是", "已為您", "當然，", "沒錯", "沒錯，"
        ]
        if any(result.startswith(m) for m in startswith_markers):
            return True
            
        # 回覆比原文長 3 倍以上，可能是加了過多解釋
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
