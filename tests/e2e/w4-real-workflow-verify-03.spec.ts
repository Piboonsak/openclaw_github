import { test, type Page } from "@playwright/test";
import { writeFileSync, mkdirSync } from "node:fs";

/**
 * W4-SIT-E2E-CLAUDE-REAL-WORKFLOW-VERIFY-03
 *
 * Reproduction script (not a strict pass/fail regression test) that drives the
 * REAL live SIT surface (/phase2/prototype) with the customer's actual sample
 * files, and records what actually happens at each step of RWG-01..RWG-04 into
 * an evidence JSON file for the completion report / gap register update.
 *
 * Each step is wrapped so one failure doesn't abort the whole run — we want the
 * full picture, not a single stack trace.
 */

declare const process: { env: Record<string, string | undefined> };

const APP_USER = process.env.SIT_APP_USER || "";
const APP_PASS = process.env.SIT_APP_PASS || "";

const COMPANY_NAME = "บริษัท ฤทธิ์ล้ำเลิศ จำกัด";
const COMPANY_TAX_ID = "0125561025189";
const STAFF_EMAIL = "test@yahwan.biz";

const COA_PDF = "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ ผังบัญชี.pdf";
const AP_CSV = "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/APAR/AP-CCSS.csv";
const AR_CSV = "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/APAR/AR-CCSS.csv";
const RRL_FILES = [
  "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125257.pdf",
  "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125316.pdf",
];

const EVIDENCE_DIR = "test-results/w4-real-workflow-verify-03";
type Finding = { id: string; area: string; note: string; evidence?: unknown };
const findings: Finding[] = [];
function record(id: string, area: string, note: string, evidence?: unknown) {
  findings.push({ id, area, note, evidence });
  console.log(`[${id}] ${area}: ${note}`);
}

async function step(id: string, area: string, fn: () => Promise<void>) {
  try {
    await fn();
  } catch (error) {
    record(id, area, `EXCEPTION: ${(error as Error).message}`);
  }
}

async function shot(page: Page, name: string) {
  try {
    await page.screenshot({ path: `${EVIDENCE_DIR}/${name}.png`, fullPage: true });
  } catch {
    /* best-effort */
  }
}

// A stuck drawer/modal backdrop blocks every click behind it, which would
// otherwise hang each subsequent step until the test timeout. Force-close via
// the app's own global helpers rather than guessing at an ambiguous "cancel"
// button selector (several modals share the same Thai button text).
async function closeAnyOverlay(page: Page) {
  await page
    .evaluate(() => {
      const w = window as unknown as {
        closeDrawer?: (id: string) => void;
        closeModal?: (id: string) => void;
      };
      ["drawer-company", "drawer-user"].forEach((id) => w.closeDrawer && w.closeDrawer(id));
      [
        "modal-clone-template",
        "modal-import-coa",
        "modal-import-vendor",
        "modal-import-customer",
        "modal-confirm",
      ].forEach((id) => w.closeModal && w.closeModal(id));
    })
    .catch(() => {});
  await page.keyboard.press("Escape").catch(() => {});
}

const NAV_TIMEOUT = 10_000;

test.describe("W4-SIT-E2E-CLAUDE-REAL-WORKFLOW-VERIFY-03", () => {
  test.skip(!APP_USER || !APP_PASS, "SIT_APP_USER / SIT_APP_PASS not set");

  test("real workflow reproduction with actual sample files", async ({ page, browser }) => {
    test.setTimeout(300_000);
    mkdirSync(EVIDENCE_DIR, { recursive: true });

    let createdCompanyId = "";

    // ---- Login as admin ----
    await step("LOGIN", "auth", async () => {
      await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 60_000 });
      await page.fill("#loginUser", APP_USER);
      await page.fill("#loginPw", APP_PASS);
      const loginResp = page.waitForResponse((r) => r.url().includes("/api/v1/auth/login"), { timeout: 30_000 });
      await page.click("#loginForm button[type=submit], #loginForm .btn-primary");
      const resp = await loginResp;
      record("LOGIN", "auth", `login status=${resp.status()}`);
      await page.waitForSelector("#app.visible", { timeout: 15_000 });
    });

    // ==================== RWG-01 ====================
    await step("RWG01-CREATE", "company", async () => {
      await page.click("[data-screen='s-companies']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(600);
      const existing = page.locator("#companiesTableBody").getByText(COMPANY_TAX_ID);
      if (await existing.count()) {
        record("RWG01-CREATE", "company", "Company already exists from a prior run — reusing it");
      } else {
        await page.click("text=+ เพิ่มบริษัท");
        await page.fill("#companyNameInput", COMPANY_NAME);
        await page.fill("#companyTaxIdInput", COMPANY_TAX_ID);
        const createResp = page.waitForResponse(
          (r) => r.url().includes("/api/v1/admin/companies") && r.request().method() === "POST",
          { timeout: 15_000 },
        );
        await page.click("#companyDrawerSaveBtn");
        const resp = await createResp;
        const body = await resp.json().catch(() => ({}));
        createdCompanyId = body.id || "";
        record("RWG01-CREATE", "company", `POST /admin/companies status=${resp.status()}`, body);
      }
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.waitForSelector("#app.visible", { timeout: 15_000 });
      await page.click("[data-screen='s-companies']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(600);
      const persisted = await page.locator("#companiesTableBody").getByText(COMPANY_TAX_ID).count();
      record("RWG01-CREATE", "company", `persists after refresh: ${persisted > 0}`);
      await shot(page, "01-companies-list");
    });

    await step("RWG01-DUPLICATE", "company", async () => {
      await page.click("text=+ เพิ่มบริษัท");
      await page.fill("#companyNameInput", COMPANY_NAME + " (dup test)");
      await page.fill("#companyTaxIdInput", COMPANY_TAX_ID);
      const createResp = page.waitForResponse(
        (r) => r.url().includes("/api/v1/admin/companies") && r.request().method() === "POST",
        { timeout: 15_000 },
      );
      await page.click("#companyDrawerSaveBtn");
      const resp = await createResp;
      record("RWG01-DUPLICATE", "company", `duplicate tax_id create status=${resp.status()} (expect 409)`);
      await closeAnyOverlay(page);
    });

    await step("RWG01-OPEN-DETAIL", "company-detail", async () => {
      await closeAnyOverlay(page);
      await page.click("[data-screen='s-companies']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(400);
      const row = page.locator("#companiesTableBody tr", { hasText: COMPANY_TAX_ID });
      await row.getByRole("button", { name: /ตั้งค่า/ }).click({ timeout: NAV_TIMEOUT });
      await page.waitForSelector("#s-company-detail", { timeout: 10_000 });
      const cid = await page.locator("#s-company-detail").getAttribute("data-company-id");
      if (cid) createdCompanyId = cid;
      record("RWG01-OPEN-DETAIL", "company-detail", `opened detail, company_id=${createdCompanyId}`);
      await shot(page, "02-company-detail-coa");
    });

    await step("RWG01-COA-BANNER", "coa", async () => {
      const bannerText = await page.locator("#company-coa").innerText();
      const isHonestlyDeferred = /Deferred/i.test(bannerText);
      record("RWG01-COA-BANNER", "coa", `COA tab shows explicit Deferred banner: ${isHonestlyDeferred}`, {
        bannerSnippet: bannerText.slice(0, 200),
      });
      // Confirm there is no PDF-specific upload control at all (only YAML/CSV import modal)
      const importBtn = page.locator("#company-coa").getByText("นำเข้า YAML/CSV");
      record("RWG01-COA-BANNER", "coa", `Only YAML/CSV import entry point exists (no PDF upload control): ${await importBtn.count() > 0}`);
    });

    await step("RWG01-AP-IMPORT", "ap", async () => {
      await page.click("button:has-text('AP · ผู้จำหน่าย')", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(300);
      const before = await page.locator("#vendorMasterStatus").innerText();
      await page.click("text=นำเข้า Vendor CSV/YAML");
      await page.setInputFiles("#vendorImportFileInput", AP_CSV);
      const importResp = page.waitForResponse((r) => r.url().includes("/vendor-master/import"), { timeout: 30_000 });
      await page.click("#vendorImportSubmitBtn");
      const resp = await importResp;
      const body = await resp.json().catch(() => ({}));
      record("RWG01-AP-IMPORT", "ap", `POST vendor-master/import status=${resp.status()} before="${before}"`, body);
      await page.waitForTimeout(500);
      const after = await page.locator("#vendorMasterStatus").innerText();
      record("RWG01-AP-IMPORT", "ap", `vendor status after import: "${after}"`);
      await shot(page, "03-ap-imported");
    });

    await step("RWG01-AR-IMPORT", "ar", async () => {
      await page.click("button:has-text('AR · ลูกค้า')", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(300);
      const before = await page.locator("#customerMasterStatus").innerText();
      await page.click("text=นำเข้า Customer CSV/YAML");
      await page.setInputFiles("#customerImportFileInput", AR_CSV);
      const importResp = page.waitForResponse((r) => r.url().includes("/customer-master/import"), { timeout: 30_000 });
      await page.click("#customerImportSubmitBtn");
      const resp = await importResp;
      const body = await resp.json().catch(() => ({}));
      record("RWG01-AR-IMPORT", "ar", `POST customer-master/import status=${resp.status()} before="${before}"`, body);
      await page.waitForTimeout(500);
      const after = await page.locator("#customerMasterStatus").innerText();
      record("RWG01-AR-IMPORT", "ar", `customer status after import: "${after}"`);
      await shot(page, "04-ar-imported");
    });

    await step("RWG01-REIMPORT-UPSERT", "ap", async () => {
      // Re-import same AP file to check upsert behavior (no duplication)
      await page.click("button:has-text('AP · ผู้จำหน่าย')", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(300);
      await page.click("text=นำเข้า Vendor CSV/YAML");
      await page.setInputFiles("#vendorImportFileInput", AP_CSV);
      const importResp = page.waitForResponse((r) => r.url().includes("/vendor-master/import"), { timeout: 30_000 });
      await page.click("#vendorImportSubmitBtn");
      const resp = await importResp;
      const body = await resp.json().catch(() => ({}));
      record("RWG01-REIMPORT-UPSERT", "ap", `re-import same file status=${resp.status()}`, body);
    });

    await step("RWG01-MAPPING-RULES", "mapping-rules", async () => {
      await page.locator("#s-company-detail .tab-bar").getByText("ตั้งค่า", { exact: true }).click({ timeout: NAV_TIMEOUT });
      await page.waitForTimeout(300);
      const addBtn = page.getByRole("button", { name: "+ เพิ่ม Rule" });
      await addBtn.click();
      await page.waitForTimeout(300);
      const toast = page.locator(".toast").last();
      const toastText = await toast.innerText().catch(() => "(no toast found)");
      const toastClass = await toast.getAttribute("class").catch(() => "");
      record("RWG01-MAPPING-RULES", "mapping-rules", `"+ เพิ่ม Rule" toast="${toastText}" class="${toastClass}"`);
    });

    // ==================== RWG-02 ====================
    await step("RWG02-CREATE-USER", "user", async () => {
      await page.click("[data-screen='s-users']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(500);
      const existing = await page.locator("#usersTableBody").getByText(STAFF_EMAIL).count();
      if (existing) {
        record("RWG02-CREATE-USER", "user", "User already exists from a prior run — will need manual password reset to continue");
        return;
      }
      await page.click("text=+ เพิ่มผู้ใช้");
      await page.fill("#userEmailInput", STAFF_EMAIL);
      await page.fill("#userUsernameInput", "test.yahwan");
      await page.selectOption("#userRoleSelect", "staff");
      await page.waitForTimeout(300);
      // check the created company's checkbox
      const checkbox = page.locator(".user-company-checkbox").filter({ hasText: "" });
      const boxes = page.locator("#userCompanyCheckboxes label", { hasText: COMPANY_NAME });
      if (await boxes.count()) {
        await boxes.locator("input").check();
      }
      const createResp = page.waitForResponse(
        (r) => r.url().includes("/api/v1/admin/users") && r.request().method() === "POST",
        { timeout: 15_000 },
      );
      await page.click("#userDrawerSaveBtn");
      const resp = await createResp;
      const body = await resp.json().catch(() => ({}));
      record("RWG02-CREATE-USER", "user", `POST /admin/users status=${resp.status()}`, {
        ...body,
        temp_password: body.temp_password ? "<redacted-captured>" : undefined,
      });
      (globalThis as unknown as { __tempPassword?: string }).__tempPassword = body.temp_password;
      await shot(page, "05-user-created");
    });

    await step("RWG02-NAV-VISIBILITY", "rbac", async () => {
      const usersNavVisible = await page.locator("[data-screen='s-users']").isVisible();
      const companiesNavVisible = await page.locator("[data-screen='s-companies']").isVisible();
      const addCompanyBtnVisible = await page.getByText("+ เพิ่มบริษัท").isVisible().catch(() => false);
      record(
        "RWG02-NAV-VISIBILITY",
        "rbac",
        `As ADMIN: Users nav visible=${usersNavVisible}, Companies nav visible=${companiesNavVisible}, +เพิ่มบริษัท visible=${addCompanyBtnVisible} (baseline — same nav is not yet role-filtered client-side)`,
      );
    });

    // ---- Login as the newly created staff user in a fresh context ----
    const tempPassword = (globalThis as unknown as { __tempPassword?: string }).__tempPassword;
    if (tempPassword) {
      const staffContext = await browser.newContext();
      const staffPage = await staffContext.newPage();
      await step("RWG02-STAFF-LOGIN", "rbac", async () => {
        await staffPage.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 60_000 });
        await staffPage.fill("#loginUser", STAFF_EMAIL);
        await staffPage.fill("#loginPw", tempPassword);
        const loginResp = staffPage.waitForResponse((r) => r.url().includes("/api/v1/auth/login"), { timeout: 30_000 });
        await staffPage.click("#loginForm button[type=submit], #loginForm .btn-primary");
        const resp = await loginResp;
        record("RWG02-STAFF-LOGIN", "rbac", `staff first login status=${resp.status()}`);
      });

      await step("RWG02-STAFF-SCOPE", "rbac", async () => {
        await staffPage.waitForTimeout(500);
        // may be forced into change-password flow (must_change_password) — check screen state
        const appVisible = await staffPage.locator("#app.visible").isVisible().catch(() => false);
        record("RWG02-STAFF-SCOPE", "rbac", `staff app visible without forced password change: ${appVisible}`);
        if (appVisible) {
          const companiesResp = staffPage.waitForResponse((r) => r.url().includes("/api/v1/admin/companies"), { timeout: 15_000 }).catch(() => null);
          await staffPage.click("[data-screen='s-companies']", { timeout: NAV_TIMEOUT });
          const resp = await companiesResp;
          if (resp) {
            const body = await resp.json().catch(() => []);
            record(
              "RWG02-STAFF-SCOPE",
              "rbac",
              `staff GET /admin/companies status=${resp.status()}, returned ${Array.isArray(body) ? body.length : "?"} companies (staff is assigned to only 1)`,
              Array.isArray(body) ? body.map((c: { name: string; tax_id: string }) => ({ name: c.name, tax_id: c.tax_id })) : body,
            );
          }
          await shot(staffPage, "06-staff-companies-view");

          const usersResp = staffPage.waitForResponse((r) => r.url().includes("/api/v1/admin/users"), { timeout: 15_000 }).catch(() => null);
          await staffPage.click("[data-screen='s-users']", { timeout: NAV_TIMEOUT }).catch(() => {});
          const uResp = await usersResp;
          if (uResp) {
            record("RWG02-STAFF-SCOPE", "rbac", `staff GET /admin/users status=${uResp.status()} (expect 403)`);
          }

          // staff attempting company create
          const addBtnVisible = await staffPage.getByText("+ เพิ่มบริษัท").isVisible().catch(() => false);
          record("RWG02-STAFF-SCOPE", "rbac", `staff sees "+ เพิ่มบริษัท" button: ${addBtnVisible} (button visibility, not yet proof of a blocked request)`);
          if (addBtnVisible) {
            await staffPage.click("[data-screen='s-companies']", { timeout: NAV_TIMEOUT });
            await staffPage.click("text=+ เพิ่มบริษัท", { timeout: NAV_TIMEOUT });
            await staffPage.fill("#companyNameInput", "Staff Attempt Co");
            await staffPage.fill("#companyTaxIdInput", "0199999999999");
            const createResp = staffPage.waitForResponse(
              (r) => r.url().includes("/api/v1/admin/companies") && r.request().method() === "POST",
              { timeout: 15_000 },
            );
            await staffPage.click("#companyDrawerSaveBtn");
            const resp2 = await createResp;
            record("RWG02-STAFF-SCOPE", "rbac", `staff POST /admin/companies (create) status=${resp2.status()} (expect 403)`);
          }
        }
      });
      await staffContext.close();
    } else {
      record("RWG02-STAFF-LOGIN", "rbac", "No temp password captured (user pre-existed) — could not test staff scoping this run");
    }

    // ==================== RWG-03 ====================
    await step("RWG03-UPLOAD", "upload", async () => {
      await closeAnyOverlay(page);
      await page.click("[data-screen='s-upload']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(400);
      const bodyText = await page.locator("#s-upload").innerText();
      const labeledFixture = /fixture/i.test(bodyText);
      record("RWG03-UPLOAD", "upload", `Upload screen self-labels as fixture/non-real: ${labeledFixture}`);
      await shot(page, "07-upload-screen");
    });

    await step("RWG03-PROCESSING", "processing", async () => {
      await page.click("[data-screen='s-processing']", { timeout: NAV_TIMEOUT }).catch(async () => {
        await page.evaluate(() => (window as unknown as { navigate: (s: string) => void }).navigate("s-processing"));
      });
      await page.waitForTimeout(400);
      await shot(page, "08-processing-screen");
    });

    await step("RWG03-REVIEW-SCAN", "review-scan", async () => {
      await page.click("[data-screen='s-review-scan']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(400);
      const approveAllBtn = page.getByRole("button", { name: /Approve All|อนุมัติทั้งหมด/i }).first();
      if (await approveAllBtn.count()) {
        await approveAllBtn.click();
        await page.waitForTimeout(300);
        const toast = await page.locator(".toast").last().innerText().catch(() => "(none)");
        record("RWG03-REVIEW-SCAN", "review-scan", `Approve All toast: "${toast}"`);
      } else {
        record("RWG03-REVIEW-SCAN", "review-scan", "Approve All control not found on this screen");
      }
      await shot(page, "09-review-scan");
    });

    await step("RWG03-REVIEW-MAPPING", "review-mapping", async () => {
      await page.click("[data-screen='s-review-mapping']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(400);
      const confirmBtn = page.getByRole("button", { name: /Confirm Mapping|ยืนยัน Mapping/i }).first();
      if (await confirmBtn.count()) {
        await confirmBtn.click();
        await page.waitForTimeout(300);
        const toast = await page.locator(".toast").last().innerText().catch(() => "(none)");
        record("RWG03-REVIEW-MAPPING", "review-mapping", `Confirm Mapping toast: "${toast}"`);
      } else {
        record("RWG03-REVIEW-MAPPING", "review-mapping", "Confirm Mapping control not found on this screen");
      }
      await shot(page, "10-review-mapping");
    });

    await step("RWG03-EXPORT", "export", async () => {
      await page.click("[data-screen='s-export']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(600);
      const previewResp = page.waitForResponse((r) => r.url().includes("/api/v1/export/preview"), { timeout: 10_000 }).catch(() => null);
      const quickCard = page.locator("#exportModeQuickCard");
      if (await quickCard.count()) await quickCard.click();
      const resp = await previewResp;
      record("RWG03-EXPORT", "export", `export preview request observed: ${resp ? `status=${resp.status()}` : "none within timeout"}`);
      await shot(page, "11-export-screen");
    });

    // ==================== RWG-04 ====================
    await step("RWG04-TEMPLATES-LIST", "templates", async () => {
      await page.click("[data-screen='s-templates']", { timeout: NAV_TIMEOUT });
      await page.waitForTimeout(400);
      const companyTabText = await page.locator("#tmpl-company").innerText().catch(() => "");
      const mentionsCreatedCompany = companyTabText.includes(COMPANY_NAME);
      record(
        "RWG04-TEMPLATES-LIST",
        "templates",
        `"Templates บริษัท" tab mentions the company we just created: ${mentionsCreatedCompany} (expected true if company-scoped; static fixture would be false)`,
        { snippet: companyTabText.slice(0, 300) },
      );
      await shot(page, "12-templates-master");
    });

    await step("RWG04-LIVE-API-BRIDGE", "templates", async () => {
      const refreshBtn = page.locator("#refreshTemplatesBtn");
      const listResp = page.waitForResponse((r) => r.url().includes("/api/v1/templates") && r.request().method() === "GET", { timeout: 15_000 }).catch(() => null);
      await refreshBtn.click();
      const resp = await listResp;
      const status = await page.locator("#liveTemplateStatus").innerText().catch(() => "");
      record("RWG04-LIVE-API-BRIDGE", "templates", `Refresh Templates -> GET /api/v1/templates status=${resp ? resp.status() : "none"}, status text="${status}"`);
      await shot(page, "13-live-api-bridge");
    });

    await step("RWG04-CLONE-FIXTURE", "templates", async () => {
      await page.locator("button:has-text('Clone to Company')").first().click({ timeout: NAV_TIMEOUT }).catch(() => {});
      await page.waitForTimeout(300);
      const cloneBtn = page.locator("#modal-clone-template").getByRole("button", { name: /Clone/ });
      if (await cloneBtn.count()) {
        await cloneBtn.click();
        await page.waitForTimeout(300);
        const toast = await page.locator(".toast").last().innerText().catch(() => "(none)");
        record("RWG04-CLONE-FIXTURE", "templates", `Fixture-card "Clone to Company" toast: "${toast}"`);
      }
    });

    // ---- Dump evidence ----
    writeFileSync(`${EVIDENCE_DIR}/findings.json`, JSON.stringify(findings, null, 2), "utf8");
    console.log(`\n=== ${findings.length} findings written to ${EVIDENCE_DIR}/findings.json ===`);
  });
});
