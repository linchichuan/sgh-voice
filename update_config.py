import json
import os

config_path = os.path.expanduser("~/.voice-input/config.json")
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config["enable_hybrid_mode"] = True
    config["hybrid_audio_threshold"] = 15
    config["hybrid_text_threshold"] = 30
    config["local_llm_model"] = "qwen2.5:3b"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print("Hybrid mode enabled successfully.")
