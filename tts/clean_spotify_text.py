import os, re
from pathlib import Path

def clean_text(text):
    # 徹底拔除 Spotify 不需要的所有標記
    text = text.replace("**", "")  # 移除粗體
    text = re.sub(r'#+', '', text) # 移除標題
    text = text.replace("---", "") # 移除分隔線
    text = text.replace(">", "")   # 移除引用
    # 移除多餘空白與空行
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join([l for l in lines if l])

def process_all():
    base_src = "/Users/lin/Library/CloudStorage/Dropbox-新義豊株式会社/林紀全/LIN個人檔案/自傳self story"
    base_dst = "/Volumes/Satechi_SSD/voice-input/tts-data/cleaned_text"
    
    dirs = ["tts", "tts_en", "tts_jp"]
    
    for d in dirs:
        src_path = Path(base_src) / d
        dst_path = Path(base_dst) / d
        os.makedirs(dst_path, exist_ok=True)
        
        print(f"🧹 正在清理 {d} ...")
        for f in src_path.glob("*.txt"):
            content = f.read_text(encoding='utf-8')
            cleaned = clean_text(content)
            (dst_path / f.name).write_text(cleaned, encoding='utf-8')
            print(f"  ✓ {f.name}")

if __name__ == "__main__":
    process_all()
