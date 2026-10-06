"""Single-flight Windows recording lifecycle with local-only recognition.

The existing Recorder and the offline CPU transcriber provide speech IO. This
module owns only desktop lifecycle, cancellation and delivery policy.
"""
from __future__ import annotations

import os
from pathlib import Path
import queue
import threading
import time

WINDOWS_DEFAULTS = {
    "windows_language": "ja",
    "windows_lexicon_enabled": False,
    "windows_save_history": False,
    "windows_auto_insert": False,
    "windows_toggle_hotkey": "Ctrl+Alt+F9",
    "windows_cancel_hotkey": "Ctrl+Alt+F10",
}


def runtime_config(settings):
    """Strip cloud credentials and force local-only execution, even for old settings."""
    result = dict(settings)
    result.update({
        "stt_engine": "faster-whisper-local",
        "llm_engine": "disabled",
        "enable_claude_polish": False,
        "enable_hybrid_mode": False,
        "allow_cross_provider_llm_fallback": False,
        "enable_fewshot": False,
        "enable_app_awareness": False,
        "enable_voiceprint": False,
        "enable_voice_commands": False,
        "enable_auto_learn": False,
        "active_scene": "general",
        "backup_audio_dir": "",
        "sample_rate": 16000,
        # UI is toggle; Recorder's PTT mode supplies a silence safety cutoff.
        "hotkey_mode": "push_to_talk",
        "max_recording_duration": 180,
        "ptt_silence_autostop_seconds": 120,
    })
    for name in ("groq", "openai", "anthropic", "openrouter", "elevenlabs"):
        result[f"{name}_api_key"] = ""
    result["windows_cloud_consent"] = False
    # The bundled model is Japanese-only; old multilingual settings cannot override it.
    result["windows_language"] = "ja"
    return result


def _installed_model():
    from windows_client.local_stt import validate_model_directory
    from windows_client.models import verified_model_dir
    return validate_model_directory(verified_model_dir())


def _new_memory(retain, cancelled):
    if not retain:
        return None
    from memory import Memory

    class WindowsMemory(Memory):
        def add_to_history(self, entry):
            if retain and not cancelled():
                super().add_to_history(entry)

    memory = WindowsMemory()
    return memory


class Controller:
    def __init__(self, config, on_event, native=None, *, recorder_factory=None,
                 transcriber_factory=None, memory_factory=None, model_locator=None):
        self.config = {**WINDOWS_DEFAULTS, **config}
        self._emit_callback = on_event
        self.native = native
        self._recorder_factory = recorder_factory
        self._transcriber_factory = transcriber_factory
        self._memory_factory = memory_factory or _new_memory
        self._model_locator = model_locator
        self._model_dir = None
        self._model_error = "model_missing"
        self._decode_options = {}
        self._transcriber = None
        self._transcriber_key = None
        self._lock = threading.RLock()
        self._cancelled = threading.Event()
        self._commands = queue.Queue()
        self._closed = False
        self._recorder = None
        self._capture_open = False
        self._session = 0
        self._target = None
        self.state = "idle"
        self.last_text = ""
        self._worker = threading.Thread(target=self._work, daemon=True, name="windows-voice")
        self._worker.start()
        # Verify the installed model off the UI thread before the first recording.
        self._set_state("verifying_model")
        self._commands.put((self._verify_model, self._session))

    def _emit(self, event, payload):
        try:
            self._emit_callback(event, payload)
        except Exception:
            pass  # A destroyed view must not prevent microphone/file cleanup.

    def _set_state(self, state):
        self.state = state
        self._emit("status", state)

    @property
    def model_ready(self):
        return self._model_dir is not None

    def apply_config(self, config):
        with self._lock:
            if self.state != "idle" or self._closed:
                raise RuntimeError("busy")
            self.config = {**WINDOWS_DEFAULTS, **config}

    def toggle(self, target=None):
        with self._lock:
            if self._closed:
                return False
            if self.state == "recording":
                self._set_state("stopping")
                self._commands.put((self._finish, self._session))
                return True
            if self.state != "idle":
                return False
            if self._model_dir is None:
                self._emit("error", self._model_error)
                return False
            self._session += 1
            self._cancelled.clear()
            self.last_text = ""
            self._target = target
            self._snapshot = runtime_config(self.config)
            self._snapshot["windows_model_dir"] = str(self._model_dir)
            self._snapshot["windows_decode_options"] = dict(self._decode_options)
            self._set_state("recording")
            self._commands.put((self._start, self._session))
            return True

    def _verify_model(self, session):
        """Locate and hash-check the installed model; never downloads anything."""
        from windows_client.models import MANIFEST, ModelIntegrityError
        try:
            path = (self._model_locator or _installed_model)()
            with self._lock:
                self._model_dir = path
                self._decode_options = dict(MANIFEST.get("decode", {}))
        except ModelIntegrityError as exc:
            self._model_error = exc.code
            self._emit("error", exc.code)
        except Exception as exc:
            self._model_error = getattr(exc, "code", None) or "model_invalid"
            self._emit("error", self._model_error)
        finally:
            with self._lock:
                if not self._closed:
                    self._set_state("idle")

    def import_file(self, path):
        """Transcribe a chosen WAV/MP3 recording; preview only, never auto-inserted."""
        with self._lock:
            if self._closed or self.state != "idle":
                return False
            if self._model_dir is None:
                self._emit("error", self._model_error)
                return False
            self._session += 1
            self._cancelled.clear()
            self.last_text = ""
            self._target = None
            self._snapshot = runtime_config(self.config)
            self._snapshot["windows_model_dir"] = str(self._model_dir)
            self._snapshot["windows_decode_options"] = dict(self._decode_options)
            self._set_state("importing")
            self._commands.put((lambda session: self._import(session, str(path)), self._session))
            return True

    def _import(self, session, source):
        import shutil
        import tempfile
        from windows_client.audio_import import AudioImportError, convert_to_pcm16k
        folder = tempfile.mkdtemp(prefix="sghvoice-import-")
        progress = lambda fraction: self._emit("file_progress", {"percent": int(max(0.0, min(1.0, fraction)) * 100)})
        try:
            wav = Path(folder) / "import.wav"
            try:
                duration = convert_to_pcm16k(source, wav, should_cancel=self._cancelled.is_set,
                                             on_progress=lambda f: progress(0.1 * f))
            except AudioImportError as exc:
                if exc.code != "cancelled" and not self._cancelled.is_set():
                    self._emit("error", exc.code)
                return
            with self._lock:
                self._set_state("processing")
            transcriber = self._get_transcriber(None)
            result = transcriber.transcribe(
                {"path": str(wav)}, duration, "file", should_cancel=self._cancelled.is_set,
                on_progress=lambda f: progress(0.1 + 0.9 * f))
            with self._lock:
                if self._cancelled.is_set() or self._closed:
                    return
                if not result or not result.get("final"):
                    self._emit("error", "transcription_failed")
                    return
                self.last_text = result["final"]
                progress(1.0)
                self._emit("result", {"text": self.last_text, "source": "file",
                                      "insertion": {"success": False, "reason": "preview_only"},
                                      "lexicon_candidates": self._lexicon(self.last_text)})
        finally:
            shutil.rmtree(folder, ignore_errors=True)
            with self._lock:
                if not self._closed:
                    self._set_state("idle")

    def _get_transcriber(self, memory):
        if self._transcriber_factory is None:
            from windows_client.local_stt import LocalTranscriber
            self._transcriber_factory = LocalTranscriber
        model_key = (self._snapshot.get("windows_model_dir"), self._snapshot.get("windows_language"))
        if self._transcriber is None or self._transcriber_key != model_key:
            self._transcriber = self._transcriber_factory(self._snapshot, memory)
            self._transcriber_key = model_key
        return self._transcriber

    def _lexicon(self, text):
        if not self._snapshot.get("windows_lexicon_enabled"):
            return []
        from dataclasses import asdict
        from windows_client.lexicon import suggestions
        return [asdict(item) for item in suggestions(text)]

    def cancel(self):
        with self._lock:
            self._cancelled.set()
            self.last_text = ""
            if self.state == "recording":
                self._set_state("stopping")
                self._commands.put((self._discard, self._session))

    def close(self):
        with self._lock:
            if self._closed:
                return
            self.cancel()
            self._closed = True
            self._commands.put(None)

    def _work(self):
        while True:
            command = self._commands.get()
            if command is None:
                self._set_state("closed")
                return
            try:
                action, session = command
                if session != self._session:
                    continue
                action(session)
            except Exception as exc:
                # Never expose provider exception text, audio or credential data.
                from windows_client.local_stt import LocalSTTError
                self._emit("error", exc.code if isinstance(exc, LocalSTTError) else "transcription_failed")
                self._discard(self._session)

    def _start(self, session):
        if self._cancelled.is_set():
            return
        if self._recorder_factory is None:
            from recorder import Recorder
            self._recorder_factory = Recorder
        # Reuse the Recorder: its start guard owns the previous PortAudio
        # thread and refuses a new stream until that thread has terminated.
        if self._recorder is None:
            self._recorder = self._recorder_factory(self._snapshot)
        recorder = self._recorder
        recorder.config = self._snapshot
        recorder.set_level_listener(lambda value: self._emit("level", value))
        try:
            if recorder.start(on_error=lambda _message: self._recording_error(session)) is False:
                raise RuntimeError("microphone_failed")
            self._capture_open = True
        except Exception:
            self._emit("error", "microphone_failed")
            self._cancelled.set()
            self._discard(session)
            return
        threading.Thread(target=self._watch_recorder, args=(recorder, session), daemon=True).start()

    def _recording_error(self, session):
        with self._lock:
            if session != self._session:
                return
            self._emit("error", "microphone_failed")
            self.cancel()

    def _watch_recorder(self, recorder, session):
        # Recorder stops itself at the silence/time limit; finalize exactly once.
        while True:
            time.sleep(0.1)
            with self._lock:
                if session != self._session or self.state != "recording":
                    return
                if not recorder.is_recording:
                    self._set_state("stopping")
                    self._commands.put((self._finish, self._session))
                    return

    @staticmethod
    def _remove(path):
        if path:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def _take_recording(self):
        recorder = self._recorder
        if recorder is None or not self._capture_open:
            return None, None, 0
        audio, path, duration = recorder.stop()
        self._capture_open = False
        capture_thread = getattr(recorder, "_thread", None)
        if capture_thread is not None and capture_thread.is_alive():
            self._remove(path)
            self._emit("error", "microphone_failed")
            return None, None, 0
        return audio, path, duration

    def _discard(self, session):
        path = None
        try:
            _audio, path, _duration = self._take_recording()
        finally:
            self._remove(path)
            self._emit("level", 0.0)
            with self._lock:
                self._set_state("idle")

    def _finish(self, session):
        path = None
        try:
            audio, path, duration = self._take_recording()
            if self._cancelled.is_set():
                return
            if not path:
                self._emit("error", "audio_unavailable")
                return
            with self._lock:
                self._set_state("processing")
            memory = self._memory_factory(
                bool(self._snapshot.get("windows_save_history", False)),
                self._cancelled.is_set,
            )
            transcriber = self._get_transcriber(memory)
            result = transcriber.transcribe(
                {"array": audio, "path": path}, duration, "dictate",
                should_cancel=self._cancelled.is_set,
            )
            with self._lock:
                if self._cancelled.is_set() or self._closed:
                    return
                if not result or result.get("error") or not result.get("final"):
                    self._emit("error", "transcription_failed")
                    return
                self.last_text = result["final"]
                candidates = self._lexicon(self.last_text)
                if self._snapshot.get("windows_save_history"):
                    from datetime import datetime
                    memory.add_to_history({"timestamp": datetime.now().isoformat(),
                                           "whisper_raw": self.last_text, "final_text": self.last_text,
                                           "mode": "dictate", "duration": duration,
                                           "stt_engine": "faster-whisper-local", "llm_source": None})
                insertion = {"success": False, "reason": "preview_only"}
                if self._snapshot.get("windows_auto_insert") and self._target and self.native:
                    try:
                        delivered = self.native.send_text(self._target, self.last_text)
                        insertion = {"success": delivered.success, "reason": delivered.reason}
                    except Exception:
                        insertion = {"success": False, "reason": "input_failed"}
                self._emit("result", {"text": self.last_text, "insertion": insertion,
                                      "lexicon_candidates": candidates})
        finally:
            self._remove(path)
            self._emit("level", 0.0)
            with self._lock:
                self._set_state("idle")
