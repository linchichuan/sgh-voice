# -*- mode: python ; coding: utf-8 -*-
"""
VoiceInput.app — PyInstaller 打包配置
Apple Silicon (arm64) only
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

block_cipher = None

# 收集 native extension 的所有檔案
# NOTE: 在 Python 3.14 + PyInstaller 下，collect_all('mlx') 會觸發
# collect_submodules 匯入 mlx.optimizers，進而在無可用 Metal device 時崩潰。
# 這裡改成靜態收集資料/動態庫，避免打包階段主動匯入 mlx 子模組。
mlx_datas = collect_data_files('mlx')
mlx_bins = collect_dynamic_libs('mlx')
mlx_imports = ['mlx', 'mlx.core', 'mlx.nn']
mlx_nn_datas, mlx_nn_bins, mlx_nn_imports = [], [], []
whisper_datas = collect_data_files('mlx_whisper')
whisper_bins = collect_dynamic_libs('mlx_whisper')
whisper_imports = ['mlx_whisper']
sd_datas, sd_bins, sd_imports = collect_all('sounddevice')
sf_datas, sf_bins, sf_imports = collect_all('soundfile')
opencc_datas = collect_data_files('opencc')
rumps_datas, rumps_bins, rumps_imports = collect_all('rumps')
tiktoken_datas, tiktoken_bins, tiktoken_imports = collect_all('tiktoken')
# scipy_datas, scipy_bins, scipy_imports = collect_all('scipy')

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=mlx_bins + mlx_nn_bins + whisper_bins + sd_bins + sf_bins + rumps_bins + tiktoken_bins,
    datas=[
        ('static', 'static'),
    ] + mlx_datas + mlx_nn_datas + whisper_datas + sd_datas + sf_datas + opencc_datas + rumps_datas + tiktoken_datas,
    hiddenimports=[
        # App 核心
        'app', 'config', 'memory', 'transcriber', 'recorder', 'dashboard', 'overlay', 'voiceprint',
        # GUI / 系統
        'rumps',
        'pynput', 'pynput.keyboard', 'pynput.keyboard._darwin',
        'pynput.mouse', 'pynput.mouse._darwin',
        'pyperclip',
        # Audio
        'sounddevice', 'soundfile',
        # ML
        'mlx', 'mlx.core', 'mlx.nn', 'mlx_whisper',
        # Web
        'flask', 'flask.json', 'webview',
        # API
        'anthropic', 'openai', 'httpx', 'httpcore', 'h11', 'h2', 'hpack', 'hyperframe',
        'anyio', 'anyio._backends', 'anyio._backends._asyncio',
        'sniffio', 'certifi', 'distro', 'jiter',
        # NLP
        'opencc', 'tiktoken', 'tiktoken_ext', 'tiktoken_ext.openai_public',
        'regex', 'more_itertools',
        # PyObjC（rumps / pynput 底層）
        'AppKit', 'Foundation', 'Cocoa', 'Quartz',
        'objc', 'PyObjCTools', 'PyObjCTools.Conversion',
        # 標準庫
        'json', 'csv', 'io', 'shutil', 'threading', 'datetime',
    ] + mlx_imports + mlx_nn_imports + whisper_imports + sd_imports + sf_imports + rumps_imports + tiktoken_imports,
    excludes=[
        # 排除 torch（mlx-whisper 推理不需要，省 500MB+）
        'torch', 'torchvision', 'torchaudio', 'torch._C',
        # 排除不需要的大型套件
        'tkinter', 'matplotlib', 'PIL', 'cv2',
        'pytest', 'ruff', 'black', 'mypy', 'pylint',
        'jupyter', 'notebook', 'IPython',
        'scipy', 'numba', 'llvmlite', 'whisper', 'librosa',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SGH Voice',
    debug=False,
    strip=False,
    upx=False,
    console=False,  # rumps 需要 GUI 模式
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='SGH_Voice',
)

app = BUNDLE(
    coll,
    name='SGH Voice.app',
    icon='resources/icon.icns',
    bundle_identifier='com.shingihou.sghvoice',
    info_plist={
        'CFBundleName': 'SGH Voice',
        'CFBundleDisplayName': 'SGH Voice',
        'CFBundleVersion': '1.3.0',
        'CFBundleShortVersionString': '1.3.0',
        'LSMinimumSystemVersion': '13.0',
        'LSUIElement': True,  # 選單列 App，不顯示 Dock 圖示
        'NSMicrophoneUsageDescription': 'SGH Voice 需要麥克風權限來錄製語音並轉為文字。',
        'NSAppleEventsUsageDescription': 'SGH Voice 需要控制其他 App 來自動貼上轉錄文字。',
        'NSAccessibilityUsageDescription': 'SGH Voice 需要輔助使用權限來偵測全域快捷鍵和自動貼上。',
        'NSHumanReadableCopyright': '© 2026 Shingihou Co., Ltd.',
    },
)
