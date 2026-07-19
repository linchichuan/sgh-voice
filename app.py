#!/usr/bin/env python3
"""
app.py — Voice Input 主程式
macOS 選單列常駐 + Web Dashboard + 全域快捷鍵

使用方式:
    python app.py              # 選單列 + Dashboard
    python app.py --cli        # 純 CLI 模式
    python app.py --dashboard  # 只開 Dashboard
"""
import sys
import os

# 模型快取指向外接 SSD（Ollama 由 .zshrc 的 OLLAMA_MODELS 管理）
if not os.environ.get("HF_HOME") and os.path.isdir("/Volumes/Satechi_SSD/huggingface"):
    os.environ["HF_HOME"] = "/Volumes/Satechi_SSD/huggingface"

import subprocess
import threading
import tempfile
import locale
import signal
import atexit
import event_ledger
from multilingual import (
    convert_traditional_preserving_japanese,
    resolve_output_language_hint,
)
from hotkey_config import (
    FN_KEYCODE,
    HOTKEY_FIELDS,
    MODIFIER_KEYCODES,
    RECOMMENDED_RECORD_HOTKEY,
    HotkeyValidationError,
    modifier_is_pressed,
    parse_hotkey,
)
from text_insertion import (
    accessibility_is_trusted,
    capture_pasteboard,
    insert_text_via_accessibility,
    pasteboard_change_count_matches,
    request_accessibility_prompt,
    restore_pasteboard,
    schedule_pasteboard_restore,
    stage_text_on_pasteboard,
)


_active_engines = []
_ACTION_HOTKEY_FIELDS = tuple(
    field for field in HOTKEY_FIELDS if field != "hotkey"
)


def _resource_path(*parts):
    """Resolve bundled PyInstaller resources and source-tree assets uniformly."""

    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def _register_engine_for_cleanup(engine):
    if engine not in _active_engines:
        _active_engines.append(engine)


def _graceful_shutdown(signum=None, frame=None):
    """Ctrl+C / SIGTERM 時把錄音串流乾淨收掉並刷出 memory pending writes。"""
    for engine in _active_engines:
        try:
            rec = getattr(engine, "recorder", None)
            if rec and getattr(rec, "is_recording", False):
                rec._stop_event.set()
                rec.is_recording = False
                thr = getattr(rec, "_thread", None)
                if thr and thr.is_alive():
                    thr.join(timeout=2)
        except Exception:
            pass
        # 防禦性 flush：正常路徑已逐筆原子落盤，這裡涵蓋未來可能的批次寫入。
        try:
            mem = getattr(engine, "memory", None)
            if mem and hasattr(mem, "flush_history"):
                mem.flush_history()
        except Exception:
            pass
    if signum is not None:
        # 收到訊號時再用預設行為退出，讓 shell exit code 正確
        sys.exit(0)

# ─── 系統語言偵測 ─────────────────────────────────────────
def get_sys_lang():
    """獲取系統語系群組 (ja, zh, en)"""
    try:
        # macOS 優先檢查環境變數或 locale
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

def get_i18n(key, fallback=""):
    lang_group = get_sys_lang()
    
    msgs = {
        'en': {
            'log_warmup': ' 🔄 Background warming up models...',
            'log_ollama_ok': ' ✅ Ollama detected: ',
            'log_whisper_ok': ' ✅ mlx-whisper model warmed up',
            'log_recording': ' 🔴 Recording...',
            'log_processing': ' ⏳ Processing...',
            'menu_dashboard': '📊 Open Dashboard',
            'menu_record': '🎤 Start Recording',
            'menu_stop': '⏹ Stop Recording',
            'menu_processing': '⏳ Processing...',
            'menu_quit': 'Quit',
            'notif_learn_title': 'SGH Voice Auto-Learn',
            'notif_learn_body': '📚 Added to dictionary: ',
            'alert_title': 'SGH Voice',
            'alert_body': 'SGH Voice needs "Accessibility" permission to auto-paste text.\n\nPlease enable it in "System Settings -> Privacy & Security -> Accessibility".',
            'alert_btn': 'Open System Settings'
        },
        'ja': {
            'log_warmup': ' 🔄 バックグラウンドでモデルを予熱中...',
            'log_ollama_ok': ' ✅ Ollama を検出しました: ',
            'log_whisper_ok': ' ✅ mlx-whisper モデルの準備が完了しました',
            'log_recording': ' 🔴 録音中...',
            'log_processing': ' ⏳ 処理中...',
            'menu_dashboard': '📊 ダッシュボード設定',
            'menu_record': '🎤 録音開始',
            'menu_stop': '⏹ 録音停止',
            'menu_processing': '⏳ 処理中...',
            'menu_quit': '終了',
            'notif_learn_title': 'SGH Voice 自動学習',
            'notif_learn_body': '📚 辞書に追加されました: ',
            'alert_title': 'SGH Voice',
            'alert_body': 'テキストを自動ペーストするには「アクセシビリティ」権限が必要です。\n\nシステム設定 > プライバシーとセキュリティからSGH Voiceを有効にしてください。',
            'alert_btn': 'システム設定を開く'
        },
        'zh': {
            'log_warmup': ' 🔄 背景預熱 Whisper + Ollama 模型...',
            'log_ollama_ok': ' ✅ Ollama 偵測成功: ',
            'log_whisper_ok': ' ✅ mlx-whisper 模型預熱完成',
            'log_recording': ' 🔴 錄音中...',
            'log_processing': ' ⏳ 辨識處理中...',
            'menu_dashboard': '📊 開啟 Dashboard',
            'menu_record': '🎤 開始錄音',
            'menu_stop': '⏹ 停止錄音',
            'menu_processing': '⏳ 辨識處理中...',
            'menu_quit': '退出',
            'notif_learn_title': 'SGH Voice 自動學習',
            'notif_learn_body': '📚 已新增至詞庫：',
            'alert_title': 'SGH Voice',
            'alert_body': 'SGH Voice 需要「輔助使用」權限才能自動貼上文字。\n\n請在「系統設定 → 隱私與安全性 → 輔助使用」中開啟 SGH Voice。',
            'alert_btn': '打開系統設定'
        }
    }
    
    return msgs.get(lang_group, msgs['en']).get(key, fallback or key)

import time
import argparse
import webbrowser

from config import load_config, save_config, update_stats
from memory import Memory
from transcriber import Transcriber
from recorder import Recorder
from overlay import StatusOverlay


# ─── Logger ──────────────────────────────────────────────

_ANSI = {
    "reset": "\033[0m",  "bold": "\033[1m",  "dim": "\033[2m",
    "red":   "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
    "blue":  "\033[94m", "magenta": "\033[95m", "cyan": "\033[96m",
    "gray":  "\033[90m",
}

def _c(color, text):
    """套用 ANSI 色彩（僅 terminal 有效，.app bundle 下自動關閉）"""
    if not sys.stdout.isatty():
        return text
    return f"{_ANSI.get(color,'')}{text}{_ANSI['reset']}"

def _now():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

def log(level, msg):
    """
    統一 log 格式：
      INFO  →  灰色時間 + 白字
      OK    →  綠色 ✓
      WARN  →  黃色 ⚠
      ERROR →  紅色 ✕
      REC   →  紅色錄音狀態
      STT   →  藍色辨識結果
      LLM   →  青色 LLM 結果
      DONE  →  加粗最終輸出
    """
    ts = _c("gray", f"[{_now()}]")
    icons = {
        "info":  ("  ", ""),
        "ok":    ("✓ ", "green"),
        "warn":  ("⚠ ", "yellow"),
        "error": ("✕ ", "red"),
        "rec":   ("🔴", "red"),
        "stt":   ("◎ ", "blue"),
        "llm":   ("◈ ", "cyan"),
        "done":  ("▶ ", "bold"),
    }
    icon, color = icons.get(level, ("  ", ""))
    prefix = _c(color, icon) if color else icon
    print(f"{ts} {prefix}{msg}")

def log_sep(char="─", width=56):
    print(_c("gray", char * width))


# Pasteboard generations created by SGH Voice must never be interpreted as a
# user-verified correction.  The transactional insertion path stages the
# transcript and then restores the original multi-format clipboard payload;
# both operations increment NSPasteboard.changeCount().
_INTERNAL_PASTEBOARD_LOCK = threading.RLock()
_INTERNAL_PASTEBOARD_GENERATIONS = {}
_INTERNAL_PASTEBOARD_TTL_SEC = 30.0


def _current_pasteboard_generation():
    try:
        from AppKit import NSPasteboard
        return int(NSPasteboard.generalPasteboard().changeCount())
    except Exception:
        return None


def _remember_internal_pasteboard_generation(change_count=None):
    """Register one exact app-generated pasteboard generation for the observer."""
    if change_count is None:
        change_count = _current_pasteboard_generation()
    if change_count is None:
        return
    now = time.monotonic()
    with _INTERNAL_PASTEBOARD_LOCK:
        expired = [
            generation for generation, expiry in _INTERNAL_PASTEBOARD_GENERATIONS.items()
            if expiry <= now
        ]
        for generation in expired:
            _INTERNAL_PASTEBOARD_GENERATIONS.pop(generation, None)
        _INTERNAL_PASTEBOARD_GENERATIONS[int(change_count)] = (
            now + _INTERNAL_PASTEBOARD_TTL_SEC
        )


def _consume_internal_pasteboard_generation(change_count):
    """Return True once for an app-generated generation, then forget it."""
    now = time.monotonic()
    try:
        generation = int(change_count)
    except (TypeError, ValueError):
        return False
    with _INTERNAL_PASTEBOARD_LOCK:
        expired = [
            item for item, expiry in _INTERNAL_PASTEBOARD_GENERATIONS.items()
            if expiry <= now
        ]
        for item in expired:
            _INTERNAL_PASTEBOARD_GENERATIONS.pop(item, None)
        return _INTERNAL_PASTEBOARD_GENERATIONS.pop(generation, None) is not None


def _restore_pasteboard_and_mark(snapshot, expected_change_count):
    """Restore atomically relative to the observer and mark the resulting generation."""
    with _INTERNAL_PASTEBOARD_LOCK:
        restored = restore_pasteboard(snapshot, expected_change_count)
        if restored:
            _remember_internal_pasteboard_generation()
        return restored


# ─── Utility ─────────────────────────────────────────────

def _paste_log(msg):
    """將貼上除錯資訊寫入檔案（.app 的 stdout 不可見）"""
    try:
        import os
        log_path = os.path.expanduser("~/.voice-input/paste_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _wait_modifiers_released(max_wait=0.6, poll_interval=0.01):
    """Polling 等修飾鍵（Cmd/Shift/Opt/Ctrl）全部放開，避免送 Cmd+V 跟使用者按鍵打架。
    典型 50-150ms 即可放開，原 fixed sleep(0.6) 是 worst-case 容錯。"""
    try:
        from Quartz import (
            CGEventSourceFlagsState,
            kCGEventSourceStateHIDSystemState,
            kCGEventFlagMaskCommand,
            kCGEventFlagMaskAlternate,
            kCGEventFlagMaskShift,
            kCGEventFlagMaskControl,
        )
        MOD_MASK = (
            kCGEventFlagMaskCommand
            | kCGEventFlagMaskAlternate
            | kCGEventFlagMaskShift
            | kCGEventFlagMaskControl
        )
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            flags = CGEventSourceFlagsState(kCGEventSourceStateHIDSystemState)
            if (flags & MOD_MASK) == 0:
                return  # 修飾鍵都放開了，立刻 return
            time.sleep(poll_interval)
    except Exception:
        # Quartz 不可用就 fallback 到 fixed sleep（保守處理）
        time.sleep(max_wait)


def _wait_clipboard_change(old_value, max_wait=0.2, poll_interval=0.01):
    """Polling 等剪貼簿被新值更新（Cmd+C 後讀內容用）。
    典型 30-50ms 內就會變化。"""
    try:
        import pyperclip
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            cur = pyperclip.paste()
            if cur != old_value:
                return cur
            time.sleep(poll_interval)
        return pyperclip.paste()
    except Exception:
        time.sleep(max_wait)
        try:
            import pyperclip
            return pyperclip.paste()
        except Exception:
            return ""


def paste_text(text):
    """將文字插入游標位置，優先完全不碰使用者的剪貼簿。

    一般文字欄位使用 AXSelectedText 直接插入。Terminal／Canvas 等不支援該
    attribute 的 App 才短暫交換 pasteboard，送出 Cmd+V 後 250ms 內完整還原
    所有原始格式（不只 plain text）。
    """
    if not text:
        return False

    # 記錄當前前景 App (協助除錯)
    target_pid = None
    curr_app = None
    try:
        from AppKit import NSWorkspace
        curr_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        app_info = f"{curr_app.localizedName()} ({curr_app.bundleIdentifier()})"
        target_pid = int(curr_app.processIdentifier())
    except Exception:
        app_info = "Unknown"

    # 檢查輔助使用權限
    is_trusted = accessibility_is_trusted()
    _paste_log(f"AXIsProcessTrusted={is_trusted}, app={app_info}")

    # 方法 1：直接寫入目前 selection/caret，完全不使用剪貼簿。
    if is_trusted and insert_text_via_accessibility(text, target_pid):
        _paste_log(f"AXSelectedText 直接插入成功 [{app_info}], chars={len(text)}")
        try:
            bundle_id = curr_app.bundleIdentifier() if curr_app else None
        except Exception:
            bundle_id = None
        event_ledger.paste_method(
            method="accessibility",
            success=True,
            text_len=len(text),
            app_id=bundle_id,
        )
        return True

    # 方法 2：不支援 AXSelectedText 的 App 使用 transactional pasteboard。
    # snapshot 保存所有格式（文字／圖片／檔案／RTF／HTML），不是只存 plain text。
    snapshot = None
    fallback_old_text = None
    baseline_change_count = None
    try:
        with _INTERNAL_PASTEBOARD_LOCK:
            snapshot = capture_pasteboard()
            baseline_change_count = stage_text_on_pasteboard(text)
            _remember_internal_pasteboard_generation(baseline_change_count)
        _paste_log(f"暫存文字至 pasteboard [{app_info}], chars={len(text)}")
    except Exception as e:
        _paste_log(f"Pasteboard transaction unavailable: {e}")
        try:
            import pyperclip

            with _INTERNAL_PASTEBOARD_LOCK:
                fallback_old_text = pyperclip.paste()
                pyperclip.copy(text)
                _remember_internal_pasteboard_generation()
        except Exception as fallback_error:
            _paste_log(f"Clipboard fallback error: {fallback_error}")
            return False

    # 動態 polling 等修飾鍵放開，避免使用者的 Cmd/Shift 與 synthetic Cmd+V 打架。
    _wait_modifiers_released(max_wait=0.6)

    clipboard_changed_before_paste = False

    def _transaction_is_current():
        if snapshot is not None and baseline_change_count is not None:
            return pasteboard_change_count_matches(baseline_change_count)
        if fallback_old_text is not None:
            try:
                import pyperclip

                return pyperclip.paste() == text
            except Exception:
                return False
        return False

    # 使用者可能在等待修飾鍵放開的 0.6 秒內又做了 copy/cut。
    # 這時必須取消本次 Cmd+V，否則會把使用者剛複製的內容貼進文稿。
    if not _transaction_is_current():
        clipboard_changed_before_paste = True
        _paste_log("偵測到使用者新的 copy/cut，取消本次 synthetic paste")

    pasted = False
    paste_method_used = None
    if is_trusted and not clipboard_changed_before_paste:
        try:
            # 儘可能貼近事件送出時再檢查一次，縮小 copy/paste 競態窗口。
            if not _transaction_is_current():
                clipboard_changed_before_paste = True
                raise RuntimeError("pasteboard changed before Quartz Cmd+V")
            from Quartz import (
                CGEventCreateKeyboardEvent, CGEventPost, kCGSessionEventTap,
                CGEventSetFlags, kCGEventFlagMaskCommand
            )
            V_KEYCODE = 9
            event_down = CGEventCreateKeyboardEvent(None, V_KEYCODE, True)
            CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
            event_up = CGEventCreateKeyboardEvent(None, V_KEYCODE, False)
            CGEventSetFlags(event_up, kCGEventFlagMaskCommand)
            CGEventPost(kCGSessionEventTap, event_down)
            time.sleep(0.02)
            CGEventPost(kCGSessionEventTap, event_up)
            pasted = True
            paste_method_used = "quartz"
            _paste_log("Quartz CGEvent 貼上發送完成")
        except Exception as e:
            _paste_log(f"CGEvent exception: {e}")

    # 方法 3：Quartz 不可用時才走 System Events。
    if not pasted and not clipboard_changed_before_paste:
        try:
            if not _transaction_is_current():
                clipboard_changed_before_paste = True
                raise RuntimeError("pasteboard changed before System Events Cmd+V")
            result = subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to keystroke "v" using command down'
            ], capture_output=True, text=True, timeout=5)
            _paste_log(f"osascript returncode={result.returncode}")
            if result.returncode == 0:
                pasted = True
                paste_method_used = "osascript"
        except Exception as e:
            _paste_log(f"osascript exception: {e}")

    _paste_log(f"最終結果: pasted={pasted}")
    # Ledger: 哪個 paste method 真正生效（追蹤 fallback chain 觸發率）
    try:
        bundle_id = curr_app.bundleIdentifier() if 'curr_app' in dir() else None
    except Exception:
        bundle_id = None
    event_ledger.paste_method(
        method=paste_method_used or "clipboard_only",
        success=bool(pasted),
        text_len=len(text or ""),
        app_id=bundle_id,
    )

    if snapshot is not None and baseline_change_count is not None:
        if pasted:
            schedule_pasteboard_restore(
                snapshot,
                baseline_change_count,
                delay=0.25,
                restore=_restore_pasteboard_and_mark,
            )
        else:
            # 沒貼上也不能把轉錄文字留在 clipboard；立即恢復原始所有格式。
            try:
                _restore_pasteboard_and_mark(snapshot, baseline_change_count)
            except Exception:
                pass
    elif fallback_old_text is not None:
        def _restore_plain_text():
            if pasted:
                time.sleep(0.25)
            try:
                import pyperclip

                with _INTERNAL_PASTEBOARD_LOCK:
                    if pyperclip.paste() == text:
                        pyperclip.copy(fallback_old_text)
                        _remember_internal_pasteboard_generation()
            except Exception:
                pass

        threading.Thread(target=_restore_plain_text, daemon=True).start()

    if not pasted:
        _paste_log("全部自動插入方法失敗；已保留原剪貼簿")
        if clipboard_changed_before_paste:
            notify(
                "SGH Voice",
                "為保留你剛複製的內容，本次自動輸入已取消。",
            )
        elif not is_trusted:
            request_accessibility_prompt()
            notify(
                "SGH Voice",
                "⚠️ 自動貼上權限未開啟；原剪貼簿已保留。請在輔助使用中啟用 SGH Voice。",
            )
        else:
            notify("SGH Voice", "⚠️ 目前欄位不接受自動輸入；原剪貼簿已保留。")
    return pasted


def show_copy_dialog(text):
    """顯示「複製最後的轉錄」對話框（模仿 Typeless）"""
    preview = text[:60].replace('"', '\\"').replace("'", "'")
    try:
        subprocess.Popen([
            "osascript", "-e",
            f'''display dialog "複製最後的轉錄" & return & return & "\\"{preview}\\"" '''
            f'''buttons {{"關閉", "複製"}} default button "複製" with title "Voice Input" with icon note'''
            f''' giving up after 15'''
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        notify("Voice Input", f"📋 已複製: {preview}")


def notify(title, message):
    """非同步顯示 macOS 通知，不阻塞主流程"""
    try:
        msg = message[:80].replace('"', '\\"')
        subprocess.Popen([
            "osascript", "-e",
            f'display notification "{msg}" with title "{title}" sound name "Glass"'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


# ─── Core Engine ─────────────────────────────────────────

class VoiceEngine:
    """語音輸入核心引擎，被 CLI / MenuBar / Dashboard 共用"""

    def __init__(self):
        self.version = "2.6.0"
        self.config = load_config()
        self.memory = Memory()
        self.transcriber = Transcriber(self.config, self.memory)
        self.recorder = Recorder(self.config)
        self.overlay = StatusOverlay()
        self.is_recording = False
        self.is_processing = False
        self._processing_start_ts = None
        self._state_lock = threading.RLock()
        # Recorder owns one PortAudio stream and mutable audio buffer.  Keep
        # start/stop/cancel transitions strictly serialized while still
        # allowing the completed audio to transcribe in parallel afterwards.
        self._recorder_transition_lock = threading.RLock()
        self._on_status_change = None  # callback(status_str)
        self._on_hotkey_reset = None   # callback() — 讓 hotkey closure 清掉 stale press state
        self._watchdog_timer = None
        self._record_start_ts = None
        # Recording-scoped cancellation closes the PTT-release race: a Cancel
        # gesture marks the exact recording before its callback thread runs.
        self._active_recording_tokens = set()
        self._cancelled_recording_tokens = set()
        self._stopping_recording_token = None
        self._processing_recording_tokens = []
        self._continuous_cancel_event = None
        # 多段轉寫並行時序列化 paste，避免剪貼簿/Cmd+V 互踩
        self._paste_lock = threading.Lock()
        self._inflight_transcriptions = 0
        # Cancel hotkey 標記：set 後 paste 階段會跳過
        self._cancel_inflight = False

    def start_background_tasks(self):
        """主程式啟動後再跑背景任務，避免搶佔啟動時的系統資源"""
        if self.config.get("enable_hybrid_mode", True) and self.config.get("enable_model_warmup", False):
            print(get_i18n("log_warmup"))
            threading.Thread(target=self.transcriber.warmup, daemon=True).start()

    def reload_config(self):
        previous = self.config
        self.config = load_config()
        self.transcriber.config = self.config
        self.transcriber.reset_clients()
        self.recorder.config = self.config
        hotkeys_changed = any(
            previous.get(key) != self.config.get(key)
            for key in (*HOTKEY_FIELDS, "hotkey_mode")
        )
        if hotkeys_changed and self._on_hotkey_reset:
            try:
                self._on_hotkey_reset()
            except Exception as exc:
                log("warn", f"hotkey reload reset failed: {exc}")
        if (
            hotkeys_changed
            and self.is_recording
            and previous.get("hotkey_mode", "push_to_talk") == "push_to_talk"
        ):
            # 若使用者在按住舊 PTT 時儲存新鍵，舊 key-up 不再屬於新 target。
            # 立即正常結束本段，避免錄音一路卡到 watchdog。
            log("warn", "錄音中修改熱鍵；正在安全結束目前錄音")
            threading.Thread(target=self.stop_and_process, daemon=True).start()
        log("ok", "設定已即時重新載入")
        if hotkeys_changed:
            log("ok", f"錄音熱鍵已即時更新: {self.config.get('hotkey')}")

    def start_recording(self, from_hotkey=False):
        """from_hotkey=True 才會 arm push-to-talk watchdog；CLI/Dashboard/menu bar
        從外部主動呼叫時請保持 False，否則會被 60s watchdog 截掉。"""
        # stop_and_process/cancel_current 也使用這把鎖。新一段錄音只會在
        # 上一段 InputStream 完成 join、audio_data 已取走後才開始，避免舊 stop
        # 清掉新錄音的 buffer / start time / stop event。
        with self._recorder_transition_lock:
            with self._state_lock:
                if self.is_recording:
                    return False
                # is_processing 只代表「背景有轉寫在跑」，不應該阻擋新錄音。
                # paste 由 self._paste_lock 序列化，不會互踩。
                self.is_recording = True
                self._record_start_ts = time.time()
                recording_token = self._record_start_ts
                self._active_recording_tokens.add(recording_token)

            recorder_started = False
            try:
                # on_error：stream 開啟失敗（PortAudio 裝置清單過期等）時由 recorder
                # thread 回呼。閉包鎖定本段 token，避免 callback 晚到時誤殺新錄音。
                started = self.recorder.start(
                    on_error=lambda msg, _ts=recording_token: self._on_recorder_error(msg, _ts)
                )
                if started is False:
                    with self._state_lock:
                        if self._record_start_ts == recording_token:
                            self.is_recording = False
                            self._record_start_ts = None
                        self._active_recording_tokens.discard(recording_token)
                        self._cancelled_recording_tokens.discard(recording_token)
                    log("warn", "recorder 尚未釋放，略過本次錄音啟動")
                    self._safe_status_change("idle")
                    return False
                recorder_started = True

                # Recorder thread 可能在 start() 返回前就回報開流失敗；只有本段
                # token 仍有效時才顯示 recording/arm watchdog，避免 ghost recording。
                with self._state_lock:
                    still_active = (
                        self.is_recording
                        and self._record_start_ts == recording_token
                    )
                if not still_active:
                    return False

                try:
                    self.overlay.show("recording")
                except Exception as exc:
                    # Overlay is cosmetic.  A rendering failure must not turn a
                    # healthy microphone stream into a failed start.
                    log("warn", f"recording overlay: {exc}")
                self._safe_status_change("recording")
                log("rec", "錄音中…")
                self._arm_watchdog(from_hotkey=from_hotkey)

                # Close the final check-to-UI race: the Recorder thread can
                # report an input-stream failure after the first token check
                # but while overlay/watchdog setup is running.  Revalidate
                # after arming so a failed stream is never returned as a
                # successful (ghost) recording.
                with self._state_lock:
                    still_active = (
                        self.is_recording
                        and self._record_start_ts == recording_token
                    )
                if not still_active:
                    self._cancel_watchdog()
                    try:
                        self.overlay.show("idle")
                    except Exception:
                        pass
                    self._safe_status_change("idle")
                    return False
                return True
            except Exception:
                # Once Recorder.start succeeded, every later failure must fully
                # join/discard that stream before Engine reports idle.  Merely
                # rolling back Engine state would leave an orphan microphone.
                self._cancel_watchdog()
                if recorder_started or getattr(self.recorder, "is_recording", False):
                    try:
                        _audio, failed_filepath, _duration = self.recorder.stop()
                        if failed_filepath and os.path.exists(failed_filepath):
                            os.remove(failed_filepath)
                    except Exception as stop_exc:
                        log("warn", f"failed start cleanup: {stop_exc}")
                with self._state_lock:
                    if self._record_start_ts == recording_token:
                        self.is_recording = False
                        self._record_start_ts = None
                    self._active_recording_tokens.discard(recording_token)
                    self._cancelled_recording_tokens.discard(recording_token)
                self._safe_status_change("idle")
                raise

    def _on_recorder_error(self, msg, armed_for_ts):
        """recorder thread 回報「麥克風串流開啟失敗」：重置 engine 狀態 + 明確告知使用者。
        沒有這個 handler 時，engine 的 is_recording 卡 True、紅燈照亮，
        但實際上一個 chunk 都沒收到，stop 後音訊是空的且毫無提示（2026-06-13 實際災情）。"""
        with self._state_lock:
            if self._record_start_ts != armed_for_ts:
                return  # 已經是新的一段錄音，別動
            self.is_recording = False
            self._record_start_ts = None
            self._active_recording_tokens.discard(armed_for_ts)
            self._cancelled_recording_tokens.discard(armed_for_ts)
        self._cancel_watchdog()
        log("error", f"🎙 {msg}")
        log("warn", "已重新初始化音訊系統，請再按一次熱鍵重試；若仍失敗請檢查 系統設定→隱私權與安全性→麥克風，或重啟 App")
        try: self.overlay.show("idle")
        except Exception: pass
        self._safe_status_change("idle")
        cb = self._on_hotkey_reset
        if cb:
            try: cb()
            except Exception as e:
                log("warn", f"hotkey reset callback error: {e}")

    def _arm_watchdog(self, from_hotkey=False):
        """錄音保險：超過 max 秒仍在錄音 → 強制停止。所有 path 共用同一上限：
        max_recording_duration（預設 30 分鐘）。push-to-talk 講三五分鐘是合理使用情境，
        不該因為「以防 hotkey 卡住」就被特別截短。`pushtotalk_max_seconds` 仍可被
        config override 拿來縮短，但預設沿用 max_recording_duration。"""
        self._cancel_watchdog()
        is_ptt = (
            from_hotkey
            and self.config.get("hotkey_mode", "push_to_talk") == "push_to_talk"
        )
        try:
            ptt_override = self.config.get("pushtotalk_max_seconds") if is_ptt else None
            max_sec = float(
                ptt_override if ptt_override else self.config.get("max_recording_duration", 1800)
            )
        except Exception:
            max_sec = 1800.0
        if max_sec <= 0:
            return

        armed_for_ts = self._record_start_ts

        def _fire():
            with self._state_lock:
                current_ts = self._record_start_ts
                is_recording = self.is_recording
            # 同一段錄音才處理；如果是新的（使用者在 timer 等候期間 stop 再 start），略過
            if not is_recording or current_ts != armed_for_ts:
                return
            elapsed = time.time() - (current_ts or time.time())
            log("warn", f"⏱ 錄音已 {elapsed:.0f}s 超過上限 {max_sec:.0f}s，自動停止")
            try:
                self.stop_and_process()
            except Exception as e:
                log("error", f"watchdog stop_and_process error: {e}")
                with self._state_lock:
                    self.is_recording = False
                    self.is_processing = False
                try: self.overlay.show("idle")
                except Exception: pass
                self._safe_status_change("idle")
            # 通知 hotkey closure 清掉 stale press state——但只有在「真的沒有新錄音
            # 接著開始」的時候才清，避免 stop_and_process 跑完到這裡的空檔，
            # 使用者剛好重按 hotkey 起了一段新錄音，反而把新錄音的 press state 弄壞。
            if not from_hotkey:
                return  # 非 hotkey path 沒有 hotkey closure 要重置
            with self._state_lock:
                new_recording_running = self.is_recording
            if new_recording_running:
                return  # 有新錄音了，別動 hotkey state
            cb = self._on_hotkey_reset
            if cb:
                try: cb()
                except Exception as e:
                    log("warn", f"hotkey reset callback error: {e}")

        t = threading.Timer(max_sec, _fire)
        t.daemon = True
        t.start()
        self._watchdog_timer = t

    def _cancel_watchdog(self):
        t = self._watchdog_timer
        if t is not None:
            try: t.cancel()
            except Exception: pass
            self._watchdog_timer = None

    def _safe_status_change(self, status):
        """送出狀態變更；menubar callback 會自行排程到主執行緒更新 UI。"""
        if not self._on_status_change:
            return
        try:
            self._on_status_change(status)
        except Exception as e:
            print(f"Status change error (non-fatal): {e}")

    def mark_cancel_intent(self, recording_token):
        """Atomically mark one still-active recording as cancelled.

        This is intentionally synchronous and cheap so the NSEvent arbiter can
        call it before scheduling the user-facing Cancel callback.  The marker
        survives the gap where ``stop_and_process`` has cleared is_recording
        but has not yet entered the processing phase.
        """

        if recording_token is None:
            return False
        with self._state_lock:
            if recording_token not in self._active_recording_tokens:
                return False
            self._cancelled_recording_tokens.add(recording_token)
            return True

    def _recording_token_is_cancelled(self, recording_token):
        if recording_token is None:
            return False
        with self._state_lock:
            return recording_token in self._cancelled_recording_tokens

    def _finish_recording_token(self, recording_token):
        if recording_token is None:
            return
        with self._state_lock:
            self._active_recording_tokens.discard(recording_token)
            self._cancelled_recording_tokens.discard(recording_token)
            self._processing_recording_tokens = [
                token
                for token in self._processing_recording_tokens
                if token != recording_token
            ]
            if self._stopping_recording_token == recording_token:
                self._stopping_recording_token = None

    def latest_cancellable_recording_token(self):
        """Return the newest exact recording pipeline Cancel should target."""

        with self._state_lock:
            # Continuous mode is one live stream rather than a tokenized PTT
            # pipeline.  A generic Cancel must stop that stream, not an older
            # PTT result that happens to still be processing.
            if getattr(self, "_continuous_active", False):
                return None
            if self._record_start_ts is not None:
                return self._record_start_ts
            if self._stopping_recording_token is not None:
                return self._stopping_recording_token
            if self._processing_recording_tokens:
                return max(self._processing_recording_tokens)
            return None

    def _discard_cancelled_recording(self, recording_token, filepath=None):
        """Drop a cancelled recording before STT and clean its temp audio."""

        if not self._recording_token_is_cancelled(recording_token):
            return False
        self._finish_recording_token(recording_token)
        if filepath:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except OSError:
                pass
        log("warn", "🚫 錄音已取消，略過轉寫與貼上")
        with self._state_lock:
            pending = self._inflight_transcriptions
            still_recording = self.is_recording
        if pending == 0 and not still_recording:
            try:
                self.overlay.show("idle")
            except Exception:
                pass
            self._safe_status_change("idle")
        return True

    def stop_and_process(self, mode="dictate", edit_context="", sync=False):
        """停止錄音 → 立刻釋放 engine（可開新錄音）→ 轉寫/貼上在背景跑。
        sync=True 時改為同步等待轉寫結果（CLI/REPL 用）。"""
        # Claim engine state and fully release the old PortAudio stream as one
        # serialized recorder transition.  STT starts only after this lock is
        # released, so it remains safe for later recordings to overlap STT.
        with self._recorder_transition_lock:
            with self._state_lock:
                if getattr(self, "_continuous_active", False):
                    log("warn", "連續模式中忽略一般錄音停止要求")
                    return None
                if not self.is_recording:
                    return None
                recording_token = self._record_start_ts
                self.is_recording = False
                self._record_start_ts = None
                self._stopping_recording_token = recording_token

            self._cancel_watchdog()

            try:
                audio_array, filepath, duration = self.recorder.stop()
            except Exception as e:
                log("error", f"recorder.stop 錯誤: {e}")
                self._finish_recording_token(recording_token)
                self._safe_status_change("idle")
                return None

        if self._discard_cancelled_recording(recording_token, filepath):
            return None

        if (audio_array is None or (hasattr(audio_array, '__len__') and len(audio_array) == 0)) and not filepath:
            # 不可以靜默：使用者按了停止卻什麼都沒發生，會以為 App 壞了。
            # 帶上 recorder 的串流錯誤（若有），讓「為什麼沒錄到」可被診斷。
            rec_err = getattr(self.recorder, "last_error", None)
            if rec_err:
                log("error", f"🎙 未錄到音訊：{rec_err}")
                log("warn", "已重新初始化音訊系統，請再試一次；若持續失敗請重啟 App")
            else:
                log("warn", "未錄到任何音訊（錄音過短，或麥克風沒有輸入）")
            with self._state_lock:
                pending = self._inflight_transcriptions
                still_recording = self.is_recording
            if pending == 0 and not still_recording:
                self.overlay.show("idle")
                self._safe_status_change("idle")
            self._finish_recording_token(recording_token)
            return None

        if self.config.get("target_language") and mode == "dictate":
            target = str(self.config.get("target_language", "")).lower()
            edit_context = {
                "ja": "translate_ja", "japanese": "translate_ja",
                "zh": "translate_zh", "zh-tw": "translate_zh", "chinese": "translate_zh",
                "en": "translate_en", "english": "translate_en",
            }.get(target, "")
            if edit_context:
                mode = "edit"

        if sync:
            return self._transcribe_and_paste(
                audio_array,
                filepath,
                duration,
                mode,
                edit_context,
                recording_token,
            )

        threading.Thread(
            target=self._transcribe_and_paste,
            args=(
                audio_array,
                filepath,
                duration,
                mode,
                edit_context,
                recording_token,
            ),
            daemon=True,
        ).start()
        return None

    def _transcribe_and_paste(
        self,
        audio_array,
        filepath,
        duration,
        mode,
        edit_context,
        recording_token=None,
    ):
        """背景跑：Whisper → 後處理 → 自動貼上。paste 用 lock 序列化。"""
        if self._discard_cancelled_recording(recording_token, filepath):
            return None
        with self._state_lock:
            if self._stopping_recording_token == recording_token:
                self._stopping_recording_token = None
            if recording_token is not None:
                self._processing_recording_tokens.append(recording_token)
            self._inflight_transcriptions += 1
            self.is_processing = True
            if self._processing_start_ts is None:
                self._processing_start_ts = time.time()

        # 只在沒人在錄音時把 overlay 切到 processing，避免蓋掉新一段錄音的狀態
        with self._state_lock:
            show_processing = not self.is_recording
        if show_processing:
            try: self.overlay.show("processing")
            except Exception: pass
            self._safe_status_change("processing")
        log("info", f"錄音 {duration:.1f}s，開始辨識處理…")

        # 階段化 overlay label：STT / LLM / paste 三段，幫助使用者知道目前卡哪。
        # 但若 user 此時已開始新錄音（continuous 模式 / 快速連按），overlay 已被切回
        # "recording"，這時候 update_stage 會把錄音動畫的 prefix 偷換掉 → 顯示錯亂。
        # 所以 callback 內要再次 check 當前 is_recording 才能真正套用。
        def _on_stage(stage):
            with self._state_lock:
                if self.is_recording:
                    return
            try: self.overlay.update_stage(stage)
            except Exception: pass

        result = None
        cancelled_output = False
        paste_succeeded = None
        try:
            audio_input = (
                {"array": audio_array, "path": filepath}
                if audio_array is not None and filepath
                else (audio_array if audio_array is not None else filepath)
            )
            # audio_input dict now owns the ndarray reference; keep this frame lighter while
            # STT/LLM runs, especially when cloud STT reads the wav file directly.
            audio_array = None
            result = self.transcriber.transcribe(audio_input, duration, mode, edit_context, on_stage=_on_stage)

            if result:
                final = result["final"] or ""
                proc  = result.get("process_time", 0)
                log("done", f"{_c('bold', final[:80])}{'…' if len(final)>80 else ''}")
                log("info", f"錄音 {duration:.1f}s  |  處理 {proc:.1f}s  |  {len(final)} 字元")
                log_sep()
                try:
                    update_stats(final, duration, self.config)
                except Exception as e:
                    log("warn", f"Stats update: {e}")

                with self._state_lock:
                    token_cancelled = (
                        recording_token in self._cancelled_recording_tokens
                        if recording_token is not None
                        else False
                    )
                    legacy_cancelled = (
                        self._cancel_inflight
                        if recording_token is None
                        else False
                    )
                    if legacy_cancelled:
                        self._cancel_inflight = False
                cancelled_output = token_cancelled or legacy_cancelled
                if cancelled_output:
                    log("warn", "🚫 已取消，跳過 paste")
                elif self.config.get("auto_paste") and final:
                    _on_stage("paste")
                    with self._paste_lock:
                        # Cancel may arrive while the LLM result is returning;
                        # check once more immediately before insertion.
                        with self._state_lock:
                            token_cancelled = (
                                recording_token in self._cancelled_recording_tokens
                                if recording_token is not None
                                else False
                            )
                            legacy_cancelled = (
                                self._cancel_inflight
                                if recording_token is None
                                else False
                            )
                            if legacy_cancelled:
                                self._cancel_inflight = False
                        cancelled_output = token_cancelled or legacy_cancelled
                        if cancelled_output:
                            log("warn", "🚫 已取消，略過最後 paste")
                        else:
                            try:
                                paste_succeeded = paste_text(final)
                            except Exception as e:
                                paste_succeeded = False
                                log("warn", f"Paste: {e}")

                with self._state_lock:
                    other_inflight = self._inflight_transcriptions > 1 or self.is_recording
                if not other_inflight and not cancelled_output:
                    if paste_succeeded is False:
                        log("warn", "轉寫已完成，但自動輸入失敗；結果保留於 History")
                        try: self.overlay.show("paste_failed")
                        except Exception: pass
                    elif self.config.get("enable_transcript_overlay", True):
                        try: self.overlay.show_transcript(final, duration=2.5)
                        except Exception:
                            try: self.overlay.show("done")
                            except Exception: pass
                    else:
                        try: self.overlay.show("done")
                        except Exception: pass
            else:
                log("warn", "無有效音訊，已略過")
                log_sep()
                with self._state_lock:
                    other_inflight = self._inflight_transcriptions > 1 or self.is_recording
                if not other_inflight:
                    try: self.overlay.show("idle")
                    except Exception: pass

            if filepath:
                discard_file = cancelled_output or self._recording_token_is_cancelled(
                    recording_token
                )

                def _backup(discard=discard_file):
                    try:
                        if discard:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                            return
                        audio_dir = self.config.get("backup_audio_dir", "")
                        if audio_dir and os.path.isdir(os.path.dirname(audio_dir)):
                            os.makedirs(audio_dir, exist_ok=True)
                            from datetime import datetime
                            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                            ext = os.path.splitext(filepath)[1]
                            import shutil
                            shutil.move(filepath, os.path.join(audio_dir, f"{ts}{ext}"))
                        else:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                    except Exception:
                        pass
                threading.Thread(target=_backup, daemon=True).start()
        except Exception as e:
            log("error", f"transcribe 未預期錯誤: {e}")
            import traceback
            traceback.print_exc()
        finally:
            with self._state_lock:
                if recording_token is not None:
                    self._processing_recording_tokens = [
                        token
                        for token in self._processing_recording_tokens
                        if token != recording_token
                    ]
                self._inflight_transcriptions = max(0, self._inflight_transcriptions - 1)
                if self._inflight_transcriptions == 0:
                    self.is_processing = False
                    self._processing_start_ts = None
                    going_idle = not self.is_recording
                    # cancel flag 兜底清理：若該次 transcribe 回 None（audio gate /
                    # STT 全失敗），flag 沒被 paste 階段消費，會殘留到「下一次」
                    # 正常錄音 → 成功結果被誤吞。inflight 歸零時一律重置。
                    self._cancel_inflight = False
                else:
                    going_idle = False
            self._finish_recording_token(recording_token)
            if going_idle:
                self._safe_status_change("idle")
        return result

    # ─── Quick-Rewrite (B) ─────────────────────────────────
    # v2.5.0：風格 prompt 統一收斂到 config.REWRITE_STYLE_DIRECTIVES（單一事實來源），
    # 由 transcriber._wrap_edit_text 以 <command>/<text> 結構包裝（含 injection 防護）。

    def _simulate_cmd_c(self):
        """模擬 Cmd+C 複製選取的文字。回傳 True 表示送出。"""
        try:
            import ApplicationServices
            if not ApplicationServices.AXIsProcessTrusted():
                log("warn", "Cmd+C 需要輔助使用權限")
                return False
        except Exception:
            pass
        try:
            from Quartz import (
                CGEventCreateKeyboardEvent, CGEventPost, kCGSessionEventTap,
                CGEventSetFlags, kCGEventFlagMaskCommand,
            )
            C_KEYCODE = 8
            ev_down = CGEventCreateKeyboardEvent(None, C_KEYCODE, True)
            CGEventSetFlags(ev_down, kCGEventFlagMaskCommand)
            ev_up = CGEventCreateKeyboardEvent(None, C_KEYCODE, False)
            CGEventSetFlags(ev_up, kCGEventFlagMaskCommand)
            CGEventPost(kCGSessionEventTap, ev_down)
            time.sleep(0.02)
            CGEventPost(kCGSessionEventTap, ev_up)
            return True
        except Exception as e:
            log("warn", f"Cmd+C simulate error: {e}")
            return False

    def _rewrite_text(self, text, style):
        """共用改寫核心，沿用主 LLM fallback 鏈，但用獨立 system prompt（_EDIT_SYSTEM）。
        edit_context=style → _wrap_edit_text 自動查 REWRITE_STYLE_DIRECTIVES 並以
        <command>/<text> 結構包裝（選取文字含指令字樣也不會被執行）。"""
        if style not in self.transcriber._STYLE_DIRECTIVES:
            style = "concise"
        # 走 transcriber 的 LLM fallback 鏈（mode='edit' 會跳 few-shot 並用 _EDIT_SYSTEM）
        for fn_name in ("_groq_llm_process", "_openrouter_process", "_claude_process", "_openai_process"):
            try:
                fn = getattr(self.transcriber, fn_name, None)
                if not fn:
                    continue
                res = fn(text, mode="edit", edit_context=style)
                if res:
                    res = res.strip()
                    # 繁中終層防護：Quick-Rewrite 不走 _transcribe_impl 的 OpenCC。
                    # 多語 helper 只繁化中文 clause，保留日文新字體（国／画像／来週）。
                    opencc = getattr(self.transcriber, "_opencc", None)
                    if opencc and style != "translate_ja":
                        res = convert_traditional_preserving_japanese(
                            res,
                            opencc,
                            language_hint=resolve_output_language_hint(
                                style, self.config.get("language"),
                            ),
                        )
                    return res
            except Exception as e:
                log("warn", f"rewrite {fn_name} error: {e}")
        return None

    # ─── Cancel (中止當前錄音或處理中的轉寫) ─────────────
    def cancel_current(self, recording_token=None):
        """Cancel hotkey：
        - 錄音中 → 立刻停止 recorder + 丟棄音訊（不轉寫）
        - 處理中 → 設 _cancel_inflight flag，後續 paste 階段檢查跳過
        UI 立刻回 idle，給使用者「控制感」。"""
        if recording_token is None:
            recording_token = self.latest_cancellable_recording_token()

        token_active = False
        if recording_token is not None:
            token_active = self.mark_cancel_intent(recording_token)
        # Use the same recorder transition lock as normal stop/start.  Cancel
        # must wait for the stream thread to finish before a new PTT start can
        # reuse Recorder.audio_data/_stop_event.
        with self._recorder_transition_lock:
            with self._state_lock:
                current_token = self._record_start_ts
                was_recording = self.is_recording and (
                    recording_token is None or recording_token == current_token
                )
                if was_recording:
                    # Atomically claim the recording before stop_and_process can
                    # claim it.  Whichever path gets the transition lock first
                    # owns Recorder; the other observes is_recording=False.
                    self.is_recording = False
                    self._record_start_ts = None
                was_processing = self.is_processing
                if recording_token is not None:
                    token_active = (
                        recording_token in self._active_recording_tokens
                    )

            cancelled_filepath = None
            continuous_cancelled = False
            if was_recording and not getattr(self, "_continuous_active", False):
                try:
                    _audio, cancelled_filepath, _duration = self.recorder.stop()
                except Exception as exc:
                    log("warn", f"cancel recorder.stop: {exc}")
            elif was_recording:
                # RLock allows this helper to reuse the exact same transition
                # lock; do not expose a gap where PTT could start before the
                # continuous stream has actually joined.
                continuous_cancelled = bool(
                    self.stop_continuous_mode(cancel=True)
                )

        if continuous_cancelled:
            event_ledger.user_action("cancel", phase="recording")
            return
        if not was_recording and not was_processing and not token_active:
            log("warn", "目前沒有可取消的錄音/處理")
            event_ledger.user_action("cancel", phase="idle")
            return
        event_ledger.user_action(
            "cancel",
            phase=(
                "recording"
                if was_recording
                else ("processing" if was_processing else "stopping")
            ),
        )
        try:
            if was_recording:
                # 純錄音中：直接停 recorder + 重置 engine 狀態，不會進入 _transcribe_and_paste。
                # 不設 _cancel_inflight（否則 flag 會殘留到下一次正常錄音的 paste 階段被誤吞）。
                self._cancel_watchdog()
                if cancelled_filepath:
                    try:
                        if os.path.exists(cancelled_filepath):
                            os.remove(cancelled_filepath)
                    except OSError:
                        pass
                self._finish_recording_token(current_token)
                log("warn", "🚫 錄音已取消")
            if was_processing:
                # 處理中：pipeline 已經跑起來，無法 abort LLM call，只能標記讓 paste 階段跳過
                # 有 recording_token 時用 token-specific marker，避免誤吞另一個
                # 同時處理中的錄音；無 token 的一般 Cancel 沿用全域 fallback。
                if recording_token is None:
                    self._cancel_inflight = True
                log("warn", "🚫 處理中的轉寫已標記取消（paste 階段會跳過）")
            elif token_active and not was_recording:
                log("warn", "🚫 錄音停止中，取消意圖已鎖定")
            try: self.overlay.show("idle")
            except Exception: pass
            self._safe_status_change("idle")
        except Exception as e:
            log("error", f"cancel_current 失敗: {e}")

    # ─── Retry (重做最後一筆，跳過 STT) ───────────────────
    def retry_last_transcription(self):
        """Retry hotkey：用 cache 的 raw STT 重跑 LLM，貼上新版。
        不重錄、不重跑 STT，省 1.5-2s。"""
        if getattr(self, "_retry_in_progress", False):
            return
        if self.is_recording:
            log("warn", "錄音中，無法 retry")
            return
        cache = getattr(self.transcriber, "_last_stt_cache", None)
        if not cache:
            log("warn", "沒有可重做的紀錄（先錄一段）")
            event_ledger.user_action("retry", phase="no_cache")
            return

        event_ledger.user_action("retry", phase="processing")
        self._retry_in_progress = True
        try:
            try: self.overlay.show("processing")
            except Exception: pass
            self._safe_status_change("processing")
            log("info", f"🔁 Retry：跳過 STT，重跑 LLM（raw={cache['raw'][:30]}...）")

            def _retry_on_stage(stage):
                # 同 _transcribe_and_paste：若 user 在 retry 期間開始新錄音，不要偷改 prefix
                with self._state_lock:
                    if self.is_recording:
                        return
                try: self.overlay.update_stage(stage)
                except Exception: pass

            result = self.transcriber.retry_last_llm(on_stage=_retry_on_stage)
            if not result:
                log("warn", "Retry 失敗（cache 過期或 LLM 全部失敗）")
                try: self.overlay.show("idle")
                except Exception: pass
                self._safe_status_change("idle")
                return

            final = (result.get("final") or "").strip()
            if not final:
                log("warn", "Retry 結果為空")
                try: self.overlay.show("idle")
                except Exception: pass
                self._safe_status_change("idle")
                return

            paste_succeeded = None
            if self.config.get("auto_paste", True):
                _retry_on_stage("paste")
                with self._paste_lock:
                    try: paste_succeeded = paste_text(final)
                    except Exception as e:
                        paste_succeeded = False
                        log("warn", f"Retry paste: {e}")

            log("ok", f"Retry 完成 ({len(final)} 字)")
            if paste_succeeded is False:
                log("warn", "Retry 轉寫完成，但自動輸入失敗；結果保留於 History")
                try: self.overlay.show("paste_failed")
                except Exception: pass
            else:
                try: self.overlay.show_transcript(final, duration=2.5)
                except Exception:
                    try: self.overlay.show("done")
                    except Exception: pass
            self._safe_status_change("idle")
        finally:
            self._retry_in_progress = False

    # ─── Continuous Mode (C) ──────────────────────────────
    def toggle_continuous_mode(self):
        """連續錄音模式切換：開 → 麥克風持續監聽，自動切片轉寫；再按 → 關。"""
        if getattr(self, "_continuous_active", False):
            self.stop_continuous_mode()
        else:
            self.start_continuous_mode()

    def start_continuous_mode(self):
        # v2.4.0：補上 _state_lock 保護 + PortAudio thread liveness 檢查（與 Recorder.start 對齊）
        # 之前 is_recording / _continuous_active 寫入完全沒鎖，且繞過 Recorder.start 的 thread-alive
        # 檢查 → 若上一段 push-to-talk 的 _record_loop 還在收尾就硬開連續 stream，會 deadlock
        # 在 Pa_OpenStream。把守門集中到 start_continuous_mode 入口處。
        def _on_segment(audio_array, duration):
            try:
                if duration < 0.4 or cancel_event.is_set():
                    return
                # history_mode="continuous"：由 transcriber 內部寫一筆正確標記的歷史。
                # 原本這裡再手動 add_to_history 一次 → 每段切片寫兩筆重複歷史，
                # 污染統計 / few-shot 範例 / dictionary promote 來源。
                result = self.transcriber.transcribe(
                    audio_array, audio_duration=duration, history_mode="continuous"
                )
                if not result or cancel_event.is_set():
                    return
                final = (result.get("final") or "").strip()
                if not final:
                    return
                paste_succeeded = None
                if self.config.get("auto_paste", True):
                    # max_pending_segments=2 允許兩段並行處理 → paste 必須拿
                    # _paste_lock 序列化（與 _transcribe_and_paste 同一把鎖），
                    # 否則剪貼簿互相覆蓋、Cmd+V 打架、文字貼錯段
                    with self._paste_lock:
                        if cancel_event.is_set():
                            return
                        try: paste_succeeded = paste_text(final)
                        except Exception as e:
                            paste_succeeded = False
                            log("warn", f"continuous paste: {e}")
                if cancel_event.is_set():
                    return
                if paste_succeeded is False:
                    try: self.overlay.show("paste_failed")
                    except Exception: pass
                else:
                    try: self.overlay.show_transcript(final, duration=2.5)
                    except Exception: pass
                log("ok", f"[continuous] {final[:60]}")
            except Exception as e:
                log("error", f"continuous segment: {e}")

        def _on_voice(is_voice):
            if cancel_event.is_set():
                return
            try:
                self.overlay.show("recording" if is_voice else "idle")
            except Exception:
                pass

        def _on_stopped():
            # 連續模式 stream 死亡（麥克風被拔 / PortAudioError）時的自動復原：
            # 沒有這個 callback 的話 _continuous_active / is_recording 永久卡 True，
            # 之後所有 push-to-talk 都被擋掉且無提示。
            with self._state_lock:
                if self._continuous_cancel_event is not cancel_event:
                    return  # 舊 session callback，不得清除新 session
                was_active = getattr(self, "_continuous_active", False)
                if not was_active:
                    return  # 正常 stop_continuous_mode 路徑已自行收尾
                self._continuous_active = False
                self.is_recording = False
                self._continuous_cancel_event = None
            log("warn", "連續模式 stream 已結束（裝置中斷？），狀態已自動重置")
            try: self.overlay.show("idle")
            except Exception: pass
            self._safe_status_change("idle")

        with self._recorder_transition_lock:
            with self._state_lock:
                if self.is_recording:
                    log("warn", "已在錄音中，無法啟動連續模式")
                    return False

            # 防 PortAudio deadlock：等上一段 recorder thread 完全結束。
            # join 時不持有 _state_lock，因舊 recorder callback 也會取該鎖。
            prev_thread = getattr(self.recorder, "_thread", None)
            if prev_thread is not None and prev_thread.is_alive():
                log("warn", "上一段錄音 thread 尚未結束，等 2s…")
                prev_thread.join(timeout=2.0)
                if prev_thread.is_alive():
                    log("error", "audio stream 未釋放，拒絕啟動連續模式")
                    return False

            with self._state_lock:
                self._continuous_active = True
                self.is_recording = True
                cancel_event = threading.Event()
                self._continuous_cancel_event = cancel_event
            try:
                started = self.recorder.start_continuous(
                    on_segment=_on_segment,
                    on_voice_change=_on_voice,
                    on_stopped=_on_stopped,
                )
            except Exception:
                with self._state_lock:
                    self._continuous_active = False
                    self.is_recording = False
                    if self._continuous_cancel_event is cancel_event:
                        self._continuous_cancel_event = None
                raise
            if started is False:
                with self._state_lock:
                    self._continuous_active = False
                    self.is_recording = False
                    if self._continuous_cancel_event is cancel_event:
                        self._continuous_cancel_event = None
                log("warn", "recorder 尚未釋放，無法啟動連續模式")
                return False

            # The stream thread may fail immediately and invoke _on_stopped
            # before start_continuous() returns.  Do not paint a stale
            # recording state over that recovery callback.
            with self._state_lock:
                still_active = (
                    self._continuous_active
                    and self.is_recording
                    and self._continuous_cancel_event is cancel_event
                )
            if not still_active:
                return False

            try: self.overlay.show("recording")
            except Exception: pass
            self._safe_status_change("recording")
            log("rec", "連續模式啟動 — 持續監聽中…")
            return True

    def stop_continuous_mode(self, cancel=False):
        # v2.4.0：補 _state_lock 保護 + 等 thread 真的 join 結束。原本只 set stop_event 然後
        # 立刻把 is_recording 翻 False，但 recorder thread 還在 InputStream 收尾 → 下次 start
        # 又會撞上 thread alive 守門被 reject。改成 join with timeout，並把狀態翻轉收進 lock。
        with self._recorder_transition_lock:
            with self._state_lock:
                if not getattr(self, "_continuous_active", False):
                    return False
                cancel_event = self._continuous_cancel_event
                if cancel and cancel_event is not None:
                    # Set before stopping Recorder: the loop may flush its
                    # current buffer immediately after seeing _stop_event.
                    cancel_event.set()
                # 先翻 False 再 set stop_event：讓 recorder 的 on_stopped callback
                # 能辨別「正常關閉」（不觸發裝置中斷警告路徑）
                self._continuous_active = False
                self.recorder._stop_event.set()
            # transition lock 阻擋新 stream；join 時不持有 _state_lock。
            thread = getattr(self.recorder, "_thread", None)
            if thread is not None:
                thread.join(timeout=5)
                if thread.is_alive():
                    log("warn", "continuous recorder thread 5s 未結束（PortAudio 可能 stuck）")
            with self._state_lock:
                self._continuous_active = False
                self.is_recording = False
                if self._continuous_cancel_event is cancel_event:
                    self._continuous_cancel_event = None
        if cancel:
            # Synchronize with a segment that had already entered the paste
            # critical section.  After this barrier returns, no cancelled
            # session can paste later and contradict the visible Cancel state.
            with self._paste_lock:
                pass
        try: self.overlay.show("idle")
        except Exception: pass
        self._safe_status_change("idle")
        log("ok", "連續模式已取消" if cancel else "連續模式關閉")
        return True

    def rewrite_selection(self, style=None):
        """全域快捷鍵入口：複製選取文字 → LLM 改寫 → 貼回。"""
        with self._state_lock:
            if self.is_recording:
                log("warn", "錄音中，已略過 Quick-Rewrite")
                return
        if getattr(self, "_rewrite_in_progress", False):
            return
        self._rewrite_in_progress = True
        try:
            style = style or self.config.get("default_rewrite_style", "concise")
            try:
                import pyperclip
            except Exception:
                log("warn", "pyperclip 未安裝，無法 quick-rewrite")
                return

            old_clip = None
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass

            # Polling 等鬆鍵（典型 50ms 內），不再固定 sleep(0.25)
            _wait_modifiers_released(max_wait=0.3)
            if not self._simulate_cmd_c():
                return
            # Polling 等剪貼簿變化（典型 30-50ms 內），不再固定 sleep(0.2)
            selected = _wait_clipboard_change(old_clip or "", max_wait=0.25) or ""

            if not selected.strip():
                log("warn", "未偵測到選取文字，已取消改寫")
                return
            if old_clip is not None and selected == old_clip:
                # Cmd+C 沒拿到新東西（可能沒選取）
                log("warn", "選取內容與剪貼簿相同，已取消")
                return

            try:
                self.overlay.show("processing")
            except Exception:
                pass

            log("info", f"Quick-Rewrite [{style}] 處理中：{selected[:40]}...")
            rewritten = self._rewrite_text(selected, style)
            if not rewritten or rewritten.strip() == selected.strip():
                log("warn", "改寫結果為空或無變化")
                try: self.overlay.show("idle")
                except Exception: pass
                return

            paste_text(rewritten)
            log("ok", f"Quick-Rewrite 完成 ({len(rewritten)} 字)")
            # 直接切回 idle，省掉 0.4s 過場（overlay.show_transcript 在 _transcribe_and_paste 才用）
            try: self.overlay.show("idle")
            except Exception: pass
        finally:
            self._rewrite_in_progress = False


# ─── Hotkey Listener ─────────────────────────────────────

def setup_hotkey(engine):
    """設定全域快捷鍵 (Native macOS NSEvent implementation to avoid pynput crash)"""
    try:
        from AppKit import NSEvent, NSKeyDown, NSKeyUp, NSFlagsChanged
    except ImportError:
        # Fallback to pynput if PyObjC is not available (e.g. CLI mode without rumps)
        return _setup_hotkey_pynput(engine)

    config = engine.config
    hotkey_source = str(config.get("hotkey", RECOMMENDED_RECORD_HOTKEY) or "")
    mode = config.get("hotkey_mode", "push_to_talk")
    try:
        initial_spec = parse_hotkey(
            hotkey_source,
            field="hotkey",
            allow_legacy_single_modifier=True,
        )
    except HotkeyValidationError as exc:
        log(
            "warn",
            f"Invalid recording hotkey ({exc}); using {RECOMMENDED_RECORD_HOTKEY}",
        )
        initial_spec = parse_hotkey(RECOMMENDED_RECORD_HOTKEY, field="hotkey")
    hotkey_str = initial_spec.normalized
    target_keys = set(initial_spec.keycodes)

    # Tracking state
    currently_pressed = set()
    
    # Event mask: only key events and flags changed (modifier keys)
    # NSKeyDownMask=1<<10, NSKeyUpMask=1<<11, NSFlagsChangedMask=1<<12
    KEY_EVENT_MASK = (1 << 10) | (1 << 11) | (1 << 12)

    def _process_event(event):
        """Core event processing logic (shared by global and local monitors)"""
        nonlocal currently_pressed, hotkey_source, hotkey_str, mode, target_keys

        # Dashboard save 會即時 reload engine.config。Listener 不需重複註冊
        # NSEvent monitor；下一個鍵盤事件到來時直接切換 target。
        next_source = str(
            engine.config.get("hotkey", RECOMMENDED_RECORD_HOTKEY) or ""
        )
        next_mode = engine.config.get("hotkey_mode", "push_to_talk")
        if next_source != hotkey_source or next_mode != mode:
            hotkey_source = next_source
            mode = next_mode
            try:
                next_spec = parse_hotkey(
                    hotkey_source,
                    field="hotkey",
                    allow_legacy_single_modifier=True,
                )
                hotkey_str = next_spec.normalized
                target_keys = set(next_spec.keycodes)
            except HotkeyValidationError as exc:
                log("warn", f"Invalid runtime recording hotkey: {exc}")
                target_keys = set()
            currently_pressed.clear()
            _process_event.last_active = False

        if not target_keys:
            return
        try:
            etype = event.type()
            vk = event.keyCode()
        except Exception:
            return  # Not a valid NSEvent, skip

        # Skip auto-repeat keydowns：使用者長按非 modifier hotkey（space/letter）時
        # 系統會狂送 NSKeyDown(isARepeat=True)。若 watchdog 剛 fire 清掉狀態，
        # 下一個 autorepeat 會被當成新的 rising edge 而立刻再開錄音，繞過 watchdog。
        if etype == NSKeyDown:
            try:
                if event.isARepeat():
                    return
            except Exception:
                pass

        # Update state
        if etype == NSKeyDown:
            if vk in target_keys:
                currently_pressed.add(vk)
        elif etype == NSKeyUp:
            currently_pressed.discard(vk)
        elif etype == NSFlagsChanged:
            flags = event.modifierFlags()
            if vk in target_keys:
                if modifier_is_pressed(vk, flags):
                    currently_pressed.add(vk)
                else:
                    currently_pressed.discard(vk)

        # Trigger Logic
        if len(target_keys) == 1:
            list_target = list(target_keys)[0]
            is_active = (list_target in currently_pressed)
            if getattr(engine, "_continuous_active", False):
                # Continuous mode owns Recorder until its own toggle/cancel.
                # Track the physical chord but never reinterpret its release
                # as a PTT stop for the continuous stream.
                _process_event.last_active = is_active
                return
            
            if is_active:
                 if not getattr(_process_event, 'last_active', False):  # Rising Edge
                     if mode == "push_to_talk":
                         if not engine.is_recording:
                             engine.start_recording(from_hotkey=True)
                     elif mode == "toggle":
                         if engine.is_recording:
                             threading.Thread(target=engine.stop_and_process, daemon=True).start()
                         else:
                             engine.start_recording(from_hotkey=True)
            else:
                 if getattr(_process_event, 'last_active', False):  # Falling Edge
                     if mode == "push_to_talk":
                         if engine.is_recording:
                             threading.Thread(target=engine.stop_and_process, daemon=True).start()

            _process_event.last_active = is_active

        else:
            # Combo Mode
            is_active = target_keys.issubset(currently_pressed)
            if getattr(engine, "_continuous_active", False):
                _process_event.last_active = is_active
                return

            if is_active and not getattr(_process_event, 'last_active', False):
                if mode == "push_to_talk":
                    if not engine.is_recording:
                         engine.start_recording(from_hotkey=True)
                elif mode == "toggle":
                    if engine.is_recording:
                        threading.Thread(target=engine.stop_and_process, daemon=True).start()
                    else:
                        engine.start_recording(from_hotkey=True)
            
            elif not is_active and getattr(_process_event, 'last_active', False):
                 if mode == "push_to_talk" and engine.is_recording:
                     threading.Thread(target=engine.stop_and_process, daemon=True).start()

            _process_event.last_active = is_active

    def handle_global_event(event):
        """Global monitor handler — does NOT return the event (void callback)"""
        try:
            _process_event(event)
        except Exception as e:
            print(f"⚠️ Global event handler error: {e}")
        # Global monitor handler must NOT return the event

    def handle_local_event(event):
        """Local monitor handler — MUST return the event (or None to swallow it)"""
        try:
            _process_event(event)
        except Exception as e:
            print(f"⚠️ Local event handler error: {e}")
        return event  # Always pass through

    # Add Global Monitor (Background) — only key events
    NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
        KEY_EVENT_MASK, handle_global_event
    )
    # Add Local Monitor (Foreground) — only key events
    NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
        KEY_EVENT_MASK, handle_local_event
    )

    # 提供 reset hook：watchdog fire（代表 keyUp 被吞）時清掉 stale press state，
    # 否則 closure 還以為使用者持續按著，下一次按會被吃掉。
    def _reset_hotkey_state():
        currently_pressed.clear()
        _process_event.last_active = False
        action_reset = getattr(engine, "_on_action_hotkey_reset", None)
        if action_reset:
            action_reset()
    engine._on_hotkey_reset = _reset_hotkey_state

    # NOTE: 曾經在這裡放過 _key_state_reconciler（polling thread + CGEventSourceKeyState /
    # NSEvent.modifierFlags），目的是補救漏掉的 keyUp / flagsChanged。實測 false positive
    # 太嚴重：背景 thread 拿到的 modifierFlags 不是 live state、CGEventSourceKeyState 對
    # modifier key 也不穩，會在使用者仍按著的時候誤判成已放開，把錄音切成 0.2~0.8s。
    # 已移除。漏事件的兜底改靠 _arm_watchdog（max_recording_duration，預設 30 分鐘）。
    # 想要更嚴格 cap 可在 config 設 pushtotalk_max_seconds。


def _setup_dynamic_action_hotkey(engine, config_key, action_callback, label):
    """Register an action in the shared, release-triggered NSEvent arbiter.

    Modifier-only action chords are prefixes of many normal shortcuts.  Firing
    on key-down would make ``ctrl+option+k`` invoke Quick-Rewrite before ``k``
    arrives.  The shared arbiter therefore arms one exact chord, invalidates it
    if any extra key joins the gesture, and invokes it only when the chord is
    released.  One latch is shared by every action, so modifier rollover cannot
    invoke a second action in the same gesture.
    """

    try:
        from AppKit import NSEvent, NSFlagsChanged, NSKeyDown, NSKeyUp
    except ImportError:
        return None

    registry = getattr(engine, "_action_hotkey_registry", None)
    if registry is None:
        registry = {}
        engine._action_hotkey_registry = registry
    registry[config_key] = (action_callback, label)

    existing_monitors = getattr(engine, "_action_hotkey_monitors", None)
    if existing_monitors is not None:
        own_source = str(engine.config.get(config_key, "") or "").strip()
        if own_source:
            log("ok", f"{label} hotkey: {own_source}")
        return existing_monitors

    hotkey_sources = None
    action_specs = {}
    relevant_keys = set()
    recording_keys = set()
    currently_pressed = set()
    foreign_pressed = set()
    armed_field = None
    armed_keys = set()
    armed_while_recording = False
    armed_recording_token = None
    gesture_blocked = False
    gesture_latched = False
    key_event_mask = (1 << 10) | (1 << 11) | (1 << 12)

    def _refresh_targets():
        nonlocal hotkey_sources, action_specs, relevant_keys, recording_keys
        nonlocal armed_field, armed_keys, armed_while_recording
        nonlocal armed_recording_token
        nonlocal gesture_blocked, gesture_latched
        action_sources = tuple(
            str(engine.config.get(field, "") or "").strip()
            for field in _ACTION_HOTKEY_FIELDS
        )
        recording_source = str(
            engine.config.get("hotkey", RECOMMENDED_RECORD_HOTKEY) or ""
        ).strip()
        next_sources = (recording_source, *action_sources)
        if next_sources == hotkey_sources:
            return
        hotkey_sources = next_sources
        currently_pressed.clear()
        foreign_pressed.clear()
        armed_field = None
        armed_keys = set()
        armed_while_recording = False
        armed_recording_token = None
        gesture_blocked = False
        gesture_latched = False
        action_specs = {}
        relevant_keys = set()
        recording_keys = set()
        try:
            recording_keys = set(
                parse_hotkey(
                    recording_source,
                    field="hotkey",
                    allow_legacy_single_modifier=True,
                ).keycodes
            )
        except HotkeyValidationError as exc:
            log("warn", f"Invalid hotkey: {exc}")
        for field, source in zip(_ACTION_HOTKEY_FIELDS, action_sources):
            try:
                parsed_keys = set(parse_hotkey(source, field=field).keycodes)
            except HotkeyValidationError as exc:
                log("warn", f"Invalid {field}: {exc}")
                continue
            action_specs[field] = parsed_keys
            relevant_keys.update(parsed_keys)

    def _on_event(event):
        nonlocal armed_field, armed_keys, armed_while_recording
        nonlocal armed_recording_token
        nonlocal gesture_blocked, gesture_latched
        _refresh_targets()
        try:
            event_type = event.type()
            keycode = event.keyCode()
        except Exception:
            return

        pressed_now = False
        if event_type == NSKeyDown:
            try:
                if event.isARepeat():
                    return
            except Exception:
                pass
            if keycode in relevant_keys:
                currently_pressed.add(keycode)
                pressed_now = True
            elif keycode not in recording_keys:
                foreign_pressed.add(keycode)
                pressed_now = True
        elif event_type == NSKeyUp:
            currently_pressed.discard(keycode)
            foreign_pressed.discard(keycode)
        elif event_type == NSFlagsChanged and keycode in relevant_keys:
            if modifier_is_pressed(keycode, event.modifierFlags()):
                currently_pressed.add(keycode)
                pressed_now = True
            else:
                currently_pressed.discard(keycode)
        elif event_type == NSFlagsChanged and keycode in recording_keys:
            # PTT is deliberately disjoint from action chords.  Ignore its
            # held modifiers so Cancel remains available during recording.
            # On generic-only KVMs, however, releasing a left-side action key
            # while its right-side PTT sibling remains held cannot be observed.
            # A recording-key event may safely *remove* action modifiers whose
            # generic family flag is now off; it must never add them here.
            flags = event.modifierFlags()
            for action_key in relevant_keys & MODIFIER_KEYCODES:
                if not modifier_is_pressed(action_key, flags):
                    currently_pressed.discard(action_key)
        elif event_type == NSFlagsChanged and keycode in MODIFIER_KEYCODES:
            if modifier_is_pressed(keycode, event.modifierFlags()):
                foreign_pressed.add(keycode)
                pressed_now = True
            else:
                foreign_pressed.discard(keycode)
        else:
            return

        if pressed_now and foreign_pressed and currently_pressed:
            gesture_blocked = True

        if gesture_latched:
            if not currently_pressed:
                gesture_latched = False
                gesture_blocked = False
                foreign_pressed.clear()
            return

        if armed_field is not None:
            if (currently_pressed - armed_keys) or foreign_pressed:
                gesture_blocked = True
            if armed_keys.issubset(currently_pressed):
                return

            callback_entry = registry.get(armed_field)
            should_run = not gesture_blocked and callback_entry is not None
            recording_now = bool(getattr(engine, "is_recording", False))
            if armed_while_recording or recording_now:
                should_run = should_run and (
                    armed_field == "cancel_hotkey"
                    or (
                        armed_field == "continuous_hotkey"
                        and bool(getattr(engine, "_continuous_active", False))
                    )
                )

            if should_run:
                callback, _callback_label = callback_entry
                callback_target = callback
                if (
                    armed_field == "cancel_hotkey"
                    and armed_recording_token is not None
                ):
                    marker = getattr(engine, "mark_cancel_intent", None)
                    if marker is not None:
                        if marker(armed_recording_token):
                            token = armed_recording_token
                            callback_target = (
                                lambda cb=callback, tok=token: cb(
                                    recording_token=tok
                                )
                            )
                        else:
                            should_run = False
                if should_run:
                    threading.Thread(
                        target=callback_target,
                        daemon=True,
                    ).start()

            armed_field = None
            armed_keys = set()
            armed_while_recording = False
            armed_recording_token = None
            gesture_latched = True
            if not currently_pressed:
                gesture_latched = False
                gesture_blocked = False
                foreign_pressed.clear()
            return

        if gesture_blocked or foreign_pressed or not currently_pressed:
            if not currently_pressed:
                gesture_blocked = False
                foreign_pressed.clear()
            return

        exact_matches = [
            field
            for field, keys in action_specs.items()
            if keys and keys == currently_pressed and field in registry
        ]
        if len(exact_matches) == 1:
            armed_field = exact_matches[0]
            armed_keys = set(currently_pressed)
            armed_while_recording = bool(getattr(engine, "is_recording", False))
            if armed_field == "cancel_hotkey":
                token_getter = getattr(
                    engine, "latest_cancellable_recording_token", None
                )
                if callable(token_getter):
                    armed_recording_token = token_getter()
                else:
                    armed_recording_token = (
                        getattr(engine, "_record_start_ts", None)
                        if armed_while_recording
                        else getattr(engine, "_stopping_recording_token", None)
                    )
            else:
                armed_recording_token = None
        elif len(exact_matches) > 1:
            # Validation normally makes this impossible; fail closed if a
            # hand-edited legacy config bypasses the Dashboard API.
            gesture_blocked = True

    def _global(event):
        try:
            _on_event(event)
        except Exception as exc:
            log("warn", f"{label} global handler: {exc}")

    def _local(event):
        try:
            _on_event(event)
        except Exception as exc:
            log("warn", f"{label} local handler: {exc}")
        return event

    _refresh_targets()
    global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
        key_event_mask, _global
    )
    local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
        key_event_mask, _local
    )
    monitors = (global_monitor, local_monitor)
    engine._action_hotkey_monitors = monitors

    def _reset_action_hotkey_state():
        nonlocal armed_field, armed_keys, armed_while_recording
        nonlocal armed_recording_token, gesture_blocked, gesture_latched
        currently_pressed.clear()
        foreign_pressed.clear()
        armed_field = None
        armed_keys = set()
        armed_while_recording = False
        armed_recording_token = None
        gesture_blocked = False
        gesture_latched = False

    engine._on_action_hotkey_reset = _reset_action_hotkey_state
    own_source = str(engine.config.get(config_key, "") or "").strip()
    if own_source:
        log("ok", f"{label} hotkey: {own_source}")
    return monitors


def setup_continuous_hotkey(engine):
    """連續模式 toggle 熱鍵（空字串=關閉）。"""
    return _setup_dynamic_action_hotkey(
        engine,
        "continuous_hotkey",
        engine.toggle_continuous_mode,
        "Continuous-mode",
    )


def setup_rewrite_hotkey(engine):
    """Quick-Rewrite 全域熱鍵：選取文字 → 觸發 → LLM 改寫 → 貼回。
    與其他 action 共用 NSEvent arbiter，預設 ctrl+option。"""
    return _setup_dynamic_action_hotkey(
        engine,
        "rewrite_hotkey",
        engine.rewrite_selection,
        "Quick-Rewrite",
    )


def _setup_action_hotkey(engine, config_key, action_callback, label):
    """共用：註冊全域 action，安全放開組合鍵後在背景執行 callback。
    config_key 為 None 或空字串時直接 noop（功能關閉）。"""
    return _setup_dynamic_action_hotkey(
        engine,
        config_key,
        action_callback,
        label,
    )


def setup_retry_hotkey(engine):
    """Retry hotkey：跳過 STT 重跑 LLM，貼上新版。預設 ctrl+shift。"""
    _setup_action_hotkey(engine, "retry_hotkey", engine.retry_last_transcription, "Retry")


def setup_cancel_hotkey(engine):
    """Cancel hotkey：錄音中或處理中按下 → 丟棄並回 idle。預設 ctrl+cmd。"""
    _setup_action_hotkey(engine, "cancel_hotkey", engine.cancel_current, "Cancel")


def _setup_hotkey_pynput(engine):
    """Dynamic pynput fallback using the same grammar as native NSEvent."""
    from pynput import keyboard

    special_names = {
        "fn": ("fn",),
        "cmd": ("cmd_l", "cmd"),
        "right_cmd": ("cmd_r",),
        "option": ("alt_l", "alt"),
        "right_option": ("alt_r", "alt_gr"),
        "ctrl": ("ctrl_l", "ctrl"),
        "right_ctrl": ("ctrl_r",),
        "shift": ("shift_l", "shift"),
        "right_shift": ("shift_r",),
        "space": ("space",),
        "escape": ("esc",),
    }
    for number in range(1, 13):
        special_names[f"f{number}"] = (f"f{number}",)

    def _token_for_key(key):
        if getattr(key, "vk", None) == FN_KEYCODE:
            return "fn"
        for token, names in special_names.items():
            for name in names:
                candidate = getattr(keyboard.Key, name, None)
                if candidate is not None and key == candidate:
                    return token
        char = getattr(key, "char", None)
        if isinstance(char, str) and len(char) == 1:
            return char.lower()
        return None

    hotkey_source = None
    target_tokens = set()
    currently_pressed = set()
    last_active = False

    def _refresh_target():
        nonlocal hotkey_source, target_tokens, last_active
        next_source = str(
            engine.config.get("hotkey", RECOMMENDED_RECORD_HOTKEY) or ""
        )
        if next_source == hotkey_source:
            return
        hotkey_source = next_source
        currently_pressed.clear()
        last_active = False
        try:
            target_tokens = set(
                parse_hotkey(
                    hotkey_source,
                    field="hotkey",
                    allow_legacy_single_modifier=True,
                ).tokens
            )
        except HotkeyValidationError as exc:
            log(
                "warn",
                f"Invalid pynput hotkey ({exc}); using "
                f"{RECOMMENDED_RECORD_HOTKEY}",
            )
            target_tokens = set(
                parse_hotkey(RECOMMENDED_RECORD_HOTKEY, field="hotkey").tokens
            )

    def _apply_active_state():
        nonlocal last_active
        is_active = bool(target_tokens) and target_tokens.issubset(
            currently_pressed
        )
        if getattr(engine, "_continuous_active", False):
            last_active = is_active
            return
        mode = engine.config.get("hotkey_mode", "push_to_talk")
        if is_active and not last_active:
            if mode == "push_to_talk":
                if not engine.is_recording:
                    engine.start_recording(from_hotkey=True)
            elif engine.is_recording:
                threading.Thread(
                    target=engine.stop_and_process, daemon=True
                ).start()
            else:
                engine.start_recording(from_hotkey=True)
        elif not is_active and last_active:
            if mode == "push_to_talk" and engine.is_recording:
                threading.Thread(
                    target=engine.stop_and_process, daemon=True
                ).start()
        last_active = is_active

    def on_press(key):
        _refresh_target()
        token = _token_for_key(key)
        if token in target_tokens:
            currently_pressed.add(token)
        _apply_active_state()

    def on_release(key):
        _refresh_target()
        token = _token_for_key(key)
        if token:
            currently_pressed.discard(token)
        _apply_active_state()

    _refresh_target()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()

    def _reset_hotkey_state():
        nonlocal last_active
        currently_pressed.clear()
        last_active = False
        action_reset = getattr(engine, "_on_action_hotkey_reset", None)
        if action_reset:
            action_reset()

    engine._on_hotkey_reset = _reset_hotkey_state
    return listener


# ─── CLI Mode ────────────────────────────────────────────

def run_cli():
    engine = VoiceEngine()
    _register_engine_for_cleanup(engine)
    config = engine.config

    if not config.get("openai_api_key"):
        print("⚠️  請先設定 OpenAI API Key")
        print("   執行: python app.py --dashboard")
        print("   或編輯: ~/.voice-input/config.json")
        return

    print("🎙  Voice Input — CLI 模式")
    print(f"   語言: {config.get('language', 'auto')}")
    print(f"   Claude 後處理: {'✅' if config.get('enable_claude_polish') else '❌'}")
    print(f"   翻譯模式: {config.get('target_language') or '關閉'}")
    print("─" * 50)
    print("按 Enter 開始錄音，再按 Enter 停止")
    print("指令: q=退出, d=開 Dashboard, t=翻譯模式, e=語音編輯\n")

    while True:
        cmd = input("▶ ").strip().lower()
        if cmd == "q":
            break
        if cmd == "d":
            _start_dashboard(config)
            continue

        mode = "dictate"
        edit_ctx = ""
        if cmd == "t":
            mode = "translate"
            print("🌐 翻譯模式")
        elif cmd == "e":
            mode = "edit"
            edit_ctx = input("📝 貼上要編輯的文字: ").strip()
            if not edit_ctx:
                continue

        print("🔴 錄音中... 按 Enter 停止")
        engine.start_recording()
        input()
        result = engine.stop_and_process(mode=mode, edit_context=edit_ctx, sync=True)

        if not result:
            print("⚠️  未偵測到音訊\n")
            continue

        # v2.4.0：transcribe() 只回傳 {raw, final, process_time}，沒有 corrected 中間欄位。
        # 之前印 result['corrected'] 每次都 KeyError crash → CLI mode 完全不可用。
        print(f"\n📝 Whisper: {result['raw']}")
        if result['final'] != result['raw']:
            print(f"✨ 後處理:  {result['final']}")
        print(f"✅ 最終: {result['final']}")
        print(f"⏱  耗時: {result['process_time']:.1f}s")

        # 手動修正 → 自動學習
        correction = input("✏️  修正 (Enter 跳過): ").strip()
        if correction and config.get("enable_auto_learn"):
            learned = engine.memory.learn_correction(result['final'], correction)
            if learned:
                for l in learned:
                    print(f"   📚 學到: {l['wrong']} → {l['right']}")
            paste_text(correction)
        print()


# ─── Clipboard Auto-Learn Observer ───────────────────────
def start_clipboard_observer(engine):
    """
    背景監聽剪貼簿變化，若使用者複製的文字與最後一次語音辨識非常相似，
    即判定為「使用者手動修正後複製」，自動萃取差異並加入詞庫。
    """
    try:
        from AppKit import NSPasteboard
    except ImportError:
        return  # 不在 macOS 或沒安裝 PyObjC

    pb = NSPasteboard.generalPasteboard()
    last_count = pb.changeCount()

    def _observer():
        nonlocal last_count
        from datetime import datetime
        while True:
            time.sleep(1.5)

            # Consume the pasteboard generation first, even while learning is disabled
            # or recording is active.  Otherwise an old copy event is processed later
            # as if it were a correction to a newer dictation.
            current_count = pb.changeCount()
            if current_count == last_count:
                continue
            last_count = current_count

            # Transactional insertion stages and restores the pasteboard itself.
            # Those exact generations are bookkeeping, not evidence that the user
            # edited and copied a transcript.  A later real copy has a new generation
            # and remains eligible for learning.
            if _consume_internal_pasteboard_generation(current_count):
                continue

            if not engine.config.get("enable_auto_learn", True):
                continue
            # 檢查有無新語音紀錄
            if getattr(engine, "is_recording", False):
                continue

            # 使用者最近一次的語音紀錄（含時間戳記）
            recent = engine.memory.get_history(n=1)
            if not recent:
                continue

            last_item = recent[0]
            last_dictated = last_item.get("final_text", "")
            last_ts_str = last_item.get("timestamp", "")

            if not last_dictated or len(last_dictated) < 4 or not last_ts_str:
                continue

            # 檢查時間視窗：最後一次口述必須在 300 秒（5 分鐘）內
            try:
                last_ts = datetime.fromisoformat(last_ts_str)
                if (datetime.now() - last_ts).total_seconds() > 300:
                    continue
            except Exception:
                continue

            # 讀取剪貼簿文字
            items = pb.pasteboardItems()
            if not items:
                continue
            copied_text = pb.stringForType_("public.utf8-plain-text")
            if not copied_text or not copied_text.strip():
                continue

            copied_text = copied_text.strip()

            # 若完全相同或差太多，不處理
            if copied_text == last_dictated:
                continue

            # 若只是標點差異，不視為修正（例如只是加了逗號）
            import re
            punc_pattern = r'[^\w\s]'
            c1 = re.sub(punc_pattern, '', last_dictated).strip()
            c2 = re.sub(punc_pattern, '', copied_text).strip()
            if c1 == c2:
                continue

            import difflib
            ratio = difflib.SequenceMatcher(None, last_dictated, copied_text).ratio()
            length_gap = abs(len(copied_text) - len(last_dictated)) / max(len(last_dictated), 1)

            # 只接受高度相似且長度接近的內容，避免把別段文字誤學成詞庫
            if 0.72 < ratio < 0.98 and length_gap <= 0.40:
                # Persist the verified correction first.  v2.5.4 only mutated the
                # in-memory last item, so edited=True was never written and few-shot
                # personalization always had zero trusted examples after restart.
                old_text = engine.memory.update_history_item(
                    last_ts_str, copied_text, source="clipboard",
                )
                if old_text is None:
                    continue
                learned = engine.memory.learn_correction(old_text, copied_text, source="clipboard")
                if learned:
                    updates = ", ".join([f"{item['wrong']}→{item['right']}" for item in learned])
                    print(f" 📚 由剪貼簿自動學習：{updates}")
                    notify(get_i18n("notif_learn_title"), f"{get_i18n('notif_learn_body')}{updates}")

    t = threading.Thread(target=_observer, daemon=True)
    t.start()


# ─── Menu Bar Mode ───────────────────────────────────────

def run_menubar():
    try:
        import rumps
    except ImportError:
        print("⚠️  rumps 未安裝，切換到 CLI 模式")
        print("   安裝: pip install rumps")
        run_cli()
        return

    engine = VoiceEngine()
    _register_engine_for_cleanup(engine)
    config = engine.config

    # 啟動時檢查輔助使用權限（自動貼上必需）
    try:
        if not request_accessibility_prompt():
            alert_body = get_i18n("alert_body")
            alert_btn = get_i18n("alert_btn")
            alert_title = get_i18n("alert_title")
            subprocess.Popen([
                "osascript", "-e",
                f'display dialog "{alert_body}" '
                f'buttons {{"{alert_btn}"}} default button 1 with title "{alert_title}" with icon caution',
                "-e",
                'tell application "System Settings" to activate',
                "-e",
                'open location "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _paste_log("啟動時偵測到無輔助使用權限，已彈出引導對話框")
    except Exception as e:
        _paste_log(f"輔助使用權限檢查失敗: {e}")

    class App(rumps.App):
        def __init__(self):
            self._menubar_icons = {
                "idle": _resource_path("resources", "menubar", "idleTemplate.png"),
                "recording": _resource_path(
                    "resources", "menubar", "recordingTemplate.png"
                ),
                "processing": _resource_path(
                    "resources", "menubar", "processingTemplate.png"
                ),
            }
            idle_icon = self._menubar_icons["idle"]
            super().__init__(
                "SGH Voice",
                title=None if os.path.exists(idle_icon) else "🎙",
                icon=idle_icon if os.path.exists(idle_icon) else None,
                template=True,
                quit_button=None,
            )
            self.record_item = rumps.MenuItem(get_i18n("menu_record"), callback=self.toggle_rec)
            self._status_lock = threading.Lock()
            self._pending_status = "idle"
            self._current_status = None
            self.menu = [
                rumps.MenuItem(get_i18n("menu_dashboard"), callback=self.open_dash),
                None,
                self.record_item,
                None,
                rumps.MenuItem(get_i18n("menu_quit"), callback=rumps.quit_application),
            ]

            # Status callback
            engine._on_status_change = self.queue_status
            self._status_timer = rumps.Timer(self.flush_status, 0.1)
            self._status_timer.start()

            # Start hotkey listener
            setup_hotkey(engine)

            # Start Quick-Rewrite hotkey listener (B)
            setup_rewrite_hotkey(engine)

            # Start Continuous-mode hotkey listener (C)
            setup_continuous_hotkey(engine)

            # Start Retry hotkey listener（重做最後一筆，跳過 STT）
            setup_retry_hotkey(engine)

            # Start Cancel hotkey listener（中止當前錄音/處理）
            setup_cancel_hotkey(engine)

            # Start Clipboard AI Learning observer
            start_clipboard_observer(engine)

            # 啟動橫幅
            port = config.get("dashboard_port", 7865)
            llm  = config.get("llm_engine", "groq")
            llm_model = config.get(f"{llm}_model", config.get("local_llm_model", "—"))
            stt  = config.get("stt_engine", "mlx-whisper")
            stt_model = config.get("local_whisper_model", "—") if stt == "mlx-whisper" else "Groq Whisper"
            log_sep("━")
            print(f"  {_c('bold', '🎙  SGH Voice')}  {_c('gray', 'v' + engine.version)}")
            print(f"  {_c('gray','STT')}  {stt}  {_c('dim', stt_model)}")
            print(f"  {_c('gray','LLM')}  {llm}  {_c('dim', llm_model)}")
            print(f"  {_c('gray','Dashboard')}  http://localhost:{port}")
            log_sep("━")

            # Start dashboard server in background
            _start_dashboard_bg(config, engine.memory, engine)

            # 延遲 1.5 秒啟動背景任務，避開 macOS 啟動時的 IMK 通訊高峰
            rumps.Timer(lambda t: (engine.start_background_tasks(), t.stop()), 1.5).start()

        def queue_status(self, s):
            with self._status_lock:
                self._pending_status = s

        def flush_status(self, _):
            with self._status_lock:
                status = self._pending_status
            if status != self._current_status:
                self._status(status)

        def _status(self, s):
            self._current_status = s
            if s == "recording":
                icon_key = "recording"
                self.record_item.title = get_i18n("menu_stop")
            elif s == "processing":
                icon_key = "processing"
                self.record_item.title = get_i18n("menu_processing")
            else:
                icon_key = "idle"
                self.record_item.title = get_i18n("menu_record")
            icon_path = self._menubar_icons.get(icon_key)
            if icon_path and os.path.exists(icon_path):
                self.icon = icon_path
                self.title = None
            else:
                self.icon = None
                self.title = {
                    "recording": "●",
                    "processing": "…",
                    "idle": "🎙",
                }[icon_key]

        def toggle_rec(self, sender):
            if engine.is_recording:
                threading.Thread(target=self._process, daemon=True).start()
            else:
                engine.start_recording()

        def _process(self):
            engine.stop_and_process()
            self.queue_status("idle")

        def open_dash(self, sender):
            port = config.get("dashboard_port", 7865)
            _open_dashboard_ui(port)

    app = App()
    app.run()


# ─── Dashboard ───────────────────────────────────────────

def _open_dashboard_ui(port):
    import subprocess
    import sys
    if getattr(sys, 'frozen', False):
        # 打包成 .app 後，sys.executable 指向 VoiceInput 二進位檔
        subprocess.Popen([sys.executable, "--webview", str(port)])
    else:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_window.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path, str(port)])
        else:
            webbrowser.open(f"http://127.0.0.1:{port}")


def _find_free_port(start_port=7865, max_port=7900):
        import socket
        for port in range(start_port, max_port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('127.0.0.1', port))
                    return port
                except OSError:
                    continue
        return start_port

def _start_dashboard_bg(config, shared_memory=None, engine=None):
    """背景啟動 Dashboard"""
    port = config.get("dashboard_port", 7865)
    port = _find_free_port(port)
    config["dashboard_port"] = port  # 讓其他部分也知道現在用哪個 port
    t = threading.Thread(target=_run_dashboard, args=(port, shared_memory, engine), daemon=True)
    t.start()
    time.sleep(1)
    _open_dashboard_ui(port)


def _run_dashboard(port, shared_memory=None, engine=None):
    from dashboard import run_dashboard, set_memory, set_engine
    if shared_memory:
        set_memory(shared_memory)
    if engine:
        set_engine(engine)
    run_dashboard(port)


def _start_dashboard(config):
    """前景啟動 Dashboard"""
    port = config.get("dashboard_port", 7865)
    port = _find_free_port(port)
    config["dashboard_port"] = port
    print(f"📊 Dashboard: http://localhost:{port}")
    _open_dashboard_ui(port)
    from dashboard import run_dashboard
    run_dashboard(port)


# ─── Entry Point ─────────────────────────────────────────

def main():
    # 確保 Ctrl+C / kill 時麥克風串流被乾淨關閉，避免 PortAudio 留下 leaked semaphore
    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    atexit.register(_graceful_shutdown)

    parser = argparse.ArgumentParser(description="🎙 Voice Input — AI 語音輸入工具")
    parser.add_argument("--cli", action="store_true", help="CLI 模式")
    parser.add_argument("--dashboard", action="store_true", help="只開 Dashboard")
    parser.add_argument("--webview", type=int, help="內部使用：以 Webview 視窗開啟指定 Port")
    args = parser.parse_args()

    if getattr(args, "webview", None):
        import webview
        url = f"http://127.0.0.1:{args.webview}"
        webview.create_window("Voice Input Dashboard", url, width=1100, height=850)
        webview.start()
        return

    if args.dashboard:
        config = load_config()
        _start_dashboard(config)
    elif args.cli:
        run_cli()
    else:
        run_menubar()


if __name__ == "__main__":
    main()
