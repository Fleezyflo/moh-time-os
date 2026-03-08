# HANDOFF -- Audit Remediation

**Generated:** 2026-03-08
**Current Phase:** phase-09 (pending)
**Current Session:** 9
**Track:** T2 in progress

---

## What Just Happened

### Session 008 -- Phase 08: Verify Cleanup + API + Production

Verification-only phase. Investigated 4 areas via code reading: tier excision, morning brief excision, API route completeness, and production readiness. All 4 tasks produced DONE or GAP reports.

**Results:**
- Task 01 (tier excision): **DONE** -- feature_flags.yaml, tier_calculator.py, test_tier_calculator.py all deleted. Zero Tier 0-4 references. Client tiers A/B/C are legitimate and remain.
- Task 02 (morning brief excision): **DONE with GAP** -- All old brief files deleted (lib/brief.py, lib/notifier/briefs.py, lib/notifier/channels/clawdbot.py, lib/integrations/clawdbot_api.py, lib/time_truth/brief.py). New `lib/detectors/morning_brief.py` is sole active brief. GAP-08-01 found.
- Task 03 (API route completeness): **DONE with GAPs** -- 217 routes in system-map.json. All UI fetch calls have matching handlers. GAP-08-02, GAP-08-03, GAP-08-04 found.
- Task 04 (production readiness): **DONE with GAPs** -- Error handling, logging, graceful shutdown, health checks, config, secrets, security, backup, monitoring, self-healing all verified. GAP-08-05, GAP-08-06, GAP-08-07 found.

**7 gaps found:**
- **GAP-08-01 (low):** 4 stale Clawdbot references in comments/docstrings: cron_tasks.py:4, cron_tasks.py:248, autonomous_loop.py:44, notifier/__init__.py:5
- **GAP-08-02 (medium):** System map generator misses ~43 routes from 6 sub-routers (intelligence_router, sse_router, paginated_router, export_router, governance_router, action_router, chat_webhook_router)
- **GAP-08-03 (medium):** ui_api_calls always empty in system-map.json -- generator looks for literal `fetch('/api/...')` but UI uses `fetchJson(${API_BASE}/...)` wrapper
- **GAP-08-04 (low):** UI calls `/api/v2/search` (api.ts:1732) but spec_router has no search endpoint -- only server.py has `/api/search`
- **GAP-08-05 (medium):** validate_production.py is minimal -- checks imports/DB/snapshot/tests but not API endpoints, daemon cycle, or notification system
- **GAP-08-06 (low):** /api/health returns `{"status": "healthy"}` unconditionally without checking DB, daemon, or subsystems
- **GAP-08-07 (low):** CORS defaults to `"*"` with no production-mode warning or enforcement

**Status:** PR #TBD (branch: verify/cleanup-api-production)

---

## What's Next

### Phase 09: Verify Operations
- 3 verification tasks -- reporting only, no code changes
- See `audit-remediation/plan/phase-09.yaml`
- Tasks: verify collector coverage, test coverage counts, 24h unattended operation

---

## Key Rules

1. Never run git from sandbox (creates .git/index.lock)
2. Never format from sandbox (ruff version mismatch)
3. Verification phases (07-13) report DONE or GAP, never fix inline
4. All rules from CLAUDE.md apply
5. Match existing patterns -- logging.getLogger(__name__), %s format, narrowed exception types
6. No `noqa`, `nosec`, `# type: ignore` -- fix the root cause
7. Commit subject under 72 chars, first letter after prefix lowercase
8. GAP-07-01 exists: engagements not in schema.py -- do not fix during T2 verification
9. GAP-08-01 through GAP-08-07 exist -- do not fix during T2 verification

---

## Documents to Read

1. `audit-remediation/AGENT.md` -- Engineering standards for this project
2. `audit-remediation/plan/phase-09.yaml` -- Next phase
3. `audit-remediation/state.json` -- Current project state
4. `CLAUDE.md` -- Repo-level engineering rules
