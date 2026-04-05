import { describe, expect, it } from "vitest";
import {
  resolveSafeBinProfiles,
  SAFE_BIN_PROFILES,
  validateSafeBinArgv,
} from "../../src/infra/exec-safe-bin-policy.js";

// Regression suite: NongKung agent tool execution capability.
// Verifies that safe-bin profiles allow NongKung's expected tools
// (web search via curl, file reads via cat, GitHub diagnostics via gh)
// and deny genuinely dangerous flags.

describe("NongKung regression — tool execution (safe-bin policy)", () => {
  describe("web search via curl", () => {
    const curlProfile = SAFE_BIN_PROFILES.curl;

    it("allows a basic HTTP GET for web search (no query string)", () => {
      // Note: URLs containing glob-like characters (? * []) are rejected by the safe-bin
      // policy to prevent shell glob expansion attacks. Use separate curl flags for params.
      expect(validateSafeBinArgv(["https://api.example.com/search"], curlProfile)).toBe(true);
    });

    it("rejects URLs containing glob characters (e.g. query string with ?)", () => {
      // The safe-bin policy treats ? as a glob token to prevent glob-expansion attacks.
      expect(validateSafeBinArgv(["https://api.example.com/search?q=gold"], curlProfile)).toBe(
        false,
      );
    });

    it("allows curl with silent and fail flags (standard probe pattern)", () => {
      expect(
        validateSafeBinArgv(["-s", "-f", "-S", "https://api.example.com/health"], curlProfile),
      ).toBe(true);
    });

    it("allows curl with custom header (e.g. API key for search)", () => {
      expect(
        validateSafeBinArgv(
          ["-H", "Authorization: Bearer token", "https://api.example.com/search"],
          curlProfile,
        ),
      ).toBe(true);
    });

    it("allows curl with max-time flag to prevent hangs", () => {
      expect(validateSafeBinArgv(["-m", "10", "https://api.example.com/search"], curlProfile)).toBe(
        true,
      );
    });

    it("denies curl --output (prevents writing files to disk)", () => {
      expect(
        validateSafeBinArgv(["--output", "/tmp/out.txt", "https://api.example.com/"], curlProfile),
      ).toBe(false);
    });

    it("denies curl --config (prevents loading arbitrary config)", () => {
      expect(
        validateSafeBinArgv(["--config", "/etc/curlrc", "https://api.example.com/"], curlProfile),
      ).toBe(false);
    });
  });

  describe("file read via cat", () => {
    const catProfile = SAFE_BIN_PROFILES.cat;

    it("allows reading a single file", () => {
      expect(validateSafeBinArgv(["/data/.openclaw/workspace/memory.md"], catProfile)).toBe(true);
    });

    it("allows reading multiple files", () => {
      expect(
        validateSafeBinArgv(
          ["/data/.openclaw/workspace/memory.md", "/data/.openclaw/openclaw.json"],
          catProfile,
        ),
      ).toBe(true);
    });

    it("allows reading relative paths", () => {
      expect(validateSafeBinArgv(["memory/2026-04-01.md"], catProfile)).toBe(true);
    });
  });

  describe("GitHub diagnostics via gh (NongKung use case)", () => {
    it("allows NongKung gh api diagnostic command", () => {
      const ghProfile = resolveSafeBinProfiles({
        gh: {
          minPositional: 0,
          maxPositional: 8,
          allowedValueFlags: ["--repo", "-R", "--field", "-F", "--jq", "--json", "--paginate"],
        },
      });

      expect(
        validateSafeBinArgv(
          [
            "api",
            "repos/Piboonsak/Openclaw/actions/runs",
            "-F",
            "per_page=3",
            "--json",
            "name,status",
          ],
          ghProfile.gh,
        ),
      ).toBe(true);
    });

    it("allows standard gh profile for listing issues", () => {
      const ghProfile = SAFE_BIN_PROFILES.gh;
      expect(
        validateSafeBinArgv(
          ["issue", "list", "--repo", "Piboonsak/Openclaw", "--state", "open"],
          ghProfile,
        ),
      ).toBe(true);
    });
  });

  describe("grep for log/file analysis", () => {
    const grepProfile = SAFE_BIN_PROFILES.grep;

    it("allows grep pattern search in files", () => {
      expect(validateSafeBinArgv(["-r", "-n", "ERROR", "/var/log/"], grepProfile)).toBe(true);
    });

    it("denies grep --file (no reading pattern from arbitrary file)", () => {
      expect(validateSafeBinArgv(["--file", "/tmp/patterns.txt", "/var/log/"], grepProfile)).toBe(
        false,
      );
    });
  });
});
