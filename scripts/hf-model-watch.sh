#!/bin/bash
# ─── HuggingFace 新 ASR 模型監控 ───────────────────────────
# launchd 每天 08:00 執行，發現新模型推 macOS 通知
# 用法：
#   手動測試：bash scripts/hf-model-watch.sh
#   啟用排程：launchctl load ~/Library/LaunchAgents/com.shingihou.hf-watch.plist

DATA_DIR="$HOME/.voice-input"
TRACKER_FILE="$DATA_DIR/hf_seen_models.txt"
NOTIFY_LOG="$DATA_DIR/hf_alerts.log"
mkdir -p "$DATA_DIR"
touch "$TRACKER_FILE"

# 搜尋關鍵字（ASR 相關）
QUERIES=(
  "speech+recognition+japanese"
  "whisper+chinese+mandarin"
  "asr+multilingual+2026"
  "speech+to+text+edge"
  "whisper+traditional+chinese"
)

NEW_MODELS=""

for query in "${QUERIES[@]}"; do
  # HuggingFace API：抓最近 7 天更新的模型
  RESULTS=$(curl -s --max-time 15 \
    "https://huggingface.co/api/models?search=${query}&sort=lastModified&direction=-1&limit=10" \
    | python3 -c "
import sys, json
from datetime import datetime, timedelta
try:
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    models = json.load(sys.stdin)
    for m in models:
        if m.get('lastModified','') > cutoff:
            mid = m['modelId']
            downloads = m.get('downloads', 0)
            likes = m.get('likes', 0)
            print(f'{mid}|{downloads}|{likes}')
except:
    pass
" 2>/dev/null)

  while IFS='|' read -r model_id downloads likes; do
    [ -z "$model_id" ] && continue
    # 已追蹤的跳過
    grep -qF "$model_id" "$TRACKER_FILE" && continue
    # 新模型
    echo "$model_id" >> "$TRACKER_FILE"
    NEW_MODELS="${NEW_MODELS}
📦 ${model_id} (⬇${downloads} ❤${likes})"
  done <<< "$RESULTS"
done

# 有新模型 → macOS 通知 + 寫 log
if [ -n "$NEW_MODELS" ]; then
  TITLE="🔍 SGH Voice: 新 ASR 模型發現"
  # 只取前 5 行（通知太長會被截斷）
  BODY=$(echo "$NEW_MODELS" | head -5 | sed '/^$/d')

  # macOS 原生通知
  osascript -e "display notification \"${BODY}\" with title \"${TITLE}\"" 2>/dev/null

  # 寫 log
  {
    echo "$(date '+%Y-%m-%d %H:%M') — 新模型:"
    echo "$NEW_MODELS"
    echo "---"
  } >> "$NOTIFY_LOG"

  echo "[hf-model-watch] 發現新模型:${NEW_MODELS}"
else
  echo "[hf-model-watch] $(date '+%Y-%m-%d %H:%M') 無新模型"
fi

# ─── 進階：Claude API 相關性評估（需要 ANTHROPIC_API_KEY 環境變數）───
# 如果有設定 API key 且有新模型，對高下載量模型進行自動評分
if [ -n "$NEW_MODELS" ] && [ -n "$ANTHROPIC_API_KEY" ]; then
  echo "$NEW_MODELS" | while IFS='|' read -r line; do
    model_id=$(echo "$line" | sed 's/📦 //' | awk -F' ' '{print $1}')
    [ -z "$model_id" ] && continue

    EVAL=$(curl -s --max-time 20 https://api.anthropic.com/v1/messages \
      -H "x-api-key: $ANTHROPIC_API_KEY" \
      -H "anthropic-version: 2023-06-01" \
      -H "content-type: application/json" \
      -d "{
        \"model\": \"claude-haiku-4-5-20251001\",
        \"max_tokens\": 200,
        \"messages\": [{
          \"role\": \"user\",
          \"content\": \"模型 ${model_id} 剛在 HuggingFace 發布。請評估它對 SGH Voice（macOS 多語言語音輸入工具，需要中日英 ASR，目前用 Breeze-ASR-25）的相關性，1-10 分，只回覆數字和一行理由。\"
        }]
      }" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['content'][0]['text'])" 2>/dev/null)

    if [ -n "$EVAL" ]; then
      SCORE=$(echo "$EVAL" | grep -oE '^[0-9]+')
      if [ "$SCORE" -ge 7 ] 2>/dev/null; then
        osascript -e "display notification \"${model_id}: ${EVAL}\" with title \"🔥 高分新模型！\"" 2>/dev/null
        echo "[hf-model-watch] 高分: ${model_id} — ${EVAL}" >> "$NOTIFY_LOG"
      fi
    fi
  done
fi
