import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  type BrowserHealthEvent,
  type BrowserHealthMonitor,
  createBrowserHealthMonitor,
} from "./browser-health.js";

/**
 * Helpers to advance fake timers and let the monitor's async tick() settle.
 * We need at least one micro-task flush after advancing time.
 */
async function tickTimers(ms = 0): Promise<void> {
  await vi.advanceTimersByTimeAsync(ms);
}

describe("createBrowserHealthMonitor", () => {
  let events: BrowserHealthEvent[];
  let checkHealth: ReturnType<typeof vi.fn>;
  let restart: ReturnType<typeof vi.fn>;

  function makeMonitor(overrides?: {
    checkIntervalMs?: number;
    maxRestartAttempts?: number;
    restartDelayMs?: number;
  }): BrowserHealthMonitor {
    return createBrowserHealthMonitor({
      checkHealth,
      restart,
      config: {
        checkIntervalMs: overrides?.checkIntervalMs ?? 1_000,
        maxRestartAttempts: overrides?.maxRestartAttempts ?? 3,
        restartDelayMs: overrides?.restartDelayMs ?? 0,
      },
      onEvent: (e) => events.push(e),
    });
  }

  beforeEach(() => {
    events = [];
    checkHealth = vi.fn();
    restart = vi.fn();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ---------------------------------------------------------------------------
  // getStatus()
  // ---------------------------------------------------------------------------

  describe("getStatus()", () => {
    it("returns 'stopped' before start() is called", () => {
      const monitor = makeMonitor();
      expect(monitor.getStatus()).toBe("stopped");
    });

    it("returns 'healthy' after a successful start()", async () => {
      checkHealth.mockResolvedValue(true);
      const monitor = makeMonitor();
      await monitor.start();
      expect(monitor.getStatus()).toBe("healthy");
      monitor.stop();
    });

    it("returns 'stopped' after stop() is called", async () => {
      checkHealth.mockResolvedValue(true);
      const monitor = makeMonitor();
      await monitor.start();
      monitor.stop();
      expect(monitor.getStatus()).toBe("stopped");
    });
  });

  // ---------------------------------------------------------------------------
  // start() — startup verification
  // ---------------------------------------------------------------------------

  describe("start() — startup verification", () => {
    it("emits 'started' when browser is already healthy", async () => {
      checkHealth.mockResolvedValue(true);
      const monitor = makeMonitor();
      await monitor.start();
      expect(events).toContainEqual({ type: "started" });
      monitor.stop();
    });

    it("restarts browser once if startup check fails then succeeds", async () => {
      // First checkHealth (startup) fails; restart brings it back.
      checkHealth
        .mockResolvedValueOnce(false) // startup check
        .mockResolvedValueOnce(true); // post-restart verification
      restart.mockResolvedValue(undefined);

      const monitor = makeMonitor();
      await monitor.start();

      expect(restart).toHaveBeenCalledTimes(1);
      expect(events).toContainEqual(expect.objectContaining({ type: "restarted", attempt: 1 }));
      expect(events).toContainEqual({ type: "started" });
      expect(monitor.getStatus()).toBe("healthy");
      monitor.stop();
    });

    it("enters 'degraded' when browser never starts within maxRestartAttempts", async () => {
      // All checks fail.
      checkHealth.mockResolvedValue(false);
      restart.mockResolvedValue(undefined);

      const monitor = makeMonitor({ maxRestartAttempts: 3 });
      await monitor.start();

      expect(restart).toHaveBeenCalledTimes(3);
      expect(monitor.getStatus()).toBe("degraded");
      expect(events).toContainEqual({ type: "degraded", maxAttempts: 3 });
      // 'started' must NOT be emitted if we degraded.
      expect(events).not.toContainEqual({ type: "started" });
    });

    it("emits 'restart-failed' when restart() throws during startup", async () => {
      checkHealth.mockResolvedValue(false);
      restart.mockRejectedValue(new Error("spawn error"));

      const monitor = makeMonitor({ maxRestartAttempts: 2 });
      await monitor.start();

      expect(events.some((e) => e.type === "restart-failed")).toBe(true);
      expect(monitor.getStatus()).toBe("degraded");
    });
  });

  // ---------------------------------------------------------------------------
  // Periodic health polling
  // ---------------------------------------------------------------------------

  describe("periodic health polling", () => {
    it("does not restart when browser stays healthy", async () => {
      checkHealth.mockResolvedValue(true);
      const monitor = makeMonitor({ checkIntervalMs: 500 });
      await monitor.start();

      // Advance past two check intervals.
      await tickTimers(1_200);

      expect(restart).not.toHaveBeenCalled();
      monitor.stop();
    });

    it("restarts browser when a periodic check fails then succeeds", async () => {
      // Startup OK; second periodic check fails; restart succeeds.
      checkHealth
        .mockResolvedValueOnce(true) // startup
        .mockResolvedValueOnce(false) // first periodic check (browser crashed)
        .mockResolvedValueOnce(true); // post-restart check
      restart.mockResolvedValue(undefined);

      const monitor = makeMonitor({ checkIntervalMs: 500 });
      await monitor.start();

      // Trigger one periodic tick.
      await tickTimers(600);

      expect(restart).toHaveBeenCalledTimes(1);
      expect(events).toContainEqual(expect.objectContaining({ type: "restarted" }));
      monitor.stop();
    });

    it("enters 'degraded' after maxRestartAttempts consecutive periodic failures", async () => {
      checkHealth
        .mockResolvedValueOnce(true) // startup
        .mockResolvedValue(false); // all periodic checks fail
      restart.mockResolvedValue(undefined);

      const monitor = makeMonitor({ checkIntervalMs: 100, maxRestartAttempts: 2 });
      await monitor.start();

      // Advance enough ticks to exhaust restart budget.
      await tickTimers(1_000);

      expect(monitor.getStatus()).toBe("degraded");
      expect(events).toContainEqual({ type: "degraded", maxAttempts: 2 });
    });

    it("resets failure streak when browser recovers", async () => {
      checkHealth
        .mockResolvedValueOnce(true) // startup
        .mockResolvedValueOnce(false) // tick 1: crash
        .mockResolvedValueOnce(true) // restart verify success
        .mockResolvedValueOnce(true); // tick 2: still healthy
      restart.mockResolvedValue(undefined);

      const monitor = makeMonitor({ checkIntervalMs: 200, maxRestartAttempts: 3 });
      await monitor.start();

      await tickTimers(500);

      // After recovery the monitor stays healthy and does not degrade.
      expect(monitor.getStatus()).toBe("healthy");
      monitor.stop();
    });
  });

  // ---------------------------------------------------------------------------
  // stop()
  // ---------------------------------------------------------------------------

  describe("stop()", () => {
    it("emits 'stopped' event", async () => {
      checkHealth.mockResolvedValue(true);
      const monitor = makeMonitor();
      await monitor.start();
      monitor.stop();
      expect(events).toContainEqual({ type: "stopped" });
    });

    it("stops the periodic interval after stop()", async () => {
      checkHealth.mockResolvedValue(true);
      const monitor = makeMonitor({ checkIntervalMs: 200 });
      await monitor.start();
      monitor.stop();

      const callsBefore = checkHealth.mock.calls.length;
      await tickTimers(1_000);
      // No new checkHealth calls should happen after stop().
      expect(checkHealth.mock.calls.length).toBe(callsBefore);
    });

    it("is idempotent — calling stop() twice does not throw", async () => {
      checkHealth.mockResolvedValue(true);
      const monitor = makeMonitor();
      await monitor.start();
      expect(() => {
        monitor.stop();
        monitor.stop();
      }).not.toThrow();
    });

    it("does not emit 'stopped' again when already degraded", async () => {
      checkHealth.mockResolvedValue(false);
      restart.mockResolvedValue(undefined);

      const monitor = makeMonitor({ maxRestartAttempts: 1 });
      await monitor.start();

      // Already degraded at this point.
      const eventsBefore = [...events];
      monitor.stop();

      // The only 'stopped' events should be from before we called stop() manually.
      const stoppedEvents = events.filter((e) => e.type === "stopped");
      const stoppedBefore = eventsBefore.filter((e) => e.type === "stopped");
      expect(stoppedEvents.length).toBe(stoppedBefore.length);
    });
  });

  // ---------------------------------------------------------------------------
  // Edge cases
  // ---------------------------------------------------------------------------

  describe("edge cases", () => {
    it("handles checkHealth() throwing during periodic tick", async () => {
      checkHealth
        .mockResolvedValueOnce(true) // startup
        .mockRejectedValueOnce(new Error("network error")) // tick throws
        .mockResolvedValue(true); // restart verify / subsequent checks

      restart.mockResolvedValue(undefined);

      const monitor = makeMonitor({ checkIntervalMs: 200, maxRestartAttempts: 3 });
      await monitor.start();
      await tickTimers(400);

      // Should not crash; status should recover or stay healthy.
      expect(["healthy", "degraded"]).toContain(monitor.getStatus());
      monitor.stop();
    });

    it("observer errors in onEvent do not crash the monitor", async () => {
      const throwingMonitor = createBrowserHealthMonitor({
        checkHealth: vi.fn().mockResolvedValue(true),
        restart: vi.fn(),
        config: { checkIntervalMs: 200, maxRestartAttempts: 3, restartDelayMs: 0 },
        onEvent: () => {
          throw new Error("observer exploded");
        },
      });

      await expect(throwingMonitor.start()).resolves.not.toThrow();
      throwingMonitor.stop();
    });
  });
});
