#!/usr/bin/env bash
# sync-r2.sh — Sync /backup/db to Cloudflare R2 via rclone
# Usage: bash scripts/backup/sync-r2.sh
# Prerequisites:
#   1. rclone installed: curl https://rclone.org/install.sh | sudo bash
#   2. rclone configured with R2 remote named "r2":
#      rclone config create r2 s3 provider Cloudflare \
#        access_key_id $R2_ACCESS_KEY_ID \
#        secret_access_key $R2_SECRET_ACCESS_KEY \
#        endpoint https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com acl private
# Ref: https://rclone.org/s3/#cloudflare-r2
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backup/db}"
R2_BUCKET="${R2_BUCKET:-ledgerflow-backup}"
R2_REMOTE="${R2_REMOTE:-r2}"
R2_RETAIN_DAYS="${R2_RETAIN_DAYS:-30}"

echo "=== Sync ${BACKUP_DIR} → ${R2_REMOTE}:${R2_BUCKET} ==="

if ! command -v rclone &>/dev/null; then
  echo "ERROR: rclone not installed. Run: curl https://rclone.org/install.sh | sudo bash"
  exit 1
fi

rclone copy "${BACKUP_DIR}/" "${R2_REMOTE}:${R2_BUCKET}/" \
  --min-age 0 \
  --log-level INFO

echo "Sync complete"

echo "=== Removing R2 objects older than ${R2_RETAIN_DAYS} days ==="
rclone delete "${R2_REMOTE}:${R2_BUCKET}/" \
  --min-age "${R2_RETAIN_DAYS}d" \
  --log-level INFO

echo "R2 cleanup complete"
