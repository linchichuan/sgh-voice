#!/usr/bin/env python3
"""
launcher.py — .app bundle 入口點
處理 frozen app 的路徑解析和首次初始化
"""
import sys
import os
import shutil
import json


def get_bundle_dir():
    """取得 .app bundle 內的資源路徑"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def init_user_data():
    """首次啟動：複製預設設定到 ~/.voice-input/"""
    data_dir = os.path.expanduser("~/.voice-input")
    if os.path.exists(os.path.join(data_dir, "config.json")):
        return  # 已初始化

    os.makedirs(data_dir, exist_ok=True)
    from config import DEFAULT_CONFIG, save_config, save_dictionary
    
    # 建立預設 config
    if not os.path.exists(os.path.join(data_dir, "config.json")):
        save_config(DEFAULT_CONFIG.copy())

    # 建立預設 dictionary
    if not os.path.exists(os.path.join(data_dir, "dictionary.json")):
        save_dictionary({"corrections": {}, "frequency": {}, "auto_added": []})

    # 初始化空的 history 和 stats
    for filename, default in [
        ("history.json", []),
        ("stats.json", {
            "total_dictations": 0, "total_words": 0,
            "total_characters": 0, "total_seconds_saved": 0,
            "total_audio_seconds": 0, "daily": {},
            "languages_detected": {}, "corrections_applied": 0,
            "first_use_date": "", "streak_days": 0, "last_use_date": "",
        }),
    ]:
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import multiprocessing
    # 解決打包成 .app 後，mlx_whisper（或 scipy 底層）使用 multiprocessing 引發的 unrecognized arguments 錯誤
    multiprocessing.freeze_support()

    # 設定 bundle 路徑環境變數，讓其他模組可以使用
    os.environ["VOICEINPUT_BUNDLE_DIR"] = get_bundle_dir()

    # ★ .app bundle 啟動時，HuggingFace cache 路徑可能沒設定
    #   導致 mlx-whisper 找不到已下載的模型，靜默失敗 fallback 到 Cloud Whisper
    #   Cloud Whisper + 長 prompt → 幻覺（輸出字典詞彙而非你說的話）
    if not os.environ.get("HF_HOME"):
        # 優先用外接 SSD
        if os.path.isdir("/Volumes/Satechi_SSD/huggingface"):
            os.environ["HF_HOME"] = "/Volumes/Satechi_SSD/huggingface"
        else:
            # 使用預設的 ~/.cache/huggingface
            default_hf = os.path.expanduser("~/.cache/huggingface")
            os.environ["HF_HOME"] = default_hf

    init_user_data()
    from app import main
    main()
