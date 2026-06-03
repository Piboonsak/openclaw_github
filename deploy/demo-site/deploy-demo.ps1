# deploy-demo.ps1 — Deploy static demo to VPS
# Usage: .\deploy\demo-site\deploy-demo.ps1

$ErrorActionPreference = "Stop"

$VPS_IP = "76.13.210.250"
$SSH_KEY = "$env:USERPROFILE\.ssh\id_ed25519_hostinger"
$SSH_OPTS = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL"
$REMOTE_USER = "root"
$REMOTE_DIR = "/var/www/demo-aiaccount"
$NGINX_CONF_REMOTE = "/etc/nginx/conf.d/demo-aiaccount.conf"
$DOMAIN = "demo-aiaccount.yahwan.biz"

$PROJECT_ROOT = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
if (-not $PROJECT_ROOT) { $PROJECT_ROOT = Get-Location }

$LOCAL_HTML = Join-Path $PROJECT_ROOT "src\frontend\ux-ui-prototype.html"
$LOCAL_CSS = Join-Path $PROJECT_ROOT "src\frontend\ux-ui-prototype.css"
$LOCAL_NGINX = Join-Path $PROJECT_ROOT "deploy\demo-site\nginx-demo-aiaccount.conf"

function Invoke-SSH($cmd) {
    $result = ssh -i $SSH_KEY $SSH_OPTS "${REMOTE_USER}@${VPS_IP}" $cmd
    if ($LASTEXITCODE -ne 0) { throw "SSH command failed: $cmd" }
    return $result
}

function Invoke-SCP($local, $remote) {
    scp -i $SSH_KEY $SSH_OPTS $local "${REMOTE_USER}@${VPS_IP}:${remote}"
    if ($LASTEXITCODE -ne 0) { throw "SCP failed: $local -> $remote" }
}

Write-Host "=== Deploy demo-aiaccount.yahwan.biz ===" -ForegroundColor Cyan

# Step 1: Create remote directory
Write-Host "[1/6] Creating remote directory..." -ForegroundColor Yellow
Invoke-SSH "mkdir -p $REMOTE_DIR"

# Step 2: Upload static files
Write-Host "[2/6] Uploading HTML + CSS..." -ForegroundColor Yellow
Invoke-SCP $LOCAL_HTML "${REMOTE_DIR}/ux-ui-prototype.html"
Invoke-SCP $LOCAL_CSS "${REMOTE_DIR}/ux-ui-prototype.css"

# Step 3: Upload nginx config
Write-Host "[3/6] Uploading nginx config..." -ForegroundColor Yellow
Invoke-SCP $LOCAL_NGINX $NGINX_CONF_REMOTE

# Step 4: Test nginx config
Write-Host "[4/6] Testing nginx configuration..." -ForegroundColor Yellow
Invoke-SSH "nginx -t"

# Step 5: Reload nginx
Write-Host "[5/6] Reloading nginx..." -ForegroundColor Yellow
Invoke-SSH "systemctl reload nginx"

# Step 6: Verify HTTP response
Write-Host "[6/6] Verifying HTTP response..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
$response = Invoke-SSH "curl -s -o /dev/null -w '%{http_code}' http://localhost -H 'Host: $DOMAIN'"
if ($response -match "200") {
    Write-Host "SUCCESS: Site responds 200 on HTTP" -ForegroundColor Green
} else {
    Write-Host "WARNING: Got HTTP $response (DNS may not be propagated yet)" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Next: Run certbot for HTTPS ===" -ForegroundColor Cyan
Write-Host "SSH into VPS and run:"
Write-Host "  certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@yahwan.biz"
Write-Host ""
Write-Host "Then verify: https://$DOMAIN" -ForegroundColor Green
