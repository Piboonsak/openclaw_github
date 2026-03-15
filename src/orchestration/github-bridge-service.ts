import { applyTransition } from "./state-machine.js";
import type { NormalizedGitHubEvent } from "./event-ingestion.js";
import type { OrchestrationEventType, OrchestrationJob, TransitionResult } from "./types.js";

export function mapGitHubEventToOrchestrationEvent(
  event: NormalizedGitHubEvent,
  payload: Record<string, unknown>,
): OrchestrationEventType | undefined {
  if (event.eventType === "pull_request") {
    if (event.action === "opened") {
      return "PR_OPENED";
    }
    if (event.action === "closed") {
      const merged = (payload.pull_request as { merged?: boolean } | undefined)?.merged;
      return merged ? "PR_MERGED" : "FAILED_RETRYABLE";
    }
  }

  if (event.eventType === "pull_request_review" && event.action === "submitted") {
    const state = String((payload.review as { state?: string } | undefined)?.state ?? "").toLowerCase();
    if (state === "changes_requested") {
      return "PR_CHANGES_REQUESTED";
    }
  }

  if (event.eventType === "workflow_run" && event.action === "completed") {
    const conclusion = String((payload.workflow_run as { conclusion?: string } | undefined)?.conclusion ?? "").toLowerCase();
    if (conclusion === "success") {
      return "DISPATCHED";
    }
    if (conclusion === "cancelled") {
      return "CANCEL";
    }
    return "FAILED_RETRYABLE";
  }

  if (event.eventType === "issue_comment" && event.action === "created") {
    const body = String((payload.comment as { body?: string } | undefined)?.body ?? "").trim();
    if (body.startsWith("/copilot-resume")) {
      return "RESUMED";
    }
    if (body.startsWith("/copilot-cancel")) {
      return "CANCEL";
    }
  }

  return undefined;
}

export class GitHubBridgeService {
  handleWebhook(params: {
    job: OrchestrationJob;
    event: NormalizedGitHubEvent;
    payload: Record<string, unknown>;
    at?: Date;
  }): TransitionResult {
    const mapped = mapGitHubEventToOrchestrationEvent(params.event, params.payload);
    if (!mapped) {
      return { ok: true, reason: "No mapped transition for this webhook event" };
    }
    return applyTransition(params.job, mapped, params.at);
  }
}