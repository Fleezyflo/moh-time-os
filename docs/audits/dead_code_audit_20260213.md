# Dead Code Audit — 2026-02-13

## Summary
- Total modules scanned: 277
- ACTIVE: 9
- TEST-ONLY: 4
- ORPHANED: 125
- ENTRY-POINT: 108
- UNCERTAIN: 31

---

## ACTIVE Modules
| Module | Path | Imported By (production) |
|--------|------|-------------------------|
| engine.__init__ | `engine/__init__.py` | collectors/_legacy/asana_sync.py, collectors/xero_ops.py, engine/financial_pulse.py |
| engine.gogcli | `engine/gogcli.py` | engine/knowledge_base.py |
| lib.__init__ | `lib/__init__.py` | api/spec_router.py, collectors/_legacy/asana_sync.py, collectors/chat_direct.py |
| lib.state_store | `lib/state_store.py` | lib/collectors/xero.py |
| lib.ui_spec_v21.__init__ | `lib/ui_spec_v21/__init__.py` | api/spec_router.py, lib/ui_spec_v21/tests/test_evidence_contracts.py, lib/ui_spec_v21/tests/test_integration.py |
| lib.ui_spec_v21.endpoints | `lib/ui_spec_v21/endpoints.py` | api/spec_router.py, lib/ui_spec_v21/tests/test_spec_cases.py |
| lib.ui_spec_v21.inbox_lifecycle | `lib/ui_spec_v21/inbox_lifecycle.py` | api/spec_router.py, lib/ui_spec_v21/tests/test_integration.py, lib/ui_spec_v21/tests/test_spec_cases.py |
| lib.ui_spec_v21.issue_lifecycle | `lib/ui_spec_v21/issue_lifecycle.py` | api/spec_router.py, lib/ui_spec_v21/tests/test_integration.py, lib/ui_spec_v21/tests/test_spec_cases.py |
| lib.ui_spec_v21.suppression | `lib/ui_spec_v21/suppression.py` | lib/ui_spec_v21/tests/test_spec_cases.py |

---

## TEST-ONLY Modules
| Module | Path | Imported By (tests) |
|--------|------|---------------------|
| lib.collectors.recorder | `lib/collectors/recorder.py` | tests/cassettes/test_collector_replay.py |
| lib.contracts.invariants | `lib/contracts/invariants.py` | tests/contract/test_invariants.py |
| lib.paths | `lib/paths.py` | tests/test_api_contracts.py |
| lib.safety.audit | `lib/safety/audit.py` | tests/test_safety.py |

---

## ORPHANED Modules (candidates for removal)
| Module | Path | Lines | Description |
|--------|------|-------|-------------|
| collectors._legacy.__init__ | `collectors/_legacy/__init__.py` | 16 | DEPRECATED: Legacy collectors — DO NOT IMPORT |
| collectors._legacy.team_calendar | `collectors/_legacy/team_calendar.py` | 303 | Team Calendar Collector - Pulls calendars from ALL team members. Uses domain-wid |
| engine.action_queue | `engine/action_queue.py` | 147 | (no description) |
| engine.calibration | `engine/calibration.py` | 110 | (no description) |
| engine.chat_discovery | `engine/chat_discovery.py` | 332 | (no description) |
| engine.discovery | `engine/discovery.py` | 472 | (no description) |
| engine.render_html | `engine/render_html.py` | 410 | Render a local operator console.  Design targets (v0.3): |
| engine.rules_store | `engine/rules_store.py` | 46 | (no description) |
| engine.store | `engine/store.py` | 55 | (no description) |
| engine.tasks_board | `engine/tasks_board.py` | 627 | (no description) |
| engine.tasks_discovery | `engine/tasks_discovery.py` | 284 | (no description) |
| lib.agency_snapshot.__init__ | `lib/agency_snapshot/__init__.py` | 32 | Agency Snapshot Generator - Produces agency_snapshot.json per Page 0/1/2/3/4 spe |
| lib.agency_snapshot.client360 | `lib/agency_snapshot/client360.py` | 2203 | Client 360 Engine - Per Page 2 LOCKED SPEC (v1) |
| lib.agency_snapshot.confidence | `lib/agency_snapshot/confidence.py` | 266 | Confidence Model - Per Page 0 §3.3. |
| lib.agency_snapshot.delivery | `lib/agency_snapshot/delivery.py` | 782 | Delivery Engine - Slip Risk, Project Status, Critical Chain. |
| lib.agency_snapshot.deltas | `lib/agency_snapshot/deltas.py` | 290 | Delta Detection - Track changes between snapshots. |
| lib.agency_snapshot.generator | `lib/agency_snapshot/generator.py` | 1702 | Agency Snapshot Generator - Produces agency_snapshot.json per Page 0/1/2/3/4 spe |
| lib.agency_snapshot.scoring | `lib/agency_snapshot/scoring.py` | 312 | Scoring Engine - BaseScore, ModeWeights, Eligibility Gates. |
| lib.analyzers.anomaly | `lib/analyzers/anomaly.py` | 443 | Anomaly Detector - Detects unusual patterns and potential issues. |
| lib.analyzers.orchestrator | `lib/analyzers/orchestrator.py` | 300 | Analyzer Orchestrator - Coordinates all analysis modules. |
| lib.analyzers.patterns | `lib/analyzers/patterns.py` | 376 | Pattern Analyzer - Detects recurring patterns in work, communications, and sched |
| lib.analyzers.priority | `lib/analyzers/priority.py` | 373 | Priority Analyzer - Computes unified priority queue across all items. THIS IS TH |
| lib.analyzers.time | `lib/analyzers/time.py` | 304 | Time Analyzer - Analyzes time allocation, capacity, and scheduling patterns. |
| lib.backup | `lib/backup.py` | 190 | Backup and restore functionality for MOH Time OS. |
| lib.capture | `lib/capture.py` | 335 | High-level capture functions for conversation-based item creation.  This is the  |
| lib.client_truth.__init__ | `lib/client_truth/__init__.py` | 24 | Client Truth Module (Tier 3) |
| lib.collector_registry | `lib/collector_registry.py` | 158 | Collector Registry — Single Source of Truth |
| lib.collectors.asana | `lib/collectors/asana.py` | 113 | Asana Collector - Pulls tasks from Asana via real API client. |
| lib.collectors.base | `lib/collectors/base.py` | 159 | Base Collector - Template for all data collectors. Every collector MUST: |
| lib.collectors.gmail | `lib/collectors/gmail.py` | 302 | Gmail Collector - Pulls emails from Gmail via Service Account API. Uses direct G |
| lib.collectors.tasks | `lib/collectors/tasks.py` | 135 | Tasks Collector - Pulls tasks from Google Tasks via gog CLI. REPLACES the broken |
| lib.db_writer | `lib/db_writer.py` | 132 | Single DB Write Module - All writes go through here. |
| lib.executor.engine | `lib/executor/engine.py` | 232 | Executor Engine - Processes and executes approved actions. |
| lib.executor.handlers | `lib/executor/handlers.py` | 255 | Action Handlers - Execute specific action types against external systems. |
| lib.executor.handlers.__init__ | `lib/executor/handlers/__init__.py` | 20 | Executor Handlers - Action handlers for different domains. |
| lib.executor.handlers.calendar | `lib/executor/handlers/calendar.py` | 78 | Calendar Handler - Executes calendar-related actions. |
| lib.executor.handlers.delegation | `lib/executor/handlers/delegation.py` | 286 | Delegation Handler - Executes delegation actions. |
| lib.executor.handlers.email | `lib/executor/handlers/email.py` | 63 | Email Handler - Executes email-related actions. |
| lib.executor.handlers.notification | `lib/executor/handlers/notification.py` | 155 | Notification Handler - Executes notification actions. |
| lib.executor.handlers.task | `lib/executor/handlers/task.py` | 209 | Task Handler - Executes task-related actions. |
| lib.health | `lib/health.py` | 262 | Health checks and self-healing for MOH Time OS. |
| lib.integrations.__init__ | `lib/integrations/__init__.py` | 5 | MOH Time OS — External Integrations |
| lib.integrations.calendar_integration | `lib/integrations/calendar_integration.py` | 197 | MOH Time OS — Calendar Integration |
| lib.integrations.clawdbot_api | `lib/integrations/clawdbot_api.py` | 138 | ClawdbotAPI - Full Clawdbot Gateway integration. |
| lib.integrations.email_integration | `lib/integrations/email_integration.py` | 234 | MOH Time OS — Email Integration |
| lib.integrations.tasks_integration | `lib/integrations/tasks_integration.py` | 339 | MOH Time OS — Google Tasks Integration |
| lib.migrations.__init__ | `lib/migrations/__init__.py` | 0 | (no description) |
| lib.normalize.__init__ | `lib/normalize/__init__.py` | 49 | Normalize Module — Canonical Data Representation and Resolution. |
| lib.normalize.domain_models | `lib/normalize/domain_models.py` | 305 | Domain Models — Canonical Types for Normalized Data. |
| lib.normalize.extractors.__init__ | `lib/normalize/extractors/__init__.py` | 19 | Extractors — Per-domain raw data extraction. |
| lib.normalize.resolvers | `lib/normalize/resolvers.py` | 355 | Resolvers Module — Exhaustive Semantic Resolution Rules. |
| lib.notifier.channels.__init__ | `lib/notifier/channels/__init__.py` | 10 | MOH TIME OS - Notification Channels |
| lib.notifier.channels.clawdbot | `lib/notifier/channels/clawdbot.py` | 193 | ClawdbotChannel - Send notifications via Clawdbot tools/invoke API. CRITICAL: Di |
| lib.observability.context | `lib/observability/context.py` | 54 | Request context management with thread-local storage. |
| lib.observability.health | `lib/observability/health.py` | 166 | Health check system with component-level checks. |
| lib.observability.log_schema | `lib/observability/log_schema.py` | 134 | Log schema enforcement. |
| lib.observability.logging | `lib/observability/logging.py` | 108 | Structured JSON logging with request ID propagation. |
| lib.observability.metrics | `lib/observability/metrics.py` | 225 | Minimal metrics collection for observability. |
| lib.priority | `lib/priority.py` | 154 | Priority scoring for items. |
| lib.protocol | `lib/protocol.py` | 310 | A Protocol — How I (A) use MOH Time OS.  This module provides the high-level fun |
| lib.queries | `lib/queries.py` | 273 | Query helpers for common access patterns. |
| lib.reasoner.__init__ | `lib/reasoner/__init__.py` | 9 | Reasoner - Decision engine. Makes decisions based on analysis and governance rul |
| lib.reasoner.decisions | `lib/reasoner/decisions.py` | 300 | Decision Maker - Creates decisions based on insights and anomalies. |
| lib.reasoner.engine | `lib/reasoner/engine.py` | 74 | Reasoner Engine - Main orchestrator for decision-making. |
| lib.resolve | `lib/resolve.py` | 409 | Entity resolution for conversation-based capture.  Resolves natural language ref |
| lib.safety.context | `lib/safety/context.py` | 165 | Write Context Management |
| lib.safety.json_parse | `lib/safety/json_parse.py` | 138 | Safe JSON parsing with trust tracking. |
| lib.safety.utils | `lib/safety/utils.py` | 56 | Utility functions for safety module. |
| lib.ui_spec_v21.engagement_lifecycle | `lib/ui_spec_v21/engagement_lifecycle.py` | 485 | Engagement Lifecycle — Spec Section 6.7 |
| lib.ui_spec_v21.org_settings | `lib/ui_spec_v21/org_settings.py` | 245 | Org Settings — Spec Section 0.1 |
| lib.ui_spec_v21.tests.__init__ | `lib/ui_spec_v21/tests/__init__.py` | 5 | Test Suite — Time OS UI Spec v2.1 |
| lib.ui_spec_v21.tests.test_evidence_contracts | `lib/ui_spec_v21/tests/test_evidence_contracts.py` | 418 | Evidence Renderer Contract Tests — Spec Section 6.16 |
| lib.v4.artifact_service | `lib/v4/artifact_service.py` | 542 | Time OS V4 - Artifact Service |
| lib.v4.collector_hooks | `lib/v4/collector_hooks.py` | 1384 | Time OS V4 - Collector Hooks |
| lib.v4.detectors.__init__ | `lib/v4/detectors/__init__.py` | 20 | Time OS V4 - Detectors |
| lib.v4.detectors.anomaly_detector | `lib/v4/detectors/anomaly_detector.py` | 277 | Time OS V4 - Anomaly Detector |
| lib.v4.detectors.base | `lib/v4/detectors/base.py` | 158 | Time OS V4 - Base Detector |
| lib.v4.detectors.commitment_detector | `lib/v4/detectors/commitment_detector.py` | 319 | Time OS V4 - Commitment Detector |
| lib.v4.detectors.deadline_detector | `lib/v4/detectors/deadline_detector.py` | 398 | Time OS V4 - Deadline Detector |
| lib.v4.detectors.health_detector | `lib/v4/detectors/health_detector.py` | 297 | Time OS V4 - Health Detector |
| lib.v4.entity_link_service | `lib/v4/entity_link_service.py` | 627 | Time OS V4 - Entity Link Service |
| lib.v4.identity_service | `lib/v4/identity_service.py` | 609 | Time OS V4 - Identity Service |
| lib.v4.policy_service | `lib/v4/policy_service.py` | 683 | Time OS V4 - Policy Service |
| lib.v4.report_service | `lib/v4/report_service.py` | 483 | Time OS V4 - Report Service |
| lib.v4.signal_service | `lib/v4/signal_service.py` | 989 | Time OS V4 - Signal Service |
| lib.v5.__init__ | `lib/v5/__init__.py` | 98 | Time OS V5 — Signal-Based Client Health Monitoring |
| lib.v5.api.__init__ | `lib/v5/api/__init__.py` | 7 | Time OS V5 — API Package |
| lib.v5.api.main | `lib/v5/api/main.py` | 74 | Time OS V5 — API Main |
| lib.v5.api.routes.__init__ | `lib/v5/api/routes/__init__.py` | 7 | Time OS V5 — API Routes |
| lib.v5.api.routes.health | `lib/v5/api/routes/health.py` | 387 | Time OS V5 — Health Dashboard API |
| lib.v5.api.routes.issues | `lib/v5/api/routes/issues.py` | 380 | Time OS V5 — Issues API |
| lib.v5.api.routes.signals | `lib/v5/api/routes/signals.py` | 388 | Time OS V5 — Signals API |
| lib.v5.data_loader | `lib/v5/data_loader.py` | 291 | Time OS V5 — Data Loader |
| lib.v5.database | `lib/v5/database.py` | 400 | Time OS V5 — Database Module |
| lib.v5.detectors.__init__ | `lib/v5/detectors/__init__.py` | 23 | Time OS V5 — Detectors Package |
| lib.v5.detectors.asana_task_detector | `lib/v5/detectors/asana_task_detector.py` | 146 | Time OS V5 — Asana Task Detector |
| lib.v5.detectors.base | `lib/v5/detectors/base.py` | 481 | Time OS V5 — Base Signal Detector |
| lib.v5.detectors.calendar_meet_detector | `lib/v5/detectors/calendar_meet_detector.py` | 122 | Time OS V5 — Calendar/Meet Detector |
| lib.v5.detectors.gchat_detector | `lib/v5/detectors/gchat_detector.py` | 223 | Time OS V5 — Google Chat Detector |
| lib.v5.detectors.gmail_detector | `lib/v5/detectors/gmail_detector.py` | 291 | Time OS V5 — Gmail Detector |
| lib.v5.detectors.registry | `lib/v5/detectors/registry.py` | 260 | Time OS V5 — Detector Registry |
| lib.v5.detectors.xero_financial_detector | `lib/v5/detectors/xero_financial_detector.py` | 112 | Time OS V5 — Xero Financial Detector |
| lib.v5.integrations.__init__ | `lib/v5/integrations/__init__.py` | 1 | Time OS V5 — integrations module. |
| lib.v5.issues.__init__ | `lib/v5/issues/__init__.py` | 37 | Time OS V5 — Issues Package |
| lib.v5.issues.formation_service | `lib/v5/issues/formation_service.py` | 405 | Time OS V5 — Issue Formation Service |
| lib.v5.issues.patterns | `lib/v5/issues/patterns.py` | 271 | Time OS V5 — Issue Patterns |
| lib.v5.jobs.__init__ | `lib/v5/jobs/__init__.py` | 1 | Time OS V5 — jobs module. |
| lib.v5.migrations.__init__ | `lib/v5/migrations/__init__.py` | 1 | Time OS V5 — migrations module. |
| lib.v5.models.__init__ | `lib/v5/models/__init__.py` | 192 | Time OS V5 — Models Package |
| lib.v5.models.base | `lib/v5/models/base.py` | 259 | Time OS V5 — Base Models |
| lib.v5.models.calendar | `lib/v5/models/calendar.py` | 510 | Time OS V5 — Calendar & Meet Integration Models |
| lib.v5.models.entities | `lib/v5/models/entities.py` | 507 | Time OS V5 — Entity Models |
| lib.v5.models.gchat | `lib/v5/models/gchat.py` | 273 | Time OS V5 — Google Chat Integration Models |
| lib.v5.models.issue | `lib/v5/models/issue.py` | 484 | Time OS V5 — Issue Model |
| lib.v5.models.signal | `lib/v5/models/signal.py` | 517 | Time OS V5 — Signal Model |
| lib.v5.models.xero | `lib/v5/models/xero.py` | 251 | Time OS V5 — Xero Integration Models |
| lib.v5.repositories.__init__ | `lib/v5/repositories/__init__.py` | 11 | Time OS V5 — Repositories Package |
| lib.v5.repositories.signal_repository | `lib/v5/repositories/signal_repository.py` | 567 | Time OS V5 — Signal Repository |
| lib.v5.resolution.__init__ | `lib/v5/resolution/__init__.py` | 33 | Time OS V5 — Resolution Package |
| lib.v5.resolution.balance_rules | `lib/v5/resolution/balance_rules.py` | 229 | Time OS V5 — Balance Rules Configuration |
| lib.v5.resolution.balance_service | `lib/v5/resolution/balance_service.py` | 513 | Time OS V5 — Balance Service |
| lib.v5.resolution.resolution_service | `lib/v5/resolution/resolution_service.py` | 412 | Time OS V5 — Resolution Service |
| lib.v5.services.__init__ | `lib/v5/services/__init__.py` | 14 | Time OS V5 — Services Package |
| lib.v5.services.detection_orchestrator | `lib/v5/services/detection_orchestrator.py` | 336 | Time OS V5 — Detection Orchestrator |
| lib.v5.services.signal_service | `lib/v5/services/signal_service.py` | 439 | Time OS V5 — Signal Service |

---

## ENTRY-POINT Modules
| Module | Path | Purpose |
|--------|------|---------|
| api.server | `api/server.py` | MOH TIME OS API Server - REST API for dashboard and integrations. |
| collectors._legacy.asana_sync | `collectors/_legacy/asana_sync.py` | Asana Full Sync — Proper hierarchy-aware sync. |
| collectors.chat_direct | `collectors/chat_direct.py` | Direct Google Chat API access using service account. Bypasses gog CLI to avoid I |
| collectors.contacts_direct | `collectors/contacts_direct.py` | Direct Google Contacts/People API access using service account. |
| collectors.drive_direct | `collectors/drive_direct.py` | Direct Google Drive API access using service account. |
| collectors.gmail_multi_user | `collectors/gmail_multi_user.py` | Gmail Multi-User Collector |
| collectors.scheduled_collect | `collectors/scheduled_collect.py` | Scheduled Collector — Runs periodically to refresh cached data. |
| collectors.xero_ops | `collectors/xero_ops.py` | Xero Operational Intelligence collector. |
| engine.asana_client | `engine/asana_client.py` | Asana API client using Personal Access Token. |
| engine.financial_pulse | `engine/financial_pulse.py` | Financial Pulse — MVP |
| engine.heartbeat_pulse | `engine/heartbeat_pulse.py` | Heartbeat Pulse — Surface what matters during heartbeat checks. |
| engine.knowledge_base | `engine/knowledge_base.py` | Knowledge base: ingest clients, team, projects from source systems. |
| engine.xero_client | `engine/xero_client.py` | Xero API client with OAuth2 refresh token flow. |
| lib.agency_snapshot.capacity_command_page7 | `lib/agency_snapshot/capacity_command_page7.py` | Capacity Command Engine - Page 7 LOCKED SPEC (v1) |
| lib.agency_snapshot.cash_ar | `lib/agency_snapshot/cash_ar.py` | Cash/AR Command Engine - Page 3 locked spec implementation. |
| lib.agency_snapshot.cash_ar_page12 | `lib/agency_snapshot/cash_ar_page12.py` | Cash/AR Command Engine - Page 12 LOCKED SPEC (v1) |
| lib.agency_snapshot.client360_page10 | `lib/agency_snapshot/client360_page10.py` | Client 360 Engine - Page 10 LOCKED SPEC (v1) |
| lib.agency_snapshot.comms_commitments | `lib/agency_snapshot/comms_commitments.py` | Comms/Commitments Command Engine - Page 4 locked spec implementation. |
| lib.agency_snapshot.comms_commitments_page11 | `lib/agency_snapshot/comms_commitments_page11.py` | Comms/Commitments Command Engine - Page 11 LOCKED SPEC (v1) |
| lib.aggregator | `lib/aggregator.py` | Aggregator Module - Produces unified snapshot.json per MASTER_SPEC.md §15.3 |
| lib.analyzers.attendance | `lib/analyzers/attendance.py` | Attendance Analyzer - Scores meeting attendance with instrumentality heuristic. |
| lib.autonomous_loop | `lib/autonomous_loop.py` | Autonomous Loop - The heart of MOH TIME OS. This is the MAIN WIRING - connects a |
| lib.brief | `lib/brief.py` | Morning brief generation for MOH Time OS. |
| lib.build_client_identities | `lib/build_client_identities.py` | Build Client Identities Registry |
| lib.build_team_registry | `lib/build_team_registry.py` | Build Team Member Registry |
| lib.calibration | `lib/calibration.py` | Weekly Calibration Loop - Reviews patterns and adjusts weights. |
| lib.capacity_truth.calculator | `lib/capacity_truth/calculator.py` | Capacity Calculator - Compute lane capacity and utilization. |
| lib.capacity_truth.debt_tracker | `lib/capacity_truth/debt_tracker.py` | Debt Tracker - Track and resolve time debt for lanes. |
| lib.change_bundles | `lib/change_bundles.py` | MOH Time OS — Change Bundle System |
| lib.classify | `lib/classify.py` | Client tier classification and data quality tools. |
| lib.client_truth.health_calculator | `lib/client_truth/health_calculator.py` | Health Calculator - Compute client health scores. |
| lib.client_truth.linker | `lib/client_truth/linker.py` | Client Linker - Link projects to clients. |
| lib.collectors.all_users_runner | `lib/collectors/all_users_runner.py` | All-Users Runner - Collects Gmail + Calendar for all internal users. |
| lib.collectors.calendar | `lib/collectors/calendar.py` | Calendar Collector - Pulls events from Google Calendar via Service Account API.  |
| lib.collectors.debug_directory_auth | `lib/collectors/debug_directory_auth.py` | Isolated Directory API Auth Probe - Debug Script |
| lib.collectors.debug_dwd_token | `lib/collectors/debug_dwd_token.py` | (no description) |
| lib.collectors.debug_dwd_token2 | `lib/collectors/debug_dwd_token2.py` | (no description) |
| lib.collectors.debug_dwd_token3 | `lib/collectors/debug_dwd_token3.py` | debug_dwd_token3.py |
| lib.collectors.orchestrator | `lib/collectors/orchestrator.py` | Collector Orchestrator - Manages all collectors and coordinates syncing. This is |
| lib.collectors.test_calendar_sync_modes | `lib/collectors/test_calendar_sync_modes.py` | Unit tests for Calendar sync mode code paths. |
| lib.collectors.xero | `lib/collectors/xero.py` | Xero Collector - Full invoice sync from Xero. |
| lib.commitment_extractor | `lib/commitment_extractor.py` | Commitment Extractor |
| lib.commitment_truth.commitment_manager | `lib/commitment_truth/commitment_manager.py` | Commitment Manager - CRUD and linking for commitments. |
| lib.commitment_truth.detector | `lib/commitment_truth/detector.py` | Commitment Detector - Pattern-based extraction of promises and requests. |
| lib.commitment_truth.llm_extractor | `lib/commitment_truth/llm_extractor.py` | LLM-based Commitment Extraction |
| lib.config_store | `lib/config_store.py` | MOH Time OS — Configuration Store |
| lib.conflicts | `lib/conflicts.py` | MOH Time OS — Conflict Tracking |
| lib.contacts | `lib/contacts.py` | External contact management.  External contacts are PEOPLE at CLIENT COMPANIES,  |
| lib.cron_tasks | `lib/cron_tasks.py` | Cron task handlers for MOH Time OS. |
| lib.daemon | `lib/daemon.py` | Time OS Daemon — Standalone Background Scheduler |
| lib.delegation_engine | `lib/delegation_engine.py` | MOH Time OS — Delegation Engine |
| lib.delegation_graph | `lib/delegation_graph.py` | MOH Time OS — Delegation Graph |
| lib.enrollment_detector | `lib/enrollment_detector.py` | Enrollment Detector - Detects potential new retainers/projects from signals. |
| lib.entity_linker | `lib/entity_linker.py` | Entity Linker — Links projects to clients, brands, and sets engagement types. |
| lib.gates | `lib/gates.py` | Gates Module - Data Integrity & Quality Gates |
| lib.heartbeat_processor | `lib/heartbeat_processor.py` | Heartbeat Processor — Intelligent heartbeat handling. |
| lib.lane_assigner | `lib/lane_assigner.py` | Lane Assignment Logic |
| lib.link_projects | `lib/link_projects.py` | Improve project-client linking. |
| lib.maintenance | `lib/maintenance.py` | Maintenance utilities for MOH Time OS. |
| lib.migrations.migrate_to_spec_v12 | `lib/migrations/migrate_to_spec_v12.py` | Migration to MASTER_SPEC.md §12 - EXACT COMPLIANCE |
| lib.migrations.normalize_client_ids | `lib/migrations/normalize_client_ids.py` | Client ID Normalization Migration |
| lib.migrations.rebuild_schema_v12 | `lib/migrations/rebuild_schema_v12.py` | Schema Rebuild Migration - Align with MASTER_SPEC.md §12 |
| lib.migrations.seed_brands | `lib/migrations/seed_brands.py` | Seed Brands Migration - Create brands from existing project names |
| lib.migrations.spec_schema_migration | `lib/migrations/spec_schema_migration.py` | Spec Schema Migration - Align database with MASTER_SPEC.md §12 |
| lib.migrations.v29_engagement_lifecycle | `lib/migrations/v29_engagement_lifecycle.py` | v2.9 Engagement Lifecycle Migration |
| lib.migrations.v29_full_schema | `lib/migrations/v29_full_schema.py` | v2.9 Full Schema Migration |
| lib.migrations.v29_inbox_schema | `lib/migrations/v29_inbox_schema.py` | v2.9 Inbox Schema Migration |
| lib.migrations.v29_org_settings | `lib/migrations/v29_org_settings.py` | v2.9 Org Settings Migration |
| lib.migrations.v29_spec_alignment | `lib/migrations/v29_spec_alignment.py` | v2.9 Spec Alignment Migration |
| lib.migrations.v4_milestone1_truth_proof | `lib/migrations/v4_milestone1_truth_proof.py` | Time OS V4 Migration - Milestone 1: Truth & Proof Backbone |
| lib.migrations.v4_milestone4_intersections_reports_policy | `lib/migrations/v4_milestone4_intersections_reports_policy.py` | Time OS V4 Migration - Milestone 4: Intersections, Reports & Policy |
| lib.move_executor | `lib/move_executor.py` | Move Executor - Execute approved moves per MASTER_SPEC.md §18.6 |
| lib.moves | `lib/moves.py` | Exec Moves Engine - Per MASTER_SPEC.md §18 |
| lib.normalizer | `lib/normalizer.py` | Normalizer - Single Source of Truth for Derived Columns |
| lib.notifier.briefs | `lib/notifier/briefs.py` | Brief Generator - Creates and sends scheduled briefings. |
| lib.priority_engine | `lib/priority_engine.py` | MOH Time OS — Priority Scoring Engine |
| lib.projects | `lib/projects.py` | MOH Time OS — Project Registry |
| lib.promise_tracker | `lib/promise_tracker.py` | Promise Debt Tracker — Captures and tracks commitments made in conversation. |
| lib.resolution_queue | `lib/resolution_queue.py` | Resolution Queue - Surfaces entities needing manual resolution |
| lib.routing_engine | `lib/routing_engine.py` | MOH Time OS — Routing Engine |
| lib.scheduling_engine | `lib/scheduling_engine.py` | MOH Time OS — Scheduling & Capacity Engine |
| lib.state_tracker | `lib/state_tracker.py` | State Tracker — Tracks what's been surfaced to avoid duplicate alerts. |
| lib.status_engine | `lib/status_engine.py` | MOH Time OS — Status Engine |
| lib.sync | `lib/sync.py` | Sync data from Xero and Asana into MOH Time OS v2. |
| lib.sync_ar | `lib/sync_ar.py` | Sync AR data from Xero and update client tiers. |
| lib.sync_asana | `lib/sync_asana.py` | Asana → Projects & Items sync. |
| lib.sync_xero | `lib/sync_xero.py` | Xero → Clients sync. |
| lib.task_classification | `lib/task_classification.py` | Task classification - distinguish work from tracking. |
| lib.task_duration | `lib/task_duration.py` | Smart task duration estimation based on title patterns. |
| lib.task_parser | `lib/task_parser.py` | Task Title Parser - Extracts client/project info from task titles. |
| lib.time_truth.block_manager | `lib/time_truth/block_manager.py` | Block Manager - Core time block operations for Tier 0 (Time Truth). |
| lib.time_truth.brief | `lib/time_truth/brief.py` | Time Brief Generator - Generate the Time Truth portion of the daily brief. |
| lib.time_truth.calendar_sync | `lib/time_truth/calendar_sync.py` | Calendar Sync - Synchronize calendar events and generate time blocks. |
| lib.time_truth.rollover | `lib/time_truth/rollover.py` | Rollover - Move incomplete tasks to the next day. |
| lib.time_truth.scheduler | `lib/time_truth/scheduler.py` | Scheduler - Auto-schedule tasks into time blocks. |
| lib.ui_spec_v21.detectors | `lib/ui_spec_v21/detectors.py` | Detector Module — Spec Section 6.4 |
| lib.ui_spec_v21.evidence | `lib/ui_spec_v21/evidence.py` | Evidence Module — Spec Section 6.16 |
| lib.ui_spec_v21.health | `lib/ui_spec_v21/health.py` | Health Score Module — Spec Section 6.6 |
| lib.ui_spec_v21.inbox_enricher | `lib/ui_spec_v21/inbox_enricher.py` | Inbox Enricher — Populates drill-down context for inbox items. |
| lib.ui_spec_v21.migrations.__init__ | `lib/ui_spec_v21/migrations/__init__.py` | Migration Runner — Time OS UI Spec v2.1 |
| lib.ui_spec_v21.tests.test_integration | `lib/ui_spec_v21/tests/test_integration.py` | Integration Tests — Full Lifecycle Flows |
| lib.ui_spec_v21.tests.test_spec_cases | `lib/ui_spec_v21/tests/test_spec_cases.py` | Spec Test Cases — Time OS UI Spec v2.1 |
| lib.ui_spec_v21.time_utils | `lib/ui_spec_v21/time_utils.py` | Time Utilities — Spec Section 0.1 |
| lib.v4.proposal_aggregator | `lib/v4/proposal_aggregator.py` | Time OS V4 - Proposal Aggregator |
| lib.v4.proposal_scoring | `lib/v4/proposal_scoring.py` | Time OS V4 - Proposal Scoring |
| lib.v4.seed_identities | `lib/v4/seed_identities.py` | Time OS V4 - Seed Identities from Existing Tables |
| lib.v5.migrations.run_migrations | `lib/v5/migrations/run_migrations.py` | Time OS V5 — Migration Runner |
| lib.v5.orchestrator | `lib/v5/orchestrator.py` | Time OS V5 — Main Orchestrator |

---

## UNCERTAIN (needs manual review)
| Module | Path | Lines | Reason |
|--------|------|-------|--------|
| api.spec_router | `api/spec_router.py` | 1369 | Imported by: api/server.py |
| lib.analyzers.__init__ | `lib/analyzers/__init__.py` | 18 | Imported by: api/server.py, cli/main.py, lib/notifier/briefs |
| lib.audit.__init__ | `lib/audit/__init__.py` | 302 | Imported by: scripts/replay_events.py |
| lib.capacity_truth.__init__ | `lib/capacity_truth/__init__.py` | 23 | Imported by: lib/capacity_truth/debt_tracker.py |
| lib.collectors.__init__ | `lib/collectors/__init__.py` | 18 | Imported by: api/server.py, cli/main.py |
| lib.commitment_truth.__init__ | `lib/commitment_truth/__init__.py` | 27 | Imported by: lib/commitment_truth/commitment_manager.py |
| lib.contracts.__init__ | `lib/contracts/__init__.py` | 74 | Imported by: lib/agency_snapshot/generator.py, scripts/spec_ |
| lib.contracts.predicates | `lib/contracts/predicates.py` | 220 | Imported by: lib/agency_snapshot/generator.py, scripts/valid |
| lib.contracts.schema | `lib/contracts/schema.py` | 326 | Imported by: lib/agency_snapshot/generator.py, scripts/spec_ |
| lib.contracts.thresholds | `lib/contracts/thresholds.py` | 338 | Imported by: lib/agency_snapshot/generator.py, scripts/valid |
| lib.db | `lib/db.py` | 744 | Imported by: scripts/migrate_matrix.py, scripts/rollback_dri |
| lib.entities | `lib/entities.py` | 751 | Imported by: lib/sync_asana.py, lib/sync_xero.py |
| lib.executor.__init__ | `lib/executor/__init__.py` | 9 | Imported by: cli/main.py |
| lib.features.__init__ | `lib/features/__init__.py` | 215 | Imported by: scripts/flags_smoke.py |
| lib.governance | `lib/governance.py` | 326 | Imported by: api/server.py, cli/main.py |
| lib.items | `lib/items.py` | 565 | Imported by: lib/sync_asana.py |
| lib.notifier.__init__ | `lib/notifier/__init__.py` | 10 | Imported by: lib/notifier/briefs.py |
| lib.notifier.engine | `lib/notifier/engine.py` | 392 | Imported by: lib/notifier/briefs.py |
| lib.observability.__init__ | `lib/observability/__init__.py` | 95 | Imported by: lib/audit/__init__.py, scripts/trace_smoke.py |
| lib.observability.tracing | `lib/observability/tracing.py` | 271 | Imported by: lib/audit/__init__.py, scripts/trace_smoke.py |
| lib.safety.__init__ | `lib/safety/__init__.py` | 46 | Imported by: scripts/migrate_matrix.py, scripts/rollback_dri |
| lib.safety.migrations | `lib/safety/migrations.py` | 508 | Imported by: tools/db_exec.py |
| lib.safety.schema | `lib/safety/schema.py` | 302 | Imported by: scripts/migrate_matrix.py |
| lib.store | `lib/store.py` | 237 | Imported by: lib/migrations/normalize_client_ids.py, lib/syn |
| lib.time_truth.__init__ | `lib/time_truth/__init__.py` | 31 | Imported by: lib/time_truth/brief.py, lib/time_truth/calenda |
| lib.v4.__init__ | `lib/v4/__init__.py` | 57 | Imported by: api/server.py, cli_v4.py |
| lib.v4.coupling_service | `lib/v4/coupling_service.py` | 305 | Imported by: api/server.py |
| lib.v4.ingest_pipeline | `lib/v4/ingest_pipeline.py` | 597 | Imported by: cli_v4.py |
| lib.v4.issue_service | `lib/v4/issue_service.py` | 771 | Imported by: api/server.py |
| lib.v4.orchestrator | `lib/v4/orchestrator.py` | 402 | Imported by: cli_v4.py |
| lib.v4.proposal_service | `lib/v4/proposal_service.py` | 719 | Imported by: api/server.py |