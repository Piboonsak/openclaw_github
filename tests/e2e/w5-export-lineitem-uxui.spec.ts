/**
 * W5-EXPORT-LINEITEM-REALDATA-04 — real-data Export + line-item review UI.
 *
 * Proves: (1) the live Export page lists REAL reviewed/mapped documents for the
 * selected company (with an honest empty state and no fixture rows) and sends
 * `company_id` on the live preview/export path; (2) Review Scan renders extracted
 * line items for an enable_stock document and can confirm them.
 *
 * Local run (PowerShell), static root serving src/frontend with /static/auth.js:
 *   $env:POC_URL='http://127.0.0.1:8765'; npx playwright test tests/e2e/w5-export-lineitem-uxui.spec.ts --workers=1
 */
import { expect, test, type Page } from "@playwright/test";

const LOCAL_BASE = "http://127.0.0.1:8765";

async function gotoWithRetry(page: Page, path: string) {
  let lastError: unknown;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      await page.goto(LOCAL_BASE + path, { waitUntil: "domcontentloaded", timeout: 60_000 });
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
  name: "บริษัท สต๊อก จำกัด",
  tax_id: "0125561025189",
  branch_code: "00000",
  address: null,
  business_type: "trading",
  is_active: true,
  settings: { enable_stock: true },
};

const DOC_READY = {
  id: "doc-9",
  filename: "INV-STOCK-001.pdf",
  original_filename: "INV-STOCK-001.pdf",
  status: "mapping_confirmed",
  scan_status: "approved",
  invoice_number: "INV-STOCK-001",
  invoice_date: "2026-07-01",
  seller_name: "Vendor Co",
  buyer_tax_id: "0125561025189",
  taxid_match: true,
  net_amount: 1000.0,
  vat_amount: 70.0,
  wht_amount: 0.0,
  total_amount: 1070.0,
  overall_confidence: 0.9,
  processing_error: null,
  created_at: "2026-07-05T10:00:00Z",
};

const DOC_DETAIL_WITH_LINE_ITEMS = {
  ...DOC_READY,
  status: "review_scan",
  extraction_fields: {},
  confidence_per_field: {},
  critical_flags: {},
  voucher: null,
  line_items: [
    {
      id: "li-1",
      line_order: 1,
      product_name: "ท่อ PVC 4 นิ้ว",
      qty: 10,
      unit: "เส้น",
      unit_price: 80,
      line_amount: 800,
      confidence: 0.86,
      line_type: "part_or_material",
      matched_product_code: null,
      status: "pending",
    },
  ],
};

async function baseMocks(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FAKE_USER) }),
  );
  await page.route("**/api/v1/admin/companies", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([COMPANY_A]) }),
  );
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}

async function login(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem("lf_token", "fake-test-token"));
  await gotoWithRetry(page, "/main-ux-ui.html");
  await page.waitForFunction(() => {
    const el = document.getElementById("companiesStatus");
    return !!el && el.textContent !== "กำลังโหลดรายชื่อบริษัท...";
  });
}

test.describe("W5 real-data Export + line items", () => {
  test("Export lists real ready documents and sends company_id on live preview (no fixtures)", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_READY]) }),
    );
    let previewBody: any = null;
    await page.route("**/api/v1/export/preview", (route) => {
      previewBody = JSON.parse(route.request().postData() || "{}");
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ columns: ["Invoice No."], rows: [["INV-STOCK-001"]] }),
      });
    });
    await login(page);

    await page.click("[data-screen='s-export']");
    // Real ready-document list, no Metro/INV-2605 fixture.
    await expect(page.locator("#exportDocsBody")).toContainText("INV-STOCK-001.pdf");
    await expect(page.locator("#exportDocsCount")).toContainText("1 เอกสาร");
    await expect(page.locator("#exportDocsBody")).not.toContainText("Metro");

    await page.click("#exportModeQuickCard");
    await page.click("#exportPreviewBtn");
    await expect.poll(() => (previewBody ? previewBody.company_id : null)).toBe(COMPANY_A.id);
  });

  test("Export shows an honest empty state when no documents are ready", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    await login(page);

    await page.click("[data-screen='s-export']");
    await expect(page.locator("#exportDocsBody")).toContainText("ยังไม่มีเอกสารที่พร้อม export");
    await expect(page.locator("#exportDocsBody")).not.toContainText("Metro");
  });

  test("Review Scan renders extracted line items and confirms them", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ ...DOC_READY, status: "review_scan", scan_status: "pending" }]),
      }),
    );
    await page.route("**/api/v1/documents/doc-9", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(DOC_DETAIL_WITH_LINE_ITEMS) }),
    );
    await page.route("**/api/v1/documents/doc-9/line-items/confirm", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ...DOC_DETAIL_WITH_LINE_ITEMS,
          line_items: [{ ...DOC_DETAIL_WITH_LINE_ITEMS.line_items[0], status: "confirmed" }],
        }),
      }),
    );
    await login(page);

    await page.click("[data-screen='s-review-scan']");
    await page.click("#reviewScanListBody li");
    // Line-item review table appears with the extracted product (editable input).
    await expect(page.locator("#reviewScanLineItemsCard")).toBeVisible();
    await expect(
      page.locator('#reviewScanLineItems input[data-li-field="product_name"]'),
    ).toHaveValue("ท่อ PVC 4 นิ้ว");
    await expect(page.locator("#reviewScanLineItems")).toContainText("รอยืนยัน");

    await page.click("#reviewScanConfirmLineItemsBtn");
    await expect(page.locator("#reviewScanLineItems")).toContainText("ยืนยันแล้ว");
  });
});
