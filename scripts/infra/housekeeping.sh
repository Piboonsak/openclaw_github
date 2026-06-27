#!/bin/bash
set -euo pipefail
# LedgerFlow housekeeping: temp cleanup + disk monitoring
# Runs daily at 03:00 UTC via cron (TASK-1311)
# LINE alert fires at 80% disk usage

THRESHOLD=80
UPLOAD_STAGING="${UPLOAD_STAGING_DIR:-/opt/ledgerflow/uploads/staging}"
NOTIFY_SCRIPT="$(dirname "$0")/../deploy/notify-line.sh"

# 1. Clean temp files older than 24h
if [ -d "/tmp/ledgerflow" ]; then
  find /tmp/ledgerflow -type f -mmin +1440 -delete
  echo "$(date): /tmp/ledgerflow cleaned"
fi

# 2. Clean upload staging older than 24h
if [ -d "$UPLOAD_STAGING" ]; then
  find "$UPLOAD_STAGING" -type f -mmin +1440 -delete
  echo "$(date): staging cleaned"
fi

# 3. Check disk usage - alert at 80%
USAGE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$USAGE" -ge "$THRESHOLD" ]; then
  MESSAGE="LedgerFlow disk usage at ${USAGE}% (threshold: ${THRESHOLD}%)"
  if [ -f "$NOTIFY_SCRIPT" ]; then
    bash "$NOTIFY_SCRIPT" "failure" "$MESSAGE"
  fi
  echo "$(date): ALERT - disk ${USAGE}%"
fi
