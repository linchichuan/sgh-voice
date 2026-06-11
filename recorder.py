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

    def start(self, on_done=None):
        """開始錄音。
        防 PortAudio deadlock：若上一段 _record_loop thread 還活著（stream 沒收完），
        會等最多 2s；超時就 raise，由 caller 決定怎麼處理（不要硬開新 stream，否則 PA
        會在 Pa_OpenStream 內 deadlock，整個 audio 子系統就鎖死）。"""
        if self.is_recording:
            return
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
        self._start_time = time.time()

        self._thread = threading.Thread(target=self._record_loop, daemon=True, name="recorder")
        self._thread.start()

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
            # blocksize=chunk 讓 read 的 block 跟我們 loop 對齊，
            # 不會 buffer 太大導致 stop 後還要消化 1+s 殘留
            with sd.InputStream(samplerate=sr, channels=1, dtype="float32",
                                blocksize=chunk) as stream:
                while not self._stop_event.is_set() and total < max_chunks:
                    try:
                        data, _ = stream.read(chunk)
                    except sd.PortAudioError as e:
                        print(f" ⚠️ PortAudio read error: {e}")
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
        except Exception as e:
            print(f" Recording error: {e}")
        finally:
            # 確保旗標被重置，即使 stream 開失敗 / read 拋 exception 也一樣
            self.is_recording = False

        if self._on_done and self.audio_data:
            filepath = self._save()
            duration = time.time() - self._start_time if self._start_time else 0
            if filepath:
                self._on_done(filepath, duration)

    def _save(self, audio_array=None):
        """儲存音訊檔（供 fallback 和 SSD 備份使用）"""
        if audio_array is None and not self.audio_data:
            return None
        try:
            audio = audio_array if audio_array is not None else np.concatenate(self.audio_data, axis=0).flatten()
            sr = self.config.get("sample_rate", 16000)
            if len(audio) < sr * 0.3:
                return None
            fp = os.path.join(tempfile.gettempdir(), "voice_input_rec.wav")
            sf.write(fp, audio, sr)
            return fp
        except Exception as e:
            print(f"Save error: {e}")
            return None

    # ─── Continuous Mode (C) ─────────────────────────────
    def start_continuous(self, on_segment, on_voice_change=None):
        """連續錄音模式：麥克風長開，偵測 voice/silence 邊界，每完成一段呼叫
        on_segment(audio_array: np.ndarray, duration_sec: float)。
        on_voice_change(is_voice: bool) 用於 UI 狀態（可選）。"""
        if self.is_recording:
            return False
        if sd is None:
            raise RuntimeError("請安裝 sounddevice: pip install sounddevice soundfile")
        self.is_recording = True
        self._stop_event.clear()
        self._start_time = time.time()
        self._thread = threading.Thread(
            target=self._continuous_loop,
            args=(on_segment, on_voice_change),
            daemon=True,
        )
        self._thread.start()
        return True

    def _continuous_loop(self, on_segment, on_voice_change):
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

        def _flush_segment():
            """送出當前 buffer，回呼 on_segment（背景執行）。"""
            nonlocal seg_buffer
            if len(seg_buffer) < min_seg_chunks + silence_chunks:
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
            # 削掉尾端大部分靜音，留 200ms 緩衝供 ASR 吃
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
            with sd.InputStream(samplerate=sr, channels=1, dtype="float32",
                                blocksize=chunk) as stream:
                while not self._stop_event.is_set():
                    data, _ = stream.read(chunk)
                    rms = float(np.sqrt(np.mean(data ** 2)))
                    is_voice = rms > silence_threshold

                    if is_voice:
                        if not in_voice:
                            in_voice = True
                            if on_voice_change:
                                try: on_voice_change(True)
                                except Exception: pass
                        seg_buffer.append(data.copy())
                        consecutive_silence = 0
                        # 強制切片：太長就先送出避免 Whisper 太重
                        if len(seg_buffer) >= max_seg_chunks:
                            _flush_segment()
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
                # 結束時還有 buffer 就最後送一次
                if in_voice and seg_buffer:
                    _flush_segment()
        except Exception as e:
            print(f"Continuous recording error: {e}")
        finally:
            self.is_recording = False

    @staticmethod
    def list_devices():
        if sd is None:
            return []
        devices = sd.query_devices()
        return [{"id": i, "name": d["name"], "channels": d["max_input_channels"]}
                for i, d in enumerate(devices) if d["max_input_channels"] > 0]
