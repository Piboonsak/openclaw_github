#!/usr/bin/env bash
# housekeeping.sh — Temp cleanup + disk usage monitoring with LINE alert
# Usage: bash scripts/infra/housekeeping.sh
# Env vars:
#   DISK_ALERT_THRESHOLD — default 80 (percent)
#   UPLOAD_STAGING_DIR   — default /opt/ledgerflow/data/uploads
#   LINE_CHANNEL_ACCESS_TOKEN + LINE_USER_ID — for disk alerts
set -euo pipefail

DISK_ALERT_THRESHOLD="${DISK_ALERT_THRESHOLD:-80}"
UPLOAD_STAGING_DIR="${UPLOAD_STAGING_DIR:-/opt/ledgerflow/data/uploads}"
HOSTNAME_SHORT=$(hostname -s)

echo "=== Housekeeping: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# ── 1. Clean /tmp files older than 24h ────────────────────────────────
echo "--- Cleaning /tmp (>24h) ---"
find /tmp -maxdepth 2 -mtime +1 -type f -delete 2>/dev/null || true
echo "Done"

# ── 2. Clean upload staging dir older than 7 days ─────────────────────
if [[ -d "${UPLOAD_STAGING_DIR}" ]]; then
  echo "--- Cleaning upload staging (>7d): ${UPLOAD_STAGING_DIR} ---"
  find "${UPLOAD_STAGING_DIR}" -maxdepth 3 -mtime +7 -type f -delete 2>/dev/null || true
  echo "Done"
fi

# ── 3. Disk usage check ────────────────────────────────────────────────
echo "--- Disk usage check ---"
DISK_USAGE=$(df / | awk 'NR==2 {gsub("%",""); print $5}')
echo "Disk usage: ${DISK_USAGE}%"

if [[ "${DISK_USAGE}" -ge "${DISK_ALERT_THRESHOLD}" ]]; then
  MSG="⚠️ LedgerFlow Disk Alert\nHost: ${HOSTNAME_SHORT}\nDisk: ${DISK_USAGE}% used (threshold: ${DISK_ALERT_THRESHOLD}%)\nTime: $(date -u +'%Y-%m-%d %H:%M UTC')"
  echo "ALERT: Disk at ${DISK_USAGE}% — sending LINE notification"

  if [[ -n "${LINE_CHANNEL_ACCESS_TOKEN:-}" && -n "${LINE_USER_ID:-}" ]]; then
    curl -sf -X POST \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${LINE_CHANNEL_ACCESS_TOKEN}" \
      -d "{\"to\":\"${LINE_USER_ID}\",\"messages\":[{\"type\":\"text\",\"text\":\"${MSG}\"}]}" \
      https://api.line.me/v2/bot/message/push || echo "LINE notify failed (non-fatal)"
  else
    echo "LINE env vars not set — skipping notification"
  fi
fi

echo "=== Housekeeping complete ==="
