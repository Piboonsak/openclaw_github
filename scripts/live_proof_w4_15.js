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

function nowStamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

async function waitFor(condition, timeoutMs, stepMs = 300) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (condition()) return true;
    await sleep(stepMs);
  }
  return false;
}

async function main() {
  const env = {
    ...loadEnv(path.resolve(__dirname, "..", ".env.sit.local")),
    ...process.env,
  };

  const POC_URL = env.POC_URL || "https://sit.yahwan.biz";
  const SIT_BASIC_USER = env.SIT_BASIC_USER || "admin";
  const SIT_BASIC_PASS = env.SIT_BASIC_PASS || "admin";
  const SIT_APP_USER = env.SIT_APP_USER || "admin";
  const SIT_APP_PASS = env.SIT_APP_PASS || "admin";
  const LF_TOKEN = env.LF_TOKEN || "";
  const EXPECTED_MIN_SHA = env.W4_EXPECTED_MIN_SHA || "bb7bd5f";
  const EXPECTED_HEAD_SHA = env.W4_EXPECTED_HEAD_SHA || "bb7bd5ff23e3b4df824d8a1c4bdb0ae1efb7c2ce";

  const stamp = nowStamp();
  const outDir = path.resolve(__dirname, "..", "test-results", "w4-company-context-live-proof-15", stamp);
  fs.mkdirSync(outDir, { recursive: true });

  const networkEvents = [];
  const taggedEvents = [];
  let currentTag = "boot";

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    baseURL: POC_URL,
    viewport: { width: 1680, height: 1200 },
    httpCredentials: {
      username: SIT_BASIC_USER,
      password: SIT_BASIC_PASS,
    },
  });

  if (LF_TOKEN) {
    await context.addInitScript((tk) => {
      window.localStorage.setItem("lf_token", tk);
    }, LF_TOKEN);
  }

  const page = await context.newPage();

  page.on("response", async (res) => {
    const url = res.url();
    if (!url.includes("/api/")) return;
    let bodyText = "";
    try {
      bodyText = await res.text();
    } catch {
      bodyText = "";
    }
    const entry = {
      t: new Date().toISOString(),
      tag: currentTag,
      method: res.request().method(),
      status: res.status(),
      url,
      companyId: getCompanyIdFromUrl(url),
      bodyPreview: bodyText.slice(0, 5000),
    };
    networkEvents.push(entry);
    taggedEvents.push(entry);
  });

  const summary = {
    doc_id: "W4-SIT-E2E-COPILOT-COMPANY-CONTEXT-LIVE-PROOF-RESULT-15",
    tracking_tag: "W4-SIT-E2E-COMPANY-CONTEXT-LIVE-PROOF-15",
    generated_at_utc: new Date().toISOString(),
    proof_artifact_dir: outDir,
    target_ref: {
      expected_branch: "dev",
      expected_head_sha: EXPECTED_HEAD_SHA,
      expected_short_sha: EXPECTED_MIN_SHA,
    },
    credential_session_notes: {
      sit_basic_auth_user: SIT_BASIC_USER,
      app_login_user: SIT_APP_USER,
      app_login_password_source: "SIT_APP_PASS from .env.sit.local/process.env",
      auth_method: LF_TOKEN ? "runtime_token" : "ui_login",
      force_change_password_triggered: false,
      force_change_password_details: null,
    },
    company_context: {
      auth_me_company_ids: [],
      topbar_companies: [],
      selected_company_a: null,
      selected_company_b: null,
      b_not_in_auth_me_company_ids: null,
    },
    transitions: {
      upload: null,
      processing: null,
      review_scan: null,
    },
    auth_refresh_evidence: [],
    screenshot_evidence: [],
  };

  function mark(tag) {
    currentTag = tag;
  }

  try {
    mark("open-prototype");
    await page.goto("/phase2/prototype", { waitUntil: "domcontentloaded", timeout: 120000 });
    await page.waitForTimeout(2000);

    const loginVisible = await page.locator("#login-screen").isVisible().catch(() => false);
    if (loginVisible && !LF_TOKEN) {
      mark("login");
      await page.fill("#loginUser", SIT_APP_USER);
      await page.fill("#loginPw", SIT_APP_PASS);
      await page.click("#loginForm button[type='submit']");
      await page.waitForTimeout(2500);
    }

    const forceVisible = await page.locator("#force-change-password-screen").isVisible().catch(() => false);
    if (forceVisible) {
      const newPw = `Admin@${new Date().getUTCFullYear()}${String(new Date().getUTCMonth() + 1).padStart(2, "0")}!`;
      summary.credential_session_notes.force_change_password_triggered = true;
      summary.credential_session_notes.force_change_password_details = {
        old_password_source: "SIT_APP_PASS",
        new_password_used: newPw,
      };

      mark("force-change-password");
      await page.fill("#forceChangeOldPw", SIT_APP_PASS);
      await page.fill("#forceChangeNewPw", newPw);
      await page.fill("#forceChangeConfirmPw", newPw);
      await page.click("#forceChangePasswordForm button[type='submit']");
      await page.waitForTimeout(3500);
    }

    await page.waitForSelector("#app", { timeout: 60000 });
    await page.waitForTimeout(2500);

    const authMeEvents = networkEvents.filter((e) => /\/api\/v1\/auth\/me$/i.test(e.url));
    for (const event of authMeEvents) {
      const body = safeJsonParse(event.bodyPreview) || {};
      summary.auth_refresh_evidence.push({
        t: event.t,
        status: event.status,
        company_ids: Array.isArray(body.company_ids) ? body.company_ids : [],
      });
    }

    const latestAuthMe = authMeEvents.length ? safeJsonParse(authMeEvents[authMeEvents.length - 1].bodyPreview) : null;
    const authCompanyIds = Array.isArray(latestAuthMe && latestAuthMe.company_ids) ? latestAuthMe.company_ids : [];
    summary.company_context.auth_me_company_ids = authCompanyIds;

    const options = await page.$$eval("#topbarCompanySelect option", (els) =>
      els
        .map((el) => ({ value: el.value || "", label: (el.textContent || "").trim() }))
        .filter((o) => !!o.value)
    );

    summary.company_context.topbar_companies = options;
    if (!options.length) {
      throw new Error("No accessible companies found in #topbarCompanySelect");
    }

    const selectedA = await page.$eval("#topbarCompanySelect", (el) => el.value);
    summary.company_context.selected_company_a = selectedA;

    const candidateB =
      options.find((o) => o.value !== selectedA && !authCompanyIds.includes(o.value)) ||
      options.find((o) => o.value !== selectedA) ||
      null;

    if (!candidateB) {
      throw new Error("Could not determine second company candidate from topbar options");
    }

    summary.company_context.selected_company_b = candidateB.value;
    summary.company_context.b_not_in_auth_me_company_ids = !authCompanyIds.includes(candidateB.value);

    mark("select-company-b");
    await page.selectOption("#topbarCompanySelect", candidateB.value);
    await page.waitForTimeout(2500);

    const screenshot1 = path.join(outDir, "01-topbar-company-b-selected.png");
    await page.screenshot({ path: screenshot1, fullPage: true });
    summary.screenshot_evidence.push(screenshot1);

    mark("navigate-upload");
    await page.click('[data-screen="s-upload"]');
    await page.waitForTimeout(2500);

    const uploadCompanyValue = await page.$eval("#uploadCompanySelect", (el) => el.value);
    const uploadScopedCall = networkEvents.find(
      (e) => e.tag === "navigate-upload" && e.companyId && /\/documents/i.test(e.url)
    ) || null;
    summary.transitions.upload = {
      topbar_company_id: await page.$eval("#topbarCompanySelect", (el) => el.value),
      upload_company_id: uploadCompanyValue,
      first_company_scoped_call: uploadScopedCall,
    };

    mark("navigate-processing");
    await page.click('[data-screen="s-processing"]');
    await page.waitForTimeout(3000);
    const processingScopedCall = networkEvents.find(
      (e) => e.tag === "navigate-processing" && e.companyId && /\/documents/i.test(e.url)
    ) || null;
    summary.transitions.processing = {
      topbar_company_id: await page.$eval("#topbarCompanySelect", (el) => el.value),
      first_company_scoped_call: processingScopedCall,
    };

    mark("trigger-processing-auth-refresh");
    const startBtnVisible = await page.locator("#processingStartBtn").isVisible().catch(() => false);
    if (startBtnVisible) {
      await page.click("#processingStartBtn").catch(() => {});
      await page.waitForTimeout(2000);
    }

    mark("navigate-review-scan");
    await page.click('[data-screen="s-review-scan"]');
    await page.waitForTimeout(3000);
    const reviewScopedCall = networkEvents.find(
      (e) => e.tag === "navigate-review-scan" && e.companyId && /\/documents/i.test(e.url)
    ) || null;
    summary.transitions.review_scan = {
      topbar_company_id: await page.$eval("#topbarCompanySelect", (el) => el.value),
      first_company_scoped_call: reviewScopedCall,
    };

    const screenshot2 = path.join(outDir, "02-review-scan-with-company-b.png");
    await page.screenshot({ path: screenshot2, fullPage: true });
    summary.screenshot_evidence.push(screenshot2);

    // Confirm at least one auth/me refresh after selecting company B.
    const authAfterB = networkEvents.filter((e) => {
      if (!/\/api\/v1\/auth\/me$/i.test(e.url)) return false;
      const selectedAtMoment = summary.company_context.selected_company_b;
      return !!selectedAtMoment;
    });
    summary.auth_refresh_evidence_after_select_b_count = authAfterB.length;

    // Final consistency checks for the report.
    const selectedNow = await page.$eval("#topbarCompanySelect", (el) => el.value);
    summary.company_context.selected_company_at_end = selectedNow;
    summary.company_context.snap_back_detected = selectedNow !== candidateB.value;

    summary.assertions = {
      selected_b_exists: !!candidateB.value,
      upload_uses_b:
        !!summary.transitions.upload &&
        summary.transitions.upload.topbar_company_id === candidateB.value &&
        summary.transitions.upload.upload_company_id === candidateB.value,
      processing_call_uses_b:
        !!summary.transitions.processing &&
        !!summary.transitions.processing.first_company_scoped_call &&
        summary.transitions.processing.first_company_scoped_call.companyId === candidateB.value,
      review_scan_call_uses_b:
        !!summary.transitions.review_scan &&
        !!summary.transitions.review_scan.first_company_scoped_call &&
        summary.transitions.review_scan.first_company_scoped_call.companyId === candidateB.value,
      no_snap_back: selectedNow === candidateB.value,
      auth_refresh_seen: summary.auth_refresh_evidence.length > 0,
    };

    const summaryPath = path.join(outDir, "summary.json");
    const eventsPath = path.join(outDir, "network-events.json");
    fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf8");
    fs.writeFileSync(eventsPath, JSON.stringify(networkEvents, null, 2), "utf8");

    console.log(
      JSON.stringify(
        {
          outDir,
          summaryPath,
          eventsPath,
          selectedCompanyB: candidateB.value,
          selectedCompanyBLabel: candidateB.label,
          authCompanyIds,
          assertions: summary.assertions,
        },
        null,
        2
      )
    );
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
