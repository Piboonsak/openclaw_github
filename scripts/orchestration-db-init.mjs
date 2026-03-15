#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

const defaultBase = process.env.OPENCLAW_ORCHESTRATION_HOME ?? path.join(process.cwd(), ".openclaw", "orchestration");
const dbPath = process.env.OPENCLAW_ORCHESTRATION_DB_PATH ?? path.join(defaultBase, "orchestrator.sqlite");

fs.mkdirSync(path.dirname(dbPath), { recursive: true });

const db = new DatabaseSync(dbPath);
db.exec("PRAGMA journal_mode=WAL;");
db.exec("PRAGMA foreign_keys=ON;");
db.exec(`
  CREATE TABLE IF NOT EXISTS orchestration_jobs (
    job_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
  );
`);
db.close();

console.log(`Orchestration SQLite DB ready at: ${dbPath}`);
