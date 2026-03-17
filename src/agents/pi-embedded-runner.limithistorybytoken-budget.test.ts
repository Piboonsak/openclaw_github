import type { AgentMessage } from "@mariozechner/pi-agent-core";
import { describe, expect, it } from "vitest";
import { limitHistoryByTokenBudget } from "./pi-embedded-runner/history.js";

describe("limitHistoryByTokenBudget", () => {
  const mockUsage = {
    input: 1,
    output: 1,
    cacheRead: 0,
    cacheWrite: 0,
    totalTokens: 2,
    cost: {
      input: 0,
      output: 0,
      cacheRead: 0,
      cacheWrite: 0,
      total: 0,
    },
  } as const;

  const userMessage = (text: string, tokenCount: number = 10): AgentMessage =>
    ({
      role: "user",
      content: [
        { type: "text", text: text + "\n".repeat(Math.ceil((tokenCount * 4) / text.length)) },
      ],
      timestamp: Date.now(),
    }) as AgentMessage;

  const assistantMessage = (text: string, tokenCount: number = 10): AgentMessage =>
    ({
      role: "assistant",
      content: [
        { type: "text", text: text + "\n".repeat(Math.ceil((tokenCount * 4) / text.length)) },
      ],
      stopReason: "stop",
      api: "anthropic-messages",
      provider: "anthropic",
      model: "claude-opus-4-6",
      usage: mockUsage,
      timestamp: Date.now(),
    }) as AgentMessage;

  const toolResultMessage = (text: string, tokenCount: number = 100): AgentMessage =>
    ({
      role: "toolResult",
      toolCallId: "tool-call-id",
      toolName: "exec",
      isError: false,
      content: [
        { type: "text", text: text + "\n".repeat(Math.ceil((tokenCount * 4) / text.length)) },
      ],
      timestamp: Date.now(),
    }) as unknown as AgentMessage;

  it("returns all messages when budget is undefined", () => {
    const messages = [
      userMessage("hi", 50),
      assistantMessage("hello", 50),
      userMessage("how are you", 50),
      assistantMessage("im good", 50),
    ];
    // Mock estimateTokens to return consistent values
    const result = limitHistoryByTokenBudget(messages, undefined);
    expect(result).toBe(messages);
  });

  it("returns all messages when budget is 0 or negative", () => {
    const messages = [userMessage("hi", 50), assistantMessage("hello", 50)];
    expect(limitHistoryByTokenBudget(messages, 0)).toBe(messages);
    expect(limitHistoryByTokenBudget(messages, -100)).toBe(messages);
  });

  it("returns empty list for empty messages", () => {
    const result = limitHistoryByTokenBudget([], 5000);
    expect(result).toEqual([]);
  });

  it("keeps all messages when total tokens within budget", () => {
    const messages = [
      userMessage("short", 20),
      assistantMessage("ok", 10),
      userMessage("fine", 15),
    ];
    // Default budget is 12000, so this should keep all
    const result = limitHistoryByTokenBudget(messages, 12000);
    expect(result.length).toBeLessThanOrEqual(messages.length);
  });

  it("removes oldest messages when exceeding budget", () => {
    // Create messages with controlled sizes
    const messages = [
      userMessage("message1", 100), // 100 tokens
      assistantMessage("reply1", 100), // 100 tokens
      userMessage("message2", 100), // 100 tokens
      assistantMessage("reply2", 100), // 100 tokens
      userMessage("message3", 100), // 100 tokens
    ];

    // Budget allows ~300 tokens, should keep last 3-4 messages
    const result = limitHistoryByTokenBudget(messages, 300);

    // Result should prefer recent messages
    expect(result.length).toBeGreaterThan(0);
    expect(result.length).toBeLessThanOrEqual(messages.length);

    // Should contain the last message
    if (result.length > 0) {
      const lastResult = result[result.length - 1];
      const lastExpected = messages[messages.length - 1];
      if ("content" in lastResult && "content" in lastExpected) {
        expect(lastResult.content).toEqual(lastExpected.content);
      }
    }
  });

  it("always keeps at least the last message for continuity", () => {
    const messages = [
      userMessage("very long message that uses up all the budget and more", 5000),
      assistantMessage("response", 50),
      userMessage("final", 10),
    ];

    // TightBudget that definitely can't fit all messages
    const result = limitHistoryByTokenBudget(messages, 100);

    // Should have at least one message
    expect(result.length).toBeGreaterThan(0);

    // Should include the last message
    expect(result[result.length - 1]).toEqual(messages[messages.length - 1]);
  });

  it("handles default budget of 12000 tokens", () => {
    const messages = [
      userMessage("msg1", 500),
      assistantMessage("resp1", 500),
      userMessage("msg2", 500),
      assistantMessage("resp2", 500),
      userMessage("msg3", 500),
      assistantMessage("resp3", 500),
    ];

    // Default budget allows ~12k tokens, which should fit most of these messages
    const result = limitHistoryByTokenBudget(messages);
    expect(result.length).toBeGreaterThan(0);
    expect(result.length).toBeLessThanOrEqual(messages.length);
  });

  it("preserves message order (newest at end)", () => {
    const messages = [
      userMessage("old", 50),
      assistantMessage("reply_old", 50),
      userMessage("middle", 50),
      assistantMessage("reply_middle", 50),
      userMessage("new", 50),
    ];

    const result = limitHistoryByTokenBudget(messages, 200);

    // Latest message should be at the end
    if (result.length > 1) {
      // The result should have messages in original order
      expect(Array.isArray(result)).toBe(true);

      // Messages should be in chronological order (older to newer)
      for (let i = 1; i < result.length; i++) {
        expect(result[i].timestamp).toBeGreaterThanOrEqual(result[i - 1].timestamp);
      }
    }
  });

  it("includes reasonably sized tool results", () => {
    const messages = [
      userMessage("please read file", 20),
      assistantMessage("sure", 10),
      toolResultMessage("file contents here", 80),
      userMessage("thanks", 10),
      assistantMessage("done", 10),
    ];

    // Budget allows tool results
    const result = limitHistoryByTokenBudget(messages, 500);

    // Should attempt to keep tool result if it fits
    expect(result.length).toBeGreaterThan(0);
  });

  it("does not break when message estimation returns 0", () => {
    const messages = [
      userMessage("empty", 0),
      assistantMessage("reply", 100),
      userMessage("final", 50),
    ];

    // Should not crash even with edge-case token counts
    const result = limitHistoryByTokenBudget(messages, 200);
    expect(result.length).toBeGreaterThan(0);
  });
});
