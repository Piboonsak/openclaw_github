import { mkdir, readdir, readFile, rename, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import type { OrchestrationJob } from "./types.js";

export class FileJobStore {
  private readonly jobsDir: string;

  constructor(baseDir: string) {
    this.jobsDir = path.join(baseDir, "jobs");
  }

  async ensureReady(): Promise<void> {
    await mkdir(this.jobsDir, { recursive: true });
  }

  async save(job: OrchestrationJob): Promise<void> {
    await this.ensureReady();
    const finalPath = this.getPath(job.jobId);
    const tempPath = `${finalPath}.tmp`;
    const body = `${JSON.stringify(job, null, 2)}\n`;
    await writeFile(tempPath, body, "utf8");
    await rename(tempPath, finalPath);
  }

  async get(jobId: string): Promise<OrchestrationJob | undefined> {
    const filePath = this.getPath(jobId);
    try {
      const raw = await readFile(filePath, "utf8");
      return JSON.parse(raw) as OrchestrationJob;
    } catch {
      return undefined;
    }
  }

  async list(): Promise<OrchestrationJob[]> {
    await this.ensureReady();
    const names = await readdir(this.jobsDir);
    const jobs: OrchestrationJob[] = [];
    for (const name of names) {
      if (!name.endsWith(".json")) {
        continue;
      }
      const raw = await readFile(path.join(this.jobsDir, name), "utf8");
      jobs.push(JSON.parse(raw) as OrchestrationJob);
    }
    return jobs.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  async delete(jobId: string): Promise<void> {
    await unlink(this.getPath(jobId)).catch(() => undefined);
  }

  private getPath(jobId: string): string {
    return path.join(this.jobsDir, `${jobId}.json`);
  }
}
