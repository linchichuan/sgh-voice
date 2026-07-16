"""
recorder.py — 音訊錄製（支援 Push-to-Talk 和 Toggle 模式）
"""
import os
import tempfile
import threading
import time
import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
except ImportError:
    sd = None
    sf = None


class Recorder:
    def __init__(self, config):
        self.config = config
        self.is_recording = False
        self.audio_data = []
        self._thread = None
        self._stop_event = threading.Event()
        self._start_time = None
        self._segment_lock = threading.Lock()
        self._pending_segments = 0
        # 最近一次串流錯誤（stream 開失敗 / read 中斷）。engine 在 stop 時讀取，
        # 用來把「為什麼沒錄到音訊」回報給使用者，而不是靜默丟棄。
        self.last_error = None
        self._on_error = None
        self._on_done = None

    def start(self, on_done=None, on_error=None):
        """開始錄音。
        on_error(msg)：stream 開啟失敗（重試後仍失敗）時從 recorder thread 回呼，
        讓 engine 立刻重置狀態 + 顯示錯誤，而不是等使用者 stop 後才發現沒錄到。
        防 PortAudio deadlock：若上一段 _record_loop thread 還活著（stream 沒收完），
        會等最多 2s；超時就 raise，由 caller 決定怎麼處理（不要硬開新 stream，否則 PA
        會在 Pa_OpenStream 內 deadlock，整個 audio 子系統就鎖死）。"""
        if self.is_recording:
            return False
        if sd is None:
            raise RuntimeError("請安裝 sounddevice: pip install sounddevice soundfile")

        # 等上一段 thread 完全結束（含 InputStream 的 __exit__ tear-down）
        if self._thread is not None and self._thread.is_alive():
            print(" ⚠️ 上一段錄音 thread 尚未結束（PortAudio 可能還在收尾），等 2s…")
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                raise RuntimeError(
                    "上一段 audio stream 未釋放 — 拒絕開新錄音以防 PortAudio deadlock。"
                    "請重啟 app。"
                )

        self.is_recording = True
        self.audio_data = []
        self._stop_event.clear()
        self._on_done = on_done
        self._on_error = on_error
        self.last_error = None
        self._start_time = time.time()

        self._thread = threading.Thread(target=self._record_loop, daemon=True, name="recorder")
        try:
            self._thread.start()
        except Exception:
            # Thread never became a usable stream.  Roll back Recorder itself
            # so Engine cleanup does not inherit a false busy state.
            self.is_recording = False
            self._start_time = None
            self._thread = None
            self.audio_data = []
            raise
        return True

    def stop(self):
        """停止錄音，回傳 (音訊數據, 音訊檔路徑, 錄音秒數)。
        thread.join 設長 timeout（5s），不夠就明確 log 但不假裝成功 — 否則下次 start
        會踩到還活著的 thread → 由 start() 那邊偵測 + raise。"""
        if not self._start_time:
            return None, None, 0
        self._stop_event.set()
        self.is_recording = False
        duration = time.time() - self._start_time if self._start_time else 0
        if self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                # PortAudio 卡住沒有乾淨辦法強殺 daemon thread；
                # 留 thread reference，下次 start() 會偵測 + 拒絕
                print(f" ⚠️ recorder thread 未在 5s 內結束（PortAudio 可能 stuck）")
        self._start_time = None

        audio_array = None
        if self.audio_data:
            audio_array = np.concatenate(self.audio_data, axis=0).flatten()

        filepath = self._save(audio_array)
        # 釋放每個 100ms chunk 的 list/array 參考；後續流程只需要 audio_array 或 wav 檔。
        self.audio_data = []
        return audio_array, filepath, duration

    def _record_loop(self):
        sr = self.config.get("sample_rate", 16000)
        max_dur = self.config.get("max_recording_duration", 1800)
        silence_threshold = self.config.get("silence_threshold", 0.001)
        silence_duration = self.config.get("silence_duration", 2.0)
        hotkey_mode = self.config.get("hotkey_mode", "push_to_talk")
        chunk = int(sr * 0.1)
        total = 0
        max_chunks = int(max_dur / 0.1)
        silence_chunks = int(silence_duration / 0.1)
        consecutive_silence = 0
        has_voice = False

        try:
            stream = self._open_input_stream(sr, chunk)
        except Exception as e:
            # 開 stream 失敗（含重新初始化後重試仍失敗）→ 立刻通知 engine，
            # 否則 engine 的 is_recording 卡 True、使用者 stop 後音訊是空的且毫無提示。
            self.last_error = f"麥克風串流開啟失敗: {e}"
            print(f" ⚠️ {self.last_error}")
            self.is_recording = False
            if self._on_error:
                try: self._on_error(self.last_error)
                except Exception: pass
            return

        stream_error = None
        try:
            # blocksize=chunk 讓 read 的 block 跟我們 loop 對齊，
            # 不會 buffer 太大導致 stop 後還要消化 1+s 殘留
            with stream:
                while not self._stop_event.is_set() and total < max_chunks:
                    try:
                        data, _ = stream.read(chunk)
                    except sd.PortAudioError as e:
                        print(f" ⚠️ PortAudio read error: {e}")
                        stream_error = e
                        break
                    self.audio_data.append(data.copy())
                    total += 1

                    rms = np.sqrt(np.mean(data ** 2))
                    if rms > silence_threshold:
                        has_voice = True
                        consecutive_silence = 0
                    else:
                        consecutive_silence += 1

                    if hotkey_mode == "toggle" and has_voice and consecutive_silence >= silence_chunks:
                        print(f" 🔇 靜音 {silence_duration}s，自動停止錄音")
                        break
        except sd.PortAudioError as e:
            print(f" ⚠️ PortAudio stream error: {e}")
            stream_error = e
        except Exception as e:
            print(f" Recording error: {e}")
            stream_error = e
        finally:
            # 確保旗標被重置，即使 stream 開失敗 / read 拋 exception 也一樣
            self.is_recording = False
            if stream_error is not None:
                self.last_error = f"音訊串流中斷: {stream_error}"
                # 串流死在半路通常是裝置被切換/拔除 — 刷新 PortAudio，
                # 讓「下一段」錄音能正常開啟，不用重啟 App。
                self._reinit_portaudio()

        if self._on_done and self.audio_data:
            filepath = self._save()
            duration = time.time() - self._start_time if self._start_time else 0
            if filepath:
                self._on_done(filepath, duration)

    def _open_input_stream(self, sr, chunk):
        """開啟 InputStream；失敗時重新初始化 PortAudio 後重試一次。
        macOS 睡眠喚醒或切換輸入裝置（AirPods / 外接麥克風拔插）後，
        PortAudio 內部的裝置清單會過期 — 之後每次 Pa_OpenStream 都失敗且
        永遠不會自癒，唯一解法是 Pa_Terminate + Pa_Initialize 刷新。
        2026-06-13 實際案例：app 長跑 + 凌晨裝置變更後，每段錄音都收到
        0 個 chunk，使用者只看到「錄音中…」之後毫無下文。"""
        kwargs = dict(samplerate=sr, channels=1, dtype="float32", blocksize=chunk)
        try:
            return sd.InputStream(**kwargs)
        except sd.PortAudioError as e:
            print(f" ⚠️ InputStream 開啟失敗（{e}），重新初始化 PortAudio 後重試…")
            self._reinit_portaudio()
            return sd.InputStream(**kwargs)

    def _reinit_portaudio(self):
        """刷新 PortAudio 裝置清單。只能在沒有任何 stream 開著時呼叫
        （Pa_Terminate 會強制關閉所有 stream）— 本 class 同時間只有一個
        錄音 thread，呼叫點都在 stream 已關閉/開啟失敗之後，安全。"""
        try:
            sd._terminate()
            sd._initialize()
            print(" 🔄 PortAudio 已重新初始化（音訊裝置清單已刷新）")
        except Exception as e:
            print(f" ⚠️ PortAudio 重新初始化失敗: {e}")

    def _save(self, audio_array=None):
        """儲存音訊檔（供 fallback 和 SSD 備份使用）。
        ⚠️ 檔名必須每段唯一：STT 改為優先讀 wav 後，固定檔名會讓並行轉寫互相
        覆寫/搬走音檔（A 還在上傳，B 的 stop() 覆寫同一檔 → A 轉出 B 的內容；
        或 A 的 _backup 把檔案 move 走 → B 的 STT 讀不到、音訊整段遺失）。"""
        if audio_array is None and not self.audio_data:
            return None
        try:
            audio = audio_array if audio_array is not None else np.concatenate(self.audio_data, axis=0).flatten()
            sr = self.config.get("sample_rate", 16000)
            if len(audio) < sr * 0.3:
                return None
            fp = os.path.join(tempfile.gettempdir(), f"voice_input_{time.time_ns()}.wav")
            sf.write(fp, audio, sr)
            return fp
        except Exception as e:
            print(f"Save error: {e}")
            return None

    # ─── Continuous Mode (C) ─────────────────────────────
    def start_continuous(self, on_segment, on_voice_change=None, on_stopped=None):
        """連續錄音模式：麥克風長開，偵測 voice/silence 邊界，每完成一段呼叫
        on_segment(audio_array: np.ndarray, duration_sec: float)。
        on_voice_change(is_voice: bool) 用於 UI 狀態（可選）。
        on_stopped() 在 loop 結束（含例外死亡，如麥克風被拔）時必定呼叫 —
        讓 engine 重置狀態，否則 stream 例外死亡後 is_recording 永久卡 True，
        之後所有 push-to-talk 都被擋掉且無任何提示。"""
        if self.is_recording:
            return False
        if sd is None:
            raise RuntimeError("請安裝 sounddevice: pip install sounddevice soundfile")
        self.is_recording = True
        self._stop_event.clear()
        self.last_error = None
        self._start_time = time.time()
        self._thread = threading.Thread(
            target=self._continuous_loop,
            args=(on_segment, on_voice_change, on_stopped),
            daemon=True,
        )
        try:
            self._thread.start()
        except Exception:
            self.is_recording = False
            self._start_time = None
            self._thread = None
            raise
        return True

    def _continuous_loop(self, on_segment, on_voice_change, on_stopped=None):
        sr = self.config.get("sample_rate", 16000)
        silence_threshold = self.config.get("silence_threshold", 0.001)
        silence_duration = float(self.config.get("continuous_silence_duration", 1.5))
        min_seg_dur = float(self.config.get("continuous_min_segment_duration", 0.6))
        max_seg_dur = float(self.config.get("continuous_max_segment_duration", 30.0))
        chunk = int(sr * 0.1)
        silence_chunks = max(1, int(silence_duration / 0.1))
        min_seg_chunks = max(1, int(min_seg_dur / 0.1))
        max_seg_chunks = max(silence_chunks + 1, int(max_seg_dur / 0.1))

        seg_buffer = []
        consecutive_silence = 0
        in_voice = False
        # pre-roll ring buffer：起音的弱輔音/氣音常低於 RMS 閾值（100-300ms），
        # 沒有 pre-roll 時句首字會被剪掉，Whisper 漏字。voice onset 時 prepend 進 buffer。
        from collections import deque
        preroll = deque(maxlen=3)  # 3 chunks = 300ms

        def _flush_segment(has_trailing_silence=True):
            """送出當前 buffer，回呼 on_segment（背景執行）。
            has_trailing_silence：buffer 尾端是否帶有靜音 chunk —
            - 靜音切片（VAD 邊界）→ True：尾端有 silence_chunks 個靜音可裁
            - max 強制切片 / stop 最後 flush → False：buffer 全是語音，
              照裁會切掉 1.3 秒正在講的話；最短長度檢查也不該加計 silence_chunks
              （否則 stop 前最後一句 < 2.1s 整段被丟，與設定的 0.6s 下限不符）。"""
            nonlocal seg_buffer
            required = min_seg_chunks + (silence_chunks if has_trailing_silence else 0)
            if len(seg_buffer) < required:
                seg_buffer = []
                return
            max_pending = max(1, int(self.config.get("continuous_max_pending_segments", 2)))
            with self._segment_lock:
                if self._pending_segments >= max_pending:
                    print(f" ⚠️ continuous segment dropped: pending={self._pending_segments}")
                    seg_buffer = []
                    return
                self._pending_segments += 1
            audio_array = np.concatenate(seg_buffer, axis=0).flatten()
            # 削掉尾端大部分靜音，留 200ms 緩衝供 ASR 吃（僅在尾端真的是靜音時）
            if has_trailing_silence:
                tail_keep = int(sr * 0.2)
                tail_cut = max(0, silence_chunks * chunk - tail_keep)
                if tail_cut > 0:
                    audio_array = audio_array[:-tail_cut] if tail_cut < len(audio_array) else audio_array
            seg_buffer = []
            duration = len(audio_array) / sr
            def _run_segment():
                try:
                    on_segment(audio_array, duration)
                finally:
                    with self._segment_lock:
                        self._pending_segments = max(0, self._pending_segments - 1)
            threading.Thread(
                target=_run_segment, daemon=True
            ).start()

        try:
            with self._open_input_stream(sr, chunk) as stream:
                while not self._stop_event.is_set():
                    data, _ = stream.read(chunk)
                    rms = float(np.sqrt(np.mean(data ** 2)))
                    is_voice = rms > silence_threshold

                    if is_voice:
                        if not in_voice:
                            in_voice = True
                            # 把 pre-roll（起音前 300ms）prepend 進段落，保住句首弱輔音
                            if preroll:
                                seg_buffer.extend(preroll)
                                preroll.clear()
                            if on_voice_change:
                                try: on_voice_change(True)
                                except Exception: pass
                        seg_buffer.append(data.copy())
                        consecutive_silence = 0
                        # 強制切片：太長就先送出避免 Whisper 太重
                        # （buffer 全是語音，不可裁尾 → has_trailing_silence=False）
                        if len(seg_buffer) >= max_seg_chunks:
                            _flush_segment(has_trailing_silence=False)
                            in_voice = False
                            if on_voice_change:
                                try: on_voice_change(False)
                                except Exception: pass
                    else:
                        if in_voice:
                            seg_buffer.append(data.copy())
                            consecutive_silence += 1
                            if consecutive_silence >= silence_chunks:
                                _flush_segment()
                                in_voice = False
                                consecutive_silence = 0
                                if on_voice_change:
                                    try: on_voice_change(False)
                                    except Exception: pass
                        else:
                            preroll.append(data.copy())
                # 結束時還有 buffer 就最後送一次（尾端沒有靜音可裁）
                if in_voice and seg_buffer:
                    _flush_segment(has_trailing_silence=False)
        except Exception as e:
            print(f"Continuous recording error: {e}")
            self.last_error = f"連續錄音串流中斷: {e}"
            # 同 _record_loop：串流死亡多半是裝置變更，刷新讓下一次能重開
            self._reinit_portaudio()
        finally:
            self.is_recording = False
            # 通知 engine：loop 已結束（正常 stop 或例外死亡都要通知，
            # 否則 engine 端 _continuous_active / is_recording 永久卡死）
            if on_stopped:
                try: on_stopped()
                except Exception: pass

    @staticmethod
    def list_devices():
        if sd is None:
            return []
        devices = sd.query_devices()
        return [{"id": i, "name": d["name"], "channels": d["max_input_channels"]}
                for i, d in enumerate(devices) if d["max_input_channels"] > 0]
