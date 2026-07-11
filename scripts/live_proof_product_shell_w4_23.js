const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

function loadEnv(filePath) {
  const env = {};
  if (!fs.existsSync(filePath)) return env;
  const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/);
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx === -1) continue;
    env[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  return env;
}

function stamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

async function main() {
  const env = {
    ...loadEnv(path.resolve(__dirname, "..", ".env.sit.local")),
    ...process.env,
  };

  const POC_URL = env.POC_URL || "https://sit.yahwan.biz";
  const SIT_BASIC_USER = env.SIT_BASIC_USER || "admin";
  const SIT_BASIC_PASS = env.SIT_BASIC_PASS || "admin";
  const SYS_ADMIN_USER = env.SIT_SYS_ADMIN_USER || "sit-admin@ledgerflow.local";
  const SYS_ADMIN_PASS = env.SIT_SYS_ADMIN_PASS || "admin123456";

  const ts = Date.now();
  const TEST_TAX_ID = String(ts).slice(0, 13);
  const TEST_COMPANY_NAME = "W4-23 Live Proof Co " + ts;
  const TEST_ADMIN_EMAIL = "w4-23-admin-" + ts + "@ledgerflow.local";

  const outDir = path.resolve(__dirname, "..", "test-results", "w4-product-shell-live-proof-23", stamp());
  fs.mkdirSync(outDir, { recursive: true });

  const events = [];
  const result = {
    generated_at_utc: new Date().toISOString(),
    out_dir: outDir,
    poc_url: POC_URL,
    sys_admin_user: SYS_ADMIN_USER,
    test_company_name: TEST_COMPANY_NAME,
    test_tax_id: TEST_TAX_ID,
    test_admin_email: TEST_ADMIN_EMAIL,
    steps: {},
  };

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    baseURL: POC_URL,
    viewport: { width: 1700, height: 1200 },
    httpCredentials: { username: SIT_BASIC_USER, password: SIT_BASIC_PASS },
    acceptDownloads: true,
  });
  const page = await context.newPage();

  page.on("dialog", async (dialog) => {
    events.push({ t: new Date().toISOString(), type: "dialog", message: dialog.message() });
    await dialog.accept();
  });

  page.on("response", async (res) => {
    const url = res.url();
    if (!url.includes("/api/")) return;
    const entry = { t: new Date().toISOString(), method: res.request().method(), status: res.status(), url };
    if (/\/api\/v1\/admin\/companies/.test(url) || /\/api\/v1\/llm\/routing/.test(url) || /\/api\/v1\/auth\/me/.test(url)) {
      try {
        entry.body = await res.json();
      } catch {
        // ignore non-JSON bodies
      }
    }
    events.push(entry);
  });

  async function shot(name) {
    await page.screenshot({ path: path.join(outDir, name + ".png"), fullPage: true });
  }

  async function loginAs(user, pass) {
    await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForTimeout(1000);
    const loginVisible = await page.locator("#login-screen").isVisible().catch(() => false);
    if (loginVisible) {
      await page.fill("#loginUser", user);
      await page.fill("#loginPw", pass);
      await page.click("#loginForm button[type='submit']");
      await page.waitForTimeout(2000);
    }
    await page.waitForSelector("#app", { timeout: 60000 });
    await page.waitForTimeout(1000);
  }

  function lastMeRole() {
    for (let i = events.length - 1; i >= 0; i--) {
      const e = events[i];
      if (e.url && e.url.includes("/api/v1/auth/me") && e.body && e.body.role) return e.body.role;
    }
    return null;
  }

  try {
    // ── Step 1: Log in as sys_admin on SIT ──
    await loginAs(SYS_ADMIN_USER, SYS_ADMIN_PASS);
    await page.waitForTimeout(500);
    const role1 = lastMeRole();
    result.steps.step1_login_sys_admin = { role_after_login: role1 };
    await shot("01-logged-in-sys-admin");

    // ── Step 2: Open Companies, create test company with stock/line-item checkbox ON ──
    await page.click('[data-screen="s-companies"]');
    await page.waitForTimeout(800);
    const createVisible = await page.locator("#createCompanyBtn").isVisible().catch(() => false);
    result.steps.step2_create_company_button_visible_for_sys_admin = createVisible;
    await page.click("#createCompanyBtn");
    await page.waitForTimeout(300);
    await page.fill("#companyNameInput", TEST_COMPANY_NAME);
    await page.fill("#companyTaxIdInput", TEST_TAX_ID);
    await page.check("#companyEnableStockInput");
    await shot("02-company-create-form-stock-on");
    const [createResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/admin/companies") && r.request().method() === "POST"),
      page.click("#companyDrawerSaveBtn"),
    ]);
    await page.waitForTimeout(800);
    let createBody = {};
    try { createBody = await createResp.json(); } catch { /* ignore */ }
    result.steps.step2_create_company_response = { status: createResp.status(), body: createBody };
    const testCompanyId = createBody.id || null;
    await shot("02b-company-created");

    // ── Step 3: Reload/revisit edit, confirm checkbox still enabled from persisted data ──
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForSelector("#app", { timeout: 60000 });
    await page.click('[data-screen="s-companies"]');
    await page.waitForTimeout(800);
    const editButtonForTest = page.locator("tr", { hasText: TEST_COMPANY_NAME }).locator("button", { hasText: "แก้ไข" });
    await editButtonForTest.click();
    await page.waitForTimeout(400);
    const stockCheckedAfterReload = await page.locator("#companyEnableStockInput").isChecked();
    result.steps.step3_stock_checkbox_persisted_after_reload = stockCheckedAfterReload;
    await shot("03-company-edit-stock-checked-after-reload");

    // ── Step 4: Toggle checkbox off, save, reopen, confirm persisted OFF ──
    await page.uncheck("#companyEnableStockInput");
    const [updateResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/admin/companies/") && r.request().method() === "PUT"),
      page.click("#companyDrawerSaveBtn"),
    ]);
    let updateBody = {};
    try { updateBody = await updateResp.json(); } catch { /* ignore */ }
    result.steps.step4_toggle_off_response = { status: updateResp.status(), body: updateBody };
    await page.waitForTimeout(600);
    await page.click('[data-screen="s-companies"]');
    await page.waitForTimeout(500);
    const editButtonForTest2 = page.locator("tr", { hasText: TEST_COMPANY_NAME }).locator("button", { hasText: "แก้ไข" });
    await editButtonForTest2.click();
    await page.waitForTimeout(400);
    const stockCheckedAfterToggleOff = await page.locator("#companyEnableStockInput").isChecked();
    result.steps.step4_stock_checkbox_persisted_off = stockCheckedAfterToggleOff;
    await shot("04-company-edit-stock-unchecked-persisted");
    await page.click('#drawer-company button:has-text("ยกเลิก")');
    await page.waitForTimeout(300);

    // ── Step 5: As sys_admin, delete button visible; soft-delete the test company ──
    const deleteBtnRow = page.locator("tr", { hasText: TEST_COMPANY_NAME });
    const deleteBtnVisible = await deleteBtnRow.locator("button", { hasText: "ลบ" }).isVisible().catch(() => false);
    result.steps.step5_delete_button_visible_for_sys_admin = deleteBtnVisible;
    await shot("05-sys-admin-delete-button-visible");
    const [deleteResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/admin/companies/") && r.request().method() === "DELETE"),
      deleteBtnRow.locator("button", { hasText: "ลบ" }).click(),
    ]);
    result.steps.step5_delete_response = { status: deleteResp.status(), url: deleteResp.url() };
    await page.waitForTimeout(600);
    await shot("05b-after-delete");

    // ── Bootstrap: create a plain "admin" test user via real Users Admin API (needed for step 6) ──
    await page.click('[data-screen="s-users"]');
    await page.waitForTimeout(600);
    await page.click('button:has-text("+ เพิ่มผู้ใช้")');
    await page.waitForTimeout(300);
    await page.fill("#userEmailInput", TEST_ADMIN_EMAIL);
    await page.fill("#userUsernameInput", "w4-23-admin-" + ts);
    await page.fill("#userDisplayNameInput", "W4-23 Test Admin");
    await page.selectOption("#userRoleSelect", "admin");
    const [userCreateResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/admin/users") && r.request().method() === "POST"),
      page.click("#userDrawerSaveBtn"),
    ]);
    let userCreateBody = {};
    try { userCreateBody = await userCreateResp.json(); } catch { /* ignore */ }
    result.steps.bootstrap_test_admin_user = { status: userCreateResp.status(), email: TEST_ADMIN_EMAIL, temp_password: userCreateBody.temporary_password || userCreateBody.temp_password || null };
    await shot("05c-test-admin-user-created");
    const tempPassword = userCreateBody.temporary_password || userCreateBody.temp_password || null;
    await page.click('#drawer-user button:has-text("ยกเลิก")').catch(() => {});

    // ── Step 6: As admin (non-sys_admin), confirm delete button not visible ──
    if (tempPassword) {
      // logout by clearing storage and reloading to login screen
      await page.evaluate(() => { try { localStorage.clear(); sessionStorage.clear(); } catch {} });
      await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(800);
      await page.fill("#loginUser", TEST_ADMIN_EMAIL);
      await page.fill("#loginPw", tempPassword);
      await page.click("#loginForm button[type='submit']");
      await page.waitForTimeout(1500);
      // Handle forced password change on first login if present
      const forceChangeVisible = await page.locator("#force-change-password-screen").isVisible().catch(() => false);
      result.steps.step6_force_change_password_prompted = forceChangeVisible;
      if (forceChangeVisible) {
        const newPass = "LfProof23" + ts;
        await page.fill("#forceChangeOldPw", tempPassword).catch(() => {});
        await page.fill("#forceChangeNewPw", newPass).catch(() => {});
        await page.fill("#forceChangeConfirmPw", newPass).catch(() => {});
        await page.click("#force-change-password-screen button[type='submit']").catch(() => {});
        await page.waitForTimeout(1500);
      }
      await page.waitForSelector("#app", { timeout: 60000 }).catch(() => {});
      await page.click('[data-screen="s-companies"]').catch(() => {});
      await page.waitForTimeout(600);
      const role6 = lastMeRole();
      const anyDeleteButtonVisible = await page.locator('button:has-text("ลบ")').first().isVisible().catch(() => false);
      result.steps.step6_role_confirmed = role6;
      result.steps.step6_delete_button_visible_for_admin = anyDeleteButtonVisible;
      await shot("06-admin-no-delete-button");
    } else {
      result.steps.step6_skipped_reason = "temp_password not captured from user-create response";
    }

    // ── Re-login as sys_admin for remaining steps ──
    await page.evaluate(() => { try { localStorage.clear(); sessionStorage.clear(); } catch {} });
    await loginAs(SYS_ADMIN_USER, SYS_ADMIN_PASS);

    // Create two companies for processing toggle-on/off checks
    async function createCompany(name, enableStock) {
      await page.click('[data-screen="s-companies"]');
      await page.waitForTimeout(500);
      await page.click("#createCompanyBtn");
      await page.waitForTimeout(300);
      await page.fill("#companyNameInput", name);
      await page.fill("#companyTaxIdInput", String(Date.now()).slice(0, 13));
      if (enableStock) await page.check("#companyEnableStockInput");
      const [resp] = await Promise.all([
        page.waitForResponse((r) => r.url().includes("/api/v1/admin/companies") && r.request().method() === "POST"),
        page.click("#companyDrawerSaveBtn"),
      ]);
      let body = {};
      try { body = await resp.json(); } catch { /* ignore */ }
      await page.waitForTimeout(500);
      return body.id || null;
    }

    const companyOnId = await createCompany("W4-23 Stock ON " + ts, true);
    const companyOffId = await createCompany("W4-23 Stock OFF " + ts, false);
    result.steps.processing_test_companies = { on: companyOnId, off: companyOffId };

    async function selectTopbarCompany(companyId) {
      if (!companyId) return;
      await page.selectOption("#topbarCompanySelect", companyId);
      await page.waitForTimeout(500);
    }

    // ── Step 7: Processing with toggle ON company -> notice appears ──
    await selectTopbarCompany(companyOnId);
    await page.click('[data-screen="s-processing"]');
    await page.waitForTimeout(1000);
    const noticeVisibleOn = await page.locator("#processingLineItemNotice").isVisible().catch(() => false);
    result.steps.step7_line_item_notice_visible_when_on = noticeVisibleOn;
    await shot("07-processing-notice-on");

    // ── Step 8: Processing with toggle OFF company -> notice does not appear ──
    await selectTopbarCompany(companyOffId);
    await page.click('[data-screen="s-processing"]');
    await page.waitForTimeout(1000);
    const noticeVisibleOff = await page.locator("#processingLineItemNotice").isVisible().catch(() => false);
    result.steps.step8_line_item_notice_hidden_when_off = !noticeVisibleOff;
    await shot("08-processing-notice-off");

    // ── Step 9: header-only Upload -> Processing -> Review Scan works for toggle-OFF company ──
    await page.click('[data-screen="s-upload"]');
    await page.waitForTimeout(800);
    const sampleFile = "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026130449.pdf";
    let uploadOk = false;
    if (fs.existsSync(sampleFile)) {
      await page.setInputFiles("#uploadFileInput", [sampleFile]);
      await page.waitForTimeout(800);
      const count = await page.locator("#uploadFileCount").innerText().catch(() => "0");
      uploadOk = count !== "0";
    }
    result.steps.step9_upload_sample_selected = uploadOk;
    await shot("09-upload-toggle-off-company");
    await page.click('[data-screen="s-review-scan"]').catch(() => {});
    await page.waitForTimeout(1000);
    const reviewScanReached = await page.locator("#s-review-scan.active, #s-review-scan.screen.active").count().catch(() => 0);
    result.steps.step9_review_scan_reachable = reviewScanReached > 0 || (await page.locator("#s-review-scan").isVisible().catch(() => false));
    await shot("09b-review-scan-screen");

    // ── Step 10: Review Mapping — filename-first labels ──
    await page.click('[data-screen="s-review-mapping"]');
    await page.waitForTimeout(1000);
    const mappingListText = await page.locator("#reviewMappingListBody").innerText().catch(() => "");
    const mappingDetailText = await page.locator("#reviewMappingDetail").innerText().catch(() => "");
    result.steps.step10_review_mapping_list_sample = mappingListText.slice(0, 500);
    result.steps.step10_review_mapping_detail_sample = mappingDetailText.slice(0, 500);
    await shot("10-review-mapping-filename-first");

    // ── Step 11: Internal Console reachable by sys_admin ──
    const consoleNavVisible = await page.locator("#internalConsoleNavItem").isVisible().catch(() => false);
    result.steps.step11_internal_console_nav_visible = consoleNavVisible;
    if (consoleNavVisible) {
      await page.click("#internalConsoleNavItem");
      await page.waitForTimeout(800);
      const consoleScreenActive = await page.locator("#s-system-home").isVisible().catch(() => false);
      result.steps.step11_internal_console_screen_opened = consoleScreenActive;
      await shot("11-internal-console");
    }

    // ── Step 12: Settings -> Model Router live values from GET /api/v1/llm/routing ──
    await page.click('[data-screen="s-settings"]').catch(async () => {
      await page.evaluate(() => window.navigate && window.navigate("s-settings"));
    });
    await page.waitForTimeout(1500);
    const [routingResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/llm/routing"), { timeout: 15000 }).catch(() => null),
      page.evaluate(() => window.loadLlmRouting && window.loadLlmRouting()),
    ]);
    let routingBody = null;
    if (routingResp) {
      try { routingBody = await routingResp.json(); } catch { /* ignore */ }
    }
    const llmRoutingText = await page.locator("#llmRoutingLive").innerText().catch(() => "");
    result.steps.step12_model_router_response_body = routingBody;
    result.steps.step12_model_router_rendered_text_sample = llmRoutingText.slice(0, 500);
    await shot("12-settings-model-router");

    // ── Step 13: Dashboard no old Metro subtitle; Export no fake fixture rows ──
    await page.click('[data-screen="s-dashboard"]').catch(async () => {
      await page.evaluate(() => window.navigate && window.navigate("s-dashboard"));
    });
    await page.waitForTimeout(800);
    const dashboardSubtitle = await page.locator("#dashboardCompanySubtitle").innerText().catch(() => "");
    result.steps.step13_dashboard_subtitle = dashboardSubtitle;
    result.steps.step13_dashboard_subtitle_has_metro = /metro/i.test(dashboardSubtitle);
    await shot("13-dashboard");

    await page.click('[data-screen="s-export"]').catch(async () => {
      await page.evaluate(() => window.navigate && window.navigate("s-export"));
    });
    await page.waitForTimeout(800);
    const exportScreenText = await page.locator("#s-export").innerText().catch(() => "");
    result.steps.step13_export_screen_has_metro_fixture = /Metro_May2569|Express_GL_Metro/i.test(exportScreenText);
    await shot("13b-export-screen");

    result.status = "completed";
  } catch (err) {
    result.status = "error";
    result.error = String(err && err.stack ? err.stack : err);
    await shot("zz-error-state").catch(() => {});
  } finally {
    result.network_events = events;
    fs.writeFileSync(path.join(outDir, "result.json"), JSON.stringify(result, null, 2));
    await browser.close();
  }

  console.log(JSON.stringify(result, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
