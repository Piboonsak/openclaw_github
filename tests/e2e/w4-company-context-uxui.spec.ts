import { expect, test, type Page } from "@playwright/test";

// W4-SIT-E2E-COMPANY-CONTEXT-13 (HR-01): the production shell must have ONE
// database-backed selected-company source of truth. The topbar selector, the
// Upload/Templates selects, and every company-scoped API call must all read the
// same state.currentCompanyId. These tests exercise the local file on disk via
// the throwaway static server (see scratch/localweb), not the deployed SIT HTML.
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
  is_active: true,
};

const COMPANY_B = {
  id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  name: "บริษัท กรีน ซัพพลาย จำกัด",
  tax_id: "0105559000002",
  branch_code: "00000",
  address: null,
  business_type: "service",
  is_active: true,
};

const FAKE_USER = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "admin@ledgerflow.local",
  display_name: "SIT Admin",
  role: "admin",
  must_change_password: false,
  company_ids: [COMPANY_A.id, COMPANY_B.id],
};

async function baseMocks(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FAKE_USER) })
  );
  await page.route("**/api/v1/admin/companies", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([COMPANY_A, COMPANY_B]) })
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
  // Company list finished loading -> topbar select is populated.
  await page.waitForFunction(() => {
    const el = document.getElementById("companiesStatus");
    return !!el && el.textContent !== "กำลังโหลดรายชื่อบริษัท...";
  });
  await page.waitForFunction(
    (expected) => {
      const sel = document.getElementById("topbarCompanySelect") as HTMLSelectElement | null;
      return !!sel && sel.options.length >= expected;
    },
    3 // placeholder + A + B
  );
}

test.describe("W4 SIT closure — one selected-company source of truth (HR-01)", () => {
  test("topbar company options come from the API, not the old hardcoded fixture array", async ({ page }) => {
    await baseMocks(page);
    await login(page);

    const options = await page.locator("#topbarCompanySelect option").allTextContents();
    expect(options).toContain(COMPANY_A.name);
    expect(options).toContain(COMPANY_B.name);
    // The legacy hardcoded cycle array is gone.
    expect(options.join("|")).not.toContain("ห้างหุ้นส่วนจำกัด ซันชายน์");
    expect(options.join("|")).not.toContain("บ. ธนาสิน โฮลดิ้ง จำกัด");

    // Seeded to the user's primary company on load.
    await expect(page.locator("#topbarCompanySelect")).toHaveValue(COMPANY_A.id);
  });

  test("selecting a company in the topbar updates the Upload company selector", async ({ page }) => {
    await baseMocks(page);
    await login(page);

    await page.selectOption("#topbarCompanySelect", COMPANY_B.id);
    await page.click("[data-screen='s-upload']");

    await expect(page.locator("#uploadCompanySelect")).toHaveValue(COMPANY_B.id);
  });

  test("selecting a company in Upload updates the topbar selector", async ({ page }) => {
    await baseMocks(page);
    await login(page);

    await page.click("[data-screen='s-upload']");
    await page.selectOption("#uploadCompanySelect", COMPANY_B.id);

    await expect(page.locator("#topbarCompanySelect")).toHaveValue(COMPANY_B.id);
  });

  test("document-list query uses the company id selected in the topbar, not the primary", async ({ page }) => {
    await baseMocks(page);
    // Resolve the captured company id from inside the route handler so the
    // assertion synchronizes on the actual interception (avoids racing a
    // separate waitForRequest listener against the capture).
    let resolveDocsCompanyId: (id: string) => void = () => {};
    const firstDocsCompanyId = new Promise<string>((resolve) => {
      resolveDocsCompanyId = resolve;
    });
    await page.route("**/api/v1/companies/*/documents", (route) => {
      const match = route.request().url().match(/companies\/([^/]+)\/documents/);
      if (match) resolveDocsCompanyId(match[1]);
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });
    await login(page);

    // Switch away from the primary company (A) to B in the topbar, then open
    // Processing. The first (and only) document-list fetch must target B.
    await page.selectOption("#topbarCompanySelect", COMPANY_B.id);
    await page.click("[data-screen='s-processing']");

    const companyId = await firstDocsCompanyId;
    expect(companyId).toBe(COMPANY_B.id);
  });
});

// W4-SIT-E2E-COMPANY-CONTEXT-FOLLOWUP-14 (Codex P1): admin/sys_admin users see
// EVERY active company from /api/v1/admin/companies — a superset of their
// personal auth/me.company_ids. Selecting one of those "not personally
// assigned" companies must survive requireLiveAuth() (which runs on every live
// action). Here the admin is assigned only to A but can list A and B; selecting
// B must not snap back to A on the next API action.
const ADMIN_ASSIGNED_A_ONLY = {
  ...FAKE_USER,
  company_ids: [COMPANY_A.id],
};

async function adminSeesBothMocks(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ADMIN_ASSIGNED_A_ONLY) })
  );
  await page.route("**/api/v1/admin/companies", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([COMPANY_A, COMPANY_B]) })
  );
  await page.route("**/api/v1/admin/users", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.route("**/api/v1/templates**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
}

test.describe("W4 SIT closure — admin selection persistence beyond auth/me.company_ids (FOLLOWUP-14)", () => {
  test("topbar lists every company the admin can access, not just personally-assigned ones", async ({ page }) => {
    await adminSeesBothMocks(page);
    await login(page);

    const options = await page.locator("#topbarCompanySelect option").allTextContents();
    // B is NOT in auth/me.company_ids yet must appear (admin sees all).
    expect(options).toContain(COMPANY_A.name);
    expect(options).toContain(COMPANY_B.name);
  });

  test("selecting a company outside auth/me.company_ids persists across a requireLiveAuth() action", async ({ page }) => {
    await adminSeesBothMocks(page);
    // Capture the company id used by the document-list fetch that Processing
    // fires after re-auth (goToProcessing -> requireLiveAuth -> getCurrentUser).
    let resolveDocsCompanyId: (id: string) => void = () => {};
    const firstDocsCompanyId = new Promise<string>((resolve) => {
      resolveDocsCompanyId = resolve;
    });
    await page.route("**/api/v1/companies/*/documents", (route) => {
      const match = route.request().url().match(/companies\/([^/]+)\/documents/);
      if (match) resolveDocsCompanyId(match[1]);
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });
    await login(page);

    // Select B — a company the admin can see but is not in auth/me.company_ids.
    await page.selectOption("#topbarCompanySelect", COMPANY_B.id);
    await page.click("[data-screen='s-processing']");

    // Would FAIL on 26bd05e: resolveSelectedCompanyId validated only against
    // company_ids=[A], so B fell back to primary A and the fetch used A while
    // the topbar still showed B (the exact drift symptom).
    const companyId = await firstDocsCompanyId;
    expect(companyId).toBe(COMPANY_B.id);
    // And the topbar must still show B after the re-auth round-trip.
    await expect(page.locator("#topbarCompanySelect")).toHaveValue(COMPANY_B.id);
  });
});
