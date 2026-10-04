"""Native Windows preview UI. Worker callbacks only enqueue Python data.

Tk is imported only when the application is opened, allowing the queue and
settings boundary to be exercised without a display or Windows installation.
"""
from __future__ import annotations

import math
import ntpath
import os
import queue
from copy import deepcopy


LABELS = {
    'en': {
        'title': 'SGH Voice — Windows preview (not yet verified on Windows)',
        'intro': 'Record, review, then copy. Use the global shortcut from your target application for optional insertion.',
        'record': 'Record to preview',
        'stop': 'Stop and transcribe',
        'cancel': 'Cancel',
        'copy': 'Copy text',
        'result': 'Result — review before use',
        'level': 'Microphone level',
        'settings': 'Settings',
        'language': 'Speech language (ja / zh / en)',
        'ui_language': 'Interface language',
        'toggle_hotkey': 'Record / stop shortcut',
        'cancel_hotkey': 'Cancel shortcut',
        'auto_insert': 'Allow insertion into the target captured by the global shortcut',
        'insert_notice': 'Insertion requires the original target to remain focused. Sending an input command does not confirm delivery. Copied or inserted text follows the destination app’s data handling; other local clipboard tools may read copied text.',
        'save_history': 'Save transcript history on this computer',
        'history_notice': 'History is off by default. Results remain visible until replaced or this window closes.',
        'save': 'Save settings',
        'saved': 'Settings saved.',
        'idle': 'Ready',
        'recording': 'Recording — press Stop or the shortcut again',
        'stopping': 'Stopping recording…',
        'processing': 'Transcribing locally…',
        'closed': 'Closing…',
        'copied': 'Copied to the clipboard. Paste into your chosen application.',
        'copy_failed': 'Could not copy. Select the result and copy it manually.',
        'preview': 'Text is ready for review and manual copying.',
        'paste_sent': 'Paste command sent. Confirm the text in the target application; it is also retained here.',
        'paste_fallback': 'Automatic insertion was not completed. Check the target for partial text before copying this result.',
        'hotkeys_ready': 'Shortcuts active: {toggle} / cancel {cancel}',
        'hotkeys_failed': 'Shortcuts unavailable. Check their format or whether another application uses them. Preview recording still works.',
        'save_failed': 'Settings were not saved. Check access to the application data folder.',
        'invalid_settings': 'Choose a supported language, an absolute model folder path, and two distinct valid shortcuts.',
        'busy': 'Wait until recording, processing, or model preparation finishes before changing settings.',
        'microphone_failed': 'Could not open the microphone. Check Windows microphone permissions and the default input device.',
        'audio_unavailable': 'No usable audio was captured. Check the microphone and try again.',
        'transcription_failed': 'Local transcription failed. Check the model and microphone, then record again.',
        'settings_failed': 'Could not apply settings. Check your selections and save again.',
        'error': 'The operation failed. Check the settings and try again.',
        'startup_failed': 'SGH Voice could not start. Check the installation and application data access.',
        'dirty': 'Settings changed — save before recording.',
        'model_dir': 'Local model folder',
        'browse': 'Choose folder…',
        'model_source': 'Model source / files',
        'prepare_model': 'Download local model…',
        'offline_notice': 'Speech recognition runs on this computer’s CPU. SGH Voice does not upload recordings or transcripts for recognition. No cloud fallback or API key is used.',
        'model_required': 'A local speech model is required. Choose a prepared model folder, or explicitly download the model before recording.',
        'model_invalid': 'The selected model folder is incomplete or unsupported. Choose a prepared model folder.',
        'model_load_failed': 'Could not load the local model. Check the model files, available memory, and the installed CPU runtime.',
        'model_missing': 'The local model is missing. Choose a prepared model folder or download the model.',
        'model_metadata_unavailable': 'Model download details are unavailable. You can still choose an already prepared model folder.',
        'model_selected': 'Selected model folder: {path}. Files are checked before recording.',
        'model_details': '{name} · {size}\nSource: {source}',
        'model_download_confirm': 'Download {name} now?\n\nSource: {source}\nDownload size: {size}\n\nThis one-time public model download uses your internet connection and disk space. No recording or transcript is uploaded. Recording afterward works locally. Nothing downloads unless you confirm.',
        'model_download_failed': 'Model preparation failed. Check disk space and your connection, then retry. No cloud recognition was used.',
        'model_download_cancelled': 'Model preparation was cancelled. No cloud recognition was used.',
        'model_ready': 'Model prepared and settings saved.',
        'model_progress': 'Preparing the local model… {progress}',
        'preparing_model': 'Preparing the local model…',
        'lexicon_enabled': 'Show local Japanese psychiatry term candidates for manual review',
        'lexicon_notice': 'Term candidates do not rewrite the transcript or establish clinical meaning. Verify the wording and context before editing or using the result.',
        'lexicon_candidates': 'Term candidates — review only',
        'loading_model': 'Loading the local model…',
    },
    'zh-TW': {
        'title': 'SGH Voice — Windows 預覽版（尚未完成 Windows 實機驗收）',
        'intro': '錄音後先檢視文字，再複製。若要自動貼字，請從目標程式按全域快捷鍵開始。',
        'record': '錄音並預覽',
        'stop': '停止並辨識',
        'cancel': '取消',
        'copy': '複製文字',
        'result': '辨識結果 — 使用前請先確認',
        'level': '麥克風音量',
        'settings': '設定',
        'language': '語音語言（ja／zh／en）',
        'ui_language': '介面語言',
        'toggle_hotkey': '錄音／停止快捷鍵',
        'cancel_hotkey': '取消快捷鍵',
        'auto_insert': '允許貼入全域快捷鍵啟動時記錄的目標輸入框',
        'insert_notice': '貼字時原目標必須仍有焦點；送出輸入指令不代表已確認送達。複製或貼入後的資料處理依目標程式而定，其他本機剪貼簿工具也可能讀取已複製的文字。',
        'save_history': '在本機儲存逐字稿歷史紀錄',
        'history_notice': '歷史紀錄預設關閉。結果會留在此視窗，直到被取代或關閉視窗。',
        'save': '儲存設定',
        'saved': '已儲存設定。',
        'idle': '就緒',
        'recording': '錄音中 — 按停止或再次按快捷鍵',
        'stopping': '正在停止錄音…',
        'processing': '正在本機辨識…',
        'closed': '正在關閉…',
        'copied': '已複製至剪貼簿，請貼入您選擇的程式。',
        'copy_failed': '無法複製，請選取結果後手動複製。',
        'preview': '文字已保留，請確認後手動複製。',
        'paste_sent': '已送出貼上指令，請在目標程式確認文字；此處仍保留結果。',
        'paste_fallback': '未完成自動貼字。複製前請先檢查目標是否已有部分文字，避免重複貼入。',
        'hotkeys_ready': '快捷鍵啟用：{toggle}／取消 {cancel}',
        'hotkeys_failed': '無法啟用快捷鍵，請檢查格式或是否被其他程式占用。仍可使用視窗錄音預覽。',
        'save_failed': '未儲存設定，請檢查程式資料夾的存取權限。',
        'invalid_settings': '請選擇支援的語言、模型資料夾完整路徑，以及兩組不同的有效快捷鍵。',
        'busy': '請等候錄音、辨識或模型準備完成後再更改設定。',
        'microphone_failed': '無法開啟麥克風，請檢查 Windows 麥克風權限及預設輸入裝置。',
        'audio_unavailable': '未取得可用音訊，請檢查麥克風後重試。',
        'transcription_failed': '本機辨識失敗，請檢查模型與麥克風後重新錄音。',
        'settings_failed': '無法套用設定，請檢查選項後重新儲存。',
        'error': '操作失敗，請檢查設定後重試。',
        'startup_failed': '無法啟動 SGH Voice，請檢查安裝及程式資料存取權限。',
        'dirty': '設定已變更，錄音前請先儲存。',
        'model_dir': '本機模型資料夾',
        'browse': '選擇資料夾…',
        'model_source': '模型來源／檔案',
        'prepare_model': '下載本機模型…',
        'offline_notice': '語音辨識在此電腦的 CPU 執行。SGH Voice 不會上傳錄音或逐字稿進行辨識，也不會退回雲端或使用 API 金鑰。',
        'model_required': '尚需本機語音模型。請選擇已準備的模型資料夾，或明確點選下載模型後再錄音。',
        'model_invalid': '選取的模型資料夾不完整或不受支援，請選擇已準備的模型資料夾。',
        'model_load_failed': '無法載入本機模型，請檢查模型檔案、可用記憶體與已安裝的 CPU 執行元件。',
        'model_missing': '找不到本機模型，請選擇已準備的模型資料夾或下載模型。',
        'model_metadata_unavailable': '目前缺少模型下載資訊；仍可選擇已準備的本機模型資料夾。',
        'model_selected': '已選擇模型資料夾：{path}。開始錄音前會檢查檔案。',
        'model_details': '{name} · {size}\n來源：{source}',
        'model_download_confirm': '現在下載 {name} 嗎？\n\n來源：{source}\n下載容量：{size}\n\n這是一次性的公開模型下載，會使用網路與磁碟空間，不會上傳錄音或逐字稿。之後的錄音辨識在本機執行；只有確認後才會開始下載。',
        'model_download_failed': '模型準備失敗，請檢查磁碟空間及網路後重試；未使用雲端辨識。',
        'model_download_cancelled': '已取消模型準備；未使用雲端辨識。',
        'model_ready': '模型已準備，並已儲存設定。',
        'model_progress': '正在準備本機模型… {progress}',
        'preparing_model': '正在準備本機模型…',
        'lexicon_enabled': '顯示本機日文精神科詞彙候選，供人工確認',
        'lexicon_notice': '詞彙候選不會改寫逐字稿，也不能用來確定臨床意義。編輯或使用結果前，請先確認用字與上下文。',
        'lexicon_candidates': '詞彙候選 — 僅供人工確認',
        'loading_model': '正在載入本機模型…',
    },
    'ja': {
        'title': 'SGH Voice — Windows プレビュー（Windows 実機未検証）',
        'intro': '録音後に文字を確認してコピーしてください。自動入力は入力先のアプリでショートカットを押して開始します。',
        'record': '録音してプレビュー',
        'stop': '停止して文字起こし',
        'cancel': 'キャンセル',
        'copy': '文字をコピー',
        'result': '結果 — 使用前に確認してください',
        'level': 'マイク音量',
        'settings': '設定',
        'language': '音声の言語（ja / zh / en）',
        'ui_language': '表示言語',
        'toggle_hotkey': '録音／停止ショートカット',
        'cancel_hotkey': 'キャンセルショートカット',
        'auto_insert': 'ショートカット開始時の入力先への自動入力を許可する',
        'insert_notice': '入力時に元の入力先のフォーカスが必要です。操作の送信は入力完了の確認ではありません。コピー・入力後のデータは入力先アプリの管理に従い、他のクリップボードツールからも読み取られる場合があります。',
        'save_history': '文字起こし履歴をこのパソコンに保存する',
        'history_notice': '履歴保存は初期設定でオフです。結果は置き換えられるか、このウィンドウを閉じるまで表示されます。',
        'save': '設定を保存',
        'saved': '設定を保存しました。',
        'idle': '準備完了',
        'recording': '録音中 — 停止ボタンかショートカットで停止',
        'stopping': '録音を停止しています…',
        'processing': 'ローカルで文字起こし中…',
        'closed': '終了しています…',
        'copied': 'クリップボードにコピーしました。入力先のアプリに貼り付けてください。',
        'copy_failed': 'コピーできませんでした。結果を選択して手動でコピーしてください。',
        'preview': '文字を確認してコピーしてください。',
        'paste_sent': '貼り付け操作を送信しました。入力先で結果を確認してください。文字はここにも残ります。',
        'paste_fallback': '自動入力が完了しませんでした。コピーする前に、入力先に一部の文字が入っていないか確認してください。',
        'hotkeys_ready': 'ショートカット有効：{toggle}／キャンセル {cancel}',
        'hotkeys_failed': 'ショートカットを登録できません。形式と他のアプリとの競合を確認してください。録音ボタンは使用できます。',
        'save_failed': '設定を保存できません。アプリデータへのアクセス権を確認してください。',
        'invalid_settings': '対応言語、モデルフォルダーの絶対パス、異なる有効なショートカットを選択してください。',
        'busy': '録音、認識、モデルの準備が終了してから設定を変更してください。',
        'microphone_failed': 'マイクを開けません。Windows のマイク権限と既定の入力機器を確認してください。',
        'audio_unavailable': '有効な音声がありません。マイクを確認して再試行してください。',
        'transcription_failed': 'ローカルの文字起こしに失敗しました。モデルとマイクを確認して録音し直してください。',
        'settings_failed': '設定を適用できません。内容を確認して保存し直してください。',
        'error': '操作に失敗しました。設定を確認して再試行してください。',
        'startup_failed': 'SGH Voice を起動できません。インストールとアプリデータへのアクセスを確認してください。',
        'dirty': '設定が変更されています。録音前に保存してください。',
        'model_dir': 'ローカルモデルのフォルダー',
        'browse': 'フォルダーを選択…',
        'model_source': 'モデルの配布元／ファイル',
        'prepare_model': 'ローカルモデルをダウンロード…',
        'offline_notice': '音声認識はこのパソコンの CPU で実行します。SGH Voice は認識のために録音や文字起こしを送信しません。クラウドへの切り替えや API キーは使用しません。',
        'model_required': 'ローカル音声モデルが必要です。準備済みフォルダーを選ぶか、モデルのダウンロードを明示的に開始してから録音してください。',
        'model_invalid': '選択したモデルのフォルダーが不完全か未対応です。準備済みのフォルダーを選択してください。',
        'model_load_failed': 'ローカルモデルを読み込めません。モデルのファイル、空きメモリ、CPU 実行環境を確認してください。',
        'model_missing': 'ローカルモデルが見つかりません。準備済みフォルダーを選択するか、モデルをダウンロードしてください。',
        'model_metadata_unavailable': 'モデルのダウンロード情報がありません。準備済みのローカルフォルダーは選択できます。',
        'model_selected': '選択したフォルダー：{path}。録音前にファイルを確認します。',
        'model_details': '{name} · {size}\n配布元：{source}',
        'model_download_confirm': '{name} を今ダウンロードしますか？\n\n配布元：{source}\nダウンロード容量：{size}\n\n公開モデルを一度ダウンロードし、通信とディスク容量を使用します。録音や文字起こしは送信しません。その後の認識はローカルで実行します。確認するまでダウンロードは始まりません。',
        'model_download_failed': 'モデルを準備できませんでした。空き容量と接続を確認して再試行してください。クラウド認識は使用していません。',
        'model_download_cancelled': 'モデルの準備をキャンセルしました。クラウド認識は使用していません。',
        'model_ready': 'モデルを準備し、設定を保存しました。',
        'model_progress': 'ローカルモデルを準備しています… {progress}',
        'preparing_model': 'ローカルモデルを準備しています…',
        'lexicon_enabled': 'ローカルの日本語精神科用語候補を表示し、手動で確認する',
        'lexicon_notice': '用語候補は文字起こしを自動変更せず、臨床的意味を確定しません。編集・使用前に表記と文脈を確認してください。',
        'lexicon_candidates': '用語候補 — 手動確認用',
        'loading_model': 'ローカルモデルを読み込んでいます…',
    },
}


_LOCAL_MESSAGES = {
    "en": {
        "needs_model": "Prepare a local model before recording",
        "invalid_language": "Choose Japanese (ja), Chinese (zh), or English (en) and save settings.",
        "invalid_cpu_threads": "The CPU thread setting is invalid. Restore the application’s default CPU setting.",
        "local_runtime_missing": "The local speech runtime is missing. Use a complete SGH Voice Windows installation.",
        "invalid_mode": "This Windows preview supports local dictation only.",
        "model_disk_space": "There is not enough free disk space to prepare the model. Free space and retry the download.",
    },
    "zh-TW": {
        "needs_model": "錄音前請先準備本機模型",
        "invalid_language": "請選擇日文（ja）、中文（zh）或英文（en），並儲存設定。",
        "invalid_cpu_threads": "CPU 執行緒設定無效，請還原程式預設的 CPU 設定。",
        "local_runtime_missing": "缺少本機語音辨識元件，請使用完整的 SGH Voice Windows 安裝程式。",
        "invalid_mode": "此 Windows 預覽版僅支援本機聽寫。",
        "model_disk_space": "可用磁碟空間不足，請釋放空間後重新下載模型。",
    },
    "ja": {
        "needs_model": "録音前にローカルモデルを準備してください",
        "invalid_language": "日本語（ja）、中国語（zh）、英語（en）を選択し、設定を保存してください。",
        "invalid_cpu_threads": "CPU スレッド設定が無効です。アプリの既定の CPU 設定に戻してください。",
        "local_runtime_missing": "ローカル音声認識の実行環境がありません。完全な SGH Voice Windows インストーラーを使用してください。",
        "invalid_mode": "この Windows プレビューはローカル音声入力のみ対応しています。",
        "model_disk_space": "モデルを準備する空き容量が不足しています。容量を確保してダウンロードし直してください。",
    },
}
for _language, _messages in LABELS.items():
    _messages.update(_LOCAL_MESSAGES[_language])
    for _code, _message in {
        "invalid_model_path": "model_required",
        "model_not_ready": "model_invalid",
        "local_model_load_failed": "model_load_failed",
        "local_transcription_failed": "transcription_failed",
    }.items():
        _messages[_code] = _messages[_message]


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


def settings_snapshot(current, values):
    """Validate UI choices while preserving unrelated existing configuration."""
    if (values.get("windows_language") not in ("zh", "ja", "en")
            or values.get("ui_language") not in LABELS):
        raise ValueError("invalid_settings")
    model_dir = values.get("windows_model_dir", "")
    if not isinstance(model_dir, str):
        raise ValueError("invalid_settings")
    model_dir = model_dir.strip()
    if model_dir and not (os.path.isabs(model_dir) or ntpath.isabs(model_dir)):
        raise ValueError("invalid_settings")
    toggle = values.get("windows_toggle_hotkey", "").strip()
    cancel = values.get("windows_cancel_hotkey", "").strip()
    if not toggle or not cancel or toggle.lower().replace(" ", "") == cancel.lower().replace(" ", ""):
        raise ValueError("invalid_settings")
    updated = deepcopy(current)
    updated.update(values)
    updated.update(windows_toggle_hotkey=toggle, windows_cancel_hotkey=cancel,
                   windows_model_dir=model_dir)
    return updated


def candidate_lines(candidates):
    """Render review-only terminology; never return a changed transcript."""
    lines = []
    for candidate in candidates[:8] if isinstance(candidates, (list, tuple)) else ():
        if not isinstance(candidate, dict):
            continue
        preferred = str(candidate.get("preferred", ""))[:120]
        alias = str(candidate.get("matched_alias", ""))[:120]
        category = str(candidate.get("category", ""))[:80]
        if preferred:
            term = f"{alias} → {preferred}" if alias and alias != preferred else preferred
            lines.append(f"• {term}" + (f" ({category})" if category else ""))
    return "\n".join(lines)


class WindowsApp:
    """Single Tk-thread owner; local speech, microphone and hotkeys use a queue."""

    def __init__(self, root, config, *, controller_factory, native, hotkeys_factory,
                 save_config, validate_hotkey=None, model_info=None,
                 choose_directory=None, confirm_download=None, open_url=None):
        self.root = root
        self.config = deepcopy(config)
        self.native = native
        self.hotkeys_factory = hotkeys_factory
        self.save_config = save_config
        self.validate_hotkey = validate_hotkey
        self.model_info = dict(model_info or {})
        self.choose_directory = choose_directory
        self.confirm_download = confirm_download
        self.open_url = open_url
        self.events = queue.SimpleQueue()
        self.closed = False
        self.hotkeys = None
        self._after_id = None
        self._close_after_id = None
        self._pending_model_save = False
        self.lang = interface_language(config.get("ui_language"))
        self._status_key = "idle"
        self._notice_key = ""
        self._hotkeys_ready = False
        self._dirty = False
        self._drop_results = False
        self._build()
        self.controller = controller_factory(self.config, self.enqueue, native=native)
        self._render_state()
        self._render_model_info()
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
        self.settings_frame.grid(row=8, column=0, sticky="ew")
        self._labels.append((self.settings_frame, "settings"))
        self.settings_frame.columnconfigure(1, weight=1)
        self.vars = {}
        self._setting_widgets = []
        fields = (
            ("windows_language", "language", ("ja", "zh", "en"), "ja"),
            ("ui_language", "ui_language", ("zh-TW", "ja", "en"), self.lang),
        )
        for row, (field, key, choices, default) in enumerate(fields):
            label(self.settings_frame, key).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            value = self.config.get(field, default)
            self.vars[field] = tk.StringVar(value=value if value in choices else default)
            combo = ttk.Combobox(self.settings_frame, textvariable=self.vars[field], values=choices, state="readonly", width=20)
            combo.grid(row=row, column=1, sticky="ew", pady=3)
            self._setting_widgets.append((combo, "readonly"))
        label(self.settings_frame, "offline_notice", wraplength=760).grid(row=2, column=0, columnspan=2, sticky="ew", pady=6)
        label(self.settings_frame, "model_dir").grid(row=3, column=0, sticky="w")
        self.vars["windows_model_dir"] = tk.StringVar(value=self.config.get("windows_model_dir", ""))
        model_entry = ttk.Entry(self.settings_frame, textvariable=self.vars["windows_model_dir"])
        model_entry.grid(row=3, column=1, sticky="ew", pady=3)
        self._setting_widgets.append((model_entry, "normal"))
        model_buttons = ttk.Frame(self.settings_frame)
        model_buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)
        self.browse_button = ttk.Button(model_buttons, text=self.tr("browse"), command=self._browse_model)
        self.browse_button.pack(side="left")
        self._labels.append((self.browse_button, "browse"))
        self._setting_widgets.append((self.browse_button, "normal"))
        self.source_button = ttk.Button(model_buttons, text=self.tr("model_source"), command=self._open_model_source)
        self.source_button.pack(side="left", padx=6)
        self._labels.append((self.source_button, "model_source"))
        self.prepare_button = ttk.Button(model_buttons, text=self.tr("prepare_model"), command=self._prepare_model)
        self.prepare_button.pack(side="left")
        self._labels.append((self.prepare_button, "prepare_model"))
        self.model_details, self.model_notice = tk.StringVar(), tk.StringVar()
        ttk.Label(self.settings_frame, textvariable=self.model_details, wraplength=760).grid(row=5, column=0, columnspan=2, sticky="ew")
        ttk.Label(self.settings_frame, textvariable=self.model_notice, wraplength=760).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        for row, field, key, default in (
                (7, "windows_toggle_hotkey", "toggle_hotkey", "Ctrl+Alt+F9"),
                (8, "windows_cancel_hotkey", "cancel_hotkey", "Ctrl+Alt+F10")):
            label(self.settings_frame, key).grid(row=row, column=0, sticky="w", padx=(0, 8))
            self.vars[field] = tk.StringVar(value=self.config.get(field, default))
            entry = ttk.Entry(self.settings_frame, textvariable=self.vars[field])
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self._setting_widgets.append((entry, "normal"))
        self.hotkey_notice = tk.StringVar()
        ttk.Label(self.settings_frame, textvariable=self.hotkey_notice, wraplength=760).grid(row=9, column=0, columnspan=2, sticky="w", pady=(3, 6))
        for row, field, key, default in (
                (10, "windows_lexicon_enabled", "lexicon_enabled", False),
                (12, "windows_auto_insert", "auto_insert", False),
                (14, "windows_save_history", "save_history", False)):
            self.vars[field] = tk.BooleanVar(value=bool(self.config.get(field, default)))
            check = ttk.Checkbutton(self.settings_frame, text=self.tr(key), variable=self.vars[field])
            check.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
            self._labels.append((check, key))
            self._setting_widgets.append((check, "normal"))
        label(self.settings_frame, "lexicon_notice", wraplength=760).grid(row=11, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        label(self.settings_frame, "insert_notice", wraplength=760).grid(row=13, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        label(self.settings_frame, "history_notice", wraplength=760).grid(row=15, column=0, columnspan=2, sticky="ew")
        self.save_button = ttk.Button(self.settings_frame, text=self.tr("save"), command=self._save)
        self.save_button.grid(row=16, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._labels.append((self.save_button, "save"))
        self.candidates = tk.StringVar()
        ttk.Label(frame, textvariable=self.candidates, wraplength=790).grid(row=7, column=0, sticky="ew", pady=8)
        for variable in self.vars.values():
            variable.trace_add("write", self._mark_dirty)

    def _mark_dirty(self, *_):
        self._dirty = True
        self._set_notice("dirty")

    def _browse_model(self):
        if self.controller.state != "idle":
            self._set_notice("busy")
            return
        choose = self.choose_directory
        if choose is None:
            from tkinter import filedialog
            choose = filedialog.askdirectory
        path = choose(parent=self.root, title=self.tr("model_dir"), mustexist=True)
        if path:
            self.vars["windows_model_dir"].set(path)
            self._mark_dirty()
            self._render_model_info()

    def _model_metadata_ready(self):
        return (all(self.model_info.get(key) for key in ("name", "source_url", "size_label"))
                and self.model_info["source_url"].startswith("https://"))

    def _render_model_info(self):
        if self._model_metadata_ready():
            self.model_details.set(self.tr("model_details").format(
                name=self.model_info["name"], size=self.model_info["size_label"],
                source=self.model_info["source_url"]))
        else:
            self.model_details.set(self.tr("model_metadata_unavailable"))
        path = self.vars["windows_model_dir"].get().strip()
        self.model_notice.set(self.tr("model_selected").format(path=path) if path else self.tr("model_required"))
        idle = self.controller.state == "idle" and not self.closed
        self.prepare_button.configure(state="normal" if idle and self._model_metadata_ready() else "disabled")
        self.source_button.configure(state="normal" if self._model_metadata_ready() and not self.closed else "disabled")

    def _open_model_source(self):
        if not self._model_metadata_ready() or self.closed:
            return
        opener = self.open_url
        if opener is None:
            import webbrowser
            opener = webbrowser.open
        opener(self.model_info["source_url"])

    def _prepare_model(self):
        if self.controller.state != "idle":
            self._set_notice("busy")
            return
        if not self._model_metadata_ready():
            self._set_notice("model_metadata_unavailable")
            return
        confirm = self.confirm_download
        if confirm is None:
            from tkinter import messagebox
            confirm = messagebox.askyesno
        accepted = confirm(self.tr("prepare_model"), self.tr("model_download_confirm").format(
            name=self.model_info["name"], source=self.model_info["source_url"],
            size=self.model_info["size_label"]), parent=self.root)
        if not accepted:
            return
        self.controller.prepare_model()
        self._render_state()

    def _set_notice(self, key):
        self._notice_key = key
        self.notice.set(self.tr(key) if key else "")

    def _render_state(self):
        state = self.controller.state
        self._status_key = state if state in ("idle", "recording", "stopping", "processing", "preparing_model", "loading_model", "closed") else "idle"
        if state == "idle" and not self.vars["windows_model_dir"].get().strip():
            self._status_key = "needs_model"
        self.status.set(self.tr(self._status_key))
        self.record_button.configure(text=self.tr("stop" if state == "recording" else "record"), state="normal" if state in ("idle", "recording") else "disabled")
        self.cancel_button.configure(state="normal" if state in ("recording", "stopping", "processing", "preparing_model", "loading_model") else "disabled")
        self.save_button.configure(state="normal" if state == "idle" else "disabled")
        for widget, enabled_state in self._setting_widgets:
            widget.configure(state=enabled_state if state == "idle" else "disabled")
        if state != "recording":
            self.meter.configure(value=0)
        self._render_model_info()

    def _toggle_preview(self):
        self._toggle(None)

    def _clear_result(self):
        self.result.delete("1.0", "end")
        self.result.edit_reset()
        self.candidates.set("")

    def _toggle(self, target):
        if self._dirty and self.controller.state == "idle":
            self._set_notice("dirty")
            return
        was_idle = self.controller.state == "idle"
        accepted = self.controller.toggle(target=target)
        if accepted and was_idle:
            self._drop_results = False
            self._clear_result()
            self._set_notice("")
        self._render_state()

    def _cancel(self):
        self._drop_results = True
        self.controller.cancel()
        self._clear_result()
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
            updated = settings_snapshot(self.config, {field: variable.get() for field, variable in self.vars.items()})
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
            # Never expose raw exception text or private local paths in diagnostics.
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
        return True

    def _save_prepared_model(self):
        if self._pending_model_save and self.controller.state == "idle":
            self._pending_model_save = False
            if self._save():
                self._set_notice("model_ready")

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
                self._save_prepared_model()
            elif event == "model_progress" and isinstance(payload, dict):
                percent = payload.get("percent")
                if isinstance(percent, (int, float)) and math.isfinite(percent):
                    self.model_notice.set(self.tr("model_progress").format(progress=f"{max(0, min(100, int(percent)))}%"))
            elif event == "model_ready" and isinstance(payload, dict):
                path = payload.get("path")
                if isinstance(path, str) and path:
                    self.vars["windows_model_dir"].set(path)
                    self._dirty = True
                    self._pending_model_save = True
                    self._save_prepared_model()
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
                self._clear_result()
                self.result.insert("1.0", payload.get("text", ""))
                self.result.edit_reset()
                terms = candidate_lines(payload.get("lexicon_candidates", [])) if self.config.get("windows_lexicon_enabled") else ""
                self.candidates.set(f"{self.tr('lexicon_candidates')}\n{terms}" if terms else "")
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
        for widget in (self.record_button, self.cancel_button, self.save_button,
                       self.copy_button, self.prepare_button, self.source_button):
            widget.configure(state="disabled")
        for widget, _enabled_state in self._setting_widgets:
            widget.configure(state="disabled")
        self.meter.configure(value=0)
        self._clear_result()
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
    from windows_client.models import MODEL_DOWNLOAD_INFO

    root = tk.Tk()
    root.withdraw()
    try:
        config = {**WINDOWS_DEFAULTS, **load_config()}
        WindowsApp(root, config, controller_factory=Controller, native=WindowsNative(),
                   hotkeys_factory=GlobalHotkeys, save_config=save_config,
                   validate_hotkey=Hotkey.parse, model_info=MODEL_DOWNLOAD_INFO)
    except Exception:
        messagebox.showerror("SGH Voice", LABELS["en"]["startup_failed"], parent=root)
        root.destroy()
        return 1
    root.deiconify()
    root.mainloop()
    return 0
