import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  onDiagnosticEvent,
  resetDiagnosticEventsForTest,
  type DiagnosticToolLoopEvent,
} from "../infra/diagnostic-events.js";
import { resetDiagnosticSessionStateForTest } from "../logging/diagnostic-session-state.js";
import { getGlobalHookRunner } from "../plugins/hook-runner-global.js";
import { wrapToolWithBeforeToolCallHook } from "./pi-tools.before-tool-call.js";
import {
  CRITICAL_THRESHOLD,
  GLOBAL_CIRCUIT_BREAKER_THRESHOLD,
  RAPID_SUCCESSION_THRESHOLD,
} from "./tool-loop-detection.js";
import type { AnyAgentTool } from "./tools/common.js";

vi.mock("../plugins/hook-runner-global.js");

const mockGetGlobalHookRunner = vi.mocked(getGlobalHookRunner);

describe("before_tool_call loop detection behavior", () => {
  let hookRunner: {
    hasHooks: ReturnType<typeof vi.fn>;
    runBeforeToolCall: ReturnType<typeof vi.fn>;
  };
  const enabledLoopDetectionContext = {
    agentId: "main",
    sessionKey: "main",
    loopDetection: { enabled: true },
  };

  // Context that disables rapid_succession so tests for other detectors
  // (known_poll, generic_repeat, global_circuit_breaker) are not blocked early
  // by RAPID_SUCCESSION_THRESHOLD consecutive same-tool-name calls.
  const noRapidSuccessionContext = {
    agentId: "main",
    sessionKey: "main",
    loopDetection: { enabled: true, detectors: { rapidSuccession: false } },
  };

  const disabledLoopDetectionContext = {
    agentId: "main",
    sessionKey: "main",
    loopDetection: { enabled: false },
  };

  beforeEach(() => {
    resetDiagnosticSessionStateForTest();
    resetDiagnosticEventsForTest();
    hookRunner = {
      hasHooks: vi.fn(),
      runBeforeToolCall: vi.fn(),
    };
    // oxlint-disable-next-line typescript/no-explicit-any
    mockGetGlobalHookRunner.mockReturnValue(hookRunner as any);
    hookRunner.hasHooks.mockReturnValue(false);
  });

  function createWrappedTool(
    name: string,
    execute: ReturnType<typeof vi.fn>,
    loopDetectionContext = enabledLoopDetectionContext,
  ) {
    return wrapToolWithBeforeToolCallHook(
      { name, execute } as unknown as AnyAgentTool,
      loopDetectionContext,
    );
  }

  async function withToolLoopEvents(
    run: (emitted: DiagnosticToolLoopEvent[]) => Promise<void>,
    filter: (evt: DiagnosticToolLoopEvent) => boolean = () => true,
  ) {
    const emitted: DiagnosticToolLoopEvent[] = [];
    const stop = onDiagnosticEvent((evt) => {
      if (evt.type === "tool.loop" && filter(evt)) {
        emitted.push(evt);
      }
    });
    try {
      await run(emitted);
    } finally {
      stop();
    }
  }

  function createPingPongTools(options?: { withProgress?: boolean }) {
    const readExecute = options?.withProgress
      ? vi.fn().mockImplementation(async (toolCallId: string) => ({
          content: [{ type: "text", text: `read ${toolCallId}` }],
          details: { ok: true },
        }))
      : vi.fn().mockResolvedValue({
          content: [{ type: "text", text: "read ok" }],
          details: { ok: true },
        });
    const listExecute = options?.withProgress
      ? vi.fn().mockImplementation(async (toolCallId: string) => ({
          content: [{ type: "text", text: `list ${toolCallId}` }],
          details: { ok: true },
        }))
      : vi.fn().mockResolvedValue({
          content: [{ type: "text", text: "list ok" }],
          details: { ok: true },
        });
    return {
      readTool: createWrappedTool("read", readExecute),
      listTool: createWrappedTool("list", listExecute),
    };
  }

  async function runPingPongSequence(
    readTool: ReturnType<typeof createWrappedTool>,
    listTool: ReturnType<typeof createWrappedTool>,
    count: number,
  ) {
    for (let i = 0; i < count; i += 1) {
      if (i % 2 === 0) {
        await readTool.execute(`read-${i}`, { path: "/a.txt" }, undefined, undefined);
      } else {
        await listTool.execute(`list-${i}`, { dir: "/workspace" }, undefined, undefined);
      }
    }
  }

  function createGenericReadRepeatFixture(context = noRapidSuccessionContext) {
    const execute = vi.fn().mockResolvedValue({
      content: [{ type: "text", text: "same output" }],
      details: { ok: true },
    });
    return {
      tool: createWrappedTool("read", execute, context),
      params: { path: "/tmp/file" },
    };
  }

  it("blocks known poll loops when no progress repeats", async () => {
    const execute = vi.fn().mockResolvedValue({
      content: [{ type: "text", text: "(no new output)\n\nProcess still running." }],
      details: { status: "running", aggregated: "steady" },
    });
    // Disable rapid_succession so known_poll_no_progress detector can fire at CRITICAL_THRESHOLD.
    const tool = createWrappedTool("process", execute, noRapidSuccessionContext);
    const params = { action: "poll", sessionId: "sess-1" };

    for (let i = 0; i < CRITICAL_THRESHOLD; i += 1) {
      await expect(tool.execute(`poll-${i}`, params, undefined, undefined)).resolves.toBeDefined();
    }

    await expect(
      tool.execute(`poll-${CRITICAL_THRESHOLD}`, params, undefined, undefined),
    ).rejects.toThrow("CRITICAL");
  });

  it("does nothing when loopDetection.enabled is false", async () => {
    const execute = vi.fn().mockResolvedValue({
      content: [{ type: "text", text: "(no new output)\n\nProcess still running." }],
      details: { status: "running", aggregated: "steady" },
    });
    // oxlint-disable-next-line typescript/no-explicit-any
    const tool = wrapToolWithBeforeToolCallHook({ name: "process", execute } as any, {
      ...disabledLoopDetectionContext,
    });
    const params = { action: "poll", sessionId: "sess-off" };

    for (let i = 0; i < CRITICAL_THRESHOLD; i += 1) {
      await expect(tool.execute(`poll-${i}`, params, undefined, undefined)).resolves.toBeDefined();
    }
  });

  it("does not block known poll loops when output progresses", async () => {
    const execute = vi.fn().mockImplementation(async (toolCallId: string) => {
      return {
        content: [{ type: "text", text: `output ${toolCallId}` }],
        details: { status: "running", aggregated: `output ${toolCallId}` },
      };
    });
    // Disable rapid_succession so that CRITICAL_THRESHOLD + 5 consecutive calls
    // don't block; only known_poll with progressing output would (which should pass).
    const tool = createWrappedTool("process", execute, noRapidSuccessionContext);
    const params = { action: "poll", sessionId: "sess-2" };

    for (let i = 0; i < CRITICAL_THRESHOLD + 5; i += 1) {
      await expect(
        tool.execute(`poll-progress-${i}`, params, undefined, undefined),
      ).resolves.toBeDefined();
    }
  });

  it("keeps generic repeated calls warn-only below global breaker", async () => {
    const { tool, params } = createGenericReadRepeatFixture();

    for (let i = 0; i < CRITICAL_THRESHOLD + 5; i += 1) {
      await expect(tool.execute(`read-${i}`, params, undefined, undefined)).resolves.toBeDefined();
    }
  });

  it("blocks generic repeated no-progress calls at global breaker threshold", async () => {
    const { tool, params } = createGenericReadRepeatFixture();

    for (let i = 0; i < GLOBAL_CIRCUIT_BREAKER_THRESHOLD; i += 1) {
      await expect(tool.execute(`read-${i}`, params, undefined, undefined)).resolves.toBeDefined();
    }

    await expect(
      tool.execute(`read-${GLOBAL_CIRCUIT_BREAKER_THRESHOLD}`, params, undefined, undefined),
    ).rejects.toThrow("global circuit breaker");
  });

  it("coalesces repeated generic warning events into threshold buckets", async () => {
    await withToolLoopEvents(
      async (emitted) => {
        const { tool, params } = createGenericReadRepeatFixture();

        for (let i = 0; i < 21; i += 1) {
          await tool.execute(`read-bucket-${i}`, params, undefined, undefined);
        }

        const genericWarns = emitted.filter((evt) => evt.detector === "generic_repeat");
        expect(genericWarns.map((evt) => evt.count)).toEqual([10, 20]);
      },
      (evt) => evt.level === "warning",
    );
  });

  it("emits structured warning diagnostic events for ping-pong loops", async () => {
    await withToolLoopEvents(async (emitted) => {
      const { readTool, listTool } = createPingPongTools();
      await runPingPongSequence(readTool, listTool, 9);

      await listTool.execute("list-9", { dir: "/workspace" }, undefined, undefined);
      await readTool.execute("read-10", { path: "/a.txt" }, undefined, undefined);
      await listTool.execute("list-11", { dir: "/workspace" }, undefined, undefined);

      const pingPongWarns = emitted.filter(
        (evt) => evt.level === "warning" && evt.detector === "ping_pong",
      );
      expect(pingPongWarns).toHaveLength(1);
      const loopEvent = pingPongWarns[0];
      expect(loopEvent?.type).toBe("tool.loop");
      expect(loopEvent?.level).toBe("warning");
      expect(loopEvent?.action).toBe("warn");
      expect(loopEvent?.detector).toBe("ping_pong");
      expect(loopEvent?.count).toBe(10);
      expect(loopEvent?.toolName).toBe("list");
    });
  });

  it("blocks ping-pong loops at critical threshold and emits critical diagnostic events", async () => {
    await withToolLoopEvents(async (emitted) => {
      const { readTool, listTool } = createPingPongTools();
      await runPingPongSequence(readTool, listTool, CRITICAL_THRESHOLD - 1);

      await expect(
        listTool.execute(
          `list-${CRITICAL_THRESHOLD - 1}`,
          { dir: "/workspace" },
          undefined,
          undefined,
        ),
      ).rejects.toThrow("CRITICAL");

      const loopEvent = emitted.at(-1);
      expect(loopEvent?.type).toBe("tool.loop");
      expect(loopEvent?.level).toBe("critical");
      expect(loopEvent?.action).toBe("block");
      expect(loopEvent?.detector).toBe("ping_pong");
      expect(loopEvent?.count).toBe(CRITICAL_THRESHOLD);
      expect(loopEvent?.toolName).toBe("list");
    });
  });

  it("does not block ping-pong at critical threshold when outcomes are progressing", async () => {
    await withToolLoopEvents(async (emitted) => {
      const { readTool, listTool } = createPingPongTools({ withProgress: true });
      await runPingPongSequence(readTool, listTool, CRITICAL_THRESHOLD - 1);

      await expect(
        listTool.execute(
          `list-${CRITICAL_THRESHOLD - 1}`,
          { dir: "/workspace" },
          undefined,
          undefined,
        ),
      ).resolves.toBeDefined();

      const criticalPingPong = emitted.find(
        (evt) => evt.level === "critical" && evt.detector === "ping_pong",
      );
      expect(criticalPingPong).toBeUndefined();
      const warningPingPong = emitted.find(
        (evt) => evt.level === "warning" && evt.detector === "ping_pong",
      );
      expect(warningPingPong).toBeTruthy();
    });
  });

  it("emits structured critical diagnostic events when blocking loops", async () => {
    await withToolLoopEvents(async (emitted) => {
      const execute = vi.fn().mockResolvedValue({
        content: [{ type: "text", text: "(no new output)\n\nProcess still running." }],
        details: { status: "running", aggregated: "steady" },
      });
      // Disable rapid_succession so known_poll_no_progress fires at CRITICAL_THRESHOLD.
      const tool = createWrappedTool("process", execute, noRapidSuccessionContext);
      const params = { action: "poll", sessionId: "sess-crit" };

      for (let i = 0; i < CRITICAL_THRESHOLD; i += 1) {
        await tool.execute(`poll-${i}`, params, undefined, undefined);
      }

      await expect(
        tool.execute(`poll-${CRITICAL_THRESHOLD}`, params, undefined, undefined),
      ).rejects.toThrow("CRITICAL");

      const loopEvent = emitted.at(-1);
      expect(loopEvent?.type).toBe("tool.loop");
      expect(loopEvent?.level).toBe("critical");
      expect(loopEvent?.action).toBe("block");
      expect(loopEvent?.detector).toBe("known_poll_no_progress");
      expect(loopEvent?.count).toBe(CRITICAL_THRESHOLD);
      expect(loopEvent?.toolName).toBe("process");
    });
  });

  describe("rapid_succession storm detection (integration)", () => {
    it("blocks a tool storm and emits a critical diagnostic event with callTrace", async () => {
      await withToolLoopEvents(async (emitted) => {
        const execute = vi.fn().mockResolvedValue({
          content: [{ type: "text", text: "ok" }],
          details: { ok: true },
        });
        const tool = createWrappedTool("bash", execute);

        // Execute RAPID_SUCCESSION_THRESHOLD - 1 calls first to build up history
        for (let i = 0; i < RAPID_SUCCESSION_THRESHOLD - 1; i += 1) {
          await tool.execute(`bash-${i}`, { cmd: `echo ${i}` }, undefined, undefined);
        }

        // The Nth consecutive call should be blocked
        await expect(
          tool.execute(
            `bash-${RAPID_SUCCESSION_THRESHOLD}`,
            { cmd: "echo storm" },
            undefined,
            undefined,
          ),
        ).rejects.toThrow("CRITICAL");

        const stormEvent = emitted.find((evt) => evt.detector === "rapid_succession");
        expect(stormEvent?.type).toBe("tool.loop");
        expect(stormEvent?.level).toBe("critical");
        expect(stormEvent?.action).toBe("block");
        expect(stormEvent?.detector).toBe("rapid_succession");
        expect(stormEvent?.toolName).toBe("exec"); // "bash" normalizes to "exec" via TOOL_NAME_ALIASES
        expect(stormEvent?.count).toBe(RAPID_SUCCESSION_THRESHOLD);
        // callTrace must be present
        expect(Array.isArray(stormEvent?.callTrace)).toBe(true);
        expect(stormEvent?.callTrace?.length).toBeGreaterThan(0);
        expect(stormEvent?.callTrace?.at(-1)).toBe("exec"); // normalized alias
      });
    });

    it("does not block when a different tool interrupts the succession", async () => {
      const execute = vi.fn().mockResolvedValue({
        content: [{ type: "text", text: "ok" }],
        details: { ok: true },
      });
      const bashTool = createWrappedTool("bash", execute);
      const readTool = createWrappedTool("read", execute);

      for (let i = 0; i < RAPID_SUCCESSION_THRESHOLD - 1; i += 1) {
        await bashTool.execute(`bash-${i}`, { cmd: `echo ${i}` }, undefined, undefined);
      }
      // Interrupt with a different tool
      await readTool.execute("read-1", { path: "/a.txt" }, undefined, undefined);

      // bash again — streak is reset
      await expect(
        bashTool.execute("bash-final", { cmd: "echo after" }, undefined, undefined),
      ).resolves.toBeDefined();
    });

    it("emits callTrace field in warning diagnostic events", async () => {
      await withToolLoopEvents(async (emitted) => {
        const execute = vi.fn().mockResolvedValue({
          content: [{ type: "text", text: "ok" }],
          details: { ok: true },
        });
        const params = { action: "poll", sessionId: "sess-warn" };
        const tool = createWrappedTool("process", execute);

        for (let i = 0; i < 10; i += 1) {
          await tool.execute(`poll-${i}`, params, undefined, undefined);
        }

        const warnEvent = emitted.find((evt) => evt.level === "warning");
        if (warnEvent) {
          expect(Array.isArray(warnEvent.callTrace)).toBe(true);
        }
      });
    });
  });
});
