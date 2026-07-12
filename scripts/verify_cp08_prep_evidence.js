const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const { chromium, request } = require("playwright");

function loadEnv(filePath) {
  if (!fs.existsSync(filePath)) return;
  const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/);
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim().replace(/^"|"$/g, "");
    if (!process.env[key]) process.env[key] = value;
  }
}

function mustEnv(name) {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env: ${name}`);
  return v;
}

function stamp() {
  return new Date().toISOString().replace(/[.:]/g, "-");
}

function runCurl(cmd) {
  try {
    const out = execSync(cmd, { stdio: ["ignore", "pipe", "pipe"], encoding: "utf8" });
    return { ok: true, output: out.trim() };
  } catch (error) {
    const stdout = error.stdout ? String(error.stdout) : "";
    const stderr = error.stderr ? String(error.stderr) : "";
    return { ok: false, output: `${stdout}\n${stderr}`.trim(), code: error.status };
  }
}

function matchW5Company(name) {
  return ["W5H06", "W5 Proof", "SIT Verify", "CP-08"].some((p) => String(name || "").startsWith(p));
}

function matchW5User(user) {
  const email = String(user.email || "").toLowerCase();
  const username = String(user.username || "").toLowerCase();
  const display = String(user.display_name || "").toLowerCase();
  const [localPart, domain] = email.includes("@") ? email.split("@") : ["", ""];

  const patterns = [
    /^w5h06[-_]/,
    /^w5-proof[-_]/,
    /^w5-sysadmin-/,
    /^w5-h06-/,
    /^sit-verify[-_]/,
    /^cp-?08[-_]/,
  ];

  const matched = patterns.some((rx) => rx.test(username) || rx.test(display) || rx.test(localPart));
  if (!matched) return false;
  if (domain) return domain === "ledgerflow.local";
  return true;
}

async function main() {
  const repoRoot = path.resolve(__dirname, "..");
  loadEnv(path.join(repoRoot, ".env.sit.local"));
  loadEnv(path.join(repoRoot, ".env.local"));

  const baseUrl = mustEnv("POC_URL");
  const sysUser = mustEnv("SIT_SYS_ADMIN_USER");
  const sysPass = mustEnv("SIT_SYS_ADMIN_PASS");

  const outDir = path.join(repoRoot, "test-results", "w5-copilot-human-review-deploy-proof-08", `${stamp()}-prep-evidence`);
  fs.mkdirSync(outDir, { recursive: true });

  const apiAnon = await request.newContext({ baseURL: baseUrl, ignoreHTTPSErrors: true });
  const loginRes = await apiAnon.post("/api/v1/auth/login", {
    data: { username: sysUser, password: sysPass },
  });
  if (!loginRes.ok()) {
    throw new Error(`auth/login failed status=${loginRes.status()} body=${await loginRes.text()}`);
  }
  const login = await loginRes.json();
  await apiAnon.dispose();

  const api = await request.newContext({
    baseURL: baseUrl,
    ignoreHTTPSErrors: true,
    extraHTTPHeaders: { Authorization: `Bearer ${login.access_token}` },
  });

  const companiesRes = await api.get("/api/v1/admin/companies");
  const usersRes = await api.get("/api/v1/admin/users");
  if (!companiesRes.ok()) throw new Error(`admin/companies failed: ${companiesRes.status()}`);
  if (!usersRes.ok()) throw new Error(`admin/users failed: ${usersRes.status()}`);

  const companies = await companiesRes.json();
  const users = await usersRes.json();

  const activeW5Companies = companies.filter((c) => c.is_active && matchW5Company(c.name));
  const activeW5Users = users.filter((u) => u.is_active && matchW5User(u));

  const curlLogin = runCurl(`curl.exe -sSI ${baseUrl}/login.html`);
  fs.writeFileSync(path.join(outDir, "curl-login-headers.txt"), curlLogin.output + "\n", "utf8");

  const curlInternal = runCurl(`curl.exe -sSI ${baseUrl}/_internal/probe`);
  fs.writeFileSync(path.join(outDir, "curl-internal-headers.txt"), curlInternal.output + "\n", "utf8");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1600, height: 1000 } });
  const page = await context.newPage();

  const loginNav = await page.goto(`${baseUrl}/login.html`, { waitUntil: "domcontentloaded", timeout: 120000 });
  const loginPageShot = path.join(outDir, "browser-login-page.png");
  await page.screenshot({ path: loginPageShot, fullPage: true });

  const loginFormVisible = await page.isVisible("#loginForm").catch(() => false);
  let appHomeShot = null;
  let companiesShot = null;
  let usersShot = null;
  let companyRowsWithW5 = [];
  let usersNavVisible = false;
  let userRowsWithW5 = [];

  if (loginFormVisible) {
    await page.fill("#loginUser", sysUser);
    await page.fill("#loginPw", sysPass);
    await page.click("#loginForm button[type='submit']");
    await page.waitForSelector("#app", { timeout: 120000 });

    appHomeShot = path.join(outDir, "browser-app-home.png");
    await page.screenshot({ path: appHomeShot, fullPage: true });

    await page.click("button[data-screen='s-companies']");
    await page.waitForSelector("#companiesTableBody", { timeout: 30000 });
    await page.waitForTimeout(1500);
    companiesShot = path.join(outDir, "browser-companies-screen.png");
    await page.screenshot({ path: companiesShot, fullPage: true });

    companyRowsWithW5 = await page.$$eval("#companiesTableBody tr", (rows) => {
      return rows
        .map((r) => (r.textContent || "").trim())
        .filter((t) => /W5H06|W5 Proof|SIT Verify|CP-08/i.test(t));
    });

    usersNavVisible = await page.isVisible("#usersNavItem").catch(() => false);
    if (usersNavVisible) {
      await page.click("button[data-screen='s-users']");
      await page.waitForSelector("#usersTableBody", { timeout: 30000 });
      await page.waitForTimeout(1500);
      usersShot = path.join(outDir, "browser-users-screen.png");
      await page.screenshot({ path: usersShot, fullPage: true });
      userRowsWithW5 = await page.$$eval("#usersTableBody tr", (rows) => {
        return rows
          .map((r) => (r.textContent || "").trim())
          .filter((t) => /W5H06|W5 Proof|SIT Verify|CP-08|w5-|w5h06|sit-verify|cp-?08/i.test(t));
      });
    }
  }

  await context.close();
  await browser.close();
  await api.dispose();

  const summary = {
    generated_at_utc: new Date().toISOString(),
    base_url: baseUrl,
    selectors: {
      company_prefixes: ["W5H06", "W5 Proof", "SIT Verify", "CP-08"],
      user_selector: "strict-v2",
    },
    curl_evidence: {
      login_headers_file: path.join("test-results", "w5-copilot-human-review-deploy-proof-08", path.basename(outDir), "curl-login-headers.txt"),
      internal_headers_file: path.join("test-results", "w5-copilot-human-review-deploy-proof-08", path.basename(outDir), "curl-internal-headers.txt"),
      login_www_authenticate_present: /www-authenticate/i.test(curlLogin.output),
      internal_www_authenticate_present: /www-authenticate/i.test(curlInternal.output),
      login_status_line: curlLogin.output.split(/\r?\n/)[0] || null,
      internal_status_line: curlInternal.output.split(/\r?\n/)[0] || null,
    },
    browser_evidence: {
      login_navigation_status: loginNav ? loginNav.status() : null,
      login_form_visible: loginFormVisible,
      login_page_screenshot: path.join("test-results", "w5-copilot-human-review-deploy-proof-08", path.basename(outDir), "browser-login-page.png"),
      app_home_screenshot: appHomeShot
        ? path.join("test-results", "w5-copilot-human-review-deploy-proof-08", path.basename(outDir), "browser-app-home.png")
        : null,
      companies_screen_screenshot: companiesShot
        ? path.join("test-results", "w5-copilot-human-review-deploy-proof-08", path.basename(outDir), "browser-companies-screen.png")
        : null,
      users_screen_screenshot: usersShot
        ? path.join("test-results", "w5-copilot-human-review-deploy-proof-08", path.basename(outDir), "browser-users-screen.png")
        : null,
    },
    api_visibility_proof: {
      active_w5_companies_count: activeW5Companies.length,
      active_w5_users_count: activeW5Users.length,
      active_w5_company_names: activeW5Companies.map((c) => c.name),
      active_w5_user_names: activeW5Users.map((u) => u.username || u.email),
    },
    ui_visibility_proof: {
      companies_rows_with_w5_count: companyRowsWithW5.length,
      companies_rows_with_w5: companyRowsWithW5,
      users_nav_visible: usersNavVisible,
      users_rows_with_w5_count: userRowsWithW5.length,
      users_rows_with_w5: userRowsWithW5,
    },
  };

  const summaryPath = path.join(outDir, "prep-evidence-summary.json");
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf8");

  console.log(JSON.stringify({ status: "completed", output_dir: outDir, summary_json: summaryPath }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
