#!/bin/bash
# ════════════════════════════════════════════════════════════
# 🎤 SGH TTS — 一次性安裝腳本
# 安裝 BreezyVoice（聯發科繁中 voice cloning）到外接 SSD
# ════════════════════════════════════════════════════════════
set -e

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; C='\033[0;36m'; N='\033[0m'

# ── 設定 ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SSD_ROOT="/Volumes/Satechi_SSD/voice-input/tts-data"
VENV_DIR="$SSD_ROOT/venv"
MODELS_DIR="$SSD_ROOT/models"
PYTHON_VERSION="3.10"

echo -e "${C}╔═══════════════════════════════════════════════╗${N}"
echo -e "${C}║  🎤 SGH TTS — BreezyVoice 安裝                ║${N}"
echo -e "${C}╚═══════════════════════════════════════════════╝${N}"
echo ""

# ── [1] 檢查外接 SSD ──
echo -e "${Y}[1/7] 檢查外接 SSD...${N}"
if [ ! -d "/Volumes/Satechi_SSD" ]; then
    echo -e "${R}❌ /Volumes/Satechi_SSD 未掛載，請先接上 Satechi SSD${N}"
    exit 1
fi
mkdir -p "$SSD_ROOT"/{models,reference,articles/done,output,logs}
echo -e "${G}✓${N} 外接 SSD 已掛載：$SSD_ROOT"

# ── [2] 確認 Python 3.10 ──
echo ""
echo -e "${Y}[2/7] 確認 Python ${PYTHON_VERSION}...${N}"
PYTHON_BIN=""
if command -v uv &> /dev/null; then
    echo -e "${G}✓${N} 使用 uv 管理 Python 環境"
    USE_UV=1
elif command -v "python${PYTHON_VERSION}" &> /dev/null; then
    PYTHON_BIN=$(command -v "python${PYTHON_VERSION}")
    echo -e "${G}✓${N} 找到 $PYTHON_BIN"
    USE_UV=0
elif command -v pyenv &> /dev/null; then
    if pyenv versions | grep -q "${PYTHON_VERSION}"; then
        PYTHON_BIN="$(pyenv root)/versions/$(pyenv versions | grep "${PYTHON_VERSION}" | head -1 | tr -d ' *')/bin/python"
        echo -e "${G}✓${N} 找到 pyenv $PYTHON_BIN"
    else
        echo -e "${Y}📦 用 pyenv 安裝 Python ${PYTHON_VERSION}.14...${N}"
        pyenv install -s 3.10.14
        PYTHON_BIN="$(pyenv root)/versions/3.10.14/bin/python"
    fi
    USE_UV=0
else
    echo -e "${Y}📦 未找到 Python 3.10 / uv / pyenv，建議安裝 uv（最快）：${N}"
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  或安裝 pyenv：brew install pyenv && pyenv install 3.10.14"
    exit 1
fi

# ── [3] 建立 venv ──
echo ""
echo -e "${Y}[3/7] 建立 venv 在外接 SSD...${N}"
if [ "$USE_UV" = "1" ]; then
    uv venv "$VENV_DIR" --python "$PYTHON_VERSION" --prompt "tts" 2>&1 | tail -5
else
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo -e "${G}✓${N} venv: $VENV_DIR"
python --version

# ── [4] clone BreezyVoice 倉庫 ──
echo ""
echo -e "${Y}[4/7] clone BreezyVoice 官方倉庫...${N}"
BV_REPO="$MODELS_DIR/BreezyVoice"
if [ -d "$BV_REPO/.git" ]; then
    echo -e "${G}✓${N} 已存在，更新中..."
    (cd "$BV_REPO" && git pull --ff-only)
else
    git clone --depth 1 https://github.com/mtkresearch/BreezyVoice.git "$BV_REPO"
fi

# ── [5] 安裝依賴 ──
echo ""
echo -e "${Y}[5/7] 安裝 BreezyVoice 依賴（5-10 分鐘）...${N}"
if [ "$USE_UV" = "1" ]; then
    uv pip install -r "$BV_REPO/requirements.txt" 2>&1 | tail -10
    uv pip install watchdog soundfile numpy 2>&1 | tail -3
else
    pip install --upgrade pip
    pip uninstall -y onnxruntime 2>/dev/null || true
    pip install -r "$BV_REPO/requirements.txt"
    pip install watchdog soundfile numpy
fi
echo -e "${G}✓${N} 依賴安裝完成"

# ── [6] 下載 BreezyVoice 模型權重 ──
echo ""
echo -e "${Y}[6/7] 下載 BreezyVoice-300M 模型（~1.2GB）...${N}"
MODEL_DIR="$MODELS_DIR/BreezyVoice-300M"
if [ -d "$MODEL_DIR" ] && [ -n "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
    echo -e "${G}✓${N} 模型已下載"
else
    if ! command -v git-lfs &> /dev/null; then
        echo -e "${Y}📦 安裝 git-lfs...${N}"
        brew install git-lfs
    fi
    git lfs install
    git clone https://huggingface.co/MediaTek-Research/BreezyVoice-300M "$MODEL_DIR"
fi

# ── [7] 寫入預設 config.json ──
echo ""
echo -e "${Y}[7/7] 寫入預設 config.json...${N}"
CONFIG_FILE="$SCRIPT_DIR/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" <<EOF
{
  "engine": "breezyvoice",
  "ssd_root": "$SSD_ROOT",
  "venv": "$VENV_DIR",
  "models_dir": "$MODELS_DIR",
  "breezyvoice_repo": "$BV_REPO",
  "breezyvoice_model": "$MODEL_DIR",
  "reference_wav": "$SSD_ROOT/reference/ref.wav",
  "reference_text": "$SSD_ROOT/reference/ref.txt",
  "articles_dir": "$SSD_ROOT/articles",
  "output_dir": "$SSD_ROOT/output",
  "lexicon_path": "$SCRIPT_DIR/lexicon.json"
}
EOF
    echo -e "${G}✓${N} 已寫入 $CONFIG_FILE"
else
    echo -e "${G}✓${N} config.json 已存在（不覆蓋）"
fi

echo ""
echo -e "${C}╔═══════════════════════════════════════════════╗${N}"
echo -e "${C}║  ✅ 安裝完成                                   ║${N}"
echo -e "${C}╚═══════════════════════════════════════════════╝${N}"
echo ""
echo -e "${G}下一步：${N}"
echo "  1. 準備 reference 音檔："
echo "     ${C}python prepare_reference.py${N}"
echo ""
echo "  2. 把要朗讀的文章 .txt 丟到："
echo "     ${C}$SSD_ROOT/articles/${N}"
echo ""
echo "  3. 啟動 watcher（電腦跑著就好）："
echo "     ${C}python batch.py${N}"
echo ""
echo "  測試（無需 reference）："
echo "     ${C}source $VENV_DIR/bin/activate && cd $BV_REPO && python single_inference.py --help${N}"
