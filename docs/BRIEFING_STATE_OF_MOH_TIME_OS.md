# MOH TIME OS — State of the System
> **Generated:** 2025-02-13 | **Status:** Post-Stabilization

---

## What It Is

A personal executive operating system that ingests data from Google Workspace (Gmail, Calendar, Chat, Drive), Asana, and Xero, then surfaces issues, priorities, and operational intelligence via a dashboard UI.

**Core thesis:** Runs autonomously without AI in the critical path. Signal detection → Proposal surfacing → Manual tagging → Issue lifecycle → Resolution.

---

## What's Actually Working (Production)

| Layer | Component | Status | Notes |
|-------|-----------|--------|-------|
| **Data Collection** | Gmail, Calendar, Chat, Drive | ✅ Stable | 20 subjects, full-sweep exhaustive, cursor-based resume |
| **Data Collection** | Asana sync | ✅ Working | Tasks/projects linked |
| **Data Collection** | Xero sync | ✅ Working | Invoices/payments |
| **Storage** | SQLite (moh_time_os.db) | ✅ Stable | ~500K rows across 100+ tables |
| **API** | FastAPI `/api/v2/*` | ✅ Stable | spec_router.py (v2.9 spec) |
| **UI** | React dashboard | ✅ Working | Vite + TailwindCSS, served at :8420 |
| **Safety** | Write context, audit log, triggers | ✅ Enforced | All v29 tables have SAFETY triggers |
| **Tests** | 297 tests | ✅ All pass | Contract + golden + safety tests |

### Live Data Counts
- Gmail: 255 messages | Calendar: 38,643 events | Chat: 183,244 messages | Drive: 17,722 files
- Clients: 160 | Projects: 354 | Tasks: 3,946 | Invoices: 1,254 | People: 71
- Issues (v29): 6 | Inbox items (v29): 121

---

## Architecture Layers (What Exists)

```
┌─────────────────────────────────────────────────────────────┐
│  UI (time-os-ui/)           React dashboard, spec v2.9     │
├─────────────────────────────────────────────────────────────┤
│  API (api/)                 FastAPI, spec_router.py        │
├─────────────────────────────────────────────────────────────┤
│  Engine Layer               lib/ui_spec_v21/ (active)      │
│                             lib/v4/ (partial, spec-based)  │
│                             lib/v5/ (skeleton)             │
├─────────────────────────────────────────────────────────────┤
│  Core Services              lib/*.py (~80 modules)         │
├─────────────────────────────────────────────────────────────┤
│  Collectors                 lib/collectors/ + collectors/  │
├─────────────────────────────────────────────────────────────┤
│  Storage                    SQLite + sync cursors          │
└─────────────────────────────────────────────────────────────┘
```

---

## What's Intentional vs Byproduct

| Category | Items | Status |
|----------|-------|--------|
| **Intentional & Active** | Data collectors, api/spec_router.py, lib/ui_spec_v21/, lib/safety/, tests/, time-os-ui/ | Production |
| **Intentional but Dormant** | lib/v4/ (SPEC_V4), lib/v5/ (next iteration), lib/autonomous_loop.py | Built, not wired |
| **Legacy / Superseded** | api/server.py (179KB monolith), lib/aggregator.py, lib/moves.py, collectors/_legacy/ | Kept for reference |
| **Byproduct / Scaffolding** | Many lib/*.py modules from exploratory work | May have dead code |
| **Documentation Sprawl** | 1,039 .md files, many spec iterations | Needs cleanup |

---

## Architecture Versions

| Version | Location | Status |
|---------|----------|--------|
| **v2.1 / v2.9** | `lib/ui_spec_v21/`, `api/spec_router.py` | **ACTIVE** — powers current dashboard |
| **v4** | `lib/v4/`, `SPEC_V4_EXECUTIVE_OS.md` | **BUILT** — artifact-centric proposal system, not yet integrated |
| **v5** | `lib/v5/` | **SKELETON** — next iteration, mostly stubs |

---

## Key Gaps / Known Issues

1. **v4 not wired:** The proposal → tagging → issue loop (v4 spec) is implemented but not connected to the UI/API.
2. **Docs collector not live:** `docs/` pipeline spec exists but Docs ingestion isn't running.
3. **server.py bloat:** 179KB monolith API alongside lean spec_router.py — redundancy.
4. **Schema sprawl:** 100+ tables, many likely unused. Some are views masquerading as tables.
5. **Test fixture drift:** Fixture schema required manual sync with live DB (fixed today).

---

## File System Layout (Key Paths)

```
moh_time_os/
├── api/                    # FastAPI (spec_router.py = active, server.py = legacy)
├── collectors/             # Top-level collectors (xero, scheduled)
├── engine/                 # Discovery, pulse, tasks_board
├── lib/                    # Core modules (~80 files)
│   ├── collectors/         # Gmail, Chat, Drive, Calendar collectors
│   ├── ui_spec_v21/        # Active API logic (v2.9 spec)
│   ├── safety/             # Write context, audit, triggers
│   ├── v4/                 # Dormant v4 implementation
│   └── v5/                 # Skeleton v5
├── tests/                  # 297 tests (contract, golden, safety)
├── time-os-ui/             # React frontend
├── docs/                   # Agent prompts, outputs, specs
└── data/                   # (runtime) DB, cassettes, exports
```

---

## Next Steps (Recommendations)

1. **Decide v4 fate:** Either wire it up or archive it. Currently occupying headspace.
2. **Prune server.py:** Migrate anything needed to spec_router.py, then delete.
3. **Audit lib/*.py:** Many modules may be dead. Grep for imports, delete unused.
4. **Schema cleanup:** Drop empty/unused tables, consolidate views.
5. **Consolidate docs:** 1,039 .md files is excessive. Archive old specs.

---

## Verification Status (as of 2025-02-13)

| Check | Result |
|-------|--------|
| Full test suite | ✅ 297 passed |
| DB subject coverage | ✅ 20/20 all services |
| Cursor invariants | ✅ All present |
| Safety triggers | ✅ Active on v29 tables |
| API contracts | ✅ All endpoints 200 |

---

*This is the system as it stands. Functional, stable, but carrying weight from multiple spec iterations.*
