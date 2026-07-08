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
  const SIT_APP_USER = env.SIT_APP_USER || "sit-admin@ledgerflow.local";
  const SIT_APP_PASS = env.SIT_APP_PASS || "admin123456";
  const FILES = [
    "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026130449.pdf",
    "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026130503.pdf",
    "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026130520.pdf",
  ];

  const outDir = path.resolve(__dirname, "..", "test-results", "w4-processing-celery-fix-20", stamp());
  fs.mkdirSync(outDir, { recursive: true });

  const events = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    baseURL: POC_URL,
    viewport: { width: 1700, height: 1200 },
    httpCredentials: { username: SIT_BASIC_USER, password: SIT_BASIC_PASS },
  });
  const page = await context.newPage();

  page.on("response", async (res) => {
    const url = res.url();
    if (!url.includes("/api/")) return;
    events.push({ t: new Date().toISOString(), method: res.request().method(), status: res.status(), url });
  });

  const result = { generated_at_utc: new Date().toISOString(), out_dir: outDir, steps: {} };

  try {
    await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForTimeout(1500);

    const loginVisible = await page.locator("#login-screen").isVisible().catch(() => false);
    if (loginVisible) {
      await page.fill("#loginUser", SIT_APP_USER);
      await page.fill("#loginPw", SIT_APP_PASS);
      await page.click("#loginForm button[type='submit']");
      await page.waitForTimeout(2500);
    }
    await page.waitForSelector("#app", { timeout: 60000 });
    await page.waitForTimeout(1500);

    await page.click('[data-screen="s-upload"]');
    await page.waitForTimeout(1000);
    await page.setInputFiles("#uploadFileInput", FILES);
    await page.waitForTimeout(500);
    result.steps.file_count_selected = await page.locator("#uploadFileCount").innerText().catch(() => null);

    const uploadRespPromise = page
      .waitForResponse((res) => /\/api\/v1\/companies\/[0-9a-f-]+\/documents\/upload$/i.test(res.url()), { timeout: 30000 })
      .catch(() => null);
    await page.click("#uploadSubmitBtn");
    const uploadResp = await uploadRespPromise;
    result.steps.upload = uploadResp ? { status: uploadResp.status() } : { fired: false };

    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outDir, "01-processing-before-start.png"), fullPage: true });

    // Capture table state right after clicking Start (should show parallel "stage" labels, not one at a time).
    await page.click("#processingStartBtn");
    await page.waitForTimeout(1800);
    await page.screenshot({ path: path.join(outDir, "02-processing-parallel-stages.png"), fullPage: true });
    result.steps.mid_run_table_html = await page.locator("#processingTableBody").innerHTML().catch(() => null);
    result.steps.mid_run_percent_text = await page.locator("#processingPercentText").innerText().catch(() => null);
    result.steps.mid_run_summary_text = await page.locator("#processingSummaryText").innerText().catch(() => null);

    // Track distinct in-flight task-status polling calls to prove concurrency.
    await page.waitForTimeout(2500);
    const taskCalls = events.filter((e) => /\/api\/v1\/tasks\//.test(e.url));
    const distinctTaskIds = new Set(
      taskCalls.map((e) => (e.url.match(/\/api\/v1\/tasks\/([a-f0-9-]+)/i) || [])[1]).filter(Boolean)
    );
    result.steps.distinct_concurrent_task_ids_seen = Array.from(distinctTaskIds);

    await page.waitForSelector("#s-review-scan", { state: "visible", timeout: 180000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(outDir, "03-review-scan-after-processing.png"), fullPage: true });

    result.steps.review_scan_list_html = await page.locator("#reviewScanListBody").innerHTML().catch(() => null);

    const previewBox = await page.locator("#reviewScanPreviewBody").boundingBox().catch(() => null);
    result.steps.review_scan_preview_box_height_px = previewBox ? previewBox.height : null;
  } finally {
    fs.writeFileSync(path.join(outDir, "summary.json"), JSON.stringify(result, null, 2), "utf8");
    fs.writeFileSync(path.join(outDir, "network-events.json"), JSON.stringify(events, null, 2), "utf8");
    await browser.close();
  }

  console.log(JSON.stringify({ outDir, steps: result.steps }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
