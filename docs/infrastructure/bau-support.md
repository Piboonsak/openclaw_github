# BAU Support Procedures — LedgerFlow

> **TASK-1309** | Created: 2026-06-21 | Owner: DevOps

## VPS Access

### SSH Commands

```bash
# UAT (deploy user — primary)
ssh -i ~/.ssh/id_ed25519_hostinger deploy@72.62.74.232

# PROD (deploy user — primary)
ssh -i ~/.ssh/id_ed25519_hostinger deploy@72.62.247.9

# Demo/PoC
ssh -i ~/.ssh/id_ed25519_hostinger root@76.13.210.250

# Emergency root access (UAT/PROD — use only when deploy user insufficient)
ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.74.232
ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.247.9
```

- SSH key (Windows): `C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger`
- SSH key (Linux/Mac): `~/.ssh/id_ed25519_hostinger`

## View Logs

### Docker container logs

```bash
# List running containers
docker ps

# Follow logs for a specific service
docker logs -f --tail 100 <container_name>

# Common service names (after Docker Compose deployment):
docker logs -f --tail 100 backend
docker logs -f --tail 100 celery-worker
docker logs -f --tail 100 postgres
docker logs -f --tail 100 nginx
docker logs -f --tail 100 redis
docker logs -f --tail 100 minio
```

### System logs

```bash
# SSH login attempts
journalctl -u ssh --since "1 hour ago"

# fail2ban status
fail2ban-client status sshd

# Cert check logs
journalctl -t certcheck --since "1 day ago"

# auditd SSH events
ausearch -k ssh_login --start recent

# Certbot renewal logs
cat /var/log/letsencrypt/letsencrypt.log | tail -50
```

## Restart Services

### Restart all services (Docker Compose)

```bash
# UAT
cd /opt/ledgerflow
docker compose -f docker-compose.uat.yml restart

# Restart specific service
docker compose -f docker-compose.uat.yml restart backend

# Full stop + start (use when restart isn't enough)
docker compose -f docker-compose.uat.yml down
docker compose -f docker-compose.uat.yml up -d
```

### Restart system services

```bash
# SSH
sudo systemctl restart ssh

# fail2ban
sudo systemctl restart fail2ban

# UFW (should not need restart, but if needed)
sudo ufw reload

# Docker daemon
sudo systemctl restart docker
```

## Health Checks

```bash
# From VPS (after Docker Compose deployment)
curl -s http://localhost:8000/api/health

# From external
curl -s https://uat.bwcacc.biz/api/health
curl -s https://app.bwcacc.biz/api/health

# Database connectivity (from inside backend container)
docker exec backend python -c "from sqlalchemy import create_engine; e=create_engine('$DATABASE_URL'); e.connect(); print('DB OK')"
```

## SSL Certificate Management

```bash
# Check cert expiry
openssl x509 -in /etc/letsencrypt/live/uat.bwcacc.biz/cert.pem -noout -enddate
openssl x509 -in /etc/letsencrypt/live/app.bwcacc.biz/cert.pem -noout -enddate

# Manual renewal (auto-renew runs via systemd timer)
sudo certbot renew

# Check auto-renew timer
systemctl list-timers certbot.timer

# Force renew (if needed)
sudo certbot renew --force-renewal
```

## Firewall Management

```bash
# View current rules
sudo ufw status verbose

# Temporarily allow a port (debugging only — remove after)
sudo ufw allow 5432/tcp comment 'temp DB access'
sudo ufw delete allow 5432/tcp   # REMOVE when done

# Block an IP
sudo ufw deny from <IP_ADDRESS>
```

## Disk Usage

```bash
# Overview
df -h

# Docker disk usage
docker system df

# Largest directories
du -sh /var/lib/docker/volumes/* 2>/dev/null | sort -rh | head -10
du -sh /backup/db/* 2>/dev/null | sort -rh | head -10

# Clean Docker (unused images/containers)
docker system prune -f
```

## Database Operations

```bash
# Manual backup (after Docker Compose deployment)
docker exec postgres pg_dump -U ledgerflow ledgerflow_uat | gzip > /backup/db/manual_$(date +%Y%m%d_%H%M%S).sql.gz

# List backups
ls -lah /backup/db/

# Check DB size
docker exec postgres psql -U ledgerflow -c "SELECT pg_size_pretty(pg_database_size('ledgerflow_uat'));"
```

## DNS Management

```bash
# List current DNS records
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/dns/v1/zones/bwcacc.biz | python3 -m json.tool

# Verify DNS resolution
nslookup uat.bwcacc.biz 8.8.8.8
nslookup app.bwcacc.biz 8.8.8.8
```

## Emergency Contacts

| Role | Contact | When to reach |
|------|---------|---------------|
| DevOps Lead | (project owner) | VPS/network/SSL issues |
| Hostinger Support | hPanel ticket | VPS hardware/billing issues |
| Let's Encrypt | community.letsencrypt.org | Certificate issues |

## Escalation Path

1. **Level 1**: Check logs (`docker logs`, `journalctl`) — identify the failing service
2. **Level 2**: Restart the specific service (`docker compose restart <service>`)
3. **Level 3**: Restart all services (`docker compose down && docker compose up -d`)
4. **Level 4**: Check VPS resources (`htop`, `df -h`, `free -h`) — scale if needed
5. **Level 5**: Contact DevOps Lead — root cause investigation
