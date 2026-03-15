import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { FileJobStore } from "./job-store.js";
import type { OrchestrationJob } from "./types.js";

const tempDirs: string[] = [];

afterEach(async () => {
  await Promise.all(tempDirs.map((dir) => rm(dir, { recursive: true, force: true })));
  tempDirs.length = 0;
});

function sampleJob(jobId: string): OrchestrationJob {
  const now = new Date().toISOString();
  return {
    jobId,
    state: "CREATED",
    createdAt: now,
    updatedAt: now,
    retryCount: 0,
    maxRetries: 3,
    target: { owner: "Piboonsak", repo: "openclaw_github", ref: "main" },
    intent: { description: "sample", mode: "implement", issueRefs: ["#129"] },
    events: [],
  };
}

describe("file job store", () => {
  it("saves and loads a job", async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), "openclaw-orch-"));
    tempDirs.push(dir);

    const store = new FileJobStore(dir);
    const job = sampleJob("job-100");
    await store.save(job);

    const loaded = await store.get("job-100");
    expect(loaded?.jobId).toBe("job-100");
    expect(loaded?.target.repo).toBe("openclaw_github");
  });

  it("lists persisted jobs", async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), "openclaw-orch-"));
    tempDirs.push(dir);

    const store = new FileJobStore(dir);
    await store.save(sampleJob("job-1"));
    await store.save(sampleJob("job-2"));

    const jobs = await store.list();
    expect(jobs.length).toBe(2);
  });
});
