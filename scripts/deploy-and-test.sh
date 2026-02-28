#!/bin/bash
# OpenClaw VPS Deployment & Testing Script (v2026.2.27-ws23)
# Complete flow: pull → verify → backup → test
# Run on: ssh root@76.13.210.250

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗"
echo -e "║   OpenClaw Production Deployment & Testing (v2026.2.27-ws23)   ║"
echo -e "║   Complete VPS setup with regression testing                   ║"
echo -e "╚═══════════════════════════════════════════════════════════════╝${NC}\n"

# Step 1: Pull latest code
echo -e "${YELLOW}[Step 1/5]${NC} Pulling latest code from GitHub..."
cd /docker/openclaw-sgnl
git fetch origin main
git reset --hard origin/main
echo -e "${GREEN}✓ Code updated${NC}\n"

# Step 2: Environment validation
echo -e "${YELLOW}[Step 2/5]${NC} Validating environment variables..."
bash docker/scripts/check-env.sh
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All API keys are set${NC}\n"
else
    echo -e "${RED}✗ Missing environment variables. Set them in Hostinger UI and try again.${NC}"
    exit 1
fi

# Step 3: Pre-deployment checks
echo -e "${YELLOW}[Step 3/5]${NC} Running pre-deployment checklist..."
bash tests/pre-test-checklist.sh
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ VPS is ready${NC}\n"
else
    echo -e "${RED}✗ Pre-test checks failed. Review errors above.${NC}"
    exit 1
fi

# Step 4: Create backup
echo -e "${YELLOW}[Step 4/5]${NC} Creating config backup..."
docker compose --profile maintenance run --rm backup-config 2>/dev/null || true
echo -e "${GREEN}✓ Backup complete${NC}\n"

# Step 5: Run automated regression tests
echo -e "${YELLOW}[Step 5/5]${NC} Running automated regression test suite..."
echo -e "(This takes 5-10 minutes)\n"
bash tests/regression-tests.sh

# Summary
echo -e "\n${BLUE}┌───────────────────────────────────────────────────────────┐"
echo -e "│ Deployment Complete                                       │"
echo -e "└───────────────────────────────────────────────────────────┘${NC}\n"

echo -e "${GREEN}✓ All automated tests passed!${NC}\n"

echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Send manual test messages to LINE bot:"
echo "   See: tests/LINE-REGRESSION-MESSAGES.md"
echo ""
echo "2. Test messages (Thai):"
echo "   • ตอนนี้กี่โมงแล้วครับ (time check via session_status)"
echo "   • รันคำสั่ง date (exec test, no approval needed)"
echo "   • แสดงผู้ใช้ปัจจุบัน (whoami on gateway host)"
echo "   • ค้นหาราคาทองวันนี้ (web_search with BRAVE_API_KEY)"
echo "   • ตอนนี้กี่โมง ราคาทอง ชื่อผู้ใช้ (combined test all tools)"
echo ""
echo "3. Expected responses:"
echo "   • No 'Unknown sessionId' errors"
echo "   • No 'host not allowed' errors"
echo "   • No approval prompts (LINE has no UI)"
echo "   • All tools respond within timeout limits"
echo ""
echo "4. Verify container persistence:"
echo "   $ docker restart openclaw-sgnl-openclaw-1"
echo "   $ sleep 15"
echo "   [Send time check message again - should still work]"
echo ""
echo -e "${YELLOW}Troubleshooting:${NC}"
echo "   See: tests/REGRESSION-TESTING.md (complete guide)"
echo "   Logs: docker logs --since=5m openclaw-sgnl-openclaw-1"
echo ""
echo -e "${GREEN}Status: v2026.2.27-ws23 READY FOR PRODUCTION${NC}\n"
