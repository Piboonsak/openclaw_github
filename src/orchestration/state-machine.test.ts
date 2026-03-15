import { describe, expect, it } from "vitest";
import { applyTransition, canTransition } from "./state-machine.js";
import type { OrchestrationJob } from "./types.js";

function createJob(): OrchestrationJob {
  return {
    jobId: "job-1",
    state: "CREATED",
    createdAt: "2026-03-15T00:00:00.000Z",
    updatedAt: "2026-03-15T00:00:00.000Z",
    retryCount: 0,
    maxRetries: 2,
    target: { owner: "Piboonsak", repo: "openclaw_github", ref: "main" },
    intent: { description: "test", mode: "implement", issueRefs: ["#111"] },
    events: [],
  };
}

describe("orchestration state machine", () => {
  it("allows a valid state progression", () => {
    const job = createJob();
    expect(applyTransition(job, "PREFLIGHT_PASSED").ok).toBe(true);
    expect(job.state).toBe("QUEUED");
    expect(applyTransition(job, "DISPATCHED").ok).toBe(true);
    expect(job.state).toBe("RUNNING");
    expect(applyTransition(job, "PR_OPENED").ok).toBe(true);
    expect(job.state).toBe("PR_OPEN");
    expect(applyTransition(job, "PR_MERGED").ok).toBe(true);
    expect(job.state).toBe("MERGED");
  });

  it("blocks invalid transitions", () => {
    const result = canTransition("CREATED", "PR_MERGED");
    expect(result.ok).toBe(false);
  });

  it("enforces retry max on RESUMED", () => {
    const job = createJob();
    job.state = "RETRYABLE_FAILURE";
    job.retryCount = 2;
    const result = applyTransition(job, "RESUMED");
    expect(result.ok).toBe(false);
    expect(result.reason).toContain("Retry limit reached");
  });
});
