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
//   - Configurator: 3-tab persistent setup surface
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
    // Companies is now a real API-backed table (W4 SIT closure), so the row
    // actions only render once a company list loads — mock a minimal
    // logged-in session instead of relying on static markup.
    await page.addInitScript(() => window.localStorage.setItem("lf_token", "fake-test-token"));
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "11111111-1111-1111-1111-111111111111",
          email: "admin@ledgerflow.local",
          display_name: "SIT Admin",
          role: "admin",
          must_change_password: false,
          company_ids: [],
        }),
      })
    );
    await page.route("**/api/v1/templates**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
    );
    await page.route("**/api/v1/admin/companies", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", name: "Metro Electric", tax_id: "0105560123456", branch_code: "00000", address: null, business_type: null, is_active: true },
        ]),
      })
    );
    await gotoWithRetry(page, "/prototype");
    await expect(page.locator("#companiesTableBody")).toContainText("Metro Electric");
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

  test("Template Configurator is structured as a 3-tab persistent setup surface", async ({ page }) => {
    await gotoWithRetry(page, "/prototype");
    await expect(page.locator("#configTabBtn-upload")).toHaveCount(1);
    await expect(page.locator("#configTabBtn-configure")).toHaveCount(1);
    await expect(page.locator("#configTabBtn-test")).toHaveCount(1);
    await expect(page.locator("#configuratorTab-upload")).toHaveCount(1);
    await expect(page.locator("#configuratorTab-configure")).toHaveCount(1);
    await expect(page.locator("#configuratorTab-test")).toHaveCount(1);
  });
});

// Interaction checks that require the app shell to be visible. These bypass login via a
// client-side-only DOM toggle (no backend call), so they still run without credentials —
// consistent with the rest of this file. They exercise real clicks/inputs, not just DOM
// presence, because a prior pass on this Configurator looked fully wired (onclick="" on
// every button, real backing functions) but every one of those functions was declared
// inside an IIFE and never exposed on `window` — inline onclick handlers run in global
// scope, so every tab button and several actions threw "ReferenceError" and did nothing
// on a real click despite passing pure DOM-presence assertions. These tests click for real.
async function bypassLogin(page: Page) {
  await gotoWithRetry(page, "/prototype");
  await page.evaluate(() => {
    const loginScreen = document.getElementById("login-screen");
    const app = document.getElementById("app");
    if (loginScreen) loginScreen.style.display = "none";
    if (app) app.classList.add("visible");
  });
}

test.describe("W4 Export + Configurator interaction wiring", () => {
  test("Configurator tab buttons switch panels via real clicks with no console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await bypassLogin(page);
    await page.evaluate(() => (window as unknown as { navigate: (id: string) => void }).navigate("s-template-configurator"));

    await page.click("#configTabBtn-configure");
    await expect(page.locator("#configuratorTab-configure")).toBeVisible();
    await expect(page.locator("#configuratorTab-upload")).toBeHidden();

    await page.click("#configTabBtn-test");
    await expect(page.locator("#configuratorTab-test")).toBeVisible();

    await page.click("#configTabBtn-upload");
    await expect(page.locator("#configuratorTab-upload")).toBeVisible();

    expect(errors, "console/page errors during real tab clicks: " + JSON.stringify(errors)).toEqual([]);
  });

  test("Configurator's Configure tab has a real editable column table shared with the Export screen", async ({ page }) => {
    await bypassLogin(page);
    await page.evaluate(() => {
      const w = window as unknown as { navigate: (id: string) => void; setExportMode: (m: string) => void; setConfiguratorTab: (t: string) => void };
      w.navigate("s-template-configurator");
      w.setExportMode("quick");
      w.setConfiguratorTab("configure");
    });

    const rows = page.locator("#configuratorColumnsBody tr");
    await expect(rows).toHaveCount(10);

    const firstInput = rows.nth(0).locator("input.field-input");
    await firstInput.fill("Renamed From Configurator");
    await expect(firstInput).toHaveValue("Renamed From Configurator");

    // Same state.exportColumns array backs the Export screen's own table.
    await page.evaluate(() => (window as unknown as { navigate: (id: string) => void }).navigate("s-export"));
    const exportFirstValue = await page.locator("#exportColumnsBody tr").nth(0).locator("input.field-input").inputValue();
    expect(exportFirstValue).toBe("Renamed From Configurator");
  });

  test("Orphaned client-side Quick Export helpers were removed", async ({ page }) => {
    await bypassLogin(page);
    const stillDefined = await page.evaluate(() => {
      const w = window as unknown as Record<string, unknown>;
      return typeof w.downloadQuickExportCsv === "function" || typeof w.renderQuickPreview === "function";
    });
    expect(stillDefined).toBe(false);
  });
});

// Regression guard for W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02 (Codex Review 01
// found Review Scan / Review Mapping / Processing fixture controls still
// claiming success via showToast(..., 'ok') with no backend behind them).
// These are static, no-login-required fixture screens, so a real click is
// enough to prove the toast type/wording without mocking any API.
test.describe("W4 SIT E2E — residual fake-success controls stay honestly deferred", () => {
  test("Review Scan Approve and Approve All show a deferred warning, not a fake success", async ({ page }) => {
    await bypassLogin(page);
    await page.click("[data-screen='s-review-scan']");

    await page.click("button:has-text('✓ Approve')");
    let toast = page.locator(".toast").last();
    await expect(toast).toHaveClass(/warn/);
    await expect(toast).not.toHaveClass(/\bok\b/);
    await expect(toast).toContainText("deferred");

    await page.click("button:has-text('✓ Approve All ที่เหลือ')");
    toast = page.locator(".toast").last();
    await expect(toast).toHaveClass(/warn/);
    await expect(toast).toContainText("deferred");
  });

  test("Review Scan Flag modal shows a deferred warning, not a fake success", async ({ page }) => {
    await bypassLogin(page);
    await page.click("[data-screen='s-review-scan']");
    await page.click("button:has-text('🚩 Flag')");
    await page.click("#modal-flag button:has-text('บันทึก Flag')");

    const toast = page.locator(".toast").last();
    await expect(toast).toHaveClass(/warn/);
    await expect(toast).toContainText("deferred");
  });

  test("Review Mapping Confirm shows a deferred warning, not a fake success", async ({ page }) => {
    await bypassLogin(page);
    await page.click("[data-screen='s-review-mapping']");
    await page.click("button:has-text('✓ Confirm Mapping')");

    const toast = page.locator(".toast").last();
    await expect(toast).toHaveClass(/warn/);
    await expect(toast).not.toHaveClass(/\bok\b/);
    await expect(toast).toContainText("deferred");
  });

  test("Processing error-retry modal shows a deferred warning, not a fake success", async ({ page }) => {
    await bypassLogin(page);
    await page.click("[data-screen='s-processing']");
    await page.click("a:has-text('ดู Error')");
    await page.click("#modal-proc-error button:has-text('ลองใหม่')");

    const toast = page.locator(".toast").last();
    await expect(toast).toHaveClass(/warn/);
    await expect(toast).toContainText("deferred");
  });
});
