import { expect, test } from "@playwright/test";

test.describe("PoC User-Trial Smoke", () => {
  test("health endpoints respond", async ({ request }) => {
    await expect(await request.get("/health")).toBeOK();
    await expect(await request.get("/api/health")).toBeOK();
  });

  test("prototype loads with theme assets", async ({ page }) => {
    await page.goto("/prototype");
    await expect(page).toHaveTitle(/LedgerFlow/);
    await expect(page.locator(".topbar-title")).toHaveText("LedgerFlow");

    const font = await page
      .locator("body")
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(font).toContain("DM Sans");
  });

  test("core workflow controls render without console errors", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
    });

    await page.goto("/prototype");
    await page.waitForLoadState("networkidle");
    await expect(page.locator(".step-item")).toHaveCount(6);
    await expect(page.locator("#coaRuleResultWrap")).toBeAttached();
    await expect(page.locator("#coaRuleInlineEditorWrap")).toBeAttached();
    expect(errors).toHaveLength(0);
  });

  test("capture PoC homepage screenshot", async ({ page }) => {
    await page.goto("/prototype");
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: "playwright-report/poc-homepage.png",
      fullPage: true,
    });
  });
});
