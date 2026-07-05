import { expect, test, type Page } from "@playwright/test";

const RETRY_ATTEMPTS = 3;

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

// Static, no-login-required checks for the W4 UX/UI corrections:
//   - Export: Quick/Template mode picker + inline (non-modal) column adjustment
//   - Company management: AP/AR split, entry no longer labeled bare "COA"
//   - Templates: low-ambiguity Express master template families reflected
// The main-ux-ui.html markup exists in the DOM regardless of login state
// (the login screen is a CSS overlay, not a separate document), so these
// assertions check DOM presence/content only — no interaction that would
// require a real session.
test.describe("W4 Export + Configurator UX corrections", () => {
  test("Export screen has a Quick/Template mode picker, not a modal-first popup", async ({ page }) => {
    await gotoWithRetry(page, "/prototype");
    await expect(page.locator("#exportModeQuickCard")).toHaveCount(1);
    await expect(page.locator("#exportModeTemplateCard")).toHaveCount(1);
    await expect(page.locator("#modal-export-preview")).toHaveCount(0);
  });

  test("Export screen has an inline Adjust Columns panel with reorder/rename/transform/visibility controls", async ({ page }) => {
    await gotoWithRetry(page, "/prototype");
    await expect(page.locator("#exportColumnsBody")).toHaveCount(1);
    await expect(page.locator("#exportAddColumnSelect")).toHaveCount(1);
    await expect(page.locator("#exportPreviewInline")).toHaveCount(1);
    await expect(page.locator("#exportSaveAsTemplateBtn")).toHaveCount(1);
    await expect(page.locator("#exportUpdateTemplateBtn")).toHaveCount(1);
  });

  test("Company entry point is reframed away from a bare 'COA' label", async ({ page }) => {
    await gotoWithRetry(page, "/prototype");
    await expect(page.locator("#s-companies button", { hasText: /^COA$/ })).toHaveCount(0);
    await expect(page.locator("#s-companies button", { hasText: "ตั้งค่า" }).first()).toHaveCount(1);
  });

  test("Company detail separates AP (vendors) and AR (customers) into distinct tabs", async ({ page }) => {
    await gotoWithRetry(page, "/prototype");
    await expect(page.locator("#s-company-detail button", { hasText: /AP.*ผู้จำหน่าย/ })).toHaveCount(1);
    await expect(page.locator("#s-company-detail button", { hasText: /AR.*ลูกค้า/ })).toHaveCount(1);
    await expect(page.locator("#company-ar")).toContainText("Customer Code");
    await expect(page.locator("#modal-import-customer")).toHaveCount(1);
  });

  test("Templates screen reflects the low-ambiguity Express master template families", async ({ page }) => {
    await gotoWithRetry(page, "/prototype");
    const cards = page.locator("#tmpl-master .two-col-grid > .card");
    await expect(cards).toHaveCount(8);
    await expect(page.locator("#tmpl-master")).toContainText("Express ซื้อสด (Book 12)");
    await expect(page.locator("#tmpl-master")).toContainText("Express ซื้อเชื่อ (Book 14)");
    await expect(page.locator("#tmpl-master")).toContainText("Express ค่าใช้จ่ายอื่นๆ (Book 15)");
    await expect(page.locator("#tmpl-master")).toContainText("WHT 3%");
    await expect(page.locator("#tmpl-master")).toContainText("Express ขายสด (Book 22)");
    await expect(page.locator("#tmpl-master")).toContainText("Express ขายเชื่อ (Book 24)");
  });
});
