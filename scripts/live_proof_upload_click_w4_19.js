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
  const SAMPLE_FILE =
    env.W4_DIAG_FILE ||
    "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125257.pdf";

  const outDir = path.resolve(
    __dirname,
    "..",
    "test-results",
    "w4-upload-click-fix-19",
    stamp()
  );
  fs.mkdirSync(outDir, { recursive: true });

  const events = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    baseURL: POC_URL,
    viewport: { width: 1600, height: 1200 },
    httpCredentials: { username: SIT_BASIC_USER, password: SIT_BASIC_PASS },
  });
  const page = await context.newPage();

  page.on("response", async (res) => {
    const url = res.url();
    if (!url.includes("/api/")) return;
    events.push({ t: new Date().toISOString(), method: res.request().method(), status: res.status(), url });
  });

  const result = {
    doc_id: "W4-SIT-E2E-COPILOT-UPLOAD-CLICK-FIX-RESULT-19",
    generated_at_utc: new Date().toISOString(),
    out_dir: outDir,
    target_ref: { branch: "dev", minimum_commit: "52b0544" },
    steps: {},
    acceptance: {},
  };

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
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(outDir, "01-upload-screen-before-click.png"), fullPage: true });

    // Step: click the visible dropzone and prove the native file picker opens.
    const fileChooserPromise = page.waitForEvent("filechooser", { timeout: 15000 });
    await page.click("#uploadDropzone");
    let fileChooserOpened = false;
    let fileChooserError = null;
    try {
      const fileChooser = await fileChooserPromise;
      fileChooserOpened = true;
      await fileChooser.setFiles(SAMPLE_FILE);
    } catch (err) {
      fileChooserError = String(err);
    }
    result.steps.dropzone_click_filechooser = {
      opened: fileChooserOpened,
      error: fileChooserError,
    };

    await page.waitForTimeout(1000);
    const fileCountText = await page.locator("#uploadFileCount").innerText().catch(() => null);
    const fileListText = await page.locator("#uploadFileListBody").innerText().catch(() => null);
    result.steps.file_list_state = {
      uploadFileCount: fileCountText,
      uploadFileListBodyContainsFile: !!(fileListText && fileListText.includes(path.basename(SAMPLE_FILE))),
    };
    await page.screenshot({ path: path.join(outDir, "02-upload-screen-after-file-selected.png"), fullPage: true });

    // Step: click Upload and capture whether the real upload POST fires.
    const uploadRespPromise = page
      .waitForResponse((res) => /\/api\/v1\/companies\/[0-9a-f-]+\/documents\/upload$/i.test(res.url()), {
        timeout: 30000,
      })
      .catch(() => null);
    await page.click("#uploadSubmitBtn").catch(() => {});
    const uploadResp = await uploadRespPromise;

    if (uploadResp) {
      const uploadText = await uploadResp.text().catch(() => "");
      result.steps.upload_post = {
        fired: true,
        status: uploadResp.status(),
        url: uploadResp.url(),
        bodyPreview: uploadText.slice(0, 500),
      };
    } else {
      result.steps.upload_post = { fired: false };
    }

    await page.waitForTimeout(1500);
    const navigatedToProcessing = await page.locator("#s-processing").isVisible().catch(() => false);
    result.steps.navigated_to_processing = navigatedToProcessing;
    await page.screenshot({ path: path.join(outDir, "03-after-upload-submit.png"), fullPage: true });

    result.acceptance = {
      dropzone_opens_native_picker: fileChooserOpened,
      file_list_updates: result.steps.file_list_state.uploadFileCount === "1" &&
        result.steps.file_list_state.uploadFileListBodyContainsFile,
      upload_post_fires: !!(result.steps.upload_post && result.steps.upload_post.fired),
      first_failing_boundary: !fileChooserOpened
        ? "dropzone_click"
        : !(result.steps.file_list_state.uploadFileCount === "1")
        ? "file_chooser_to_list_render"
        : !(result.steps.upload_post && result.steps.upload_post.fired)
        ? "upload_post"
        : "none",
    };
  } finally {
    fs.writeFileSync(path.join(outDir, "summary.json"), JSON.stringify(result, null, 2), "utf8");
    fs.writeFileSync(path.join(outDir, "network-events.json"), JSON.stringify(events, null, 2), "utf8");
    await browser.close();
  }

  console.log(JSON.stringify({ outDir, summary: path.join(outDir, "summary.json"), acceptance: result.acceptance }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
