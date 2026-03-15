#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

function parseFileArg(argv) {
  const index = argv.findIndex((item) => item === "--file");
  if (index === -1 || !argv[index + 1]) {
    return undefined;
  }
  return argv[index + 1];
}

const defaultBase = process.env.OPENCLAW_ORCHESTRATION_HOME ?? path.join(process.cwd(), ".openclaw", "orchestration");
const dbPath = process.env.OPENCLAW_ORCHESTRATION_DB_PATH ?? path.join(defaultBase, "orchestrator.sqlite");
const backupFile = parseFileArg(process.argv.slice(2));

if (!backupFile) {
  console.error("Usage: node scripts/orchestration-db-restore.mjs --file <backup.sqlite>");
  process.exit(1);
}

const sourcePath = path.resolve(backupFile);
if (!fs.existsSync(sourcePath)) {
  console.error(`Backup file not found: ${sourcePath}`);
  process.exit(1);
}

fs.mkdirSync(path.dirname(dbPath), { recursive: true });

if (fs.existsSync(dbPath)) {
  const safetyPath = `${dbPath}.before-restore-${Date.now()}.bak`;
  fs.copyFileSync(dbPath, safetyPath);
  console.log(`Current DB backup: ${safetyPath}`);
}

const tempTarget = `${dbPath}.restore.tmp`;
fs.copyFileSync(sourcePath, tempTarget);
fs.renameSync(tempTarget, dbPath);

console.log(`Restore complete: ${dbPath}`);
