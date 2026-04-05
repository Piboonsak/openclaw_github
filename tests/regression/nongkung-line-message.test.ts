import { describe, expect, it } from "vitest";
import {
  hasControlCommand,
  hasInlineCommandTokens,
  isControlCommandMessage,
  shouldComputeCommandAuthorized,
} from "../../src/auto-reply/command-detection.js";
import { getLineSourceInfo } from "../../src/line/bot-message-context.js";

// Regression suite: NongKung agent responds to basic LINE messages.
// Verifies that the bot correctly identifies control commands (/status, /help, etc.)
// and routes regular chat messages vs. bot-control messages as expected.

describe("NongKung regression — agent responds to basic LINE message", () => {
  describe("LINE source info extraction", () => {
    it("extracts user source correctly", () => {
      const src = getLineSourceInfo({ type: "user", userId: "U123" });
      expect(src.userId).toBe("U123");
      expect(src.isGroup).toBe(false);
      expect(src.groupId).toBeUndefined();
    });

    it("extracts group source correctly", () => {
      const src = getLineSourceInfo({ type: "group", userId: "U123", groupId: "C456" });
      expect(src.userId).toBe("U123");
      expect(src.groupId).toBe("C456");
      expect(src.isGroup).toBe(true);
    });

    it("extracts room source correctly", () => {
      const src = getLineSourceInfo({ type: "room", userId: "U123", roomId: "R789" });
      expect(src.userId).toBe("U123");
      expect(src.roomId).toBe("R789");
      expect(src.isGroup).toBe(true);
    });
  });

  describe("control command detection", () => {
    it("detects /status command from a LINE message", () => {
      expect(hasControlCommand("/status")).toBe(true);
      expect(hasControlCommand("/help")).toBe(true);
      expect(hasControlCommand("/stop")).toBe(true);
    });

    it("does not treat plain chat messages as control commands", () => {
      expect(hasControlCommand("สวัสดีครับ")).toBe(false);
      expect(hasControlCommand("hello, how are you?")).toBe(false);
      expect(hasControlCommand("what time is it")).toBe(false);
    });

    it("does not detect empty or whitespace-only text as a command", () => {
      expect(hasControlCommand("")).toBe(false);
      expect(hasControlCommand("   ")).toBe(false);
      expect(hasControlCommand(undefined)).toBe(false);
    });

    it("detects control command with arguments (e.g. /model <name>)", () => {
      expect(hasControlCommand("/model gpt-5")).toBe(true);
    });
  });

  describe("inline command token detection", () => {
    it("detects inline /status token in a regular message", () => {
      expect(hasInlineCommandTokens("hey /status")).toBe(true);
      expect(hasInlineCommandTokens("/help")).toBe(true);
    });

    it("does not detect inline commands in plain text", () => {
      expect(hasInlineCommandTokens("hello world")).toBe(false);
      expect(hasInlineCommandTokens("")).toBe(false);
    });
  });

  describe("command authorized routing", () => {
    it("routes control commands to command handler", () => {
      expect(shouldComputeCommandAuthorized("/status")).toBe(true);
      expect(shouldComputeCommandAuthorized("/help")).toBe(true);
    });

    it("routes inline directives to command evaluation", () => {
      expect(shouldComputeCommandAuthorized("urgent /status")).toBe(true);
    });

    it("does not route plain chat messages to command handler", () => {
      expect(shouldComputeCommandAuthorized("สวัสดี")).toBe(false);
      expect(shouldComputeCommandAuthorized("hello")).toBe(false);
    });

    it("correctly identifies full control command messages", () => {
      expect(isControlCommandMessage("/status")).toBe(true);
      expect(isControlCommandMessage("/compact")).toBe(true);
    });

    it("does not treat regular messages as control messages", () => {
      expect(isControlCommandMessage("good morning")).toBe(false);
      expect(isControlCommandMessage("ค้นหาราคาทอง")).toBe(false);
    });
  });
});
