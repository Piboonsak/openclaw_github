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
  id: "doc-2",
  filename: "INV-002.pdf",
  status: "review_scan",
  scan_status: "pending",
  invoice_number: "INV-002",
  invoice_date: "2026-07-01",
  seller_name: "Vendor Co Ltd",
  buyer_tax_id: "0125561025189",
  taxid_match: true,
  net_amount: 1000.0,
  vat_amount: 70.0,
  wht_amount: 30.0,
  total_amount: 1040.0,
  overall_confidence: 0.91,
};

const DOC_SCAN_APPROVED = {
  ...DOC_REVIEW_SCAN,
  id: "doc-3",
  filename: "INV-003.pdf",
  invoice_number: "INV-003",
  status: "scan_approved",
  scan_status: "approved",
};

const VOUCHER = {
  id: "voucher-1",
  voucher_no: null,
  voucher_date: "2026-07-01",
  book_code: "PV",
  rule_id: "DEFAULT-PURCHASE",
  status: "draft",
  is_balanced: true,
  total_debit: 1070.0,
  total_credit: 1070.0,
  flags: [],
  lines: [
    { id: "line-1", line_order: 1, account_code: "5040", account_name: "ค่าใช้จ่าย", is_debit: true, amount: 1000.0, description: null },
    { id: "line-2", line_order: 2, account_code: "1154", account_name: "ภาษีซื้อ", is_debit: true, amount: 70.0, description: null },
    { id: "line-3", line_order: 3, account_code: "2195", account_name: "เจ้าหนี้การค้า", is_debit: false, amount: 1070.0, description: null },
  ],
};

async function baseMocks(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FAKE_USER) })
  );
  await page.route("**/api/v1/admin/companies", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([COMPANY_A]) })
  );
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
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

test.describe("W4 SIT closure — real routine Upload/Processing/Review Scan/Review Mapping (Pack B)", () => {
  test("Upload dropzone is genuinely clickable and opens the native file picker", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
    );
    await login(page);

    await page.click("[data-screen='s-upload']");
    await page.selectOption("#uploadCompanySelect", COMPANY_A.id);

    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.click("#uploadDropzone");
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: "INV-clickable.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 clickable picker"),
    });

    await expect(page.locator("#uploadFileCount")).toHaveText("1");
    await expect(page.locator("#uploadFileListBody")).toContainText("INV-clickable.pdf");
  });

  test("Upload screen lists real companies and calls the real upload API", async ({ page }) => {
    await baseMocks(page);
    let uploadCalled = false;
    await page.route("**/api/v1/companies/*/documents/upload", (route) => {
      uploadCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ documents: [DOC_UPLOADED] }),
      });
    });
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
    );
    await login(page);

    await page.click("[data-screen='s-upload']");
    await expect(page.locator("#uploadCompanySelect option")).toHaveCount(2); // placeholder + COMPANY_A
    await page.selectOption("#uploadCompanySelect", COMPANY_A.id);

    await page.setInputFiles("#uploadFileInput", {
      name: "INV-001.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 fake content"),
    });
    await expect(page.locator("#uploadFileCount")).toHaveText("1");
    await expect(page.locator("#uploadFileListBody")).toContainText("INV-001.pdf");

    await page.click("#uploadSubmitBtn");
    await expect(page.locator("#s-processing")).toBeVisible();
    expect(uploadCalled).toBe(true);
  });

  test("Processing screen shows real per-document status and processes pending documents", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_UPLOADED]) });
      }
      return route.continue();
    });
    let processCalled = false;
    await page.route("**/api/v1/documents/*/process", (route) => {
      processCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...DOC_REVIEW_SCAN, id: DOC_UPLOADED.id }),
      });
    });
    await login(page);

    await page.click("[data-screen='s-processing']");
    await expect(page.locator("#processingTableBody")).toContainText("INV-001.pdf");
    await expect(page.locator("#processingTableBody")).toContainText("อัปโหลดแล้ว");

    await page.click("#processingStartBtn");
    await expect(page.locator("#s-review-scan")).toBeVisible({ timeout: 10_000 });
    expect(processCalled).toBe(true);
  });

  test("Review Scan loads real extraction data and Approve calls the real API", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_REVIEW_SCAN]) })
    );
    await page.route("**/api/v1/documents/doc-2", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...DOC_REVIEW_SCAN, extraction_fields: {}, confidence_per_field: {}, critical_flags: {}, voucher: null }) })
    );
    let approveCalled = false;
    await page.route("**/api/v1/documents/doc-2/approve", (route) => {
      approveCalled = true;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...DOC_REVIEW_SCAN, status: "scan_approved" }) });
    });
    await login(page);

    await page.click("[data-screen='s-review-scan']");
    await expect(page.locator("#reviewScanListBody")).toContainText("INV-002");
    await page.click("#reviewScanListBody li");
    await expect(page.locator("#reviewScanFields input[value='INV-002']")).toHaveCount(1);
    await expect(page.locator("#reviewScanApproveBtn")).toBeEnabled();

    // Register the response listener BEFORE clicking — the mocked response can
    // resolve in the microtask gap after click() and be missed forever otherwise.
    const approveResponse = page.waitForResponse((r) => r.url().includes("/documents/doc-2/approve"));
    await page.click("#reviewScanApproveBtn");
    await approveResponse;
    expect(approveCalled).toBe(true);
  });

  test("Review Scan field edits are saved via the real PUT /fields API (TC-RWG03-04)", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_REVIEW_SCAN]) })
    );
    await page.route("**/api/v1/documents/doc-2", (route) => {
      if (route.request().method() !== "GET") return route.continue();
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...DOC_REVIEW_SCAN, extraction_fields: {}, confidence_per_field: {}, critical_flags: {}, voucher: null }) });
    });
    await page.route("**/api/v1/documents/doc-2/file", (route) =>
      route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) })
    );
    let putBody: any = null;
    await page.route("**/api/v1/documents/doc-2/fields", (route) => {
      putBody = route.request().postDataJSON();
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...DOC_REVIEW_SCAN, invoice_number: "INV-002-CORRECTED" }) });
    });
    await login(page);

    await page.click("[data-screen='s-review-scan']");
    await page.click("#reviewScanListBody li");
    await expect(page.locator("#reviewScanSaveBtn")).toBeEnabled();

    await page.fill("#reviewScanFieldInvoiceNumber", "INV-002-CORRECTED");
    const fieldsResponse = page.waitForResponse((r) => r.url().includes("/documents/doc-2/fields"));
    await page.click("#reviewScanSaveBtn");

    await fieldsResponse;
    expect(putBody.invoice_number).toBe("INV-002-CORRECTED");
  });

  test("Review Scan shows a real in-page file preview fetched from the file API, not a placeholder", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_REVIEW_SCAN]) })
    );
    await page.route("**/api/v1/documents/doc-2", (route) => {
      if (route.request().method() !== "GET") return route.continue();
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...DOC_REVIEW_SCAN, extraction_fields: {}, confidence_per_field: {}, critical_flags: {}, voucher: null }) });
    });
    let fileRequested = false;
    await page.route("**/api/v1/documents/doc-2/file", (route) => {
      fileRequested = true;
      return route.fulfill({ status: 200, contentType: "application/pdf", body: Buffer.from("%PDF-1.4 fake pdf bytes") });
    });
    await login(page);

    await page.click("[data-screen='s-review-scan']");
    await page.click("#reviewScanListBody li");

    await expect(page.locator("#reviewScanPreviewBody iframe")).toHaveCount(1);
    await expect(page.locator("#reviewScanDownloadLink")).toBeVisible();
    expect(fileRequested).toBe(true);
  });

  test("Review Scan Flag modal submits the real flag API with reason and comment", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_REVIEW_SCAN]) })
    );
    await page.route("**/api/v1/documents/doc-2", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...DOC_REVIEW_SCAN, extraction_fields: {}, confidence_per_field: {}, critical_flags: {}, voucher: null }) })
    );
    let flagBody: any = null;
    await page.route("**/api/v1/documents/doc-2/flag", (route) => {
      flagBody = route.request().postDataJSON();
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...DOC_REVIEW_SCAN, status: "scan_flagged" }) });
    });
    await login(page);

    await page.click("[data-screen='s-review-scan']");
    await page.click("#reviewScanListBody li");
    await page.click("#reviewScanFlagBtn");
    await expect(page.locator("#modal-flag")).toHaveClass(/open/);
    await page.selectOption("#flagReasonSelect", "เลขภาษีไม่ตรง");
    await page.fill("#flagCommentInput", "buyer tax id mismatch");
    await page.click("text=บันทึก Flag");

    await expect(page.locator("#modal-flag")).not.toHaveClass(/open/);
    expect(flagBody).toEqual({ reason: "เลขภาษีไม่ตรง", comment: "buyer tax id mismatch" });
  });

  test("Review Mapping shows real Dr/Cr lines and Confirm calls the real API", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_SCAN_APPROVED]) })
    );
    await page.route("**/api/v1/documents/doc-3", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...DOC_SCAN_APPROVED, extraction_fields: {}, confidence_per_field: {}, critical_flags: {}, voucher: VOUCHER }),
      })
    );
    let confirmCalled = false;
    await page.route("**/api/v1/journal-vouchers/voucher-1/confirm", (route) => {
      confirmCalled = true;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...VOUCHER, status: "confirmed" }) });
    });
    await login(page);

    await page.click("[data-screen='s-review-mapping']");
    await expect(page.locator("#reviewMappingListBody")).toContainText("INV-003");
    await page.click("#reviewMappingListBody li");
    await expect(page.locator("#reviewMappingDetail")).toContainText("✓ Balance");
    await expect(page.locator("#reviewMappingDetail input[value='5040']")).toHaveCount(1);

    // Register the response listener BEFORE clicking — the mocked response can
    // resolve in the microtask gap after click() and be missed forever otherwise.
    const confirmResponse = page.waitForResponse((r) => r.url().includes("/journal-vouchers/voucher-1/confirm"));
    await page.click("#confirmMappingBtn");
    await confirmResponse;
    expect(confirmCalled).toBe(true);
  });

  test("Review Mapping blocks Confirm when the voucher is unbalanced", async ({ page }) => {
    await baseMocks(page);
    const unbalancedVoucher = { ...VOUCHER, is_balanced: false, total_debit: 500, total_credit: 1070 };
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_SCAN_APPROVED]) })
    );
    await page.route("**/api/v1/documents/doc-3", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...DOC_SCAN_APPROVED, extraction_fields: {}, confidence_per_field: {}, critical_flags: {}, voucher: unbalancedVoucher }),
      })
    );
    await login(page);

    await page.click("[data-screen='s-review-mapping']");
    await page.click("#reviewMappingListBody li");
    await expect(page.locator("#reviewMappingDetail")).toContainText("✗ Unbalanced");
    await expect(page.locator("#confirmMappingBtn")).toBeDisabled();
  });

  test("Review Mapping account-code edit calls the real PUT API", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_SCAN_APPROVED]) })
    );
    await page.route("**/api/v1/documents/doc-3", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...DOC_SCAN_APPROVED, extraction_fields: {}, confidence_per_field: {}, critical_flags: {}, voucher: VOUCHER }),
      })
    );
    let putBody: any = null;
    await page.route("**/api/v1/journal-vouchers/voucher-1/lines/line-1", (route) => {
      putBody = route.request().postDataJSON();
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...VOUCHER, lines: [{ ...VOUCHER.lines[0], account_code: "5099" }, ...VOUCHER.lines.slice(1)] }),
      });
    });
    await login(page);

    await page.click("[data-screen='s-review-mapping']");
    await page.click("#reviewMappingListBody li");
    const firstLineInput = page.locator("#reviewMappingDetail table.data-table input.mono").first();
    await firstLineInput.fill("5099");
    const lineResponse = page.waitForResponse((r) => r.url().includes("/journal-vouchers/voucher-1/lines/line-1"));
    await firstLineInput.dispatchEvent("change");

    await lineResponse;
    expect(putBody).toEqual({ account_code: "5099" });
  });
});
