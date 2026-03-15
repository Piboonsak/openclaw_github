import { createHmac, timingSafeEqual } from "node:crypto";
import { normalizeGitHubEvent, type NormalizedGitHubEvent } from "./event-ingestion.js";

export interface ParsedGitHubWebhook {
  normalized: NormalizedGitHubEvent;
  payload: Record<string, unknown>;
}

function getHeader(headers: Record<string, string | string[] | undefined>, key: string): string | undefined {
  const value = headers[key] ?? headers[key.toLowerCase()];
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function hashBody(secret: string, rawBody: string): string {
  return `sha256=${createHmac("sha256", secret).update(rawBody).digest("hex")}`;
}

export function verifyWebhookSignature(params: {
  secret: string;
  signature?: string;
  rawBody: string;
}): boolean {
  if (!params.signature) {
    return false;
  }
  const expected = Buffer.from(hashBody(params.secret, params.rawBody));
  const received = Buffer.from(params.signature);
  if (expected.length !== received.length) {
    return false;
  }
  return timingSafeEqual(expected, received);
}

export function parseGitHubWebhook(params: {
  headers: Record<string, string | string[] | undefined>;
  rawBody: string;
  secret?: string;
}): ParsedGitHubWebhook {
  const payload = JSON.parse(params.rawBody) as Record<string, unknown>;
  if (params.secret) {
    const signature = getHeader(params.headers, "x-hub-signature-256");
    const ok = verifyWebhookSignature({
      secret: params.secret,
      signature,
      rawBody: params.rawBody,
    });
    if (!ok) {
      throw new Error("Invalid GitHub webhook signature");
    }
  }

  return {
    normalized: normalizeGitHubEvent({ headers: params.headers, payload }),
    payload,
  };
}
