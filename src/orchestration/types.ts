export type OrchestrationState =
  | "CREATED"
  | "PREFLIGHT"
  | "QUEUED"
  | "RUNNING"
  | "PR_OPEN"
  | "CHANGES_REQUESTED"
  | "RETRYABLE_FAILURE"
  | "TERMINAL_FAILURE"
  | "PAUSED_APPROVAL"
  | "TIMED_OUT"
  | "CANCELED"
  | "MERGED"
  | "SUCCEEDED"
  | "PREFLIGHT_FAILED";

export type OrchestrationEventType =
  | "PREFLIGHT_PASSED"
  | "PREFLIGHT_FAILED"
  | "DISPATCHED"
  | "PR_OPENED"
  | "PR_CHANGES_REQUESTED"
  | "PR_MERGED"
  | "FAILED_RETRYABLE"
  | "FAILED_TERMINAL"
  | "RESUMED"
  | "APPROVAL_REQUIRED"
  | "TIMEOUT"
  | "CANCEL";

export interface OrchestrationTransitionEvent {
  type: OrchestrationEventType;
  at: string;
  detail?: string;
}

export interface OrchestrationTarget {
  owner: string;
  repo: string;
  ref: string;
}

export interface OrchestrationIntent {
  description: string;
  mode: "implement" | "review" | "merge" | "assign";
  issueRefs: string[];
}

export interface OrchestrationJob {
  jobId: string;
  state: OrchestrationState;
  createdAt: string;
  updatedAt: string;
  retryCount: number;
  maxRetries: number;
  target: OrchestrationTarget;
  intent: OrchestrationIntent;
  events: OrchestrationTransitionEvent[];
}

export interface TransitionResult {
  ok: boolean;
  reason?: string;
  nextState?: OrchestrationState;
}
