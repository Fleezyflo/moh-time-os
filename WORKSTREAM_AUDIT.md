# Workstream Completion Audit

**Date:** 2026-03-06
**Auditor:** Claude (Session 3)
**Method:** Cross-referenced each task spec in `tasks/` against actual codebase — checked file existence, line counts, function counts, import wiring, and known defects.

---

## Legend

- **DONE** — Code exists, is substantial, and is wired into the system
- **PARTIAL** — Code exists but has known defects or incomplete wiring
- **NOT DONE** — Task spec describes work that hasn't been completed
- **UNWIRED** — Code file exists with real logic but is not imported/called by anything

---

## PH — Pipeline Hygiene

| Task | Status | Detail |
|------|--------|--------|
| PH-1.1 Fix lane column alignment | **NOT DONE** | `lib/lane_assigner.py:190` still has `t.lane` instead of `t.lane_id`. `capacity_command_page7.py` is fixed. |
| PH-1.2 Add communications columns | **DONE** | `from_domain`, `client_id`, `link_status` in schema.py. Migration file exists at `lib/migrations/add_communications_columns.py`. |
| PH-2.1 Create missing tables | **DONE** | `client_identities` and `resolution_queue` defined in schema.py with indexes. |
| PH-3.1 Populate brand IDs | Needs verification | Task spec not read in detail — verify `brand_id` population in clients table. |
| PH-3.2 Derive comm domains | Needs verification | Task spec not read in detail — verify `from_domain` derivation logic. |
| PH-4.1 Fix f-string SQL | **DONE** | Zero f-string SQL outside `safe_sql.py` (which validates identifiers) and `migrations/`. |
| PH-4.2 Fix hardcoded config | **PARTIAL** | Most emails extracted to env vars. **Remaining:** `lib/collectors/chat.py:31` still has hardcoded `DEFAULT_USER = "molham@hrmny.co"` (no `os.environ.get` wrapper). 102 `return {}`/`return []` instances need individual evaluation for error-masking. Zero `except: pass` remaining (good). |
| PH-5.1 Pipeline validation | Needs verification | End-to-end pipeline validation task. |

**Action items:**
1. Fix `lib/lane_assigner.py:190`: `t.lane` → `t.lane_id`
2. Fix `lib/collectors/chat.py:31`: wrap in `os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")`
3. Audit 102 `return {}`/`return []` for error-masking patterns
4. Verify PH-3.1, PH-3.2, PH-5.1

---

## TR — Tech Remediation

| Task | Status | Detail |
|------|--------|--------|
| TR-1.1 Fix datetime.UTC imports | **NOT DONE** | 29 files still use `from datetime import UTC`. No `lib/compat.py` exists. Will crash on Python 3.10. |
| TR-1.2 Fix StrEnum imports | **NOT DONE** | 15 files still use `from enum import StrEnum`. No compat shim. Will crash on Python 3.10. |
| TR-2.1 Install missing dependencies | **DONE** (runtime) | pydantic and fastapi are in pyproject.toml and installed. This was a runtime/venv task, not code. |
| TR-3.1 Fix test fixture schema | **DONE** | `tests/test_task_project_linker.py` fixture uses correct `asana_name`, `project_id` columns. |
| TR-4.1 Full suite validation | Needs verification | Overall test suite pass rate. |

**Action items:**
1. Create `lib/compat.py` with `UTC = timezone.utc` and `StrEnum` backport
2. Replace `from datetime import UTC` in 29 files
3. Replace `from enum import StrEnum` in 15 files
4. Run full test suite to verify

---

## DF — Data Foundation

| Task | Status | Detail |
|------|--------|--------|
| DF-1.1 Fix Asana task sync | **DONE** | `lib/sync_asana.py` exists (not measured but functional, used by collectors). |
| DF-1.2 Gmail historical backfill | **DONE** | `lib/collectors/gmail.py` (706 lines, 23 functions). |
| DF-1.3 Auto client tiers | **DONE** | `lib/classify.py` (294 lines, 8 functions). |
| DF-2.1 Populate engagements | Needs verification | Check if engagements table populated. |
| DF-2.2 Confirm entity links | **DONE** | `lib/entity_linker.py` (458 lines, 11 functions). |
| DF-2.3 Link orphan projects | **DONE** | `lib/link_projects.py` exists. `lib/task_project_linker.py` (222 lines, 5 functions). |
| DF-3.1 Calibrate signal thresholds | **DONE** | `lib/calibration.py` (196 lines). |
| DF-3.2 Resume sync schedule | **DONE** | `lib/cron_tasks.py` exists. Collectors have scheduling. |
| DF-3.3 Capacity lanes bootstrap | **DONE** | `lib/capacity_truth/lane_bootstrap.py` (387 lines). |
| DF-4.1 Data foundation validation | Needs verification | End-to-end validation. |

**Action items:**
1. Verify DF-2.1, DF-4.1

---

## UR — Unification/Readiness

| Task | Status | Detail |
|------|--------|--------|
| UR-1.1 Excise tier system | Needs verification | Check if old tier/scoring labels removed from views. (Phase 15f addresses remnants.) |
| UR-1.2 Excise morning brief (old) | Needs verification | Old morning brief may have been replaced by Phase 15e. |
| UR-2.1 Wire truth modules | **DONE** | All 4 truth modules wired in `autonomous_loop.py` (time_truth, commitment_truth, capacity_truth, client_truth) and `server.py`. |
| UR-2.2 Initialize time blocks | **DONE** | `lib/time_truth/block_manager.py` (472 lines). |
| UR-2.3 Seed commitments | **DONE** | `lib/commitment_truth/commitment_manager.py` (407 lines). |
| UR-3.1 Upgrade snapshot builders | **DONE** | `lib/agency_snapshot/` exists with multiple page generators (1000+ lines each). |
| UR-3.2 Unify aggregation | **DONE** | `lib/aggregator.py` exists, imported in autonomous_loop.py. |
| UR-4.1 Google Chat notifications | **DONE** | `lib/notifier/channels/google_chat.py` (92 lines), wired into NotificationEngine. |
| UR-5.1 Daemon first cycle | **DONE** | `lib/daemon.py` (688 lines). |
| UR-6.1 API verification | Needs verification | |
| UR-6.2 Production readiness | Needs verification | |

**Action items:**
1. Verify UR-1.1, UR-1.2, UR-6.1, UR-6.2

---

## CS — Collector System

| Task | Status | Detail |
|------|--------|--------|
| CS-1.1 Expand DB schema | **DONE** | `lib/schema.py` is comprehensive (1400+ lines). |
| CS-2.1 Collector resilience | **DONE** | `lib/collectors/resilience.py` (203 lines, retry/backoff logic, 11 references). |
| CS-3.1 Asana deep pull | **DONE** | `lib/collectors/asana.py` (641 lines, 11 functions). |
| CS-4.1 Gmail expansion | **DONE** | `lib/collectors/gmail.py` (706 lines, 23 functions). |
| CS-4.2 Chat expansion | **DONE** | `lib/collectors/chat.py` (488 lines, 15 functions). |
| CS-5.1 Calendar expansion | **DONE** | `lib/collectors/calendar.py` (524 lines, 17 functions). |
| CS-5.2 Xero expansion | **DONE** | `lib/collectors/xero.py` (539 lines, 12 functions). |
| CS-6.1 Coverage audit | Needs verification | |

**Action items:**
1. Verify CS-6.1 coverage audit results

---

## AO — Autonomous Operations

| Task | Status | Detail |
|------|--------|--------|
| AO-1.1 Harden autonomous loop | **DONE** | `lib/autonomous_loop.py` (1100+ lines), proper error handling per phase, gate system. |
| AO-2.1 Wire change bundles | **DONE** | `lib/change_bundles.py` (612 lines), `BundleManager` imported in autonomous_loop.py. |
| AO-3.1 Production observability | **DONE** | `lib/observability/` (7 modules: metrics, tracing, health, logging, middleware, context, log_schema). |
| AO-4.1 Data lifecycle | **DONE** | `lib/data_lifecycle.py` (571 lines). |
| AO-5.1 Core test coverage | Needs verification | Check actual test count and pass rate. |
| AO-6.1 Unattended validation | Needs verification | |

**Action items:**
1. Verify AO-5.1, AO-6.1

---

## DQ — Data Quality

| Task | Status | Detail |
|------|--------|--------|
| DQ-1.1 Freshness tracker | **UNWIRED** | `lib/intelligence/data_freshness.py` (330 lines) exists but 0 imports from outside itself. |
| DQ-2.1 Completeness scorer | **UNWIRED** | `lib/intelligence/completeness_scorer.py` (271 lines) exists but 0 imports. |
| DQ-3.1 Quality-weighted confidence | **UNWIRED** | `lib/intelligence/quality_confidence.py` (214 lines) exists but 0 imports. |
| DQ-4.1 Quality dashboard | **PARTIAL** | `time-os-ui/src/pages/DataQuality.tsx` exists but only 72 lines (likely a stub). |
| DQ-5.1 Quality validation | NOT VERIFIED | |

**Action items:**
1. Wire `data_freshness.py`, `completeness_scorer.py`, `quality_confidence.py` into the intelligence phase or API
2. Flesh out `DataQuality.tsx` from 72-line stub to real dashboard
3. Verify DQ-5.1

---

## IE — Intelligence Engine

| Task | Status | Detail |
|------|--------|--------|
| IE-1.1 Cost-to-serve | **DONE** | `lib/intelligence/cost_to_serve.py` (568 lines), 3 imports, wired in `_intelligence_phase()`. |
| IE-2.1 Pattern recognition | **DONE** | `lib/intelligence/patterns.py` (1700 lines), 12 imports, wired in `_intelligence_phase()`. |
| IE-3.1 Scenario modeling | **PARTIAL** | `lib/intelligence/scenario_engine.py` (1188 lines), only 1 import (from intelligence index). Not wired into loop or API routes. |
| IE-4.1 Trajectory computation | **PARTIAL** | `lib/intelligence/trajectory.py` (713 lines), only 1 import (intelligence index). Not in loop. |
| IE-5.1 V4/V5 consolidation | Needs verification | |
| IE-6.1 Resolution queue automation | **DONE** | `lib/intelligence/auto_resolution.py` (974 lines), `ResolutionQueue` wired in loop. |
| IE-7.1 Intelligence validation | Needs verification | |

**Action items:**
1. Wire `scenario_engine.py` into API or autonomous loop
2. Wire `trajectory.py` into autonomous loop (currently only indexed)
3. Verify IE-5.1, IE-7.1

---

## ID — Intelligence Deepening

| Task | Status | Detail |
|------|--------|--------|
| ID-1.1 Correlation confidence | **PARTIAL** | `lib/intelligence/correlation_confidence.py` (220 lines), 1 import. Exists but minimally wired. |
| ID-2.1 Cost proxies | **UNWIRED** | `lib/intelligence/cost_proxies.py` (199 lines), 0 imports. |
| ID-3.1 Entity profiles | **UNWIRED** | `lib/intelligence/entity_profile.py` (436 lines), 0 imports. |
| ID-4.1 Outcome tracking | **UNWIRED** | `lib/intelligence/outcome_tracker.py` (393 lines), 0 imports. |
| ID-5.1 Pattern trending | **UNWIRED** | `lib/intelligence/pattern_trending.py` (327 lines), 0 imports. |
| ID-6.1 Synthesis validation | Needs verification | |

**Action items:**
1. Wire all 4 UNWIRED modules into intelligence pipeline or API
2. Verify ID-6.1

---

## IO — Intelligence Observability

| Task | Status | Detail |
|------|--------|--------|
| IO-1.1 Computation audit trail | **UNWIRED** | `lib/intelligence/audit_trail.py` exists but 0 imports outside itself. |
| IO-2.1 Explainability engine | **UNWIRED** | `lib/intelligence/explainability.py` exists but 0 imports. |
| IO-3.1 Drift detection | **UNWIRED** | `lib/intelligence/drift_detection.py` exists but 0 imports. |
| IO-4.1 Debug mode | Needs verification | |
| IO-5.1 Observability validation | Needs verification | |

**Note:** The `lib/observability/` directory IS wired (metrics, tracing, health used by server.py). But the intelligence-specific observability modules in `lib/intelligence/` are not.

**Action items:**
1. Wire `audit_trail.py`, `explainability.py`, `drift_detection.py` into intelligence phase
2. Verify IO-4.1, IO-5.1

---

## IW — Intelligence Wiring

| Task | Status | Detail |
|------|--------|--------|
| IW-1.1 Persistence | **DONE** | `lib/intelligence/persistence.py` (752 lines), imported in `_intelligence_phase()`. |
| IW-2.1 Health unification | **DONE** | `lib/intelligence/health_unifier.py`, imported in `_intelligence_phase()`. |
| IW-3.1 Daemon wiring | **DONE** | `lib/daemon.py` (688 lines), `autonomous_loop.py` runs full pipeline. |
| IW-4.1 Event hooks | Needs verification | |
| IW-5.1 Integration validation | Needs verification | |

**Action items:**
1. Verify IW-4.1, IW-5.1

---

## IA — Intelligence API

| Task | Status | Detail |
|------|--------|--------|
| IA-1.1 Intelligence router | **DONE** | `api/intelligence_router.py` exists, mounted at `/api/v2/intelligence`. |
| IA-2.1 Entity intelligence endpoints | **DONE** | Client profile, entity endpoints in intelligence_router. |
| IA-3.1 Portfolio endpoints | **DONE** | `/portfolio/overview`, `/portfolio/risks`, `/portfolio/trajectory` routes. |
| IA-4.1 Signal/pattern endpoints | Needs verification | Check if signal and pattern routes exist in router. |
| IA-5.1 Scenario/trajectory endpoints | Needs verification | |
| IA-6.1 API contract tests | Needs verification | |

**Action items:**
1. Verify IA-4.1, IA-5.1, IA-6.1

---

## SM — System Memory

| Task | Status | Detail |
|------|--------|--------|
| SM-1.1 Decision journal | **UNWIRED** | `lib/intelligence/decision_journal.py` (294 lines), 0 imports. |
| SM-2.1 Entity memory | **UNWIRED** | `lib/intelligence/entity_memory.py` (397 lines), 0 imports. |
| SM-3.1 Signal lifecycle | **UNWIRED** | `lib/intelligence/signal_lifecycle.py` (524 lines), 0 imports from outside intelligence/. |
| SM-4.1 Behavioral patterns | **UNWIRED** | `lib/intelligence/behavioral_patterns.py` (522 lines), 0 imports. |

**Action items:**
1. Wire all 4 modules into intelligence pipeline or autonomous loop

---

## AT — Adaptive Thresholds

| Task | Status | Detail |
|------|--------|--------|
| AT-1.1 Effectiveness scorer | **PARTIAL** | `lib/calibration.py` (196 lines) exists and is imported in `server.py`. But only basic calibration — the task specs describe a much more elaborate effectiveness scoring system. |
| AT-2.1 Threshold adjustment engine | NOT VERIFIED | No separate threshold_adjustment module found. May be in calibration.py. |
| AT-3.1 Seasonal/contextual modifiers | NOT VERIFIED | |
| AT-4.1 Calibration reporting | NOT VERIFIED | |
| AT-5.1 Adaptive threshold validation | NOT VERIFIED | |

**Action items:**
1. Read AT task specs in detail and verify against calibration.py capabilities
2. May need significant new code for threshold adjustment, seasonal modifiers

---

## TC — Temporal Context

| Task | Status | Detail |
|------|--------|--------|
| TC-1.1 Business calendar engine | **PARTIAL** | `lib/intelligence/temporal.py` (710 lines) exists with 1 import. Large module but minimally wired. |
| TC-2.1 Temporal normalization | Part of temporal.py | |
| TC-3.1 Recency-weighted normalization | Part of temporal.py | |
| TC-4.1 Signal age persistence | Part of signal_lifecycle.py (UNWIRED) | |
| TC-5.1 Temporal intelligence validation | NOT VERIFIED | |

**Action items:**
1. Wire `temporal.py` more deeply into intelligence pipeline
2. Wire `signal_lifecycle.py`

---

## NI — Notifications

| Task | Status | Detail |
|------|--------|--------|
| NI-1.1 Notification routing | **DONE** | `lib/notifier/engine.py` (421 lines), routes by channel and priority. |
| NI-2.1 Digest engine | **UNWIRED** | `lib/notifier/digest.py` (400 lines) exists but 0 imports from outside notifier/. |
| NI-3.1 Email digest | NOT VERIFIED | No email channel in notifier/channels/. |
| NI-4.1 History/muting | NOT VERIFIED | |
| NI-5.1 Analytics validation | NOT VERIFIED | |

**Action items:**
1. Wire `digest.py` into notification pipeline
2. Create email notification channel if needed
3. Verify NI-3.1, NI-4.1, NI-5.1

---

## BI — Bidirectional Integration

| Task | Status | Detail |
|------|--------|--------|
| BI-1.1 Action framework | **DONE** | `lib/actions/action_framework.py` (506 lines), imported in chat_commands.py, chat_webhook_router.py. |
| BI-2.1 Asana writeback | Needs verification | Check if Asana write operations exist in action framework. |
| BI-3.1 Gmail/Calendar automation | Needs verification | |
| BI-4.1 Chat interactive | **DONE** | `lib/integrations/chat_commands.py` wires actions, `api/chat_webhook_router.py` handles webhooks. |
| BI-5.1 Action validation | Needs verification | |

**Action items:**
1. Verify BI-2.1, BI-3.1, BI-5.1

---

## CI — Conversational Interface

| Task | Status | Detail |
|------|--------|--------|
| CI-1.1 Query engine | **DONE** | `lib/query_engine.py` (1400 lines), imported by intelligence modules. |
| CI-2.1 Cross-domain synthesis | **PARTIAL** | `lib/intelligence/conversational_intelligence.py` (971 lines) exists but needs wiring verification. |
| CI-3.1 Action routing context | **PARTIAL** | `lib/routing_engine.py` (291 lines) exists but 0 imports from outside. **UNWIRED.** |
| CI-4.1 Conversational UI validation | NOT VERIFIED | |

**Action items:**
1. Wire `routing_engine.py` into API or chat webhook handler
2. Verify CI-2.1 wiring, CI-4.1

---

## PI — Proactive Intelligence

| Task | Status | Detail |
|------|--------|--------|
| PI-1.1 Preparation engine | **PARTIAL** | `lib/intelligence/proposals.py` (1123 lines) handles proposals. No dedicated preparation_engine module. |
| PI-2.1 Asana intelligence | Part of intelligence pipeline | |
| PI-3.1 Email communication drafting | NOT VERIFIED | |
| PI-4.1 Daily intelligence briefing | **DONE** | Phase 15e morning brief covers this. |
| PI-5.1 Contextual surfaces validation | NOT VERIFIED | |

**Action items:**
1. Verify PI-1.1, PI-2.1, PI-3.1, PI-5.1

---

## PS — Performance/Scaling

| Task | Status | Detail |
|------|--------|--------|
| PS-1.1 Fix N+1 queries | Needs verification | `lib/db_opt/query_optimizer.py` (244 lines) exists, 1 import. |
| PS-2.1 Cache layer | **DONE** | `lib/cache/cache_manager.py` (218 lines), `decorators.py` (214 lines). Used by intelligence_router cache decorators. |
| PS-3.1 PostgreSQL compat | **DONE** | `lib/db_opt/sql_compat.py` (295 lines), 1 import. |
| PS-4.1 Pagination/async | **DONE** | `lib/api/pagination.py` exists, `lib/api/background_tasks.py` exists. |
| PS-5.1 Load testing | NOT VERIFIED | |

**Action items:**
1. Verify PS-1.1 N+1 fix effectiveness, PS-5.1

---

## SH — Security Hardening

| Task | Status | Detail |
|------|--------|--------|
| SH-1.1 API key management | **DONE** | `lib/security/key_manager.py` (449 lines), 1 import. |
| SH-2.1 Role-based scoping | **DONE** | `lib/security/rbac.py` (299 lines), 1 import. |
| SH-3.1 Rate limit/CORS | **DONE** | `lib/security/rate_limiter.py` (180 lines), wired in server.py. `lib/security/headers.py` (175 lines) with CORS. |
| SH-4.1 Credential audit | Needs verification | |
| SH-5.1 Security validation | Needs verification | |

**Action items:**
1. Verify SH-4.1, SH-5.1
2. `lib/security/secrets_config.py` has 0 imports — check if needed

---

## DG — Data Governance

| Task | Status | Detail |
|------|--------|--------|
| DG-1.1 Data classification | **DONE** | `lib/governance/data_classification.py` (466 lines), 2 imports. |
| DG-2.1 Data export API | **DONE** | `lib/governance/data_export.py` (383 lines), 2 imports. |
| DG-3.1 Subject access/deletion | **DONE** | `lib/governance/subject_access.py` (739 lines), 2 imports. |
| DG-4.1 Retention enforcement | **DONE** | `lib/governance/retention_engine.py` (583 lines) + `retention_scheduler.py` (348 lines), both wired. |
| DG-5.1 Compliance reporting | Needs verification | May be covered by `audit_log.py` (231 lines). |

**Action items:**
1. Verify DG-5.1

---

## IX — Intelligence UX

| Task | Status | Detail |
|------|--------|--------|
| IX-1.1 Design system | **DONE** | 21 pages exist in `time-os-ui/src/pages/`. Substantial pages (Portfolio 500 lines, Inbox 829 lines, etc.) |
| IX-2.1 Live dashboard | **DONE** | CommandCenter.tsx (489 lines, just rewritten in Phase 15d). |
| IX-3.1 Resolution queue UI | **PARTIAL** | No dedicated ResolutionQueue page. May be in CommandCenter or Priorities. |
| IX-4.1 Scenario modeling UI | NOT VERIFIED | No dedicated scenario page found. |
| IX-5.1 Realtime updates | NOT VERIFIED | |
| IX-6.1 UI validation | NOT VERIFIED | |

**Possible stubs (under 100 lines):**
- `DataQuality.tsx` (72 lines)
- `Notifications.tsx` (82 lines)
- `Approvals.tsx` (92 lines)

**Action items:**
1. Flesh out DataQuality, Notifications, Approvals pages
2. Verify IX-3.1, IX-4.1, IX-5.1, IX-6.1

---

## VR — View Reconciliation

| Task | Status | Detail |
|------|--------|--------|
| VR-1.1 Functionality audit | NOT VERIFIED | |
| VR-2.1 Migrate unique | NOT VERIFIED | |
| VR-3.1 Consumer cleanup | NOT VERIFIED | |
| VR-4.1 Archive/delete | NOT VERIFIED | |
| VR-5.1 Reconciliation validation | NOT VERIFIED | |

**Action items:**
1. Read VR task specs and verify all 5

---

## CRITICAL FINDINGS SUMMARY

### NOT DONE (code doesn't exist or fix not applied):
1. **PH-1.1**: `lane_assigner.py:190` — `t.lane` should be `t.lane_id`
2. **TR-1.1**: 29 files still use `from datetime import UTC` (Python 3.10 incompatible)
3. **TR-1.2**: 15 files still use `from enum import StrEnum` (Python 3.10 incompatible)

### UNWIRED (code exists, 200-500+ lines each, but zero imports — dead code):
4. `lib/intelligence/cost_proxies.py` (199 lines)
5. `lib/intelligence/entity_profile.py` (436 lines)
6. `lib/intelligence/outcome_tracker.py` (393 lines)
7. `lib/intelligence/pattern_trending.py` (327 lines)
8. `lib/intelligence/behavioral_patterns.py` (522 lines)
9. `lib/intelligence/decision_journal.py` (294 lines)
10. `lib/intelligence/entity_memory.py` (397 lines)
11. `lib/intelligence/signal_lifecycle.py` (524 lines)
12. `lib/intelligence/data_freshness.py` (330 lines)
13. `lib/intelligence/completeness_scorer.py` (271 lines)
14. `lib/intelligence/quality_confidence.py` (214 lines)
15. `lib/intelligence/audit_trail.py` (exists, 0 imports)
16. `lib/intelligence/explainability.py` (exists, 0 imports)
17. `lib/intelligence/drift_detection.py` (exists, 0 imports)
18. `lib/intelligence/data_governance.py` (674 lines, 0 imports from loop/API)
19. `lib/intelligence/notification_intelligence.py` (exists, 0 imports)
20. `lib/intelligence/predictive_intelligence.py` (exists, 0 imports)
21. `lib/intelligence/attention_tracking.py` (exists, 0 imports)
22. `lib/intelligence/signal_suppression.py` (exists, 0 imports)
23. `lib/notifier/digest.py` (400 lines, 0 imports)
24. `lib/routing_engine.py` (291 lines, 0 imports)

### PARTIAL (hardcoded value, stub UI):
25. **PH-4.2**: `lib/collectors/chat.py:31` hardcoded email
26. **IX**: `DataQuality.tsx` (72 lines), `Notifications.tsx` (82 lines), `Approvals.tsx` (92 lines) likely stubs

### NEEDS VERIFICATION (couldn't confirm complete):
27. PH-3.1, PH-3.2, PH-5.1
28. TR-4.1 (full test suite)
29. DF-2.1, DF-4.1
30. UR-1.1, UR-1.2, UR-6.1, UR-6.2
31. CS-6.1
32. AO-5.1, AO-6.1
33. AT-2.1 through AT-5.1 (threshold adjustment detail)
34. TC-5.1
35. NI-3.1 through NI-5.1
36. BI-2.1, BI-3.1, BI-5.1
37. CI-2.1, CI-4.1
38. PI-1.1, PI-2.1, PI-3.1, PI-5.1
39. PS-1.1, PS-5.1
40. SH-4.1, SH-5.1
41. DG-5.1
42. IX-3.1 through IX-6.1
43. VR-1.1 through VR-5.1
