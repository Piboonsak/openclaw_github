#!/usr/bin/env bash
# backup-db.sh — pg_dump PROD database, compress, cleanup old backups
# Usage: bash scripts/backup/backup-db.sh
# Env vars (set in cron or via .env):
#   BACKUP_DIR   — default /backup/db
#   DB_USER      — default ledgerflow
#   DB_NAME      — default ledgerflow_prod
#   PG_CONTAINER — default ledgerflow-postgres
#   RETAIN_DAYS  — default 7
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backup/db}"
DB_USER="${DB_USER:-ledgerflow}"
DB_NAME="${DB_NAME:-ledgerflow_prod}"
PG_CONTAINER="${PG_CONTAINER:-ledgerflow-postgres}"
RETAIN_DAYS="${RETAIN_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "=== DB Backup: ${DB_NAME} → ${BACKUP_FILE} ==="

mkdir -p "${BACKUP_DIR}"

docker exec "${PG_CONTAINER}" \
  pg_dump -U "${DB_USER}" "${DB_NAME}" \
  | gzip > "${BACKUP_FILE}"

if [[ ! -s "${BACKUP_FILE}" ]]; then
  echo "ERROR: Backup file is empty or missing: ${BACKUP_FILE}"
  exit 1
fi

SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo "Backup complete: ${BACKUP_FILE} (${SIZE})"

echo "=== Cleaning backups older than ${RETAIN_DAYS} days ==="
find "${BACKUP_DIR}" -name "*.sql.gz" -mtime "+${RETAIN_DAYS}" -delete
REMAINING=$(find "${BACKUP_DIR}" -name "*.sql.gz" | wc -l)
echo "Remaining backup files: ${REMAINING}"
