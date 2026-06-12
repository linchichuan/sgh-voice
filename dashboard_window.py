import sys
import os
import webview
import pathlib


def set_dock_icon():
    """設定 Dock 圖示為自訂 icon（取代 Python 火箭圖示）"""
    try:
        from AppKit import NSApplication, NSImage

        # 先嘗試 module 目錄，通常為 source 版；若為 PyInstaller 打包版則 fallback 到 bundle Resources
        icon_path_candidates = [
            pathlib.Path(__file__).resolve().parent / "resources" / "icon.icns",
        ]
        if hasattr(sys, "frozen") and sys.executable:
            exe_dir = pathlib.Path(sys.executable).resolve().parent
            icon_path_candidates.append(exe_dir.parent / "Resources" / "icon.icns")

        icon_path = next((p for p in icon_path_candidates if p.exists()), None)
        if icon_path is None and getattr(sys, "_MEIPASS", None):
            icon_path_candidates.append(pathlib.Path(sys._MEIPASS) / "resources" / "icon.icns")
            icon_path = next((p for p in icon_path_candidates if p.exists()), None)

        if icon_path is None:
            return

        icon_path = str(icon_path)
        if os.path.exists(icon_path):
            app = NSApplication.sharedApplication()
            icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
            app.setApplicationIconImage_(icon)
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        print("Usage: python dashboard_window.py <port>")
        sys.exit(1)
    port = sys.argv[1]
    url = f"http://127.0.0.1:{port}"
    set_dock_icon()
    webview.create_window("Voice Input Dashboard", url, width=1100, height=850)
    webview.start()

if __name__ == '__main__':
    main()
