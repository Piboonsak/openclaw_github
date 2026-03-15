import { createHmac } from "node:crypto";
import { describe, expect, it } from "vitest";
import { parseGitHubWebhook, verifyWebhookSignature } from "./github-webhook.js";

function sign(secret: string, body: string): string {
  return `sha256=${createHmac("sha256", secret).update(body).digest("hex")}`;
}

describe("github webhook parser", () => {
  it("verifies signature", () => {
    const body = JSON.stringify({ action: "opened" });
    const secret = "top-secret";
    const signature = sign(secret, body);

    const ok = verifyWebhookSignature({ secret, rawBody: body, signature });
    expect(ok).toBe(true);
  });

  it("parses normalized webhook payload", () => {
    const body = JSON.stringify({ action: "opened", repository: { full_name: "Piboonsak/openclaw_github" } });
    const parsed = parseGitHubWebhook({
      rawBody: body,
      headers: {
        "x-github-delivery": "delivery-1",
        "x-github-event": "pull_request",
      },
    });

    expect(parsed.normalized.deliveryId).toBe("delivery-1");
    expect(parsed.normalized.eventType).toBe("pull_request");
    expect(parsed.normalized.action).toBe("opened");
  });
});