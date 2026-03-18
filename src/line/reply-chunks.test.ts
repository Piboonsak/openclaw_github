import { describe, expect, it, vi } from "vitest";
import { sendLineReplyChunks } from "./reply-chunks.js";

const quickReplyItems = (quickReplies: string[]) =>
  quickReplies.map((label) => ({
    type: "action" as const,
    action: {
      type: "message" as const,
      label,
      text: label,
    },
  }));

function createReplyChunksHarness() {
  const replyMessageLine = vi.fn(async () => ({}));
  const pushMessagesLine = vi.fn(async () => ({}));
  const pushMessageLine = vi.fn(async () => ({}));
  const pushTextMessageWithQuickReplies = vi.fn(async () => ({}));
  const createTextMessageWithQuickReplies = vi.fn((text: string, quickReplies: string[]) => ({
    type: "text" as const,
    text,
    quickReply: { items: quickReplyItems(quickReplies) },
  }));

  return {
    replyMessageLine,
    pushMessagesLine,
    pushMessageLine,
    pushTextMessageWithQuickReplies,
    createTextMessageWithQuickReplies,
  };
}

describe("sendLineReplyChunks", () => {
  it("uses reply token for all chunks when possible", async () => {
    const {
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
    } = createReplyChunksHarness();

    const result = await sendLineReplyChunks({
      to: "line:group:1",
      chunks: ["one", "two", "three"],
      quickReplies: ["A", "B"],
      replyToken: "token",
      replyTokenUsed: false,
      accountId: "default",
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
    });

    expect(result.replyTokenUsed).toBe(true);
    expect(replyMessageLine).toHaveBeenCalledTimes(1);
    expect(createTextMessageWithQuickReplies).toHaveBeenCalledWith("three", ["A", "B"]);
    expect(replyMessageLine).toHaveBeenCalledWith(
      "token",
      [
        { type: "text", text: "one" },
        { type: "text", text: "two" },
        {
          type: "text",
          text: "three",
          quickReply: { items: quickReplyItems(["A", "B"]) },
        },
      ],
      { accountId: "default" },
    );
    expect(pushMessagesLine).not.toHaveBeenCalled();
    expect(pushMessageLine).not.toHaveBeenCalled();
    expect(pushTextMessageWithQuickReplies).not.toHaveBeenCalled();
  });

  it("attaches quick replies to a single reply chunk", async () => {
    const { replyMessageLine, pushMessagesLine, pushMessageLine, pushTextMessageWithQuickReplies } =
      createReplyChunksHarness();
    const createTextMessageWithQuickReplies = vi.fn((text: string, _quickReplies: string[]) => ({
      type: "text" as const,
      text,
      quickReply: { items: [] },
    }));

    const result = await sendLineReplyChunks({
      to: "line:user:1",
      chunks: ["only"],
      quickReplies: ["A"],
      replyToken: "token",
      replyTokenUsed: false,
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
    });

    expect(result.replyTokenUsed).toBe(true);
    expect(createTextMessageWithQuickReplies).toHaveBeenCalledWith("only", ["A"]);
    expect(replyMessageLine).toHaveBeenCalledTimes(1);
    expect(pushMessagesLine).not.toHaveBeenCalled();
    expect(pushMessageLine).not.toHaveBeenCalled();
    expect(pushTextMessageWithQuickReplies).not.toHaveBeenCalled();
  });

  it("replies with up to five chunks before pushing the rest as a batch", async () => {
    const {
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
    } = createReplyChunksHarness();

    const chunks = ["1", "2", "3", "4", "5", "6", "7"];
    const result = await sendLineReplyChunks({
      to: "line:group:1",
      chunks,
      quickReplies: ["A"],
      replyToken: "token",
      replyTokenUsed: false,
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
    });

    expect(result.replyTokenUsed).toBe(true);
    expect(replyMessageLine).toHaveBeenCalledTimes(1);
    expect(replyMessageLine).toHaveBeenCalledWith(
      "token",
      [
        { type: "text", text: "1" },
        { type: "text", text: "2" },
        { type: "text", text: "3" },
        { type: "text", text: "4" },
        { type: "text", text: "5" },
      ],
      { accountId: undefined },
    );
    expect(pushMessagesLine).toHaveBeenCalledTimes(1);
    expect(pushMessagesLine).toHaveBeenCalledWith(
      "line:group:1",
      [
        { type: "text", text: "6" },
        { type: "text", text: "7", quickReply: { items: quickReplyItems(["A"]) } },
      ],
      {
        accountId: undefined,
      },
    );
    expect(createTextMessageWithQuickReplies).toHaveBeenCalledWith("7", ["A"]);
    expect(pushMessageLine).not.toHaveBeenCalled();
    expect(pushTextMessageWithQuickReplies).not.toHaveBeenCalled();
  });

  it("falls back to batched push flow when replying fails", async () => {
    const {
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
    } = createReplyChunksHarness();
    const onReplyError = vi.fn();
    replyMessageLine.mockRejectedValueOnce(new Error("reply failed"));

    const result = await sendLineReplyChunks({
      to: "line:group:1",
      chunks: ["1", "2", "3"],
      quickReplies: ["A"],
      replyToken: "token",
      replyTokenUsed: false,
      accountId: "default",
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
      onReplyError,
    });

    expect(result.replyTokenUsed).toBe(true);
    expect(onReplyError).toHaveBeenCalledWith(expect.any(Error));
    expect(pushMessagesLine).toHaveBeenCalledWith(
      "line:group:1",
      [
        { type: "text", text: "1" },
        { type: "text", text: "2" },
        { type: "text", text: "3", quickReply: { items: quickReplyItems(["A"]) } },
      ],
      {
        accountId: "default",
      },
    );
    expect(createTextMessageWithQuickReplies).toHaveBeenCalledWith("3", ["A"]);
    expect(pushMessageLine).not.toHaveBeenCalled();
    expect(pushTextMessageWithQuickReplies).not.toHaveBeenCalled();
  });

  it("batches long push-only replies into groups of five messages", async () => {
    const {
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
    } = createReplyChunksHarness();

    await sendLineReplyChunks({
      to: "line:user:1",
      chunks: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
      quickReplies: ["A"],
      replyTokenUsed: true,
      accountId: "default",
      replyMessageLine,
      pushMessagesLine,
      pushMessageLine,
      pushTextMessageWithQuickReplies,
      createTextMessageWithQuickReplies,
    });

    expect(replyMessageLine).not.toHaveBeenCalled();
    expect(pushMessagesLine).toHaveBeenCalledTimes(3);
    expect(pushMessagesLine).toHaveBeenNthCalledWith(
      1,
      "line:user:1",
      [
        { type: "text", text: "1" },
        { type: "text", text: "2" },
        { type: "text", text: "3" },
        { type: "text", text: "4" },
        { type: "text", text: "5" },
      ],
      {
        accountId: "default",
      },
    );
    expect(pushMessagesLine).toHaveBeenNthCalledWith(
      2,
      "line:user:1",
      [
        { type: "text", text: "6" },
        { type: "text", text: "7" },
      ],
      {
        accountId: "default",
      },
    );
    expect(pushMessagesLine).toHaveBeenNthCalledWith(
      3,
      "line:user:1",
      [
        { type: "text", text: "8" },
        { type: "text", text: "9" },
        { type: "text", text: "10" },
        { type: "text", text: "11" },
        { type: "text", text: "12", quickReply: { items: quickReplyItems(["A"]) } },
      ],
      {
        accountId: "default",
      },
    );
    expect(createTextMessageWithQuickReplies).toHaveBeenCalledWith("12", ["A"]);
    expect(pushMessageLine).not.toHaveBeenCalled();
    expect(pushTextMessageWithQuickReplies).not.toHaveBeenCalled();
  });
});
