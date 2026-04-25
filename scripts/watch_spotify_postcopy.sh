#!/bin/zsh
set -euo pipefail

LOG_PATH="$1"
SRC_ROOT="$2"
DEST_ROOT="$3"

while true; do
  if [[ -f "$LOG_PATH" ]] && tail -n 5 "$LOG_PATH" | grep -q "queue completed"; then
    mkdir -p "$DEST_ROOT"
    rsync -a "$SRC_ROOT/zh" "$SRC_ROOT/en" "$SRC_ROOT/jp" "$DEST_ROOT/"
    rm -rf "$SRC_ROOT/zh" "$SRC_ROOT/en" "$SRC_ROOT/jp" "$SRC_ROOT/_work"
    find "$SRC_ROOT" -type f \( -name "*.concat.txt" -o -name "*.tmp.wav" \) -delete
    exit 0
  fi
  sleep 60
done
