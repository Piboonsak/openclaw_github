import { expect, test, type Page } from "@playwright/test";

const RETRY_ATTEMPTS = 3;

// This spec verifies uncommitted local edits to main-ux-ui.html. The repo's
// default Playwright baseURL comes from `.env.sit.local` (POC_URL, the real
// deployed SIT server) — going through that would test the *last-deployed*
// HTML, not these local changes. Point straight at a throwaway local static
// server instead (see scratch/localweb) so this spec exercises the file on disk.
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
      if (attempt < RETRY_ATTEMPTS) await page.waitForTimeout(1500);
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
  name: "Metro Electric Co Ltd",
  tax_id: "0105560123456",
  branch_code: "00000",
  address: null,
  business_type: "retail",
  is_active: true,
};

async function mockBaseApis(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FAKE_USER) })
  );
  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
  await page.route("**/api/v1/admin/companies", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([COMPANY_A]) });
    }
    return route.continue();
  });
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
  await page.route("**/api/v1/companies/*/vendor-master", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 50, search: null }) })
  );
  await page.route("**/api/v1/companies/*/customer-master", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 50, search: null }) })
  );
}

// Playwright invokes the MOST RECENTLY registered route handler first (not
// last), so a generic fallback registered here would always shadow whatever
// a test registers beforehand. Every test must therefore register its own
// `/coa` and `/mapping-rules` routes explicitly (opening company detail always
// fetches both) rather than relying on a shared default.
async function loginWithMocks(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("lf_token", "fake-test-token");
  });
  await mockBaseApis(page);
  await gotoWithRetry(page, "/main-ux-ui.html");
  await page.waitForFunction(() => {
    const el = document.getElementById("companiesStatus");
    return !!el && el.textContent !== "กำลังโหลดรายชื่อบริษัท...";
  });
}

async function openCompanyDetail(page: Page) {
  await page.click("[data-screen='s-companies']");
  await page.click("#companiesTableBody button:has-text('⚙️ ตั้งค่า')");
  await expect(page.locator("#s-company-detail")).toBeVisible();
}

function mockEmptyCoa(page: Page) {
  return page.route("**/api/v1/companies/*/coa", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
}

function mockEmptyMappingRules(page: Page) {
  return page.route("**/api/v1/companies/*/mapping-rules", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );
}

test.describe("W4 SIT closure — Chart of Accounts + Mapping Rules real-click flows", () => {
  test("COA tab loads real data from the backend, not the old fixture rows", async ({ page }) => {
    await page.route("**/api/v1/companies/*/coa", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { id: "c1", account_code: "1100", account_name: "Cash Real", account_type: "asset", is_active: true },
        ]),
      })
    );
    mockEmptyMappingRules(page);
    await loginWithMocks(page);
    await openCompanyDetail(page);

    await expect(page.locator("#coaTableBody")).toContainText("Cash Real");
    await expect(page.locator("#coaTableBody")).not.toContainText("เงินสด"); // old hardcoded fixture row is gone
  });

  test("COA YAML/CSV import calls the real API and refreshes the table", async ({ page }) => {
    await page.route("**/api/v1/companies/*/coa", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      }
      return route.continue();
    });
    let imported = false;
    await page.route("**/api/v1/companies/*/coa/import", (route) => {
      imported = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ imported: 1, updated: 0, errors: [] }),
      });
    });
    mockEmptyMappingRules(page);
    await loginWithMocks(page);
    await openCompanyDetail(page);

    await page.click("text=📁 นำเข้า YAML/CSV");
    await expect(page.locator("#modal-import-coa")).toHaveClass(/open/);
    await page.setInputFiles("#coaImportFileInput", {
      name: "coa.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("account_code,account_name,account_type\n1100,Cash,asset\n"),
    });
    await page.click("#coaImportSubmitBtn");

    await expect(page.locator("#modal-import-coa")).not.toHaveClass(/open/);
    expect(imported).toBe(true);
  });

  test("COA PDF AI-extract runs as an async job with visible progress, then an editable review table", async ({ page }) => {
    // W4-SIT-E2E-COA-ASYNC-10: the UI must start a background task and poll
    // for progress instead of holding one long request open (which died at
    // the SIT nginx 120s proxy wall with HTTP 504 on the real sample PDF).
    await page.route("**/api/v1/companies/*/coa", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      }
      return route.continue();
    });
    let confirmCalled = false;
    let syncEndpointCalled = false;
    await page.route("**/api/v1/companies/*/coa/import-pdf", (route) => {
      syncEndpointCalled = true;
      return route.fulfill({ status: 504, contentType: "text/html", body: "<h1>504 Gateway Time-out</h1>" });
    });
    await page.route("**/api/v1/companies/*/coa/import-pdf-async", (route) =>
      route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ task_id: "task-e2e-1", status: "queued" }),
      })
    );
    let statusPolls = 0;
    await page.route("**/api/v1/companies/*/coa/import-pdf-async/*", (route) => {
      statusPolls += 1;
      if (statusPolls === 1) {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ task_id: "task-e2e-1", status: "running", stage: "ocr" }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          task_id: "task-e2e-1",
          status: "succeeded",
          accounts: [{ code: "1100", name: "Cash (AI)", type: "asset", confidence: 88 }],
          company_name_detected: "Metro Electric Co Ltd",
        }),
      });
    });
    await page.route("**/api/v1/companies/*/coa/confirm", (route) => {
      confirmCalled = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ imported: 1, updated: 0, errors: [] }),
      });
    });
    mockEmptyMappingRules(page);
    await loginWithMocks(page);
    await openCompanyDetail(page);

    await page.click("text=📄 นำเข้าจาก PDF (AI)");
    await expect(page.locator("#modal-import-coa-pdf")).toHaveClass(/open/);
    await page.setInputFiles("#coaPdfFileInput", {
      name: "coa.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-fake"),
    });
    await page.click("#coaPdfExtractBtn");

    // Progress state is visible while the background job runs (first poll → OCR stage).
    await expect(page.locator("#coaPdfProgress")).toBeVisible();
    await expect(page.locator("#coaPdfProgressStage")).toContainText("OCR");

    // Second poll (~2.5s later) reports success → review step with editable rows, not yet saved.
    await expect(page.locator("#coaPdfReviewStep")).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("#coaPdfPreviewBody input").first()).toHaveValue("1100");
    expect(confirmCalled).toBe(false);
    expect(statusPolls).toBeGreaterThanOrEqual(2);
    expect(syncEndpointCalled).toBe(false); // the timeout-prone sync route is no longer used

    await page.click("#coaPdfConfirmBtn");
    expect(confirmCalled).toBe(true);
  });

  test("COA PDF async job failure shows a specific error and re-enables the extract button", async ({ page }) => {
    await page.route("**/api/v1/companies/*/coa", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      }
      return route.continue();
    });
    await page.route("**/api/v1/companies/*/coa/import-pdf-async", (route) =>
      route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ task_id: "task-e2e-fail", status: "queued" }),
      })
    );
    await page.route("**/api/v1/companies/*/coa/import-pdf-async/*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          task_id: "task-e2e-fail",
          status: "failed",
          error: "COA PDF yielded no readable text.",
        }),
      })
    );
    mockEmptyMappingRules(page);
    await loginWithMocks(page);
    await openCompanyDetail(page);

    await page.click("text=📄 นำเข้าจาก PDF (AI)");
    await page.setInputFiles("#coaPdfFileInput", {
      name: "coa.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-fake"),
    });
    await page.click("#coaPdfExtractBtn");

    await expect(page.locator("#coaPdfExtractResult")).toBeVisible();
    await expect(page.locator("#coaPdfExtractResult")).toContainText("no readable text");
    await expect(page.locator("#coaPdfReviewStep")).not.toBeVisible();
    await expect(page.locator("#coaPdfExtractBtn")).toBeEnabled();
    await expect(page.locator("#coaPdfProgress")).not.toBeVisible();
  });

  test("Mapping Rules tab loads real data and manual add calls the real API", async ({ page }) => {
    await page.route("**/api/v1/companies/*/mapping-rules", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      }
      if (route.request().method() === "POST") {
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "r1", vendor_name: "OfficeMate", document_type: "Invoice",
            recommended_debit_code: "5100", recommended_account_name: "Office Supplies",
            confirmed_count: 1, last_confirmed_at: "2026-07-05T00:00:00",
          }),
        });
      }
      return route.continue();
    });
    mockEmptyCoa(page);
    await loginWithMocks(page);
    await openCompanyDetail(page);
    await page.locator("#s-company-detail .tab-bar").getByText("ตั้งค่า", { exact: true }).click();

    await page.click("text=+ เพิ่ม Rule");
    await expect(page.locator("#modal-mapping-rule")).toHaveClass(/open/);
    await page.fill("#mappingRuleVendorInput", "OfficeMate");
    await page.fill("#mappingRuleDebitCodeInput", "5100");
    await page.click("#mappingRuleSaveBtn");

    await expect(page.locator("#modal-mapping-rule")).not.toHaveClass(/open/);
  });

  test("Mapping Rules DOCX AI-extract flow shows an editable review table before saving anything", async ({ page }) => {
    await page.route("**/api/v1/companies/*/mapping-rules", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      }
      return route.continue();
    });
    let confirmedRules: unknown[] | null = null;
    await page.route("**/api/v1/companies/*/mapping-rules/import-docx", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          rules: [
            { vendor_name: "OfficeMate", document_type: "Invoice", recommended_debit_code: "5100", recommended_account_name: "Office Supplies" },
            { vendor_name: "Duplicate Vendor", document_type: "Invoice", recommended_debit_code: "5100", recommended_account_name: "Duplicate" },
          ],
          source_text_preview: "extracted text",
        }),
      })
    );
    await page.route("**/api/v1/companies/*/mapping-rules/confirm", (route) => {
      confirmedRules = JSON.parse(route.request().postData() || "{}").rules;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ imported: confirmedRules?.length || 0, updated: 0, errors: [] }),
      });
    });
    mockEmptyCoa(page);
    await loginWithMocks(page);
    await openCompanyDetail(page);
    await page.locator("#s-company-detail .tab-bar").getByText("ตั้งค่า", { exact: true }).click();

    await page.click("text=📁 นำเข้าจาก DOCX (AI)");
    await expect(page.locator("#modal-import-mapping-docx")).toHaveClass(/open/);
    await page.setInputFiles("#mappingDocxFileInput", {
      name: "mapping.docx",
      mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      buffer: Buffer.from("PK\x03\x04fake"),
    });
    await page.click("#mappingDocxExtractBtn");

    await expect(page.locator("#mappingDocxReviewStep")).toBeVisible();
    await expect(page.locator("#mappingDocxPreviewBody input").first()).toHaveValue("OfficeMate");
    await expect(page.locator("#mappingDocxPreviewBody tr")).toHaveCount(2);
    expect(confirmedRules).toBeNull();

    await page.click("#mappingDocxPreviewBody tr:first-child button:has-text('ลบ')");
    await expect(page.locator("#mappingDocxPreviewBody")).not.toContainText("OfficeMate");
    await expect(page.locator("#mappingDocxPreviewBody tr")).toHaveCount(1);

    await page.click("#mappingDocxConfirmBtn");
    expect(confirmedRules).toEqual([
      { vendor_name: "Duplicate Vendor", document_type: "Invoice", recommended_debit_code: "5100", recommended_account_name: "Duplicate" },
    ]);
  });
});
