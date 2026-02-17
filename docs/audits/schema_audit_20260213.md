# Schema Audit — 2026-02-13

## Summary
- Total tables: 83
- Total views: 3
- ACTIVE: 60 (171,083 rows)
- POPULATED-ORPHAN: 5 (201,540 rows)
- EMPTY-REFERENCED: 15
- EMPTY-ORPHAN: 3 (safe to drop)
- LEGACY-VERSION: 0

---

## Core Entity Tables
| Entity | Table Name | Primary Key | Row Count | Key Relationships |
|--------|-----------|-------------|-----------|-------------------|
| Clients | `clients` | id | 160 | (pending analysis) |
| Projects | `projects` | id | 354 | (pending analysis) |
| Tasks | `tasks` | id | 3,946 | (pending analysis) |
| People/Contacts | `people` | id | 71 | (pending analysis) |
| Gmail messages | _(not found)_ | — | — | — |
| Chat messages | _(not found)_ | — | — | — |
| Calendar events | `calendar_events` | id | 38,643 | (pending analysis) |
| Drive files | _(not found)_ | — | — | — |
| Invoices | `invoices` | id | 1,254 | (pending analysis) |
| Issues | `issues` | issue_id | 10 | (pending analysis) |
| Inbox items | `inbox_items_v29` | id | 121 | (pending analysis) |

---

## ACTIVE Tables
| Table | Rows | Referenced By |
|-------|------|--------------|
| `artifact_excerpts` | 42,415 | lib/migrations/v4_milestone1_truth_proof.py, lib/v4/artifact_service.py, lib/v4/policy_service.py (+1 more) |
| `calendar_events` | 38,643 | lib/collectors/test_calendar_sync_modes.py, lib/agency_snapshot/capacity_command_page7.py |
| `couplings` | 37,200 | lib/v4/coupling_service.py, lib/v4/orchestrator.py |
| `entity_links` | 30,129 | lib/migrations/v4_milestone1_truth_proof.py, lib/v4/policy_service.py, lib/v4/entity_link_service.py (+5 more) |
| `artifact_blobs` | 4,367 | lib/migrations/v4_milestone1_truth_proof.py, lib/v4/artifact_service.py, lib/v4/policy_service.py (+2 more) |
| `artifacts` | 4,070 | lib/migrations/v4_milestone1_truth_proof.py, lib/v4/artifact_service.py, lib/v4/ingest_pipeline.py (+9 more) |
| `tasks` | 3,946 | lib/db.py, lib/state_store.py, lib/lane_assigner.py (+63 more) |
| `detector_runs` | 1,538 | lib/v4/signal_service.py |
| `invoices` | 1,254 | lib/db.py, lib/build_client_identities.py, lib/moves.py (+25 more) |
| `sync_cursor` | 1,222 | lib/collectors/all_users_runner.py, lib/collectors/test_calendar_sync_modes.py |
| `identity_profiles` | 880 | lib/migrations/v4_milestone1_truth_proof.py, lib/v4/identity_service.py |
| `signals` | 807 | lib/db.py, lib/state_store.py, lib/enrollment_detector.py (+23 more) |
| `identity_claims` | 724 | lib/migrations/v4_milestone1_truth_proof.py, lib/v4/identity_service.py |
| `fix_data_queue` | 532 | lib/migrations/v4_milestone1_truth_proof.py, lib/v4/entity_link_service.py, lib/v4/collector_hooks.py (+1 more) |
| `issue_evidence` | 462 | lib/v4/issue_service.py |
| `item_history` | 450 | lib/store.py, lib/items.py, api/spec_router.py |
| `projects` | 354 | lib/store.py, lib/db.py, lib/state_store.py (+47 more) |
| `cycle_logs` | 341 | lib/autonomous_loop.py, lib/governance.py, lib/agency_snapshot/confidence.py (+2 more) |
| `items` | 272 | lib/store.py, lib/moves.py, lib/aggregator.py (+28 more) |
| `db_write_audit_v1` | 244 | lib/safety/audit.py, lib/safety/migrations.py, lib/safety/schema.py |
| `events` | 167 | lib/db.py, lib/state_store.py, lib/enrollment_detector.py (+18 more) |
| `issue_signals` | 166 | lib/ui_spec_v21/endpoints.py, lib/v4/issue_service.py |
| `clients` | 160 | lib/store.py, lib/db.py, lib/build_client_identities.py (+61 more) |
| `communications` | 132 | lib/db.py, lib/state_store.py, lib/build_client_identities.py (+32 more) |
| `inbox_items_v29` | 121 | lib/db.py, lib/safety/__init__.py, lib/safety/migrations.py (+7 more) |
| `protocol_violations` | 80 | lib/v4/policy_service.py, lib/v4/detectors/anomaly_detector.py |
| `people` | 71 | lib/store.py, lib/db.py, lib/task_duration.py (+18 more) |
| `commitments` | 37 | lib/moves.py, lib/resolution_queue.py, lib/aggregator.py (+15 more) |
| `subject_blocklist` | 37 | lib/collectors/all_users_runner.py |
| `asana_project_map` | 36 | lib/migrations/spec_schema_migration.py, lib/migrations/migrate_to_spec_v12.py |
| `team_members` | 31 | lib/build_team_registry.py, lib/migrations/spec_schema_migration.py, lib/migrations/migrate_to_spec_v12.py (+4 more) |
| `brands` | 20 | lib/gates.py, lib/entity_linker.py, lib/normalizer.py (+11 more) |
| `proposals_v4` | 20 | lib/db.py, lib/state_store.py, lib/v4/proposal_service.py (+3 more) |
| `signal_definitions` | 15 | lib/v4/coupling_service.py, lib/v4/signal_service.py |
| `events_raw` | 14 | lib/v4/ingest_pipeline.py, engine/store.py |
| `watchers` | 13 | lib/v4/orchestrator.py, lib/v4/issue_service.py, api/server.py (+1 more) |
| `signal_feedback` | 11 | lib/v4/signal_service.py |
| `entity_acl` | 10 | lib/v4/policy_service.py |
| `issues` | 10 | lib/db.py, lib/migrations/normalize_client_ids.py, lib/v5/orchestrator.py (+16 more) |
| `client_health_log` | 9 | lib/client_truth/health_calculator.py, lib/agency_snapshot/client360_page10.py |
| `decision_log` | 9 | lib/v4/issue_service.py |
| `issue_notes` | 9 | api/server.py |
| `issue_transitions` | 6 | lib/migrations/v29_inbox_schema.py, lib/ui_spec_v21/time_utils.py, lib/ui_spec_v21/inbox_lifecycle.py (+4 more) |
| `issues_v29` | 6 | lib/db.py, lib/safety/migrations.py, lib/safety/schema.py (+5 more) |
| `retention_rules` | 6 | lib/v4/policy_service.py |
| `redaction_markers` | 5 | lib/v4/policy_service.py |
| `access_roles` | 4 | lib/v4/policy_service.py |
| `detector_versions` | 4 | lib/v4/signal_service.py |
| `report_templates` | 4 | lib/v4/report_service.py |
| `sync_state` | 4 | lib/state_store.py, lib/agency_snapshot/confidence.py, lib/agency_snapshot/client360.py |
| `_schema_version` | 3 | lib/migrations/v4_milestone4_intersections_reports_policy.py, lib/migrations/v4_milestone1_truth_proof.py |
| `handoffs` | 3 | lib/v4/issue_service.py |
| `identity_operations` | 2 | lib/migrations/v4_milestone1_truth_proof.py, lib/v4/identity_service.py |
| `report_snapshots` | 2 | lib/v4/report_service.py |
| `config_kv` | 1 | engine/store.py |
| `inbox_suppression_rules_v29` | 1 | lib/db.py, lib/safety/migrations.py, lib/safety/schema.py (+1 more) |
| `maintenance_mode_v1` | 1 | lib/safety/migrations.py, lib/safety/schema.py |
| `org_settings` | 1 | lib/migrations/v29_org_settings.py, lib/ui_spec_v21/org_settings.py |
| `proposals` | 1 | lib/scheduling_engine.py, lib/status_engine.py, lib/v4/proposal_aggregator.py (+6 more) |
| `write_context_v1` | 1 | lib/safety/context.py, lib/safety/migrations.py, lib/safety/schema.py |

---

## POPULATED-ORPHAN Tables (have data, nothing reads them)
| Table | Rows | Sample Columns | Possible Purpose |
|-------|------|----------------|-----------------|
| `chat_messages` | 183,244 | id, subject_email, message_name, space_name... | Chat messages |
| `drive_files` | 17,722 | id, subject_email, file_id, name... | Drive files |
| `docs_documents` | 318 | id, subject_email, doc_id, title... | (unknown) |
| `gmail_messages` | 255 | id, subject_email, message_id, thread_id... | Gmail messages |
| `_health_check` | 1 | id, checked_at | (unknown) |

---

## EMPTY-REFERENCED Tables
| Table | Referenced By |
|-------|--------------|
| `actions` | lib/state_store.py, lib/reasoner/decisions.py, lib/ui_spec_v21/endpoints.py |
| `capacity_lanes` | lib/gates.py, lib/capacity_truth/calculator.py, lib/migrations/migrate_to_spec_v12.py |
| `client_projects` | lib/migrations/normalize_client_ids.py, lib/client_truth/health_calculator.py, lib/client_truth/linker.py |
| `conflicts` | lib/config_store.py, lib/analyzers/time.py, lib/analyzers/orchestrator.py |
| `decisions` | lib/state_store.py, lib/autonomous_loop.py, lib/analyzers/anomaly.py |
| `engagement_transitions` | lib/ui_spec_v21/engagement_lifecycle.py |
| `engagements` | lib/normalize/resolvers.py, lib/ui_spec_v21/engagement_lifecycle.py, lib/ui_spec_v21/inbox_lifecycle.py |
| `feedback` | lib/link_projects.py, lib/calibration.py, lib/analyzers/patterns.py |
| `identities` | lib/v4/ingest_pipeline.py, lib/v4/orchestrator.py, api/server.py |
| `inbox_suppression_rules` | lib/migrations/v29_inbox_schema.py, lib/ui_spec_v21/time_utils.py, lib/ui_spec_v21/tests/test_spec_cases.py |
| `insights` | lib/state_store.py, lib/calibration.py, lib/analyzers/orchestrator.py |
| `issue_transitions_v29` | lib/db.py, lib/safety/migrations.py, lib/safety/schema.py |
| `notifications` | lib/autonomous_loop.py, lib/notifier/engine.py, lib/executor/handlers/notification.py |
| `patterns` | lib/analyzers/patterns.py, lib/analyzers/orchestrator.py, lib/v4/ingest_pipeline.py |
| `time_debt` | lib/capacity_truth/debt_tracker.py, lib/capacity_truth/calculator.py, lib/agency_snapshot/capacity_command_page7.py |

---

## EMPTY-ORPHAN Tables (safe to drop)
| Table |
|-------|
| `canonical_projects` |
| `canonical_tasks` |
| `change_bundles` |

---

## LEGACY-VERSION Tables
| Table | Version | Rows | Likely Current Version |
|-------|---------|------|----------------------|

---

## Views
| View | Selects From | Purpose |
|------|-------------|---------|
| `inbox_items` | inbox_items_v29 | Inbox items |
| `issues_v29_view_backup` | issues_v29 | Issues |
| `signals_v29` | signals | (utility) |

---

## Version Lineage

_(no multi-version tables detected)_
