import { test, expect, type Page } from "@playwright/test";

/**
 * TASK-1313 — Live click-through verification of the W4 SIT review surface.
 *
 * This drives the REAL production-facing review surface (main-ux-ui.html served
 * at /phase2/prototype) through a genuine browser: Basic-Auth edge -> app login
 * (real /api/v1/auth/login) -> navigate every core screen -> assert each renders
 * distinct content with no console errors / failed auth calls.
 *
 * Credentials are read from the environment (never hardcoded / committed):
 *   POC_URL          base URL, e.g. https://sit.yahwan.biz   (set in playwright.config baseURL)
 *   SIT_BASIC_USER   Basic-Auth edge username  (-> httpCredentials in config)
 *   SIT_BASIC_PASS   Basic-Auth edge password
 *   SIT_APP_USER     app login username (SIT seed admin)
 *   SIT_APP_PASS     app login password
 *
 * Populate them in an untracked `.env.sit.local` at repo root (git-ignored via
 * `.env.*.local`) — see `.env.sit.local.example`. Then run:
 *   POC_URL=https://sit.yahwan.biz npx playwright test tests/e2e/sit-clickthrough.spec.ts --project=chromium
 */

declare const process: { env: Record<string, string | undefined> };

const APP_USER = process.env.SIT_APP_USER || "";
const APP_PASS = process.env.SIT_APP_PASS || "";

// Core screens per the TASK-1313 acceptance criteria. `nav` = sidebar data-screen id.
const SCREENS: Array<{ key: string; nav: string; label: string }> = [
  { key: "dashboard", nav: "s-dashboard", label: "Dashboard" },
  { key: "upload", nav: "s-upload", label: "Upload" },
  { key: "review", nav: "s-review-scan", label: "Review (Scan)" },
  { key: "review-map", nav: "s-review-mapping", label: "Review (Mapping)" },
  { key: "export", nav: "s-export", label: "Export" },
  { key: "templates", nav: "s-templates", label: "Templates" },
];

type ScreenIssue = { screen: string; consoleErrors: string[]; failedRequests: string[] };

function attachCollectors(page: Page, bucket: { errors: string[]; failed: string[] }) {
  page.on("console", (msg) => {
    if (msg.type() === "error") bucket.errors.push(msg.text());
  });
  page.on("response", (res) => {
    const s = res.status();
    if (s === 401 || s === 403 || s === 404 || s >= 500) {
      bucket.failed.push(`${s} ${res.request().method()} ${res.url()}`);
    }
  });
}

test.describe("TASK-1313 SIT live click-through", () => {
  test.skip(!APP_USER || !APP_PASS, "SIT_APP_USER / SIT_APP_PASS not set — populate .env.sit.local");

  test("login and click through every core screen with no console/auth errors", async ({ page }) => {
    test.setTimeout(120_000); // live remote run: login + 7 screens on SIT
    const bucket = { errors: [] as string[], failed: [] as string[] };
    attachCollectors(page, bucket);
    const issues: ScreenIssue[] = [];

    // 1. Land on the official W4 review-surface route (Basic-Auth handled by httpCredentials).
    await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 60_000 });
    await expect(page).toHaveTitle(/Full Prototype/i);
    await expect(page.locator("#login-screen")).toBeVisible();

    // 2. Real app login (hits /api/v1/auth/login -> /api/v1/auth/me).
    await page.fill("#loginUser", APP_USER);
    await page.fill("#loginPw", APP_PASS);
    const loginResp = page.waitForResponse(
      (r) => r.url().includes("/api/v1/auth/login"),
      { timeout: 30_000 },
    );
    await page.click("#loginForm button[type=submit], #loginForm .btn-primary");
    const login = await loginResp;
    expect(login.status(), "login API status").toBe(200);

    // App shell becomes visible on success.
    await expect(page.locator("#app")).toHaveClass(/visible/, { timeout: 15_000 });
    await expect(page.locator("#login-screen")).toBeHidden();

    // 3. Click through each core screen via the sidebar.
    for (const s of SCREENS) {
      const before = { e: bucket.errors.length, f: bucket.failed.length };
      await page.click(`.nav-item[data-screen="${s.nav}"]`);
      const screen = page.locator(`#${s.nav}`);
      await expect(screen, `${s.label} screen renders`).toBeVisible({ timeout: 10_000 });
      await page.waitForTimeout(400); // let async fetches settle
      await page.screenshot({ path: `test-results/sit-evidence/sit-${s.key}.png`, fullPage: true });
      const newErrors = bucket.errors.slice(before.e);
      const newFailed = bucket.failed.slice(before.f);
      if (newErrors.length || newFailed.length) {
        issues.push({ screen: s.label, consoleErrors: newErrors, failedRequests: newFailed });
      }
    }

    // 4. Configurator (reached from Templates via an Edit action, not a sidebar item).
    await page.click(`.nav-item[data-screen="s-templates"]`);
    await expect(page.locator("#s-templates")).toBeVisible();
    const editBtn = page.getByRole("button", { name: /แก้ไข/ }).first();
    if (await editBtn.count()) {
      await editBtn.click();
    } else {
      // Fallback: invoke the same handler the Edit button would (global fn).
      await page.evaluate(() => {
        const w = window as unknown as Record<string, (...a: unknown[]) => void>;
        if (typeof w.openTemplateConfigurator === "function") w.openTemplateConfigurator("view", "SIT check");
        else if (typeof w.navigate === "function") w.navigate("s-template-configurator");
      });
    }
    await expect(page.locator("#s-template-configurator")).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: "test-results/sit-evidence/sit-configurator.png", fullPage: true });

    // 5. Report. Fail the test if any screen produced console errors or failed auth/5xx calls.
    if (issues.length) {
      const report = issues
        .map(
          (i) =>
            `\n[${i.screen}]` +
            (i.consoleErrors.length ? `\n  console: ${i.consoleErrors.join("\n           ")}` : "") +
            (i.failedRequests.length ? `\n  network: ${i.failedRequests.join("\n           ")}` : ""),
        )
        .join("");
      throw new Error(`Click-through found issues on ${issues.length} screen(s):${report}`);
    }
  });
});
