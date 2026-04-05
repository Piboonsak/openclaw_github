import { describe, expect, it } from "vitest";
import {
  DEFAULT_HEARTBEAT_ACK_MAX_CHARS,
  DEFAULT_HEARTBEAT_EVERY,
  HEARTBEAT_PROMPT,
  isHeartbeatContentEffectivelyEmpty,
  resolveHeartbeatPrompt,
  stripHeartbeatToken,
} from "../../src/auto-reply/heartbeat.js";
import { HEARTBEAT_TOKEN } from "../../src/auto-reply/tokens.js";

// Regression suite: NongKung agent heartbeat command capability.
// Verifies that the heartbeat system responds correctly to HEARTBEAT.md content
// and produces canonical HEARTBEAT_OK tokens.

describe("NongKung regression — heartbeat command", () => {
  it("HEARTBEAT_PROMPT is defined and references HEARTBEAT.md", () => {
    expect(HEARTBEAT_PROMPT).toBeTruthy();
    expect(HEARTBEAT_PROMPT).toContain("HEARTBEAT.md");
  });

  it("default heartbeat interval is 30m", () => {
    expect(DEFAULT_HEARTBEAT_EVERY).toBe("30m");
  });

  it("default ack max chars is 300", () => {
    expect(DEFAULT_HEARTBEAT_ACK_MAX_CHARS).toBe(300);
  });

  it("resolveHeartbeatPrompt returns default when no custom prompt configured", () => {
    expect(resolveHeartbeatPrompt(undefined)).toBe(HEARTBEAT_PROMPT);
    expect(resolveHeartbeatPrompt("")).toBe(HEARTBEAT_PROMPT);
    expect(resolveHeartbeatPrompt("  ")).toBe(HEARTBEAT_PROMPT);
  });

  it("resolveHeartbeatPrompt returns custom prompt when provided", () => {
    const custom = "Custom heartbeat: check open tickets.";
    expect(resolveHeartbeatPrompt(custom)).toBe(custom);
  });

  it("strips HEARTBEAT_OK token from a heartbeat reply", () => {
    const result = stripHeartbeatToken(HEARTBEAT_TOKEN, { mode: "heartbeat" });
    expect(result.shouldSkip).toBe(true);
    expect(result.didStrip).toBe(true);
    expect(result.text).toBe("");
  });

  it("keeps long heartbeat replies that contain the token", () => {
    const long = "A".repeat(DEFAULT_HEARTBEAT_ACK_MAX_CHARS + 1);
    const result = stripHeartbeatToken(`${long} ${HEARTBEAT_TOKEN}`, { mode: "heartbeat" });
    expect(result.shouldSkip).toBe(false);
    expect(result.didStrip).toBe(true);
    expect(result.text).toBe(long);
  });

  it("skips empty heartbeat replies", () => {
    expect(stripHeartbeatToken("", { mode: "heartbeat" }).shouldSkip).toBe(true);
    expect(stripHeartbeatToken(undefined, { mode: "heartbeat" }).shouldSkip).toBe(true);
  });

  it("isHeartbeatContentEffectivelyEmpty returns false for undefined (missing file)", () => {
    expect(isHeartbeatContentEffectivelyEmpty(undefined)).toBe(false);
    expect(isHeartbeatContentEffectivelyEmpty(null)).toBe(false);
  });

  it("isHeartbeatContentEffectivelyEmpty returns true for comment-only content", () => {
    expect(isHeartbeatContentEffectivelyEmpty("# no tasks")).toBe(true);
    expect(isHeartbeatContentEffectivelyEmpty("# header\n# another")).toBe(true);
    expect(isHeartbeatContentEffectivelyEmpty("   \n  \n")).toBe(true);
  });

  it("isHeartbeatContentEffectivelyEmpty returns false when actionable tasks exist", () => {
    expect(isHeartbeatContentEffectivelyEmpty("- Check status")).toBe(false);
    expect(isHeartbeatContentEffectivelyEmpty("Review open PRs")).toBe(false);
  });
});
