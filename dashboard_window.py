import sys
import webview

def main():
    if len(sys.argv) < 2:
        print("Usage: python dashboard_window.py <port>")
        sys.exit(1)
    port = sys.argv[1]
    url = f"http://127.0.0.1:{port}"
    webview.create_window("Voice Input Dashboard", url, width=1100, height=850)
    webview.start()

if __name__ == '__main__':
    main()
