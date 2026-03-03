import sys
import os
import webview


def set_dock_icon():
    """設定 Dock 圖示為自訂 icon（取代 Python 火箭圖示）"""
    try:
        from AppKit import NSApplication, NSImage
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.icns")
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
