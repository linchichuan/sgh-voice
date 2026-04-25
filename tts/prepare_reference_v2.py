#!/usr/bin/env python3
"""
prepare_reference_v2.py — 從新資料夾自動挑選並處理 OpenVoice V2 參考音。
"""
import os, sys, json, subprocess
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config():
    return json.loads(CONFIG_PATH.read_text())

def main():
    cfg = load_config()
    
    # 來源目錄 (新下載的那包)
    new_data_dir = "/Users/lin/Downloads/drive-download-20260422T004701Z-3-001"
    ref_dir = Path(cfg["ssd_root"]) / "reference_v2"
    ref_dir.mkdir(parents=True, exist_ok=True)

    print(f"🔍 掃描新錄音檔: {new_data_dir}")
    files = [f for f in os.listdir(new_data_dir) if f.endswith('.m4a')]
    files.sort()

    for i, f in enumerate(files, 1):
        print(f"  [{i}] {f}")

    choice = input("\n請選擇一個作為參考音 [1-{}] (建議選 5.m4a 或 Line_bot): ".format(len(files))).strip()
    try:
        idx = int(choice) - 1
        selected_file = files[idx]
    except:
        print("❌ 無效選擇")
        return

    src_path = os.path.join(new_data_dir, selected_file)
    dst_wav = ref_dir / "seed.wav"

    print(f"🎬 正在轉檔並擷取前 30 秒: {selected_file} -> seed.wav")
    # 轉為 16kHz 單聲道 wav (OpenVoice 偏好 16k 或 48k)
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-ss", "0", "-t", "30",
        "-ar", "16000", "-ac", "1",
        str(dst_wav)
    ]
    subprocess.run(cmd, check=True)

    print(f"\n✅ 參考音已就位: {dst_wav}")
    print("下個步驟：我將修改 generate.py 來呼叫 OpenVoice 進行合成。")

if __name__ == "__main__":
    main()
