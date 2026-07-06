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

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function getCompanyIdFromUrl(url) {
  const m = url.match(/\/api\/v1\/companies\/([^/]+)/i);
  return m ? m[1] : null;
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
  const SAMPLE_FILE = env.W4_DIAG_FILE || "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125257.pdf";

  const outDir = path.resolve(__dirname, "..", "test-results", "w4-upload-ocr-diagnosis-16", stamp());
  fs.mkdirSync(outDir, { recursive: true });

  const events = [];
  let currentTag = "boot";

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    baseURL: POC_URL,
    viewport: { width: 1600, height: 1200 },
    httpCredentials: {
      username: SIT_BASIC_USER,
      password: SIT_BASIC_PASS,
    },
  });
  const page = await context.newPage();

  page.on("response", async (res) => {
    const url = res.url();
    if (!url.includes("/api/")) return;
    let body = "";
    try {
      body = await res.text();
    } catch {
      body = "";
    }
    events.push({
      t: new Date().toISOString(),
      tag: currentTag,
      method: res.request().method(),
      status: res.status(),
      url,
      companyId: getCompanyIdFromUrl(url),
      bodyPreview: body.slice(0, 4000),
    });
  });

  const result = {
    doc_id: "W4-SIT-E2E-COPILOT-UPLOAD-OCR-RUNTIME-DIAGNOSIS-16",
    generated_at_utc: new Date().toISOString(),
    out_dir: outDir,
    sample_file: SAMPLE_FILE,
    session: {
      app_user: SIT_APP_USER,
      basic_auth_user: SIT_BASIC_USER,
    },
    steps: {},
    first_failing_boundary: null,
  };

  function mark(tag) {
    currentTag = tag;
  }

  try {
    mark("open");
    await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForTimeout(1500);

    const loginVisible = await page.locator("#login-screen").isVisible().catch(() => false);
    if (loginVisible) {
      mark("login");
      await page.fill("#loginUser", SIT_APP_USER);
      await page.fill("#loginPw", SIT_APP_PASS);
      await page.click("#loginForm button[type='submit']");
      await page.waitForTimeout(2500);
    }

    const forceVisible = await page.locator("#force-change-password-screen").isVisible().catch(() => false);
    result.steps.force_change_password_screen = forceVisible;
    if (forceVisible) {
      result.first_failing_boundary = {
        boundary: "auth_password_policy_gate",
        detail: "Force change password screen shown for this user",
      };
      await page.screenshot({ path: path.join(outDir, "00-force-change-password.png"), fullPage: true });
      throw new Error("Force change password gate blocks diagnosis flow for current credentials");
    }

    await page.waitForSelector("#app", { timeout: 60000 });
    await page.waitForTimeout(2000);

    const topbarValue = await page.$eval("#topbarCompanySelect", (el) => el.value).catch(() => "");
    result.steps.topbar_company_initial = topbarValue;

    mark("goto-upload");
    await page.click('[data-screen="s-upload"]');
    await page.waitForTimeout(1200);

    const uploadCompany = await page.$eval("#uploadCompanySelect", (el) => el.value).catch(() => "");
    result.steps.upload_company_selected = uploadCompany;

    await page.setInputFiles("#uploadFileInput", SAMPLE_FILE);
    await page.screenshot({ path: path.join(outDir, "01-upload-ready.png"), fullPage: true });

    mark("upload-post");
    const uploadRespPromise = page.waitForResponse(
      (res) => /\/api\/v1\/companies\/[0-9a-f-]+\/documents\/upload$/i.test(res.url()),
      { timeout: 120000 }
    );
    await page.click("#uploadSubmitBtn");
    const uploadResp = await uploadRespPromise;
    const uploadText = await uploadResp.text().catch(() => "");
    const uploadBody = safeJsonParse(uploadText);

    const uploadedDocId =
      uploadBody && Array.isArray(uploadBody.documents) && uploadBody.documents[0]
        ? uploadBody.documents[0].id
        : null;

    result.steps.upload = {
      status: uploadResp.status(),
      url: uploadResp.url(),
      bodyPreview: uploadText.slice(0, 1200),
      document_id: uploadedDocId,
      at_utc: new Date().toISOString(),
    };

    if (uploadResp.status() >= 400) {
      result.first_failing_boundary = {
        boundary: "upload_request",
        status: uploadResp.status(),
        detail: uploadText.slice(0, 600),
      };
      await page.screenshot({ path: path.join(outDir, "02-upload-failed.png"), fullPage: true });
      return;
    }

    mark("goto-processing");
    await page.click('[data-screen="s-processing"]');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(outDir, "03-processing-before-start.png"), fullPage: true });

    const processRespPromise = page
      .waitForResponse(
        (res) => {
          if (!/\/api\/v1\/documents\/[0-9a-f-]+\/process$/i.test(res.url())) return false;
          if (!uploadedDocId) return true;
          return res.url().includes(`/api/v1/documents/${uploadedDocId}/process`);
        },
        { timeout: 120000 }
      )
      .catch(() => null);

    mark("process-post");
    await page.click("#processingStartBtn").catch(() => {});
    const processResp = await processRespPromise;

    if (!processResp) {
      result.steps.process = {
        fired: false,
        at_utc: new Date().toISOString(),
      };
      result.first_failing_boundary = {
        boundary: "process_request_not_fired",
        detail: "No POST /api/v1/documents/{id}/process observed within timeout",
      };
      await page.screenshot({ path: path.join(outDir, "04-process-not-fired.png"), fullPage: true });
      return;
    }

    const processText = await processResp.text().catch(() => "");
    result.steps.process = {
      fired: true,
      status: processResp.status(),
      url: processResp.url(),
      bodyPreview: processText.slice(0, 1200),
      at_utc: new Date().toISOString(),
    };

    if (processResp.status() >= 400) {
      result.first_failing_boundary = {
        boundary: "process_request",
        status: processResp.status(),
        detail: processText.slice(0, 600),
      };
      await page.screenshot({ path: path.join(outDir, "05-process-failed.png"), fullPage: true });
      return;
    }

    result.first_failing_boundary = {
      boundary: "none",
      detail: "Upload and process requests both succeeded in this run",
    };
    await page.click('[data-screen="s-review-scan"]').catch(() => {});
    await page.waitForTimeout(1800);
    await page.screenshot({ path: path.join(outDir, "06-review-scan.png"), fullPage: true });
  } finally {
    fs.writeFileSync(path.join(outDir, "summary.json"), JSON.stringify(result, null, 2), "utf8");
    fs.writeFileSync(path.join(outDir, "network-events.json"), JSON.stringify(events, null, 2), "utf8");
    await browser.close();
  }

  console.log(JSON.stringify({ outDir, summary: path.join(outDir, "summary.json") }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
