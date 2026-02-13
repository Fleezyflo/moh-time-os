# MOH TIME OS — Build State

**Last Updated:** 2026-02-01  
**Status:** 🟡 PARTIAL — Core working, wiring incomplete

---

## What Works

### Data Layer ✅
- SQLite state.db with 12 tables
- Collectors syncing: Asana, Gmail, Calendar, Tasks (every 1-5 min)
- 40 tasks, 10 calendar events in DB

### API Layer ⚠️
- FastAPI server running on port 8420
- 26 endpoints implemented
- `/api/priorities` — returns 40 items ✅
- `/api/insights` — returns calendar overlaps ✅
- `/api/events`, `/api/emails` — working ✅
- `/api/governance/*` — working ✅
- **Missing:** /api/overview, /api/tasks, /api/team, /api/delegations, /api/projects

### Autonomous Loop ⚠️
- `python3 -m lib.autonomous_loop status` — works
- `python3 -m lib.autonomous_loop run` — hangs (needs investigation)
- Last successful cycle: 2026-02-01 17:33

### Dashboard ❌
- `ui/index.html` exists (17KB)
- **Not served** — no static file routing in API
- User hits 404 at root

---

## What's Broken

1. **Dashboard not accessible** — API doesn't serve static files
2. **`run` command hangs** — autonomous loop doesn't complete
3. **Duplicate insights** — same 2 calendar overlaps repeated 60x
4. **Design mismatch** — implementation differs from DESIGN_V4_SURGICAL.md

---

## Gap: Design vs Implementation

| DESIGN_V4 Spec | Implemented |
|----------------|-------------|
| /api/overview | ❌ |
| /api/calendar | /api/events, /api/day, /api/week |
| /api/tasks | ❌ |
| /api/team | ❌ |
| /api/delegations | ❌ |
| /api/inbox | /api/emails |
| /api/projects | ❌ |
| /api/decisions | /api/approvals |
| 10-page dashboard | 1 HTML file, not served |

---

## Critical Path

See `MASTER_CHECKLIST.md` for full plan.

**Immediate:**
1. Fix dashboard serving (add static file route)
2. Fix autonomous loop `run` command
3. Deduplicate insights (don't re-insert same anomaly)

**Then:**
- Align API to DESIGN_V4 spec
- Complete dashboard pages
- Wire governance to all writes

---

## Commands

```bash
# Check status
cd ~/clawd/moh_time_os && source .venv/bin/activate
python3 -m lib.autonomous_loop status

# Test API
curl http://localhost:8420/api/priorities
curl http://localhost:8420/api/insights
curl http://localhost:8420/api/health

# Check logs
cat /tmp/time-os-collect.log
```
