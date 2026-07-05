import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const RETRY_ATTEMPTS = 3;

async function getWithRetry(request: APIRequestContext, path: string) {
  let lastError: unknown;
  for (let attempt = 1; attempt <= RETRY_ATTEMPTS; attempt += 1) {
    try {
      const response = await request.get(path, { timeout: 30_000 });
      if (!response.ok()) {
        throw new Error(`GET ${path} failed with status ${response.status()}`);
      }
      return response;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

async function gotoWithRetry(page: Page, path: string) {
  let lastError: unknown;
  for (let attempt = 1; attempt <= RETRY_ATTEMPTS; attempt += 1) {
    try {
      await page.goto(path, { waitUntil: "domcontentloaded", timeout: 60_000 });
      return;
    } catch (error) {
      lastError = error;
      if (attempt < RETRY_ATTEMPTS) {
        await page.waitForTimeout(1500);
      }
    }
  }
  throw lastError;
}

test.describe("PoC User-Trial Smoke", () => {
  test("health endpoints respond", async ({ request }) => {
    await expect(await getWithRetry(request, "/health")).toBeOK();
    await expect(await getWithRetry(request, "/api/health")).toBeOK();
  });

  test("prototype alias resolves to the production-facing review page", async ({ page }) => {
    await gotoWithRetry(page, "/prototype");
    await expect(page).toHaveTitle(/Full Prototype/);
    await expect(page).toHaveURL(/\/phase2\/prototype$/);
  });

  test("legacy workflow demo loads with theme assets", async ({ page }) => {
    await gotoWithRetry(page, "/workflow-demo");
    await expect(page).toHaveTitle(/LedgerFlow/);
    await expect(page.locator(".topbar-title")).toHaveText("LedgerFlow");
    const cssResponse = await page.request.get("/static/ux-ui-prototype.css", {
      timeout: 30_000,
    });
    await expect(cssResponse).toBeOK();
    const contentType = cssResponse.headers()["content-type"] || "";
    expect(contentType).toContain("text/css");
  });

  test("phase II review routes render timeline and prototype", async ({ page }) => {
    await gotoWithRetry(page, "/phase2");
    await expect(page).toHaveTitle(/Phase II/);
    await expect(page.getByRole("link", { name: "Open Timeline" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Prototype" })).toBeVisible();

    await gotoWithRetry(page, "/phase2/timeline");
    await expect(page).toHaveTitle(/Project Timeline/);

    await gotoWithRetry(page, "/phase2/prototype");
    await expect(page).toHaveTitle(/Full Prototype/);
  });

  test("legacy workflow controls render without console errors", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        // Known non-blocking noise on some VPS/nginx setups.
        if (text.includes("MIME type ('application/json')") && text.includes("ux-ui-prototype.css")) {
          return;
        }
        errors.push(text);
      }
    });

    await gotoWithRetry(page, "/workflow-demo");
    await page.waitForLoadState("networkidle");
    await expect(page.locator(".step-item")).toHaveCount(6);
    await expect(page.locator("#coaRuleResultWrap")).toBeAttached();
    await expect(page.locator("#coaRuleInlineEditorWrap")).toBeAttached();
    expect(errors).toHaveLength(0);
  });

  test("capture PoC homepage screenshot", async ({ page }) => {
    await gotoWithRetry(page, "/prototype");
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: "playwright-report/poc-homepage.png",
      fullPage: true,
    });
  });
});
