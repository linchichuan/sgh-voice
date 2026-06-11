import sys, subprocess, time
import pyperclip

text = "test paste"
pyperclip.copy(text)
time.sleep(0.05)
result = subprocess.run([
    "osascript", "-e",
    'tell application "System Events" to keystroke "v" using command down'
], capture_output=True, text=True, timeout=3)
print(f"returncode: {result.returncode}")
print(f"stdout: {result.stdout}")
print(f"stderr: {result.stderr}")
