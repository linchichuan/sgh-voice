"""
overlay.py — 浮動狀態窗口
模仿 Typeless / Superwhisper 的半透明浮動提示視窗
顯示錄音中 / 處理中 / 完成狀態
"""
import threading
import objc

try:
    import AppKit
    import Foundation
    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False


# 用於跨執行緒 UI 更新的 helper class
if HAS_APPKIT:
    class _Updater(AppKit.NSObject):
        """NSObject 子類，用 performSelectorOnMainThread 安全更新 UI"""

        def initWithOverlay_(self, overlay):
            self = objc.super(_Updater, self).init()
            if self is None:
                return None
            self._overlay = overlay
            self._pending_status = None
            return self

        def setStatus_(self, status):
            """從任何執行緒呼叫，排程到主執行緒執行"""
            self._pending_status = status
            self.performSelectorOnMainThread_withObject_waitUntilDone_(
                "applyUpdate:", None, True
            )

        @objc.python_method
        def _apply(self):
            """實際在主執行緒上更新 UI"""
            payload = self._pending_status
            if isinstance(payload, tuple) and len(payload) >= 2 and payload[0] == "__transcript__":
                self._overlay._do_show_transcript(payload[1], payload[2] if len(payload) > 2 else 2.5)
            else:
                self._overlay._do_update(payload)

        def applyUpdate_(self, _sender):
            self._apply()


class StatusOverlay:
    """浮動狀態視窗（macOS only，需要 PyObjC）"""

    def __init__(self):
        self._window = None
        self._label = None
        self._timer = None
        self._dot_count = 0
        self._updater = None

        if HAS_APPKIT:
            self._setup_window()

    def _get_texts(self):
        lang = "en"
        if HAS_APPKIT:
            langs = AppKit.NSLocale.preferredLanguages()
            if langs:
                l = langs[0].lower()
                if 'zh' in l:
                    if 'hant' in l or 'tw' in l or 'hk' in l:
                        lang = 'zh-TW'
                    else:
                        lang = 'zh-CN'
                elif 'ja' in l:
                    lang = 'ja'
        
        db = {
            'zh-TW': {'recording': '🔴  錄音中', 'processing': '⏳  辨識處理中', 'done': '✅  完成'},
            'zh-CN': {'recording': '🔴  录音中', 'processing': '⏳  识别处理中', 'done': '✅  完成'},
            'ja': {'recording': '🔴  録音中', 'processing': '⏳  認識処理中', 'done': '✅  完了'},
            'en': {'recording': '🔴  Recording', 'processing': '⏳  Processing', 'done': '✅  Done'},
        }
        return db[lang]

    def _setup_window(self):
        """建立半透明浮動視窗"""
        screen = AppKit.NSScreen.mainScreen()
        if not screen:
            return
        
        self.texts = self._get_texts()
        
        screen_frame = screen.frame()
        w, h = 180, 40
        x = (screen_frame.size.width - w) / 2
        # 將浮動視窗放到螢幕下方 (10% 高度)
        y = screen_frame.size.height * 0.10

        rect = Foundation.NSMakeRect(x, y, w, h)
        style = AppKit.NSWindowStyleMaskBorderless
        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, style, AppKit.NSBackingStoreBuffered, False
        )

        # 視窗屬性：最上層浮動、半透明、不接受滑鼠事件
        self._window.setLevel_(AppKit.NSStatusWindowLevel + 1)
        self._window.setOpaque_(False)
        self._window.setBackgroundColor_(AppKit.NSColor.clearColor())
        self._window.setHasShadow_(True)
        self._window.setIgnoresMouseEvents_(True)
        self._window.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
            AppKit.NSWindowCollectionBehaviorStationary
        )

        # 背景：毛玻璃與半透明設定
        content = self._window.contentView()
        effect_view = AppKit.NSVisualEffectView.alloc().initWithFrame_(content.bounds())
        effect_view.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )
        effect_view.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        effect_view.setMaterial_(AppKit.NSVisualEffectMaterialDark)
        effect_view.setState_(AppKit.NSVisualEffectStateActive)
        effect_view.setAlphaValue_(0.7)  # 讓背景更透明一點，透出背後的畫面
        effect_view.setWantsLayer_(True)
        effect_view.layer().setCornerRadius_(12.0)
        effect_view.layer().setMasksToBounds_(True)
        content.addSubview_(effect_view)

        # 文字標籤 (垂直置中：高度 40，字體 15，所以稍微往下推 10)
        label_rect = Foundation.NSMakeRect(0, 10, w, 20)
        self._label = AppKit.NSTextField.alloc().initWithFrame_(label_rect)
        self._label.setEditable_(False)
        self._label.setBordered_(False)
        self._label.setDrawsBackground_(False)
        self._label.setAlignment_(AppKit.NSTextAlignmentCenter)
        self._label.setTextColor_(AppKit.NSColor.whiteColor())
        self._label.setFont_(
            AppKit.NSFont.systemFontOfSize_weight_(15, AppKit.NSFontWeightMedium)
        )
        self._label.setStringValue_("")
        content.addSubview_(self._label)

        # 建立跨執行緒 updater
        self._updater = _Updater.alloc().initWithOverlay_(self)

    def show(self, status):
        """顯示狀態（thread-safe，可從任何執行緒呼叫）"""
        if not HAS_APPKIT or not self._window:
            return

        if threading.current_thread() is threading.main_thread():
            self._do_update(status)
        else:
            self._updater.setStatus_(status)

    def _do_update(self, status):
        """實際更新 UI（必須在主執行緒）"""
        if status == "recording":
            self._label.setStringValue_(self.texts["recording"] + "...")
            self._label.setTextColor_(AppKit.NSColor.whiteColor())
            self._window.orderFront_(None)
            self._start_animation(status)
        elif status == "processing":
            self._label.setStringValue_(self.texts["processing"] + "...")
            self._label.setTextColor_(
                AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.65, 0.82, 1.0, 1.0)
            )
            self._window.orderFront_(None)
            self._start_animation(status)
        elif status == "done":
            self._stop_animation()
            self._label.setStringValue_(self.texts["done"])
            self._label.setTextColor_(
                AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.82, 0.63, 1.0)
            )
            self._window.orderFront_(None)
            # 1.5 秒後自動隱藏
            Foundation.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                1.5, False, lambda t: self._window.orderOut_(None) if self._window else None
            )
        else:  # idle / hide
            self._stop_animation()
            self._window.orderOut_(None)

    def _start_animation(self, status):
        """動畫效果：... 跳動"""
        self._stop_animation()
        self._dot_count = 0
        prefix = self.texts["recording"] if status == "recording" else self.texts["processing"]

        def _animate(timer):
            self._dot_count = (self._dot_count + 1) % 4
            dots = "." * self._dot_count + "   "[self._dot_count:]
            if self._label:
                self._label.setStringValue_(f"{prefix}{dots}")

        self._timer = Foundation.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            0.5, True, _animate
        )

    def _stop_animation(self):
        if self._timer:
            self._timer.invalidate()
            self._timer = None

    # ─── 即時轉寫顯示（C 連續模式 / 一般模式皆可用）────────
    def show_transcript(self, text, duration=2.5):
        """顯示最近一段轉寫結果，N 秒後自動淡出。Thread-safe。"""
        if not HAS_APPKIT or not self._window or not text:
            return
        if threading.current_thread() is threading.main_thread():
            self._do_show_transcript(text, duration)
        else:
            # 透過 _updater 排程到主執行緒
            payload = ("__transcript__", text, duration)
            self._updater._pending_status = payload
            self._updater.performSelectorOnMainThread_withObject_waitUntilDone_(
                "applyUpdate:", None, True
            )

    def _do_show_transcript(self, text, duration):
        """主執行緒：拓寬視窗 + 顯示節錄文字 + 自動淡出。"""
        snippet = text.strip().replace("\n", " ")
        if len(snippet) > 70:
            snippet = snippet[:68] + "…"

        screen = AppKit.NSScreen.mainScreen()
        if not screen:
            return
        screen_frame = screen.frame()
        # 動態寬度：依文字長度估算（中文 ~16px / 字, 英文 ~9px）
        char_w = 16 if any(ord(c) > 0x4e00 for c in snippet) else 11
        w = max(280, min(560, len(snippet) * char_w + 60))
        h = 56
        x = (screen_frame.size.width - w) / 2
        y = screen_frame.size.height * 0.10
        self._window.setFrame_display_animate_(Foundation.NSMakeRect(x, y, w, h), True, False)

        # 重新置中 label
        self._label.setFrame_(Foundation.NSMakeRect(8, 16, w - 16, 24))
        self._label.setStringValue_(snippet)
        self._label.setTextColor_(
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.85, 0.95, 1.0, 1.0)
        )
        self._label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(13, AppKit.NSFontWeightRegular))
        self._stop_animation()
        self._window.orderFront_(None)

        Foundation.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            duration, False, lambda t: self._fade_out()
        )

    def _fade_out(self):
        if not self._window:
            return
        try:
            self._window.orderOut_(None)
            # 還原原本尺寸（180x40）以免下次 status 顯示時太寬
            screen = AppKit.NSScreen.mainScreen()
            if screen:
                sf = screen.frame()
                w, h = 180, 40
                x = (sf.size.width - w) / 2
                y = sf.size.height * 0.10
                self._window.setFrame_display_(Foundation.NSMakeRect(x, y, w, h), False)
                self._label.setFrame_(Foundation.NSMakeRect(0, 10, w, 20))
                self._label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(15, AppKit.NSFontWeightMedium))
        except Exception:
            pass
