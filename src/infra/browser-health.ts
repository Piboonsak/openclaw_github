import { setTimeout as delay } from "node:timers/promises";

/** Configuration for the browser health monitor. */
export type BrowserHealthConfig = {
  /** How often to poll browser health (ms). Default: 30_000. */
  checkIntervalMs?: number;
  /** Maximum restart attempts before entering degraded state. Default: 5. */
  maxRestartAttempts?: number;
  /** Delay between restart attempts (ms). Default: 2_000. */
  restartDelayMs?: number;
};

/** Current health status of the monitored browser. */
export type BrowserHealthStatus = "healthy" | "degraded" | "stopped";

/** Events emitted by the health monitor for logging/observability. */
export type BrowserHealthEvent =
  | { type: "started" }
  | { type: "crashed" }
  | { type: "restarted"; attempt: number }
  | { type: "restart-failed"; attempt: number; error: string }
  | { type: "degraded"; maxAttempts: number }
  | { type: "stopped" };

/** Handle returned by `createBrowserHealthMonitor`. */
export type BrowserHealthMonitor = {
  /**
   * Verifies the browser is reachable on startup (attempting restarts if needed),
   * then begins periodic health polling.
   */
  start(): Promise<void>;
  /** Stops health polling and releases resources. */
  stop(): void;
  /** Returns the current health status. */
  getStatus(): BrowserHealthStatus;
};

const DEFAULTS: Required<BrowserHealthConfig> = {
  checkIntervalMs: 30_000,
  maxRestartAttempts: 5,
  restartDelayMs: 2_000,
};

/**
 * Creates a browser health monitor that periodically checks whether the browser
 * is alive and automatically attempts to restart it on failure.
 *
 * Graceful degradation: after `maxRestartAttempts` consecutive failures the
 * monitor stops and reports `"degraded"` status so callers can disable
 * browser-dependent features.
 */
export function createBrowserHealthMonitor(params: {
  checkHealth: () => Promise<boolean>;
  restart: () => Promise<void>;
  config?: BrowserHealthConfig;
  onEvent?: (event: BrowserHealthEvent) => void;
}): BrowserHealthMonitor {
  const cfg: Required<BrowserHealthConfig> = {
    checkIntervalMs: params.config?.checkIntervalMs ?? DEFAULTS.checkIntervalMs,
    maxRestartAttempts: params.config?.maxRestartAttempts ?? DEFAULTS.maxRestartAttempts,
    restartDelayMs: params.config?.restartDelayMs ?? DEFAULTS.restartDelayMs,
  };

  let status: BrowserHealthStatus = "stopped";
  let intervalHandle: ReturnType<typeof setInterval> | null = null;
  // Consecutive restart failures (reset to 0 on success).
  let failureStreak = 0;

  function emit(event: BrowserHealthEvent): void {
    try {
      params.onEvent?.(event);
    } catch {
      // Never let observer errors propagate into the monitor loop.
    }
  }

  /** Attempt to restart the browser; increments the failure streak. */
  async function attemptRestart(): Promise<boolean> {
    failureStreak += 1;
    emit({ type: "crashed" });

    if (cfg.restartDelayMs > 0) {
      await delay(cfg.restartDelayMs);
    }

    try {
      await params.restart();
      // Verify the restart actually worked.
      if (await params.checkHealth()) {
        emit({ type: "restarted", attempt: failureStreak });
        failureStreak = 0;
        return true;
      }
    } catch (err) {
      emit({
        type: "restart-failed",
        attempt: failureStreak,
        error: err instanceof Error ? err.message : String(err),
      });
    }

    if (failureStreak >= cfg.maxRestartAttempts) {
      status = "degraded";
      stop();
      emit({ type: "degraded", maxAttempts: cfg.maxRestartAttempts });
    }

    return false;
  }

  /** One health-check tick, called on the interval. */
  async function tick(): Promise<void> {
    if (status === "stopped" || status === "degraded") {
      return;
    }
    try {
      const alive = await params.checkHealth();
      if (alive) {
        failureStreak = 0;
        status = "healthy";
        return;
      }
    } catch {
      // Treat check errors as a failed health check.
    }

    await attemptRestart();
  }

  function stop(): void {
    if (intervalHandle !== null) {
      clearInterval(intervalHandle);
      intervalHandle = null;
    }
    if (status !== "degraded") {
      status = "stopped";
      emit({ type: "stopped" });
    }
  }

  async function start(): Promise<void> {
    // Startup verification: ensure the browser is reachable before monitoring.
    const alive = await params.checkHealth().catch(() => false);
    if (!alive) {
      // Try to restart up to maxRestartAttempts times before giving up.
      let startupOk = false;
      for (let attempt = 1; attempt <= cfg.maxRestartAttempts; attempt++) {
        if (cfg.restartDelayMs > 0) {
          await delay(cfg.restartDelayMs);
        }
        try {
          await params.restart();
          if (await params.checkHealth().catch(() => false)) {
            emit({ type: "restarted", attempt });
            failureStreak = 0;
            startupOk = true;
            break;
          }
        } catch (err) {
          emit({
            type: "restart-failed",
            attempt,
            error: err instanceof Error ? err.message : String(err),
          });
        }
      }

      if (!startupOk) {
        status = "degraded";
        emit({ type: "degraded", maxAttempts: cfg.maxRestartAttempts });
        return;
      }
    }

    status = "healthy";
    emit({ type: "started" });

    // Begin periodic health polling.
    intervalHandle = setInterval(() => {
      // Fire-and-forget; errors are handled inside tick().
      tick().catch(() => {});
    }, cfg.checkIntervalMs);
  }

  return { start, stop, getStatus: () => status };
}
