"""
Declarative Schema Definition — THE single source of truth.

Every table, column, index, and data migration for MOH TIME OS lives here.
Nothing else defines schema. The schema_engine reads this and converges
any database to match.

Adding a column = add one line here. The engine handles the rest.
No migration scripts, no scattered ALTER TABLEs, no divergence.

Column definitions use CREATE TABLE syntax. The schema_engine knows how
to derive ALTER TABLE ADD COLUMN DDL (strips PK, adjusts NOT NULL, etc.).
"""

from collections import OrderedDict

# =============================================================================
# Schema version — bump when you change this file
# =============================================================================
SCHEMA_VERSION = 27

# =============================================================================
# Table Definitions
#
# Format: TABLES[name] = {"columns": [(col_name, col_ddl), ...]}
#
# col_ddl is the full column definition as used in CREATE TABLE.
# For ALTER TABLE ADD COLUMN, the engine strips unsupported clauses.
# =============================================================================

TABLES: dict[str, dict] = OrderedDict()

# ---------------------------------------------------------------------------
# §12 Core: clients
# ---------------------------------------------------------------------------
TABLES["clients"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("name_normalized", "TEXT"),
        ("tier", "TEXT DEFAULT 'C'"),
        ("health_score", "REAL"),
        ("type", "TEXT"),
        # Financial
        ("financial_annual_value", "REAL"),
        ("financial_ar_outstanding", "REAL"),
        ("financial_ar_aging", "TEXT"),
        ("financial_payment_pattern", "TEXT"),
        # Relationship
        ("relationship_health", "TEXT"),
        ("relationship_trend", "TEXT"),
        ("relationship_last_interaction", "TEXT"),
        ("relationship_notes", "TEXT"),
        # JSON blobs
        ("contacts_json", "TEXT"),
        ("active_projects_json", "TEXT"),
        # Revenue (used by drift detector with COALESCE fallback)
        ("prior_year_revenue", "REAL"),
        ("ytd_revenue", "REAL"),
        ("lifetime_revenue", "REAL"),
        # External IDs
        ("xero_contact_id", "TEXT"),
        # Timestamps
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12 Core: brands
# ---------------------------------------------------------------------------
TABLES["brands"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("client_id", "TEXT NOT NULL REFERENCES clients(id)"),
        ("name", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12 Core: projects
# ---------------------------------------------------------------------------
TABLES["projects"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("source", "TEXT"),
        ("source_id", "TEXT"),
        ("name", "TEXT NOT NULL"),
        ("name_normalized", "TEXT"),
        ("brand_id", "TEXT"),
        ("client_id", "TEXT"),
        ("is_internal", "INTEGER NOT NULL DEFAULT 0"),
        ("type", "TEXT NOT NULL DEFAULT 'project'"),
        ("engagement_type", "TEXT"),
        ("status", "TEXT DEFAULT 'active'"),
        ("health", "TEXT DEFAULT 'green'"),
        ("enrollment_status", "TEXT DEFAULT 'enrolled'"),
        ("rule_bundles", "TEXT"),
        ("owner", "TEXT"),
        ("deadline", "TEXT"),
        ("tasks_total", "INTEGER DEFAULT 0"),
        ("tasks_done", "INTEGER DEFAULT 0"),
        ("blockers", "TEXT"),
        ("next_milestone", "TEXT"),
        ("context", "TEXT"),
        # Extended project metadata
        ("involvement_type", "TEXT"),
        ("aliases", "TEXT"),
        ("recognizers", "TEXT"),
        ("lane_mapping", "TEXT"),
        ("routing_rules", "TEXT"),
        ("delegation_policy", "TEXT"),
        ("reporting_cadence", "TEXT"),
        ("sensitivity_profile", "TEXT"),
        ("enrollment_evidence", "TEXT"),
        ("enrolled_at", "TEXT"),
        ("health_reasons", "TEXT"),
        ("owner_id", "TEXT"),
        ("owner_name", "TEXT"),
        ("lane", "TEXT"),
        ("client", "TEXT"),
        ("days_to_deadline", "INTEGER"),
        ("tasks_completed", "INTEGER"),
        ("tasks_overdue", "INTEGER"),
        ("tasks_blocked", "INTEGER"),
        ("completion_pct", "REAL"),
        ("velocity_trend", "TEXT"),
        ("next_milestone_date", "TEXT"),
        ("last_activity_at", "TEXT"),
        ("start_date", "TEXT"),
        ("target_end_date", "TEXT"),
        ("value", "REAL"),
        ("stakes", "TEXT"),
        ("description", "TEXT"),
        ("milestones", "TEXT"),
        ("team", "TEXT"),
        ("asana_project_id", "TEXT"),
        ("proposed_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# §12 Core: tasks
# ---------------------------------------------------------------------------
TABLES["tasks"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("source", "TEXT NOT NULL DEFAULT 'system'"),
        ("source_id", "TEXT"),
        ("title", "TEXT NOT NULL"),
        ("status", "TEXT DEFAULT 'active'"),
        ("priority", "INTEGER DEFAULT 50"),
        # §12 linking
        ("project_id", "TEXT"),
        ("brand_id", "TEXT"),
        ("client_id", "TEXT"),
        ("project_link_status", "TEXT DEFAULT 'unlinked'"),
        ("client_link_status", "TEXT DEFAULT 'unlinked'"),
        ("assignee_id", "TEXT"),
        ("assignee_raw", "TEXT"),
        ("lane", "TEXT DEFAULT 'ops'"),
        # Scheduling
        ("due_date", "TEXT"),
        ("due_time", "TEXT"),
        ("duration_min", "INTEGER DEFAULT 60"),
        # Legacy fields
        ("assignee", "TEXT"),
        ("project", "TEXT"),
        ("tags", "TEXT"),
        ("dependencies", "TEXT"),
        ("blockers", "TEXT"),
        ("context", "TEXT"),
        ("notes", "TEXT"),
        ("description", "TEXT DEFAULT ''"),
        ("priority_reasons", "TEXT"),
        ("synced_at", "TEXT"),
        ("completed_at", "TEXT"),
        # Collector expansion
        ("section_id", "TEXT"),
        ("section_name", "TEXT"),
        ("subtask_count", "INTEGER DEFAULT 0"),
        ("has_dependencies", "INTEGER DEFAULT 0"),
        ("attachment_count", "INTEGER DEFAULT 0"),
        ("story_count", "INTEGER DEFAULT 0"),
        ("custom_fields_json", "TEXT"),
        # Extended metadata
        ("urgency", "INTEGER"),
        ("impact", "INTEGER"),
        ("sensitivity", "TEXT"),
        ("effort_min", "INTEGER"),
        ("effort_max", "INTEGER"),
        ("waiting_for", "TEXT"),
        ("deadline_type", "TEXT"),
        ("dedupe_key", "TEXT"),
        ("conflict_markers", "TEXT"),
        ("delegated_by", "TEXT"),
        ("delegated_at", "TEXT"),
        ("assignee_name", "TEXT"),
        ("is_supervised", "INTEGER DEFAULT 0"),
        ("last_activity_at", "TEXT"),
        ("stale_days", "INTEGER"),
        ("scheduled_block_id", "TEXT"),
        # Timestamps
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12 Core: events
# ---------------------------------------------------------------------------
TABLES["events"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("source", "TEXT"),
        ("source_id", "TEXT"),
        ("title", "TEXT"),
        # Dual time columns: legacy (start_time/end_time) + current (start_at/end_at)
        ("start_time", "TEXT"),
        ("end_time", "TEXT"),
        ("start_at", "TEXT"),
        ("end_at", "TEXT"),
        ("location", "TEXT"),
        ("attendees", "TEXT"),
        ("status", "TEXT DEFAULT 'confirmed'"),
        ("prep_required", "TEXT"),
        ("prep_notes", "TEXT"),
        ("context", "TEXT"),
        # Collector expansion
        ("organizer_email", "TEXT"),
        ("organizer_name", "TEXT"),
        ("conference_url", "TEXT"),
        ("conference_type", "TEXT"),
        ("recurrence", "TEXT"),
        ("event_type", "TEXT"),
        ("calendar_id", "TEXT DEFAULT 'primary'"),
        ("attendee_count", "INTEGER DEFAULT 0"),
        ("accepted_count", "INTEGER DEFAULT 0"),
        ("declined_count", "INTEGER DEFAULT 0"),
        # Timestamps
        ("created_at", "TEXT"),
        ("updated_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# §12 Core: communications
# ---------------------------------------------------------------------------
TABLES["communications"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("source", "TEXT NOT NULL DEFAULT 'system'"),
        ("source_id", "TEXT"),
        ("thread_id", "TEXT"),
        ("from_email", "TEXT"),
        ("from_domain", "TEXT"),
        ("to_emails", "TEXT"),
        ("subject", "TEXT"),
        ("snippet", "TEXT"),
        ("body_text", "TEXT"),
        ("body_text_source", "TEXT"),
        ("content_hash", "TEXT"),
        ("received_at", "TEXT"),
        # §12 linking
        ("client_id", "TEXT"),
        ("link_status", "TEXT DEFAULT 'unlinked'"),
        # Legacy fields
        ("priority", "INTEGER DEFAULT 50"),
        ("requires_response", "INTEGER DEFAULT 0"),
        ("response_deadline", "TEXT"),
        ("sentiment", "TEXT"),
        ("labels", "TEXT"),
        ("processed", "INTEGER DEFAULT 0"),
        ("sensitivity", "TEXT"),
        ("stakeholder_tier", "TEXT"),
        ("is_read", "INTEGER"),
        ("is_starred", "INTEGER"),
        ("importance", "TEXT"),
        ("has_attachments", "INTEGER DEFAULT 0"),
        ("attachment_count", "INTEGER DEFAULT 0"),
        ("label_ids", "TEXT"),
        # Extended metadata
        ("lane", "TEXT"),
        ("is_vip", "INTEGER DEFAULT 0"),
        ("from_name", "TEXT"),
        ("is_unread", "INTEGER"),
        ("is_important", "INTEGER"),
        ("priority_reasons", "TEXT"),
        ("response_urgency", "TEXT"),
        ("expected_response_by", "TEXT"),
        ("processed_at", "TEXT"),
        ("action_taken", "TEXT"),
        ("linked_task_id", "TEXT"),
        ("age_hours", "REAL"),
        # Timestamps
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12 Core: people
# ---------------------------------------------------------------------------
TABLES["people"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("name_normalized", "TEXT"),
        ("email", "TEXT"),
        ("phone", "TEXT"),
        ("company", "TEXT"),
        ("role", "TEXT"),
        ("type", "TEXT DEFAULT 'external'"),
        ("relationship", "TEXT"),
        ("importance", "INTEGER DEFAULT 50"),
        ("last_contact", "TEXT"),
        ("contact_frequency_days", "INTEGER"),
        ("notes", "TEXT"),
        ("context", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12 Core: invoices
# Dual columns: legacy (due_at/paid_at/total) + §12 (due_date/paid_date/amount)
# ---------------------------------------------------------------------------
TABLES["invoices"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("source", "TEXT"),
        ("source_id", "TEXT"),
        ("external_id", "TEXT"),
        ("client_id", "TEXT"),
        ("client_name", "TEXT"),
        ("brand_id", "TEXT"),
        ("project_id", "TEXT"),
        # Financial — §12 names
        ("amount", "REAL"),
        ("currency", "TEXT DEFAULT 'AED'"),
        ("issue_date", "TEXT"),
        ("due_date", "TEXT"),
        ("paid_date", "TEXT"),
        ("payment_date", "TEXT"),
        # Financial — legacy names (live DB has these with data)
        ("total", "REAL"),
        ("amount_due", "REAL"),
        ("issued_at", "TEXT"),
        ("due_at", "TEXT"),
        ("paid_at", "TEXT"),
        # Status & aging
        ("status", "TEXT DEFAULT 'pending'"),
        ("aging_bucket", "TEXT"),
        # Timestamps
        ("created_at", "TEXT DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12: team_members
# ---------------------------------------------------------------------------
TABLES["team_members"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("email", "TEXT"),
        ("asana_gid", "TEXT"),
        ("default_lane", "TEXT DEFAULT 'ops'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12: client_identities
# ---------------------------------------------------------------------------
TABLES["client_identities"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16))))"),
        ("client_id", "TEXT NOT NULL REFERENCES clients(id)"),
        ("identity_type", "TEXT NOT NULL"),
        ("identity_value", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12: commitments
# ---------------------------------------------------------------------------
TABLES["commitments"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16))))"),
        ("source_type", "TEXT NOT NULL DEFAULT 'communication'"),
        ("source_id", "TEXT NOT NULL"),
        ("text", "TEXT NOT NULL"),
        ("type", "TEXT NOT NULL"),
        ("confidence", "REAL"),
        ("deadline", "TEXT"),
        ("speaker", "TEXT"),
        ("target", "TEXT"),
        ("client_id", "TEXT"),
        ("task_id", "TEXT"),
        ("status", "TEXT DEFAULT 'open'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12: capacity_lanes
# ---------------------------------------------------------------------------
TABLES["capacity_lanes"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("display_name", "TEXT"),
        ("owner", "TEXT"),
        ("weekly_hours", "INTEGER DEFAULT 40"),
        ("buffer_pct", "REAL DEFAULT 0.2"),
        ("color", "TEXT DEFAULT '#6366f1'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12: resolution_queue
# ---------------------------------------------------------------------------
TABLES["resolution_queue"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16))))"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("issue_type", "TEXT NOT NULL"),
        ("priority", "INTEGER NOT NULL DEFAULT 2"),
        ("context", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("expires_at", "TEXT"),
        ("resolved_at", "TEXT"),
        ("resolved_by", "TEXT"),
        ("resolution_action", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# §12: pending_actions
# ---------------------------------------------------------------------------
TABLES["pending_actions"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16))))"),
        ("idempotency_key", "TEXT NOT NULL"),
        ("action_type", "TEXT NOT NULL"),
        ("entity_type", "TEXT"),
        ("entity_id", "TEXT"),
        ("payload", "TEXT NOT NULL"),
        ("risk_level", "TEXT NOT NULL"),
        ("approval_mode", "TEXT NOT NULL"),
        ("status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("proposed_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("proposed_by", "TEXT"),
        ("decided_at", "TEXT"),
        ("decided_by", "TEXT"),
        ("executed_at", "TEXT"),
        ("execution_result", "TEXT"),
        ("expires_at", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12: asana_project_map
# ---------------------------------------------------------------------------
TABLES["asana_project_map"] = {
    "columns": [
        ("asana_gid", "TEXT PRIMARY KEY"),
        ("project_id", "TEXT NOT NULL"),
        ("asana_name", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §12: asana_user_map
# ---------------------------------------------------------------------------
TABLES["asana_user_map"] = {
    "columns": [
        ("asana_gid", "TEXT PRIMARY KEY"),
        ("team_member_id", "TEXT NOT NULL"),
        ("asana_name", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# V29: issues_v29
# NOTE: In the live DB this may be a VIEW. The engine skips table creation
# when the name already exists as a view.
# ---------------------------------------------------------------------------
TABLES["issues_v29"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("type", "TEXT NOT NULL"),
        ("state", "TEXT NOT NULL DEFAULT 'detected'"),
        ("severity", "TEXT NOT NULL"),
        ("client_id", "TEXT NOT NULL"),
        ("brand_id", "TEXT"),
        ("engagement_id", "TEXT"),
        ("title", "TEXT NOT NULL"),
        ("evidence", "TEXT"),
        ("evidence_version", "TEXT DEFAULT 'v1'"),
        ("aggregation_key", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
        ("snoozed_until", "TEXT"),
        ("snoozed_by", "TEXT"),
        ("snoozed_at", "TEXT"),
        ("snooze_reason", "TEXT"),
        ("tagged_by_user_id", "TEXT"),
        ("tagged_at", "TEXT"),
        ("assigned_to", "TEXT"),
        ("assigned_at", "TEXT"),
        ("assigned_by", "TEXT"),
        ("suppressed", "INTEGER NOT NULL DEFAULT 0"),
        ("suppressed_at", "TEXT"),
        ("suppressed_by", "TEXT"),
        ("escalated", "INTEGER NOT NULL DEFAULT 0"),
        ("escalated_at", "TEXT"),
        ("escalated_by", "TEXT"),
        ("regression_watch_until", "TEXT"),
        ("closed_at", "TEXT"),
    ],
    "skip_if_view": True,
}

# ---------------------------------------------------------------------------
# V29: issue_transitions_v29
# ---------------------------------------------------------------------------
TABLES["issue_transitions_v29"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("issue_id", "TEXT NOT NULL"),
        ("from_state", "TEXT NOT NULL"),
        ("to_state", "TEXT NOT NULL"),
        ("action", "TEXT"),
        ("actor", "TEXT"),
        ("reason", "TEXT"),
        ("transitioned_at", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# V29: inbox_items_v29
# ---------------------------------------------------------------------------
TABLES["inbox_items_v29"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("type", "TEXT NOT NULL"),
        ("state", "TEXT NOT NULL DEFAULT 'proposed'"),
        ("severity", "TEXT NOT NULL"),
        ("proposed_at", "TEXT NOT NULL"),
        ("last_refreshed_at", "TEXT NOT NULL"),
        ("read_at", "TEXT"),
        ("resurfaced_at", "TEXT"),
        ("resolved_at", "TEXT"),
        ("snooze_until", "TEXT"),
        ("snoozed_by", "TEXT"),
        ("snoozed_at", "TEXT"),
        ("snooze_reason", "TEXT"),
        ("dismissed_by", "TEXT"),
        ("dismissed_at", "TEXT"),
        ("dismiss_reason", "TEXT"),
        ("suppression_key", "TEXT"),
        ("underlying_issue_id", "TEXT"),
        ("underlying_signal_id", "TEXT"),
        ("resolved_issue_id", "TEXT"),
        ("title", "TEXT NOT NULL"),
        ("client_id", "TEXT"),
        ("brand_id", "TEXT"),
        ("engagement_id", "TEXT"),
        ("evidence", "TEXT"),
        ("evidence_version", "TEXT DEFAULT 'v1'"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# V29: signals_v29
# NOTE: In the live DB this may be a VIEW.
# ---------------------------------------------------------------------------
TABLES["signals_v29"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("source", "TEXT NOT NULL"),
        ("source_id", "TEXT NOT NULL"),
        ("client_id", "TEXT"),
        ("engagement_id", "TEXT"),
        ("sentiment", "TEXT"),
        ("signal_type", "TEXT"),
        ("summary", "TEXT"),
        ("observed_at", "TEXT NOT NULL"),
        ("ingested_at", "TEXT NOT NULL"),
        ("evidence", "TEXT"),
        ("dismissed_at", "TEXT"),
        ("dismissed_by", "TEXT"),
        ("analysis_provider", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
    ],
    "skip_if_view": True,
}

# ---------------------------------------------------------------------------
# V29: inbox_suppression_rules_v29
# ---------------------------------------------------------------------------
TABLES["inbox_suppression_rules_v29"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("suppression_key", "TEXT NOT NULL"),
        ("item_type", "TEXT NOT NULL"),
        ("scope_client_id", "TEXT"),
        ("scope_engagement_id", "TEXT"),
        ("scope_source", "TEXT"),
        ("scope_rule", "TEXT"),
        ("reason", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
        ("expires_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Legacy: issues
# ---------------------------------------------------------------------------
TABLES["issues"] = {
    "columns": [
        ("issue_id", "TEXT PRIMARY KEY"),
        ("source_proposal_id", "TEXT NOT NULL"),
        ("issue_type", "TEXT NOT NULL"),
        ("state", "TEXT NOT NULL DEFAULT 'open'"),
        ("primary_ref_type", "TEXT NOT NULL"),
        ("primary_ref_id", "TEXT NOT NULL"),
        ("scope_refs", "TEXT NOT NULL"),
        ("headline", "TEXT NOT NULL"),
        ("priority", "INTEGER NOT NULL"),
        ("resolution_criteria", "TEXT NOT NULL"),
        ("opened_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("last_activity_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("closed_at", "TEXT"),
        ("closed_reason", "TEXT"),
        ("visibility", "TEXT NOT NULL DEFAULT 'tagged_only'"),
    ],
}

# ---------------------------------------------------------------------------
# Legacy: signals
# ---------------------------------------------------------------------------
TABLES["signals"] = {
    "columns": [
        ("signal_id", "TEXT PRIMARY KEY"),
        ("signal_type", "TEXT NOT NULL"),
        ("entity_ref_type", "TEXT"),
        ("entity_ref_id", "TEXT"),
        ("value", "TEXT"),
        ("severity", "TEXT NOT NULL DEFAULT 'medium'"),
        ("detected_at", "TEXT"),
        ("interpretation_confidence", "REAL"),
        ("linkage_confidence_floor", "REAL"),
        ("evidence_excerpt_ids", "TEXT"),
        ("evidence_artifact_ids", "TEXT"),
        ("detector_id", "TEXT"),
        ("detector_version", "TEXT"),
        ("status", "TEXT DEFAULT 'active'"),
        ("consumed_by_proposal_id", "TEXT"),
        ("expires_at", "TEXT"),
        ("resolved_at", "TEXT"),
        ("resolution", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Proposals (v4 intelligence layer)
# ---------------------------------------------------------------------------
TABLES["proposals_v4"] = {
    "columns": [
        # V4 service columns (proposal_service.py)
        ("proposal_id", "TEXT PRIMARY KEY"),
        ("proposal_type", "TEXT NOT NULL"),
        ("primary_ref_type", "TEXT NOT NULL"),
        ("primary_ref_id", "TEXT NOT NULL"),
        ("scope_refs", "TEXT NOT NULL DEFAULT '[]'"),
        ("headline", "TEXT NOT NULL"),
        ("summary", "TEXT"),
        ("impact", "TEXT NOT NULL DEFAULT '{}'"),
        ("top_hypotheses", "TEXT NOT NULL DEFAULT '[]'"),
        ("signal_ids", "TEXT NOT NULL DEFAULT '[]'"),
        ("proof_excerpt_ids", "TEXT NOT NULL DEFAULT '[]'"),
        ("score", "REAL NOT NULL DEFAULT 0"),
        ("first_seen_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("last_seen_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("occurrence_count", "INTEGER NOT NULL DEFAULT 1"),
        ("trend", "TEXT NOT NULL DEFAULT 'flat'"),
        ("ui_exposure_level", "TEXT DEFAULT 'none'"),
        ("status", "TEXT NOT NULL DEFAULT 'open'"),
        ("snoozed_until", "TEXT"),
        ("dismissed_reason", "TEXT"),
        # Aggregator columns (spec_router.py, proposal_aggregator.py)
        ("scope_level", "TEXT DEFAULT 'project'"),
        ("scope_name", "TEXT"),
        ("client_id", "TEXT"),
        ("client_name", "TEXT"),
        ("client_tier", "TEXT"),
        ("brand_id", "TEXT"),
        ("brand_name", "TEXT"),
        ("engagement_type", "TEXT"),
        ("signal_summary_json", "TEXT"),
        ("score_breakdown_json", "TEXT"),
        ("affected_task_ids_json", "TEXT"),
        # Timestamps
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Intelligence layer
# ---------------------------------------------------------------------------
TABLES["insights"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("type", "TEXT NOT NULL"),
        ("domain", "TEXT NOT NULL"),
        ("title", "TEXT NOT NULL"),
        ("description", "TEXT"),
        ("confidence", "REAL DEFAULT 0.5"),
        ("data", "TEXT"),
        ("actionable", "INTEGER DEFAULT 0"),
        ("action_taken", "INTEGER DEFAULT 0"),
        # V19: severity for anomaly ordering (I-I1 from closure-audit, D2)
        ("severity", "TEXT DEFAULT 'medium'"),
        ("created_at", "TEXT NOT NULL"),
        ("expires_at", "TEXT"),
    ],
}

TABLES["decisions"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("domain", "TEXT NOT NULL"),
        ("decision_type", "TEXT NOT NULL"),
        ("description", "TEXT"),
        ("input_data", "TEXT"),
        ("options", "TEXT"),
        ("selected_option", "TEXT"),
        ("rationale", "TEXT"),
        ("confidence", "REAL DEFAULT 0.5"),
        ("requires_approval", "INTEGER DEFAULT 1"),
        ("approved", "INTEGER"),
        ("approved_at", "TEXT"),
        ("executed", "INTEGER DEFAULT 0"),
        ("executed_at", "TEXT"),
        ("outcome", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

TABLES["notifications"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("type", "TEXT NOT NULL"),
        ("priority", "TEXT NOT NULL DEFAULT 'normal'"),
        ("title", "TEXT NOT NULL"),
        ("body", "TEXT"),
        ("action_url", "TEXT"),
        ("action_data", "TEXT"),
        ("channels", "TEXT"),
        ("sent_at", "TEXT"),
        ("read_at", "TEXT"),
        ("acted_on_at", "TEXT"),
        # V19: dismissed ≠ read (N-I1, N-I2 from closure-audit)
        ("dismissed", "INTEGER DEFAULT 0"),
        ("dismissed_at", "TEXT"),
        # V19: task/recipient context for notification routing (N-I3, N-I4)
        ("task_id", "TEXT"),
        ("recipient_id", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

TABLES["actions"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("type", "TEXT NOT NULL"),
        ("target_system", "TEXT"),
        ("payload", "TEXT NOT NULL"),
        ("status", "TEXT DEFAULT 'pending'"),
        ("requires_approval", "INTEGER DEFAULT 1"),
        ("approved_by", "TEXT"),
        ("approved_at", "TEXT"),
        ("executed_at", "TEXT"),
        ("result", "TEXT"),
        ("error", "TEXT"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

TABLES["feedback"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("decision_id", "TEXT"),
        ("insight_id", "TEXT"),
        ("action_id", "TEXT"),
        ("feedback_type", "TEXT"),
        ("details", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

TABLES["patterns"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("domain", "TEXT NOT NULL"),
        ("pattern_type", "TEXT NOT NULL"),
        ("description", "TEXT"),
        ("data", "TEXT"),
        ("confidence", "REAL DEFAULT 0.5"),
        ("occurrences", "INTEGER DEFAULT 1"),
        ("last_seen", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# System tables
# ---------------------------------------------------------------------------
TABLES["cycle_logs"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("cycle_number", "INTEGER"),
        ("phase", "TEXT"),
        ("data", "TEXT"),
        ("duration_ms", "REAL"),
        # V19: columns used by sync_health.py for collector health checks (CL-T1..4)
        ("source", "TEXT"),
        ("status", "TEXT"),
        ("completed_at", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

TABLES["sync_state"] = {
    "columns": [
        ("source", "TEXT PRIMARY KEY"),
        ("last_sync", "TEXT"),
        ("last_success", "TEXT"),
        ("items_synced", "INTEGER DEFAULT 0"),
        ("error", "TEXT"),
        ("error_type", "TEXT"),  # auth, transport, rate_limit, timeout, parse, storage
        ("status", "TEXT"),  # success, partial, stale, failed, skipped
    ],
}

# ---------------------------------------------------------------------------
# Client health
# ---------------------------------------------------------------------------
TABLES["client_projects"] = {
    "columns": [
        ("client_id", "TEXT NOT NULL"),
        ("project_id", "TEXT NOT NULL"),
        ("linked_at", "TEXT NOT NULL"),
    ],
}

TABLES["client_health_log"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("client_id", "TEXT NOT NULL"),
        ("health_score", "INTEGER"),
        ("factors", "TEXT"),
        ("computed_at", "TEXT NOT NULL"),
    ],
}

TABLES["time_debt"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("lane", "TEXT NOT NULL"),
        ("amount_min", "INTEGER NOT NULL"),
        ("reason", "TEXT"),
        ("source_task_id", "TEXT"),
        ("incurred_at", "TEXT NOT NULL"),
        ("resolved_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# §15 Time Truth: time_blocks — scheduled time blocks for tasks
# Source: block_manager.py / calendar_sync.py
# Matches SCHEMA_ATLAS (03_SCHEMA_ATLAS.sql)
# ---------------------------------------------------------------------------
TABLES["time_blocks"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("date", "TEXT NOT NULL"),
        ("start_time", "TEXT NOT NULL"),
        ("end_time", "TEXT NOT NULL"),
        ("lane", "TEXT NOT NULL"),
        ("task_id", "TEXT REFERENCES tasks(id)"),
        ("is_protected", "INTEGER DEFAULT 0"),
        ("is_buffer", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Collector expansion: Asana
# ---------------------------------------------------------------------------
TABLES["asana_custom_fields"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("project_id", "TEXT NOT NULL"),
        ("task_id", "TEXT"),
        ("field_name", "TEXT NOT NULL"),
        ("field_type", "TEXT NOT NULL"),
        ("text_value", "TEXT"),
        ("number_value", "REAL"),
        ("enum_value", "TEXT"),
        ("date_value", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

TABLES["asana_subtasks"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("parent_task_id", "TEXT NOT NULL"),
        ("name", "TEXT NOT NULL"),
        ("assignee_id", "TEXT"),
        ("assignee_name", "TEXT"),
        ("completed", "INTEGER DEFAULT 0"),
        ("due_on", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

TABLES["asana_sections"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("project_id", "TEXT NOT NULL"),
        ("name", "TEXT NOT NULL"),
        ("sort_order", "INTEGER"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

TABLES["asana_stories"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("task_id", "TEXT NOT NULL"),
        ("type", "TEXT NOT NULL"),
        ("text", "TEXT"),
        ("created_by", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

TABLES["asana_task_dependencies"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("task_id", "TEXT NOT NULL"),
        ("depends_on_task_id", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

TABLES["asana_portfolios"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("owner_id", "TEXT"),
        ("owner_name", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

TABLES["asana_goals"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("owner_id", "TEXT"),
        ("owner_name", "TEXT"),
        ("status", "TEXT"),
        ("due_on", "TEXT"),
        ("html_notes", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

TABLES["asana_attachments"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("task_id", "TEXT NOT NULL"),
        ("name", "TEXT NOT NULL"),
        ("download_url", "TEXT"),
        ("host", "TEXT"),
        ("size_bytes", "INTEGER"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Collector expansion: Gmail
# ---------------------------------------------------------------------------
TABLES["gmail_participants"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("thread_id", "TEXT"),
        ("message_id", "TEXT NOT NULL"),
        ("role", "TEXT NOT NULL"),
        ("email", "TEXT NOT NULL"),
        ("name", "TEXT"),
    ],
}

TABLES["gmail_attachments"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("thread_id", "TEXT"),
        ("message_id", "TEXT NOT NULL"),
        ("filename", "TEXT NOT NULL"),
        ("mime_type", "TEXT"),
        ("size_bytes", "INTEGER"),
        ("attachment_id", "TEXT"),
    ],
}

TABLES["gmail_labels"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("thread_id", "TEXT"),
        ("message_id", "TEXT NOT NULL"),
        ("label_id", "TEXT NOT NULL"),
        ("label_name", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Collector expansion: Drive
# ---------------------------------------------------------------------------
TABLES["drive_files"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("source", "TEXT"),
        ("source_id", "TEXT"),
        ("name", "TEXT"),
        ("mime_type", "TEXT"),
        ("modified_time", "TEXT"),
        ("created_time", "TEXT"),
        ("owners", "TEXT"),
        ("last_modifying_user", "TEXT"),
        ("web_view_link", "TEXT"),
        ("shared", "INTEGER DEFAULT 0"),
        ("size", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Collector expansion: Contacts
# ---------------------------------------------------------------------------
TABLES["contacts"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("source", "TEXT"),
        ("source_id", "TEXT"),
        ("name", "TEXT"),
        ("first_name", "TEXT"),
        ("last_name", "TEXT"),
        ("primary_email", "TEXT"),
        ("emails", "TEXT"),
        ("phones", "TEXT"),
        ("organization", "TEXT"),
        ("title", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Collector expansion: Calendar
# ---------------------------------------------------------------------------
TABLES["calendar_attendees"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("event_id", "TEXT NOT NULL"),
        ("email", "TEXT NOT NULL"),
        ("display_name", "TEXT"),
        ("response_status", "TEXT"),
        ("organizer", "INTEGER DEFAULT 0"),
        ("self", "INTEGER DEFAULT 0"),
    ],
}

TABLES["calendar_recurrence_rules"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("event_id", "TEXT NOT NULL"),
        ("rrule", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Collector expansion: Chat
# ---------------------------------------------------------------------------
TABLES["chat_messages"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("message_name", "TEXT"),
        ("space_id", "TEXT"),
        ("space_name", "TEXT"),
        ("sender_id", "TEXT"),
        ("sender_name", "TEXT"),
        ("sender_email", "TEXT"),
        ("text", "TEXT"),
        ("create_time", "TEXT"),
        ("raw_json", "TEXT"),
        ("thread_id", "TEXT"),
        ("thread_reply_count", "INTEGER DEFAULT 0"),
        ("reaction_count", "INTEGER DEFAULT 0"),
        ("has_attachment", "INTEGER DEFAULT 0"),
        ("attachment_count", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT"),
    ],
}

TABLES["chat_reactions"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("message_id", "TEXT NOT NULL"),
        ("emoji", "TEXT NOT NULL"),
        ("user_id", "TEXT"),
        ("user_name", "TEXT"),
    ],
}

TABLES["chat_attachments"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("message_id", "TEXT NOT NULL"),
        ("name", "TEXT"),
        ("content_type", "TEXT"),
        ("source_uri", "TEXT"),
        ("thumbnail_uri", "TEXT"),
    ],
}

TABLES["chat_space_metadata"] = {
    "columns": [
        ("space_id", "TEXT PRIMARY KEY"),
        ("display_name", "TEXT"),
        ("space_type", "TEXT"),
        ("threaded", "INTEGER DEFAULT 0"),
        ("member_count", "INTEGER"),
        ("created_time", "TEXT"),
        ("last_synced", "TEXT"),
    ],
}

TABLES["chat_space_members"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("space_id", "TEXT NOT NULL"),
        ("member_id", "TEXT NOT NULL"),
        ("display_name", "TEXT"),
        ("email", "TEXT"),
        ("role", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Collector expansion: Xero
# ---------------------------------------------------------------------------
TABLES["xero_line_items"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("invoice_id", "TEXT NOT NULL"),
        ("description", "TEXT"),
        ("quantity", "REAL"),
        ("unit_amount", "REAL"),
        ("line_amount", "REAL"),
        ("tax_type", "TEXT"),
        ("tax_amount", "REAL"),
        ("account_code", "TEXT"),
        ("tracking_category", "TEXT"),
        ("tracking_option", "TEXT"),
    ],
}

TABLES["xero_contacts"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("email", "TEXT"),
        ("phone", "TEXT"),
        ("account_number", "TEXT"),
        ("tax_number", "TEXT"),
        ("is_supplier", "INTEGER DEFAULT 0"),
        ("is_customer", "INTEGER DEFAULT 0"),
        ("default_currency", "TEXT"),
        ("outstanding_balance", "REAL"),
        ("overdue_balance", "REAL"),
        ("last_synced", "TEXT"),
    ],
}

TABLES["xero_credit_notes"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("contact_id", "TEXT"),
        ("date", "TEXT"),
        ("status", "TEXT"),
        ("total", "REAL"),
        ("currency_code", "TEXT"),
        ("remaining_credit", "REAL"),
        ("allocated_amount", "REAL"),
        ("last_synced", "TEXT"),
    ],
}

TABLES["xero_bank_transactions"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("type", "TEXT"),
        ("contact_id", "TEXT"),
        ("date", "TEXT"),
        ("status", "TEXT"),
        ("total", "REAL"),
        ("currency_code", "TEXT"),
        ("reference", "TEXT"),
        ("last_synced", "TEXT"),
    ],
}

TABLES["xero_tax_rates"] = {
    "columns": [
        ("name", "TEXT PRIMARY KEY"),
        ("tax_type", "TEXT"),
        ("effective_rate", "REAL"),
        ("status", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Governance & safety
# ---------------------------------------------------------------------------
TABLES["governance_audit_log"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("timestamp", "TEXT"),
        ("action", "TEXT"),
        ("actor", "TEXT"),
        ("subject_identifier", "TEXT"),
        ("details", "TEXT"),
        ("ip_address", "TEXT"),
        ("created_at", "TEXT"),
    ],
}

TABLES["api_keys"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("key_hash", "TEXT NOT NULL"),
        ("name", "TEXT NOT NULL"),
        ("role", "TEXT NOT NULL CHECK(role IN ('viewer', 'operator', 'admin'))"),
        ("created_at", "TEXT NOT NULL"),
        ("expires_at", "TEXT"),
        ("last_used_at", "TEXT"),
        ("is_active", "INTEGER NOT NULL DEFAULT 1"),
        ("created_by", "TEXT"),
    ],
    "unique": [["key_hash"]],
    # Bump when constraints change to trigger rebuild of existing weak tables.
    "constraint_version": 1,
}

TABLES["subject_access_requests"] = {
    "columns": [
        ("request_id", "TEXT PRIMARY KEY"),
        ("subject_identifier", "TEXT"),
        ("request_type", "TEXT"),
        ("requested_at", "TEXT"),
        ("fulfilled_at", "TEXT"),
        ("status", "TEXT"),
        ("requested_by", "TEXT"),
        ("reason", "TEXT"),
        ("created_at", "TEXT"),
    ],
}

TABLES["write_context_v1"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY"),
        ("request_id", "TEXT"),
        ("actor", "TEXT"),
        ("source", "TEXT"),
        ("git_sha", "TEXT"),
    ],
}

TABLES["maintenance_mode_v1"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY"),
        ("flag", "INTEGER DEFAULT 0"),
        ("reason", "TEXT"),
        ("set_by", "TEXT"),
        ("set_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Safety: db_write_audit_v1 — audit trail of all DB writes.
# Previously defined as runtime DDL in lib/safety/migrations.py.
# Consolidated here in SCHEMA_VERSION 25 (C-002 PR3).
# ---------------------------------------------------------------------------
TABLES["db_write_audit_v1"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("at", "TEXT NOT NULL"),
        ("actor", "TEXT NOT NULL"),
        ("request_id", "TEXT NOT NULL"),
        ("source", "TEXT NOT NULL"),
        ("git_sha", "TEXT NOT NULL"),
        ("table_name", "TEXT NOT NULL"),
        ("op", "TEXT NOT NULL"),
        ("row_id", "TEXT NOT NULL"),
        ("before_json", "TEXT"),
        ("after_json", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Governance: retention_policies — retention policy definitions.
# Previously defined as runtime DDL in lib/governance/retention_engine.py.
# Consolidated here in SCHEMA_VERSION 25 (C-002 PR3).
# ---------------------------------------------------------------------------
TABLES["retention_policies"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("table_name", "TEXT NOT NULL"),
        ("retention_days", "INTEGER NOT NULL"),
        ("archive_before_delete", "INTEGER NOT NULL"),
        ("require_approval", "INTEGER NOT NULL"),
        ("min_rows_preserve", "INTEGER NOT NULL"),
        ("timestamp_column", "TEXT"),
        ("active", "INTEGER NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Governance: retention_audit — audit log of retention enforcement actions.
# Previously defined as runtime DDL in lib/governance/retention_engine.py.
# Consolidated here in SCHEMA_VERSION 25 (C-002 PR3).
# ---------------------------------------------------------------------------
TABLES["retention_audit"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("table_name", "TEXT NOT NULL"),
        ("action_type", "TEXT NOT NULL"),
        ("rows_affected", "INTEGER"),
        ("cutoff_date", "TEXT"),
        ("dry_run", "INTEGER NOT NULL"),
        ("executed_at", "TEXT NOT NULL"),
        ("error_message", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Governance: retention_runs — scheduler run history.
# Previously defined as runtime DDL in lib/governance/retention_scheduler.py.
# Consolidated here in SCHEMA_VERSION 25 (C-002 PR3).
# ---------------------------------------------------------------------------
TABLES["retention_runs"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("schedule", "TEXT NOT NULL"),
        ("started_at", "TEXT NOT NULL"),
        ("completed_at", "TEXT"),
        ("status", "TEXT NOT NULL"),
        ("total_rows_deleted", "INTEGER"),
        ("total_rows_archived", "INTEGER"),
        ("total_rows_anonymized", "INTEGER"),
        ("error_count", "INTEGER"),
        ("warning_count", "INTEGER"),
        ("duration_ms", "INTEGER"),
        ("dry_run", "INTEGER NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Governance: retention_locks — lock table for scheduler concurrency.
# Previously defined as runtime DDL in lib/governance/retention_scheduler.py.
# Consolidated here in SCHEMA_VERSION 25 (C-002 PR3).
# ---------------------------------------------------------------------------
TABLES["retention_locks"] = {
    "columns": [
        ("lock_key", "TEXT PRIMARY KEY"),
        ("acquired_at", "TEXT NOT NULL"),
        ("released_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Intelligence events
# ---------------------------------------------------------------------------
TABLES["intelligence_events"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("event_type", "TEXT"),
        ("severity", "TEXT"),
        ("entity_type", "TEXT"),
        ("entity_id", "TEXT"),
        ("event_data", "TEXT"),
        ("source_module", "TEXT"),
        ("created_at", "TEXT"),
        ("consumed_at", "TEXT"),
        ("consumer", "TEXT"),
    ],
}

TABLES["intelligence_events_archive"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("event_type", "TEXT"),
        ("severity", "TEXT"),
        ("entity_type", "TEXT"),
        ("entity_id", "TEXT"),
        ("event_data", "TEXT"),
        ("source_module", "TEXT"),
        ("created_at", "TEXT"),
        ("consumed_at", "TEXT"),
        ("consumer", "TEXT"),
        ("archived_at", "TEXT"),
    ],
}

TABLES["cost_snapshots"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("computed_at", "TEXT"),
        ("snapshot_type", "TEXT"),
        ("entity_id", "TEXT"),
        ("effort_score", "REAL"),
        ("efficiency_ratio", "REAL"),
        ("profitability_band", "TEXT"),
        ("cost_drivers", "TEXT"),
        ("data", "TEXT"),
        ("cycle_id", "TEXT"),
    ],
}

TABLES["pattern_snapshots"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("detected_at", "TEXT"),
        ("pattern_id", "TEXT"),
        ("pattern_name", "TEXT"),
        ("pattern_type", "TEXT"),
        ("severity", "TEXT"),
        ("confidence", "REAL"),
        ("entities_involved", "TEXT"),
        ("evidence", "TEXT"),
        ("cycle_id", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Digest system
# ---------------------------------------------------------------------------
TABLES["digest_history"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("user_id", "TEXT"),
        ("bucket", "TEXT"),
        ("digest_json", "TEXT"),
        ("item_count", "INTEGER"),
        ("sent_at", "TEXT"),
    ],
}

TABLES["digest_queue"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("user_id", "TEXT"),
        ("notification_id", "TEXT"),
        ("event_type", "TEXT"),
        ("category", "TEXT"),
        ("severity", "TEXT"),
        ("bucket", "TEXT"),
        ("processed", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT"),
        ("processed_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Decision options (from state_store)
# ---------------------------------------------------------------------------
TABLES["decision_options"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("decision_id", "TEXT"),
        ("label", "TEXT"),
        ("description", "TEXT"),
        ("data", "TEXT"),
        ("created_at", "TEXT"),
    ],
}

# =============================================================================
# Index Definitions
#
# Format: (index_name, table_name, column_expression, optional_where_clause)
# =============================================================================

INDEXES: list[tuple[str, str, str, str | None]] = [
    # Tasks
    ("idx_tasks_status", "tasks", "status", None),
    ("idx_tasks_due", "tasks", "due_date", None),
    ("idx_tasks_priority", "tasks", "priority DESC", None),
    ("idx_tasks_project_id", "tasks", "project_id", None),
    ("idx_tasks_client", "tasks", "client_id", None),
    ("idx_tasks_project_link_status", "tasks", "project_link_status", None),
    ("idx_tasks_client_link_status", "tasks", "client_link_status", None),
    ("idx_tasks_assignee", "tasks", "assignee_id", None),
    # Communications
    ("idx_communications_priority", "communications", "priority DESC", None),
    ("idx_communications_client", "communications", "client_id", None),
    ("idx_communications_processed", "communications", "processed", None),
    ("idx_communications_content_hash", "communications", "content_hash", None),
    ("idx_communications_from_email", "communications", "from_email", None),
    ("idx_communications_from_domain", "communications", "from_domain", None),
    # Projects
    ("idx_projects_brand", "projects", "brand_id", None),
    ("idx_projects_client", "projects", "client_id", None),
    ("idx_projects_status", "projects", "status", None),
    # Invoices
    ("idx_invoices_status", "invoices", "status", None),
    ("idx_invoices_due_at", "invoices", "due_at", None),
    ("idx_invoices_client", "invoices", "client_id", None),
    # Events
    ("idx_events_start", "events", "start_time", None),
    ("idx_events_start_at", "events", "start_at", None),
    # Commitments
    ("idx_commitments_source", "commitments", "source_id", None),
    ("idx_commitments_client", "commitments", "client_id", None),
    # Resolution queue
    (
        "idx_resolution_queue_pending",
        "resolution_queue",
        "entity_type, entity_id",
        "resolved_at IS NULL",
    ),
    # Pending actions
    ("idx_pending_actions_status", "pending_actions", "status", None),
    # V29 tables
    ("idx_issues_v29_client", "issues_v29", "client_id", None),
    ("idx_issues_v29_state", "issues_v29", "state", None),
    ("idx_issues_v29_severity", "issues_v29", "severity", None),
    ("idx_issues_v29_type", "issues_v29", "type", None),
    ("idx_issue_transitions_v29_issue", "issue_transitions_v29", "issue_id", None),
    ("idx_inbox_items_v29_state", "inbox_items_v29", "state", None),
    ("idx_inbox_items_v29_type", "inbox_items_v29", "type", None),
    ("idx_inbox_items_v29_client", "inbox_items_v29", "client_id", None),
    ("idx_signals_v29_client", "signals_v29", "client_id", None),
    ("idx_signals_v29_source", "signals_v29", "source, source_id", None),
    ("idx_signals_v29_observed", "signals_v29", "observed_at", None),
    ("idx_suppression_v29_key", "inbox_suppression_rules_v29", "suppression_key", None),
    ("idx_suppression_v29_expires", "inbox_suppression_rules_v29", "expires_at", None),
    # Legacy
    ("idx_issues_state", "issues", "state", None),
    ("idx_issues_priority", "issues", "priority", None),
    # System
    ("idx_notifications_created", "notifications", "created_at DESC", None),
    ("idx_actions_status", "actions", "status", None),
    ("idx_decisions_pending", "decisions", "approved", "approved IS NULL"),
    ("idx_time_debt_lane", "time_debt", "lane", None),
    ("idx_time_debt_unresolved", "time_debt", "resolved_at", "resolved_at IS NULL"),
    ("idx_client_projects_client", "client_projects", "client_id", None),
    ("idx_client_projects_project", "client_projects", "project_id", None),
    ("idx_client_health_log_client", "client_health_log", "client_id", None),
    ("idx_proposals_hierarchy", "proposals_v4", "client_id, brand_id, scope_level", None),
    ("idx_proposals_v4_status", "proposals_v4", "status", None),
    ("idx_proposals_v4_type", "proposals_v4", "proposal_type", None),
    ("idx_proposals_v4_score", "proposals_v4", "score DESC", None),
    ("idx_proposals_v4_primary", "proposals_v4", "primary_ref_type, primary_ref_id", None),
    ("idx_proposals_v4_scope_status", "proposals_v4", "scope_level, primary_ref_id, status", None),
    # couplings
    ("idx_couplings_anchor", "couplings", "anchor_ref_type, anchor_ref_id", None),
    ("idx_couplings_strength", "couplings", "strength DESC", None),
    ("idx_couplings_type", "couplings", "coupling_type", None),
    ("idx_signals_resolved", "signals", "status, resolved_at", None),
    ("idx_signals_type", "signals", "signal_type", None),
    ("idx_signals_entity", "signals", "entity_ref_type, entity_ref_id", None),
    ("idx_signals_status", "signals", "status", None),
    ("idx_signals_severity", "signals", "severity", None),
    ("idx_signals_detected", "signals", "detected_at", None),
    # governance_history
    ("idx_governance_history_created", "governance_history", "created_at DESC", None),
    ("idx_governance_history_decision", "governance_history", "decision_id", None),
    # decision_log
    ("idx_decision_log_issue", "decision_log", "issue_id", None),
    # handoffs
    ("idx_handoffs_issue", "handoffs", "issue_id", None),
    # signal_feedback
    ("idx_signal_feedback_signal", "signal_feedback", "signal_id", None),
    # Collector
    ("idx_asana_custom_fields_project", "asana_custom_fields", "project_id", None),
    ("idx_asana_custom_fields_task", "asana_custom_fields", "task_id", None),
    ("idx_asana_subtasks_parent_task", "asana_subtasks", "parent_task_id", None),
    ("idx_asana_sections_project", "asana_sections", "project_id", None),
    ("idx_asana_stories_task", "asana_stories", "task_id", None),
    ("idx_asana_task_dependencies_task", "asana_task_dependencies", "task_id", None),
    ("idx_asana_portfolios_owner", "asana_portfolios", "owner_id", None),
    ("idx_asana_goals_owner", "asana_goals", "owner_id", None),
    ("idx_asana_attachments_task", "asana_attachments", "task_id", None),
    ("idx_gmail_participants_message", "gmail_participants", "message_id", None),
    ("idx_gmail_attachments_message", "gmail_attachments", "message_id", None),
    ("idx_gmail_labels_message", "gmail_labels", "message_id", None),
    ("idx_calendar_attendees_event", "calendar_attendees", "event_id", None),
    ("idx_calendar_recurrence_event", "calendar_recurrence_rules", "event_id", None),
    ("idx_chat_reactions_message", "chat_reactions", "message_id", None),
    ("idx_chat_attachments_message", "chat_attachments", "message_id", None),
    ("idx_chat_space_members_space", "chat_space_members", "space_id", None),
    ("idx_xero_line_items_invoice", "xero_line_items", "invoice_id", None),
    ("idx_xero_contacts_name", "xero_contacts", "name", None),
    ("idx_contacts_email", "contacts", "primary_email", None),
    ("idx_xero_credit_notes_contact", "xero_credit_notes", "contact_id", None),
    ("idx_xero_bank_transactions_contact", "xero_bank_transactions", "contact_id", None),
    # signal_state
    ("idx_signal_state_active", "signal_state", "status, severity", "status = 'active'"),
    ("idx_signal_state_entity", "signal_state", "entity_type, entity_id", None),
    ("idx_signal_state_signal", "signal_state", "signal_id", None),
    # artifacts + entity_links
    ("idx_entity_links_artifact", "entity_links", "from_artifact_id", None),
    ("idx_entity_links_target", "entity_links", "to_entity_type, to_entity_id", None),
    ("idx_entity_links_status", "entity_links", "status", None),
    # Digest system
    ("idx_digest_queue_user_bucket", "digest_queue", "user_id, bucket, processed", None),
    ("idx_digest_history_user_bucket", "digest_history", "user_id, bucket", None),
    # issue_notes, watchers, identities (moved from runtime DDL in SCHEMA_VERSION 20)
    ("idx_issue_notes_issue", "issue_notes", "issue_id", None),
    ("idx_watchers_issue", "watchers", "issue_id", None),
    ("idx_watchers_triggered", "watchers", "triggered_at", "triggered_at IS NOT NULL"),
    ("idx_identities_canonical", "identities", "canonical_id", None),
    # drift detection
    ("idx_drift_time", "drift_alerts", "detected_at", None),
    # signal suppression
    ("idx_suppress_signal", "signal_suppressions", "signal_key", None),
    ("idx_suppress_entity", "signal_suppressions", "entity_type, entity_id", None),
    ("idx_suppress_active", "signal_suppressions", "is_active, expires_at", None),
    ("idx_dismiss_log_signal", "signal_dismiss_log", "signal_key", None),
    # engagement transitions
    ("idx_engagement_transitions_engagement_id", "engagement_transitions", "engagement_id", None),
    # api_keys
    ("idx_api_keys_key_hash", "api_keys", "key_hash", None),
    # items + item_history (consolidated from lib/store.py SCHEMA in v24)
    ("idx_items_status", "items", "status", None),
    ("idx_items_due", "items", "due", None),
    ("idx_items_client", "items", "client_id", None),
    ("idx_items_project", "items", "project_id", None),
    ("idx_items_owner", "items", "owner", None),
    ("idx_history_item", "item_history", "item_id", None),
    # clients indexes (consolidated from lib/store.py SCHEMA in v24)
    ("idx_clients_tier", "clients", "tier", None),
    ("idx_clients_health", "clients", "relationship_health", None),
    ("idx_clients_xero", "clients", "xero_contact_id", None),
    # people indexes (consolidated from lib/store.py SCHEMA in v24)
    ("idx_people_type", "people", "type", None),
    ("idx_people_email", "people", "email", None),
    # projects indexes (consolidated from lib/store.py SCHEMA in v24)
    ("idx_projects_health", "projects", "health", None),
    ("idx_projects_asana", "projects", "asana_project_id", None),
    # db_write_audit_v1 indexes (consolidated from lib/safety/migrations.py in v25)
    ("idx_audit_table_row", "db_write_audit_v1", "table_name, row_id", None),
    ("idx_audit_actor", "db_write_audit_v1", "actor", None),
    ("idx_audit_request", "db_write_audit_v1", "request_id", None),
    ("idx_audit_at", "db_write_audit_v1", "at", None),
    # retention_policies (consolidated from lib/governance/retention_engine.py in v25)
    ("idx_retention_policies_table", "retention_policies", "table_name", None),
    # entity_interactions (consolidated from lib/intelligence/entity_memory.py in v26)
    ("idx_interactions_entity", "entity_interactions", "entity_type, entity_id", None),
    ("idx_interactions_time", "entity_interactions", "created_at", None),
    # data_freshness (consolidated from lib/intelligence/data_freshness.py in v26)
    ("idx_freshness_source", "data_freshness", "source", None),
    # attention_events (consolidated from lib/intelligence/attention_tracking.py in v26)
    ("idx_attention_entity", "attention_events", "entity_type, entity_id", None),
    ("idx_attention_time", "attention_events", "created_at", None),
    # intelligence_audit (consolidated from lib/intelligence/audit_trail.py in v26)
    ("idx_audit_entity_intel", "intelligence_audit", "entity_type, entity_id", None),
    ("idx_audit_operation_intel", "intelligence_audit", "operation", None),
    # notification_queue (consolidated from lib/intelligence/notifications.py in v26)
    ("idx_notification_type", "notification_queue", "type", None),
    ("idx_notification_priority", "notification_queue", "priority", None),
    # signal_outcomes (consolidated from lib/intelligence/outcome_tracker.py in v26)
    ("idx_signal_outcomes_entity", "signal_outcomes", "entity_type, entity_id", None),
    ("idx_signal_outcomes_type", "signal_outcomes", "signal_type", None),
    # resolution_escalations (consolidated from lib/intelligence/auto_resolution.py in v26)
    ("idx_escalations_item", "resolution_escalations", "item_id", None),
    # asana_task_mappings (consolidated from lib/integrations/asana_sync.py in v26)
    ("idx_asana_mappings_gid", "asana_task_mappings", "asana_gid", None),
    # sync_cursor (consolidated from lib/collectors/all_users_runner.py in v26)
    ("idx_sync_cursor_service", "sync_cursor", "service", None),
    # decision_journal_log (consolidated from lib/intelligence/decision_journal.py)
    ("idx_dj_entity", "decision_journal_log", "entity_type, entity_id", None),
    ("idx_dj_type", "decision_journal_log", "decision_type", None),
    ("idx_dj_time", "decision_journal_log", "created_at", None),
    # audit_events (consolidated from lib/audit/__init__.py)
    ("idx_audit_entity", "audit_events", "entity_type, entity_id", None),
    ("idx_audit_type", "audit_events", "event_type", None),
    ("idx_audit_timestamp", "audit_events", "timestamp", None),
]

# ---------------------------------------------------------------------------
# Cross-entity linking tables (intelligence layer)
# ---------------------------------------------------------------------------

TABLES["signal_state"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("signal_id", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("severity", "TEXT NOT NULL"),
        ("original_severity", "TEXT NOT NULL"),
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("evidence_json", "TEXT"),
        ("first_detected_at", "TEXT NOT NULL"),
        ("last_evaluated_at", "TEXT NOT NULL"),
        ("escalated_at", "TEXT"),
        ("cleared_at", "TEXT"),
        ("acknowledged_at", "TEXT"),
        ("evaluation_count", "INTEGER DEFAULT 1"),
    ],
    "unique": [("signal_id", "entity_type", "entity_id", "status")],
}

TABLES["artifacts"] = {
    "columns": [
        ("artifact_id", "TEXT PRIMARY KEY"),
        ("type", "TEXT NOT NULL"),
        ("source", "TEXT"),
        ("occurred_at", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

TABLES["entity_links"] = {
    "columns": [
        ("link_id", "TEXT PRIMARY KEY"),
        ("from_artifact_id", "TEXT"),
        ("to_entity_type", "TEXT NOT NULL"),
        ("to_entity_id", "TEXT NOT NULL"),
        ("method", "TEXT"),
        ("confidence", "REAL DEFAULT 1.0"),
        ("confidence_reasons", "TEXT DEFAULT '[]'"),
        ("status", "TEXT NOT NULL DEFAULT 'proposed'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("confirmed_by", "TEXT"),
        ("confirmed_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# §15b Detection System: detection_findings
# Main findings table -- stores detector outputs with lifecycle tracking
# ---------------------------------------------------------------------------
TABLES["detection_findings"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("detector", "TEXT NOT NULL"),
        ("finding_type", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("entity_name", "TEXT"),
        ("severity", "TEXT NOT NULL DEFAULT 'medium'"),
        ("severity_data", "TEXT"),
        ("adjacent_data", "TEXT"),
        ("related_findings", "TEXT"),
        ("first_detected_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("last_detected_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("resolved_at", "TEXT"),
        ("notified_at", "TEXT"),
        ("acknowledged_at", "TEXT"),
        ("suppressed_until", "TEXT"),
        ("suppressed_by", "TEXT"),
        ("cycle_id", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §15b Detection System: detection_findings_preview
# Identical schema to detection_findings -- used during dry-run week
# ---------------------------------------------------------------------------
TABLES["detection_findings_preview"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("detector", "TEXT NOT NULL"),
        ("finding_type", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("entity_name", "TEXT"),
        ("severity", "TEXT NOT NULL DEFAULT 'medium'"),
        ("severity_data", "TEXT"),
        ("adjacent_data", "TEXT"),
        ("related_findings", "TEXT"),
        ("first_detected_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("last_detected_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("resolved_at", "TEXT"),
        ("notified_at", "TEXT"),
        ("acknowledged_at", "TEXT"),
        ("suppressed_until", "TEXT"),
        ("suppressed_by", "TEXT"),
        ("cycle_id", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §15b Detection System: task_weight_rules
# Pattern-based weight derivation (keyword/project -> quick/standard/heavy)
# ---------------------------------------------------------------------------
TABLES["task_weight_rules"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("pattern", "TEXT NOT NULL"),
        ("field", "TEXT NOT NULL DEFAULT 'title'"),
        ("assigned_weight", "TEXT NOT NULL DEFAULT 'standard'"),
        ("weight_value", "REAL NOT NULL DEFAULT 1.0"),
        ("confidence", "REAL NOT NULL DEFAULT 0.5"),
        ("corrections_count", "INTEGER NOT NULL DEFAULT 0"),
        ("confirmations_count", "INTEGER NOT NULL DEFAULT 0"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# §15b Detection System: task_weight_overrides
# Per-task manual weight corrections
# ---------------------------------------------------------------------------
TABLES["task_weight_overrides"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("task_id", "TEXT NOT NULL"),
        ("weight_class", "TEXT NOT NULL"),
        ("weight_value", "REAL NOT NULL"),
        ("set_by", "TEXT NOT NULL DEFAULT 'user'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# V29: engagements
# ---------------------------------------------------------------------------
TABLES["engagements"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("client_id", "TEXT NOT NULL"),
        ("brand_id", "TEXT"),
        ("name", "TEXT NOT NULL"),
        ("type", "TEXT NOT NULL"),
        ("state", "TEXT NOT NULL DEFAULT 'planned'"),
        ("asana_project_gid", "TEXT"),
        ("asana_url", "TEXT"),
        ("started_at", "TEXT"),
        ("completed_at", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# V29: engagement_transitions
# ---------------------------------------------------------------------------
TABLES["engagement_transitions"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("engagement_id", "TEXT NOT NULL"),
        ("from_state", "TEXT NOT NULL"),
        ("to_state", "TEXT NOT NULL"),
        ("trigger", "TEXT"),
        ("actor", "TEXT"),
        ("note", "TEXT"),
        ("transitioned_at", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# V30: notification_mutes (GAP-10-06)
# ---------------------------------------------------------------------------
TABLES["notification_mutes"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("mute_until", "TEXT NOT NULL"),
        ("mute_reason", "TEXT"),
        ("muted_by", "TEXT DEFAULT 'system'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# V30: notification_analytics (GAP-10-07)
# ---------------------------------------------------------------------------
TABLES["notification_analytics"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("notification_id", "TEXT NOT NULL"),
        ("channel", "TEXT NOT NULL"),
        ("outcome", "TEXT NOT NULL DEFAULT 'delivered'"),
        ("delivered_at", "TEXT"),
        ("opened_at", "TEXT"),
        ("acted_on_at", "TEXT"),
        ("failed_reason", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# V19: saved_filters (D3 from closure-audit, SF-1)
# Persists user-defined filter presets for the UI SavedFilterSelector component.
# ---------------------------------------------------------------------------
TABLES["saved_filters"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("filters", "TEXT NOT NULL"),
        ("created_by", "TEXT DEFAULT 'system'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Couplings (v4 intelligence layer — intersection engine)
# Columns match coupling_service.py read/write paths.
# ---------------------------------------------------------------------------
TABLES["couplings"] = {
    "columns": [
        ("coupling_id", "TEXT PRIMARY KEY"),
        ("anchor_ref_type", "TEXT NOT NULL"),
        ("anchor_ref_id", "TEXT NOT NULL"),
        ("entity_refs", "TEXT NOT NULL"),
        ("coupling_type", "TEXT NOT NULL"),
        ("strength", "REAL NOT NULL"),
        ("why", "TEXT NOT NULL"),
        ("investigation_path", "TEXT NOT NULL"),
        ("confidence", "REAL NOT NULL"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Drift detection (intelligence layer)
# Columns match lib/intelligence/drift_detection.py read/write paths.
# ---------------------------------------------------------------------------
TABLES["drift_baselines"] = {
    "columns": [
        ("metric_name", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("mean_value", "REAL NOT NULL"),
        ("stddev_value", "REAL NOT NULL"),
        ("sample_count", "INTEGER NOT NULL"),
        ("last_updated", "TEXT NOT NULL"),
    ],
    "primary_key": ["metric_name", "entity_type", "entity_id"],
}

TABLES["drift_alerts"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("metric_name", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("current_value", "REAL NOT NULL"),
        ("baseline_mean", "REAL NOT NULL"),
        ("baseline_stddev", "REAL NOT NULL"),
        ("deviation_sigma", "REAL NOT NULL"),
        ("direction", "TEXT NOT NULL"),
        ("severity", "TEXT NOT NULL"),
        ("detected_at", "TEXT NOT NULL"),
        ("explanation", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Signal suppression (intelligence layer)
# Columns match lib/intelligence/signal_suppression.py read/write paths.
# ---------------------------------------------------------------------------
TABLES["signal_suppressions"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("signal_key", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("reason", "TEXT NOT NULL"),
        ("suppressed_at", "TEXT NOT NULL"),
        ("expires_at", "TEXT NOT NULL"),
        ("dismiss_count", "INTEGER DEFAULT 1"),
        ("is_active", "INTEGER DEFAULT 1"),
    ],
}

TABLES["signal_dismiss_log"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("signal_key", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("event_type", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Engagement transitions (ui_spec_v21 lifecycle audit trail)
# Columns match lib/ui_spec_v21/engagement_lifecycle.py read/write paths.
# ---------------------------------------------------------------------------
TABLES["engagement_transitions"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("engagement_id", "TEXT NOT NULL"),
        ("from_state", "TEXT NOT NULL"),
        ("to_state", "TEXT NOT NULL"),
        ("trigger", "TEXT"),
        ("actor", "TEXT"),
        ("note", "TEXT"),
        ("transitioned_at", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Issue notes — notes attached to control-room issues.
# Previously created at runtime in api/server.py (schema-ownership defect).
# Moved here so schema_engine owns the table definition.
# ---------------------------------------------------------------------------
TABLES["issue_notes"] = {
    "columns": [
        ("note_id", "TEXT PRIMARY KEY"),
        ("issue_id", "TEXT NOT NULL"),
        ("text", "TEXT NOT NULL"),
        ("actor", "TEXT"),
        ("created_at", "TEXT DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Watchers — alerts/watches on control-room issues.
# Previously created at runtime in api/server.py (schema-ownership defect).
# Moved here so schema_engine owns the table definition.
# ---------------------------------------------------------------------------
TABLES["watchers"] = {
    "columns": [
        ("watcher_id", "TEXT PRIMARY KEY"),
        ("issue_id", "TEXT NOT NULL"),
        ("watch_type", "TEXT NOT NULL"),
        ("params", "TEXT NOT NULL DEFAULT '{}'"),
        ("active", "INTEGER NOT NULL DEFAULT 1"),
        ("next_check_at", "TEXT NOT NULL"),
        ("last_checked_at", "TEXT"),
        ("triggered_at", "TEXT"),
        ("trigger_count", "INTEGER NOT NULL DEFAULT 0"),
        # Columns used by dismiss_watcher and snooze_watcher endpoints
        ("dismissed_at", "TEXT"),
        ("dismissed_by", "TEXT"),
        ("snoozed_until", "TEXT"),
        ("snoozed_by", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Identities — identity resolution records for data quality (Fix tab).
# Previously created at runtime in api/server.py (schema-ownership defect).
# Moved here so schema_engine owns the table definition.
# ---------------------------------------------------------------------------
TABLES["identities"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("display_name", "TEXT"),
        ("source", "TEXT"),
        ("canonical_id", "TEXT"),
        ("confidence_score", "REAL DEFAULT 0.5"),
    ],
}

# ---------------------------------------------------------------------------
# Governance: governance_history — audit trail for governance decisions.
# Previously phantom-referenced in api/server.py without a schema definition.
# ---------------------------------------------------------------------------
TABLES["governance_history"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("decision_id", "TEXT"),
        ("action", "TEXT NOT NULL"),
        ("type", "TEXT"),
        ("target_id", "TEXT"),
        ("processed_by", "TEXT"),
        ("side_effects", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# V4 Signal Service: signal_definitions — registered signal types.
# Previously created at runtime in lib/v4/signal_service.py.
# ---------------------------------------------------------------------------
TABLES["signal_definitions"] = {
    "columns": [
        ("signal_type", "TEXT PRIMARY KEY"),
        ("description", "TEXT NOT NULL"),
        ("category", "TEXT NOT NULL"),
        ("required_evidence_types", "TEXT NOT NULL"),
        ("formula_version", "TEXT NOT NULL"),
        ("min_link_confidence", "REAL NOT NULL DEFAULT 0.7"),
        ("min_interpretation_confidence", "REAL NOT NULL DEFAULT 0.6"),
        ("priority_weight", "REAL NOT NULL DEFAULT 1.0"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# V4 Signal Service: detector_versions — versioned detection algorithms.
# Previously created at runtime in lib/v4/signal_service.py.
# ---------------------------------------------------------------------------
TABLES["detector_versions"] = {
    "columns": [
        ("detector_id", "TEXT NOT NULL"),
        ("version", "TEXT NOT NULL"),
        ("description", "TEXT"),
        ("parameters", "TEXT NOT NULL"),
        ("released_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
    "unique": [("detector_id", "version")],
}

# ---------------------------------------------------------------------------
# V4 Signal Service: detector_runs — audit trail of detector executions.
# Previously created at runtime in lib/v4/signal_service.py.
# ---------------------------------------------------------------------------
TABLES["detector_runs"] = {
    "columns": [
        ("run_id", "TEXT PRIMARY KEY"),
        ("detector_id", "TEXT NOT NULL"),
        ("detector_version", "TEXT NOT NULL"),
        ("scope", "TEXT NOT NULL"),
        ("inputs_hash", "TEXT NOT NULL"),
        ("ran_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
        ("duration_ms", "INTEGER"),
        ("output_counts", "TEXT NOT NULL"),
        ("status", "TEXT NOT NULL DEFAULT 'completed'"),
    ],
}

# ---------------------------------------------------------------------------
# V4 Signal Service: signal_feedback — user feedback on signals.
# Previously created at runtime in lib/v4/signal_service.py.
# ---------------------------------------------------------------------------
TABLES["signal_feedback"] = {
    "columns": [
        ("feedback_id", "TEXT PRIMARY KEY"),
        ("signal_id", "TEXT NOT NULL"),
        ("feedback_type", "TEXT NOT NULL"),
        ("actor", "TEXT NOT NULL"),
        ("note", "TEXT"),
        ("reason", "TEXT"),
        ("snooze_until", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# V4 Issue Service: issue_signals — links issues to signals.
# Previously created at runtime in lib/v4/issue_service.py.
# ---------------------------------------------------------------------------
TABLES["issue_signals"] = {
    "columns": [
        ("issue_id", "TEXT NOT NULL"),
        ("signal_id", "TEXT NOT NULL"),
        ("attached_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
    "unique": [("issue_id", "signal_id")],
}

# ---------------------------------------------------------------------------
# V4 Issue Service: issue_evidence — links issues to evidence excerpts.
# Previously created at runtime in lib/v4/issue_service.py.
# ---------------------------------------------------------------------------
TABLES["issue_evidence"] = {
    "columns": [
        ("issue_id", "TEXT NOT NULL"),
        ("excerpt_id", "TEXT NOT NULL"),
        ("attached_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
    "unique": [("issue_id", "excerpt_id")],
}

# ---------------------------------------------------------------------------
# V4 Issue Service: decision_log — audit trail of issue decisions.
# Previously created at runtime in lib/v4/issue_service.py.
# ---------------------------------------------------------------------------
TABLES["decision_log"] = {
    "columns": [
        ("decision_id", "TEXT PRIMARY KEY"),
        ("issue_id", "TEXT NOT NULL"),
        ("actor", "TEXT NOT NULL"),
        ("decision_type", "TEXT NOT NULL"),
        ("note", "TEXT"),
        ("evidence_excerpt_ids", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# V4 Issue Service: handoffs — delegated work items.
# Previously created at runtime in lib/v4/issue_service.py.
# ---------------------------------------------------------------------------
TABLES["handoffs"] = {
    "columns": [
        ("handoff_id", "TEXT PRIMARY KEY"),
        ("issue_id", "TEXT NOT NULL"),
        ("from_person_id", "TEXT NOT NULL"),
        ("to_person_id", "TEXT NOT NULL"),
        ("what_is_expected", "TEXT NOT NULL"),
        ("due_at", "TEXT"),
        ("done_definition", "TEXT NOT NULL"),
        ("state", "TEXT NOT NULL DEFAULT 'proposed'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Outbox Pattern: side_effect_outbox — durable intent recording before
# external side effects.  Previously defined as runtime DDL in lib/outbox.py.
# ---------------------------------------------------------------------------
TABLES["side_effect_outbox"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("idempotency_key", "TEXT UNIQUE"),
        ("handler", "TEXT NOT NULL"),
        ("action", "TEXT NOT NULL"),
        ("payload", "TEXT NOT NULL"),
        ("status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("external_resource_id", "TEXT"),
        ("error", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
        ("fulfilled_at", "TEXT"),
        ("attempts", "INTEGER NOT NULL DEFAULT 0"),
    ],
}

# ---------------------------------------------------------------------------
# Outbox Pattern: idempotency_keys — persistent idempotency key → action_id
# mapping.  Previously defined as runtime DDL in lib/outbox.py.
# ---------------------------------------------------------------------------
TABLES["idempotency_keys"] = {
    "columns": [
        ("key", "TEXT PRIMARY KEY"),
        ("action_id", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# §Core: items — action items / tasks tracked by the command center.
# Previously defined as runtime DDL in lib/store.py SCHEMA constant.
# Consolidated here in SCHEMA_VERSION 24 (C-002 PR2).
# ---------------------------------------------------------------------------
TABLES["items"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("what", "TEXT NOT NULL"),
        ("status", "TEXT NOT NULL"),
        ("owner", "TEXT NOT NULL"),
        ("owner_id", "TEXT"),
        ("counterparty", "TEXT"),
        ("counterparty_id", "TEXT"),
        ("due", "TEXT"),
        ("waiting_since", "TEXT"),
        ("client_id", "TEXT"),
        ("project_id", "TEXT"),
        ("context_snapshot_json", "TEXT"),
        ("stakes", "TEXT"),
        ("history_context", "TEXT"),
        ("source_type", "TEXT"),
        ("source_ref", "TEXT"),
        ("captured_at", "TEXT NOT NULL"),
        ("resolution_outcome", "TEXT"),
        ("resolution_notes", "TEXT"),
        ("resolved_at", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# §Core: item_history — append-only audit log for item changes.
# Previously defined as runtime DDL in lib/store.py SCHEMA constant.
# Consolidated here in SCHEMA_VERSION 24 (C-002 PR2).
# ---------------------------------------------------------------------------
TABLES["item_history"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("item_id", "TEXT NOT NULL"),
        ("timestamp", "TEXT NOT NULL"),
        ("change", "TEXT NOT NULL"),
        ("changed_by", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Intelligence: entity_interactions — tracks interactions with entities.
# Previously created at runtime in lib/intelligence/entity_memory.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["entity_interactions"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("interaction_type", "TEXT NOT NULL"),
        ("summary", "TEXT NOT NULL"),
        ("details_json", "TEXT DEFAULT '{}'"),
        ("created_at", "TEXT NOT NULL"),
        ("source", "TEXT DEFAULT 'system'"),
    ],
}

# ---------------------------------------------------------------------------
# Intelligence: data_freshness — tracks data collection recency per entity.
# Previously created at runtime in lib/intelligence/data_freshness.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["data_freshness"] = {
    "columns": [
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("source", "TEXT NOT NULL"),
        ("last_collected_at", "TEXT NOT NULL"),
        ("record_count", "INTEGER DEFAULT 0"),
    ],
    "primary_key": ["entity_type", "entity_id", "source"],
}

# ---------------------------------------------------------------------------
# Intelligence: attention_events — tracks attention/focus time per entity.
# Previously created at runtime in lib/intelligence/attention_tracking.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["attention_events"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("event_type", "TEXT NOT NULL"),
        ("duration_minutes", "REAL DEFAULT 0"),
        ("notes", "TEXT DEFAULT ''"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Intelligence: intelligence_audit — audit trail for intelligence operations.
# Previously created at runtime in lib/intelligence/audit_trail.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["intelligence_audit"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("operation", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("inputs_json", "TEXT DEFAULT '{}'"),
        ("outputs_json", "TEXT DEFAULT '{}'"),
        ("duration_ms", "REAL DEFAULT 0"),
        ("created_at", "TEXT NOT NULL"),
        ("status", "TEXT DEFAULT 'success'"),
        ("error_message", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Intelligence: notification_queue — queued notifications for delivery.
# Previously created at runtime in lib/intelligence/notifications.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["notification_queue"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        ("notification_id", "TEXT UNIQUE NOT NULL"),
        ("type", "TEXT NOT NULL"),
        ("priority", "TEXT NOT NULL"),
        ("title", "TEXT NOT NULL"),
        ("body", "TEXT"),
        ("entity_type", "TEXT"),
        ("entity_id", "TEXT"),
        ("data_json", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
        ("delivered_at", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Intelligence: signal_outcomes — tracks how signals resolved over time.
# Previously created at runtime in lib/intelligence/outcome_tracker.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["signal_outcomes"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("signal_key", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("signal_type", "TEXT NOT NULL"),
        ("detected_at", "TEXT NOT NULL"),
        ("cleared_at", "TEXT NOT NULL"),
        ("duration_days", "REAL NOT NULL"),
        ("health_before", "REAL"),
        ("health_after", "REAL"),
        ("health_improved", "INTEGER"),
        ("actions_taken", "TEXT"),
        ("resolution_type", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Intelligence: resolution_escalations — escalated items needing human review.
# Previously created at runtime in lib/intelligence/auto_resolution.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["resolution_escalations"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("item_id", "TEXT NOT NULL"),
        ("issue_type", "TEXT"),
        ("reason", "TEXT NOT NULL"),
        ("entity_type", "TEXT"),
        ("entity_id", "TEXT"),
        ("escalated_at", "TEXT NOT NULL"),
        ("resolved_at", "TEXT"),
        ("resolved_by", "TEXT"),
        ("resolution_notes", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Integrations: asana_task_mappings — maps local tasks to Asana GIDs.
# Previously created at runtime in lib/integrations/asana_sync.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["asana_task_mappings"] = {
    "columns": [
        ("local_id", "TEXT PRIMARY KEY"),
        ("asana_gid", "TEXT NOT NULL UNIQUE"),
        ("project_gid", "TEXT"),
        ("local_updated_at", "TEXT"),
        ("asana_updated_at", "TEXT"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Collectors: sync_cursor — tracks collection cursor state per service/subject.
# Previously created at runtime in lib/collectors/all_users_runner.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["sync_cursor"] = {
    "columns": [
        ("service", "TEXT NOT NULL"),
        ("subject", "TEXT NOT NULL"),
        ("key", "TEXT NOT NULL"),
        ("value", "TEXT"),
        ("updated_at", "TEXT"),
    ],
    "primary_key": ["service", "subject", "key"],
}

# ---------------------------------------------------------------------------
# Collectors: subject_blocklist — subjects blocked from collection.
# Previously created at runtime in lib/collectors/all_users_runner.py.
# Consolidated here in SCHEMA_VERSION 26 (C-002 PR4).
# ---------------------------------------------------------------------------
TABLES["subject_blocklist"] = {
    "columns": [
        ("subject", "TEXT PRIMARY KEY"),
        ("reason", "TEXT NOT NULL"),
        ("error_detail", "TEXT"),
        ("updated_at", "TEXT NOT NULL"),
    ],
}

# ---------------------------------------------------------------------------
# Decision Journal: decision_journal_log — general-purpose decision audit trail.
# Used by lib/intelligence/decision_journal.py (may target a separate DB file).
# Not to be confused with decision_log (V4 Issue Service decisions above).
# ---------------------------------------------------------------------------
TABLES["decision_journal_log"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("decision_type", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("action_taken", "TEXT NOT NULL"),
        ("context_json", "TEXT DEFAULT '{}'"),
        ("outcome", "TEXT"),
        ("outcome_score", "REAL"),
        ("created_at", "TEXT NOT NULL"),
        ("source", "TEXT DEFAULT 'system'"),
    ],
}

# ---------------------------------------------------------------------------
# Audit Events: audit_events — append-only event log for state reconstruction.
# Previously created at runtime in lib/audit/__init__.py.
# ---------------------------------------------------------------------------
TABLES["audit_events"] = {
    "columns": [
        ("event_id", "TEXT PRIMARY KEY"),
        ("event_type", "TEXT NOT NULL"),
        ("entity_type", "TEXT NOT NULL"),
        ("entity_id", "TEXT NOT NULL"),
        ("payload", "TEXT NOT NULL"),
        ("timestamp", "TEXT NOT NULL"),
        ("request_id", "TEXT"),
        ("trace_id", "TEXT"),
        ("actor", "TEXT"),
        ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
    ],
}

# ---------------------------------------------------------------------------
# Org Settings: org_settings — organization-level config (timezone, currency).
# Previously created at runtime in lib/ui_spec_v21/org_settings.py.
# ---------------------------------------------------------------------------
TABLES["org_settings"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY CHECK (id = 1)"),
        ("timezone", "TEXT NOT NULL DEFAULT 'Asia/Dubai'"),
        ("base_currency", "TEXT NOT NULL DEFAULT 'AED'"),
        ("finance_calc_version", "TEXT NOT NULL DEFAULT 'v1'"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
    ],
}

# =============================================================================
# Data Migrations — Copy data between columns after schema convergence
#
# Format: (table, target_column, source_expression, where_condition)
# Executed as: UPDATE table SET target_column = source_expression WHERE condition
# Idempotent — only updates rows where target is NULL and source is NOT NULL.
# =============================================================================

# =============================================================================
# Views — Cross-entity views for the intelligence/query layer.
#
# Previously fixture-only (tests/fixtures/fixture_db.py).
# Promoted to canonical schema so production and test DBs share the same views.
# schema_engine creates these after all tables exist.
# =============================================================================

VIEWS: dict[str, str] = OrderedDict()

VIEWS["v_task_with_client"] = """
CREATE VIEW IF NOT EXISTS v_task_with_client AS
SELECT
    t.id as task_id,
    t.title as task_title,
    t.status as task_status,
    t.priority as task_priority,
    t.due_date,
    t.assignee,
    t.project_id,
    p.name as project_name,
    COALESCE(t.client_id, p.client_id) as client_id,
    c.name as client_name,
    t.created_at
FROM tasks t
LEFT JOIN projects p ON t.project_id = p.id
LEFT JOIN clients c ON COALESCE(t.client_id, p.client_id) = c.id
"""

VIEWS["v_client_operational_profile"] = """
CREATE VIEW IF NOT EXISTS v_client_operational_profile AS
SELECT
    c.id as client_id,
    c.name as client_name,
    c.tier as client_tier,
    c.relationship_health,
    (SELECT COUNT(*) FROM projects p WHERE p.client_id = c.id) as project_count,
    (SELECT COUNT(*) FROM tasks t JOIN projects p ON t.project_id = p.id
     WHERE p.client_id = c.id) as total_tasks,
    (SELECT COUNT(*) FROM tasks t JOIN projects p ON t.project_id = p.id
     WHERE p.client_id = c.id
     AND t.status NOT IN ('done', 'complete', 'completed')) as active_tasks,
    (SELECT COUNT(*) FROM invoices i WHERE i.client_id = c.id) as invoice_count,
    (SELECT COALESCE(SUM(i.amount), 0) FROM invoices i
     WHERE i.client_id = c.id) as total_invoiced,
    (SELECT COALESCE(SUM(i.amount), 0) FROM invoices i
     WHERE i.client_id = c.id AND i.status = 'paid') as total_paid,
    (SELECT COALESCE(SUM(i.amount), 0) FROM invoices i
     WHERE i.client_id = c.id AND i.status != 'paid') as total_outstanding,
    0 as financial_ar_total,
    0 as financial_ar_overdue,
    0 as ytd_revenue,
    (SELECT COUNT(*) FROM entity_links el
     WHERE el.to_entity_type = 'client'
     AND el.to_entity_id = c.id) as entity_links_count
FROM clients c
"""

VIEWS["v_project_operational_state"] = """
CREATE VIEW IF NOT EXISTS v_project_operational_state AS
SELECT
    p.id as project_id,
    p.name as project_name,
    p.status as project_status,
    p.client_id,
    c.name as client_name,
    (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) as total_tasks,
    (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
     AND t.status NOT IN ('done', 'complete', 'completed')) as open_tasks,
    (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
     AND t.status IN ('done', 'complete', 'completed')) as completed_tasks,
    (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
     AND t.due_date IS NOT NULL AND t.due_date < date('now')
     AND t.status NOT IN ('done', 'complete', 'completed')) as overdue_tasks,
    (SELECT COUNT(DISTINCT t.assignee) FROM tasks t
     WHERE t.project_id = p.id AND t.assignee IS NOT NULL)
     as assigned_people_count,
    CASE
        WHEN (SELECT COUNT(*) FROM tasks t
              WHERE t.project_id = p.id) = 0 THEN 0
        ELSE ROUND(100.0 *
             (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
              AND t.status IN ('done', 'complete', 'completed')) /
             (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id), 1)
    END as completion_rate_pct
FROM projects p
LEFT JOIN clients c ON p.client_id = c.id
"""

VIEWS["v_person_load_profile"] = """
CREATE VIEW IF NOT EXISTS v_person_load_profile AS
SELECT
    ppl.id as person_id,
    ppl.name as person_name,
    ppl.email as person_email,
    ppl.type as role,
    (SELECT COUNT(*) FROM tasks t
     WHERE LOWER(t.assignee) = LOWER(ppl.name)) as assigned_tasks,
    (SELECT COUNT(*) FROM tasks t
     WHERE LOWER(t.assignee) = LOWER(ppl.name)
     AND t.status NOT IN ('done', 'complete', 'completed')) as active_tasks,
    (SELECT COUNT(DISTINCT t.project_id) FROM tasks t
     WHERE LOWER(t.assignee) = LOWER(ppl.name)) as project_count,
    (SELECT COUNT(*) FROM entity_links el
     WHERE el.to_entity_type = 'person'
     AND el.to_entity_id = ppl.id) as communication_links
FROM people ppl
"""

VIEWS["v_communication_client_link"] = """
CREATE VIEW IF NOT EXISTS v_communication_client_link AS
SELECT
    a.artifact_id,
    a.type as artifact_type,
    a.source as source_system,
    a.occurred_at,
    el.to_entity_id as client_id,
    c.name as client_name,
    el.confidence,
    el.method as link_method
FROM artifacts a
JOIN entity_links el ON el.from_artifact_id = a.artifact_id
JOIN clients c ON el.to_entity_id = c.id
WHERE el.to_entity_type = 'client'
"""

VIEWS["v_invoice_client_project"] = """
CREATE VIEW IF NOT EXISTS v_invoice_client_project AS
SELECT
    i.id as invoice_id,
    i.external_id,
    i.client_id,
    c.name as client_name,
    i.amount,
    i.currency,
    i.status as invoice_status,
    i.issue_date,
    i.due_date,
    i.aging_bucket,
    (SELECT COUNT(*) FROM projects p
     WHERE p.client_id = i.client_id) as client_project_count,
    (SELECT COUNT(*) FROM tasks t JOIN projects p ON t.project_id = p.id
     WHERE p.client_id = i.client_id
     AND t.status NOT IN ('done', 'complete', 'completed'))
     as client_active_tasks
FROM invoices i
LEFT JOIN clients c ON i.client_id = c.id
"""

DATA_MIGRATIONS: list[tuple[str, str, str, str]] = [
    # Invoices: copy legacy column data to §12 column names
    ("invoices", "due_date", "due_at", "due_date IS NULL AND due_at IS NOT NULL"),
    ("invoices", "paid_date", "paid_at", "paid_date IS NULL AND paid_at IS NOT NULL"),
    ("invoices", "amount", "total", "amount IS NULL AND total IS NOT NULL"),
    ("invoices", "issue_date", "issued_at", "issue_date IS NULL AND issued_at IS NOT NULL"),
]
