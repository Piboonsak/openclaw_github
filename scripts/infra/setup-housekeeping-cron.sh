#!/usr/bin/env bash
# setup-housekeeping-cron.sh — Install housekeeping cron jobs
# Usage: bash scripts/infra/setup-housekeeping-cron.sh
# Run on UAT or PROD VPS as deploy user
set -euo pipefail

LEDGERFLOW_DIR="${LEDGERFLOW_DIR:-/opt/ledgerflow}"

echo "=== Installing housekeeping cron jobs ==="

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

# Temp cleanup + disk check every 6 hours
add_cron "0 0,6,12,18 * * * cd ${LEDGERFLOW_DIR} && bash scripts/infra/housekeeping.sh >> /var/log/ledgerflow-housekeeping.log 2>&1"

echo "${CRONTAB_CONTENT}" | crontab -

echo "=== Crontab installed ==="
crontab -l
