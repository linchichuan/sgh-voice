#!/bin/bash
# ─── 安裝/更新 SGH Voice launchd 排程 ───────────────────────
# 用法：bash scripts/install-launchd.sh
#       bash scripts/install-launchd.sh --uninstall

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_DIR="$SCRIPT_DIR/launchd"
AGENT_DIR="$HOME/Library/LaunchAgents"

PLISTS=(
  "com.shingihou.hf-watch"
  "com.shingihou.dict-update"
  "com.shingihou.pipeline-health"
)

if [ "$1" = "--uninstall" ]; then
  echo "🗑️  卸載 SGH Voice 排程任務..."
  for plist in "${PLISTS[@]}"; do
    if launchctl list | grep -q "$plist"; then
      launchctl bootout "gui/$(id -u)/$plist" 2>/dev/null || \
        launchctl unload "$AGENT_DIR/$plist.plist" 2>/dev/null
      echo "  ✅ 已停止 $plist"
    fi
    rm -f "$AGENT_DIR/$plist.plist"
    echo "  ✅ 已移除 $plist.plist"
  done
  echo "完成！"
  exit 0
fi

echo "📦 安裝 SGH Voice 排程任務..."
echo "   來源：$PLIST_DIR/"
echo "   目標：$AGENT_DIR/"
echo

# 確保目標目錄存在
mkdir -p "$AGENT_DIR"

# 確保腳本有執行權限
chmod +x "$SCRIPT_DIR/hf-model-watch.sh" 2>/dev/null

for plist in "${PLISTS[@]}"; do
  SRC="$PLIST_DIR/$plist.plist"
  DST="$AGENT_DIR/$plist.plist"

  if [ ! -f "$SRC" ]; then
    echo "  ⚠️  找不到 $SRC，跳過"
    continue
  fi

  # 先停止舊的（如果在運行）
  if launchctl list | grep -q "$plist"; then
    launchctl bootout "gui/$(id -u)/$plist" 2>/dev/null || \
      launchctl unload "$DST" 2>/dev/null
    echo "  🔄 已停止舊的 $plist"
  fi

  # 複製並載入
  cp "$SRC" "$DST"
  launchctl load "$DST"
  echo "  ✅ $plist — 已安裝並啟用"
done

echo
echo "📋 排程說明："
echo "  • com.shingihou.hf-watch        — 每天 08:00 監控 HuggingFace 新 ASR 模型"
echo "  • com.shingihou.dict-update      — 每週日 03:00 自動擴充醫療辭書"
echo "  • com.shingihou.pipeline-health  — 每天 23:00 管線健康診斷 + 自動優化"
echo
echo "🔧 手動測試："
echo "  bash scripts/hf-model-watch.sh"
echo "  python3 scripts/dict-update.py --dry-run"
echo "  python3 scripts/pipeline_health.py"
echo
echo "📝 Log 位置："
echo "  ~/.voice-input/hf-watch.stdout.log"
echo "  ~/.voice-input/dict-update.stdout.log"
echo "  ~/.voice-input/pipeline-health.stdout.log"
echo
echo "📊 健康報告："
echo "  ~/.voice-input/reports/health_latest.md"
