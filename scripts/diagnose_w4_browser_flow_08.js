const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

function loadEnv(filePath) {
  const env = {};
  if (!fs.existsSync(filePath)) return env;
  for (const raw of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx === -1) continue;
    env[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  }
  return env;
}

async function main() {
  const env = {
    ...loadEnv(path.resolve(__dirname, "..", ".env.sit.local")),
    ...process.env,
  };

  const token = env.LF_TOKEN;
  if (!token) {
    throw new Error("LF_TOKEN is required. Mint a valid SIT token first and pass it in the environment.");
  }
  if (!env.POC_URL || !env.SIT_BASIC_USER || !env.SIT_BASIC_PASS) {
    throw new Error("POC_URL, SIT_BASIC_USER, and SIT_BASIC_PASS must be available via .env.sit.local or process env.");
  }

  const companyId = env.W4_COMPANY_ID || "7fef16e0-bb19-47fb-b9f6-0540993142a9";
  const files = [
    env.W4_FILE_1 || "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125257.pdf",
    env.W4_FILE_2 || "D:/01_gitrepo/ai-accounting-copilot/private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125316.pdf",
  ];

  const outDir = path.resolve(__dirname, "..", "test-results", "w4-browser-flow-diagnosis-08-script");
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    baseURL: env.POC_URL,
    httpCredentials: {
      username: env.SIT_BASIC_USER,
      password: env.SIT_BASIC_PASS,
    },
    viewport: { width: 1440, height: 1200 },
  });
  await context.addInitScript((tk) => {
    window.localStorage.setItem("lf_token", tk);
  }, token);

  const page = await context.newPage();
  const events = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.type() === "warning") {
      events.push({ type: "console", level: msg.type(), text: msg.text() });
    }
  });
  page.on("request", (req) => {
    if (req.url().includes("/api/")) {
      events.push({ type: "request", method: req.method(), url: req.url() });
    }
  });
  page.on("response", async (res) => {
    if (!res.url().includes("/api/")) return;
    let text = "";
    try {
      text = (await res.text()).slice(0, 300);
    } catch {
      text = "";
    }
    events.push({ type: "response", status: res.status(), url: res.url(), text });
  });

  await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(4000);
  await page.screenshot({ path: path.join(outDir, "01-dashboard.png"), fullPage: true });

  await page.click('.nav-item[data-screen="s-upload"]');
  await page.waitForTimeout(1000);
  await page.selectOption("#uploadCompanySelect", companyId);
  await page.screenshot({ path: path.join(outDir, "02-upload-company-selected.png"), fullPage: true });

  await page.setInputFiles("#uploadFileInput", files);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(outDir, "03-upload-files-selected.png"), fullPage: true });

  await page.click("#uploadSubmitBtn");
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(outDir, "04-processing-after-upload.png"), fullPage: true });

  await page.click("#processingStartBtn").catch(() => {});
  await page.waitForTimeout(25000);
  await page.screenshot({ path: path.join(outDir, "05-review-scan-after-processing.png"), fullPage: true });

  await page.click("text=✓ Approve All ที่เหลือ").catch(() => {});
  await page.waitForTimeout(4000);
  await page.screenshot({ path: path.join(outDir, "06-after-approve-all.png"), fullPage: true });

  const summary = {
    companyId,
    files,
    uploadRequests: events.filter((e) => String(e.url || "").includes("/documents/upload")),
    processRequests: events.filter((e) => String(e.url || "").match(/\/api\/v1\/documents\/.+\/process$/)),
    approveRequests: events.filter(
      (e) => String(e.url || "").includes("/documents/approve-all") || String(e.url || "").match(/\/api\/v1\/documents\/.+\/approve$/),
    ),
    consoleEvents: events.filter((e) => e.type === "console"),
  };
  fs.writeFileSync(path.join(outDir, "summary.json"), JSON.stringify(summary, null, 2), "utf8");

  await browser.close();
  console.log(JSON.stringify({ outDir, summaryFile: path.join(outDir, "summary.json") }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});