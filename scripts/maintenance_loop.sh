#!/bin/bash
# ═══════════════════════════════════════════
# 🎙 SGH Voice — Continuous Evolution Loop
# ═══════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"
SPECS_DIR="$PROJECT_DIR/.kiro/specs"

echo "=========================================="
echo "🚀 Starting Continuous Evolution Loop"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

mkdir -p "$SPECS_DIR"
STATUS_FILE="$SPECS_DIR/auto-upgrade-status.md"

echo "# 自動進化狀態報告 (Continuous Evolution Status)" > "$STATUS_FILE"
echo "**最後執行時間**: $(date '+%Y-%m-%d %H:%M:%S')" >> "$STATUS_FILE"
echo "" >> "$STATUS_FILE"

# 1. 數據反饋迴圈（知識層進化）
echo "--> 1. 執行歷史紀錄優化分析 (Auto-Triage)..."
export PYTHONPATH="$PROJECT_DIR"
if [ -f "$VENV_PYTHON" ]; then
    "$VENV_PYTHON" "$SCRIPT_DIR/auto_triage.py"
    if [ -f ~/.voice-input/auto_triage_report.md ]; then
        echo "✅ 分析完成。"
        echo "## 1. 歷史錯誤分析" >> "$STATUS_FILE"
        cat ~/.voice-input/auto_triage_report.md >> "$STATUS_FILE"
    else
        echo "⚠️ 無法產生分析報告或無需分析。"
        echo "## 1. 歷史錯誤分析" >> "$STATUS_FILE"
        echo "今日無需更新，或分析腳本未產出新報告。" >> "$STATUS_FILE"
    fi
else
    echo "❌ 找不到 Python 虛擬環境。"
fi
echo "" >> "$STATUS_FILE"

# 2. 醫學辭書擴充（領域進化）
echo "--> 2. 檢查醫學辭書更新 (PMDA/MHLW)..."
export PYTHONPATH="$PROJECT_DIR"
if [ -f "$VENV_PYTHON" ]; then
    "$VENV_PYTHON" "$SCRIPT_DIR/dict-update.py" --dry-run >> /dev/null 2>&1
    echo "✅ 辭書檢查完成。"
fi

# 3. 模型評估迴圈（效能層進化）
echo "--> 3. 檢查 HuggingFace 新模型..."
if [ -f "$SCRIPT_DIR/hf-model-watch.sh" ]; then
    bash "$SCRIPT_DIR/hf-model-watch.sh"
    echo "## 3. 模型評估" >> "$STATUS_FILE"
    echo "✅ HuggingFace 監控完成。若有新模型會推播通知。" >> "$STATUS_FILE"
fi
echo "" >> "$STATUS_FILE"

echo "=========================================="
echo "✨ Continuous Evolution Loop Completed!"
echo "Report saved to: $STATUS_FILE"
echo "=========================================="
