import { expect, test, type Page } from "@playwright/test";

const RETRY_ATTEMPTS = 3;
const LOCAL_BASE = "http://127.0.0.1:8765";

async function gotoWithRetry(page: Page, path: string) {
  let lastError: unknown;
  await page.route("**/static/auth.js**", (route) =>
    route.fulfill({ path: "src/frontend/auth.js", contentType: "application/javascript" })
  );
  for (let attempt = 1; attempt <= RETRY_ATTEMPTS; attempt += 1) {
    try {
      await page.goto(LOCAL_BASE + path, { waitUntil: "domcontentloaded", timeout: 60_000 });
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
    await gotoWithRetry(page, "/main-ux-ui.html");
    await expect(page.locator("#exportModeQuickCard")).toHaveCount(1);
    await expect(page.locator("#exportModeTemplateCard")).toHaveCount(1);
    await expect(page.locator("#modal-export-preview")).toHaveCount(0);
  });

  test("Export screen has an inline Adjust Columns panel with reorder/rename/transform/visibility controls", async ({ page }) => {
    await gotoWithRetry(page, "/main-ux-ui.html");
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
    await gotoWithRetry(page, "/main-ux-ui.html");
    await expect(page.locator("#companiesTableBody")).toContainText("Metro Electric");
    await expect(page.locator("#s-companies button", { hasText: /^COA$/ })).toHaveCount(0);
    await expect(page.locator("#s-companies button", { hasText: "ตั้งค่า" }).first()).toHaveCount(1);
  });

  test("Company detail separates AP (vendors) and AR (customers) into distinct tabs", async ({ page }) => {
    await gotoWithRetry(page, "/main-ux-ui.html");
    await expect(page.locator("#s-company-detail button", { hasText: /AP.*ผู้จำหน่าย/ })).toHaveCount(1);
    await expect(page.locator("#s-company-detail button", { hasText: /AR.*ลูกค้า/ })).toHaveCount(1);
    await expect(page.locator("#company-ar")).toContainText("Customer Code");
    await expect(page.locator("#modal-import-customer")).toHaveCount(1);
  });

  test("Templates screen renders Master Templates from real backend data, not a static fixture", async ({ page }) => {
    // W4 SIT closure (Pack C) replaced the 8 hardcoded Express template fixture
    // cards with a company-scoped, API-backed Master/Company template list.
    // Without a logged-in session this container stays empty/loading — real
    // data coverage lives in w4-templates-real-uxui.spec.ts. Here we only
    // assert the dynamic scaffold exists and no fixture content leaked back in.
    await gotoWithRetry(page, "/main-ux-ui.html");
    await expect(page.locator("#tmplMasterCardsBody")).toHaveCount(1);
    await expect(page.locator("#tmplMasterCount")).toHaveCount(1);
    await expect(page.locator("#tmpl-master")).not.toContainText("Express ซื้อสด (Book 12)");
  });

  test("Template Configurator is structured as a 3-tab persistent setup surface", async ({ page }) => {
    await gotoWithRetry(page, "/main-ux-ui.html");
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
  await gotoWithRetry(page, "/main-ux-ui.html");
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

  test("Create Template starts a manual blank configurator path without forcing sample upload first", async ({ page }) => {
    await bypassLogin(page);
    await page.evaluate(() => (window as unknown as { navigate: (id: string) => void }).navigate("s-templates"));

    await page.click("button:has-text('สร้าง Template ใหม่')");

    await expect(page.locator("#s-template-configurator")).toHaveClass(/active/);
    await expect(page.locator("#configuratorTab-configure")).toBeVisible();
    await expect(page.locator("#configuratorTab-upload")).toBeHidden();
    await expect(page.locator("#configConfigureLiveColumns")).toContainText("ยังไม่มี runtime columns");
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

// Former regression guard for W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02 (Codex Review
// 01 found Review Scan / Review Mapping / Processing fixture controls still
// claiming success via showToast(..., 'ok') with no backend behind them).
// W4 SIT closure Pack B (TASK-W4-SIT-E2E-CLAUDE-IMPLEMENT-ROUTINE-OPS-05)
// replaced those honest-defer fixture controls with real API-backed behavior,
// so the "stays deferred" assertions this block used to make are no longer
// true by design — real coverage for Approve/Approve All/Flag/Confirm Mapping
// now lives in tests/e2e/w4-routine-ops-uxui.spec.ts. The Processing screen's
// per-row error-retry modal (`#modal-proc-error`) was fixture-only dead
// markup with no real per-stage progress backing it and has been removed
// along with its trigger.
