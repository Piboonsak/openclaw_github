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
  name: "Metro Electric Co Ltd",
  tax_id: "0105560123456",
  branch_code: "00000",
  address: null,
  business_type: "retail",
  is_active: true,
};

async function loginAndOpenDetail(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FAKE_USER) })
  );
  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.route("**/api/v1/admin/companies", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([COMPANY_A]) })
  );
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.route("**/api/v1/companies/*/vendor-master", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 50, search: null }) })
  );
  await page.route("**/api/v1/companies/*/customer-master", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 50, search: null }) })
  );
  await page.route("**/api/v1/companies/*/coa", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.route("**/api/v1/companies/*/mapping-rules", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );

  await page.addInitScript(() => {
    window.localStorage.setItem("lf_token", "fake-test-token");
  });
  await gotoWithRetry(page, "/main-ux-ui.html");
  await page.waitForFunction(() => {
    const el = document.getElementById("companiesStatus");
    return !!el && el.textContent !== "กำลังโหลดรายชื่อบริษัท...";
  });
  await page.click("[data-screen='s-companies']");
  await page.click("#companiesTableBody button:has-text('⚙️ ตั้งค่า')");
  await expect(page.locator("#s-company-detail")).toBeVisible();
  await page.locator("#s-company-detail .tab-bar").getByText("สินค้า/ราคา", { exact: true }).click();
}

test.describe("W4 SIT closure — Product/price-list master (Pack C)", () => {
  test("Products tab loads real data from the backend", async ({ page }) => {
    await page.route("**/api/v1/companies/*/product-master", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [{ code: "118-P15-R", name: "2x4", unit: "PCS.", unit_cost: 1.6008, category: "BOX", is_active: true }],
          total: 1,
          page: 1,
          page_size: 50,
          search: null,
        }),
      })
    );
    await loginAndOpenDetail(page);

    await expect(page.locator("#productMasterTableBody")).toContainText("118-P15-R");
    await expect(page.locator("#productMasterTableBody")).toContainText("BOX");
  });

  test("CSV import calls the real API and refreshes the table", async ({ page }) => {
    await page.route("**/api/v1/companies/*/product-master", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 50, search: null }),
        });
      }
      return route.continue();
    });
    let imported = false;
    await page.route("**/api/v1/companies/*/product-master/import", (route) => {
      imported = true;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ imported: 1, updated: 0, errors: [] }),
      });
    });
    await loginAndOpenDetail(page);

    await page.click("text=📁 นำเข้า Product/Price List CSV");
    await expect(page.locator("#modal-import-product")).toHaveClass(/open/);
    await page.setInputFiles("#productImportFileInput", {
      name: "products.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("product_code,product_name,unit,unit_cost,category\nP001,Widget,EA,12.5,Widgets\n"),
    });
    await page.click("#productImportSubmitBtn");

    await expect(page.locator("#modal-import-product")).not.toHaveClass(/open/);
    expect(imported).toBe(true);
  });
});
