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

function basicAuthHeader(user, pass) {
  return `Basic ${Buffer.from(`${user}:${pass}`).toString("base64")}`;
}

function logStep(message) {
  console.log(`[W5] ${message}`);
}

async function main() {
  const env = {
    ...loadEnv(path.resolve(__dirname, "..", ".env.sit.local")),
    ...process.env,
  };

  const BASE_URL = env.POC_URL || "https://sit.yahwan.biz";
  const BASIC_USER = env.SIT_BASIC_USER || "admin";
  const BASIC_PASS = env.SIT_BASIC_PASS || "admin";
  const SYS_ADMIN_USER = env.SIT_SYS_ADMIN_USER || "piboonsak.262@gmail.com";
  const SYS_ADMIN_PASS = env.SIT_SYS_ADMIN_PASS || "admin123456";

  const sampleDocs = [
    "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026130449.pdf",
    "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026130503.pdf",
    "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026130520.pdf",
  ].filter((filePath) => fs.existsSync(filePath));
  if (sampleDocs.length === 0) {
    throw new Error("No sample PDFs found under private_data/poc/Comp_1");
  }
  const sampleDoc = sampleDocs[0];

  const mappingDocx = path.resolve(__dirname, "..", "tmp", "w5-mapping-proof.docx");
  if (!fs.existsSync(mappingDocx)) {
    throw new Error(`Missing DOCX fixture: ${mappingDocx}`);
  }

  const outputDir = path.resolve(__dirname, "..", "test-results", "w5-copilot-batch-deploy-sit-proof-03", stamp());
  fs.mkdirSync(outputDir, { recursive: true });

  const events = [];
  const routeChecks = [];
  const proof = {
    generated_at_utc: new Date().toISOString(),
    base_url: BASE_URL,
    output_dir: outputDir,
    login: {},
    deploy_ref: {},
    route_status_table: [],
    processing_live_proof: {},
    users_live_proof: {},
    mapping_rules_docx_live_proof: {},
    template_configurator_live_proof: {},
    w5_12_classification: {},
    screenshots: [],
  };

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    baseURL: BASE_URL,
    viewport: { width: 1720, height: 1280 },
    httpCredentials: { username: BASIC_USER, password: BASIC_PASS },
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
    const entry = {
      t: new Date().toISOString(),
      method: res.request().method(),
      status: res.status(),
      url,
    };
    if (
      /\/api\/v1\/(auth\/me|admin\/companies|admin\/users|tasks\/|companies\/[^/]+\/mapping-rules|companies\/[^/]+\/vendor-master|companies\/[^/]+\/documents|export|llm\/routing)/.test(
        url,
      )
    ) {
      try {
        entry.body = await res.json();
      } catch {
        try {
          entry.bodyText = await res.text();
        } catch {
          entry.bodyText = "";
        }
      }
    }
    events.push(entry);
  });

  async function shot(name) {
    const filePath = path.join(outputDir, `${name}.png`);
    await page.screenshot({ path: filePath, fullPage: true });
    proof.screenshots.push(filePath);
  }

  async function gotoAndMeasure(urlPath, label, options = {}) {
    const response = await page.goto(urlPath, {
      waitUntil: "domcontentloaded",
      timeout: options.timeout || 120000,
    });
    await page.waitForTimeout(options.waitMs || 1000);
    const bodyText = await page.locator("body").innerText().catch(() => "");
    const finalUrl = page.url();
    const title = await page.title().catch(() => "");
    const result = {
      label,
      requested: urlPath,
      status: response ? response.status() : null,
      final_url: finalUrl,
      title,
      body_preview: bodyText.slice(0, 240),
    };
    routeChecks.push(result);
    return result;
  }

  async function fetchRoute(urlPath) {
    const response = await fetch(`${BASE_URL}${urlPath}`, {
      headers: {
        Authorization: basicAuthHeader(BASIC_USER, BASIC_PASS),
      },
    });
    const text = await response.text();
    const result = {
      url_path: urlPath,
      status: response.status,
      body_preview: text.slice(0, 240),
    };
    routeChecks.push(result);
    return result;
  }

  async function loginAs(user, pass) {
    logStep(`login ${user}`);
    await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForTimeout(1200);
    const loginVisible = await page.locator("#login-screen").isVisible().catch(() => false);
    if (loginVisible) {
      await page.fill("#loginUser", user);
      await page.fill("#loginPw", pass);
      await page.click("#loginForm button[type='submit']");
      await page.waitForTimeout(2500);
    }
    const forceVisible = await page.locator("#force-change-password-screen").isVisible().catch(() => false);
    if (forceVisible) {
      const newPass = `W5Proof-${Date.now()}`;
      await page.fill("#forceChangeOldPw", pass).catch(() => {});
      await page.fill("#forceChangeNewPw", newPass).catch(() => {});
      await page.fill("#forceChangeConfirmPw", newPass).catch(() => {});
      await page.click("#force-change-password-screen button[type='submit']");
      await page.waitForTimeout(2500);
    }
    await page.waitForSelector("#app", { timeout: 90000 });
    proof.login = {
      user,
      app_visible: true,
    };
  }

  async function captureAuthMeRole() {
    for (let index = events.length - 1; index >= 0; index -= 1) {
      const event = events[index];
      if (event.url && /\/api\/v1\/auth\/me$/.test(event.url) && event.body && event.body.role) {
        return event.body.role;
      }
    }
    return null;
  }

  async function expectVisible(locator) {
    await locator.waitFor({ state: "visible", timeout: 15000 });
  }

  async function createCompany(name, enableStock) {
    logStep(`create company ${name} enableStock=${enableStock}`);
    await page.click('[data-screen="s-companies"]');
    await page.waitForTimeout(800);
    await page.click("#createCompanyBtn");
    await page.waitForTimeout(250);
    const taxId = String(Date.now()).slice(0, 13);
    await page.fill("#companyNameInput", name);
    await page.fill("#companyTaxIdInput", taxId);
    const toggle = page.locator("#companyEnableStockInput");
    const checked = await toggle.isChecked().catch(() => false);
    if (enableStock && !checked) await toggle.check();
    if (!enableStock && checked) await toggle.uncheck();
    const responsePromise = page.waitForResponse(
      (response) => /\/api\/v1\/admin\/companies$/.test(response.url()) && response.request().method() === "POST",
      { timeout: 30000 },
    );
    await page.click("#companyDrawerSaveBtn");
    const response = await responsePromise;
    const body = await response.json().catch(() => ({}));
    return {
      id: body.id || null,
      name,
      tax_id: taxId,
      enable_stock: !!enableStock,
      response_status: response.status(),
      response_body: body,
    };
  }

  async function selectTopbarCompany(companyId) {
    await page.selectOption("#topbarCompanySelect", companyId);
    await page.waitForTimeout(1200);
  }

  async function createUser({ email, username, displayName, role, companyId }) {
    logStep(`create user ${email} role=${role}`);
    await page.click('[data-screen="s-users"]');
    await page.waitForTimeout(800);
    await page.click('button:has-text("+ เพิ่มผู้ใช้")');
    await page.waitForTimeout(250);
    await page.fill("#userEmailInput", email);
    await page.fill("#userUsernameInput", username);
    await page.fill("#userDisplayNameInput", displayName);
    await page.selectOption("#userRoleSelect", role);
    if (companyId) {
      const companyCheckbox = page.locator(`#userCompanyCheckboxes .user-company-checkbox[value="${companyId}"]`);
      await expectVisible(companyCheckbox);
      await companyCheckbox.check();
    }
    const responsePromise = page.waitForResponse(
      (response) => /\/api\/v1\/admin\/users$/.test(response.url()) && response.request().method() === "POST",
      { timeout: 30000 },
    );
    await page.click("#userDrawerSaveBtn");
    const response = await responsePromise;
    const body = await response.json().catch(() => ({}));
    return {
      id: body.id || null,
      email,
      username,
      displayName,
      role,
      companyId,
      response_status: response.status(),
      response_body: body,
      temp_password_present: !!(body.temp_password || body.temporary_password),
    };
  }

  try {
    proof.deploy_ref = {
      expected_minimum_commit: "1f4d9646b20c574bcc0b101eed57c041ed373890",
      expected_current_head: "dev",
    };

    logStep("route checks");
    const routePaths = [
      ["/phase2", "phase2"],
      ["/phase2/prototype", "phase2-prototype"],
      ["/prototype", "prototype"],
      ["/workflow-demo", "workflow-demo"],
      ["/index.html", "index-html"],
    ];
    for (const [routePath, label] of routePaths) {
      await gotoAndMeasure(routePath, label, { waitMs: 700 });
    }
    await fetchRoute("/api/health");
    await fetchRoute("/api/health/ready");

    await loginAs(SYS_ADMIN_USER, SYS_ADMIN_PASS);
    const authRole = await captureAuthMeRole();
    proof.login.role = authRole || proof.login.role;
    await shot("01-logged-in-sys-admin");

    logStep("companies proof");
    const companyNoStock = await createCompany(`W5 Proof No-Stock ${Date.now()}`, false);
    const companyWithStock = await createCompany(`W5 Proof Stock ${Date.now()}`, true);
    proof.processing_live_proof.company_no_stock = companyNoStock;
    proof.processing_live_proof.company_with_stock = companyWithStock;
    await shot("02-companies-created");

    logStep("processing proof");
    await selectTopbarCompany(companyNoStock.id);
    await page.click('[data-screen="s-upload"]');
    await page.waitForTimeout(800);
    await page.setInputFiles("#uploadFileInput", [sampleDoc]);
    await page.waitForTimeout(800);
    proof.processing_live_proof.upload_file_count = await page.locator("#uploadFileCount").innerText().catch(() => "0");
    proof.processing_live_proof.upload_file_names = [path.basename(sampleDoc)];

    const uploadResponsePromise = page.waitForResponse(
      (response) => /\/api\/v1\/companies\/[0-9a-f-]+\/documents\/upload$/i.test(response.url()),
      { timeout: 30000 },
    );
    await page.click("#uploadSubmitBtn");
    const uploadResponse = await uploadResponsePromise;
    proof.processing_live_proof.upload_status = uploadResponse.status();
    proof.processing_live_proof.upload_url = uploadResponse.url();
    await page.waitForTimeout(1000);

    const startProcessingResponsePromise = page.waitForResponse(
      (response) => /\/api\/v1\/tasks\/process-document\//i.test(response.url()),
      { timeout: 30000 },
    ).catch(() => null);
    await page.click("#processingStartBtn");
    const startProcessingResponse = await startProcessingResponsePromise;
    if (startProcessingResponse) {
      proof.processing_live_proof.start_processing_status = startProcessingResponse.status();
      proof.processing_live_proof.start_processing_url = startProcessingResponse.url();
    }

    await expectVisible(page.locator("#processingRunningNote"));
    proof.processing_live_proof.percent_text_running = await page.locator("#processingPercentText").innerText().catch(() => null);
    proof.processing_live_proof.running_note_text = await page.locator("#processingRunningNote").innerText().catch(() => null);
    proof.processing_live_proof.table_snapshot_running = await page.locator("#processingTableBody").innerText().catch(() => null);
    await shot("03-processing-running-no-stock");

    await page.click('[data-screen="s-review-scan"]').catch(() => {});
    await page.waitForTimeout(1000);
    proof.processing_live_proof.review_scan_visible = await page.locator("#s-review-scan").isVisible().catch(() => false);
    proof.processing_live_proof.review_scan_summary_text = await page.locator("#reviewScanSummaryText").innerText().catch(() => null);
    proof.processing_live_proof.review_scan_list_text = await page.locator("#reviewScanListBody").innerText().catch(() => null);
    proof.processing_live_proof.review_scan_preview_text = await page.locator("#reviewScanPreviewBody").innerText().catch(() => null);
    await shot("04-review-scan-no-stock");

    await page.click('[data-screen="s-review-mapping"]');
    await page.waitForTimeout(1500);
    proof.processing_live_proof.review_mapping_count = await page.locator("#reviewMappingCount").innerText().catch(() => null);
    proof.processing_live_proof.review_mapping_list_text = await page.locator("#reviewMappingListBody").innerText().catch(() => null);
    proof.processing_live_proof.review_mapping_detail_text = await page.locator("#reviewMappingDetail").innerText().catch(() => null);
    await shot("05-review-mapping-no-stock");

    logStep("users proof");
    await page.click('[data-screen="s-users"]');
    await page.waitForTimeout(800);
    const createdUser = await createUser({
      email: `w5-sysadmin-${Date.now()}@ledgerflow.local`,
      username: `w5-sysadmin-${Date.now()}`,
      displayName: "W5 SysAdmin Proof",
      role: "sys_admin",
      companyId: companyNoStock.id,
    });
    proof.users_live_proof.created_user = {
      email: createdUser.email,
      role: createdUser.role,
      company_id: createdUser.companyId,
      response_status: createdUser.response_status,
      temp_password_present: createdUser.temp_password_present,
    };
    await shot("06-user-created-sysadmin");
    await page.click('#drawer-user button:has-text("ยกเลิก")').catch(() => {});
    const userRow = page.locator("#usersTableBody tr", { hasText: createdUser.email });
    await expectVisible(userRow);
    proof.users_live_proof.sys_admin_badge_visible = await userRow.locator(".badge-danger", { hasText: "SysAdmin" }).isVisible().catch(() => false);
    proof.users_live_proof.company_name_visible = await userRow.textContent().catch(() => "");
    proof.users_live_proof.raw_company_uuid_hidden = !(proof.users_live_proof.company_name_visible || "").includes(companyNoStock.id);
    await userRow.locator("button[onclick^='deactivateUserPrompt']").click();
    await expectVisible(page.locator("#modal-confirm"));
    await page.click("#confirmOkBtn");
    await page.waitForTimeout(1500);
    await shot("07-user-deactivated");
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    await page.click('[data-screen="s-users"]');
    await page.waitForTimeout(1000);
    const reloadedUserRow = page.locator("#usersTableBody tr", { hasText: createdUser.email });
    proof.users_live_proof.inactive_after_reload = await reloadedUserRow.textContent().catch(() => "");
    proof.users_live_proof.inactive_text_visible = /Inactive|ปิดใช้งาน/.test(proof.users_live_proof.inactive_after_reload || "");
    await shot("08-user-deactivated-after-reload");

    logStep("mapping docx proof");
    await page.click('[data-screen="s-companies"]');
    await page.waitForTimeout(800);
    const companyDetailButton = page.locator("#companiesTableBody button", { hasText: "⚙" }).first();
    await companyDetailButton.click();
    await page.waitForTimeout(1200);
    await page.locator("#s-company-detail .tab-bar").getByText("ตั้งค่า", { exact: true }).click();
    await page.waitForTimeout(800);
    await page.click("text=📁 นำเข้าจาก DOCX (AI)");
    await expectVisible(page.locator("#modal-import-mapping-docx"));
    await page.setInputFiles("#mappingDocxFileInput", mappingDocx);
    const previewResponsePromise = page.waitForResponse(
      (response) => /\/api\/v1\/companies\/[0-9a-f-]+\/mapping-rules\/import-docx$/i.test(response.url()),
      { timeout: 45000 },
    );
    await page.click("#mappingDocxExtractBtn");
    const previewResponse = await previewResponsePromise;
    proof.mapping_rules_docx_live_proof.preview_status = previewResponse.status();
    const previewBody = await previewResponse.json().catch(() => ({}));
    proof.mapping_rules_docx_live_proof.preview_rule_count = Array.isArray(previewBody.rules) ? previewBody.rules.length : null;
    await page.waitForFunction(() => document.querySelectorAll("#mappingDocxPreviewBody tr").length >= 2, null, { timeout: 90000 }).catch(() => {});
    proof.mapping_rules_docx_live_proof.preview_table_text = await page.locator("#mappingDocxPreviewBody").innerText().catch(() => null);
    await shot("09-mapping-docx-preview");
    await page.locator("#mappingDocxPreviewBody tr button:has-text('ลบ')").first().click();
    await page.waitForTimeout(500);
    proof.mapping_rules_docx_live_proof.preview_text_after_delete = await page.locator("#mappingDocxPreviewBody").innerText().catch(() => null);
    const confirmImportResponsePromise = page.waitForResponse(
      (response) => /\/api\/v1\/companies\/[0-9a-f-]+\/mapping-rules\/confirm$/i.test(response.url()),
      { timeout: 30000 },
    );
    await page.click("#mappingDocxConfirmBtn");
    const confirmImportResponse = await confirmImportResponsePromise;
    proof.mapping_rules_docx_live_proof.confirm_status = confirmImportResponse.status();
    proof.mapping_rules_docx_live_proof.confirm_body = await confirmImportResponse.json().catch(() => ({}));
    await shot("10-mapping-docx-confirmed");

    logStep("template configurator proof");
    await page.click('[data-screen="s-templates"]');
    await page.waitForTimeout(800);
    await page.click('button:has-text("สร้าง Template ใหม่")');
    await page.waitForTimeout(1000);
    proof.template_configurator_live_proof.active_screen = await page.locator("#s-template-configurator").isVisible().catch(() => false);
    proof.template_configurator_live_proof.configure_tab_visible = await page.locator("#configuratorTab-configure").isVisible().catch(() => false);
    proof.template_configurator_live_proof.upload_tab_visible = await page.locator("#configuratorTab-upload").isVisible().catch(() => false);
    proof.template_configurator_live_proof.runtime_columns_text = await page.locator("#configConfigureLiveColumns").innerText().catch(() => null);
    await shot("11-template-configurator-blank");

    logStep("w5-12 honesty check");
    await selectTopbarCompany(companyWithStock.id);
    await page.click('[data-screen="s-processing"]');
    await page.waitForTimeout(1000);
    proof.w5_12_classification.line_item_notice_visible = await page.locator("#processingLineItemNotice").isVisible().catch(() => false);
    proof.w5_12_classification.line_item_notice_text = await page.locator("#processingLineItemNotice").innerText().catch(() => null);
    proof.w5_12_classification.processing_summary_text = await page.locator("#processingSummaryText").innerText().catch(() => null);
    await page.click('[data-screen="s-review-scan"]').catch(() => {});
    await page.waitForTimeout(1000);
    proof.w5_12_classification.review_scan_text = await page.locator("#s-review-scan").innerText().catch(() => null);
    await page.click('[data-screen="s-review-mapping"]').catch(() => {});
    await page.waitForTimeout(1000);
    proof.w5_12_classification.review_mapping_text = await page.locator("#s-review-mapping").innerText().catch(() => null);
    await page.click('[data-screen="s-export"]').catch(() => {});
    await page.waitForTimeout(1000);
    proof.w5_12_classification.export_live_status = await page.locator("#exportLiveStatus").innerText().catch(() => null);
    proof.w5_12_classification.export_preview_text = await page.locator("#exportPreviewInline").innerText().catch(() => null);
    proof.w5_12_classification.export_columns_text = await page.locator("#exportColumnsBody").innerText().catch(() => null);
    await shot("12-w5-12-stock-company-check");

    const exportDownloadResponsePromise = page.waitForResponse(
      (response) => /\/api\/v1\/export$/i.test(response.url()),
      { timeout: 45000 },
    ).catch(() => null);
    await page.click("#exportDownloadPrimaryBtn");
    const exportDownloadResponse = await exportDownloadResponsePromise;
    if (exportDownloadResponse) {
      proof.w5_12_classification.export_download_status = exportDownloadResponse.status();
      proof.w5_12_classification.export_download_url = exportDownloadResponse.url();
    }
    proof.w5_12_classification.export_live_badge = await page.locator("#exportLiveBadge").innerText().catch(() => null);
    proof.w5_12_classification.export_live_status_after_download = await page.locator("#exportLiveStatus").innerText().catch(() => null);
    await shot("13-export-generated");

    proof.w5_12_classification.final_classification = {
      status: "NOT CLOSED unless enable_stock=true proves backend-driven line-item extraction/review/export end-to-end",
      honest_banner_only: !!proof.w5_12_classification.line_item_notice_visible,
      real_line_item_rows_confirmed: false,
      real_line_item_export_confirmed: false,
    };
  } catch (error) {
    proof.error = String(error && error.stack ? error.stack : error);
    await page.screenshot({ path: path.join(outputDir, "zz-error.png"), fullPage: true }).catch(() => {});
  } finally {
    proof.route_status_table = routeChecks;
    proof.network_events = events;
    fs.writeFileSync(path.join(outputDir, "summary.json"), JSON.stringify(proof, null, 2), "utf8");
    fs.writeFileSync(path.join(outputDir, "network-events.json"), JSON.stringify(events, null, 2), "utf8");
    await browser.close();
  }

  console.log(JSON.stringify({
    output_dir: outputDir,
    summary: path.join(outputDir, "summary.json"),
    status: proof.error ? "error" : "completed",
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});