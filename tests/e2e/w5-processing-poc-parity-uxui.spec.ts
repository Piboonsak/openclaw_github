/**
 * W5-PROCESSING-POC-PARITY-01 — Processing screen POC-parity / perceived-stall fix.
 *
 * Proves the acceptance criterion "a focused local test proves the Processing
 * table renders queued/running/done/error stage states":
 *  1. A document driven through the real Celery task path (queued -> ocr ->
 *     extract -> mapping -> success) shows per-file stage glyphs advancing, a
 *     live elapsed clock, a "still working" reassurance note, and a stage-weighted
 *     progress bar that leaves 0% while a single doc is still running — then hands
 *     off into Review Scan.
 *  2. A document that failed (backend status "error", the off-enum value the old
 *     UI rendered as green) is honestly shown as a danger/failure row with retry.
 *
 * Local run (PowerShell), serving src/frontend on 127.0.0.1:8765:
 *   $env:POC_URL='http://127.0.0.1:8765'; npx playwright test tests/e2e/w5-processing-poc-parity-uxui.spec.ts --workers=1
 */
import { expect, test, type Page } from "@playwright/test";

const LOCAL_BASE = "http://127.0.0.1:8765";

async function gotoWithRetry(page: Page, path: string) {
  let lastError: unknown;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      await page.goto(LOCAL_BASE + path, {
        waitUntil: "domcontentloaded",
        timeout: 60_000,
      });
      return;
    } catch (error) {
      lastError = error;
      if (attempt < 3) await page.waitForTimeout(1500);
    }
  }
  throw lastError;
}

const FAKE_USER = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "admin@ledgerflow.local",
  display_name: "SIT Admin",
  role: "admin",
  must_change_password: false,
  company_ids: ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"],
};

const COMPANY_A = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  name: "บริษัท ฤทธิ์ล้ำเลิศ จำกัด",
  tax_id: "0125561025189",
  branch_code: "00000",
  address: null,
  business_type: "trading",
  is_active: true,
};

const DOC_UPLOADED = {
  id: "doc-1",
  filename: "INV-001.pdf",
  original_filename: "INV-001.pdf",
  status: "uploaded",
  scan_status: null,
  content_type: "application/pdf",
  file_size_bytes: 1024,
  invoice_number: null,
  invoice_date: null,
  seller_name: null,
  buyer_tax_id: null,
  taxid_match: null,
  net_amount: null,
  vat_amount: null,
  wht_amount: null,
  total_amount: null,
  overall_confidence: null,
  processing_error: null,
  created_at: "2026-07-05T10:00:00Z",
};

const DOC_REVIEW_SCAN = {
  ...DOC_UPLOADED,
  status: "review_scan",
  scan_status: "pending",
  invoice_number: "INV-001",
  invoice_date: "2026-07-01",
  seller_name: "Vendor Co Ltd",
  buyer_tax_id: "0125561025189",
  taxid_match: true,
  net_amount: 1000.0,
  vat_amount: 70.0,
  total_amount: 1070.0,
  overall_confidence: 0.91,
};

// Backend task-level failure historically persisted the off-enum string "error"
// (not "failed"); the old Processing UI did not recognise it and rendered a green
// badge. This fixture exercises that exact honesty gap.
const DOC_ERROR = {
  ...DOC_UPLOADED,
  id: "doc-err",
  filename: "INV-ERR.pdf",
  original_filename: "INV-ERR.pdf",
  status: "error",
  processing_error: "OCR failed: unreadable scan",
};

async function baseMocks(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_USER),
    }),
  );
  await page.route("**/api/v1/admin/companies", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([COMPANY_A]),
    }),
  );
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}

async function login(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("lf_token", "fake-test-token");
  });
  await gotoWithRetry(page, "/main-ux-ui.html");
  await page.waitForFunction(() => {
    const el = document.getElementById("companiesStatus");
    return !!el && el.textContent !== "กำลังโหลดรายชื่อบริษัท...";
  });
}

test.describe("W5 Processing POC parity", () => {
  test("per-file stages advance (queued→OCR→extract→mapping) with elapsed + moving stage bar, then hands off to Review Scan", async ({
    page,
  }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([DOC_UPLOADED]),
        });
      }
      return route.continue();
    });
    await page.route("**/api/v1/tasks/process-document/*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          task_id: "task-doc-1",
          status: "pending",
          document_id: DOC_UPLOADED.id,
        }),
      }),
    );
    // Sequential poll responses: the real backend reports a live "stage" only
    // while the Celery task is in PROGRESS ("started"). Hold each stage for a few
    // polls so the UI's running glyph/elapsed can be observed, then succeed.
    let poll = 0;
    await page.route("**/api/v1/tasks/task-doc-1", (route) => {
      poll += 1;
      let body: Record<string, unknown>;
      if (poll <= 3) {
        body = { task_id: "task-doc-1", status: "started", stage: "ocr" };
      } else if (poll <= 5) {
        body = { task_id: "task-doc-1", status: "started", stage: "extract" };
      } else if (poll <= 6) {
        body = { task_id: "task-doc-1", status: "started", stage: "mapping" };
      } else {
        body = {
          task_id: "task-doc-1",
          status: "success",
          stage: null,
          result: { status: "review_scan" },
        };
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });
    });
    await page.route("**/api/v1/documents/doc-1", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(DOC_REVIEW_SCAN),
      }),
    );
    await login(page);

    await page.click("[data-screen='s-processing']");
    await expect(page.locator("#processingTableBody")).toContainText("INV-001.pdf");
    // New glyph stage columns are present in the header.
    await expect(page.locator("#s-processing thead")).toContainText("OCR");
    await expect(page.locator("#s-processing thead")).toContainText("สกัดข้อมูล");
    await expect(page.locator("#s-processing thead")).toContainText("จัดบัญชี");

    await page.click("#processingStartBtn");

    // While the doc is running: a spinning stage glyph, a live elapsed clock, the
    // reassurance note, and a stage-weighted bar that has left 0% (single doc at
    // the "ocr" stage → conservative 35%). None of this is fake data — it is
    // derived from the real task "stage" field.
    await expect(page.locator("#processingTableBody .spin")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator("#processingTableBody")).toContainText("⏱");
    await expect(page.locator("#processingRunningNote")).toBeVisible();
    await expect(page.locator("#processingRunningNote")).toContainText("ระบบยังทำงานอยู่");
    // The stage-weighted bar must leave 0% while the single doc is mid-pipeline
    // (exact % depends on stage weights, so just assert it moved off zero).
    await expect(page.locator("#processingPercentText")).not.toHaveText("0%");

    // Completion hands off to Review Scan.
    await expect(page.locator("#s-review-scan")).toBeVisible({ timeout: 20_000 });
    expect(poll).toBeGreaterThanOrEqual(7);
  });

  test("a failed document (backend status 'error') is shown honestly as a failure with retry, not a green badge", async ({
    page,
  }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([DOC_ERROR]),
        });
      }
      return route.continue();
    });
    await login(page);

    await page.click("[data-screen='s-processing']");

    const bodyLoc = page.locator("#processingTableBody");
    await expect(bodyLoc).toContainText("INV-ERR.pdf");
    // Honest failure state: danger badge (not the old green), the ✗ stage glyph,
    // the error message, and a retry affordance.
    await expect(bodyLoc.locator(".badge-danger")).toBeVisible();
    await expect(bodyLoc).toContainText("ผิดพลาด");
    await expect(bodyLoc).toContainText("✗");
    await expect(bodyLoc).toContainText("OCR failed: unreadable scan");
    await expect(
      bodyLoc.locator("button", { hasText: "ลองใหม่" }),
    ).toBeVisible();
    // The summary legend counts the failure explicitly.
    await expect(page.locator("#processingLegend")).toContainText("ผิดพลาด 1");
    await expect(page.locator("#processingLegend")).toContainText("เสร็จแล้ว 0");
  });
});
