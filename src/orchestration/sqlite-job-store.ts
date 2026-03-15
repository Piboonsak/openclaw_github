import { mkdir } from "node:fs/promises";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import type { OrchestrationJob } from "./types.js";

function resolveDbPath(filePath: string): string {
  return path.resolve(filePath);
}

export class SqliteJobStore {
  private readonly dbPath: string;
  private db: DatabaseSync | undefined;

  constructor(filePath: string) {
    this.dbPath = resolveDbPath(filePath);
  }

  async ensureReady(): Promise<void> {
    if (this.db) {
      return;
    }
    await mkdir(path.dirname(this.dbPath), { recursive: true });
    const db = new DatabaseSync(this.dbPath);
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
    this.db = db;
  }

  async save(job: OrchestrationJob): Promise<void> {
    await this.ensureReady();
    const db = this.getDb();
    const payload = JSON.stringify(job);
    const stmt = db.prepare(`
      INSERT INTO orchestration_jobs (job_id, created_at, updated_at, payload)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(job_id) DO UPDATE SET
        updated_at = excluded.updated_at,
        payload = excluded.payload;
    `);
    stmt.run(job.jobId, job.createdAt, job.updatedAt, payload);
  }

  async get(jobId: string): Promise<OrchestrationJob | undefined> {
    await this.ensureReady();
    const db = this.getDb();
    const stmt = db.prepare("SELECT payload FROM orchestration_jobs WHERE job_id = ?");
    const row = stmt.get(jobId) as { payload?: string } | undefined;
    if (!row?.payload) {
      return undefined;
    }
    return JSON.parse(row.payload) as OrchestrationJob;
  }

  async list(): Promise<OrchestrationJob[]> {
    await this.ensureReady();
    const db = this.getDb();
    const stmt = db.prepare("SELECT payload FROM orchestration_jobs ORDER BY created_at ASC");
    const rows = stmt.all() as Array<{ payload?: string }>;
    return rows
      .map((row) => row.payload)
      .filter((value): value is string => Boolean(value))
      .map((payload) => JSON.parse(payload) as OrchestrationJob);
  }

  async delete(jobId: string): Promise<void> {
    await this.ensureReady();
    const db = this.getDb();
    const stmt = db.prepare("DELETE FROM orchestration_jobs WHERE job_id = ?");
    stmt.run(jobId);
  }

  close(): void {
    if (this.db) {
      this.db.close();
      this.db = undefined;
    }
  }

  private getDb(): DatabaseSync {
    if (!this.db) {
      throw new Error("SqliteJobStore is not initialized. Call ensureReady() first.");
    }
    return this.db;
  }
}
