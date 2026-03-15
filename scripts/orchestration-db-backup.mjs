#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const defaultBase = process.env.OPENCLAW_ORCHESTRATION_HOME ?? path.join(process.cwd(), ".openclaw", "orchestration");
const dbPath = process.env.OPENCLAW_ORCHESTRATION_DB_PATH ?? path.join(defaultBase, "orchestrator.sqlite");
const backupDir = process.env.OPENCLAW_ORCHESTRATION_BACKUP_DIR ?? path.join(defaultBase, "backups");

if (!fs.existsSync(dbPath)) {
  console.error(`SQLite DB not found: ${dbPath}`);
  process.exit(1);
}

fs.mkdirSync(backupDir, { recursive: true });
const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
const backupPath = path.join(backupDir, `orchestrator-${timestamp}.sqlite`);

fs.copyFileSync(dbPath, backupPath);

console.log(`Backup created: ${backupPath}`);
console.log(`Restore with: node scripts/orchestration-db-restore.mjs --file "${backupPath}"`);
