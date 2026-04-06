import type { WebhookRequestBody } from "@line/bot-sdk";
import type { NextFunction, Request, Response } from "express";
import { danger, loadConfig, logVerbose } from "openclaw/plugin-sdk";
import type { OpenClawConfig, RuntimeEnv } from "openclaw/plugin-sdk";
import { resolveLineAccount } from "./accounts.js";
import { handleLineWebhookEvents } from "./bot-handlers.js";
import type { LineInboundContext } from "./bot-message-context.js";
import type { LineExecApprovalHandler } from "./exec-approvals.js";
import type { ResolvedLineAccount } from "./types.js";
import { startLineWebhook } from "./webhook.js";

export interface LineBotOptions {
  channelAccessToken: string;
  channelSecret: string;
  accountId?: string;
  runtime?: RuntimeEnv;
  config?: OpenClawConfig;
  mediaMaxMb?: number;
  onMessage?: (ctx: LineInboundContext) => Promise<void>;
  /** Optional exec approval handler for resolving approval postbacks. */
  execApprovalHandler?: LineExecApprovalHandler;
}

export interface LineBot {
  handleWebhook: (body: WebhookRequestBody) => Promise<void>;
  account: ResolvedLineAccount;
}

export function createLineBot(opts: LineBotOptions): LineBot {
  const runtime: RuntimeEnv = opts.runtime ?? {
    log: console.log,
    error: console.error,
    exit: (code: number): never => {
      throw new Error(`exit ${code}`);
    },
  };

  const cfg = opts.config ?? loadConfig();
  const account = resolveLineAccount({
    cfg,
    accountId: opts.accountId,
  });

  const mediaMaxBytes = (opts.mediaMaxMb ?? account.config.mediaMaxMb ?? 10) * 1024 * 1024;

  const processMessage =
    opts.onMessage ??
    (async () => {
      logVerbose("line: no message handler configured");
    });

  const handleWebhook = async (body: WebhookRequestBody): Promise<void> => {
    if (!body.events || body.events.length === 0) {
      return;
    }

    await handleLineWebhookEvents(body.events, {
      cfg,
      account,
      runtime,
      mediaMaxBytes,
      processMessage,
      execApprovalHandler: opts.execApprovalHandler,
    });
  };

  return {
    handleWebhook,
    account,
  };
}

export function createLineWebhookCallback(
  bot: LineBot,
  channelSecret: string,
  path = "/line/webhook",
): {
  path: string;
  handler: (req: Request, res: Response, _next: NextFunction) => Promise<void>;
} {
  const { handler } = startLineWebhook({
    channelSecret,
    onEvents: bot.handleWebhook,
    path,
  });

  return { path, handler };
}
