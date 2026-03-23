import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OpenClawConfig } from "../config/config.js";
import { resolveMainSessionKey } from "../config/sessions.js";
import {
  _heartbeat429Internals,
  runHeartbeatOnce,
  type HeartbeatDeps,
} from "./heartbeat-runner.js";
import { installHeartbeatRunnerTestRuntime } from "./heartbeat-runner.test-harness.js";
import { seedSessionStore, withTempHeartbeatSandbox } from "./heartbeat-runner.test-utils.js";

// Avoid pulling optional runtime deps during isolated runs.
vi.mock("jiti", () => ({ createJiti: () => () => ({}) }));

installHeartbeatRunnerTestRuntime();

describe("runHeartbeatOnce 429 suppression", () => {
  beforeEach(() => {
    _heartbeat429Internals.heartbeat429Suppression.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("suppresses repeated sends after a 429 response", async () => {
    await withTempHeartbeatSandbox(async ({ tmpDir, storePath, replySpy }) => {
      const cfg: OpenClawConfig = {
        agents: {
          defaults: {
            workspace: tmpDir,
            heartbeat: { every: "5m", target: "telegram" },
          },
        },
        channels: {
          telegram: {
            allowFrom: ["*"],
            accounts: {
              default: {
                allowFrom: ["*"],
                botToken: "test-token",
              },
            },
          },
        },
        session: { store: storePath },
      };

      const sessionKey = resolveMainSessionKey(cfg);
      await seedSessionStore(storePath, sessionKey, {
        lastChannel: "telegram",
        lastProvider: "telegram",
        lastTo: "123456789",
      });

      replySpy.mockResolvedValue({ text: "Final alert" });

      const sendTelegram = vi
        .fn<NonNullable<HeartbeatDeps["sendTelegram"]>>()
        .mockRejectedValue(new Error("429 Too Many Requests; retry-after 60s"));

      const deps: HeartbeatDeps = {
        getQueueSize: () => 0,
        nowMs: () => 0,
        sendTelegram,
      };

      const first = await runHeartbeatOnce({ cfg, deps });
      const second = await runHeartbeatOnce({ cfg, deps });

      expect(first.status).toBe("failed");
      if (first.status === "failed") {
        expect(first.reason).toContain("line-429-backoff");
      }

      expect(second.status).toBe("skipped");
      if (second.status === "skipped") {
        expect(second.reason).toBe("line-429-backoff");
      }

      // Main heartbeat delivery attempts once; next run is suppressed before send.
      expect(sendTelegram).toHaveBeenCalledTimes(1);
      expect(replySpy).toHaveBeenCalledTimes(1);
    });
  });
});
