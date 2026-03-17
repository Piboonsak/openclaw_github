import { describe, expect, it, vi, beforeEach } from "vitest";
import { parseExecApprovalPostback, EXEC_APPROVAL_POSTBACK_PREFIX } from "./exec-approvals.js";
import type { LineExecApprovalHandler } from "./exec-approvals.js";

// --------------------------------------------------------------------------
// Unit tests for parseExecApprovalPostback (pure function, no mocks needed)
// --------------------------------------------------------------------------

describe("parseExecApprovalPostback", () => {
  it("parses allow-once postback correctly", () => {
    const result = parseExecApprovalPostback("exec_approval=allow-once&id=abc-123");
    expect(result).toEqual({ decision: "allow-once", approvalId: "abc-123" });
  });

  it("parses allow-always postback correctly", () => {
    const result = parseExecApprovalPostback("exec_approval=allow-always&id=abc-123");
    expect(result).toEqual({ decision: "allow-always", approvalId: "abc-123" });
  });

  it("parses deny postback correctly", () => {
    const result = parseExecApprovalPostback("exec_approval=deny&id=uuid-456");
    expect(result).toEqual({ decision: "deny", approvalId: "uuid-456" });
  });

  it("returns null for non-approval postback data", () => {
    expect(parseExecApprovalPostback("richmenuswitch")).toBeNull();
    expect(parseExecApprovalPostback("action=some_other_thing")).toBeNull();
    expect(parseExecApprovalPostback("")).toBeNull();
  });

  it("returns null when missing id parameter", () => {
    expect(parseExecApprovalPostback("exec_approval=allow-once")).toBeNull();
  });

  it("returns null for unknown decision values", () => {
    expect(parseExecApprovalPostback("exec_approval=unknown_action&id=abc")).toBeNull();
    expect(parseExecApprovalPostback("exec_approval=approve&id=abc")).toBeNull();
  });

  it("handles UUID-format approval IDs", () => {
    const uuid = "550e8400-e29b-41d4-a716-446655440000";
    const result = parseExecApprovalPostback(`exec_approval=allow-once&id=${uuid}`);
    expect(result).toEqual({ decision: "allow-once", approvalId: uuid });
  });

  it("EXEC_APPROVAL_POSTBACK_PREFIX matches the expected prefix", () => {
    expect(EXEC_APPROVAL_POSTBACK_PREFIX).toBe("exec_approval=");
  });
});

// --------------------------------------------------------------------------
// Integration-level tests for handlePostbackEvent exec approval interception
// --------------------------------------------------------------------------

// Mock all heavy dependencies to isolate the postback handler logic.
vi.mock("../globals.js", () => ({
  danger: (text: string) => text,
  logVerbose: () => {},
}));
vi.mock("../pairing/pairing-labels.js", () => ({
  resolvePairingIdLabel: () => "lineUserId",
}));
vi.mock("../pairing/pairing-messages.js", () => ({
  buildPairingReply: () => "pairing-reply",
}));
vi.mock("./download.js", () => ({
  downloadLineMedia: async () => {
    throw new Error("downloadLineMedia should not be called");
  },
}));

const pushMessageLineMock = vi.fn(async (..._args: unknown[]) => {});
const replyMessageLineMock = vi.fn(async (..._args: unknown[]) => {});

vi.mock("./send.js", () => ({
  pushMessageLine: (...args: unknown[]) => pushMessageLineMock(...args),
  replyMessageLine: (...args: unknown[]) => replyMessageLineMock(...args),
}));

// Mock buildLinePostbackContext so it never fires for approval postbacks
const buildLinePostbackContextMock = vi.fn(async () => null);

vi.mock("./bot-message-context.js", () => ({
  buildLineMessageContext: vi.fn(async () => null),
  buildLinePostbackContext: buildLinePostbackContextMock,
  getLineSourceInfo: (source: {
    type?: string;
    userId?: string;
    groupId?: string;
    roomId?: string;
  }) => ({
    userId: source.userId,
    groupId: source.type === "group" ? source.groupId : undefined,
    roomId: source.type === "room" ? source.roomId : undefined,
    isGroup: source.type === "group" || source.type === "room",
  }),
}));

vi.mock("../pairing/pairing-store.js", () => ({
  readChannelAllowFromStore: vi.fn(async () => []),
  upsertChannelPairingRequest: vi.fn(async () => ({ code: "CODE", created: true })),
}));

describe("handlePostbackEvent exec approval interception", () => {
  let handleLineWebhookEvents: typeof import("./bot-handlers.js").handleLineWebhookEvents;

  const baseAccount = {
    accountId: "default",
    enabled: true,
    channelAccessToken: "token",
    channelSecret: "secret",
    tokenSource: "config" as const,
    config: {},
  };

  const createRuntime = () => ({
    log: vi.fn(),
    error: vi.fn(),
    exit: vi.fn() as unknown as (code: number) => never,
  });

  beforeEach(async () => {
    vi.clearAllMocks();
    // Dynamic import after mocks are set up
    ({ handleLineWebhookEvents } = await import("./bot-handlers.js"));
  });

  function makePostbackEvent(data: string) {
    return {
      type: "postback" as const,
      postback: { data },
      replyToken: "reply-token",
      timestamp: Date.now(),
      source: { type: "user" as const, userId: "user-1" },
      mode: "active" as const,
      webhookEventId: "evt-pb-1",
      deliveryContext: { isRedelivery: false },
    };
  }

  it("intercepts exec approval postback and resolves via handler", async () => {
    const processMessage = vi.fn();
    const resolveApproval = vi.fn(async () => true);
    const handler = { resolveApproval, start: vi.fn(), stop: vi.fn() };

    await handleLineWebhookEvents([makePostbackEvent("exec_approval=allow-once&id=abc-123")], {
      cfg: {},
      account: baseAccount,
      runtime: createRuntime(),
      mediaMaxBytes: 1,
      processMessage,
      execApprovalHandler: handler as unknown as LineExecApprovalHandler,
    });

    expect(resolveApproval).toHaveBeenCalledWith("abc-123", "allow-once");
    // processMessage must NOT be called — this is the core fix for issue #55
    expect(processMessage).not.toHaveBeenCalled();
    // buildLinePostbackContext must NOT be called either
    expect(buildLinePostbackContextMock).not.toHaveBeenCalled();
  });

  it("sends expiry notification when resolve returns false", async () => {
    const processMessage = vi.fn();
    const resolveApproval = vi.fn(async () => false); // expired
    const handler = { resolveApproval, start: vi.fn(), stop: vi.fn() };

    await handleLineWebhookEvents([makePostbackEvent("exec_approval=deny&id=expired-1")], {
      cfg: {},
      account: baseAccount,
      runtime: createRuntime(),
      mediaMaxBytes: 1,
      processMessage,
      execApprovalHandler: handler as unknown as LineExecApprovalHandler,
    });

    expect(resolveApproval).toHaveBeenCalledWith("expired-1", "deny");
    expect(processMessage).not.toHaveBeenCalled();
    // Should attempt to push expiry notification
    expect(pushMessageLineMock).toHaveBeenCalledWith(
      "line:user-1",
      "⏱️ Approval expired or already resolved.",
      { accountId: "default" },
    );
  });

  it("falls through to normal postback processing for non-approval data", async () => {
    const processMessage = vi.fn();
    const resolveApproval = vi.fn();
    const handler = { resolveApproval, start: vi.fn(), stop: vi.fn() };

    await handleLineWebhookEvents([makePostbackEvent("richmenuswitch")], {
      cfg: {},
      account: baseAccount,
      runtime: createRuntime(),
      mediaMaxBytes: 1,
      processMessage,
      execApprovalHandler: handler as unknown as LineExecApprovalHandler,
    });

    // Approval handler should NOT be called for non-approval postbacks
    expect(resolveApproval).not.toHaveBeenCalled();
  });

  it("falls through when no execApprovalHandler is provided", async () => {
    const processMessage = vi.fn();

    await handleLineWebhookEvents([makePostbackEvent("exec_approval=allow-once&id=abc-123")], {
      cfg: {},
      account: baseAccount,
      runtime: createRuntime(),
      mediaMaxBytes: 1,
      processMessage,
      // No execApprovalHandler
    });

    // Without a handler, the approval postback falls through to normal processing
    expect(buildLinePostbackContextMock).toHaveBeenCalled();
  });
});
