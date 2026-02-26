# MOH Time OS — System Map

**Generated**: 2026-02-24 | **Branch**: main (post PR #27 merge)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  UI (React + Vite)  :5173                           │
│  Calls /api/v2/* via proxy → localhost:8420          │
├─────────────────────────────────────────────────────┤
│  API (FastAPI + Uvicorn)  :8420                     │
│  ├── server.py       → 140+ routes at /api/*        │
│  ├── spec_router.py  → ~35 routes at /api/v2/*      │
│  └── auth.py         → passthrough (single-user)    │
├─────────────────────────────────────────────────────┤
│  Services                                           │
│  ├── lib/ui_spec_v21/   → spec-compliant endpoints  │
│  ├── lib/intelligence/  → signals, patterns, scores │
│  ├── lib/capacity_truth/ → lanes, debt              │
│  ├── lib/client_truth/   → health, linking          │
│  ├── lib/time_truth/     → calendar, scheduling     │
│  ├── lib/commitment_truth/ → commitments            │
│  ├── lib/collectors/     → sync orchestration       │
│  └── lib/governance/     → approval, safety         │
├─────────────────────────────────────────────────────┤
│  Data                                               │
│  ├── lib/schema.py        → TABLES declaration      │
│  ├── lib/schema_engine.py → convergence engine      │
│  ├── lib/db.py            → connection + migrations │
│  └── lib/state_store.py   → query interface         │
└─────────────────────────────────────────────────────┘
```

## Root Cause: Why the UI Is Broken

The UI calls `/api/v2/*` endpoints (via Vite proxy). The backend spec_router provides ~35 routes. **The UI expects ~67+ routes.** The gap breaks the UI in three ways:

### 1. Entire Intelligence Layer Missing (21 endpoints)

The UI has a full intelligence section (`/intel/*` routes) that calls `/api/v2/intelligence/*`. **None of these endpoints exist in spec_router.** Every intelligence page returns 404.

| Missing Endpoint | UI Page |
|---|---|
| `GET /intelligence/critical` | Command Center — critical items |
| `GET /intelligence/briefing` | Briefing page |
| `GET /intelligence/signals` | Signals page |
| `GET /intelligence/signals/summary` | Signal summary widget |
| `GET /intelligence/signals/active` | Active signals view |
| `GET /intelligence/signals/history` | Signal history |
| `GET /intelligence/patterns` | Patterns page |
| `GET /intelligence/patterns/catalog` | Pattern catalog |
| `GET /intelligence/proposals` | Intelligence proposals |
| `GET /intelligence/scores/client/{id}` | Client scorecard |
| `GET /intelligence/scores/project/{id}` | Project scorecard |
| `GET /intelligence/scores/person/{id}` | Person scorecard |
| `GET /intelligence/scores/portfolio` | Portfolio health |
| `GET /intelligence/entity/client/{id}` | Client deep dive |
| `GET /intelligence/entity/person/{id}` | Person deep dive |
| `GET /intelligence/entity/portfolio` | Portfolio intelligence |
| `GET /intelligence/projects/{id}/state` | Project state |
| `GET /intelligence/clients/{id}/profile` | Client profile |
| `GET /intelligence/team/{id}/profile` | Person profile |
| `GET /intelligence/clients/{id}/trajectory` | Client trajectory |
| `GET /intelligence/team/{id}/trajectory` | Person trajectory |

**The backend HAS intelligence modules** (`lib/intelligence/`) with signals, patterns, predictive, conversational, and revenue analytics. They are just **not wired into spec_router**.

### 2. Action Endpoints Missing (7 endpoints)

The UI can display proposals, watchers, and fix-data items, but clicking buttons does nothing because the mutation endpoints don't exist:

| Missing Endpoint | UI Action |
|---|---|
| `POST /proposals/{id}/snooze` | Snooze a proposal |
| `POST /proposals/{id}/dismiss` | Dismiss a proposal |
| `POST /watchers/{id}/dismiss` | Dismiss a watcher |
| `POST /watchers/{id}/snooze` | Snooze a watcher |
| `POST /fix-data/{type}/{id}/resolve` | Resolve data conflict |
| `POST /issues` | Create issue from proposal |
| `POST /issues/{id}/notes` | Add note to issue |

### 3. Issue Endpoint Shape Mismatch (3 endpoints)

The spec_router has a generic `POST /issues/{id}/transition`, but the UI calls:

| UI Calls | Backend Has |
|---|---|
| `PATCH /issues/{id}/resolve` | `POST /issues/{id}/transition` |
| `PATCH /issues/{id}/state` | `POST /issues/{id}/transition` |
| `POST /issues/{id}/notes` | Nothing |

## What Works

These `/api/v2` endpoints exist and match the UI:

| Endpoint | UI Page | Status |
|---|---|---|
| `GET /clients` | Client Index | ✅ |
| `GET /clients/{id}` | Client Detail | ✅ |
| `GET /clients/{id}/signals` | Client signals tab | ✅ |
| `GET /clients/{id}/team` | Client team tab | ✅ |
| `GET /clients/{id}/invoices` | Client financials tab | ✅ |
| `GET /clients/{id}/ar-aging` | Client AR aging | ✅ |
| `GET /inbox` | Inbox page | ✅ |
| `GET /inbox/counts` | Inbox tab counts | ✅ |
| `GET /inbox/recent` | Recently actioned | ✅ |
| `POST /inbox/{id}/action` | Inbox actions | ✅ |
| `GET /issues` | Issues page (list) | ✅ |
| `GET /issues/{id}` | Issue detail | ✅ |
| `GET /team` | Team page | ✅ |
| `GET /proposals` | Proposals list | ✅ |
| `GET /watchers` | Watchers list | ✅ |
| `GET /fix-data` | Fix Data page | ✅ |
| `GET /couplings` | Couplings | ✅ |
| `GET /evidence/{type}/{id}` | Evidence trail | ✅ |

## What Also Exists (But UI Doesn't Use)

The old `server.py` routes at `/api/*` (not `/api/v2/*`) are fully implemented (~140 routes). These include capacity management, time blocks, commitments, governance, search, digest, calibration, sync, debugging, and more. The UI was built against the newer `/api/v2` spec and doesn't call these.

## Backend Service Modules (All Verified Working)

| Module | Purpose | Wired to /api/v2? |
|---|---|---|
| `lib/ui_spec_v21/endpoints.py` | Spec-compliant client, inbox, financials | ✅ Yes |
| `lib/intelligence/signals.py` | Signal detection + scoring | ❌ No |
| `lib/intelligence/predictive_intelligence.py` | Pattern detection | ❌ No |
| `lib/intelligence/conversational_intelligence.py` | Briefing, proposals | ❌ No |
| `lib/intelligence/revenue_analytics.py` | Revenue scoring | ❌ No |
| `lib/intelligence/recalibrate.py` | Score recalibration | ❌ No |
| `lib/capacity_truth/` | Lanes, utilization, debt | ❌ No (in /api/ only) |
| `lib/client_truth/` | Health scoring, linking | Partially (via endpoints.py) |
| `lib/time_truth/` | Calendar, scheduling | ❌ No (in /api/ only) |
| `lib/commitment_truth/` | Commitment tracking | ❌ No (in /api/ only) |
| `lib/collectors/` | Data sync | ❌ No (in /api/ only) |
| `lib/governance/` | Approval workflow | ❌ No (in /api/ only) |

## Fix Priority

1. **Wire intelligence endpoints into spec_router** — 21 routes, the intelligence modules exist, they just need routes
2. **Add mutation endpoints** — 7 routes for proposal/watcher/fix-data/issue actions
3. **Fix issue endpoint shape** — add PATCH /resolve, PATCH /state, POST /notes aliases that call the existing transition logic
4. **Total**: ~31 new routes to add to `api/spec_router.py`

## UI Pages

| Route | Page | Data Source | Working? |
|---|---|---|---|
| `/` | Inbox | `/api/v2/inbox/*` | ✅ Data loads |
| `/snapshot` | Snapshot | `/api/v2/proposals`, issues, watchers | ⚠️ Partial (read works, actions fail) |
| `/issues` | Issues | `/api/v2/issues` | ⚠️ Partial (list works, state changes fail) |
| `/clients` | Client Index | `/api/v2/clients` | ✅ Works |
| `/clients/{id}` | Client Detail | `/api/v2/clients/{id}` | ✅ Works |
| `/team` | Team | `/api/v2/team` | ✅ Works |
| `/fix-data` | Fix Data | `/api/v2/fix-data` | ⚠️ Partial (list works, resolve fails) |
| `/intel` | Command Center | `/api/v2/intelligence/*` | ❌ All 404 |
| `/intel/briefing` | Briefing | `/api/v2/intelligence/briefing` | ❌ 404 |
| `/intel/signals` | Signals | `/api/v2/intelligence/signals` | ❌ 404 |
| `/intel/patterns` | Patterns | `/api/v2/intelligence/patterns` | ❌ 404 |
| `/intel/proposals` | Proposals | `/api/v2/intelligence/proposals` | ❌ 404 |
| `/intel/client/{id}` | Client Intel | `/api/v2/intelligence/entity/client/*` | ❌ 404 |
| `/intel/person/{id}` | Person Intel | `/api/v2/intelligence/entity/person/*` | ❌ 404 |
| `/intel/project/{id}` | Project Intel | `/api/v2/intelligence/projects/*` | ❌ 404 |

## File Reference

| File | Purpose | Lines |
|---|---|---|
| `api/server.py` | Main API server, 140+ legacy routes | ~3300 |
| `api/spec_router.py` | Spec-compliant /api/v2 routes | ~1345 |
| `api/auth.py` | Auth passthrough (single-user) | ~230 |
| `lib/ui_spec_v21/endpoints.py` | Spec endpoint implementations | ~1400 |
| `lib/intelligence/signals.py` | Signal detection | ~63 |
| `lib/intelligence/predictive_intelligence.py` | Pattern engine | ~200 |
| `lib/intelligence/conversational_intelligence.py` | Briefing + proposals | ~100 |
| `time-os-ui/src/lib/api.ts` | Control Room API client | ~377 |
| `time-os-ui/src/intelligence/api.ts` | Intelligence API client | ~451 |
| `time-os-ui/src/lib/hooks.ts` | Control Room data hooks | ~120 |
| `time-os-ui/src/intelligence/hooks.ts` | Intelligence data hooks | ~291 |
| `time-os-ui/src/router.tsx` | UI routing (15 routes) | ~480 |
| `time-os-ui/vite.config.ts` | Dev proxy /api → :8420 | ~80 |
