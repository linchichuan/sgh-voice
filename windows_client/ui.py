"""Native Windows preview UI. Worker callbacks only enqueue Python data.

Tk is imported only when the application is opened, allowing the queue and
settings boundary to be exercised without a display or Windows installation.
"""
from __future__ import annotations

import math
import queue
from copy import deepcopy


LABELS = {
    "en": {
        "title": "SGH Voice — Windows preview (not yet verified on Windows)",
        "intro": "Record, review, then copy. Use the global shortcut from your target application for optional insertion.",
        "record": "Record to preview", "stop": "Stop and transcribe", "cancel": "Cancel",
        "copy": "Copy text", "result": "Result — review before use", "level": "Microphone level",
        "settings": "Settings", "provider": "Cloud provider", "key": "API key",
        "key_hint": "Stored in Windows Credential Manager. No key is bundled with this application.",
        "language": "Speech language", "ui_language": "Interface language",
        "toggle_hotkey": "Record / stop shortcut", "cancel_hotkey": "Cancel shortcut",
        "consent": "I agree to send recorded audio and, for cleanup, transcript text to the selected provider.",
        "cloud_notice": "Groq or OpenAI receives your recordings. Existing provider API charges may apply. Windows offline speech recognition is not available in this preview.",
        "polish": "Clean up the transcript with the selected cloud provider",
        "auto_insert": "Allow insertion into the target captured by the global shortcut",
        "insert_notice": "Insertion requires the original target to remain focused. Otherwise the text stays here for manual copying. Sending a paste command does not confirm delivery.",
        "save_history": "Save transcript history on this computer",
        "history_notice": "History is off by default. Results remain visible until replaced or this window closes.",
        "save": "Save settings", "saved": "Settings saved.",
        "idle": "Ready", "recording": "Recording — press Stop or the shortcut again",
        "stopping": "Stopping recording…", "processing": "Transcribing / cleaning up…",
        "closed": "Closing…", "copied": "Copied to the clipboard. Paste into your chosen application.",
        "copy_failed": "Could not copy. Select the result and copy it manually.",
        "preview": "Text is ready for review and manual copying.",
        "paste_sent": "Paste command sent. Confirm the text in the target application; it is also retained here.",
        "paste_fallback": "Automatic insertion was not completed. Check the target for partial text before copying this result.",
        "hotkeys_ready": "Shortcuts active: {toggle} / cancel {cancel}",
        "hotkeys_failed": "Shortcuts unavailable. Check their format or whether another application uses them. Preview recording still works.",
        "save_failed": "Settings were not saved. Check Windows Credential Manager and access to the application data folder.",
        "invalid_settings": "Choose a supported provider / language and two distinct valid shortcuts.",
        "busy": "Wait until recording or processing finishes before changing settings.",
        "cloud_consent_required": "Save settings with cloud consent before recording.",
        "api_key_required": "Enter and save an API key for the selected provider before recording.",
        "invalid_provider": "Select Groq or OpenAI in Settings.",
        "microphone_failed": "Could not open the microphone. Check Windows microphone permissions and the default input device.",
        "audio_unavailable": "No usable audio was captured. Check the microphone and try again.",
        "transcription_failed": "Transcription failed. Check your connection, provider account, and API key, then record again.",
        "settings_failed": "Could not apply settings. Check your selections and save again.",
        "error": "The operation failed. Check the settings and try again.",
        "startup_failed": "SGH Voice could not start. Check the installation and application data access.",
        "dirty": "Settings changed — save before recording.",
    },
    "zh-TW": {
        "title": "SGH Voice — Windows 預覽版（尚未完成 Windows 實機驗收）",
        "intro": "錄音後先檢視文字，再複製。若要自動貼字，請從目標程式按全域快捷鍵開始。",
        "record": "錄音並預覽", "stop": "停止並辨識", "cancel": "取消",
        "copy": "複製文字", "result": "辨識結果 — 使用前請先確認", "level": "麥克風音量",
        "settings": "設定", "provider": "雲端供應商", "key": "API 金鑰",
        "key_hint": "金鑰存入 Windows 認證管理員。程式未附帶 API 金鑰。",
        "language": "語音語言", "ui_language": "介面語言",
        "toggle_hotkey": "錄音／停止快捷鍵", "cancel_hotkey": "取消快捷鍵",
        "consent": "我同意將錄音及整理所需的逐字稿傳送至選定的供應商。",
        "cloud_notice": "Groq 或 OpenAI 會接收您的錄音，可能產生既有供應商的 API 費用。此 Windows 預覽版尚無離線語音辨識。",
        "polish": "使用選定的雲端供應商整理逐字稿",
        "auto_insert": "允許貼入全域快捷鍵啟動時記錄的目標輸入框",
        "insert_notice": "貼字時原目標必須仍有焦點，否則文字保留於此供手動複製。送出貼上指令不代表已確認送達。",
        "save_history": "在本機儲存逐字稿歷史紀錄",
        "history_notice": "歷史紀錄預設關閉。結果會留在此視窗，直到被取代或關閉視窗。",
        "save": "儲存設定", "saved": "已儲存設定。",
        "idle": "就緒", "recording": "錄音中 — 按停止或再次按快捷鍵",
        "stopping": "正在停止錄音…", "processing": "正在辨識／整理…",
        "closed": "正在關閉…", "copied": "已複製至剪貼簿，請貼入您選擇的程式。",
        "copy_failed": "無法複製，請選取結果後手動複製。",
        "preview": "文字已保留，請確認後手動複製。",
        "paste_sent": "已送出貼上指令，請在目標程式確認文字；此處仍保留結果。",
        "paste_fallback": "未完成自動貼字。複製前請先檢查目標是否已有部分文字，避免重複貼入。",
        "hotkeys_ready": "快捷鍵啟用：{toggle}／取消 {cancel}",
        "hotkeys_failed": "無法啟用快捷鍵，請檢查格式或是否被其他程式占用。仍可使用視窗錄音預覽。",
        "save_failed": "未儲存設定，請檢查 Windows 認證管理員及程式資料夾的存取權限。",
        "invalid_settings": "請選擇支援的供應商／語言，以及兩組不同的有效快捷鍵。",
        "busy": "請等候錄音或處理完成後再更改設定。",
        "cloud_consent_required": "請先同意雲端傳送並儲存設定，再開始錄音。",
        "api_key_required": "請先輸入並儲存選定供應商的 API 金鑰，再開始錄音。",
        "invalid_provider": "請在設定中選擇 Groq 或 OpenAI。",
        "microphone_failed": "無法開啟麥克風，請檢查 Windows 麥克風權限及預設輸入裝置。",
        "audio_unavailable": "未取得可用音訊，請檢查麥克風後重試。",
        "transcription_failed": "辨識失敗，請檢查網路、供應商帳戶及 API 金鑰後重新錄音。",
        "settings_failed": "無法套用設定，請檢查選項後重新儲存。",
        "error": "操作失敗，請檢查設定後重試。",
        "startup_failed": "無法啟動 SGH Voice，請檢查安裝及程式資料存取權限。",
        "dirty": "設定已變更，錄音前請先儲存。",
    },
    "ja": {
        "title": "SGH Voice — Windows プレビュー（Windows 実機未検証）",
        "intro": "録音後に文字を確認してコピーしてください。自動入力は入力先のアプリでショートカットを押して開始します。",
        "record": "録音してプレビュー", "stop": "停止して文字起こし", "cancel": "キャンセル",
        "copy": "文字をコピー", "result": "結果 — 使用前に確認してください", "level": "マイク音量",
        "settings": "設定", "provider": "クラウドプロバイダー", "key": "API キー",
        "key_hint": "キーは Windows 資格情報マネージャーに保存されます。API キーは付属していません。",
        "language": "音声の言語", "ui_language": "表示言語",
        "toggle_hotkey": "録音／停止ショートカット", "cancel_hotkey": "キャンセルショートカット",
        "consent": "録音と、文章整理に必要な文字起こしを選択したプロバイダーに送信することに同意します。",
        "cloud_notice": "録音は Groq または OpenAI に送信され、既存の API 料金が発生する場合があります。この Windows プレビューではオフライン音声認識は利用できません。",
        "polish": "選択したクラウドプロバイダーで文章を整理する",
        "auto_insert": "ショートカット開始時の入力先への自動入力を許可する",
        "insert_notice": "入力時に元の入力先のフォーカスが必要です。変更された場合はここからコピーしてください。貼り付け操作の送信は入力完了の確認ではありません。",
        "save_history": "文字起こし履歴をこのパソコンに保存する",
        "history_notice": "履歴保存は初期設定でオフです。結果は置き換えられるか、このウィンドウを閉じるまで表示されます。",
        "save": "設定を保存", "saved": "設定を保存しました。",
        "idle": "準備完了", "recording": "録音中 — 停止ボタンかショートカットで停止",
        "stopping": "録音を停止しています…", "processing": "文字起こし／整理中…",
        "closed": "終了しています…", "copied": "クリップボードにコピーしました。入力先のアプリに貼り付けてください。",
        "copy_failed": "コピーできませんでした。結果を選択して手動でコピーしてください。",
        "preview": "文字を確認してコピーしてください。",
        "paste_sent": "貼り付け操作を送信しました。入力先で結果を確認してください。文字はここにも残ります。",
        "paste_fallback": "自動入力が完了しませんでした。コピーする前に、入力先に一部の文字が入っていないか確認してください。",
        "hotkeys_ready": "ショートカット有効：{toggle}／キャンセル {cancel}",
        "hotkeys_failed": "ショートカットを登録できません。形式と他のアプリとの競合を確認してください。録音ボタンは使用できます。",
        "save_failed": "設定を保存できません。Windows 資格情報マネージャーとアプリデータのアクセス権を確認してください。",
        "invalid_settings": "対応するプロバイダー、言語と、異なる有効なショートカットを選択してください。",
        "busy": "録音や処理が終了してから設定を変更してください。",
        "cloud_consent_required": "クラウド送信に同意して設定を保存してから録音してください。",
        "api_key_required": "選択したプロバイダーの API キーを保存してから録音してください。",
        "invalid_provider": "設定で Groq または OpenAI を選択してください。",
        "microphone_failed": "マイクを開けません。Windows のマイク権限と既定の入力機器を確認してください。",
        "audio_unavailable": "有効な音声がありません。マイクを確認して再試行してください。",
        "transcription_failed": "文字起こしに失敗しました。接続、プロバイダーのアカウント、API キーを確認して録音し直してください。",
        "settings_failed": "設定を適用できません。内容を確認して保存し直してください。",
        "error": "操作に失敗しました。設定を確認して再試行してください。",
        "startup_failed": "SGH Voice を起動できません。インストールとアプリデータへのアクセスを確認してください。",
        "dirty": "設定が変更されています。録音前に保存してください。",
    },
}


def interface_language(value):
    return value if value in LABELS else "zh-TW"


def result_message(payload):
    """Never infer successful text delivery from a sent paste command."""
    insertion = payload.get("insertion") or {}
    if insertion.get("success"):
        return "paste_sent"
    if insertion.get("reason") in (None, "", "preview_only", "auto_insert_disabled", "no_target"):
        return "preview"
    return "paste_fallback"


def settings_snapshot(current, values, keys):
    """Validate UI choices while preserving unrelated existing configuration."""
    provider = values.get("windows_provider")
    if (provider not in ("groq", "openai")
            or values.get("language") not in ("auto", "zh", "ja", "en")
            or values.get("ui_language") not in LABELS):
        raise ValueError("invalid_settings")
    toggle = values.get("windows_toggle_hotkey", "").strip()
    cancel = values.get("windows_cancel_hotkey", "").strip()
    if not toggle or not cancel or toggle.lower().replace(" ", "") == cancel.lower().replace(" ", ""):
        raise ValueError("invalid_settings")
    updated = deepcopy(current)
    updated.update(values)
    updated.update(windows_toggle_hotkey=toggle, windows_cancel_hotkey=cancel)
    for key_provider in ("groq", "openai"):
        # Empty input means keep the saved credential, matching config.save_config.
        value = keys.get(key_provider, "").strip()
        if value:
            updated[f"{key_provider}_api_key"] = value
    return updated


class WindowsApp:
    """Single Tk-thread owner; providers, microphone and hotkeys use a queue."""

    def __init__(self, root, config, *, controller_factory, native, hotkeys_factory,
                 save_config, validate_hotkey=None):
        self.root = root
        self.config = deepcopy(config)
        self.native = native
        self.hotkeys_factory = hotkeys_factory
        self.save_config = save_config
        self.validate_hotkey = validate_hotkey
        self.events = queue.SimpleQueue()
        self.closed = False
        self.hotkeys = None
        self._after_id = None
        self._close_after_id = None
        self._key_provider = config.get("windows_provider", "groq")
        self._key_drafts = {provider: config.get(f"{provider}_api_key", "") for provider in ("groq", "openai")}
        self.lang = interface_language(config.get("ui_language"))
        self._status_key = "idle"
        self._notice_key = ""
        self._hotkeys_ready = False
        self._dirty = False
        self._drop_results = False
        self._build()
        self.controller = controller_factory(self.config, self.enqueue, native=native)
        self._render_state()
        self._start_hotkeys()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._after_id = root.after(40, self._pump)

    def tr(self, key):
        return LABELS[self.lang].get(key, LABELS[self.lang]["error"])

    def enqueue(self, event, payload=None):
        # Never read Tk variables, focus a window, or call root.after here.
        if not self.closed:
            self.events.put((event, payload))

    def _build(self):
        import tkinter as tk
        from tkinter import ttk

        self.root.title(self.tr("title"))
        self.root.geometry("850x830")
        self.root.minsize(850, 650)
        shell = ttk.Frame(self.root)
        shell.pack(fill="both", expand=True)
        canvas = tk.Canvas(shell, highlightthickness=0)
        page_scroll = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        page_scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=page_scroll.set)
        frame = ttk.Frame(canvas, padding=16)
        page = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(page, width=event.width))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(4, weight=1)
        self._labels = []

        def label(parent, key, **kwargs):
            widget = ttk.Label(parent, text=self.tr(key), **kwargs)
            self._labels.append((widget, key))
            return widget

        label(frame, "intro", wraplength=790).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.status = tk.StringVar(value=self.tr("idle"))
        ttk.Label(frame, textvariable=self.status, font=("Segoe UI", 12, "bold")).grid(row=1, column=0, sticky="w")
        controls = ttk.Frame(frame)
        controls.grid(row=2, column=0, sticky="ew", pady=8)
        self.record_button = ttk.Button(controls, text=self.tr("record"), command=self._toggle_preview)
        self.record_button.pack(side="left")
        self.cancel_button = ttk.Button(controls, text=self.tr("cancel"), command=self._cancel)
        self.cancel_button.pack(side="left", padx=8)
        self._labels.append((self.cancel_button, "cancel"))
        label(controls, "level").pack(side="left", padx=(8, 4))
        self.meter = ttk.Progressbar(controls, maximum=1.0, length=140, mode="determinate")
        self.meter.pack(side="left")
        label(frame, "result").grid(row=3, column=0, sticky="w")
        result_frame = ttk.Frame(frame)
        result_frame.grid(row=4, column=0, sticky="nsew", pady=(4, 6))
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)
        self.result = tk.Text(result_frame, height=7, wrap="word", font=("Segoe UI", 11), undo=True)
        self.result.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(result_frame, orient="vertical", command=self.result.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.result.configure(yscrollcommand=scroll.set)
        self.copy_button = ttk.Button(frame, text=self.tr("copy"), command=self._copy)
        self.copy_button.grid(row=5, column=0, sticky="w")
        self._labels.append((self.copy_button, "copy"))
        self.notice = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.notice, wraplength=790).grid(row=6, column=0, sticky="ew", pady=(5, 8))

        # The containing page scrolls when Windows text scaling needs more room.
        self.settings_frame = ttk.LabelFrame(frame, text=self.tr("settings"), padding=8)
        self.settings_frame.grid(row=7, column=0, sticky="ew")
        self._labels.append((self.settings_frame, "settings"))
        self.settings_frame.columnconfigure(1, weight=1)
        self.vars = {}
        self._setting_widgets = []
        fields = (
            ("windows_provider", "provider", ("groq", "openai"), "groq"),
            ("language", "language", ("auto", "zh", "ja", "en"), "auto"),
            ("ui_language", "ui_language", ("zh-TW", "ja", "en"), self.lang),
        )
        for row, (field, key, choices, default) in enumerate(fields):
            label(self.settings_frame, key).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            value = self.config.get(field, default)
            self.vars[field] = tk.StringVar(value=value if value in choices else default)
            combo = ttk.Combobox(self.settings_frame, textvariable=self.vars[field], values=choices, state="readonly", width=20)
            combo.grid(row=row, column=1, sticky="ew", pady=3)
            self._setting_widgets.append((combo, "readonly"))
            if field == "windows_provider":
                combo.bind("<<ComboboxSelected>>", self._provider_changed)
        label(self.settings_frame, "key").grid(row=3, column=0, sticky="w")
        self.key_var = tk.StringVar(value=self._key_drafts.get(self._key_provider, ""))
        key_entry = ttk.Entry(self.settings_frame, textvariable=self.key_var, show="•")
        key_entry.grid(row=3, column=1, sticky="ew", pady=3)
        self._setting_widgets.append((key_entry, "normal"))
        label(self.settings_frame, "key_hint", wraplength=760).grid(row=4, column=0, columnspan=2, sticky="w")
        for row, field, key, default in (
                (5, "windows_toggle_hotkey", "toggle_hotkey", "Ctrl+Alt+F9"),
                (6, "windows_cancel_hotkey", "cancel_hotkey", "Ctrl+Alt+F10")):
            label(self.settings_frame, key).grid(row=row, column=0, sticky="w", padx=(0, 8))
            self.vars[field] = tk.StringVar(value=self.config.get(field, default))
            entry = ttk.Entry(self.settings_frame, textvariable=self.vars[field])
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self._setting_widgets.append((entry, "normal"))
        self.hotkey_notice = tk.StringVar()
        ttk.Label(self.settings_frame, textvariable=self.hotkey_notice, wraplength=760).grid(row=7, column=0, columnspan=2, sticky="w", pady=(3, 6))
        label(self.settings_frame, "cloud_notice", wraplength=760).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        for row, field, key, default in (
                (9, "windows_cloud_consent", "consent", False),
                (10, "windows_polish", "polish", True),
                (11, "windows_auto_insert", "auto_insert", False),
                (13, "windows_save_history", "save_history", False)):
            self.vars[field] = tk.BooleanVar(value=bool(self.config.get(field, default)))
            check = ttk.Checkbutton(self.settings_frame, text=self.tr(key), variable=self.vars[field])
            check.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
            self._labels.append((check, key))
            self._setting_widgets.append((check, "normal"))
        label(self.settings_frame, "insert_notice", wraplength=760).grid(row=12, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        label(self.settings_frame, "history_notice", wraplength=760).grid(row=14, column=0, columnspan=2, sticky="ew")
        self.save_button = ttk.Button(self.settings_frame, text=self.tr("save"), command=self._save)
        self.save_button.grid(row=15, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._labels.append((self.save_button, "save"))
        for variable in (*self.vars.values(), self.key_var):
            variable.trace_add("write", self._mark_dirty)

    def _mark_dirty(self, *_):
        self._dirty = True
        self._set_notice("dirty")

    def _provider_changed(self, _event=None):
        provider = self.vars["windows_provider"].get()
        if provider == self._key_provider:
            return
        self._key_drafts[self._key_provider] = self.key_var.get()
        self._key_provider = provider
        self.key_var.set(self._key_drafts.get(provider, ""))
        # Changing recipients always requires a fresh explicit consent action.
        self.vars["windows_cloud_consent"].set(False)

    def _set_notice(self, key):
        self._notice_key = key
        self.notice.set(self.tr(key) if key else "")

    def _render_state(self):
        state = self.controller.state
        self._status_key = state if state in ("idle", "recording", "stopping", "processing", "closed") else "idle"
        self.status.set(self.tr(self._status_key))
        self.record_button.configure(text=self.tr("stop" if state == "recording" else "record"), state="normal" if state in ("idle", "recording") else "disabled")
        self.cancel_button.configure(state="normal" if state in ("recording", "stopping", "processing") else "disabled")
        self.save_button.configure(state="normal" if state == "idle" else "disabled")
        for widget, enabled_state in self._setting_widgets:
            widget.configure(state=enabled_state if state == "idle" else "disabled")
        if state != "recording":
            self.meter.configure(value=0)

    def _toggle_preview(self):
        self._toggle(None)

    def _toggle(self, target):
        if self._dirty and self.controller.state == "idle":
            self._set_notice("dirty")
            return
        was_idle = self.controller.state == "idle"
        accepted = self.controller.toggle(target=target)
        if accepted and was_idle:
            self._drop_results = False
            self.result.delete("1.0", "end")
            self._set_notice("")
        self._render_state()

    def _cancel(self):
        self._drop_results = True
        self.controller.cancel()
        self.result.delete("1.0", "end")
        self._set_notice("")
        self._render_state()

    def _copy(self):
        value = self.result.get("1.0", "end-1c")
        if not value.strip():
            return
        try:
            copied = self.native.copy_text(value)
            if copied is False:
                raise RuntimeError("copy_failed")
        except Exception:
            self._set_notice("copy_failed")
            return
        self._set_notice("copied")

    def _start_hotkeys(self):
        self._hotkeys_ready = False
        try:
            if self.hotkeys is not None:
                self.hotkeys.stop()
                self.hotkeys = None
            hotkeys = self.hotkeys_factory(
                on_toggle=self._capture_hotkey_target,
                on_cancel=lambda: self.enqueue("cancel_hotkey"),
                on_error=lambda _error: self.enqueue("hotkey_error"),
            )
            self.hotkeys = hotkeys
            hotkeys.start(self.config["windows_toggle_hotkey"], self.config["windows_cancel_hotkey"])
            self._hotkeys_ready = True
        except Exception:
            self._hotkeys_ready = False
        self._render_hotkeys()

    def _capture_hotkey_target(self):
        # Called by the hotkey thread before any focus-changing UI activity.
        try:
            target = self.native.capture_target()
        except Exception:
            target = None
        self.enqueue("toggle_hotkey", target)

    def _render_hotkeys(self):
        message = self.tr("hotkeys_ready").format(toggle=self.config["windows_toggle_hotkey"], cancel=self.config["windows_cancel_hotkey"]) if self._hotkeys_ready else self.tr("hotkeys_failed")
        self.hotkey_notice.set(message)

    def _save(self):
        if self.controller.state != "idle":
            self._set_notice("busy")
            return
        try:
            self._key_drafts[self._key_provider] = self.key_var.get()
            updated = settings_snapshot(self.config, {field: variable.get() for field, variable in self.vars.items()}, self._key_drafts)
            if self.validate_hotkey:
                toggle = self.validate_hotkey(updated["windows_toggle_hotkey"])
                cancel = self.validate_hotkey(updated["windows_cancel_hotkey"])
                if toggle == cancel:
                    raise ValueError("invalid_settings")
        except Exception:
            self._set_notice("invalid_settings")
            return
        try:
            self.save_config(updated)
        except Exception:
            # Never expose exception text: a storage/provider error may contain a key.
            self._set_notice("save_failed")
            return
        try:
            self.controller.apply_config(updated)
        except Exception:
            self._set_notice("settings_failed")
            return
        self.config = updated
        self._dirty = False
        self.lang = interface_language(updated["ui_language"])
        self.root.title(self.tr("title"))
        for widget, key in self._labels:
            widget.configure(text=self.tr(key))
        self._render_state()
        self._start_hotkeys()
        self._set_notice("saved")

    def _pump(self):
        if self.closed:
            return
        # Bound one pass so a busy microphone cannot starve native UI events.
        for _ in range(256):
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "toggle_hotkey":
                self._toggle(payload)
            elif event == "cancel_hotkey":
                self._cancel()
            elif event == "hotkey_error":
                self._hotkeys_ready = False
                self._render_hotkeys()
            elif event == "status":
                self._render_state()
            elif event == "level":
                try:
                    level = float(payload)
                except (ValueError, TypeError):
                    continue
                if self.controller.state == "recording" and math.isfinite(level):
                    self.meter.configure(value=max(0.0, min(1.0, level)))
            elif event == "result" and isinstance(payload, dict):
                if self._drop_results or payload.get("text") != self.controller.last_text:
                    continue
                self.result.delete("1.0", "end")
                self.result.insert("1.0", payload.get("text", ""))
                self._set_notice(result_message(payload))
                self._render_state()
            elif event == "error":
                self._set_notice(payload if isinstance(payload, str) and payload in LABELS[self.lang] else "error")
                self._render_state()
        self._after_id = self.root.after(40, self._pump)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
        self.status.set(self.tr("closed"))
        for widget in (self.record_button, self.cancel_button, self.save_button, self.copy_button):
            widget.configure(state="disabled")
        for widget, _enabled_state in self._setting_widgets:
            widget.configure(state="disabled")
        self.meter.configure(value=0)
        self.result.delete("1.0", "end")
        try:
            self.controller.close()
        finally:
            try:
                if self.hotkeys is not None:
                    self.hotkeys.stop()
            except Exception:
                self._hotkeys_ready = False
                self._render_hotkeys()
            finally:
                self._wait_for_close()

    def _wait_for_close(self):
        # The speech worker owns temporary audio cleanup. Keep the event loop
        # alive until it has finished its cancelled operation and removed audio.
        if self.controller.state == "closed":
            self.root.destroy()
        else:
            self._close_after_id = self.root.after(50, self._wait_for_close)


def run():
    import tkinter as tk
    from tkinter import messagebox

    from config import load_config, save_config
    from windows_client.controller import Controller, WINDOWS_DEFAULTS
    from windows_client.hotkeys import GlobalHotkeys, Hotkey
    from windows_client.native import WindowsNative

    root = tk.Tk()
    root.withdraw()
    try:
        config = {**WINDOWS_DEFAULTS, **load_config()}
        WindowsApp(root, config, controller_factory=Controller, native=WindowsNative(),
                   hotkeys_factory=GlobalHotkeys, save_config=save_config,
                   validate_hotkey=Hotkey.parse)
    except Exception:
        messagebox.showerror("SGH Voice", LABELS["en"]["startup_failed"], parent=root)
        root.destroy()
        return 1
    root.deiconify()
    root.mainloop()
    return 0
