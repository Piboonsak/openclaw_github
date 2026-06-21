#!/usr/bin/env bash
# notify-line.sh — Send LINE push message via Messaging API
# Usage: LINE_CHANNEL_ACCESS_TOKEN=xxx LINE_USER_ID=xxx bash scripts/deploy/notify-line.sh "message"
# Pattern: same as Openclaw/NongKung — raw curl to /v2/bot/message/push
set -euo pipefail

TOKEN="${LINE_CHANNEL_ACCESS_TOKEN:?LINE_CHANNEL_ACCESS_TOKEN env var required}"
USER_ID="${LINE_USER_ID:?LINE_USER_ID env var required}"
MESSAGE="${1:?Usage: notify-line.sh <message>}"

HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"to\":\"${USER_ID}\",\"messages\":[{\"type\":\"text\",\"text\":\"${MESSAGE}\"}]}" \
  https://api.line.me/v2/bot/message/push 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
  echo "LINE push message sent"
else
  echo "LINE push message failed (HTTP ${HTTP_CODE})"
  exit 1
fi
