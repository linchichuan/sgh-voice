#!/bin/bash
# ═══════════════════════════════════════════
# 🎙 Voice Input — 安裝與啟動
# ═══════════════════════════════════════════
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

G='\033[0;32m'
Y='\033[1;33m'
R='\033[0;31m'
C='\033[0;36m'
N='\033[0m'

echo ""
echo -e "${C}🎙 Voice Input — AI 語音輸入工具${N}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 檢查 Python ──
if ! command -v python3 &> /dev/null; then
    echo -e "${R}❌ 需要 Python 3.8+${N}"
    echo "   安裝: brew install python3"
    exit 1
fi

PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "${G}✓${N} Python ${PYVER}"

# ── 檢查 portaudio ──
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! brew list portaudio &> /dev/null 2>&1; then
        echo -e "${Y}📦 安裝 portaudio（macOS 錄音需要）...${N}"
        brew install portaudio
    fi
    echo -e "${G}✓${N} portaudio"
fi

# ── 建立虛擬環境 ──
if [ ! -d "venv" ]; then
    echo -e "${Y}📦 建立虛擬環境...${N}"
    python3 -m venv venv
fi
source venv/bin/activate
echo -e "${G}✓${N} 虛擬環境"

# ── 安裝依賴 ──
echo -e "${Y}📦 安裝依賴套件...${N}"
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${G}✓${N} 依賴安裝完成"

# ── 初始化資料（首次安裝自動匯入預設詞庫）──
DATA_DIR="$HOME/.voice-input"
CONFIG_FILE="$DATA_DIR/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${Y}📦 首次使用，建立預設設定...${N}"
    # 用 launcher.py::init_user_data() 從 DEFAULT_CONFIG 建立（自動偵測 arch：Intel 走 cloud-only）
    python3 -c "from launcher import init_user_data; init_user_data()"
    echo -e "${G}✓${N} 已建立 ~/.voice-input/（config / dictionary / history / stats）"
    ARCH=$(uname -m)
    if [ "$ARCH" != "arm64" ]; then
        echo -e "${Y}ℹ️  偵測到 ${ARCH}（非 Apple Silicon）— 已自動使用 cloud-only STT${N}"
    fi
    echo ""
    echo -e "${Y}⚠️  請在 Dashboard 設定頁填入 API 金鑰${N}"
    echo ""
fi

# ── 啟動 ──
echo ""
case "${1:-}" in
    --cli)
        echo -e "${G}▶ CLI 模式${N}"
        python3 app.py --cli
        ;;
    --dashboard)
        echo -e "${G}▶ Dashboard 模式${N}"
        python3 app.py --dashboard
        ;;
    *)
        echo -e "${G}▶ 啟動中...${N}"
        echo -e "   選單列圖示: ${C}🎙${N}"
        echo -e "   Dashboard:  ${C}http://localhost:7865${N}"
        echo ""
        echo -e "   ${Y}macOS 權限提醒:${N}"
        echo "   1. 系統設定 → 隱私與安全性 → 麥克風 → 允許 Terminal"
        echo "   2. 系統設定 → 隱私與安全性 → 輔助使用 → 允許 Terminal"
        echo "   3. 系統設定 → 隱私與安全性 → 輸入監控 → 允許 Terminal"
        echo ""
        python3 app.py
        ;;
esac
