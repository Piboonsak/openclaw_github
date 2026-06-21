#!/usr/bin/env bash
# setup-backup-cron.sh — Install backup cron jobs for deploy user
# Usage: bash scripts/backup/setup-backup-cron.sh
# Run on PROD VPS as deploy user
set -euo pipefail

LEDGERFLOW_DIR="${LEDGERFLOW_DIR:-/opt/ledgerflow}"

echo "=== Installing backup cron jobs ==="

# Write cron jobs (append to existing, avoid duplicates)
CRONTAB_CONTENT=$(crontab -l 2>/dev/null || true)

add_cron() {
  local entry="$1"
  if echo "${CRONTAB_CONTENT}" | grep -qF "${entry}"; then
    echo "Already exists: ${entry}"
  else
    CRONTAB_CONTENT="${CRONTAB_CONTENT}"$'\n'"${entry}"
    echo "Added: ${entry}"
  fi
}

# pg_dump every 6 hours
add_cron "0 0,6,12,18 * * * cd ${LEDGERFLOW_DIR} && bash scripts/backup/backup-db.sh >> /var/log/ledgerflow-backup.log 2>&1"

# R2 sync 10 min after each backup (wait for dump to finish)
add_cron "10 0,6,12,18 * * * cd ${LEDGERFLOW_DIR} && bash scripts/backup/sync-r2.sh >> /var/log/ledgerflow-backup.log 2>&1"

echo "${CRONTAB_CONTENT}" | crontab -

echo "=== Crontab installed ==="
crontab -l
