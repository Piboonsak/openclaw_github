import type { AgentMessage } from "@mariozechner/pi-agent-core";
import { estimateTokens } from "@mariozechner/pi-coding-agent";
import type { OpenClawConfig } from "../../config/config.js";
import { normalizeProviderId } from "../provider-id.js";

const THREAD_SUFFIX_REGEX = /^(.*)(?::(?:thread|topic):\d+)$/i;

function stripThreadSuffix(value: string): string {
  const match = value.match(THREAD_SUFFIX_REGEX);
  return match?.[1] ?? value;
}

/**
 * Limits conversation history to the last N user turns (and their associated
 * assistant responses). This reduces token usage for long-running DM sessions.
 */
export function limitHistoryTurns(
  messages: AgentMessage[],
  limit: number | undefined,
): AgentMessage[] {
  if (!limit || limit <= 0 || messages.length === 0) {
    return messages;
  }

  let userCount = 0;
  let lastUserIndex = messages.length;

  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "user") {
      userCount++;
      if (userCount > limit) {
        return messages.slice(lastUserIndex);
      }
      lastUserIndex = i;
    }
  }
  return messages;
}

/**
 * Extract provider + user ID from a session key and look up dmHistoryLimit.
 * Supports per-DM overrides and provider defaults.
 * For channel/group sessions, uses historyLimit from provider config.
 */
export function getHistoryLimitFromSessionKey(
  sessionKey: string | undefined,
  config: OpenClawConfig | undefined,
): number | undefined {
  if (!sessionKey || !config) {
    return undefined;
  }

  const parts = sessionKey.split(":").filter(Boolean);
  const providerParts = parts.length >= 3 && parts[0] === "agent" ? parts.slice(2) : parts;

  const provider = normalizeProviderId(providerParts[0] ?? "");
  if (!provider) {
    return undefined;
  }

  const kind = providerParts[1]?.toLowerCase();
  const userIdRaw = providerParts.slice(2).join(":");
  const userId = stripThreadSuffix(userIdRaw);

  const resolveProviderConfig = (
    cfg: OpenClawConfig | undefined,
    providerId: string,
  ):
    | {
        historyLimit?: number;
        dmHistoryLimit?: number;
        dms?: Record<string, { historyLimit?: number }>;
      }
    | undefined => {
    const channels = cfg?.channels;
    if (!channels || typeof channels !== "object") {
      return undefined;
    }
    for (const [configuredProviderId, value] of Object.entries(
      channels as Record<string, unknown>,
    )) {
      if (normalizeProviderId(configuredProviderId) !== providerId) {
        continue;
      }
      if (!value || typeof value !== "object" || Array.isArray(value)) {
        return undefined;
      }
      return value as {
        historyLimit?: number;
        dmHistoryLimit?: number;
        dms?: Record<string, { historyLimit?: number }>;
      };
    }
    return undefined;
  };

  const providerConfig = resolveProviderConfig(config, provider);
  if (!providerConfig) {
    return undefined;
  }

  // For DM sessions: per-DM override -> dmHistoryLimit.
  // Accept both "direct" (new) and "dm" (legacy) for backward compat.
  if (kind === "dm" || kind === "direct") {
    if (userId && providerConfig.dms?.[userId]?.historyLimit !== undefined) {
      return providerConfig.dms[userId].historyLimit;
    }
    return providerConfig.dmHistoryLimit;
  }

  // For channel/group sessions: use historyLimit from provider config
  // This prevents context overflow in long-running channel sessions
  if (kind === "channel" || kind === "group") {
    return providerConfig.historyLimit;
  }

  return undefined;
}

/**
 * @deprecated Use getHistoryLimitFromSessionKey instead.
 * Alias for backward compatibility.
 */
export const getDmHistoryLimitFromSessionKey = getHistoryLimitFromSessionKey;

/**
 * Limits conversation history by total token budget using a sliding window approach.
 * Prioritizes keeping the most recent messages within the token budget.
 * Falls back to keeping at least the last message if budget is very tight.
 *
 * **Default token budget: 12,000 tokens** (conservative to leave room for system prompt + response)
 */
export function limitHistoryByTokenBudget(
  messages: AgentMessage[],
  budgetTokens: number | undefined = 12_000,
): AgentMessage[] {
  // No-op cases: no budget specified, no messages, or empty budget
  if (!budgetTokens || budgetTokens <= 0 || messages.length === 0) {
    return messages;
  }

  let totalTokens = 0;
  let currentBudget = Math.max(1, Math.floor(budgetTokens));
  const kept: AgentMessage[] = [];
  let tokenEstimationFailed = false;

  // Iterate backwards from newest to oldest message
  // Add messages if they fit within budget, stop when budget exceeded
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    let messageTokens = 0;

    // Estimate tokens for this message
    try {
      messageTokens = estimateTokens(msg);
    } catch (err) {
      // If estimation fails, abort token-based limiting and return all
      // (better to send too many tokens and fail clearly than silently drop messages)
      if (!tokenEstimationFailed) {
        console.warn(
          `[limitHistoryByTokenBudget] Token estimation failed: ${String(err)}. ` +
            `Returning full history to avoid silent message loss.`,
        );
        tokenEstimationFailed = true;
      }
      return messages;
    }

    // Check if adding this message would exceed budget
    if (totalTokens + messageTokens > currentBudget) {
      // Budget exceeded, stop iterating
      break;
    }

    // Message fits, add it (at beginning since we're iterating backwards)
    kept.unshift(msg);
    totalTokens += messageTokens;
  }

  // Safety: always keep at least the last message to maintain conversation continuity
  if (kept.length === 0 && messages.length > 0) {
    kept.push(messages[messages.length - 1]);
  }

  return kept;
}
