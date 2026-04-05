import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { getLineRuntime } from "./runtime.js";

type CommandHandler = NonNullable<Parameters<OpenClawPluginApi["registerCommand"]>[0]["handler"]>;
type CommandContext = Parameters<CommandHandler>[0];

/** Default heartbeat interval (matches DEFAULT_HEARTBEAT_EVERY in auto-reply/heartbeat.ts). */
const DEFAULT_HEARTBEAT_EVERY = "30m";
/** Default minimum interval bound enforced by /heartbeat command. */
const DEFAULT_MIN_EVERY = "5m";
/** Default maximum interval bound enforced by /heartbeat command. */
const DEFAULT_MAX_EVERY = "24h";

const USAGE = `Usage: /heartbeat [interval|auto [on|off]|help]

View or change the heartbeat interval.

Examples:
  /heartbeat           → Show current heartbeat interval
  /heartbeat 15m       → Set interval to 15 minutes
  /heartbeat 30m       → Set interval to 30 minutes (default)
  /heartbeat 1h        → Set interval to 1 hour
  /heartbeat auto      → Show auto-adjust status
  /heartbeat auto on   → Enable auto-adjust (increases interval when agent is stressed)
  /heartbeat auto off  → Disable auto-adjust
  /heartbeat help      → Show this help message

Valid intervals: e.g., 5m, 10m, 30m, 1h, 2h, 24h (min: ${DEFAULT_MIN_EVERY}, max: ${DEFAULT_MAX_EVERY})`;

/**
 * Parse a simple duration string to milliseconds.
 * Supports: Nms, Ns, Nm, Nh, Nd (default unit: minutes).
 * Returns null if invalid or non-positive.
 */
function parseDurationMsSimple(raw: string): number | null {
  const trimmed = raw.trim().toLowerCase();
  const m = /^(\d+(?:\.\d+)?)(ms|s|m|h|d)?$/.exec(trimmed);
  if (!m) return null;
  const value = Number(m[1]);
  if (!Number.isFinite(value) || value <= 0) return null;
  const unit = (m[2] ?? "m") as "ms" | "s" | "m" | "h" | "d";
  const multiplier =
    unit === "ms"
      ? 1
      : unit === "s"
        ? 1000
        : unit === "m"
          ? 60_000
          : unit === "h"
            ? 3_600_000
            : 86_400_000;
  const ms = Math.round(value * multiplier);
  return Number.isFinite(ms) && ms > 0 ? ms : null;
}

export function registerLineHeartbeatCommand(api: OpenClawPluginApi): void {
  const handler = async (ctx: CommandContext) => {
    const argsStr = ctx.args?.trim() ?? "";

    // GET: show current status
    if (!argsStr) {
      const heartbeat = ctx.config.agents?.defaults?.heartbeat;
      const every = heartbeat?.every ?? DEFAULT_HEARTBEAT_EVERY;
      const minEvery = heartbeat?.minEvery ?? DEFAULT_MIN_EVERY;
      const maxEvery = heartbeat?.maxEvery ?? DEFAULT_MAX_EVERY;
      const autoAdjust = heartbeat?.autoAdjust ?? false;
      const autoStr = autoAdjust ? "enabled" : "disabled";
      return {
        text: `Heartbeat interval: ${every}\nAuto-adjust: ${autoStr}\nBounds: min ${minEvery} / max ${maxEvery}\n\n${USAGE}`,
      };
    }

    const firstArg = argsStr.toLowerCase();

    // HELP
    if (firstArg === "help" || firstArg === "?") {
      const every = ctx.config.agents?.defaults?.heartbeat?.every ?? DEFAULT_HEARTBEAT_EVERY;
      return {
        text: `Current heartbeat interval: ${every}\n\n${USAGE}`,
      };
    }

    // AUTO: toggle or query auto-adjust
    if (firstArg === "auto" || firstArg.startsWith("auto ")) {
      const parts = argsStr.split(/\s+/);
      const subCmd = parts[1]?.toLowerCase();

      // Show auto-adjust status
      if (!subCmd) {
        const autoAdjust = ctx.config.agents?.defaults?.heartbeat?.autoAdjust ?? false;
        const status = autoAdjust ? "enabled" : "disabled";
        return {
          text: `Auto-adjust is currently ${status}. Use "/heartbeat auto on" or "/heartbeat auto off" to change.`,
        };
      }

      let enable: boolean;
      if (subCmd === "on" || subCmd === "true" || subCmd === "1") {
        enable = true;
      } else if (subCmd === "off" || subCmd === "false" || subCmd === "0") {
        enable = false;
      } else {
        return {
          text: `Invalid auto-adjust value: "${subCmd}". Use "on" or "off".`,
        };
      }

      try {
        const runtime = getLineRuntime();
        const config = runtime.config.loadConfig();
        if (!config.agents) {
          config.agents = { defaults: {} };
        }
        if (!config.agents.defaults) {
          config.agents.defaults = {};
        }
        if (!config.agents.defaults.heartbeat) {
          config.agents.defaults.heartbeat = {};
        }
        config.agents.defaults.heartbeat.autoAdjust = enable;
        await runtime.config.writeConfigFile(config);
        const statusWord = enable ? "enabled" : "disabled";
        return { text: `✅ Heartbeat auto-adjust ${statusWord}` };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return { text: `❌ Failed to update auto-adjust: ${message}` };
      }
    }

    // SET: change interval
    const durationMs = parseDurationMsSimple(firstArg);
    if (durationMs === null) {
      return {
        text: `Invalid interval: "${argsStr}"\n\n${USAGE}`,
      };
    }

    // Validate against min/max bounds from config (or defaults)
    const heartbeat = ctx.config.agents?.defaults?.heartbeat;
    const minEvery = heartbeat?.minEvery ?? DEFAULT_MIN_EVERY;
    const maxEvery = heartbeat?.maxEvery ?? DEFAULT_MAX_EVERY;
    const minMs = parseDurationMsSimple(minEvery) ?? 0;
    const maxMs = parseDurationMsSimple(maxEvery) ?? Number.POSITIVE_INFINITY;

    if (durationMs < minMs) {
      return {
        text: `Interval too short. Minimum is ${minEvery}.\n\n${USAGE}`,
      };
    }
    if (durationMs > maxMs) {
      return {
        text: `Interval too long. Maximum is ${maxEvery}.\n\n${USAGE}`,
      };
    }

    try {
      const runtime = getLineRuntime();
      const config = runtime.config.loadConfig();
      if (!config.agents) {
        config.agents = { defaults: {} };
      }
      if (!config.agents.defaults) {
        config.agents.defaults = {};
      }
      if (!config.agents.defaults.heartbeat) {
        config.agents.defaults.heartbeat = {};
      }
      // Persist using the original (non-lowercased) arg to preserve user intent
      config.agents.defaults.heartbeat.every = ctx.args?.trim() ?? firstArg;
      await runtime.config.writeConfigFile(config);
      return { text: `✅ Heartbeat interval updated: ${ctx.args?.trim() ?? firstArg}` };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { text: `❌ Failed to update heartbeat interval: ${message}` };
    }
  };

  api.registerCommand({
    name: "heartbeat",
    description: "View or set the heartbeat interval (LINE).",
    acceptsArgs: true,
    requireAuth: false,
    handler,
  });
}
