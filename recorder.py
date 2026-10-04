"""
recorder.py — 音訊錄製（支援 Push-to-Talk 和 Toggle 模式）
"""
import os
import tempfile
import threading
import time
import math
import numpy as np

try:
    import sounddevice as sd
    import soundfile as sf
except ImportError:
    sd = None
    sf = None


def normalize_audio_level(rms, noise_floor=0.001, speech_ceiling=0.12):
    """Map linear RMS to an ephemeral 0...1 waveform intensity."""
    try:
        value = float(rms)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value) or value <= noise_floor:
        return 0.0
    if value >= speech_ceiling:
        return 1.0
    return max(
        0.0,
        min(
            1.0,
            math.log(value / noise_floor)
            / math.log(speech_ceiling / noise_floor),
        ),
    )


class Recorder:
    def __init__(self, config):
        self.config = config
        self.is_recording = False
        self.audio_data = []
        self._thread = None
        self._stop_event = threading.Event()
        self._start_time = None
        self._segment_lock = threading.Lock()
        self._segment_condition = threading.Condition(self._segment_lock)
        # 序列化「動 PortAudio 全域/裝置狀態」的三個路徑：warm_up() 的
        # open+close、_reinit_portaudio() 的 terminate+initialize、以及真正
        # 錄音的 _open_input_stream()。Pa_Terminate() 會強制關閉所有仍開著
        # 的 stream——若跟另一個 thread 正在執行中的 Pa_OpenStream/Close
        # 重疊，是未定義行為（可能讓整個 PortAudio/process 掛掉）。用 RLock
        # 是因為 _open_input_stream() 失敗重試時會在持鎖狀態下呼叫
        # _reinit_portaudio()，需要同一 thread 可重入。見 warm_up() /
        # _reinit_portaudio() / _open_input_stream() 的個別註解。
        self._pa_lock = threading.RLock()
        self._pending_segments = 0
        self._next_segment_sequence = 0
        self._next_segment_to_deliver = 0
        # 最近一次串流錯誤（stream 開失敗 / read 中斷）。engine 在 stop 時讀取，
        # 用來把「為什麼沒錄到音訊」回報給使用者，而不是靜默丟棄。
        self.last_error = None
        self._on_error = None
        self._on_done = None
        self._on_level = None
        # hotkey→first-frame 延遲觀測（見 _record_loop / set_hotkey_press_ts）。
        self._first_frame_listener = None
        self._pending_hotkey_ts = None

    def set_level_listener(self, listener):
        """Receive normalized 0...1 levels; ``None`` disables feedback."""
        self._on_level = listener if callable(listener) else None

    def set_first_frame_listener(self, listener):
        """Receive ``elapsed_ms`` (float) — the time between the physical
        hotkey press (see ``set_hotkey_press_ts``) and the first audio frame
        actually captured for the recording that follows. ``None`` disables."""
        self._first_frame_listener = listener if callable(listener) else None

    def set_hotkey_press_ts(self, ts):
        """Stash the ``time.perf_counter()`` timestamp of the physical hotkey
        press that is about to trigger ``start()``, so ``_record_loop`` can
        report keydown→first-frame latency. Call this immediately before every
        ``start()`` — pass ``None`` for non-hotkey callers (CLI/Dashboard/menu
        click) so a stale timestamp from an earlier press is never reused.
        ``_record_loop`` consumes (and clears) this value once per recording."""
        self._pending_hotkey_ts = ts

    def _emit_level(self, level):
        callback = self._on_level
        if callback is None:
            return
        try:
            callback(max(0.0, min(1.0, float(level))))
        except Exception:
            # The meter is cosmetic and must never interrupt recording.
            pass

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
        # 消費（並清空）本段錄音的 hotkey keydown 時間戳，越早越好——thread
        # 排程本身的延遲也算在「hotkey 按下→第一個 audio frame」量測裡。
        # None（非熱鍵觸發，如 CLI/Dashboard）時完全跳過量測與 log。
        hotkey_ts = self._pending_hotkey_ts
        self._pending_hotkey_ts = None

        sr = self.config.get("sample_rate", 16000)
        max_dur = self.config.get("max_recording_duration", 1800)
        silence_threshold = self.config.get("silence_threshold", 0.001)
        silence_duration = self.config.get("silence_duration", 2.0)
        hotkey_mode = self.config.get("hotkey_mode", "push_to_talk")
        chunk = int(sr * 0.1)
        total = 0
        # 第一個 0.1s chunk 改用一次小 probe read 取樣，量測/回報用的「第一個
        # audio frame」時間點才不會被「湊滿 100ms 才回傳」的 blocking read
        # 拖慢（實測：同一支 InputStream，100ms read 平均 ~110ms 才返回，
        # 20ms read 平均 ~18ms；差額純粹是量測延遲，音訊本身早已在
        # PortAudio 的環狀緩衝區內、不會遺失，見 docs/recorder-ptt-latency.md）。
        # 0 或未設定 → 停用，退回單次 100ms read（相容既有行為 / 測試）。
        # ⚠️ 刻意不把預設值放這裡：DEFAULT_CONFIG（config.py）才是「正式產品
        # 預設」；這裡的 fallback=0 是給裸 dict config（測試/嵌入式呼叫端）
        # 用的保守預設，避免在沒有明確 opt-in 時改變既有 read() 呼叫次數。
        try:
            probe_ms = float(self.config.get("recorder_first_frame_probe_ms", 0) or 0)
        except (TypeError, ValueError):
            probe_ms = 0
        probe_frames = 0
        if probe_ms > 0:
            probe_frames = max(1, min(chunk - 1, int(round(sr * probe_ms / 1000))))
        # int(x / 0.1) 會因 IEEE-754 截斷（如 int(0.6/0.1)==5 不是 6）；
        # round() 讓「N 秒」實際換算成文件化語意的 chunk 數，不悄悄少一格。
        max_chunks = int(round(max_dur / 0.1))
        silence_chunks = int(round(silence_duration / 0.1))
        consecutive_silence = 0
        has_voice = False

        # PTT 靜音自停安全網（config.ptt_silence_autostop_seconds）。只在
        # push_to_talk 模式生效；0 / None / 非數字一律停用。刻意不要求
        # has_voice——它防的正是「按了 PTT 之後 key-release 事件整個遺失
        # （切 App / KVM）」，包含使用者根本還沒開口就切走的情況，這種
        # 情況 toggle 的 has_voice 閘門會讓安全網永遠不觸發。
        # 觸發條件重用下面迴圈裡與 toggle 共用的同一條 rms/consecutive_silence
        # 計數（不另外算一次）。只有這個明確原因可以呼叫 _on_done；一般 stop、
        # toggle 靜音、max duration 與 stream/read error 都不能誤走 PTT 自停送出路徑。
        ptt_silence_chunks = None
        ptt_silence_seconds_display = None
        ptt_autostopped = False
        if hotkey_mode == "push_to_talk":
            ptt_silence_raw = self.config.get("ptt_silence_autostop_seconds", 120)
            if ptt_silence_raw:
                try:
                    ptt_silence_seconds = float(ptt_silence_raw)
                except (TypeError, ValueError):
                    ptt_silence_seconds = 0
                if ptt_silence_seconds > 0:
                    ptt_silence_chunks = max(1, int(round(ptt_silence_seconds / 0.1)))
                    ptt_silence_seconds_display = ptt_silence_seconds

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
            self._emit_level(0.0)
            return

        stream_error = None
        try:
            # blocksize=chunk 讓 read 的 block 跟我們 loop 對齊，
            # 不會 buffer 太大導致 stop 後還要消化 1+s 殘留
            with stream:
                while not self._stop_event.is_set() and total < max_chunks:
                    try:
                        if total == 0 and probe_frames and probe_frames < chunk:
                            # 先讀一小段（predefined probe_frames），標記「第一個
                            # audio frame 已捕捉」的真實時間點，再讀完這個 0.1s
                            # chunk 剩下的部分；兩段合併後跟平常單次 100ms read
                            # 拿到的陣列逐 byte 相同，VAD/RMS/chunk 計數完全不變。
                            probe, _ = stream.read(probe_frames)
                            first_frame_ts = time.perf_counter()
                            try:
                                rest, _ = stream.read(chunk - probe_frames)
                            except sd.PortAudioError as e:
                                print(f" ⚠️ PortAudio read error: {e}")
                                stream_error = e
                                # probe 已經成功讀到、只有 remainder 這半段失敗
                                # ——已到手的音訊（往往就是使用者開口的第一個
                                # 字）不能因為後半段 read 出錯就被默默丟棄。
                                self.audio_data.append(probe.copy())
                                break
                            data = np.concatenate([probe, rest], axis=0)
                        else:
                            data, _ = stream.read(chunk)
                            if total == 0:
                                first_frame_ts = time.perf_counter()
                    except sd.PortAudioError as e:
                        print(f" ⚠️ PortAudio read error: {e}")
                        stream_error = e
                        break
                    if total == 0 and hotkey_ts is not None:
                        elapsed_ms = (first_frame_ts - hotkey_ts) * 1000
                        print(f" ⚡ hotkey→第一個 audio frame: {elapsed_ms:.0f}ms")
                        listener = self._first_frame_listener
                        if listener is not None:
                            try:
                                listener(elapsed_ms)
                            except Exception:
                                # 純觀測用途，絕不能打斷錄音。
                                pass
                    self.audio_data.append(data.copy())
                    total += 1

                    rms = float(np.sqrt(np.mean(data ** 2)))
                    self._emit_level(normalize_audio_level(rms))
                    if rms > silence_threshold:
                        has_voice = True
                        consecutive_silence = 0
                    else:
                        consecutive_silence += 1

                    if hotkey_mode == "toggle" and has_voice and consecutive_silence >= silence_chunks:
                        print(f" 🔇 靜音 {silence_duration}s，自動停止錄音")
                        break
                    if ptt_silence_chunks and consecutive_silence >= ptt_silence_chunks:
                        ptt_autostopped = True
                        print(
                            f" 🔇 PTT 連續靜音 {ptt_silence_seconds_display:.0f}s，"
                            "自動停止錄音（安全網，防 key-release 事件遺失）"
                        )
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
            self._emit_level(0.0)
            if stream_error is not None:
                self.last_error = f"音訊串流中斷: {stream_error}"
                # 串流死在半路通常是裝置被切換/拔除 — 刷新 PortAudio，
                # 讓「下一段」錄音能正常開啟，不用重啟 App。
                self._reinit_portaudio()

        if stream_error is not None:
            if self._on_error:
                try:
                    self._on_error(self.last_error)
                except Exception:
                    pass
            return

        if ptt_autostopped and self._on_done and self.audio_data:
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
        0 個 chunk，使用者只看到「錄音中…」之後毫無下文。

        latency 明確傳 'low'（可由 config 覆寫）：sounddevice 預設是
        'high'，會用裝置的 default_high_input_latency 排一顆較大的緩衝。
        實測（本機 webcam mic, 2026-09）：open()/start() 本身耗時不受影響，
        但緩衝越小，PortAudio 內部越早有資料可讀。"""
        kwargs = dict(
            samplerate=sr, channels=1, dtype="float32", blocksize=chunk,
            latency=self._resolve_input_latency(),
        )
        # 熱鍵路徑：非阻塞地確認 warm_up()/_reinit_portaudio() 有沒有正在動
        # PortAudio 全域狀態。平常這個鎖是空的，acquire 幾乎零成本，不拖慢
        # 熱鍵；只有真的被搶線（warm-up 剛好在跑）才等一個很短、有界的時間
        # ——warm_up() 的 open+close 沒有任何人工延遲，最壞情況只有 app 剛
        # 啟動的第一次冷啟動 open（實測 300-900ms）。寧可等這一下，也不要
        # 讓自己的 Pa_OpenStream 跟 _reinit_portaudio() 的 Pa_Terminate()（或
        # 另一個 warm-up 的 Pa_OpenStream）同時發生。拿不到鎖也不放棄開
        # 錄音——recording 優先權高於預熱，不能讓 warm-up 卡住使用者錄音。
        got_lock = self._pa_lock.acquire(timeout=0.05)
        try:
            try:
                return sd.InputStream(**kwargs)
            except sd.PortAudioError as e:
                print(f" ⚠️ InputStream 開啟失敗（{e}），重新初始化 PortAudio 後重試…")
                self._reinit_portaudio()
                return sd.InputStream(**kwargs)
        finally:
            if got_lock:
                self._pa_lock.release()

    def _resolve_input_latency(self):
        """讀取 config.recorder_input_latency（'low' | 'high'），非法值一律
        安全退回 'low' 並印出警告，不讓錄音因設定錯誤而開不了 stream。"""
        raw = self.config.get("recorder_input_latency", "low")
        if isinstance(raw, str) and raw.strip().lower() in ("low", "high"):
            return raw.strip().lower()
        print(f" ⚠️ recorder_input_latency 設定無效（{raw!r}），退回 'low'")
        return "low"

    def _reinit_portaudio(self):
        """刷新 PortAudio 裝置清單。只能在沒有任何 stream 開著時呼叫
        （Pa_Terminate 會強制關閉所有 stream）— 本 class 同時間只有一個
        錄音 thread，呼叫點都在 stream 已關閉/開啟失敗之後，安全。

        ⚠️ 但「本 thread 自己的 stream」安全，不代表跟*另一個* thread 的
        warm_up() 安全：warm_up_async() 會在背景 thread 呼叫 sd.InputStream()
        （見該方法），如果這裡的 sd._terminate() 跟它同時發生，等於在另一個
        thread 還在用 PortAudio 的全域/裝置狀態時把它整個拆掉——未定義行為，
        可能讓整個 PortAudio/process 掛掉。用 self._pa_lock 跟 warm_up() 互斥
        （blocking 等待可以接受：這條路徑本來就是 stream 開失敗/中斷後的
        錯誤復原，不是熱鍵路徑，warm_up() 的臨界區也很短）。

        Pa_Terminate/Pa_Initialize 會讓 process 對 coreaudiod 的連線回到
        「未熱身」狀態（見 warm_up() docstring 的實測數據）；重新初始化成功後
        補一次背景 warm-up，避免使用者下一次按熱鍵時重新吃到 cold-start
        的開流延遲。warm_up_async() 本身不啟動任何 stream（不會點亮麥克風
        使用指示），失敗也只是印警告，不影響裝置清單已刷新的結果。刻意在
        釋放鎖之後才呼叫（它會自己重新 acquire），避免新 warm-up thread 一
        啟動就卡在等鎖。"""
        ok = False
        with self._pa_lock:
            try:
                sd._terminate()
                sd._initialize()
                print(" 🔄 PortAudio 已重新初始化（音訊裝置清單已刷新）")
                ok = True
            except Exception as e:
                print(f" ⚠️ PortAudio 重新初始化失敗: {e}")
        if ok:
            self.warm_up_async()

    def warm_up(self):
        """預熱 PortAudio/CoreAudio 的裝置協商路徑，但**絕不啟動音訊擷取**。

        背景（2026-09 實測，見 docs/recorder-ptt-latency.md）：同一個
        process 內第一次 ``sd.InputStream(...)``（Pa_OpenStream）平均耗時
        300–900ms；之後每次重開只要 35–90ms。這個「冷啟動稅」只需要付一次
        （即使中間關閉 stream、隔數十秒再開，「熱」的狀態仍會保留），所以
        在 app 啟動時（或 PortAudio 被 _reinit_portaudio() 刷新後）主動
        open()+close() 一次可以把這筆成本從「使用者第一次按熱鍵」搬到
        「App 啟動當下」，且完全不需要保留一個常駐的 input stream：
        ``Pa_OpenStream`` 只協商格式/配置緩衝，並不會呼叫
        ``Pa_StartStream``（不會觸發 CoreAudio 的 IO engine），因此 macOS
        選單列的麥克風使用指示（橘點）不會被點亮，也不構成「idle 時持續
        開啟音訊輸入 stream」。

        Config: enable_recorder_prewarm（預設 True）關閉此行為；純粹
        best-effort，任何失敗都只印警告、不拋例外、不影響後續真正錄音
        （錄音路徑有自己完整的重試/自癒邏輯，見 _open_input_stream）。

        併發安全：跟真正錄音（_open_input_stream）與 _reinit_portaudio() 共用
        self._pa_lock。(a) 錄音已在進行/即將開始就直接跳過——沒有意義再開
        一個預熱用的 stream，而且會平白製造一次不必要的並行 Pa_OpenStream；
        (b) 用非阻塞 acquire，搶不到鎖（代表 _reinit_portaudio() 或另一個
        warm-up 正在動 PortAudio）就直接放棄本次——warm-up 本來就是
        best-effort，沒有任何一次呼叫非成功不可，不值得等待或製造競爭。"""
        if sd is None:
            return False
        if not self.config.get("enable_recorder_prewarm", True):
            return False
        if self.is_recording:
            return False
        if not self._pa_lock.acquire(blocking=False):
            return False
        try:
            # 拿到鎖之後再確認一次：拿鎖前到拿到鎖之間，錄音有可能剛好開始。
            if self.is_recording:
                return False
            stream = None
            try:
                sr = self.config.get("sample_rate", 16000)
                chunk = int(sr * 0.1)
                try:
                    stream = sd.InputStream(
                        samplerate=sr, channels=1, dtype="float32", blocksize=chunk,
                        latency=self._resolve_input_latency(),
                    )
                finally:
                    # close() 一定要嘗試：即使未來這裡在 open 之後、close 之前
                    # 插入新程式碼並拋例外，也不能讓 stream 停留在打開狀態。
                    if stream is not None:
                        try:
                            stream.close()
                        except Exception:
                            pass
                print(" 🔥 PortAudio 已預熱（未啟動串流，麥克風未啟用）")
                return True
            except Exception as e:
                print(f" ⚠️ PortAudio 預熱失敗（不影響正常錄音，下次熱鍵會正常重試開流）: {e}")
                return False
        finally:
            self._pa_lock.release()

    def warm_up_async(self):
        """warm_up() 的背景執行版本；呼叫端（app 啟動 / _reinit_portaudio）
        不應被這個 best-effort 動作卡住。"""
        threading.Thread(target=self.warm_up, daemon=True, name="recorder-warmup").start()

    def _save(self, audio_array=None):
        """儲存音訊檔（供 fallback 和 SSD 備份使用）。
        ⚠️ 檔名必須每段唯一：STT 改為優先讀 wav 後，固定檔名會讓並行轉寫互相
        覆寫/搬走音檔（A 還在上傳，B 的 stop() 覆寫同一檔 → A 轉出 B 的內容；
        或 A 的 _backup 把檔案 move 走 → B 的 STT 讀不到、音訊整段遺失）。"""
        if audio_array is None and not self.audio_data:
            return None
        fp = None
        try:
            audio = audio_array if audio_array is not None else np.concatenate(self.audio_data, axis=0).flatten()
            sr = self.config.get("sample_rate", 16000)
            if len(audio) < sr * 0.3:
                return None
            fd, fp = tempfile.mkstemp(prefix="voice_input_", suffix=".wav")
            try:
                if hasattr(os, "fchmod"):
                    os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
            sf.write(fp, audio, sr)
            os.chmod(fp, 0o600)
            return fp
        except Exception as e:
            if fp:
                try:
                    os.remove(fp)
                except OSError:
                    pass
            print(f"Save error: {e}")
            return None

    # ─── Continuous Mode (C) ─────────────────────────────
    def start_continuous(self, on_segment, on_voice_change=None, on_stopped=None):
        """連續錄音模式：麥克風長開，偵測 voice/silence 邊界，每完成一段呼叫
        on_segment(audio_array: np.ndarray, duration_sec: float)。
        on_voice_change(is_voice: bool) 用於 UI 狀態（可選）。
        on_stopped() 在 loop 結束（含例外死亡，如麥克風被拔）時必定呼叫 —
        讓 engine 重置狀態，否則 stream 例外死亡後 is_recording 永久卡 True，
        之後所有 push-to-talk 都被擋掉且無任何提示。
        防 PortAudio deadlock：與 start() 同樣的守門 — 若上一段 thread（不論是
        _record_loop 還是 _continuous_loop）還活著，會等最多 2s；超時就 raise，
        不硬開新 stream（否則 PA 會在 Pa_OpenStream 內 deadlock）。app.py 目前
        的呼叫路徑（start_continuous_mode / stop_continuous_mode）已經在呼叫前
        自行 join 過一次，這裡是給任何未來繞過那層紀律的呼叫者的第二道防線，
        對既有呼叫路徑而言應該永遠不會觸發。"""
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
        # int(x / 0.1) 會因 IEEE-754 截斷（如 int(0.6/0.1)==5 不是 6）；
        # round() 讓「N 秒」實際換算成文件化語意的 chunk 數，不悄悄少一格。
        silence_chunks = max(1, int(round(silence_duration / 0.1)))
        min_seg_chunks = max(1, int(round(min_seg_dur / 0.1)))
        max_seg_chunks = max(silence_chunks + 1, int(round(max_seg_dur / 0.1)))

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
            with self._segment_condition:
                if self._pending_segments >= max_pending:
                    print(f" ⚠️ continuous segment dropped: pending={self._pending_segments}")
                    seg_buffer = []
                    return
                sequence = self._next_segment_sequence
                self._next_segment_sequence += 1
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
                    # STT latency varies by segment.  Independent callbacks would let a
                    # later, shorter segment paste before an earlier slow one.  Tickets
                    # keep user-visible delivery chronological while the pending cap
                    # continues to keep the VAD thread non-blocking.
                    with self._segment_condition:
                        while sequence != self._next_segment_to_deliver:
                            self._segment_condition.wait()
                    on_segment(audio_array, duration)
                except Exception as exc:
                    # A callback failure must not become an unhandled daemon-thread
                    # exception or permanently block every later sequence ticket.
                    print(f"Continuous segment callback error: {exc}")
                finally:
                    with self._segment_condition:
                        self._next_segment_to_deliver += 1
                        self._pending_segments = max(0, self._pending_segments - 1)
                        self._segment_condition.notify_all()
            threading.Thread(
                target=_run_segment, daemon=True
            ).start()

        try:
            with self._open_input_stream(sr, chunk) as stream:
                while not self._stop_event.is_set():
                    data, _ = stream.read(chunk)
                    rms = float(np.sqrt(np.mean(data ** 2)))
                    self._emit_level(normalize_audio_level(rms))
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
            self._emit_level(0.0)
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
