#!/usr/bin/env python3
"""
convert_breeze_to_mlx.py — 將 Breeze-ASR-25 (HF Transformers 格式) 轉換為 mlx-whisper 格式

用法:
    python scripts/convert_breeze_to_mlx.py

輸出:
    /Volumes/Satechi_SSD/huggingface/hub/breeze-asr-25-mlx/
    ├── config.json      (mlx-whisper 格式的模型維度)
    └── weights.npz      (MLX 格式權重)
"""
import json
import sys
from pathlib import Path

# 確保在 venv 環境下執行
try:
    import mlx.core as mx
    import numpy as np
    from huggingface_hub import snapshot_download
except ImportError as e:
    print(f"缺少依賴: {e}")
    print("請在 venv 環境下執行: source venv/bin/activate")
    sys.exit(1)

# ─── 設定 ───────────────────────────────────────────────
HF_REPO = "MediaTek-Research/Breeze-ASR-25"
OUTPUT_DIR = Path("/Volumes/Satechi_SSD/huggingface/hub/breeze-asr-25-mlx")

# Whisper large-v2 的模型維度（Breeze-ASR-25 基於此微調）
MLX_CONFIG = {
    "n_mels": 128,
    "n_audio_ctx": 1500,
    "n_audio_state": 1280,
    "n_audio_head": 20,
    "n_audio_layer": 32,
    "n_vocab": 51865,
    "n_text_ctx": 448,
    "n_text_state": 1280,
    "n_text_head": 20,
    "n_text_layer": 32,
    "model_type": "whisper"
}

# HF Transformers → OpenAI Whisper 權重名稱映射
def convert_hf_to_openai_key(hf_key: str) -> str:
    """將 HF Transformers 的 key 轉換為 OpenAI Whisper 的 key"""
    # model.encoder.* → encoder.*
    # model.decoder.* → decoder.*
    key = hf_key.replace("model.", "")

    # conv1, conv2
    key = key.replace("encoder.conv1", "encoder.conv1")
    key = key.replace("encoder.conv2", "encoder.conv2")

    # positional embeddings
    key = key.replace("encoder.embed_positions.weight", "encoder.positional_embedding")
    key = key.replace("decoder.embed_positions.weight", "decoder.positional_embedding")
    key = key.replace("decoder.embed_tokens.weight", "decoder.token_embedding.weight")

    # encoder layers
    key = key.replace("encoder.layers.", "encoder.blocks.")
    key = key.replace("decoder.layers.", "decoder.blocks.")

    # self attention
    key = key.replace(".self_attn_layer_norm.", ".attn_ln.")
    key = key.replace(".self_attn.", ".attn.")
    key = key.replace(".encoder_attn_layer_norm.", ".cross_attn_ln.")
    key = key.replace(".encoder_attn.", ".cross_attn.")

    # attention projections
    key = key.replace(".q_proj.", ".query.")
    key = key.replace(".k_proj.", ".key.")
    key = key.replace(".v_proj.", ".value.")
    key = key.replace(".out_proj.", ".out.")

    # feed forward
    key = key.replace(".final_layer_norm.", ".mlp_ln.")
    key = key.replace(".fc1.", ".mlp1.")
    key = key.replace(".fc2.", ".mlp2.")

    # layer norm
    key = key.replace("encoder.layer_norm.", "encoder.ln_post.")
    key = key.replace("decoder.layer_norm.", "decoder.ln.")

    # proj_out (decoder output projection, 通常 tied with token embedding)
    key = key.replace("proj_out.weight", "decoder.token_embedding.weight")

    return key


# mlx_whisper 的 encoder 不儲存 positional_embedding（用 sinusoids 計算）
SKIP_KEYS = {
    "encoder.positional_embedding",
    "encoder.embed_positions.weight",
    "model.encoder.embed_positions.weight",
}


def main():
    print(f"=== Breeze-ASR-25 → MLX Whisper 轉換 ===")
    print(f"HF Repo: {HF_REPO}")
    print(f"輸出目錄: {OUTPUT_DIR}")

    # Step 1: 找到模型（優先用 SSD 上已下載的）
    print(f"\n[1/3] 尋找 {HF_REPO}...")
    ssd_path = Path("/Volumes/Satechi_SSD/huggingface/hub/models--MediaTek-Research--Breeze-ASR-25/snapshots/cffe7ccb404d025296a00758d0a33468bec3a9d0")
    if ssd_path.exists():
        model_path = ssd_path
        print(f"  使用 SSD 上的模型: {model_path}")
    else:
        model_path = Path(snapshot_download(repo_id=HF_REPO))
        print(f"  已下載到: {model_path}")

    # Step 2: 讀取 HF config 確認模型維度
    print("\n[2/3] 讀取模型設定...")
    hf_config_path = model_path / "config.json"
    with open(hf_config_path) as f:
        hf_config = json.load(f)

    print(f"  Model type: {hf_config.get('model_type')}")
    print(f"  Encoder layers: {hf_config.get('encoder_layers')}")
    print(f"  Decoder layers: {hf_config.get('decoder_layers')}")
    print(f"  d_model: {hf_config.get('d_model')}")
    print(f"  Vocab size: {hf_config.get('vocab_size')}")

    # 用 HF config 更新 MLX config
    mlx_config = MLX_CONFIG.copy()
    if hf_config.get("encoder_layers"):
        mlx_config["n_audio_layer"] = hf_config["encoder_layers"]
    if hf_config.get("decoder_layers"):
        mlx_config["n_text_layer"] = hf_config["decoder_layers"]
    if hf_config.get("d_model"):
        mlx_config["n_audio_state"] = hf_config["d_model"]
        mlx_config["n_text_state"] = hf_config["d_model"]
    if hf_config.get("encoder_attention_heads"):
        mlx_config["n_audio_head"] = hf_config["encoder_attention_heads"]
    if hf_config.get("decoder_attention_heads"):
        mlx_config["n_text_head"] = hf_config["decoder_attention_heads"]
    if hf_config.get("vocab_size"):
        mlx_config["n_vocab"] = hf_config["vocab_size"]
    if hf_config.get("num_mel_bins"):
        mlx_config["n_mels"] = hf_config["num_mel_bins"]
    if hf_config.get("max_source_positions"):
        mlx_config["n_audio_ctx"] = hf_config["max_source_positions"]
    if hf_config.get("max_target_positions"):
        mlx_config["n_text_ctx"] = hf_config["max_target_positions"]

    print(f"  MLX Config: {json.dumps(mlx_config, indent=2)}")

    # Step 3: 轉換權重
    print("\n[3/3] 轉換權重為 MLX 格式...")

    # 找模型權重檔案
    safetensors_files = list(model_path.glob("model*.safetensors"))
    if safetensors_files:
        print(f"  找到 safetensors: {[f.name for f in safetensors_files]}")
        # 使用 MLX 直接載入（支援 bfloat16）
        hf_weights = {}
        for sf_path in sorted(safetensors_files):
            weights = mx.load(str(sf_path))
            hf_weights.update(weights)
        print(f"  載入了 {len(hf_weights)} 個權重張量")
    else:
        print("  找不到模型權重檔案")
        sys.exit(1)

    # 轉換 key 名稱
    mlx_weights = {}
    skipped = []
    for hf_key, tensor in hf_weights.items():
        mlx_key = convert_hf_to_openai_key(hf_key)

        # 跳過 encoder positional embedding（mlx_whisper 用 sinusoids 計算）
        if mlx_key in SKIP_KEYS or hf_key in SKIP_KEYS:
            skipped.append(f"{hf_key} (encoder positional, 不需要)")
            continue

        if mlx_key == hf_key and "model." not in hf_key:
            # 無法轉換的 key，可能是不需要的
            skipped.append(hf_key)
            continue

        # tensor 已經是 mx.array（從 mx.load 載入），轉為 float16（推理速度快 5-10x）
        t = tensor.astype(mx.float16)

        # HF Conv1d weight shape: (out_channels, in_channels, kernel_size)
        # MLX Conv1d weight shape: (out_channels, kernel_size, in_channels)
        if "conv1.weight" in mlx_key or "conv2.weight" in mlx_key:
            t = mx.transpose(t, axes=(0, 2, 1))

        mlx_weights[mlx_key] = t

    if skipped:
        print(f"  跳過 {len(skipped)} 個無法映射的 key:")
        for k in skipped[:5]:
            print(f"    - {k}")
        if len(skipped) > 5:
            print(f"    ... 還有 {len(skipped)-5} 個")

    print(f"  轉換了 {len(mlx_weights)} 個權重張量")

    # 儲存
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 儲存 config
    config_path = OUTPUT_DIR / "config.json"
    with open(config_path, "w") as f:
        json.dump(mlx_config, f, indent=4)
    print(f"  ✅ config.json 已儲存")

    # 儲存權重（使用 safetensors 格式，mlx_whisper 支援 weights.safetensors）
    weights_path = OUTPUT_DIR / "weights.safetensors"
    mx.save_safetensors(str(weights_path), mlx_weights)

    # 檢查檔案大小
    size_gb = weights_path.stat().st_size / (1024**3)
    print(f"  ✅ weights.safetensors 已儲存 ({size_gb:.2f} GB)")

    print(f"\n=== 轉換完成 ===")
    print(f"輸出目錄: {OUTPUT_DIR}")
    print(f"\n使用方式:")
    print(f'  mlx_whisper.transcribe(audio, path_or_hf_repo="{OUTPUT_DIR}")')


if __name__ == "__main__":
    main()
