import { expect, test, type Page } from "@playwright/test";

// W4-SIT-E2E-PRODUCT-SHELL-FOLLOWUP-22 — verifies uncommitted local edits
// directly against the throwaway local static server (the repo's default
// Playwright baseURL resolves to the deployed SIT site, which does NOT yet have
// these changes). Same convention as w4-company-context-uxui.spec.ts.
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

const COMPANY_A = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  name: "บริษัท ฤทธิ์ล้ำเลิศ จำกัด",
  tax_id: "0125561025189",
  branch_code: "00000",
  address: null,
  business_type: "trading",
  settings: {},
  is_active: true,
};

// Second company has the line-item / stock scan toggle enabled.
const COMPANY_B = {
  id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  name: "บริษัท กรีน ซัพพลาย จำกัด",
  tax_id: "0105559000002",
  branch_code: "00000",
  address: null,
  business_type: "service",
  settings: { enable_stock: true },
  is_active: true,
};

function userFor(role: string) {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    email: `${role}@ledgerflow.local`,
    display_name: role,
    role,
    must_change_password: false,
    company_ids: [COMPANY_A.id, COMPANY_B.id],
  };
}

async function mockCore(page: Page, opts: { role?: string; companies?: any[] } = {}) {
  const role = opts.role || "sys_admin";
  let companies = opts.companies ? [...opts.companies] : [{ ...COMPANY_A }, { ...COMPANY_B }];

  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(userFor(role)) })
  );
  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.route("**/api/v1/admin/companies", (route) => {
    const req = route.request();
    if (req.method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(companies) });
    }
    if (req.method() === "POST") {
      const body = JSON.parse(req.postData() || "{}");
      const created = {
        id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
        name: body.name,
        tax_id: body.tax_id,
        branch_code: body.branch_code || "00000",
        address: body.address || null,
        business_type: body.business_type || null,
        settings: body.settings || {},
        is_active: true,
      };
      companies = [...companies, created];
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
    }
    return route.continue();
  });
  await page.route("**/api/v1/admin/companies/*", (route) => {
    const req = route.request();
    if (req.method() === "DELETE") {
      companies = companies.filter((c) => !req.url().includes(c.id));
      return route.fulfill({ status: 204, contentType: "application/json", body: "" });
    }
    if (req.method() === "PUT") {
      const body = JSON.parse(req.postData() || "{}");
      const target = companies.find((c) => req.url().includes(c.id)) || companies[0];
      const updated = { ...target, ...body, settings: { ...(target.settings || {}), ...(body.settings || {}) } };
      companies = companies.map((c) => (c.id === target.id ? updated : c));
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(updated) });
    }
    return route.continue();
  });
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

test.describe("FOLLOWUP-22 — HR-18 company stock toggle + create/delete controls", () => {
  test("stock/line-item toggle round-trips through Company.settings on create + edit reload", async ({ page }) => {
    await mockCore(page, { role: "sys_admin", companies: [{ ...COMPANY_A }] });
    await login(page);
    await page.click("[data-screen='s-companies']");
    await page.click("text=+ เพิ่มบริษัท");
    await expect(page.locator("#drawer-company")).toHaveClass(/open/);
    await page.fill("#companyNameInput", "Stock Co");
    await page.fill("#companyTaxIdInput", "0107561234567");
    await page.check("#companyEnableStockInput");
    await page.click("#companyDrawerSaveBtn");

    await expect(page.locator("#companiesTableBody")).toContainText("Stock Co");
    await page.click("#companiesTableBody tr:has-text('Stock Co') button:has-text('แก้ไข')");
    // The persisted enable_stock must re-populate the checkbox, not reset it.
    await expect(page.locator("#companyEnableStockInput")).toBeChecked();
  });

  test("editing an existing company with enable_stock=true shows the toggle checked", async ({ page }) => {
    await mockCore(page, { role: "sys_admin" });
    await login(page);
    await page.click("[data-screen='s-companies']");
    await page.click("#companiesTableBody tr:has-text('กรีน ซัพพลาย') button:has-text('แก้ไข')");
    await expect(page.locator("#companyEnableStockInput")).toBeChecked();
  });

  test("company delete control is hidden for admin (delete is sys_admin-only)", async ({ page }) => {
    await mockCore(page, { role: "admin" });
    await login(page);
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#companiesTableBody")).toContainText("ฤทธิ์ล้ำเลิศ");
    await expect(page.locator("#companiesTableBody button:has-text('ลบ')")).toHaveCount(0);
  });

  test("sys_admin can delete a company via the real DELETE API and the row disappears", async ({ page }) => {
    await mockCore(page, { role: "sys_admin", companies: [{ ...COMPANY_A }] });
    await login(page);
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#companiesTableBody button:has-text('ลบ')")).toHaveCount(1);

    page.on("dialog", (dialog) => dialog.accept());
    const deleteResponse = page.waitForResponse(
      (r) => r.request().method() === "DELETE" && r.url().includes("/api/v1/admin/companies/")
    );
    await page.click("#companiesTableBody button:has-text('ลบ')");
    await deleteResponse;
    await expect(page.locator("#companiesTableBody")).not.toContainText("ฤทธิ์ล้ำเลิศ");
  });
});

test.describe("FOLLOWUP-22 — HR-20 Internal Console reachability for sys_admin", () => {
  test("sys_admin sees the Internal Console sidebar nav item and can reach the screen", async ({ page }) => {
    await mockCore(page, { role: "sys_admin" });
    await login(page);
    await expect(page.locator("#internalConsoleNavItem")).toBeVisible();
    await page.click("#internalConsoleNavItem");
    await expect(page.locator("#s-system-home")).toBeVisible();
  });

  test("admin does not see the Internal Console sidebar nav item", async ({ page }) => {
    await mockCore(page, { role: "admin" });
    await login(page);
    await expect(page.locator("#internalConsoleNavItem")).toBeHidden();
  });

  test("Settings Model Router loads live routing from the real GET /v1/llm/routing", async ({ page }) => {
    await mockCore(page, { role: "sys_admin" });
    await page.route("**/api/v1/llm/routing**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          routing: {
            provider_preference: "openrouter",
            default_model: "google/gemini-2.5-flash",
            escalation_model: "anthropic/claude-sonnet-4",
            free_models: ["google/gemini-2.5-flash:free"],
            backup_models: ["openai/gpt-4o-mini"],
            free_conf_threshold: 0.7,
          },
          recent_cost_events: [],
        }),
      })
    );
    await login(page);
    await page.click("#internalConsoleNavItem");
    await page.click("text=เปิด Settings");
    await expect(page.locator("#llmRoutingLive")).toContainText("openrouter");
    await expect(page.locator("#llmRoutingLive")).toContainText("anthropic/claude-sonnet-4");
  });
});

test.describe("FOLLOWUP-22 — HR-19 Processing line-item branch by company config", () => {
  async function mockDocs(page: Page) {
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
    );
  }

  test("line-item notice is shown when the selected company has enable_stock on", async ({ page }) => {
    await mockCore(page, { role: "sys_admin" });
    await mockDocs(page);
    await login(page);
    // Select company B (enable_stock: true) in the topbar, then open Processing.
    await page.selectOption("#topbarCompanySelect", COMPANY_B.id);
    await page.click("[data-screen='s-processing']");
    await expect(page.locator("#processingLineItemNotice")).toBeVisible();
  });

  test("line-item notice is hidden for a company with the toggle off (header-only mode)", async ({ page }) => {
    await mockCore(page, { role: "sys_admin" });
    await mockDocs(page);
    await login(page);
    await page.selectOption("#topbarCompanySelect", COMPANY_A.id);
    await page.click("[data-screen='s-processing']");
    await expect(page.locator("#processingLineItemNotice")).toBeHidden();
  });
});

test.describe("FOLLOWUP-22 — HR-17 Review Mapping filename-first labels", () => {
  const DOC_APPROVED = {
    id: "doc-9",
    filename: "03062026130503.pdf",
    original_filename: "03062026130503.pdf",
    status: "scan_approved",
    scan_status: "approved",
    content_type: "application/pdf",
    created_at: "2026-07-05T10:00:00Z",
    invoice_number: "INV-777",
    seller_name: "Vendor Co Ltd",
    net_amount: 1000,
    vat_amount: 70,
    total_amount: 1070,
    overall_confidence: 0.9,
  };
  const VOUCHER = {
    id: "voucher-9",
    voucher_no: null,
    voucher_date: "2026-07-01",
    book_code: "PV",
    status: "draft",
    is_balanced: true,
    total_debit: 1070,
    total_credit: 1070,
    flags: [],
    lines: [
      { id: "l1", line_order: 1, account_code: "5040", account_name: "ค่าใช้จ่าย", is_debit: true, amount: 1070, description: null },
      { id: "l2", line_order: 2, account_code: "2195", account_name: "เจ้าหนี้การค้า", is_debit: false, amount: 1070, description: null },
    ],
  };

  test("Review Mapping list and detail use the filename as the primary label, not invoice_number", async ({ page }) => {
    await mockCore(page, { role: "sys_admin", companies: [{ ...COMPANY_A }] });
    await page.route("**/api/v1/companies/*/documents", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([DOC_APPROVED]) })
    );
    await page.route("**/api/v1/documents/doc-9", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...DOC_APPROVED, extraction_fields: {}, confidence_per_field: {}, critical_flags: {}, voucher: VOUCHER }),
      })
    );
    await login(page);
    await page.click("[data-screen='s-review-mapping']");

    // List primary label is the filename.
    await expect(page.locator("#reviewMappingListBody")).toContainText("03062026130503.pdf");
    await page.click("#reviewMappingListBody li");
    // Detail header primary is the filename; invoice number is secondary metadata.
    await expect(page.locator("#reviewMappingDetail h3")).toHaveText("03062026130503.pdf");
    await expect(page.locator("#reviewMappingDetail")).toContainText("INV-777");
  });
});
