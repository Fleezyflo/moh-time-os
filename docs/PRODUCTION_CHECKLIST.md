# Production Deployment Checklist

Pre-deployment verification for MOH TIME OS.

---

## 1. Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `INTEL_API_TOKEN` | **REQUIRED** | Bearer token for `/api/v2/intelligence/*` endpoints |
| `SLACK_WEBHOOK_URL` | Recommended | Slack webhook for notification delivery |
| `MOH_TIME_OS_HOME` | Optional | Override default data directory |
| `MOH_TIME_OS_DB` | Optional | Override database path |
| `CORS_ORIGINS` | Optional | Comma-separated allowed origins (default: `*`) |
| `PORT` | Optional | Server port (default: `8420`) |
| `ANTHROPIC_API_KEY` | Optional | For LLM-based commitment extraction |
| `CLAWDBOT_GATEWAY_URL` | Optional | Clawdbot integration |

**Critical:** If `INTEL_API_TOKEN` is not set, authentication is DISABLED.

---

## 2. Database

- [ ] Database file exists at expected path
- [ ] All migrations applied (83 tables + views)
- [ ] Backup strategy configured
- [ ] Write permissions verified

Check: `sqlite3 $DB_PATH ".tables" | wc -w` should be ~83+

---

## 3. API Endpoints

### Core Health
- [ ] `GET /api/health` → 200
- [ ] `GET /api/v2/inbox` → 200

### Intelligence (requires auth in production)
- [ ] `GET /api/v2/intelligence/portfolio/overview` → 200 (with valid token)
- [ ] `GET /api/v2/intelligence/portfolio/overview` → 401 (without token, when INTEL_API_TOKEN set)
- [ ] `GET /api/v2/intelligence/signals/active` → 200
- [ ] `GET /api/v2/intelligence/patterns/active` → 200
- [ ] `GET /api/v2/intelligence/briefing/daily` → 200

### Stub Endpoints (should return 501)
- [ ] `POST /api/tasks/link` → 501 (not implemented)

---

## 4. Intelligence Pipeline

- [ ] Scoring computes without error
- [ ] Signal detection runs (<10s target)
- [ ] Pattern detection runs
- [ ] Proposal generation works
- [ ] Briefing generates

Run: `python -c "from lib.intelligence.engine import IntelligenceEngine; e = IntelligenceEngine(); print(e.run_full_pipeline())"`

---

## 5. UI Build

- [ ] UI built: `time-os-ui/dist/` exists
- [ ] Bundle size reasonable (<500KB JS)
- [ ] All routes accessible:
  - `/` (redirect or index)
  - `/command-center`
  - `/briefing`
  - `/signals`
  - `/patterns`
  - `/proposals`
  - `/portfolio`
  - `/portfolio/:id`

---

## 6. Collectors (if enabled)

- [ ] Google Tasks collector authenticates
- [ ] Calendar collector authenticates
- [ ] Gmail collector authenticates (if configured)
- [ ] Xero collector authenticates (if configured)

---

## 7. Notifications (if configured)

- [ ] Slack webhook URL valid
- [ ] Test notification delivers
- [ ] Notification queue processing

---

## 8. Security Audit

- [ ] No SQL injection (parameterized queries only)
- [ ] No command injection (shell=False or validated inputs)
- [ ] No secrets in logs
- [ ] Auth enabled for intelligence endpoints
- [ ] CORS configured appropriately for environment

---

## 9. Monitoring

- [ ] Logs going to appropriate destination
- [ ] Error tracking configured (if applicable)
- [ ] Health endpoint monitored

---

## Quick Verification Commands

```bash
# 1. Check database
sqlite3 ~/.moh_time_os/data/moh_time_os.db ".tables" | wc -w

# 2. Start server
python -m api.server

# 3. Health check
curl http://localhost:8420/api/health

# 4. Auth check (should fail without token)
curl http://localhost:8420/api/v2/intelligence/portfolio/overview
# Expected: 401 (if INTEL_API_TOKEN set)

# 5. Auth check (should succeed with token)
curl -H "Authorization: Bearer $INTEL_API_TOKEN" \
     http://localhost:8420/api/v2/intelligence/portfolio/overview

# 6. Stub endpoint check
curl -X POST http://localhost:8420/api/tasks/link
# Expected: 501

# 7. Run pipeline
python -c "
from lib.intelligence.engine import IntelligenceEngine
e = IntelligenceEngine()
result = e.run_full_pipeline()
print(f'Pipeline: {result.get(\"pipeline_success\", False)}')
"
```

---

## Pre-Deploy Sign-Off

| Check | Status | Verified By | Date |
|-------|--------|-------------|------|
| Env vars set | ⬜ | | |
| Database ready | ⬜ | | |
| API responding | ⬜ | | |
| Auth working | ⬜ | | |
| Pipeline running | ⬜ | | |
| UI deployed | ⬜ | | |
| Monitoring active | ⬜ | | |

---

**Do not deploy without completing this checklist.**
