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

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForStatusEvent(events, predicate, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const found = events.find(predicate);
    if (found) return found;
    await wait(400);
  }
  return null;
}

async function main() {
  const env = {
    ...loadEnv(path.resolve(__dirname, "..", ".env.sit.local")),
    ...process.env,
  };

  const token = env.LF_TOKEN;
  if (!token) throw new Error("LF_TOKEN is required");
  if (!env.POC_URL || !env.SIT_BASIC_USER || !env.SIT_BASIC_PASS) {
    throw new Error("POC_URL, SIT_BASIC_USER, SIT_BASIC_PASS are required");
  }

  const companyId = env.W4_COMPANY_ID || "78ea65ed-d929-4b20-8bcd-b0a06ddece8b";
  const routineCompanyId = env.W4_ROUTINE_COMPANY_ID || "7fef16e0-bb19-47fb-b9f6-0540993142a9";
  const companyName = env.W4_COMPANY_NAME || "บริษัท ฤทธิ์ล้ำเลิศ จำกัด";
  const coaPdf = env.W4_COA_PDF || "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ ผังบัญชี.pdf";
  const file1 = env.W4_FILE_1 || "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125257.pdf";
  const file2 = env.W4_FILE_2 || "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125316.pdf";

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const outDir = path.resolve(__dirname, "..", "test-results", "w4-live-proof-12", stamp);
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    baseURL: env.POC_URL,
    viewport: { width: 1600, height: 1400 },
    httpCredentials: {
      username: env.SIT_BASIC_USER,
      password: env.SIT_BASIC_PASS,
    },
  });

  await context.addInitScript((tk) => {
    window.localStorage.setItem("lf_token", tk);
  }, token);

  const page = await context.newPage();
  const events = [];

  page.on("response", async (res) => {
    if (!res.url().includes("/api/")) return;
    let text = "";
    try {
      text = (await res.text()).slice(0, 500);
    } catch {
      text = "";
    }
    events.push({
      t: new Date().toISOString(),
      kind: "response",
      method: res.request().method(),
      status: res.status(),
      url: res.url(),
      text,
    });
  });

  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.type() === "warning") {
      events.push({ t: new Date().toISOString(), kind: "console", level: msg.type(), text: msg.text() });
    }
  });

  const summary = {
    meta: {
      companyId,
      routineCompanyId,
      companyName,
      coaPdf,
      files: [file1, file2],
      outDir,
    },
    lp01: {},
    lp02: {},
    console: [],
  };

  await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 90000 });
  await page.waitForTimeout(3000);

  // LP-01: Company COA PDF async
  await page.click('[data-screen="s-companies"]');
  await page.waitForTimeout(1000);
  await page.locator("#companiesTableBody tr", { hasText: companyName }).first().locator("button:has-text('ตั้งค่า')").click();
  await page.waitForTimeout(1000);
  await page.locator("#s-company-detail .tab-bar").getByText("ตั้งค่า", { exact: true }).click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(outDir, "lp01-01-company-detail.png"), fullPage: true });

  await page.evaluate(() => {
    if (typeof window.openCoaPdfModal === "function") {
      window.openCoaPdfModal();
    }
  });
  await page.waitForSelector("#modal-import-coa-pdf.open", { timeout: 10000 });
  await page.setInputFiles("#coaPdfFileInput", coaPdf);

  const startRespPromise = page.waitForResponse((res) => res.url().includes("/coa/import-pdf-async") && !/import-pdf-async\/.+/.test(res.url()), { timeout: 30000 });
  await page.click("#coaPdfExtractBtn");
  const startResp = await startRespPromise;
  const startJson = await startResp.json().catch(() => ({}));
  const taskId = startJson.task_id || null;

  summary.lp01.start = {
    status: startResp.status(),
    url: startResp.url(),
    body: startJson,
  };

  await page.screenshot({ path: path.join(outDir, "lp01-02-progress-running.png"), fullPage: true });

  const succeededEvent = await waitForStatusEvent(
    events,
    (e) => e.kind === "response" && e.url.includes("/coa/import-pdf-async/") && e.status === 200 && e.text.includes('"status":"succeeded"'),
    360000,
  );

  summary.lp01.pollSucceededSeen = Boolean(succeededEvent);
  summary.lp01.pollSucceededEvent = succeededEvent || null;

  await page.waitForSelector("#coaPdfReviewStep", { state: "visible", timeout: 120000 });
  const previewRows = await page.locator("#coaPdfPreviewBody tr").count();
  summary.lp01.reviewRows = previewRows;

  await page.screenshot({ path: path.join(outDir, "lp01-03-review-table.png"), fullPage: true });

  const confirmRespPromise = page.waitForResponse((res) => res.url().includes("/coa/confirm"), { timeout: 30000 });
  await page.click("#coaPdfConfirmBtn");
  const confirmResp = await confirmRespPromise;
  let confirmJson = {};
  try {
    confirmJson = await confirmResp.json();
  } catch {
    confirmJson = {};
  }

  summary.lp01.confirm = {
    status: confirmResp.status(),
    url: confirmResp.url(),
    body: confirmJson,
    taskId,
  };

  // LP-02: Upload -> Processing -> Review Scan -> Mapping
  await page.click('[data-screen="s-upload"]');
  await page.waitForTimeout(1000);
  await page.selectOption("#uploadCompanySelect", routineCompanyId);
  await page.setInputFiles("#uploadFileInput", [file1, file2]);
  await page.screenshot({ path: path.join(outDir, "lp02-01-upload-ready.png"), fullPage: true });

  const uploadRespPromise = page.waitForResponse((res) => res.url().includes(`/companies/${routineCompanyId}/documents/upload`), { timeout: 90000 });
  await page.click("#uploadSubmitBtn");
  const uploadResp = await uploadRespPromise;
  const uploadJson = await uploadResp.json().catch(() => ({}));
  summary.lp02.upload = {
    status: uploadResp.status(),
    url: uploadResp.url(),
    count: Array.isArray(uploadJson.documents) ? uploadJson.documents.length : null,
    documentIds: Array.isArray(uploadJson.documents) ? uploadJson.documents.map((d) => d.id) : [],
  };

  await page.screenshot({ path: path.join(outDir, "lp02-02-processing-screen.png"), fullPage: true });

  await page.click("#processingStartBtn");
  await page.waitForTimeout(20000);
  await page.screenshot({ path: path.join(outDir, "lp02-03-review-scan.png"), fullPage: true });

  const processResponses = events.filter((e) => e.kind === "response" && /\/api\/v1\/documents\/.+\/process$/.test(e.url));
  summary.lp02.process = {
    count: processResponses.length,
    statuses: processResponses.map((e) => e.status),
  };

  const firstReviewItem = page.locator("#reviewScanListBody li").first();
  await firstReviewItem.click();
  await page.waitForTimeout(800);

  const approveOnePromise = page.waitForResponse((res) => /\/api\/v1\/documents\/.+\/approve$/.test(res.url()), { timeout: 30000 });
  await page.click("#reviewScanApproveBtn");
  const approveOneResp = await approveOnePromise;
  summary.lp02.approveOne = {
    status: approveOneResp.status(),
    url: approveOneResp.url(),
  };

  const approveAllPromise = page.waitForResponse((res) => res.url().includes(`/companies/${routineCompanyId}/documents/approve-all`), { timeout: 30000 });
  await page.click("button:has-text('✓ Approve All ที่เหลือ')");
  const approveAllResp = await approveAllPromise;
  let approveAllJson = {};
  try {
    approveAllJson = await approveAllResp.json();
  } catch {
    approveAllJson = {};
  }
  summary.lp02.approveAll = {
    status: approveAllResp.status(),
    url: approveAllResp.url(),
    body: approveAllJson,
  };

  await page.click("button:has-text('ไปที่ Review Mapping →')");
  await page.waitForTimeout(1500);
  const mappingCountText = await page.locator("#reviewMappingCount").innerText().catch(() => "0");
  summary.lp02.reviewMappingCount = Number(mappingCountText || "0");

  await page.screenshot({ path: path.join(outDir, "lp02-04-review-mapping.png"), fullPage: true });

  const mappingItems = page.locator("#reviewMappingListBody li");
  const mappingItemsCount = await mappingItems.count();
  summary.lp02.mappingItemsCount = mappingItemsCount;

  if (mappingItemsCount > 0) {
    await mappingItems.first().click();
    await page.waitForTimeout(1200);
    const confirmBtn = page.locator("#confirmMappingBtn");
    const disabled = await confirmBtn.isDisabled().catch(() => true);
    summary.lp02.confirmButtonDisabled = disabled;
    if (!disabled) {
      const confirmRespPromise = page.waitForResponse((res) => /\/api\/v1\/journal-vouchers\/.+\/confirm$/.test(res.url()), { timeout: 30000 });
      await confirmBtn.click();
      const confirmResp = await confirmRespPromise;
      summary.lp02.confirmMapping = {
        status: confirmResp.status(),
        url: confirmResp.url(),
      };
    } else {
      summary.lp02.confirmMapping = {
        status: null,
        url: null,
      };
    }
  }

  summary.console = events.filter((e) => e.kind === "console");

  summary.events = {
    coaAsyncStatusCalls: events.filter((e) => e.kind === "response" && e.url.includes("/coa/import-pdf-async/")),
    uploadCalls: events.filter((e) => e.kind === "response" && e.url.includes("/documents/upload")),
    approveCalls: events.filter((e) => e.kind === "response" && (e.url.includes("/documents/approve-all") || /\/api\/v1\/documents\/.+\/approve$/.test(e.url))),
    confirmCalls: events.filter((e) => e.kind === "response" && e.url.includes("/journal-vouchers/") && e.url.endsWith("/confirm")),
  };

  fs.writeFileSync(path.join(outDir, "summary.json"), JSON.stringify(summary, null, 2), "utf8");
  fs.writeFileSync(path.join(outDir, "events.json"), JSON.stringify(events, null, 2), "utf8");

  await browser.close();
  console.log(JSON.stringify({ outDir, summaryFile: path.join(outDir, "summary.json") }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
