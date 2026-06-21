#!/usr/bin/env bash
# setup-vps.sh — Idempotent VPS setup for LedgerFlow UAT/PROD
# TASK-1303: Base OS + Docker + Security Hardening
#
# Usage (from laptop):
#   # UAT (2 GB swap)
#   ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.74.232 'bash -s' < scripts/infra/setup-vps.sh
#
#   # PROD (4 GB swap)
#   ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.247.9 'SWAP_SIZE=4G bash -s' < scripts/infra/setup-vps.sh
#
# Idempotent: safe to re-run — skips already-completed steps.

set -euo pipefail

# ── Config ────────────────────────────────────────────────
DEPLOY_USER="${DEPLOY_USER:-deploy}"
SWAP_SIZE="${SWAP_SIZE:-2G}"
SSH_PORT="${SSH_PORT:-22}"
ALLOWED_PORTS="22/tcp 80/tcp 443/tcp"
LOG_PREFIX="[setup-vps]"

log()  { echo "$LOG_PREFIX $*"; }
ok()   { echo "$LOG_PREFIX ✅ $*"; }
skip() { echo "$LOG_PREFIX ⏭️  $* (already done)"; }

log "Starting VPS setup on $(hostname) — $(date -Iseconds)"
log "Swap size: $SWAP_SIZE | Deploy user: $DEPLOY_USER"

# ── 1. System update ─────────────────────────────────────
log "1/7 System packages update"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
ok "System packages updated"

# ── 2. Create deploy user ────────────────────────────────
log "2/7 Deploy user setup"
if id "$DEPLOY_USER" &>/dev/null; then
    skip "User '$DEPLOY_USER' exists"
else
    useradd -m -s /bin/bash -G docker "$DEPLOY_USER"
    ok "User '$DEPLOY_USER' created"
fi

# Ensure deploy user is in docker group
if groups "$DEPLOY_USER" | grep -q docker; then
    skip "User '$DEPLOY_USER' already in docker group"
else
    usermod -aG docker "$DEPLOY_USER"
    ok "Added '$DEPLOY_USER' to docker group"
fi

# Copy SSH authorized_keys from root to deploy user
DEPLOY_HOME="/home/$DEPLOY_USER"
if [ -f "$DEPLOY_HOME/.ssh/authorized_keys" ]; then
    skip "SSH keys for '$DEPLOY_USER' exist"
else
    mkdir -p "$DEPLOY_HOME/.ssh"
    cp /root/.ssh/authorized_keys "$DEPLOY_HOME/.ssh/authorized_keys"
    chown -R "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_HOME/.ssh"
    chmod 700 "$DEPLOY_HOME/.ssh"
    chmod 600 "$DEPLOY_HOME/.ssh/authorized_keys"
    ok "SSH keys copied to '$DEPLOY_USER'"
fi

# ── 3. SSH hardening ─────────────────────────────────────
log "3/7 SSH hardening"
SSHD_CONFIG="/etc/ssh/sshd_config"
SSHD_CHANGED=false

harden_ssh_param() {
    local param="$1" value="$2"
    if grep -qE "^${param}\s+${value}" "$SSHD_CONFIG"; then
        skip "SSH: $param $value"
    else
        # Remove existing (commented or not), then append
        sed -i "/^#*\s*${param}\b/d" "$SSHD_CONFIG"
        echo "$param $value" >> "$SSHD_CONFIG"
        SSHD_CHANGED=true
        ok "SSH: $param → $value"
    fi
}

harden_ssh_param "PermitRootLogin"        "prohibit-password"
harden_ssh_param "PasswordAuthentication" "no"
harden_ssh_param "PubkeyAuthentication"   "yes"
harden_ssh_param "MaxAuthTries"           "3"
harden_ssh_param "ClientAliveInterval"    "300"
harden_ssh_param "ClientAliveCountMax"    "2"

if [ "$SSHD_CHANGED" = true ]; then
    sshd -t
    # Ubuntu 24.04 uses 'ssh' service, older uses 'sshd'
    if systemctl is-active --quiet ssh; then
        systemctl reload ssh
    elif systemctl is-active --quiet sshd; then
        systemctl reload sshd
    fi
    ok "sshd config reloaded"
else
    skip "sshd config unchanged"
fi

# ── 4. fail2ban ──────────────────────────────────────────
log "4/7 fail2ban setup"
if command -v fail2ban-client &>/dev/null; then
    skip "fail2ban already installed"
else
    apt-get install -y -qq fail2ban
    ok "fail2ban installed"
fi

F2B_JAIL="/etc/fail2ban/jail.local"
if [ -f "$F2B_JAIL" ]; then
    skip "fail2ban jail.local exists"
else
    cat > "$F2B_JAIL" << 'JAIL'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5
backend  = systemd

[sshd]
enabled  = true
port     = ssh
filter   = sshd
logpath  = /var/log/auth.log
maxretry = 3
JAIL
    ok "fail2ban jail.local created"
fi

systemctl enable fail2ban
systemctl restart fail2ban
ok "fail2ban active"

# ── 5. UFW firewall ──────────────────────────────────────
log "5/7 UFW firewall setup"
if ! command -v ufw &>/dev/null; then
    apt-get install -y -qq ufw
fi

# Reset rules only if UFW is currently inactive
if ufw status | grep -q "inactive"; then
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    for port in $ALLOWED_PORTS; do
        ufw allow "$port"
    done
    ufw --force enable
    ok "UFW enabled: $ALLOWED_PORTS"
else
    skip "UFW already active"
    ufw status verbose
fi

# ── 6. Swap ──────────────────────────────────────────────
log "6/7 Swap setup ($SWAP_SIZE)"
SWAPFILE="/swapfile"
if swapon --show | grep -q "$SWAPFILE"; then
    skip "Swap already active"
else
    if [ -f "$SWAPFILE" ]; then
        swapoff "$SWAPFILE" 2>/dev/null || true
        rm "$SWAPFILE"
    fi
    fallocate -l "$SWAP_SIZE" "$SWAPFILE"
    chmod 600 "$SWAPFILE"
    mkswap "$SWAPFILE"
    swapon "$SWAPFILE"
    # Persist in fstab
    if ! grep -q "$SWAPFILE" /etc/fstab; then
        echo "$SWAPFILE none swap sw 0 0" >> /etc/fstab
    fi
    ok "Swap $SWAP_SIZE active"
fi

# ── 7. sysctl tuning ────────────────────────────────────
log "7/7 sysctl tuning for PostgreSQL"
SYSCTL_CONF="/etc/sysctl.d/99-ledgerflow.conf"
if [ -f "$SYSCTL_CONF" ]; then
    skip "sysctl tuning already applied"
else
    cat > "$SYSCTL_CONF" << 'SYSCTL'
# LedgerFlow — PostgreSQL + Docker tuning
vm.swappiness = 10
vm.overcommit_memory = 1
net.core.somaxconn = 512
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 5
fs.file-max = 65536
SYSCTL
    sysctl -p "$SYSCTL_CONF"
    ok "sysctl tuning applied"
fi

# ── Create app directories ───────────────────────────────
log "Creating app directories"
mkdir -p /opt/ledgerflow/{nginx/conf.d,nginx/certs,logs}
mkdir -p /backup/db
chown -R "$DEPLOY_USER:$DEPLOY_USER" /opt/ledgerflow /backup
ok "Directories created: /opt/ledgerflow, /backup/db"

# ── Summary ──────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  VPS Setup Complete — $(hostname)"
echo "════════════════════════════════════════════════════════"
echo "  Host:       $(hostname)"
echo "  IP:         $(hostname -I | awk '{print $1}')"
echo "  Docker:     $(docker version --format '{{.Server.Version}}')"
echo "  Compose:    $(docker compose version --short)"
echo "  UFW:        $(ufw status | head -1)"
echo "  fail2ban:   $(fail2ban-client status sshd 2>/dev/null | grep 'Currently banned' || echo 'active')"
echo "  Swap:       $(swapon --show --noheadings | awk '{print $3}')"
echo "  Deploy user: $DEPLOY_USER (docker: $(groups $DEPLOY_USER | grep -o docker))"
echo "  SSH:        PermitRootLogin=$(grep '^PermitRootLogin' /etc/ssh/sshd_config | awk '{print $2}')"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Next: SSH as deploy user to verify:"
echo "  ssh -i ~/.ssh/id_ed25519_hostinger $DEPLOY_USER@$(hostname -I | awk '{print $1}') 'docker ps'"
