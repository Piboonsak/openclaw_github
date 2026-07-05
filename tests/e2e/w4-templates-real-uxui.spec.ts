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

const MASTER_TEMPLATE = {
  id: "tmpl-master-1",
  template_name: "Express GL",
  template_type: "gl_ledger",
  company_id: null,
  columns: [{ source_field: "voucher_no", header_label: "Voucher" }, { source_field: "date", header_label: "Date" }],
  file_format: "csv",
  encoding: "utf-8",
  delimiter: ",",
  is_master: true,
  is_active: true,
  cloned_from: null,
};

const COMPANY_TEMPLATE = {
  id: "tmpl-company-1",
  template_name: "GL Metro Electric",
  template_type: "gl_ledger",
  company_id: COMPANY_A.id,
  columns: [{ source_field: "voucher_no", header_label: "Voucher" }],
  file_format: "csv",
  encoding: "utf-8",
  delimiter: ",",
  is_master: false,
  is_active: true,
  cloned_from: "tmpl-master-1",
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
}

async function loginAndGoToTemplates(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("lf_token", "fake-test-token");
  });
  await gotoWithRetry(page, "/main-ux-ui.html");
  await page.waitForFunction(() => {
    const el = document.getElementById("companiesStatus");
    return !!el && el.textContent !== "กำลังโหลดรายชื่อบริษัท...";
  });
  await page.click("[data-screen='s-templates']");
  await expect(page.locator("#s-templates")).toBeVisible();
}

test.describe("W4 SIT closure — real company-scoped Templates UI (Pack C)", () => {
  test("Master Templates tab loads real data, not the old fixture cards", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/templates**", (route) => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MASTER_TEMPLATE]) });
      }
      return route.continue();
    });
    await loginAndGoToTemplates(page);

    await expect(page.locator("#tmplMasterCardsBody")).toContainText("Express GL");
    await expect(page.locator("#tmplMasterCardsBody")).not.toContainText("ภ.พ.30 ภาษีซื้อ"); // old hardcoded fixture card is gone
    await expect(page.locator("#tmplMasterCount")).toHaveText("1");
  });

  test("selecting a company loads its real templates into the Templates-บริษัท tab", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/templates**", (route) => {
      const url = route.request().url();
      if (route.request().method() !== "GET") return route.continue();
      if (url.includes("company_id=")) {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MASTER_TEMPLATE, COMPANY_TEMPLATE]) });
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MASTER_TEMPLATE]) });
    });
    await loginAndGoToTemplates(page);

    await page.selectOption("#templatesCompanySelect", COMPANY_A.id);
    await page.waitForTimeout(300);
    await page.click("button:has-text('Templates บริษัท')");

    await expect(page.locator("#tmplCompanyCardsBody")).toContainText("GL Metro Electric");
    await expect(page.locator("#tmplCompanyCardsBody")).toContainText("Clone of Express GL");
    await expect(page.locator("#tmplCompanyCount")).toHaveText("1");
  });

  test("Clone to Company calls the real clone API and opens the cloned template's editor (TC-RWG04-07)", async ({ page }) => {
    await baseMocks(page);
    await page.route("**/api/v1/templates**", (route) => {
      const url = route.request().url();
      if (route.request().method() !== "GET") return route.continue();
      if (url.includes("company_id=")) {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MASTER_TEMPLATE, COMPANY_TEMPLATE]) });
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MASTER_TEMPLATE]) });
    });
    let cloneCalled = false;
    await page.route("**/api/v1/templates/tmpl-master-1/clone", (route) => {
      cloneCalled = true;
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(COMPANY_TEMPLATE) });
    });
    await loginAndGoToTemplates(page);

    await page.click("button:has-text('Clone to Company')");
    await expect(page.locator("#modal-clone-template")).toHaveClass(/open/);
    await page.selectOption("#cloneTemplateCompanySelect", COMPANY_A.id);
    await page.fill("#cloneTemplateNameInput", "GL Metro Electric");
    await page.click("#cloneTemplateSubmitBtn");

    await expect(page.locator("#modal-clone-template")).not.toHaveClass(/open/);
    expect(cloneCalled).toBe(true);
    // TC-RWG04-07: after clone, the UI must redirect into the cloned company template's editor, not just refresh the list.
    await expect(page.locator("#s-template-configurator")).toBeVisible();
    await expect(page.locator("#toastContainer")).toContainText("GL Metro Electric");
  });

  test("Delete on a company template calls the real DELETE API", async ({ page }) => {
    await baseMocks(page);
    let deleteCalled = false;
    await page.route("**/api/v1/templates**", (route) => {
      const url = route.request().url();
      const method = route.request().method();
      if (method === "DELETE" && url.endsWith("/tmpl-company-1")) {
        deleteCalled = true;
        return route.fulfill({ status: 204 });
      }
      if (method !== "GET") return route.continue();
      if (url.includes("company_id=")) {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MASTER_TEMPLATE, COMPANY_TEMPLATE]) });
      }
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([MASTER_TEMPLATE]) });
    });
    await loginAndGoToTemplates(page);
    await page.selectOption("#templatesCompanySelect", COMPANY_A.id);
    await page.waitForTimeout(300);
    await page.click("button:has-text('Templates บริษัท')");

    await page.click("#tmplCompanyCardsBody button:has-text('🗑')");
    await expect(page.locator("#modal-confirm")).toHaveClass(/open/);
    var deleteResponse = page.waitForResponse((r) => r.url().includes("/templates/tmpl-company-1") && r.request().method() === "DELETE");
    await page.click("#confirmOkBtn");
    await deleteResponse;

    expect(deleteCalled).toBe(true);
  });
});
