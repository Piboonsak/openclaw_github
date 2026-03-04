import type { OpenClawConfig } from "../config/config.js";
import { loadSessionStore, resolveStorePath } from "../config/sessions.js";
import type { ExecApprovalForwardTarget } from "../config/types.approvals.js";
import { parseAgentSessionKey } from "../routing/session-key.js";
import { isDeliverableMessageChannel, normalizeMessageChannel } from "../utils/message-channel.js";
import type { ExecApprovalRequest } from "./exec-approvals.js";
import { resolveSessionDeliveryTarget } from "./outbound/targets.js";

/**
 * Channels that have component-based (rich) exec approval handlers.
 * Text-based forwarding should be skipped for these channels.
 */
export const RICH_APPROVAL_CHANNELS = new Set(["discord", "line"]);

/**
 * Check whether a target channel has a rich (component-based) approval handler
 * and should be skipped by the text-based forwarder.
 */
export function shouldSkipRichChannelForwarding(target: ExecApprovalForwardTarget): boolean {
  const channel = normalizeMessageChannel(target.channel) ?? target.channel;
  return RICH_APPROVAL_CHANNELS.has(channel);
}

/**
 * Resolve the delivery target for an exec approval request using the session store.
 * Returns the channel, recipient, and account info, or null if not resolvable.
 */
export function resolveApprovalTarget(params: {
  cfg: OpenClawConfig;
  request: ExecApprovalRequest;
}): ExecApprovalForwardTarget | null {
  const sessionKey = params.request.request.sessionKey?.trim();
  if (!sessionKey) {
    return null;
  }
  const parsed = parseAgentSessionKey(sessionKey);
  const agentId = parsed?.agentId ?? params.request.request.agentId ?? "main";
  const storePath = resolveStorePath(params.cfg.session?.store, { agentId });
  const store = loadSessionStore(storePath);
  const entry = store[sessionKey];
  if (!entry) {
    return null;
  }
  const target = resolveSessionDeliveryTarget({ entry, requestedChannel: "last" });
  if (!target.channel || !target.to) {
    return null;
  }
  if (!isDeliverableMessageChannel(target.channel)) {
    return null;
  }
  return {
    channel: target.channel,
    to: target.to,
    accountId: target.accountId,
    threadId: target.threadId,
  };
}
