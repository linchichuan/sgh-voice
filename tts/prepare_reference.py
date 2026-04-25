#!/usr/bin/env python3
"""
prepare_reference.py — 從 audio_backup 自動挑出最佳 30 秒 reference 音檔。

策略：
1. 掃所有備份 wav（內接 + 外接 SSD）
2. 從 ~/.voice-input/history.json 配對 whisper_raw 文字稿
3. 過濾條件：
   - 時長 15-30 秒（BreezyVoice 建議）
   - 純中文 ≥ 80%（無太多英文/數字）
   - RMS 音量穩定（無爆音、無大段靜音）
   - whisper_raw 與 final_text 差異小（辨識穩定 = 音質好）
4. 顯示 Top 5 候選，使用者輸入編號選擇
5. 複製到外接 SSD reference/
"""
import os, sys, json, re, shutil
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config():
    if not CONFIG_PATH.exists():
        print(f"❌ {CONFIG_PATH} 不存在，請先跑 setup.sh")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())

def chinese_ratio(text):
    if not text: return 0
    cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return cn / max(len(text), 1)

def main():
    cfg = load_config()
    try:
        import soundfile as sf
        import numpy as np
    except ImportError:
        print("❌ 需先 activate venv：")
        print(f"   source {cfg['venv']}/bin/activate")
        sys.exit(1)

    # 來源目錄
    sources = [
        os.path.expanduser("~/.voice-input/audio_backup"),
        "/Volumes/Satechi_SSD/voice-input/voice-data-lin",
    ]

    # 載入 history 做時間戳→文字稿映射
    hist_path = os.path.expanduser("~/.voice-input/history.json")
    hist_map = {}
    if os.path.exists(hist_path):
        for h in json.load(open(hist_path)):
            ts = h.get("timestamp", "")
            if ts:
                # timestamp: 2026-04-19T21:02:58.123 → 20260419_210258
                key = ts[:19].replace("-","").replace(":","").replace("T","_")
                hist_map[key] = h

    print(f"🔍 掃描音檔來源（{len(sources)} 個目錄）...")
    candidates = []

    for src in sources:
        if not os.path.isdir(src):
            print(f"  ⚠️  跳過不存在的目錄: {src}")
            continue
        for f in sorted(os.listdir(src)):
            if not f.endswith('.wav'): continue
            path = os.path.join(src, f)
            try:
                info = sf.info(path)
                # 時長過濾
                if not (15 <= info.duration <= 30): continue
                # 取音訊算 RMS
                audio, sr = sf.read(path, dtype='float32')
                if audio.ndim > 1: audio = audio.mean(axis=1)
                rms = float(np.sqrt(np.mean(audio**2)))
                if rms < 0.02: continue  # 太安靜

                # 配對文字稿
                key = f.replace('.wav', '')
                hist = hist_map.get(key, {})
                raw = hist.get("whisper_raw", "")
                final = hist.get("final_text", "")
                cn_pct = chinese_ratio(raw or final)
                if cn_pct < 0.7: continue  # 不夠中文

                # 評分：偏好穩定（raw≈final）+ 高音量 + 適中時長
                stability = 1.0 - (abs(len(raw) - len(final)) / max(len(raw), 1)) if raw else 0.5
                score = stability * 0.4 + min(rms * 10, 1.0) * 0.3 + cn_pct * 0.3

                candidates.append({
                    "path": path,
                    "duration": info.duration,
                    "rms": rms,
                    "cn_pct": cn_pct,
                    "stability": stability,
                    "score": score,
                    "text": final or raw or "(無文字稿)",
                })
            except Exception as e:
                continue

    if not candidates:
        print("❌ 沒有找到符合條件的 reference 候選")
        print("   建議：多錄一些 15-30 秒的中文音檔再跑")
        sys.exit(1)

    candidates.sort(key=lambda x: -x["score"])
    top = candidates[:5]

    print(f"\n✅ 找到 {len(candidates)} 個候選，Top 5：\n")
    for i, c in enumerate(top, 1):
        print(f"  [{i}] {os.path.basename(c['path'])}")
        print(f"      時長 {c['duration']:.1f}s | RMS {c['rms']:.3f} | 中文率 {c['cn_pct']:.0%} | 評分 {c['score']:.2f}")
        print(f"      文字: {c['text'][:80]}...")
        print()

    # 提供 preview 指令
    print("提示：可先 preview 聽聽看")
    for i, c in enumerate(top, 1):
        print(f"  [{i}] open '{c['path']}'")
    print()

    choice = input("請選擇 [1-5]（或 q 離開）：").strip()
    if choice.lower() == 'q':
        print("已取消")
        return
    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(top)): raise ValueError
    except ValueError:
        print("❌ 無效輸入")
        sys.exit(1)

    selected = top[idx]

    # 複製到外接 SSD reference/
    ref_wav = cfg["reference_wav"]
    ref_txt = cfg["reference_text"]
    os.makedirs(os.path.dirname(ref_wav), exist_ok=True)
    shutil.copy2(selected["path"], ref_wav)
    Path(ref_txt).write_text(selected["text"])

    print(f"\n✅ Reference 已建立：")
    print(f"   音檔: {ref_wav}")
    print(f"   文字: {ref_txt}")
    print(f"\n下一步：")
    print(f"   把 .txt 文章丟到: {cfg['articles_dir']}")
    print(f"   啟動 watcher:    python batch.py")

if __name__ == "__main__":
    main()
