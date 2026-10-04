"""Single-flight Windows recording lifecycle, with explicit cloud consent.

The existing Recorder and Transcriber remain the speech implementation. This
module owns only desktop lifecycle, cancellation and delivery policy.
"""
from __future__ import annotations

import os
import queue
import threading
import time

WINDOWS_DEFAULTS = {
    "windows_provider": "groq",
    "windows_cloud_consent": False,
    "windows_polish": True,
    "windows_save_history": False,
    "windows_auto_insert": False,
    "windows_toggle_hotkey": "Ctrl+Alt+F9",
    "windows_cancel_hotkey": "Ctrl+Alt+F10",
}


def runtime_config(settings):
    """Constrain shared routing to the one provider explicitly selected here."""
    result = dict(settings)
    provider = result.get("windows_provider", "groq")
    if provider not in ("groq", "openai"):
        raise ValueError("invalid_provider")
    result.update({
        "stt_engine": "groq" if provider == "groq" else "cloud-only",
        "llm_engine": provider,
        "enable_claude_polish": bool(result.get("windows_polish", True)),
        "enable_hybrid_mode": False,
        "allow_cross_provider_llm_fallback": False,
        "enable_fewshot": False,
        "enable_app_awareness": False,
        "enable_voiceprint": False,
        "enable_voice_commands": False,
        "enable_auto_learn": False,
        "active_scene": "general",
        "backup_audio_dir": "",
        # UI is toggle; Recorder's PTT mode supplies a silence safety cutoff.
        "hotkey_mode": "push_to_talk",
        "max_recording_duration": 180,
        "ptt_silence_autostop_seconds": 120,
    })
    for name in ("groq", "openai", "anthropic", "openrouter", "elevenlabs"):
        if name != provider:
            result[f"{name}_api_key"] = ""
    return result


def _new_memory(retain, cancelled):
    from memory import Memory

    class WindowsMemory(Memory):
        def add_to_history(self, entry):
            if retain and not cancelled():
                super().add_to_history(entry)

    memory = WindowsMemory()
    if not retain:
        memory.history = []
    return memory


class Controller:
    def __init__(self, config, on_event, native=None, *, recorder_factory=None,
                 transcriber_factory=None, memory_factory=None):
        self.config = {**WINDOWS_DEFAULTS, **config}
        self._emit_callback = on_event
        self.native = native
        self._recorder_factory = recorder_factory
        self._transcriber_factory = transcriber_factory
        self._memory_factory = memory_factory or _new_memory
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

    def _emit(self, event, payload):
        try:
            self._emit_callback(event, payload)
        except Exception:
            pass  # A destroyed view must not prevent microphone/file cleanup.

    def _set_state(self, state):
        self.state = state
        self._emit("status", state)

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
            if self.config.get("windows_cloud_consent") is not True:
                self._emit("error", "cloud_consent_required")
                return False
            provider = self.config.get("windows_provider")
            if provider not in ("groq", "openai"):
                self._emit("error", "invalid_provider")
                return False
            if not str(self.config.get(f"{provider}_api_key", "")).strip():
                self._emit("error", "api_key_required")
                return False
            self._session += 1
            self._cancelled.clear()
            self.last_text = ""
            self._target = target
            self._snapshot = runtime_config(self.config)
            self._set_state("recording")
            self._commands.put((self._start, self._session))
            return True

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
            except Exception:
                # Never expose provider exception text, audio or credential data.
                self._emit("error", "transcription_failed")
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
            if self._transcriber_factory is None:
                from transcriber import Transcriber
                self._transcriber_factory = Transcriber
            transcriber = self._transcriber_factory(self._snapshot, memory)
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
                insertion = {"success": False, "reason": "preview_only"}
                if self._snapshot.get("windows_auto_insert") and self._target and self.native:
                    try:
                        delivered = self.native.send_text(self._target, self.last_text)
                        insertion = {"success": delivered.success, "reason": delivered.reason}
                    except Exception:
                        insertion = {"success": False, "reason": "input_failed"}
                self._emit("result", {"text": self.last_text, "insertion": insertion})
        finally:
            self._remove(path)
            self._emit("level", 0.0)
            with self._lock:
                self._set_state("idle")
