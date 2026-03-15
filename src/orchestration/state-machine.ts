import type {
  OrchestrationEventType,
  OrchestrationJob,
  OrchestrationState,
  TransitionResult,
} from "./types.js";

const TERMINAL_STATES = new Set<OrchestrationState>([
  "PREFLIGHT_FAILED",
  "TERMINAL_FAILURE",
  "TIMED_OUT",
  "CANCELED",
  "MERGED",
  "SUCCEEDED",
]);

const TRANSITIONS: Record<OrchestrationState, Partial<Record<OrchestrationEventType, OrchestrationState>>> = {
  CREATED: {
    PREFLIGHT_PASSED: "QUEUED",
    PREFLIGHT_FAILED: "PREFLIGHT_FAILED",
    CANCEL: "CANCELED",
  },
  PREFLIGHT: {
    PREFLIGHT_PASSED: "QUEUED",
    PREFLIGHT_FAILED: "PREFLIGHT_FAILED",
  },
  QUEUED: {
    DISPATCHED: "RUNNING",
    CANCEL: "CANCELED",
  },
  RUNNING: {
    PR_OPENED: "PR_OPEN",
    FAILED_RETRYABLE: "RETRYABLE_FAILURE",
    FAILED_TERMINAL: "TERMINAL_FAILURE",
    APPROVAL_REQUIRED: "PAUSED_APPROVAL",
    TIMEOUT: "TIMED_OUT",
    CANCEL: "CANCELED",
  },
  PR_OPEN: {
    PR_CHANGES_REQUESTED: "CHANGES_REQUESTED",
    PR_MERGED: "MERGED",
    CANCEL: "CANCELED",
  },
  CHANGES_REQUESTED: {
    RESUMED: "RUNNING",
    CANCEL: "CANCELED",
  },
  RETRYABLE_FAILURE: {
    RESUMED: "RUNNING",
    CANCEL: "CANCELED",
  },
  PAUSED_APPROVAL: {
    RESUMED: "RUNNING",
    CANCEL: "CANCELED",
  },
  PREFLIGHT_FAILED: {},
  TERMINAL_FAILURE: {},
  TIMED_OUT: {},
  CANCELED: {},
  MERGED: {},
  SUCCEEDED: {},
};

export function canTransition(state: OrchestrationState, eventType: OrchestrationEventType): TransitionResult {
  if (TERMINAL_STATES.has(state)) {
    return { ok: false, reason: `State ${state} is terminal` };
  }
  const nextState = TRANSITIONS[state][eventType];
  if (!nextState) {
    return { ok: false, reason: `Transition ${state} -> ${eventType} is not allowed` };
  }
  return { ok: true, nextState };
}

export function applyTransition(job: OrchestrationJob, eventType: OrchestrationEventType, at: Date = new Date()): TransitionResult {
  const evaluation = canTransition(job.state, eventType);
  if (!evaluation.ok || !evaluation.nextState) {
    return evaluation;
  }

  if (eventType === "RESUMED" && job.retryCount >= job.maxRetries) {
    return { ok: false, reason: `Retry limit reached (${job.maxRetries})` };
  }

  if (eventType === "RESUMED") {
    job.retryCount += 1;
  }

  job.state = evaluation.nextState;
  job.updatedAt = at.toISOString();
  job.events.push({ type: eventType, at: job.updatedAt });
  return { ok: true, nextState: job.state };
}
