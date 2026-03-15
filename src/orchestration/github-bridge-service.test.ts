import { describe, expect, it } from "vitest";
import { GitHubBridgeService, mapGitHubEventToOrchestrationEvent } from "./github-bridge-service.js";
import type { OrchestrationJob } from "./types.js";

function createJob(state: OrchestrationJob["state"] = "RUNNING"): OrchestrationJob {
  const now = "2026-03-15T00:00:00.000Z";
  return {
    jobId: "job-ws-d-1",
    state,
    createdAt: now,
    updatedAt: now,
    retryCount: 0,
    maxRetries: 3,
    target: { owner: "Piboonsak", repo: "openclaw_github", ref: "main" },
    intent: { description: "bridge", mode: "implement", issueRefs: ["#111"] },
    events: [],
  };
}

describe("github bridge service", () => {
  it("maps pull_request opened to PR_OPENED", () => {
    const mapped = mapGitHubEventToOrchestrationEvent(
      { deliveryId: "d1", eventType: "pull_request", action: "opened" },
      {},
    );
    expect(mapped).toBe("PR_OPENED");
  });

  it("moves RUNNING to PR_OPEN when PR is opened", () => {
    const service = new GitHubBridgeService();
    const job = createJob("RUNNING");

    const result = service.handleWebhook({
      job,
      event: { deliveryId: "d2", eventType: "pull_request", action: "opened" },
      payload: {},
    });

    expect(result.ok).toBe(true);
    expect(job.state).toBe("PR_OPEN");
  });

  it("maps /copilot-cancel comment to CANCEL", () => {
    const mapped = mapGitHubEventToOrchestrationEvent(
      { deliveryId: "d3", eventType: "issue_comment", action: "created" },
      { comment: { body: "/copilot-cancel" } },
    );
    expect(mapped).toBe("CANCEL");
  });
});