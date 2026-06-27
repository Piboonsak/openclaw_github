#!/bin/bash
set -euo pipefail
# Install housekeeping cron jobs for LedgerFlow (TASK-1311)
# Run once on VPS after first deploy - safe to re-run (idempotent)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOUSEKEEPING="$SCRIPT_DIR/housekeeping.sh"
CRON_ENTRY_CLEAN="0 3 * * * bash $HOUSEKEEPING >> /var/log/ledgerflow-housekeeping.log 2>&1"
CRON_ENTRY_DISK="0 0,6,12,18 * * * bash $HOUSEKEEPING >> /var/log/ledgerflow-housekeeping.log 2>&1"

# Add only if not already present
( crontab -l 2>/dev/null | grep -v "housekeeping.sh"; echo "$CRON_ENTRY_CLEAN"; echo "$CRON_ENTRY_DISK" ) | crontab -
echo "Housekeeping cron installed."
crontab -l | grep housekeeping
