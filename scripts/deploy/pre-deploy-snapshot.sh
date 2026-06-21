#!/usr/bin/env bash
# pre-deploy-snapshot.sh — pg_dump before PROD migration
# Usage: bash scripts/deploy/pre-deploy-snapshot.sh [BACKUP_DIR] [DB_USER] [DB_NAME] [CONTAINER]
# Required before every PROD deploy (see docs/cicd/prod-safety-rules.md)
set -euo pipefail

BACKUP_DIR="${1:-/backup/db}"
DB_USER="${2:-ledgerflow}"
DB_NAME="${3:-ledgerflow_prod}"
CONTAINER="${4:-ledgerflow-postgres}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/pre-deploy-${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Creating pre-deploy DB snapshot..."
echo "  Container: ${CONTAINER}"
echo "  Database:  ${DB_NAME}"
echo "  Output:    ${BACKUP_FILE}"

docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" \
  | gzip > "$BACKUP_FILE"

if [[ -f "$BACKUP_FILE" ]] && [[ -s "$BACKUP_FILE" ]]; then
  SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
  echo "Snapshot created: ${BACKUP_FILE} (${SIZE})"

  # Clean snapshots older than 7 days
  DELETED=$(find "$BACKUP_DIR" -name "pre-deploy-*.sql.gz" -mtime +7 -delete -print | wc -l)
  if [[ "$DELETED" -gt 0 ]]; then
    echo "Cleaned ${DELETED} snapshot(s) older than 7 days"
  fi
else
  echo "Snapshot FAILED or empty: ${BACKUP_FILE}"
  exit 1
fi
