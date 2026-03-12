import type { OpenClawConfig } from "../config/config.js";
import { loadConfig } from "../config/config.js";
import { buildGatewayConnectionDetails } from "../gateway/call.js";
import { GatewayClient } from "../gateway/client.js";
import type { EventFrame } from "../gateway/protocol/index.js";
import type {
  ExecApprovalDecision,
  ExecApprovalRequest,
  ExecApprovalResolved,
} from "../infra/exec-approvals.js";
import { resolveApprovalTarget } from "../infra/exec-approval-utils.js";
import { createSubsystemLogger } from "../logging/subsystem.js";
import { normalizeMessageChannel, GATEWAY_CLIENT_MODES, GATEWAY_CLIENT_NAMES } from "../utils/message-channel.js";
import { createConfirmTemplate } from "./template-messages.js";
import { postbackAction } from "./actions.js";
import { pushTemplateMessage, pushMessageLine } from "./send.js";

export type { ExecApprovalRequest, ExecApprovalResolved };

const log = createSubsystemLogger("line/exec-approvals");

/** Prefix used in LINE postback data to identify exec approval actions. */
export const EXEC_APPROVAL_POSTBACK_PREFIX = "exec_approval=";

/** Maximum characters for the command preview in the confirm template (LINE limit: 240 total). */
const COMMAND_PREVIEW_MAX = 140;

/**
 * Retry helper with exponential backoff + jitter.
 * Retries up to maxAttempts times, with delays following: delay = baseDelayMs * (2 ^ attempt) + random jitter.
 * Only retries on transient errors (429, 5xx, network timeouts).
 */
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  options: {
    maxAttempts?: number;
    baseDelayMs?: number;
    maxDelayMs?: number;
    isRetryable?: (err: unknown) => boolean;
  } = {},
): Promise<T> {
  const maxAttempts = options.maxAttempts ?? 3;
  const baseDelayMs = options.baseDelayMs ?? 300;
  const maxDelayMs = options.maxDelayMs ?? 5000;

  const isRetryableError = options.isRetryable ?? ((err: unknown) => {
    const errMsg = String(err);
    // Retry on rate limit (429), server error (5xx), and network issues
    return /429|500|502|503|504|ECONNREFUSED|ETIMEDOUT|timeout/i.test(errMsg);
  });

  let lastErr: unknown;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      if (!isRetryableError(err) || attempt === maxAttempts - 1) {
        throw err;
      }
      // Exponential backoff with jitter
      const baseWait = Math.min(baseDelayMs * Math.pow(2, attempt), maxDelayMs);
      const jitter = Math.random() * baseWait * 0.1; // ±10% jitter
      const delayMs = Math.round(baseWait + jitter);
      log.debug(
        `retry attempt ${attempt + 1}/${maxAttempts} after ${delayMs}ms due to: ${String(lastErr)}`,
      );
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  throw lastErr;
}

/**
 * Parse exec approval postback data.
 * Expected format: `exec_approval=<decision>&id=<approvalId>`
 * Returns null if the data does not match the expected format.
 */
export function parseExecApprovalPostback(
  data: string,
): { decision: ExecApprovalDecision; approvalId: string } | null {
  if (!data.startsWith(EXEC_APPROVAL_POSTBACK_PREFIX)) {
    return null;
  }
  const params = new URLSearchParams(data);
  const action = params.get("exec_approval");
  const approvalId = params.get("id");
  if (!action || !approvalId) {
    return null;
  }
  // Map LINE button actions to gateway approval decisions
  if (action === "allow-once" || action === "allow-always" || action === "deny") {
    return { decision: action, approvalId };
  }
  return null;
}

/**
 * Build the confirm template text for an exec approval request.
 * Truncates the command if it exceeds the preview limit.
 */
function buildApprovalTemplateText(request: ExecApprovalRequest, nowMs: number): string {
  const command = request.request.command;
  const commandPreview =
    command.length > COMMAND_PREVIEW_MAX
      ? `${command.slice(0, COMMAND_PREVIEW_MAX)}…`
      : command;
  const expiresIn = Math.max(0, Math.round((request.expiresAtMs - nowMs) / 1000));
  return `⚠️ Exec approval required\n\nCommand:\n${commandPreview}\n\nExpires: ${expiresIn}s`;
}

function buildApprovalFallbackText(request: ExecApprovalRequest, nowMs: number): string {
  const command = request.request.command;
  const commandPreview =
    command.length > COMMAND_PREVIEW_MAX
      ? `${command.slice(0, COMMAND_PREVIEW_MAX)}…`
      : command;
  const expiresIn = Math.max(0, Math.round((request.expiresAtMs - nowMs) / 1000));
  return `⚠️ Exec approval required\nID: ${request.id}\nCommand: ${commandPreview}\nExpires in ${expiresIn}s\n\nPlease retry the command if approval buttons do not appear.`;
}

export type LineExecApprovalHandlerOpts = {
  config: OpenClawConfig;
  gatewayUrl?: string;
  /** Override for testing — defaults to loadConfig(). */
  getConfig?: () => OpenClawConfig;
  /** Override for testing. */
  pushTemplate?: typeof pushTemplateMessage;
  /** Override for testing. */
  pushText?: typeof pushMessageLine;
};

export class LineExecApprovalHandler {
  private gatewayClient: GatewayClient | null = null;
  private opts: LineExecApprovalHandlerOpts;
  private started = false;
  /** Cache original requests so handleApprovalResolved can look up delivery target. */
  private requestCache = new Map<string, ExecApprovalRequest>();

  constructor(opts: LineExecApprovalHandlerOpts) {
    this.opts = opts;
  }

  async start(): Promise<void> {
    if (this.started) {
      return;
    }
    this.started = true;

    const { url: gatewayUrl } = buildGatewayConnectionDetails({
      config: this.opts.config,
      url: this.opts.gatewayUrl,
    });

    this.gatewayClient = new GatewayClient({
      url: gatewayUrl,
      clientName: GATEWAY_CLIENT_NAMES.GATEWAY_CLIENT,
      clientDisplayName: "LINE Exec Approvals",
      mode: GATEWAY_CLIENT_MODES.BACKEND,
      scopes: ["operator.approvals"],
      onEvent: (evt) => this.handleGatewayEvent(evt),
      onHelloOk: () => {
        log.debug("connected to gateway");
      },
      onConnectError: (err) => {
        log.error(`connect error: ${err.message}`);
      },
      onClose: (code, reason) => {
        log.debug(`gateway closed: ${code} ${reason}`);
      },
    });

    this.gatewayClient.start();
    log.debug("started");
  }

  async stop(): Promise<void> {
    if (!this.started) {
      return;
    }
    this.started = false;
    this.gatewayClient?.stop();
    this.gatewayClient = null;
    this.requestCache.clear();
    log.debug("stopped");
  }

  /**
   * Resolve an exec approval via the gateway.
   * Called from LINE postback handler when a user taps Approve/Deny.
   * Returns true if the approval was resolved, false if expired/already resolved.
   */
  async resolveApproval(approvalId: string, decision: ExecApprovalDecision): Promise<boolean> {
    if (!this.gatewayClient) {
      log.error("gateway client not connected — cannot resolve approval");
      return false;
    }

    log.debug(`resolving ${approvalId} with ${decision}`);

    try {
      await this.gatewayClient.request("exec.approval.resolve", {
        id: approvalId,
        decision,
      });
      log.debug(`resolved ${approvalId} successfully`);
      return true;
    } catch (err) {
      log.error(`resolve failed for ${approvalId}: ${String(err)}`);
      return false;
    }
  }

  private handleGatewayEvent(evt: EventFrame): void {
    if (evt.event === "exec.approval.requested") {
      const request = evt.payload as ExecApprovalRequest;
      void this.handleApprovalRequested(request);
    } else if (evt.event === "exec.approval.resolved") {
      const resolved = evt.payload as ExecApprovalResolved;
      void this.handleApprovalResolved(resolved);
    }
  }

  private async handleApprovalRequested(request: ExecApprovalRequest): Promise<void> {
    const cfg = this.opts.getConfig?.() ?? this.opts.config;

    // Resolve the delivery target — only handle LINE targets
    const target = resolveApprovalTarget({ cfg, request });
    if (!target) {
      return;
    }
    const channel = normalizeMessageChannel(target.channel) ?? target.channel;
    if (channel !== "line") {
      return; // Not a LINE session — ignore (Discord/other handlers will pick it up)
    }

    // Cache the original request so handleApprovalResolved can look up the target
    this.requestCache.set(request.id, request);

    log.debug(`sending approval template for ${request.id} to ${target.to}`);

    const templateText = buildApprovalTemplateText(request, Date.now());
    const approveAction = postbackAction(
      "Approve",
      `exec_approval=allow-once&id=${request.id}`,
      "✅ Approved",
    );
    const denyAction = postbackAction(
      "Deny",
      `exec_approval=deny&id=${request.id}`,
      "❌ Denied",
    );
    const template = createConfirmTemplate(
      templateText,
      approveAction,
      denyAction,
      "⚠️ Exec approval required — tap to approve or deny",
    );

    try {
      const pushFn = this.opts.pushTemplate ?? pushTemplateMessage;
      await retryWithBackoff(
        () => pushFn(target.to, template, { accountId: target.accountId }),
        {
          maxAttempts: 3,
          baseDelayMs: 300,
          maxDelayMs: 5000,
        },
      );
      log.debug(`sent approval template for ${request.id} successfully`);
    } catch (err) {
      log.error(`failed to send approval template after retries: ${String(err)}`);
      try {
        const pushTextFn = this.opts.pushText ?? pushMessageLine;
        await retryWithBackoff(
          () =>
            pushTextFn(target.to, buildApprovalFallbackText(request, Date.now()), {
              accountId: target.accountId,
            }),
          {
            maxAttempts: 2,
            baseDelayMs: 500,
            maxDelayMs: 3000,
          },
        );
      } catch (fallbackErr) {
        log.error(`failed to send approval fallback text after retries: ${String(fallbackErr)}`);
      }
    }
  }

  private async handleApprovalResolved(resolved: ExecApprovalResolved): Promise<void> {
    const request = this.requestCache.get(resolved.id);
    this.requestCache.delete(resolved.id);
    if (!request) {
      log.debug(`no cached request for resolved ${resolved.id} — skipping`);
      return;
    }

    const cfg = this.opts.getConfig?.() ?? this.opts.config;
    const target = resolveApprovalTarget({ cfg, request });
    if (!target) {
      return;
    }
    const channel = normalizeMessageChannel(target.channel) ?? target.channel;
    if (channel !== "line") {
      return;
    }

    const label =
      resolved.decision === "allow-once"
        ? "allowed (once)"
        : resolved.decision === "allow-always"
          ? "allowed (always)"
          : "denied";
    const emoji = resolved.decision === "deny" ? "❌" : "✅";
    const text = `${emoji} Exec approval ${label}. ID: ${resolved.id}`;

    try {
      const pushFn = this.opts.pushText ?? pushMessageLine;
      await retryWithBackoff(
        () => pushFn(target.to, text, { accountId: target.accountId }),
        {
          maxAttempts: 2,
          baseDelayMs: 300,
          maxDelayMs: 3000,
        },
      );
    } catch (err) {
      log.error(`failed to send resolution message after retries: ${String(err)}`);
    }
  }
}
