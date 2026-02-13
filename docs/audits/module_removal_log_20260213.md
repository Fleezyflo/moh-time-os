# Module Removal Log — 2026-02-13

## Summary
- Attempted: 125
- Removed: 34
- Skipped: 91
- Lines of code removed: 3,798
- Test suite: 282 passing after all removals

---

## Removed
| Path | Lines | Purpose | Tests After |
|------|-------|---------|-------------|
| `collectors/_legacy/__init__.py` | 16 | DEPRECATED: Legacy collectors — DO NOT I | ✅ 297 |
| `engine/action_queue.py` | 147 | (no description) | ✅ 297 |
| `engine/render_html.py` | 410 | Render a local operator console.  Design | ✅ 297 |
| `engine/tasks_board.py` | 627 | (no description) | ✅ 297 |
| `lib/agency_snapshot/__init__.py` | 32 | Agency Snapshot Generator - Produces age | ✅ 297 |
| `lib/client_truth/__init__.py` | 24 | Client Truth Module (Tier 3) | ✅ 297 |
| `lib/db_writer.py` | 132 | Single DB Write Module - All writes go t | ✅ 297 |
| `lib/executor/handlers/__init__.py` | 20 | Executor Handlers - Action handlers for  | ✅ 297 |
| `lib/integrations/__init__.py` | 5 | MOH Time OS — External Integrations | ✅ 297 |
| `lib/integrations/calendar_integration.py` | 197 | MOH Time OS — Calendar Integration | ✅ 297 |
| `lib/integrations/email_integration.py` | 234 | MOH Time OS — Email Integration | ✅ 297 |
| `lib/integrations/tasks_integration.py` | 339 | MOH Time OS — Google Tasks Integration | ✅ 297 |
| `lib/migrations/__init__.py` | 0 | (no description) | ✅ 297 |
| `lib/normalize/__init__.py` | 49 | Normalize Module — Canonical Data Repres | ✅ 297 |
| `lib/normalize/domain_models.py` | 305 | Domain Models — Canonical Types for Norm | ✅ 297 |
| `lib/normalize/extractors/__init__.py` | 19 | Extractors — Per-domain raw data extract | ✅ 297 |
| `lib/normalize/resolvers.py` | 355 | Resolvers Module — Exhaustive Semantic R | ✅ 297 |
| `lib/notifier/channels/__init__.py` | 10 | MOH TIME OS - Notification Channels | ✅ 297 |
| `lib/reasoner/__init__.py` | 9 | Reasoner - Decision engine. Makes decisi | ✅ 282 |
| `lib/ui_spec_v21/tests/__init__.py` | 5 | Test Suite — Time OS UI Spec v2.1 | ✅ 282 |
| `lib/ui_spec_v21/tests/test_evidence_contracts.py` | 418 | Evidence Renderer Contract Tests — Spec  | ✅ 282 |
| `lib/v4/detectors/__init__.py` | 20 | Time OS V4 - Detectors | ✅ 282 |
| `lib/v5/__init__.py` | 98 | Time OS V5 — Signal-Based Client Health  | ✅ 282 |
| `lib/v5/api/__init__.py` | 7 | Time OS V5 — API Package | ✅ 282 |
| `lib/v5/api/routes/__init__.py` | 7 | Time OS V5 — API Routes | ✅ 282 |
| `lib/v5/detectors/__init__.py` | 23 | Time OS V5 — Detectors Package | ✅ 282 |
| `lib/v5/integrations/__init__.py` | 1 | Time OS V5 — integrations module. | ✅ 282 |
| `lib/v5/issues/__init__.py` | 37 | Time OS V5 — Issues Package | ✅ 282 |
| `lib/v5/jobs/__init__.py` | 1 | Time OS V5 — jobs module. | ✅ 282 |
| `lib/v5/migrations/__init__.py` | 1 | Time OS V5 — migrations module. | ✅ 282 |
| `lib/v5/models/__init__.py` | 192 | Time OS V5 — Models Package | ✅ 282 |
| `lib/v5/repositories/__init__.py` | 11 | Time OS V5 — Repositories Package | ✅ 282 |
| `lib/v5/resolution/__init__.py` | 33 | Time OS V5 — Resolution Package | ✅ 282 |
| `lib/v5/services/__init__.py` | 14 | Time OS V5 — Services Package | ✅ 282 |

---

## Skipped (could not safely remove)
| Path | Lines | Reason |
|------|-------|--------|
| `collectors/_legacy/team_calendar.py` | 303 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `engine/calibration.py` | 110 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `engine/chat_discovery.py` | 332 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `engine/discovery.py` | 472 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `engine/rules_store.py` | 46 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `engine/store.py` | 55 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `engine/tasks_discovery.py` | 284 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/agency_snapshot/client360.py` | 2203 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/agency_snapshot/confidence.py` | 266 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/agency_snapshot/delivery.py` | 782 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/agency_snapshot/deltas.py` | 290 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/agency_snapshot/generator.py` | 1702 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/agency_snapshot/scoring.py` | 312 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/analyzers/anomaly.py` | 443 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/analyzers/orchestrator.py` | 300 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/analyzers/patterns.py` | 376 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/analyzers/priority.py` | 373 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/analyzers/time.py` | 304 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/backup.py` | 190 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/capture.py` | 335 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/collector_registry.py` | 158 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/collectors/asana.py` | 113 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/collectors/base.py` | 159 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/collectors/gmail.py` | 302 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/collectors/tasks.py` | 135 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/executor/engine.py` | 232 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/executor/handlers.py` | 255 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/executor/handlers/calendar.py` | 78 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/executor/handlers/delegation.py` | 286 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/executor/handlers/email.py` | 63 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/executor/handlers/notification.py` | 155 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/executor/handlers/task.py` | 209 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/health.py` | 262 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/integrations/clawdbot_api.py` | 138 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/notifier/channels/clawdbot.py` | 193 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/observability/context.py` | 54 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/observability/health.py` | 166 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/observability/log_schema.py` | 134 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/observability/logging.py` | 108 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/observability/metrics.py` | 225 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/priority.py` | 154 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/protocol.py` | 310 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/queries.py` | 273 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/reasoner/decisions.py` | 300 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/reasoner/engine.py` | 74 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/resolve.py` | 409 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/safety/context.py` | 165 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/safety/json_parse.py` | 138 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/safety/utils.py` | 56 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/ui_spec_v21/engagement_lifecycle.py` | 485 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/ui_spec_v21/org_settings.py` | 245 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/artifact_service.py` | 542 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/collector_hooks.py` | 1384 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/detectors/anomaly_detector.py` | 277 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/detectors/base.py` | 158 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/detectors/commitment_detector.py` | 319 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/detectors/deadline_detector.py` | 398 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/detectors/health_detector.py` | 297 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/entity_link_service.py` | 627 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/identity_service.py` | 609 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/policy_service.py` | 683 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/report_service.py` | 483 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v4/signal_service.py` | 989 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/api/main.py` | 74 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/api/routes/health.py` | 387 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/api/routes/issues.py` | 380 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/api/routes/signals.py` | 388 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/data_loader.py` | 291 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/database.py` | 400 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/detectors/asana_task_detector.py` | 146 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/detectors/base.py` | 481 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/detectors/calendar_meet_detector.py` | 122 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/detectors/gchat_detector.py` | 223 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/detectors/gmail_detector.py` | 291 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/detectors/registry.py` | 260 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/detectors/xero_financial_detector.py` | 112 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/issues/formation_service.py` | 405 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/issues/patterns.py` | 271 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/models/base.py` | 259 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/models/calendar.py` | 510 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/models/entities.py` | 507 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/models/gchat.py` | 273 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/models/issue.py` | 484 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/models/signal.py` | 517 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/models/xero.py` | 251 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/repositories/signal_repository.py` | 567 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/resolution/balance_rules.py` | 229 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/resolution/balance_service.py` | 513 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/resolution/resolution_service.py` | 412 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/services/detection_orchestrator.py` | 336 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |
| `lib/v5/services/signal_service.py` | 439 | Referenced by: /Users/molhamhomsi/clawd/moh_time_o |