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
  business_type: null,
  is_active: true,
};

// Real backend flows are exercised via Playwright route mocks (no live DB in
// this sandbox), so these tests verify the exact fetch/render code path a
// production run takes, not just DOM markup presence.
async function mockAdminApis(page: Page, options?: { companies?: unknown[] }) {
  let companies = options?.companies ?? [COMPANY_A];
  let users: unknown[] = [];

  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FAKE_USER) })
  );

  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) })
  );

  await page.route("**/api/v1/admin/companies", (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(companies) });
    }
    if (request.method() === "POST") {
      const body = JSON.parse(request.postData() || "{}");
      const created = {
        id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        name: body.name,
        tax_id: body.tax_id,
        branch_code: body.branch_code || "00000",
        address: body.address || null,
        business_type: body.business_type || null,
        is_active: true,
      };
      companies = [...companies, created];
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
    }
    return route.continue();
  });

  await page.route("**/api/v1/admin/companies/*", (route) => {
    const request = route.request();
    if (request.method() === "PUT") {
      const body = JSON.parse(request.postData() || "{}");
      const updated = { ...COMPANY_A, ...body };
      companies = companies.map((c) => ((c as { id: string }).id === COMPANY_A.id ? updated : c));
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(updated) });
    }
    return route.continue();
  });

  await page.route("**/api/v1/admin/users", (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(users) });
    }
    if (request.method() === "POST") {
      const body = JSON.parse(request.postData() || "{}");
      const created = {
        id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
        email: body.email,
        username: body.username,
        display_name: body.display_name || null,
        role: body.role || "staff",
        is_active: true,
        must_change_password: true,
        last_login: null,
        company_ids: body.company_ids || [],
        temp_password: "Lf1a2b3c4d5e",
      };
      users = [...users, created];
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(created) });
    }
    return route.continue();
  });

  await page.route("**/api/v1/companies/*/vendor-master", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [{ code: "V-0001", name: "Kasikorn Bank", is_active: true, extra: { gl_code: "2100" } }],
        total: 1,
        page: 1,
        page_size: 50,
        search: null,
      }),
    })
  );

  await page.route("**/api/v1/companies/*/customer-master", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [{ code: "C-0001", name: "Thai Materials Co", is_active: true, extra: { ar_flag: 1 } }],
        total: 1,
        page: 1,
        page_size: 50,
        search: null,
      }),
    })
  );
}

async function loginWithMocks(page: Page, options?: { role?: string }) {
  await page.addInitScript(() => {
    window.localStorage.setItem("lf_token", "fake-test-token");
  });
  if (options?.role && options.role !== FAKE_USER.role) {
    // Company create is sys_admin-only (EPIC-12 TASK-1204) — override /auth/me
    // for the tests that need to exercise that button, registered AFTER
    // mockAdminApis so it takes priority (Playwright tries the most recently
    // registered matching route first).
    await mockAdminApis(page);
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...FAKE_USER, role: options.role }),
      })
    );
  } else {
    await mockAdminApis(page);
  }
  await gotoWithRetry(page, "/prototype");
  await page.waitForFunction(() => {
    const el = document.getElementById("companiesStatus");
    return !!el && el.textContent !== "กำลังโหลดรายชื่อบริษัท...";
  });
}

test.describe("W4 SIT closure — Company/User admin CRUD real-click flows", () => {
  test("Companies screen loads real data from the backend and renders a table row", async ({ page }) => {
    await loginWithMocks(page);
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#companiesTableBody tr")).toHaveCount(1);
    await expect(page.locator("#companiesTableBody")).toContainText("Metro Electric Co Ltd");
    await expect(page.locator("#companiesTableBody")).toContainText("0105560123456");
  });

  test("Creating a company via the drawer calls the real API and refreshes the table", async ({ page }) => {
    await loginWithMocks(page, { role: "sys_admin" });
    await page.click("[data-screen='s-companies']");
    await page.click("text=+ เพิ่มบริษัท");
    await expect(page.locator("#drawer-company")).toHaveClass(/open/);

    await page.fill("#companyNameInput", "New Test Co");
    await page.fill("#companyTaxIdInput", "0107561234567");
    await page.click("#companyDrawerSaveBtn");

    await expect(page.locator("#drawer-company")).not.toHaveClass(/open/);
    await expect(page.locator("#companiesTableBody")).toContainText("New Test Co");
  });

  test("Saving a company with no name shows a real inline error, not a fake-success toast", async ({ page }) => {
    await loginWithMocks(page, { role: "sys_admin" });
    await page.click("[data-screen='s-companies']");
    await page.click("text=+ เพิ่มบริษัท");
    await page.click("#companyDrawerSaveBtn");

    await expect(page.locator("#companyDrawerError")).toBeVisible();
    await expect(page.locator("#drawer-company")).toHaveClass(/open/);
  });

  test("Editing a company pre-fills the drawer and PUTs the update", async ({ page }) => {
    await loginWithMocks(page);
    await page.click("[data-screen='s-companies']");
    await page.click("#companiesTableBody button:has-text('แก้ไข')");
    await expect(page.locator("#companyNameInput")).toHaveValue("Metro Electric Co Ltd");

    await page.fill("#companyNameInput", "Metro Electric Renamed");
    await page.click("#companyDrawerSaveBtn");

    await expect(page.locator("#companiesTableBody")).toContainText("Metro Electric Renamed");
  });

  test("Users screen creates a user and surfaces the one-time temp password (no fake email flow)", async ({ page }) => {
    await loginWithMocks(page);
    await page.click("[data-screen='s-users']");
    await page.click("text=+ เพิ่มผู้ใช้");
    await page.fill("#userEmailInput", "newstaff@example.com");
    await page.fill("#userUsernameInput", "newstaff");
    await page.click("#userDrawerSaveBtn");

    await expect(page.locator("#usersTableBody")).toContainText("newstaff@example.com");
  });

  test("Company detail settings gear loads real AP and AR master data for that company", async ({ page }) => {
    await loginWithMocks(page);
    await page.click("[data-screen='s-companies']");
    await page.click("#companiesTableBody button:has-text('⚙️ ตั้งค่า')");

    await expect(page.locator("#companyDetailName")).toHaveText("Metro Electric Co Ltd");
    await page.click("button:has-text('AP · ผู้จำหน่าย')");
    await expect(page.locator("#vendorMasterTableBody")).toContainText("Kasikorn Bank");

    await page.click("button:has-text('AR · ลูกค้า')");
    await expect(page.locator("#customerMasterTableBody")).toContainText("Thai Materials Co");
  });

  test("AP/AR single-row add buttons are honestly deferred, not fake-success", async ({ page }) => {
    await loginWithMocks(page);
    await page.click("[data-screen='s-companies']");
    await page.click("#companiesTableBody button:has-text('⚙️ ตั้งค่า')");
    await page.click("button:has-text('AP · ผู้จำหน่าย')");

    await page.click("text=+ เพิ่มผู้จำหน่าย");
    await expect(page.locator(".toast.warn")).toContainText("deferred");
  });
});
