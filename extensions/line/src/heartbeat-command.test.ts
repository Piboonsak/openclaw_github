import type { OpenClawConfig, OpenClawPluginApi, PluginRuntime } from "openclaw/plugin-sdk";
import { describe, expect, it, vi } from "vitest";
import { registerLineHeartbeatCommand } from "./heartbeat-command.js";
import { setLineRuntime } from "./runtime.js";

type CommandHandler = NonNullable<Parameters<OpenClawPluginApi["registerCommand"]>[0]["handler"]>;
type CommandContext = Parameters<CommandHandler>[0];

function makeConfig(
  heartbeat?: OpenClawConfig["agents"] extends infer A
    ? A extends { defaults?: infer D }
      ? D extends { heartbeat?: infer H }
        ? H
        : never
      : never
    : never,
): OpenClawConfig {
  return {
    agents: {
      defaults: {
        heartbeat: heartbeat ?? {},
      },
    },
  } as unknown as OpenClawConfig;
}

function makeCtx(
  args: string,
  heartbeat?: ReturnType<typeof makeConfig>["agents"] extends infer A
    ? A extends { defaults?: infer D }
      ? D extends { heartbeat?: infer H }
        ? H
        : never
      : never
    : never,
): CommandContext {
  return {
    args,
    config: makeConfig(heartbeat),
    channel: "line",
    isAuthorizedSender: true,
  } as unknown as CommandContext;
}

/**
 * Build a mock OpenClawPluginApi that captures the registered command handlers.
 */
function buildMockApi() {
  const commands = new Map<string, CommandHandler>();
  const api = {
    registerCommand(def: {
      name: string;
      description: string;
      acceptsArgs?: boolean;
      requireAuth?: boolean;
      handler: CommandHandler;
    }) {
      commands.set(def.name, def.handler);
    },
    registerChannel: vi.fn(),
  } as unknown as OpenClawPluginApi;
  return { api, commands };
}

/**
 * Build a mock PluginRuntime with a writable config.
 */
function buildMockRuntime(initialConfig: OpenClawConfig = {} as OpenClawConfig) {
  let stored = { ...initialConfig };
  const runtime = {
    config: {
      loadConfig: vi.fn(() => ({ ...stored })),
      writeConfigFile: vi.fn(async (cfg: OpenClawConfig) => {
        stored = { ...cfg };
      }),
    },
  } as unknown as PluginRuntime;
  return { runtime, getStored: () => stored };
}

describe("registerLineHeartbeatCommand", () => {
  it("registers a command named 'heartbeat'", () => {
    const { api, commands } = buildMockApi();
    const { runtime } = buildMockRuntime();
    setLineRuntime(runtime);
    registerLineHeartbeatCommand(api);
    expect(commands.has("heartbeat")).toBe(true);
  });

  describe("GET (no args)", () => {
    it("shows default interval when no heartbeat config set", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx(""));
      expect(result.text).toContain("Heartbeat interval: 30m");
      expect(result.text).toContain("Auto-adjust: disabled");
      expect(result.text).toContain("min 5m");
      expect(result.text).toContain("max 24h");
    });

    it("shows configured interval", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("", { every: "15m" }));
      expect(result.text).toContain("Heartbeat interval: 15m");
    });

    it("shows auto-adjust enabled when configured", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("", { every: "30m", autoAdjust: true }));
      expect(result.text).toContain("Auto-adjust: enabled");
    });

    it("shows custom min/max bounds", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("", { minEvery: "10m", maxEvery: "12h" }));
      expect(result.text).toContain("min 10m");
      expect(result.text).toContain("max 12h");
    });
  });

  describe("SET interval", () => {
    it("persists a valid interval to config", async () => {
      const { api, commands } = buildMockApi();
      const initial: OpenClawConfig = {
        agents: { defaults: { heartbeat: { every: "30m" } } },
      } as unknown as OpenClawConfig;
      const { runtime, getStored } = buildMockRuntime(initial);
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("15m"));
      expect(result.text).toContain("✅ Heartbeat interval updated: 15m");
      expect(getStored().agents?.defaults?.heartbeat?.every).toBe("15m");
    });

    it("persists an interval in hours", async () => {
      const { api, commands } = buildMockApi();
      const { runtime, getStored } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      await handler(makeCtx("2h"));
      expect(getStored().agents?.defaults?.heartbeat?.every).toBe("2h");
    });

    it("rejects an invalid duration string", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("notaduration"));
      expect(result.text).toContain('Invalid interval: "notaduration"');
    });

    it("rejects an interval shorter than the minimum bound", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      // Default min is 5m; 1m should be rejected
      const result = await handler(makeCtx("1m"));
      expect(result.text).toContain("Interval too short");
    });

    it("rejects an interval longer than the maximum bound", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      // Default max is 24h; 48h should be rejected
      const result = await handler(makeCtx("48h"));
      expect(result.text).toContain("Interval too long");
    });

    it("respects custom min bound from config", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      // Config has minEvery: 10m; 6m is below that
      const result = await handler(makeCtx("6m", { minEvery: "10m" }));
      expect(result.text).toContain("Interval too short");
      expect(result.text).toContain("10m");
    });

    it("returns an error message when writeConfigFile throws", async () => {
      const { api, commands } = buildMockApi();
      const runtime = {
        config: {
          loadConfig: vi.fn(() => ({}) as OpenClawConfig),
          writeConfigFile: vi.fn(async () => {
            throw new Error("disk full");
          }),
        },
      } as unknown as PluginRuntime;
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("30m"));
      expect(result.text).toContain("❌ Failed to update heartbeat interval");
      expect(result.text).toContain("disk full");
    });
  });

  describe("AUTO subcommand", () => {
    it("shows auto-adjust status when called with 'auto' only", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("auto", { autoAdjust: false }));
      expect(result.text).toContain("disabled");
    });

    it("enables auto-adjust with 'auto on'", async () => {
      const { api, commands } = buildMockApi();
      const initial: OpenClawConfig = {
        agents: { defaults: { heartbeat: { every: "30m" } } },
      } as unknown as OpenClawConfig;
      const { runtime, getStored } = buildMockRuntime(initial);
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("auto on"));
      expect(result.text).toContain("✅ Heartbeat auto-adjust enabled");
      expect(getStored().agents?.defaults?.heartbeat?.autoAdjust).toBe(true);
    });

    it("disables auto-adjust with 'auto off'", async () => {
      const { api, commands } = buildMockApi();
      const initial: OpenClawConfig = {
        agents: { defaults: { heartbeat: { autoAdjust: true } } },
      } as unknown as OpenClawConfig;
      const { runtime, getStored } = buildMockRuntime(initial);
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("auto off"));
      expect(result.text).toContain("✅ Heartbeat auto-adjust disabled");
      expect(getStored().agents?.defaults?.heartbeat?.autoAdjust).toBe(false);
    });

    it("rejects an unknown auto-adjust value", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("auto maybe"));
      expect(result.text).toContain('Invalid auto-adjust value: "maybe"');
    });

    it("returns an error message when writeConfigFile throws during auto toggle", async () => {
      const { api, commands } = buildMockApi();
      const runtime = {
        config: {
          loadConfig: vi.fn(() => ({}) as OpenClawConfig),
          writeConfigFile: vi.fn(async () => {
            throw new Error("permission denied");
          }),
        },
      } as unknown as PluginRuntime;
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("auto on"));
      expect(result.text).toContain("❌ Failed to update auto-adjust");
      expect(result.text).toContain("permission denied");
    });
  });

  describe("HELP", () => {
    it("shows usage on 'help'", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("help"));
      expect(result.text).toContain("Usage: /heartbeat");
    });

    it("shows usage on '?'", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineHeartbeatCommand(api);
      const handler = commands.get("heartbeat")!;
      const result = await handler(makeCtx("?"));
      expect(result.text).toContain("Usage: /heartbeat");
    });
  });
});
