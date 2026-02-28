#!/usr/bin/env bash
# QUICK DEPLOYMENT - Copy & paste commands into your VPS terminal
# SSH first: ssh -i ~/.ssh/id_ed25519_hostinger root@76.13.210.250

cat << 'EOF'

╔═════════════════════════════════════════════════════════════════════════════╗
║                   OPENCLAW VPS DEPLOYMENT - QUICK START                    ║
║                         v2026.2.27-ws23                                    ║
║                                                                             ║
║ Copy each command block into your SSH session on VPS                      ║
╚═════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: SSH to VPS                                                          │
└─────────────────────────────────────────────────────────────────────────────┘

  ssh -i ~/.ssh/id_ed25519_hostinger root@76.13.210.250


┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Navigate to deployment directory                                    │
└─────────────────────────────────────────────────────────────────────────────┘

  cd /docker/openclaw-sgnl


┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Pull latest code & run full deployment                             │
└─────────────────────────────────────────────────────────────────────────────┘

  git fetch origin main && \
  git reset --hard origin/main && \
  bash docker/scripts/check-env.sh && \
  bash tests/pre-test-checklist.sh && \
  docker compose --profile maintenance run --rm backup-config 2>/dev/null && \
  bash tests/regression-tests.sh


┌─────────────────────────────────────────────────────────────────────────────┐
│ WHAT TO EXPECT                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

✓ check-env.sh output:
    ✓ OPENCLAW_GATEWAY_TOKEN (first8....last4)
    ✓ OPENROUTER_API_KEY (first8....last4)
    ✓ BRAVE_API_KEY (first8....last4)
    ✓ LINE_CHANNEL_SECRET (first8....last4)
    ✓ LINE_CHANNEL_ACCESS_TOKEN (first8....last4)

✓ pre-test-checklist.sh output:
    All checks passed! Ready to run regression tests.

✓ regression-tests.sh output:
    Passed: 20+ / 20+
    Failed: 0 / 20+
    ✓ All regression tests passed!


┌─────────────────────────────────────────────────────────────────────────────┐
│ IF ANY TEST FAILS                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

1. Check container health:
   $ docker ps --filter name=openclaw --format "table {{.Names}}\t{{.Status}}"

2. View recent errors:
   $ docker logs --since=5m openclaw-sgnl-openclaw-1

3. Verify environment:
   $ bash docker/scripts/check-env.sh

4. Check volume mount:
   $ docker inspect openclaw-sgnl-openclaw-1 | grep -A5 openclaw-state

5. See full troubleshooting:
   $ cat tests/REGRESSION-TESTING.md


┌─────────────────────────────────────────────────────────────────────────────┐
│ MANUAL LINE TEST MESSAGES (after automated tests pass)                      │
└─────────────────────────────────────────────────────────────────────────────┘

Message 1A (time check - session_status):
    ตอนนี้กี่โมงแล้วครับ
    
    Expected response: เวลา [time] ค่ะ (no Unknown sessionId error)


Message 1B (model check):
    ใช้โมเดลไหน
    
    Expected response: ใช้ Gemini 2.5 Flash ค่ะ


Message 2A (exec date - no approval):
    รันคำสั่ง date
    
    Expected response: Tue Feb 17 15:32:45 +07 2026


Message 3A (whoami on gateway):
    แสดงผู้ใช้ปัจจุบัน
    
    Expected response: node (or root)


Message 4B (web_search with BRAVE_API_KEY):
    ค้นหาราคาทองวันนี้
    
    Expected response: [gold price in baht]


Message 8 (combined - all tools):
    ตอนนี้กี่โมง ราคาทอง เท่าไหร่ และบอกผู้ใช้ปัจจุบัน
    
    Expected response: 
        เวลา [time] ค่ะ
        ตัวเองคือ node
        ราคาทองแท่งวันนี้ [price] บาท


┌─────────────────────────────────────────────────────────────────────────────┐
│ VERIFY PERSISTENCE (after manual tests)                                     │
└─────────────────────────────────────────────────────────────────────────────┘

1. Restart container:
   $ docker restart openclaw-sgnl-openclaw-1

2. Wait 15 seconds:
   $ sleep 15

3. Send time check message again:
   "ตอนนี้กี่โมงแล้ว"
   
   Expected: Bot responds with current time (config persisted)


┌─────────────────────────────────────────────────────────────────────────────┐
│ SUCCESS CHECKLIST                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

Automated Tests (regression-tests.sh):
  [ ] KI-009: Volume mount correct (/data/.openclaw)
  [ ] KI-002: exec safeBins configured
  [ ] KI-010: exec host = gateway
  [ ] KI-012: Environment variables set
  [ ] No MissingEnvVarError in logs
  [ ] No "Unknown sessionId" errors
  [ ] 20+/20+ tests passed

Manual LINE Tests:
  [ ] Message 1A: time works (session_status)
  [ ] Message 1B: model info works
  [ ] Message 2A: exec date runs without approval
  [ ] Message 3A: whoami works on gateway
  [ ] Message 4B: web_search returns results
  [ ] Message 8: all tools work together

Persistence Tests:
  [ ] Container restart
  [ ] Config recovered from volume
  [ ] Bot responds after restart

Overall Status:
  [ ] v2026.2.27-ws23 READY FOR PRODUCTION


┌─────────────────────────────────────────────────────────────────────────────┐
│ REFERENCES                                                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Full deployment guide: tests/REGRESSION-TESTING.md
Manual test messages: tests/LINE-REGRESSION-MESSAGES.md
Test suite overview: tests/README.md
Known issues: docs/debug/tiered-debug-sop.md (KI-009 through KI-012)
GitHub commit: https://github.com/Piboonsak/openclaw_github/commit/4df70ba9c4dcb34688a1e297272ce5dde169463e
GitHub issues: https://github.com/Piboonsak/Openclaw/issues/1 (reply context)
               https://github.com/Piboonsak/Openclaw/issues/2 (auto memory)


═════════════════════════════════════════════════════════════════════════════════

Ready? Copy the STEP 3 command into your VPS terminal now!

EOF
