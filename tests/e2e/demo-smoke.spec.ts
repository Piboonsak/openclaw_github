import { test, expect } from "@playwright/test";

test.describe("Demo Site Post-Deploy Smoke", () => {
  test("page loads with expected title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/LedgerFlow/);
  });

  test("topbar brand renders", async ({ page }) => {
    await page.goto("/");
    const brand = page.locator(".topbar-title");
    await expect(brand).toHaveText("LedgerFlow");
  });

  test("css is loaded", async ({ page }) => {
    await page.goto("/");
    const font = await page
      .locator("body")
      .evaluate((el) => getComputedStyle(el).fontFamily);
    expect(font).toContain("DM Sans");
  });

  test("step wizard and key actions render", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".step-item")).toHaveCount(6);
    await expect(page.locator("button, .btn").first()).toBeVisible();
  });

  test("no console errors on load", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });

  test("capture visual screenshot", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: "playwright-report/demo-homepage.png",
      fullPage: true,
    });
  });
});
