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


def paste_text(text):
    """複製到剪貼簿 + Cmd+V 貼上，完成後還原原有剪貼簿內容"""
    if not text:
        return

    try:
        import pyperclip
    except ImportError:
        _paste_log("pyperclip not available")
        return

    # 記錄當前前景 App (協助除錯)
    try:
        from AppKit import NSWorkspace
        curr_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        app_info = f"{curr_app.localizedName()} ({curr_app.bundleIdentifier()})"
    except Exception:
        app_info = "Unknown"

    # 保存原有剪貼簿內容
    old_clipboard = None
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    try:
        pyperclip.copy(text)
        _paste_log(f"已複製到剪貼簿 [{app_info}]: {text[:50]}...")
    except Exception as e:
        _paste_log(f"Clipboard copy error: {e}")
        return

    # ★ 等待修飾鍵完全放開 (稍微增加到 0.6s)
    time.sleep(0.6)

    pasted = False

    # 檢查輔助使用權限
    is_trusted = False
    try:
        import ApplicationServices
        is_trusted = ApplicationServices.AXIsProcessTrusted()
    except Exception:
        is_trusted = None
    _paste_log(f"AXIsProcessTrusted={is_trusted}, app={app_info}")

    # 方法 1: Quartz CGEvent (最原生可靠，如果已授權)
    if is_trusted:
        try:
            from Quartz import (
                CGEventCreateKeyboardEvent, CGEventPost, kCGSessionEventTap,
                CGEventSetFlags, kCGEventFlagMaskCommand
            )
            V_KEYCODE = 9
            event_down = CGEventCreateKeyboardEvent(None, V_KEYCODE, True)
            CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
            event_up = CGEventCreateKeyboardEvent(None, V_KEYCODE, False)
            CGEventSetFlags(event_up, kCGEventFlagMaskCommand)
            
            # 使用兩次發送以提升成功率 (有時第一次會被忽略)
            for _ in range(1):
                CGEventPost(kCGSessionEventTap, event_down)
                time.sleep(0.02)
                CGEventPost(kCGSessionEventTap, event_up)
                time.sleep(0.05)
            
            pasted = True
            _paste_log("Quartz CGEvent 貼上發送完成")
        except Exception as e:
            _paste_log(f"CGEvent exception: {e}")

    # 方法 2: osascript System Events keystroke (傳統方法)
    if not pasted:
        try:
            # 確保 System Events 知道要對誰發送
            result = subprocess.run([
                "osascript", "-e",
                'tell application "System Events" to keystroke "v" using command down'
            ], capture_output=True, text=True, timeout=5)
            _paste_log(f"osascript returncode={result.returncode}")
            if result.returncode == 0:
                pasted = True
        except Exception as e:
            _paste_log(f"osascript exception: {e}")

    # 方法 3: AXValue 直接插入 (終極 fallback，限支援 Accessibility 的 App)
    if not pasted or (is_trusted and len(text) > 100):
        # 即使方法 1/2 "成功"，如果是長文也嘗試 AXValue 直接寫入 (速度更快，不依賴剪貼簿)
        try:
            escaped = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\r')
            result = subprocess.run([
                "osascript", "-e",
                f'tell application "System Events" to set value of attribute "AXValue" '
                f'of focused UI element of focused window of first application process '
                f'whose frontmost is true to "{escaped}"'
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                pasted = True
                _paste_log("AXValue 直接插入成功")
        except Exception as e:
            _paste_log(f"AXValue exception: {e}")

    _paste_log(f"最終結果: pasted={pasted}")

    if not pasted:
        _paste_log("全部方法失敗，文字保留在剪貼簿")
        notify("SGH Voice", "📋 文字已複製到剪貼簿，請手動貼上")
    elif old_clipboard is not None:
        def _restore():
            # 延遲還原剪貼簿，確保貼上動作已完成
            time.sleep(3.0)
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass
        threading.Thread(target=_restore, daemon=True).start()


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
        self.version = "1.9.7"
        self.config = load_config()
        self.memory = Memory()
        self.transcriber = Transcriber(self.config, self.memory)
        self.recorder = Recorder(self.config)
        self.overlay = StatusOverlay()
        self.is_recording = False
        self._on_status_change = None  # callback(status_str)

    def start_background_tasks(self):
        """主程式啟動後再跑背景任務，避免搶佔啟動時的系統資源"""
        if self.config.get("enable_hybrid_mode", True):
            print(get_i18n("log_warmup"))
            threading.Thread(target=self.transcriber.warmup, daemon=True).start()

    def reload_config(self):
        self.config = load_config()
        self.transcriber.config = self.config
        self.transcriber.reset_clients()
        self.recorder.config = self.config
        print(" 🔄 系統設定已重新載入")

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.overlay.show("recording")
        self._safe_status_change("recording")
        self.recorder.start()

    def _safe_status_change(self, status):
        """Thread-safe 狀態更新（rumps NSStatusItem 必須在 main thread 更新）"""
        if not self._on_status_change:
            return
        try:
            # 檢查是否在 main thread
            if threading.current_thread() is threading.main_thread():
                self._on_status_change(status)
            else:
                # 排程到 main thread（透過 rumps 的 timer 機制）
                import rumps
                rumps.Timer(lambda t: (self._on_status_change(status), t.stop()), 0.01).start()
        except Exception as e:
            print(f"Status change error (non-fatal): {e}")

    def stop_and_process(self, mode="dictate", edit_context=""):
        """停止錄音並處理（全面異常防護，避免 .app 閃退）"""
        if not self.is_recording:
            return None

        result = None
        try:
            # 獲取記憶體中的音訊數據與檔案路徑
            audio_array, filepath, duration = self.recorder.stop()
            self.is_recording = False

            self.overlay.show("processing")
            self._safe_status_change("processing")

            if audio_array is None and not filepath:
                self.overlay.show("idle")
                self._safe_status_change("idle")
                return None

            # 如果設定了翻譯目標語言，自動切換模式
            if self.config.get("target_language") and mode == "dictate":
                mode = "translate"

            # 傳入音訊數據 (audio_array) 而非檔案路徑，以極大化速度
            audio_input = audio_array if audio_array is not None else filepath
            result = self.transcriber.transcribe(audio_input, duration, mode, edit_context)

            if result:
                # 更新統計
                try:
                    update_stats(result["final"], duration, self.config)
                except Exception as e:
                    print(f"Stats update error (non-fatal): {e}")
                # 自動貼上
                if self.config.get("auto_paste"):
                    try:
                        paste_text(result["final"])
                    except Exception as e:
                        print(f"Paste error (non-fatal): {e}")
                self.overlay.show("done")
            else:
                self.overlay.show("idle")

            # 非同步處理存檔/備份，不阻塞主流程
            if filepath:
                def _backup():
                    try:
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
            # 全面防護：任何未預期的錯誤都不該讓 App 閃退
            print(f"❌ stop_and_process 發生未預期錯誤: {e}")
            import traceback
            traceback.print_exc()
            self.is_recording = False
            try:
                self.overlay.show("idle")
            except Exception:
                pass

        self._safe_status_change("idle")

        return result


# ─── Hotkey Listener ─────────────────────────────────────

def setup_hotkey(engine):
    """設定全域快捷鍵 (Native macOS NSEvent implementation to avoid pynput crash)"""
    try:
        from AppKit import NSEvent, NSKeyDown, NSKeyUp, NSFlagsChanged
        from Quartz import CGEventTapCreate, kCGSessionEventTap, kCGHeadInsertEventTap, kCGEventTapOptionListenOnly, CGEventTapEnable, CFMachPortCreateRunLoopSource, CFRunLoopAddSource, CFRunLoopGetCurrent, kCFRunLoopCommonModes
    except ImportError:
        # Fallback to pynput if PyObjC is not available (e.g. CLI mode without rumps)
        return _setup_hotkey_pynput(engine)

    config = engine.config
    hotkey_str = config.get("hotkey", "right_cmd")
    mode = config.get("hotkey_mode", "push_to_talk")
    
    # Key Code Mapping for macOS
    # https://github.com/phracker/MacOSX-SDKs/blob/master/MacOSX10.6.sdk/System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/HIToolbox.framework/Versions/A/Headers/Events.h
    KEY_MAP = {
        'right_cmd': 54,
        'cmd': 55, 'command': 55, 'cmd_l': 55, 'right_command': 54,
        'right_alt': 61, 'right_option': 61,
        'alt': 58, 'option': 58, 'alt_l': 58,
        'ctrl': 59, 'control': 59,
        'shift': 56, 'right_shift': 60,
        'space': 49,
        'f1': 122, 'f2': 120, 'f3': 99, 'f4': 118, 'f5': 96, 'f6': 97, 'f7': 98, 'f8': 100,
        'a': 0, 'b': 11, 'c': 8, 'd': 2, 'e': 14, 'f': 3, 'g': 5, 'h': 4, 'i': 34, 'j': 38,
        'k': 40, 'l': 37, 'm': 46, 'n': 45, 'o': 31, 'p': 35, 'q': 12, 'r': 15, 's': 1,
        't': 17, 'u': 32, 'v': 9, 'w': 13, 'x': 7, 'y': 16, 'z': 6
    }
    
    # Parse target keys
    target_keys = set()
    parts = hotkey_str.lower().replace("+", " ").split()
    for p in parts:
        if p in KEY_MAP:
            target_keys.add(KEY_MAP[p])
        elif len(p) == 1 and p in KEY_MAP: # chars
             target_keys.add(KEY_MAP[p])

    if not target_keys:
        print(f"⚠️ Unknown hotkey: {hotkey_str}, fallback to right_cmd")
        target_keys = {54}

    # Tracking state
    currently_pressed = set()
    
    # Event mask: only key events and flags changed (modifier keys)
    # NSKeyDownMask=1<<10, NSKeyUpMask=1<<11, NSFlagsChangedMask=1<<12
    KEY_EVENT_MASK = (1 << 10) | (1 << 11) | (1 << 12)

    def _process_event(event):
        """Core event processing logic (shared by global and local monitors)"""
        nonlocal currently_pressed
        try:
            etype = event.type()
            vk = event.keyCode()
        except Exception:
            return  # Not a valid NSEvent, skip

        # Update state
        if etype == NSKeyDown:
            currently_pressed.add(vk)
        elif etype == NSKeyUp:
            currently_pressed.discard(vk)
        elif etype == NSFlagsChanged:
            flags = event.modifierFlags()
            if vk in target_keys:
                is_pressed = False
                if vk == 54 or vk == 55:  # Cmd
                    is_pressed = (flags & 0x100000) > 0
                elif vk == 58 or vk == 61:  # Alt
                    is_pressed = (flags & 0x80000) > 0
                elif vk == 59 or vk == 62:  # Ctrl
                    is_pressed = (flags & 0x40000) > 0
                elif vk == 56 or vk == 60:  # Shift
                    is_pressed = (flags & 0x20000) > 0
                
                if is_pressed:
                    currently_pressed.add(vk)
                else:
                    currently_pressed.discard(vk)

        # Trigger Logic
        if len(target_keys) == 1:
            list_target = list(target_keys)[0]
            is_active = (list_target in currently_pressed)
            
            if is_active:
                 if not getattr(_process_event, 'last_active', False):  # Rising Edge
                     if mode == "push_to_talk":
                         if not engine.is_recording:
                             engine.start_recording()
                     elif mode == "toggle":
                         if engine.is_recording:
                             threading.Thread(target=engine.stop_and_process, daemon=True).start()
                         else:
                             engine.start_recording()
            else:
                 if getattr(_process_event, 'last_active', False):  # Falling Edge
                     if mode == "push_to_talk":
                         if engine.is_recording:
                             threading.Thread(target=engine.stop_and_process, daemon=True).start()
            
            _process_event.last_active = is_active
            
        else:
            # Combo Mode
            is_active = target_keys.issubset(currently_pressed)
            
            if is_active and not getattr(_process_event, 'last_active', False):
                if mode == "push_to_talk":
                    if not engine.is_recording:
                         engine.start_recording()
                elif mode == "toggle":
                    if engine.is_recording:
                        threading.Thread(target=engine.stop_and_process, daemon=True).start()
                    else:
                        engine.start_recording()
            
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


def _setup_hotkey_pynput(engine):
    """Fallback: use pynput (standard implementation)"""
    from pynput import keyboard
    config = engine.config
    hotkey_str = config.get("hotkey", "right_cmd")
    mode = config.get("hotkey_mode", "push_to_talk")

    # ... (Original pynput logic for fallback) ...
    # Minimal replication of original logic to save space and complexity if fallback needed
    # Only mapping right_cmd/right_alt specifically as requested
    if hotkey_str == "right_cmd":
        target = keyboard.Key.cmd_r
    elif hotkey_str == "right_alt":
        target = keyboard.Key.alt_r
    else:
        # Simple fallback for unknown keys in CLI mode: Cmd_R
        target = keyboard.Key.cmd_r

    def on_press(key):
        if key == target:
            if mode == "push_to_talk":
                if not engine.is_recording:
                    engine.start_recording()
            else:
                if engine.is_recording:
                    threading.Thread(target=engine.stop_and_process, daemon=True).start()
                else:
                    engine.start_recording()

    def on_release(key):
        if key == target and mode == "push_to_talk" and engine.is_recording:
            threading.Thread(target=engine.stop_and_process, daemon=True).start()

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()
    return listener


# ─── CLI Mode ────────────────────────────────────────────

def run_cli():
    engine = VoiceEngine()
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
        result = engine.stop_and_process(mode=mode, edit_context=edit_ctx)

        if not result:
            print("⚠️  未偵測到音訊\n")
            continue

        print(f"\n📝 Whisper: {result['raw']}")
        if result['corrected'] != result['raw']:
            print(f"📖 詞庫修正: {result['corrected']}")
        if result['final'] != result['corrected']:
            print(f"🤖 Claude:  {result['final']}")
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
        while True:
            time.sleep(1.5)
            # 檢查有無新語音紀錄
            if getattr(engine, "is_recording", False):
                continue
            
            # 使用者最近一次的語音輸出
            recent = engine.memory.get_recent_context(1)
            if not recent:
                continue
            last_dictated = recent[0]
            if len(last_dictated) < 4:
                continue

            current_count = pb.changeCount()
            if current_count != last_count:
                last_count = current_count
                
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
                
                import difflib
                ratio = difflib.SequenceMatcher(None, last_dictated, copied_text).ratio()
                
                # 若相似度介於 60% ~ 98%，視為人工修正版
                if 0.60 < ratio < 0.98:
                    learned = engine.memory.learn_correction(last_dictated, copied_text)
                    if learned:
                        updates = ", ".join([f"{item['wrong']}→{item['right']}" for item in learned])
                        print(f" 📚 由剪貼簿自動學習：{updates}")
                        notify(get_i18n("notif_learn_title"), f"{get_i18n('notif_learn_body')}{updates}")
                        
                        # 把歷史紀錄更新成正確版，避免重複學習與提供更好的上下文
                        for h in reversed(engine.memory.history):
                            if h.get("final_text") == last_dictated:
                                h["final_text"] = copied_text
                                break

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
    config = engine.config

    # 啟動時檢查輔助使用權限（自動貼上必需）
    try:
        from ApplicationServices import AXIsProcessTrusted
        if not AXIsProcessTrusted():
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
            super().__init__("🎙", quit_button=None)
            self.menu = [
                rumps.MenuItem(get_i18n("menu_dashboard"), callback=self.open_dash),
                None,
                rumps.MenuItem(get_i18n("menu_record"), callback=self.toggle_rec),
                None,
                rumps.MenuItem(get_i18n("menu_quit"), callback=rumps.quit_application),
            ]

            # Status callback
            engine._on_status_change = self._status

            # Start hotkey listener
            setup_hotkey(engine)
            
            # Start Clipboard AI Learning observer
            start_clipboard_observer(engine)

            # Start dashboard server in background
            _start_dashboard_bg(config, engine.memory, engine)

            # 延遲 1.5 秒啟動背景任務，避開 macOS 啟動時的 IMK 通訊高峰
            rumps.Timer(lambda t: (engine.start_background_tasks(), t.stop()), 1.5).start()

        def _status(self, s):
            if s == "recording":
                self.title = "🔴"
            elif s == "processing":
                self.title = "⏳"
            else:
                self.title = "🎙"

        def toggle_rec(self, sender):
            if engine.is_recording:
                threading.Thread(target=self._process, daemon=True).start()
            else:
                engine.start_recording()
                sender.title = "⏹ 停止錄音"

        def _process(self):
            engine.stop_and_process()
            self.menu["🎤 開始錄音"].title = "🎤 開始錄音"

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
