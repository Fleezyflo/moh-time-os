# MOH TIME OS — Master Roadmap
> **Updated:** 2026-02-21 | **Owner:** Molham | **Branch:** brief/notification-intelligence

---

## System Identity

A personal executive operating system for hrmny.co (Dubai creative agency). Ingests Google Workspace, Asana, Xero. Surfaces operational intelligence autonomously without AI in the critical path. Single-user (Molham only).

**Production DB:** ~551 MB, 107+ tables, 500K+ rows
**Intelligence layer:** 13,761 lines across 18 modules
**Test suite:** 297+ tests (growing)

---

## Brief Registry

### Legend
| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and committed |
| 📐 | Designed (brief + task files exist) |
| ⚠️ | Designed but shallow (needs deepening) |
| 🔴 | Gap — no brief exists yet |
| 🔒 | Blocked by dependency |

---

### Tier 0: Foundation (Infrastructure Prerequisites)

| # | Brief | Prefix | Tasks | Status | Dependencies | Notes |
|---|-------|--------|-------|--------|--------------|-------|
| — | Test Remediation | TR | 4 | 📐 | None | Python 3.10 compat, missing deps, schema mismatch |
| 5 | Data Foundation | DF | 10 | 📐 | TR | Asana sync fix, Gmail backfill, entity links, capacity lanes |
| 7 | Pipeline Hardening | PH | 7 | 📐 | 5 | Schema alignment, missing tables, f-string SQL, hardcoded config |

**Reality check:** Many TR and PH tasks have been addressed ad-hoc (e.g., datetime.UTC fixed in test fixtures, f-string SQL cleaned up). These briefs need an audit to mark what's actually done vs still needed.

---

### Tier 1: Core System (Running Autonomously)

| # | Brief | Prefix | Tasks | Status | Dependencies | Notes |
|---|-------|--------|-------|--------|--------------|-------|
| 8 | User Readiness | UR | 10 | 📐 | 7 | Excise dead code, truth module wiring, snapshot, daemon activation |
| 9 | Collector Supremacy | CS | 8 | 📐 | 8 | Schema expansion, resilience, deep pulls (Asana/Gmail/Calendar/Xero) |
| 10 | Autonomous Operations | AO | 6 | 📐 | 9 | Loop hardening, change bundles, observability, data lifecycle |

**Reality check:** autonomous_loop.py exists and runs. Collectors are functional. Truth modules wired. Brief 8-10 describe hardening of *already-running* infrastructure. Some tasks may be partially done.

---

### Tier 2: Intelligence (Compute & Persist)

| # | Brief | Prefix | Tasks | Status | Dependencies | Notes |
|---|-------|--------|-------|--------|--------------|-------|
| 11 | Intelligence Expansion | IE | 7 | ⚠️ | 10 | Cost-to-serve, patterns, scenarios, trajectory — **most modules already built**. IE-5.1 (V4/V5 consolidation) moved to Brief 29. |
| 17 | Intelligence Wiring | IW | 5 | ✅ | 11 | Tables, health unifier, daemon wiring, events, validation — **ALL DONE** |
| 18 | Intelligence Depth | ID | 6 | 📐 | 17 | Correlation confidence, cost proxies, entity profiles, outcomes, trending — **deepened with exact formulas** |

**Reality check:** Brief 11's modules (cost_to_serve.py, patterns.py, scenario_engine.py, trajectory.py) ALL EXIST and are functional. Brief 11 should be closed as "substantially complete."

---

### Tier 3: Memory & Prediction (Learn & Forecast)

| # | Brief | Prefix | Tasks | Status | Dependencies | Notes |
|---|-------|--------|-------|--------|--------------|-------|
| 22 | Strategic Memory | SM | 4 | 📐 | 17, 18 | Decision journal, entity memory, signal lifecycle, behavioral patterns |
| 23 | Predictive Scheduling | PS | 5 | 📐 | 11, 9, 5 | Capacity forecast, deadline prediction, cashflow, meeting analysis |

---

### Tier 4: Action & Delivery (Act & Notify)

| # | Brief | Prefix | Tasks | Status | Dependencies | Notes |
|---|-------|--------|-------|--------|--------------|-------|
| 15 | Bidirectional Integrations | BI | 5 | 📐 | 14 | Asana/Gmail/Calendar writeback, action framework |
| 21 | Notification Intelligence | NI | 5 | 📐 | 15, 19 | Routing, digest engine, email digest, muting, analytics |
| 24 | Prepared Intelligence | PI | 5 | 📐 | 17, 18, 22, 15, 23 | Preparation engine, Asana overlay, drafting, daily briefing, surfaces |

---

### Tier 5: Interface (Surface & Converse)

| # | Brief | Prefix | Tasks | Status | Dependencies | Notes |
|---|-------|--------|-------|--------|--------------|-------|
| 12 | Interface Experience | IX | 6 | 📐 | 9, 10, 11 | Design system, dashboard, resolution UI, scenario UI, real-time |
| 25 | Conversational Interface | CI | 4 | 📐 | 18, 22, 24, 23 | Query engine, synthesis, action routing, chat UI |

---

### Tier 6: Hardening & Governance (Productionize)

| # | Brief | Prefix | Tasks | Status | Dependencies | Notes |
|---|-------|--------|-------|--------|--------------|-------|
| 13 | Security Hardening | SH | 5 | 📐 | 12 | API keys, RBAC, rate limits, credential audit |
| 14 | Performance & Scale | PS | 5 | 📐 | 13 | N+1 queries, caching, PostgreSQL compat, pagination |
| 16 | Data Governance | DG | 5 | 📐 | 9, 10, 13 | Classification, export, subject access, retention, compliance |

---

### New Briefs (Gap Coverage)

| # | Brief | Prefix | Tasks | Status | Dependencies | Notes |
|---|-------|--------|-------|--------|--------------|-------|
| 26 | Intelligence API Surface | IA | 6 | 📐 | 18 | Router, entity endpoints, portfolio, signals/patterns, scenarios, contract tests |
| 27 | Data Quality Scoring | DQ | 5 | 📐 | 9 | Freshness tracker, completeness scorer, confidence adjuster, quality dashboard, validation |
| 28 | Intelligence Observability | IO | 5 | 📐 | 17, 18 | Audit trail, explainability, drift detection, debug mode, validation |
| 29 | V4/V5 Reconciliation | VR | 5 | 📐 | None | Audit, migrate, consumer cleanup, archive, validation |
| 30 | Adaptive Thresholds | AT | 5 | 📐 | 22, 28 | Effectiveness scorer, calibration engine, seasonal modifiers, reporting, validation |
| 31 | Temporal & Contextual Intelligence | TC | 5 | 📐 | 9 | Business calendar, temporal normalization, recency weighting, signal lifecycle, validation |

**Total new design work:** 6 briefs, 31 task files, ~8,350 estimated lines.

---

## Dependency Graph (Realistic Sequencing)

```
PARALLEL TRACK A: Intelligence Deepening
  Brief 17 (IW) ✅ DONE
    → Brief 18 (ID) — Intelligence Depth [deepened]
      → Brief 22 (SM) — Strategic Memory
        → Brief 30 (AT) — Adaptive Thresholds
      → Brief 28 (IO) — Intelligence Observability
      → Brief 26 (IA) — Intelligence API Surface
        → Brief 12 (IX) — Interface Experience
          → Brief 25 (CI) — Conversational Interface

PARALLEL TRACK B: Predictive & Scheduling
  Brief 23 (PS) — Predictive Scheduling
    → Brief 24 (PI) — Prepared Intelligence (also needs 18, 22, 15)

PARALLEL TRACK C: Action & Delivery
  Brief 15 (BI) — Bidirectional Integrations
    → Brief 21 (NI) — Notification Intelligence
    → Brief 24 (PI) — Prepared Intelligence

PARALLEL TRACK D: Infrastructure Hardening
  Brief 10 (AO) — Autonomous Operations
    → Brief 13 (SH) — Security Hardening
      → Brief 14 (PS-perf) — Performance & Scale
        → Brief 16 (DG) — Data Governance

PARALLEL TRACK E: Foundation Enhancement (can run anytime)
  Brief 29 (VR) — V4/V5 Reconciliation
  Brief 27 (DQ) — Data Quality Scoring
  Brief 31 (TC) — Temporal & Contextual Intelligence
  Brief 11 (IE) — audit and close (most tasks already done)
```

---

## Recommended Execution Order

### Wave 1 (Immediate — Intelligence Depth + Foundation)
1. **Brief 18 (ID)** — Intelligence Depth & Cross-Domain Synthesis
2. **Brief 29 (VR)** — V4/V5 Architecture Reconciliation (parallel, cleanup)
3. **Brief 31 (TC)** — Temporal & Contextual Intelligence (parallel, no blockers)

### Wave 2 (Memory & Quality)
4. **Brief 22 (SM)** — Strategic Memory & Decision Journal
5. **Brief 27 (DQ)** — Data Quality Scoring (parallel)
6. **Brief 28 (IO)** — Intelligence Observability (parallel, needs 18)

### Wave 3 (API Surface + Prediction)
7. **Brief 26 (IA)** — Intelligence API Surface (needs 18)
8. **Brief 23 (PS)** — Predictive Scheduling (parallel)
9. **Brief 15 (BI)** — Bidirectional Integrations (parallel)

### Wave 4 (Delivery & Notification)
10. **Brief 21 (NI)** — Notification Intelligence
11. **Brief 24 (PI)** — Prepared Intelligence
12. **Brief 30 (AT)** — Adaptive Thresholds (needs 22 + 28)

### Wave 5 (Surface & Converse)
13. **Brief 12 (IX)** — Interface Experience
14. **Brief 25 (CI)** — Conversational Interface

### Wave 6 (Hardening)
15. **Brief 10 (AO)** — Autonomous Operations hardening
16. **Brief 13 (SH)** — Security
17. **Brief 14 (PS-perf)** — Performance
18. **Brief 16 (DG)** — Data Governance

---

## Brief 11 (IE) — Status Reconciliation

Brief 11 was designed to BUILD intelligence modules from scratch. Reality: they're all built.

| Task | Designed | Reality |
|------|----------|---------|
| IE-1.1 Cost-to-Serve | Build from scratch | `cost_to_serve.py` exists (526 lines) |
| IE-2.1 Pattern Recognition | Build pattern engine | `patterns.py` exists (1,579 lines) |
| IE-3.1 Scenario Modeling | Build scenario engine | `scenario_engine.py` exists (1,060 lines) |
| IE-4.1 Trajectory | Build trajectory computer | `trajectory.py` exists (694 lines) |
| IE-5.1 V4/V5 Consolidation | Merge architectures | **Moved to Brief 29 (VR)** |
| IE-6.1 Resolution Queue | Wire automation | `auto_resolution.py` exists but escalation is stub |
| IE-7.1 Validation | End-to-end test | Partially covered by IW-5.1 tests |

**Recommendation:** Close Brief 11 as "substantially complete." IE-5.1 is now Brief 29. IE-6.1 residual work folds into a hardening task.

---

## Cross-Brief Integration Map

New briefs wire into the existing system at these touch points:

| New Brief | Feeds Into | Consumes From |
|-----------|-----------|---------------|
| 26 (IA) | Brief 12 (IX) UI endpoints | Brief 18 (ID) entity profiles, signals, patterns |
| 27 (DQ) | Brief 18 (ID) confidence modifier | Brief 9 (CS) collector freshness data |
| 28 (IO) | Brief 24 (PI) explainability, Brief 30 (AT) drift detection | Brief 17 (IW) score_history, signal_state |
| 29 (VR) | All briefs (cleaner codebase) | lib/v4/, lib/v5/ audit |
| 30 (AT) | Brief 17 thresholds.yaml | Brief 22 (SM) decision journal, Brief 28 drift detection |
| 31 (TC) | Brief 18 scoring normalization, Brief 30 seasonal modifiers | Brief 9 calendar data, config/business_calendar.yaml |

---

## Metrics

| Metric | Before This Session | After This Session |
|--------|--------------------|--------------------|
| Briefs designed | 19 | 25 (+6 gap briefs) |
| Briefs implemented | 1 (Brief 17) | 1 (Brief 17) |
| Task files | ~115 | ~146 (+31 new task files) |
| Intelligence test coverage | 74 tests | 74 (implementation agent will grow this) |
| Intelligence modules | 18 files, 13,761 lines | 18 (implementation agent will grow this) |
| Estimated new code | — | ~8,350 lines across 6 new briefs |
| Brief 18 tasks deepened | — | ID-1.1, ID-2.1, ID-3.1, ID-6.1 (exact formulas, SQL, fixtures) |
