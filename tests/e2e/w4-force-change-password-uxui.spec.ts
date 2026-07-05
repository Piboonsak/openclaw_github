import { expect, test, type Page } from "@playwright/test";

// This spec verifies uncommitted local edits to main-ux-ui.html directly
// against a throwaway local static server, NOT the repo's default Playwright
// baseURL (which resolves to the live deployed SIT server via POC_URL in
// .env.sit.local) — that would test the last-deployed HTML, not these changes.
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

const FIRST_LOGIN_USER = {
  id: "22222222-2222-2222-2222-222222222222",
  email: "newstaff@ledgerflow.local",
  display_name: "New Staff",
  role: "staff",
  must_change_password: true,
  company_ids: [],
};

async function mockLoginRoute(page: Page, user: Record<string, unknown>) {
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
}

test.describe("W4 SIT closure — forced first-login password change", () => {
  test("user with must_change_password=true is routed to the force-change screen, not the app", async ({ page }) => {
    await mockLoginRoute(page, FIRST_LOGIN_USER);
    await gotoWithRetry(page, "/main-ux-ui.html");

    await page.fill("#loginUser", "newstaff");
    await page.fill("#loginPw", "temp-password");
    await page.click("#loginForm button[type=submit]");

    await expect(page.locator("#force-change-password-screen")).toBeVisible();
    await expect(page.locator("#app")).not.toHaveClass(/visible/);
    // No dismiss control — this is enforcement, not a nag banner.
    await expect(page.locator("#force-change-password-screen button:has-text('×')")).toHaveCount(0);
  });

  test("submitting a mismatched confirmation shows an inline error and does not call the API", async ({ page }) => {
    await mockLoginRoute(page, FIRST_LOGIN_USER);
    let changeCalled = false;
    await page.route("**/api/v1/auth/change-password", (route) => {
      changeCalled = true;
      return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });
    await gotoWithRetry(page, "/main-ux-ui.html");
    await page.fill("#loginUser", "newstaff");
    await page.fill("#loginPw", "temp-password");
    await page.click("#loginForm button[type=submit]");
    await expect(page.locator("#force-change-password-screen")).toBeVisible();

    await page.fill("#forceChangeOldPw", "temp-password");
    await page.fill("#forceChangeNewPw", "NewPass1234");
    await page.fill("#forceChangeConfirmPw", "DoesNotMatch1");
    await page.click("#forceChangePasswordForm button[type=submit]");

    await expect(page.locator("#forceChangePasswordError")).toBeVisible();
    expect(changeCalled).toBe(false);
  });

  test("successful password change reveals the app shell", async ({ page }) => {
    // Mutable so /auth/me reflects the post-change state on any follow-up
    // call, same as a real backend would once must_change_password flips.
    let currentUser: Record<string, unknown> = { ...FIRST_LOGIN_USER };
    await page.route("**/api/v1/auth/login", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ access_token: "fake-token", user: currentUser }),
      })
    );
    await page.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(currentUser) })
    );
    await page.route("**/api/v1/auth/change-password", (route) => {
      currentUser = { ...currentUser, must_change_password: false };
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", user: currentUser }),
      });
    });
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
    await page.fill("#loginUser", "newstaff");
    await page.fill("#loginPw", "temp-password");
    await page.click("#loginForm button[type=submit]");
    await expect(page.locator("#force-change-password-screen")).toBeVisible();

    await page.fill("#forceChangeOldPw", "temp-password");
    await page.fill("#forceChangeNewPw", "NewPass1234");
    await page.fill("#forceChangeConfirmPw", "NewPass1234");
    await page.click("#forceChangePasswordForm button[type=submit]");

    await expect(page.locator("#app")).toHaveClass(/visible/);
    await expect(page.locator("#force-change-password-screen")).not.toBeVisible();
  });

  test("user without must_change_password goes straight to the app", async ({ page }) => {
    const normalUser = { ...FIRST_LOGIN_USER, must_change_password: false };
    await mockLoginRoute(page, normalUser);
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
    await page.fill("#loginUser", "admin");
    await page.fill("#loginPw", "admin");
    await page.click("#loginForm button[type=submit]");

    await expect(page.locator("#app")).toHaveClass(/visible/);
    await expect(page.locator("#force-change-password-screen")).not.toBeVisible();
  });
});
