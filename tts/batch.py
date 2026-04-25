#!/usr/bin/env python3
"""
batch.py — Watcher 模式，「電腦跑著就好」。

監看 articles/ 資料夾，發現新 .txt 自動處理：
  1. 用 generate.py 合成 wav
  2. 完成後 .txt 移到 articles/done/
  3. 失敗的 .txt 移到 articles/failed/

啟動：
    python batch.py

背景跑：
    nohup python batch.py > batch.log 2>&1 &
"""
import os, sys, json, time, shutil, subprocess
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent / "config.json"
SCRIPT_DIR = Path(__file__).parent

def load_config():
    if not CONFIG_PATH.exists():
        print(f"❌ {CONFIG_PATH} 不存在，請先跑 ./setup.sh")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def process_article(cfg, txt_path):
    """處理單個 .txt 檔。"""
    log(f"📖 開始: {os.path.basename(txt_path)}")
    cmd = [
        os.path.join(cfg["venv"], "bin", "python"),
        str(SCRIPT_DIR / "generate.py"),
        txt_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        log(f"✅ 完成: {os.path.basename(txt_path)}")
        # 移到 done/
        done_dir = os.path.join(cfg["articles_dir"], "done")
        os.makedirs(done_dir, exist_ok=True)
        shutil.move(txt_path, os.path.join(done_dir, os.path.basename(txt_path)))
        return True
    else:
        log(f"❌ 失敗: {os.path.basename(txt_path)}")
        log(f"   stderr: {result.stderr[-300:]}")
        # 移到 failed/
        failed_dir = os.path.join(cfg["articles_dir"], "failed")
        os.makedirs(failed_dir, exist_ok=True)
        shutil.move(txt_path, os.path.join(failed_dir, os.path.basename(txt_path)))
        # 寫 error log
        log_path = os.path.join(failed_dir, os.path.basename(txt_path) + ".error.log")
        Path(log_path).write_text(f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}")
        return False

def scan_articles(cfg):
    """回傳 articles_dir 中所有未處理的 .txt（不含 done/ failed/ 子目錄）。"""
    articles_dir = cfg["articles_dir"]
    if not os.path.isdir(articles_dir): return []
    return [
        os.path.join(articles_dir, f)
        for f in sorted(os.listdir(articles_dir))
        if f.endswith('.txt') and os.path.isfile(os.path.join(articles_dir, f))
    ]

def main():
    cfg = load_config()
    articles_dir = cfg["articles_dir"]
    os.makedirs(articles_dir, exist_ok=True)
    os.makedirs(cfg["output_dir"], exist_ok=True)

    log(f"🎤 SGH TTS Batch Watcher")
    log(f"   監看: {articles_dir}")
    log(f"   輸出: {cfg['output_dir']}")
    log(f"   引擎: {cfg['engine']}")
    log("")
    log("把 .txt 文章丟到上面的 articles/ 資料夾即可。Ctrl+C 結束。")
    log("")

    seen = set()
    while True:
        try:
            articles = scan_articles(cfg)
            new_articles = [a for a in articles if a not in seen]
            if new_articles:
                log(f"🔍 發現 {len(new_articles)} 個新文章")
                for a in new_articles:
                    process_article(cfg, a)
                    seen.add(a)
            time.sleep(3)  # 每 3 秒掃一次
        except KeyboardInterrupt:
            log("\n👋 停止")
            break
        except Exception as e:
            log(f"⚠️  Watcher 錯誤: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
