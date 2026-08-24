#!/usr/bin/env python3
"""
launcher.py — .app bundle 入口點
處理 frozen app 的路徑解析和首次初始化
"""
import sys
import os


def get_bundle_dir():
    """取得 .app bundle 內的資源路徑"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def init_user_data():
    """首次啟動：複製預設設定到 ~/.voice-input/"""
    from config import (
        CONFIG_FILE,
        DICTIONARY_FILE,
        HISTORY_FILE,
        STATS_FILE,
        DEFAULT_CONFIG,
        load_dictionary,
        load_stats,
        save_config,
        save_dictionary,
        save_history,
        save_stats,
    )
    
    # 建立預設 config
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG.copy())

    # 建立預設 dictionary
    if not os.path.exists(DICTIONARY_FILE):
        save_dictionary(load_dictionary())

    # 初始化空的 history 和 stats
    if not os.path.exists(HISTORY_FILE):
        save_history([])
    if not os.path.exists(STATS_FILE):
        save_stats(load_stats())


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
