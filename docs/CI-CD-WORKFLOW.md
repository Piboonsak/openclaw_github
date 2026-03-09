# CI/CD Workflow - OpenClaw Production Deployment

## ⚠️ CRITICAL RULE

**NEVER SSH directly into VPS to fix issues.** All changes MUST go through this CI/CD pipeline to ensure:
- Changes are version-controlled
- Deployments are reproducible
- VPS crashes can be recovered
- Team members can review/audit changes

---

## Agent Execution Policy (Autonomous CI/CD)

**Purpose:** If an agent modifies application code or production config, it must run the full CI/CD flow automatically based on this document. Do not ask the user for steps that are already defined here.

**Trigger conditions (run CI/CD automatically):**
- Any change under `src/**`, `config/**`, `docker/**`, or `docs/CI-CD-WORKFLOW.md`
- Any change that affects production runtime behavior or deployment

**No-ask rule:**
- If the decision is already defined in this document (paths, commands, step order, skip rules), execute it without asking.
- Only ask if a choice is not covered anywhere in this document or is destructive/irreversible and not already approved.
- When the full procedure (branch → PR → merge → deploy → verify) is documented below, run every step end-to-end without pausing for user confirmation.

**VPS-only changes (no repo update):**
- If you must change live config or workspace data on the VPS, still follow Steps 5 → 6 → 7 → 8 → 9.
- Skip Steps 1–4 only when there is no code or repo change.

**Non-Linux developers:**
- Steps 3–4 run automatically in GitHub Actions on push to `main`. No local Docker build needed.

### Local Credential Bootstrap (Agent token auto-read)

Agents running locally (VS Code Copilot, CLI scripts) must load the GitHub token **automatically** without prompting the user.

**Token file location:**
```
D:\key\githubToken.txt
```

**Bootstrap procedure (run once per session, before any `gh` or `git push` command):**

```powershell
# PowerShell — read token file and export for gh CLI
$GH_TOKEN = (Get-Content "D:\key\githubToken.txt" -Raw).Trim()
$env:GH_TOKEN = $GH_TOKEN
```

```bash
# Bash — read token file and export for gh CLI
export GH_TOKEN=$(cat /d/key/githubToken.txt | tr -d '\n\r')
```

**Rules:**
- **NEVER prompt the user for a GitHub token.** Always read from the file above.
- If the file is missing or empty, fail immediately with:
  `"ERROR: GitHub token file not found at D:\key\githubToken.txt — create the file with a valid GitHub PAT."`
- This file is for **local agent/CLI use only**. GitHub Actions runners use repository secrets (`secrets.GITHUB_TOKEN`) — they cannot access local D: drive paths.
- The token file must NOT be committed to any repository.

**Scope separation:**

| Context | Auth Source | Notes |
|---|---|---|
| Local agent (VS Code, CLI) | `D:\key\githubToken.txt` | Read at session start, no prompt |
| GitHub Actions runners | `secrets.GITHUB_TOKEN` / `secrets.GH_APP_PRIVATE_KEY` | Configured in repo Settings → Secrets |
| Docker Hub (Actions) | `secrets.DOCKER_USERNAME` + `secrets.DOCKER_TOKEN` | 3-retry logic in docker-build-push.yml |
| VPS SSH (Actions) | `secrets.DEPLOY_SSH_PRIVATE_KEY` | Written to ephemeral runner |

---

## GitHub Actions Pipeline Overview

All deployment is driven by two GitHub Actions workflows that run automatically:

```
Push to main (or tag v*)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  docker-build-push.yml                              │
│  ├── Checkout code                                  │
│  ├── Docker Hub login (3-retry with DOCKER_TOKEN)   │
│  ├── Build image (docker/Dockerfile.prod)           │
│  ├── Push piboonsak/openclaw:latest + SHA tag       │
│  └── Output: image digest                           │
└───────────────────┬─────────────────────────────────┘
                    │ on success (workflow_run trigger)
                    ▼
┌─────────────────────────────────────────────────────┐
│  deploy-vps.yml                                     │
│  ├── Configure SSH key (DEPLOY_SSH_PRIVATE_KEY)                │
│  ├── SCP Nginx config to VPS                        │
│  ├── Run docker/deploy.sh on VPS via SSH            │
│  │   ├── docker pull piboonsak/openclaw:latest      │
│  │   ├── docker compose up -d                       │
│  │   ├── Clear stale sessions                       │
│  │   ├── Apply exec/embeddings config               │
│  │   ├── Apply Nginx config + reload                │
│  │   └── Health check (8 retries, 40s)              │
│  ├── Verify HTTPS health (5 retries)                │
│  ├── SCP + Run regression-tests.sh on VPS           │
│  ├── SCP + Run r3-regression-tests.sh on VPS        │
│  ├── Upload test results as artifact                │
│  └── PASS/FAIL → workflow status                    │
└─────────────────────────────────────────────────────┘
```

### Required GitHub Secrets

All secrets are configured in **Settings → Secrets and variables → Actions**:

| Secret | Purpose | Used By |
|---|---|---|
| `DOCKER_USERNAME` | Docker Hub login (`piboonsak`) | docker-build-push.yml |
| `DOCKER_TOKEN` | Docker Hub Personal Access Token | docker-build-push.yml |
| `DEPLOY_SSH_PRIVATE_KEY` | SSH private key for VPS (`id_ed25519_hostinger`) | deploy-vps.yml |
| `VPS_HOST` | VPS hostname (`srv1414058.hstgr.cloud`) | deploy-vps.yml |
| `VPS_USER` | SSH user (`root`) | deploy-vps.yml |
| `GH_APP_PRIVATE_KEY` | GitHub App for issue/PR automation | labeler.yml, stale.yml |

### Workflow Files

| File | Trigger | Purpose |
|---|---|---|
| `.github/workflows/docker-build-push.yml` | push to `main`, tags `v*`, manual | Build + push Docker image to Docker Hub |
| `.github/workflows/deploy-vps.yml` | after docker-build-push succeeds, manual | Deploy to VPS + run automated verification |
| `.github/workflows/ci.yml` | push to `main`, PRs | Lint, type-check, tests, multi-platform |
| `.github/workflows/docker-release.yml` | push to `main`, tags `v*` | Multi-arch build to GHCR |

---

## Standard Deployment Workflow

### 1. Fix Code Locally

```bash
cd d:\01_gitrepo\openclaw_github

# Make your changes to:
# - config/openclaw.prod.json5
# - docker/docker-compose.prod.yml
# - docker/nginx/openclaw.conf
# - src/** (if code changes needed)
# - .env.example (document new env vars)
# - docker/vps-setup.sh (update env template if needed)
```

**Pre-commit checks:**
```bash
pnpm check           # Lint & format
pnpm test            # Run tests
pnpm build          # Type-check & build
git status          # Verify changed files
```

### 2. Push to Repository

```bash
# Stage only relevant files (avoid temp files)
git add config/openclaw.prod.json5 docker/docker-compose.prod.yml ...

# Commit with descriptive message (follow Conventional Commits)
git commit -m "fix(model): increase maxTokens to 16384 for long responses"

# Push to main
git push origin main
```

**Branch naming conventions:**
- `fix/<issue>-<short-desc>` - Bug fix work (e.g., `fix/ws22-web-search-key`)
- `feat/<short-desc>` - New features (e.g., `feat/line-webhook-retry`)
- `infra/<short-desc>` - Infrastructure-only changes (e.g., `infra/nginx-timeouts`)
- `docs/<short-desc>` - Documentation-only changes (e.g., `docs/cicd-naming`)

**Tag alignment rule (Git tag == Image tag):**
- Use one shared tag for BOTH Git and Docker image.
- Format: `vYYYY.M.D` for release, or `vYYYY.M.D-<fix>` for hotfixes.
- Example: `v2026.2.28` (release), `v2026.2.28-r3fix` (hotfix)

**Commit message format:**
- `fix(scope): description` - Bug fixes
- `feat(scope): description` - New features
- `infra(scope): description` - Infrastructure changes
- `docs(scope): description` - Documentation only

**Pull Request creation:**

For feature branches (not direct pushes to `main`):

**Option A: GitHub CLI** (preferred — fully automated)
```bash
# Token is auto-loaded from D:\key\githubToken.txt (see "Local Credential Bootstrap" above)
# If not yet loaded in this session:
$env:GH_TOKEN = (Get-Content "D:\key\githubToken.txt" -Raw).Trim()

gh pr create --title "fix(scope): description" --body-file PR_DESCRIPTION.md --base main --head feature-branch-name

# Or use interactive mode
gh pr create --web
```

**Option B: Web UI** (no local auth required)
1. Push feature branch: `git push origin feature-branch-name`
2. Visit: `https://github.com/<owner>/<repo>/compare/main...feature-branch-name?expand=1`
3. Fill title + description, click "Create pull request"

**Option C: After push, GitHub provides a URL**
```
remote: Create a pull request for 'feature-branch' on GitHub by visiting:
remote:      https://github.com/owner/repo/pull/new/feature-branch
```

**PR merge:** After approval, merge to `main` (triggers CI/CD automatically).

### 3. Build Docker Image (GitHub Actions — Automated)

**Triggered automatically** by push to `main` or tag push (`v*`).

**Workflow:** `.github/workflows/docker-build-push.yml`

**What it does:**
1. Checks out the repository
2. Sets up Docker Buildx
3. Logs in to Docker Hub using `DOCKER_USERNAME` + `DOCKER_TOKEN` (with **3-retry logic** — if auth fails after 3 attempts, workflow fails with actionable error)
4. Builds from `docker/Dockerfile.prod` (multi-stage, security-hardened)
5. Pushes with auto-generated tags:
   - `piboonsak/openclaw:latest` — on main branch push
   - `piboonsak/openclaw:main-<sha>` — git SHA prefix
   - `piboonsak/openclaw:<version>` — from git tags (e.g., `v2026.2.28` → `2026.2.28`)
6. Uses GitHub Actions cache (`type=gha`) for faster builds

**Docker Hub auth failure handling:**
```
Retry 1 → docker/login-action with DOCKER_USERNAME + DOCKER_TOKEN
Retry 2 → (if failed) wait 10s, retry login + build
Retry 3 → (if failed) wait 30s, retry login + build
→ All 3 failed: workflow FAILS with error:
  "Docker Hub auth failed after 3 attempts. Verify DOCKER_USERNAME and
   DOCKER_TOKEN in GitHub Settings → Secrets → Actions."
```

**Manual trigger:** Go to Actions → "Build and Push Docker Image" → Run workflow.

**Verify on Docker Hub:**
- Visit: https://hub.docker.com/r/piboonsak/openclaw/tags
- Confirm tags are present and image size matches

**Tag naming conventions:**
- `latest` - Current production release
- `vYYYY.M.D` - Release tag (Git tag + image tag)
- `vYYYY.M.D-<fix>` - Hotfix tag (Git tag + image tag)

### 4. Push Image to Docker Hub (GitHub Actions — Automated)

This is part of Step 3 — the `docker-build-push.yml` workflow handles both build **and** push in a single job.

**Tag naming conventions:**
- `latest` - Current production release (on main branch)
- `main-<sha>` - Git SHA-tagged build
- `<version>` - Semver from git tags (e.g., `v2026.2.28` → `2026.2.28`)

**No manual Docker push required.** The workflow handles everything.

### 5. Deploy to VPS (GitHub Actions — Automated)

**Triggered automatically** when `docker-build-push.yml` succeeds on main branch.

**Workflow:** `.github/workflows/deploy-vps.yml`

**What it does:**
1. **SSH key setup** — Writes `DEPLOY_SSH_PRIVATE_KEY` to ephemeral runner, scans host keys
2. **Sync Nginx config** — SCPs `docker/nginx/openclaw.conf` to VPS (`/tmp/openclaw-nginx.conf`)
3. **Run deploy.sh** — Executes `docker/deploy.sh` on VPS via SSH:
   - `docker pull piboonsak/openclaw:<tag>`
   - Updates `docker-compose.yml` image line
   - `docker compose up -d --pull always`
   - Verifies container is running
   - Health check (8 attempts, 40s total)
4. **Post-deploy configuration** (in deploy.sh):
   - Clears stale LINE sessions (`clear-sessions.sh`)
   - Applies exec security config (`openclaw config set tools.exec.*`)
   - Applies embeddings config (`openclaw config set agents.defaults.memorySearch.*`)
   - Applies Nginx config (`cp` + `nginx -t` + `nginx -s reload`)
   - Updates Flask bridge timeout (gunicorn `--timeout 300`)
5. **HTTPS health check** — Verifies `https://openclaw.yahwan.biz/health` returns HTTP 200 (5 retries)
6. **Automated regression tests** — See Step 7
7. **Cleanup** — Removes SSH key from runner

**Manual trigger:** Go to Actions → "Deploy to Hostinger VPS" → Run workflow (optionally specify image tag).

**Concurrency:** Only one deploy at a time (`cancel-in-progress: false` — never cancels in-flight deploy).

**Manual deployment (emergency only):**

If GitHub Actions is unavailable, deploy manually via SSH:

```bash
ssh -i "C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger" root@76.13.210.250
cd /docker/openclaw-sgnl

# Backup + clear sessions
docker compose --profile maintenance run --rm backup-config
docker compose --profile maintenance run --rm clear-sessions

# Pull + restart
docker pull piboonsak/openclaw:latest
docker compose down
docker compose up -d

# Wait for health
sleep 40
docker ps --filter name=openclaw --format "table {{.Names}}\t{{.Status}}"
```

### 5a. Create Release Git Tag

**After Step 5 deployment succeeds and regression tests pass (Step 7):**

```bash
# Create Git tag matching image tag (aligned versioning)
git tag v2026.2.28-r3fix

# Push tag to GitHub
git push origin v2026.2.28-r3fix
```

**Verify on GitHub:**
- https://github.com/Piboonsak/openclaw_github/releases
- New tag should appear with commit details

### 6. Verify OpenClaw Health (GitHub Actions — Automated)

All health checks run automatically inside the `deploy-vps.yml` workflow. The workflow **fails** if any check does not pass.

#### 6.1 Automated Verification Pipeline (in deploy-vps.yml)

| # | Check | Method | Pass Criteria | Workflow Step |
|---|---|---|---|---|
| 1 | Container running | `docker inspect --format='{{.State.Running}}'` | `true` | deploy.sh [3/4] |
| 2 | Gateway health (internal) | `curl -sf http://localhost:18789/health` | HTTP 200 (8 retries, 40s) | deploy.sh [4/4] |
| 3 | HTTPS health (external) | `curl https://openclaw.yahwan.biz/health` | HTTP 200 (5 retries, 50s) | deploy-vps.yml |
| 4 | Exec security config | `openclaw config get tools.exec.security` | `"allowlist"` | r3-regression-tests.sh |
| 5 | Exec askFallback | `openclaw config get tools.exec.askFallback` | `"allowlist"` | r3-regression-tests.sh |
| 6 | Exec safeBins has `date` | `openclaw config get tools.exec.safeBins` | contains `date` | r3-regression-tests.sh |
| 7 | Exec safeBins has `jq` | `openclaw config get tools.exec.safeBins` | contains `jq` | r3-regression-tests.sh |
| 8 | Exec safeBins has `whoami` | `openclaw config get tools.exec.safeBins` | contains `whoami` | r3-regression-tests.sh |
| 9 | Embeddings provider | `openclaw config get agents.defaults.memorySearch.provider` | `"openai"` | r3-regression-tests.sh |
| 10 | Exec host | `openclaw config get tools.exec.host` | `"gateway"` | r3-regression-tests.sh |
| 11 | Exec `date` works | `openclaw agent -m "run date" --json --timeout 30 --local` | no "Approval required" | r3-regression-tests.sh |
| 12 | Exec `whoami` works | `openclaw agent -m "run whoami" --json --timeout 30 --local` | output contains "node" | r3-regression-tests.sh |
| 13 | LINE webhook route | POST `http://localhost:18789/line/webhook` | HTTP 200 (not 502/499) | r3-regression-tests.sh |
| 14 | Nginx `/line/` → native | `nginx -T \| grep proxy_pass` on `/line/` | port 18789 | r3-regression-tests.sh |
| 15 | Nginx `/line-bridge/` | `nginx -T \| grep proxy_pass` on `/line-bridge/` | port 5100 | r3-regression-tests.sh |
| 16 | Sessions cleared | `find sessions/ -name 'line-*.jsonl' -size +50k` | 0 files | r3-regression-tests.sh |
| 17 | Flask bridge alive | `curl http://localhost:5100/line/health` | HTTP 200 | r3-regression-tests.sh |
| 18 | Volume mount correct | `docker inspect` mount at `/data/.openclaw` | mount exists | regression-tests.sh |
| 19 | Config file persists | `test -f /data/.openclaw/openclaw.json` | file exists | regression-tests.sh |
| 20 | Container TZ Bangkok | `date +%z` inside container | `+0700` | regression-tests.sh |
| 21 | BRAVE_API_KEY set | `test -n "${BRAVE_API_KEY}"` | non-empty | regression-tests.sh |
| 22 | No startup errors | `docker logs \| grep ERROR` | 0 matches | regression-tests.sh |

**If any check fails:** The `deploy-vps.yml` workflow exits with failure status (red ✗ in GitHub Actions). Test output is uploaded as a workflow artifact for debugging.

#### 6.2 Manual Verification (optional, post-deploy)

For additional confidence after a major release:

```bash
# A. Gateway probe
ssh -i "C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger" root@76.13.210.250 \
  "docker exec openclaw-sgnl-openclaw-1 openclaw channels status --probe"

# B. Config snapshot
ssh -i "C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger" root@76.13.210.250 \
  "docker exec openclaw-sgnl-openclaw-1 sh -c 'cat /data/.openclaw/openclaw.json'" | jq '
    {
      execSecurity: .tools.exec.security,
      askFallback: .tools.exec.askFallback,
      safeBins: .tools.exec.safeBins,
      memorySearch: .agents.defaults.memorySearch.provider,
      searchProvider: .tools.web.search.provider
    }
  '

# C. Log inspection
ssh -i "C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger" root@76.13.210.250 \
  "docker logs --tail 50 openclaw-sgnl-openclaw-1 2>&1 | grep -i error"
```

### 7. Run Regression Tests (GitHub Actions — Automated)

**All regression tests run automatically** as the final step of `deploy-vps.yml`. No manual LINE OA testing is needed for pass/fail determination.

#### 7.1 Automated Test Suites

Two test scripts are SCP'd to VPS and executed via SSH:

**A. `tests/regression-tests.sh` (20+ checks)** — Original infrastructure tests:
- Volume mount verification
- Config persistence across restart
- exec safeBins configuration
- Environment variables set
- Container timezone (+0700)
- Gateway health
- No startup errors

**B. `tests/r3-regression-tests.sh` (17+ checks)** — R3-specific tests:

| Category | Tests | Method |
|---|---|---|
| **Config verification** | exec security, askFallback, safeBins, embeddings provider, exec host | `docker exec openclaw config get ...` — exact value match |
| **Exec smoke tests** | `date` runs without approval, `whoami` returns "node" | `docker exec openclaw agent -m "..." --json --local` — parse JSON output, verify no "Approval required" |
| **LINE webhook** | Native handler responds HTTP 200 | `curl -X POST http://localhost:18789/line/webhook` — HTTP status code check |
| **Nginx routing** | `/line/` → port 18789, `/line-bridge/` → port 5100 | `nginx -T` grep — proxy_pass value match |
| **Session cleanup** | No LINE session > 50KB | `find ... -size +50k -print` — count == 0 |
| **Flask fallback** | Bridge health endpoint alive | `curl http://localhost:5100/line/health` — HTTP 200 |

**All tests are deterministic** — they check specific config values, HTTP status codes, command output, and file sizes. No LLM inference. No hallucination possible.

#### 7.2 Test Failure Handling

If any test fails:

1. **Workflow exits with failure** (red ✗ on GitHub Actions)
2. **Test output uploaded as artifact** — download from the workflow run page
3. **Auto-diagnostic log captured:**
   ```bash
   docker logs openclaw-sgnl-openclaw-1 --tail=200 2>&1 | grep -E "ERROR|Exception|Traceback"
   ```
4. **Do NOT retry with the same fix** — re-investigate logs first per §9.2 of copilot.instructions.md

#### 7.3 Manual LINE OA Smoke Test (optional, post-automated-pass)

For additional user-experience validation after all automated tests pass, send these messages via LINE OA:

1. **สวัสดี** — Greeting response, no errors
2. **ตอนนี้กี่โมงแล้ว** — Returns current time (exec `date` works)
3. **รันคำสั่ง date** — Runs `date` without approval prompt
4. **ใช้โมเดลไหน** — Returns model name
5. **ค้นหาราคาทองวันนี้** — Web search works, response arrives (no 499)
6. **สรุปผลทดสอบทั้งหมดให้ทีเป็นข้อ ๆ** — Summarization works

These are documented in `tests/LINE-REGRESSION-MESSAGES.md` for reference.

### 8. Update Release Documentation

**Update `README.md` release section** with the deployment details and then commit:

```bash
git add README.md
git commit -m "docs: update release notes for v2026.2.28-r3fix"
git push origin main
```

### 9. Feedback & Documentation Review (Quality Gate)

**Purpose:** Continuously improve this CI/CD workflow based on real execution experience.

**Auto-gate condition:** The deploy-vps.yml workflow includes a final summary step that outputs pass/fail counts. If all 22 automated checks pass, the pipeline is green.

**Required Question (Ask after every major release or failed pipeline):**

> "Please summarize what happened in this CI/CD run:
> 1. **What worked smoothly?** (which steps need no changes)
> 2. **What failed or was unclear?** (missing context, outdated paths, wrong commands)
> 3. **What needs to be fixed** in this document for the next run to go more smoothly?
> 4. **Specific doc improvements:** update CI-CD-WORKFLOW.md with exact corrections discovered"

**Gate Condition (Repeating Policy):**

Repeat this step after every CI/CD pipeline execution until all of the following are true:
- ✅ Steps 1-8 complete without needing SSH workarounds
- ✅ GitHub Actions pipeline is green (all 22 checks pass)
- ✅ No confusion about file paths or command syntax
- ✅ No "unknown" errors that aren't documented
- ✅ Document accurately reflects actual VPS setup
- ✅ Next developer can follow this doc end-to-end without questions

**Example improvements that were made from feedback:**

- Clarified `/docker/openclaw-sgnl/` (not `/root/openclaw-deployment`) ✅
- Fixed `docker compose` v2 syntax (not `docker-compose`) ✅
- Added skip instructions for non-Linux developers (Steps 3-4) ✅
- Added "Known Issues" for LINE channel warnings ✅
- Added Step 5a for Git tag creation timing ✅
- Migrated Steps 3-7 to GitHub Actions automation ✅
- Added 22-check automated verification table ✅
- Added 3-retry Docker Hub auth with actionable error ✅
- Added PR creation options (gh CLI, web UI, git push URL) — R3 deployment feedback ✅

---

## Pre-Fix Documentation Gate

**Purpose:** Before summarizing a problem or proposing any fix, the agent MUST check existing docs to confirm: (1) whether a solution already exists, and (2) whether the doc reflects current system state.

**Mandatory steps (execute before ANY fix proposal):**

1. **Search `docs/` for relevant documentation:**
   - `docs/channels/line.md` — LINE channel config and known issues
   - `docs/channels/troubleshooting.md` — Channel-level troubleshooting
   - `docs/cli/approvals.md` — Exec approval system and allowlist helpers
   - `docs/cli/config.md` — All config keys and their defaults
   - `docs/gateway/` — Gateway internals and WS protocol
   - `docs/help/` — General troubleshooting guides
   - `docs/concepts/context.md` — Context window and token limits
   - `docs/concepts/session.md` — Session lifecycle and timeout config
   - `docs/debug/tiered-debug-sop.md` — Known Issues Pattern Database (§7)

2. **Confirm explicitly (one of):**
   - `"Existing solution found in [doc]: [summary]"` → use it, do not reinvent
   - `"No existing solution found — proposing new approach"` → proceed with fix

3. **Never propose a new approach without first ruling out an existing one.**

4. **Cross-reference:** This gate is also required by `copilot.instructions.md` §9.1 (Pre-Fix Protocol).

---

## Production Resource Limits

**VPS specification:** Hostinger KVM VPS — up to **4 vCPU / 16 GB RAM**.

**Container resource allocation** (set in `docker/docker-compose.prod.yml`):

| Resource | Limit | Reservation | Purpose |
|----------|-------|-------------|---------|
| CPU | 4 | 1.0 | Allow burst to full VPS capability |
| Memory | 16G | 1G | Allow large context windows + embeddings |
| PIDs | 200 | — | Prevent fork bombs |
| tmpfs | 100M | — | Scratch space in read-only container |

**When to scale:**
- Monitor `docker stats openclaw-sgnl-openclaw-1` after deploy
- If RSS stays above 12G (75%), consider reducing context window config
- If OOM-killed (exit code 137), check `docker inspect` for memory stats

**Verification (automated):**
- Regression test checks `NanoCpus` = 4000000000 and `Memory` = 17179869184 bytes
- Deploy script verifies limits after `docker compose up -d`

- Added token auto-read from `D:\key\githubToken.txt` — no manual token input needed ✅
- Added Pre-Fix Documentation Gate (mandatory doc search before any fix proposal) ✅
- Added Production Resource Limits section (4 vCPU / 16 GB) with monitoring guidance ✅
- Added autonomous end-to-end execution rule (no pause for documented procedures) ✅

---

## Pre-Deploy Debug Gate

**Purpose:** Prevent broken fixes from reaching production by enforcing the debug protocol before any merge or deploy.

### Pre-Merge Checklist (Block PR if any unchecked)

```
[ ] Tier-0 log snapshot was run (§1.5 of tiered-debug-sop.md) — not assumed
[ ] Source files related to the change were read before coding (Pre-Code-Review Gate)
[ ] Fix Execution Protocol steps 1–8 were followed in order
[ ] Plan A AND Plan B were defined before implementation
[ ] Risk & Prevention Checklist completed (session state, restart impact, rollback path)
[ ] If this is a repeat issue — regression test added to /tests/
[ ] All CI checks pass (lint → unit tests → integration tests → build)
[ ] GitHub Actions pipeline green (docker-build-push.yml + deploy-vps.yml)
[ ] All 22 automated verification checks pass (see Step 6.1)
```

### Auto-Test Failure Protocol

When CI pipeline tests fail, the following steps are MANDATORY before retrying:

1. **Download the test artifact** from the failed GitHub Actions workflow run
2. **Read the failure output** — identify which of the 22 checks failed
3. **Dump additional logs** if needed:
   ```bash
   ssh -i "C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger" root@76.13.210.250 \
     "docker logs openclaw-sgnl-openclaw-1 --tail=200 2>&1 | grep -E 'ERROR|Exception|Traceback'"
   ```
4. **Quote the root error line** in PR comment before proposing any fix
5. **Never retry with same fix logic** — re-investigate first per §9.2 of copilot.instructions.md

The `deploy-vps.yml` workflow automatically captures diagnostic logs on failure and uploads them as artifacts.

---

## Emergency Procedures

### Option A: Rollback via GitHub Actions (preferred)

1. Go to **Actions → deploy-vps.yml → Run workflow**
2. Set input `image_tag` to the last known-good tag (e.g., `v2026.2.27-ws23`)
3. The workflow will deploy that specific image version
4. Verify via the automated regression tests in the same workflow run

### Option B: Rollback via SSH (emergency only)

```bash
# SSH into VPS
ssh -i "C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger" root@76.13.210.250

# Pull previous working image
cd /docker/openclaw-sgnl
docker pull piboonsak/openclaw:v2026.2.27-ws23

# Update docker-compose.yml to use specific tag
nano docker/docker-compose.prod.yml  # Change image: to specific version

# Restart with old version
docker compose down
docker compose up -d

# Verify health
docker ps
docker logs openclaw-sgnl-openclaw-1 --tail 50
```

### When VPS Crashes/Needs Rebuild

If VPS is completely lost, redeploy from clean slate:

```bash
# 1. SSH into new VPS
ssh -i "C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger" root@<NEW_IP>

# 2. Clone deployment repo
git clone https://github.com/Piboonsak/openclaw_github.git /docker/openclaw-sgnl
cd /docker/openclaw-sgnl

# 3. Run setup script
bash docker/vps-setup.sh

# 4. Configure environment variables in Hostinger UI
# (all OPENROUTER_API_KEY, BRAVE_API_KEY, etc.)

# 5. Deploy with docker-compose
docker compose up -d

# 6. Verify: run both regression test suites
bash tests/regression-tests.sh
bash tests/r3-regression-tests.sh
```

---

## Quick Reference

### File Locations

**Local (development):**
- Config: `config/openclaw.prod.json5`
- Docker Compose: `docker/docker-compose.prod.yml`
- Nginx: `docker/nginx/openclaw.conf`
- VPS Setup: `docker/vps-setup.sh`
- Deploy script: `docker/deploy.sh`
- Regression tests: `tests/regression-tests.sh`
- R3 regression tests: `tests/r3-regression-tests.sh`

**Workflows (GitHub Actions):**
- Build & push: `.github/workflows/docker-build-push.yml`
- Deploy to VPS: `.github/workflows/deploy-vps.yml`
- CI checks: `.github/workflows/ci.yml`

**VPS (production):**
- App directory: `/docker/openclaw-sgnl`
- Container: `openclaw-sgnl-openclaw-1`
- Config: `/data/.openclaw/openclaw.json` (inside container)
- Workspace: `/data/.openclaw/workspace/` (inside container)
- Sessions: `/data/.openclaw/agents/main/sessions/` (inside container)
- Logs: `docker logs openclaw-sgnl-openclaw-1`
- Clear sessions script: `docker/scripts/clear-sessions.sh`
- Flask bridge: `/opt/line-bridge/app.py` (systemd `line-bridge.service`)
- Nginx config: `/etc/nginx/sites-enabled/openclaw.conf`

### Key Commands

```bash
# Check container status
docker ps --filter name=openclaw

# View logs (live)
docker logs -f openclaw-sgnl-openclaw-1

# Restart container
docker restart openclaw-sgnl-openclaw-1

# Execute command inside container
docker exec openclaw-sgnl-openclaw-1 openclaw --version

# Check gateway health
docker exec openclaw-sgnl-openclaw-1 openclaw channels status --probe

# Check exec config
docker exec openclaw-sgnl-openclaw-1 openclaw config get tools.exec

# Clear stale LINE session history (run before deploy)
docker exec openclaw-sgnl-openclaw-1 bash /app/docker/scripts/clear-sessions.sh

# Run regression tests on VPS
bash tests/regression-tests.sh && bash tests/r3-regression-tests.sh
```

### Environment Variables (Hostinger UI)

Required for production:
- `OPENROUTER_API_KEY` - Primary LLM provider
- `OPENAI_API_KEY` - Embeddings (text-embedding-ada-002)
- `BRAVE_API_KEY` - Web search (code expects this exact name)
- `BRAVE_API_SEARCH_KEY` - Alternative Brave key
- `BRAVE_API_ANSWER_KEY` - Brave AI answers
- `LINE_CHANNEL_SECRET` - LINE bot authentication
- `LINE_CHANNEL_ACCESS_TOKEN` - LINE bot access

### GitHub Secrets (Settings → Secrets → Actions)

- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_TOKEN` - Docker Hub access token
- `DEPLOY_SSH_PRIVATE_KEY` - SSH private key for VPS
- `VPS_HOST` - VPS IP (76.13.210.250)
- `VPS_USER` - VPS user (root)

---

## Change Log

| Date | Commit | Changes | Tag | Status |
|------|--------|---------|-----|--------|
| 2026-02-27 | `e8f5f37` | Naming conventions: aligned Git tag == image tag | `docs` | ✅ Merged |
| 2026-02-27 | `cec2aac` | Config: wire Brave Search apiKey via env substitution | `config` | ✅ Deployed |
| 2026-02-27 | `ab08d4b` | WS-2.2 fixes: Gemini Flash primary, fallback chain, Brave Search, maxTokens 16384 | `v2026.2.27-ws22` | ✅ Deployed |
| 2026-02-27 | — | 7 production fixes (P0-P3), volume mount correction | `v2026.2.27-ws23` | ✅ Deployed |
| 2026-02-28 | — | docs: add Pre-Deploy Debug Gate, Auto-Test Failure Protocol, Pre-Merge checklist | `docs` | ✅ Merged |
| 2026-02-28 | `c5dd526` | R3 fix: GitHub Actions pipeline, native LINE handler, exec config, embeddings, 22-check automated tests | `v2026.2.28-r3fix` | ✅ Deployed |
| 2026-02-28 | `da32e17` | docs: CI-CD workflow improvements from R3 deployment (PR creation options, completion verification) | `docs` | ✅ Merged |
| 2026-03-01 | `b141323` | WS-2.4 CI/CD: token auto-read, autonomous no-prompt rules, pre-fix doc gate, resource scaling 4vCPU/16GB | `infra` | ✅ Deployed |
| 2026-03-01 | `3599bb7` | fix(test): WS-2.4 regression tests — query runtime config, fix safe-bins detection | `test` | ✅ Deployed & ✅ Tests PASS (7 passed, 0 failed, 3 skipped) |

---

## Notes

- **All deployment goes through GitHub Actions** — no manual SSH deploys
- **Document breaking changes** in commit messages
- **Docker Hub and GitHub tags stay in sync** (automated by docker-build-push.yml)
- **Automated tests run on every deploy** — 22 deterministic checks
- **Have rollback plan ready** — use GitHub Actions replay or emergency SSH rollback
- **3-retry on Docker Hub auth** — pipeline gives actionable error on credential issues

---

## Future Improvements

- [x] Setup GitHub Actions for automated build/deploy ✅ (docker-build-push.yml + deploy-vps.yml)
- [x] Add automated regression test suite ✅ (regression-tests.sh + r3-regression-tests.sh, 22 checks)
- [ ] Setup monitoring/alerting (UptimeRobot, Sentry)
- [ ] Add staging environment for pre-production testing
- [ ] Setup blue-green deployment for zero-downtime updates
- [ ] Add health check webhook to notify on failures
- [ ] Add Slack/Discord notification on deploy success/failure
