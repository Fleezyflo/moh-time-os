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
SCHEMA_VERSION = 12

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
        ("detector_id", "TEXT"),
        ("signal_type", "TEXT NOT NULL"),
        ("entity_ref_type", "TEXT"),
        ("entity_ref_id", "TEXT"),
        ("value", "TEXT"),
        ("detected_at", "TEXT"),
        ("status", "TEXT"),
        ("resolved_at", "TEXT"),
        ("resolution", "TEXT"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# ---------------------------------------------------------------------------
# Legacy: proposals_v4
# ---------------------------------------------------------------------------
TABLES["proposals_v4"] = {
    "columns": [
        ("id", "TEXT PRIMARY KEY"),
        ("type", "TEXT"),
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
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
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
        ("message_id", "TEXT NOT NULL"),
        ("role", "TEXT NOT NULL"),
        ("email", "TEXT NOT NULL"),
        ("name", "TEXT"),
    ],
}

TABLES["gmail_attachments"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
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
        ("message_id", "TEXT NOT NULL"),
        ("label_id", "TEXT NOT NULL"),
        ("label_name", "TEXT"),
    ],
}

# ---------------------------------------------------------------------------
# Collector expansion: Calendar
# ---------------------------------------------------------------------------
TABLES["calendar_attendees"] = {
    "columns": [
        ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
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
        ("space_id", "TEXT"),
        ("sender_id", "TEXT"),
        ("sender_name", "TEXT"),
        ("text", "TEXT"),
        ("thread_id", "TEXT"),
        ("thread_reply_count", "INTEGER DEFAULT 0"),
        ("reaction_count", "INTEGER DEFAULT 0"),
        ("has_attachment", "INTEGER DEFAULT 0"),
        ("attachment_count", "INTEGER DEFAULT 0"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
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
        ("key_hash", "TEXT"),
        ("name", "TEXT"),
        ("role", "TEXT"),
        ("created_at", "TEXT"),
        ("expires_at", "TEXT"),
        ("last_used_at", "TEXT"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("created_by", "TEXT"),
    ],
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
    ("idx_signals_resolved", "signals", "status, resolved_at", None),
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
    ("idx_xero_credit_notes_contact", "xero_credit_notes", "contact_id", None),
    ("idx_xero_bank_transactions_contact", "xero_bank_transactions", "contact_id", None),
    # signal_state
    ("idx_signal_state_active", "signal_state", "status, severity", "status = 'active'"),
    ("idx_signal_state_entity", "signal_state", "entity_type, entity_id", None),
    ("idx_signal_state_signal", "signal_state", "signal_id", None),
    # artifacts + entity_links
    ("idx_entity_links_artifact", "entity_links", "from_artifact_id", None),
    ("idx_entity_links_target", "entity_links", "to_entity_type, to_entity_id", None),
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
        ("id", "INTEGER PRIMARY KEY"),
        ("from_artifact_id", "TEXT"),
        ("to_entity_type", "TEXT NOT NULL"),
        ("to_entity_id", "TEXT NOT NULL"),
        ("confidence", "REAL DEFAULT 1.0"),
        ("method", "TEXT DEFAULT 'system'"),
        ("created_at", "TEXT NOT NULL DEFAULT (datetime('now'))"),
    ],
}

# =============================================================================
# Data Migrations — Copy data between columns after schema convergence
#
# Format: (table, target_column, source_expression, where_condition)
# Executed as: UPDATE table SET target_column = source_expression WHERE condition
# Idempotent — only updates rows where target is NULL and source is NOT NULL.
# =============================================================================

DATA_MIGRATIONS: list[tuple[str, str, str, str]] = [
    # Invoices: copy legacy column data to §12 column names
    ("invoices", "due_date", "due_at", "due_date IS NULL AND due_at IS NOT NULL"),
    ("invoices", "paid_date", "paid_at", "paid_date IS NULL AND paid_at IS NOT NULL"),
    ("invoices", "amount", "total", "amount IS NULL AND total IS NOT NULL"),
    ("invoices", "issue_date", "issued_at", "issue_date IS NULL AND issued_at IS NOT NULL"),
]
