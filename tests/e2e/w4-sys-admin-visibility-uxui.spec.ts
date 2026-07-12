import { expect, test, type Page } from "@playwright/test";

// Verifies uncommitted local edits directly against a throwaway local static
// server — see w4-coa-mapping-rules-uxui.spec.ts for why (the repo's default
// Playwright baseURL resolves to the live deployed SIT server).
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

function userFor(role: string) {
  return {
    id: "33333333-3333-3333-3333-333333333333",
    email: `${role}@ledgerflow.local`,
    display_name: role,
    role,
    must_change_password: false,
    company_ids: [],
  };
}

async function loginAs(page: Page, role: string, opts: { companies?: unknown[] } = {}) {
  const user = userFor(role);
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ access_token: "fake-token", user }),
    })
  );
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) })
  );
  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.route("**/api/v1/admin/companies", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(opts.companies ?? []),
    })
  );
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await gotoWithRetry(page, "/main-ux-ui.html");
  await page.fill("#loginUser", role);
  await page.fill("#loginPw", "whatever");
  await page.click("#loginForm button[type=submit]");
  await expect(page.locator("#app")).toHaveClass(/visible/);
}

const SAMPLE_COMPANY = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    name: "บริษัท ทดสอบ จำกัด",
    tax_id: "0105560123456",
    branch_code: "00000",
    is_active: true,
    settings: {},
  },
];

test.describe("W4 SIT closure — role-aware UI visibility (TASK-1204 3-role model)", () => {
  test("staff sees neither Users nav, Internal Console, nor the create-company button", async ({ page }) => {
    await loginAs(page, "staff");
    await expect(page.locator("#usersNavItem")).toBeHidden();
    await expect(page.locator("#internalConsoleTopbarBtn")).toBeHidden();
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#createCompanyBtn")).toBeHidden();
  });

  test("admin sees Users nav but not Internal Console or the create-company button", async ({ page }) => {
    await loginAs(page, "admin");
    await expect(page.locator("#usersNavItem")).toBeVisible();
    await expect(page.locator("#internalConsoleTopbarBtn")).toBeHidden();
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#createCompanyBtn")).toBeHidden();
  });

  test("sys_admin sees Users nav, Internal Console, and the create-company button", async ({ page }) => {
    await loginAs(page, "sys_admin");
    await expect(page.locator("#usersNavItem")).toBeVisible();
    await expect(page.locator("#internalConsoleTopbarBtn")).toBeVisible();
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#createCompanyBtn")).toBeVisible();
  });

  test("only sys_admin sees the SysAdmin role option in the user-create drawer", async ({ page }) => {
    await loginAs(page, "admin");
    await expect(page.locator("#userRoleSysAdminOption")).toBeHidden();
  });

  test("sys_admin can reach the Internal Console screen", async ({ page }) => {
    await loginAs(page, "sys_admin");
    await page.click("#internalConsoleTopbarBtn");
    await expect(page.locator("#s-system-home")).toBeVisible();
  });

  // HR-07-03: company soft-delete is sys_admin-only. The reviewer path must see
  // it (true sys_admin), and admin/staff must not — a permission-sensitive UI
  // regression that CI should catch.
  test("sys_admin sees the company delete (ลบ) action in the companies table", async ({ page }) => {
    await loginAs(page, "sys_admin", { companies: SAMPLE_COMPANY });
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#companiesTableBody")).toContainText("บริษัท ทดสอบ จำกัด");
    await expect(page.locator("#companiesTableBody .btn-danger")).toBeVisible();
  });

  test("admin does NOT see the company delete action", async ({ page }) => {
    await loginAs(page, "admin", { companies: SAMPLE_COMPANY });
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#companiesTableBody")).toContainText("บริษัท ทดสอบ จำกัด");
    await expect(page.locator("#companiesTableBody .btn-danger")).toHaveCount(0);
  });

  test("staff does NOT see the company delete action", async ({ page }) => {
    await loginAs(page, "staff", { companies: SAMPLE_COMPANY });
    await page.click("[data-screen='s-companies']");
    await expect(page.locator("#companiesTableBody .btn-danger")).toHaveCount(0);
  });

  // HR-07-06: the Template Configurator blank state must not carry demo template
  // names / runtime content ("GL เมโทร อีเล็กทริค — Clone of Express GL").
  test("Template Configurator blank state shows no demo template content", async ({ page }) => {
    await loginAs(page, "sys_admin");
    await page.evaluate(() => (window as unknown as { showScreen: (id: string) => void }).showScreen("s-template-configurator"));
    const screen = page.locator("#s-template-configurator");
    await expect(screen).not.toContainText("Clone of Express GL");
    await expect(screen).not.toContainText("เมโทร");
    await expect(page.locator("#configuratorSubtitle")).toContainText("ยังไม่ได้เลือก template");
  });
});
