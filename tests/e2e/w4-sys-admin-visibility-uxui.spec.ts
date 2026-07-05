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

async function loginAs(page: Page, role: string) {
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
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
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
});
