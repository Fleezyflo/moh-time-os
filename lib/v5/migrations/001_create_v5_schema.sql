-- Time OS V5 Database Schema
-- Created: 2025-01-27
-- Description: Complete V5 schema with signals, issues, and integrations

-- ============================================================================
-- MIGRATION TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS migrations (
    id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

-- ============================================================================
-- CORE ENTITIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. PEOPLE (Team and Contacts)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,

    -- Identity
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,

    -- Type
    person_type TEXT NOT NULL CHECK(person_type IN ('team', 'client_contact', 'vendor', 'other')) DEFAULT 'other',

    -- Team-specific
    role TEXT,
    department TEXT,
    is_active BOOLEAN DEFAULT TRUE,

    -- Client contact specific
    client_id TEXT,  -- FK added after clients table
    is_primary_contact BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_people_email ON people(email);
CREATE INDEX IF NOT EXISTS idx_people_type ON people(person_type);
CREATE INDEX IF NOT EXISTS idx_people_client ON people(client_id);

-- ----------------------------------------------------------------------------
-- 2. CLIENTS
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,

    -- Identity
    name TEXT NOT NULL,
    legal_name TEXT,
    xero_contact_id TEXT UNIQUE,

    -- Classification
    tier TEXT CHECK(tier IN ('A', 'B', 'C', 'unclassified')) DEFAULT 'unclassified',
    tier_reason TEXT,
    tier_updated_at TEXT,

    -- Commercial
    annual_revenue_target REAL DEFAULT 0,
    lifetime_revenue REAL DEFAULT 0,

    -- Relationship
    relationship_start_date TEXT,
    primary_contact_id TEXT REFERENCES people(id),
    account_lead_id TEXT REFERENCES people(id),

    -- Health (computed, cached)
    health_status TEXT CHECK(health_status IN ('healthy', 'cooling', 'at_risk', 'critical')) DEFAULT 'healthy',
    health_score REAL DEFAULT 100,
    health_updated_at TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_clients_tier ON clients(tier);
CREATE INDEX IF NOT EXISTS idx_clients_health ON clients(health_status);
CREATE INDEX IF NOT EXISTS idx_clients_xero ON clients(xero_contact_id);

-- Add FK from people to clients
-- (SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so this is enforced at app level)

-- ----------------------------------------------------------------------------
-- 3. BRANDS
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS brands (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Identity
    name TEXT NOT NULL,
    description TEXT,

    -- Health (computed, rolled up from projects/retainers)
    health_status TEXT CHECK(health_status IN ('healthy', 'at_risk', 'critical')) DEFAULT 'healthy',
    health_score REAL DEFAULT 100,
    health_updated_at TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at TEXT,

    UNIQUE(client_id, name)
);

CREATE INDEX IF NOT EXISTS idx_brands_client ON brands(client_id);
CREATE INDEX IF NOT EXISTS idx_brands_health ON brands(health_status);

-- ----------------------------------------------------------------------------
-- 4. PROJECTS (Detected, Not Declared)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS projects_v5 (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Identity
    name TEXT NOT NULL,
    description TEXT,

    -- Detection evidence
    detected_from TEXT CHECK(detected_from IN ('quote', 'invoice', 'tasks', 'manual')),
    detection_confidence REAL DEFAULT 1.0,

    -- Xero links
    quote_id TEXT,
    quote_number TEXT,
    advance_invoice_id TEXT,
    final_invoice_id TEXT,

    -- Value
    quoted_value REAL,
    invoiced_value REAL DEFAULT 0,
    paid_value REAL DEFAULT 0,

    -- Lifecycle
    phase TEXT CHECK(phase IN (
        'opportunity',
        'confirmed',
        'kickoff',
        'execution',
        'delivery',
        'closeout',
        'complete',
        'cancelled'
    )) DEFAULT 'opportunity',

    phase_changed_at TEXT,
    phase_history TEXT,

    -- Timeline
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    expected_start_date TEXT,
    expected_end_date TEXT,
    actual_start_date TEXT,
    actual_end_date TEXT,

    -- Health
    health_status TEXT CHECK(health_status IN ('on_track', 'at_risk', 'off_track')) DEFAULT 'on_track',
    health_score REAL DEFAULT 100,
    health_updated_at TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_projects_v5_brand ON projects_v5(brand_id);
CREATE INDEX IF NOT EXISTS idx_projects_v5_client ON projects_v5(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_v5_phase ON projects_v5(phase);
CREATE INDEX IF NOT EXISTS idx_projects_v5_quote ON projects_v5(quote_id);

-- ----------------------------------------------------------------------------
-- 5. RETAINERS
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS retainers (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Identity
    name TEXT NOT NULL,
    description TEXT,
    scope_definition TEXT,

    -- Commercial
    monthly_value REAL NOT NULL,
    currency TEXT DEFAULT 'AED',

    -- Timeline
    start_date TEXT NOT NULL,
    end_date TEXT,
    renewal_date TEXT,

    -- Status
    status TEXT CHECK(status IN ('active', 'paused', 'churned', 'renewed')) DEFAULT 'active',
    status_changed_at TEXT,
    churn_reason TEXT,

    -- Health
    health_status TEXT CHECK(health_status IN ('healthy', 'at_risk', 'critical')) DEFAULT 'healthy',
    health_score REAL DEFAULT 100,
    health_updated_at TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_retainers_brand ON retainers(brand_id);
CREATE INDEX IF NOT EXISTS idx_retainers_client ON retainers(client_id);
CREATE INDEX IF NOT EXISTS idx_retainers_status ON retainers(status);

-- ----------------------------------------------------------------------------
-- 6. RETAINER CYCLES
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS retainer_cycles (
    id TEXT PRIMARY KEY,
    retainer_id TEXT NOT NULL REFERENCES retainers(id) ON DELETE CASCADE,

    -- Period
    cycle_month TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,

    -- Status
    status TEXT CHECK(status IN (
        'upcoming',
        'planning',
        'active',
        'delivered',
        'invoiced',
        'paid',
        'closed'
    )) DEFAULT 'upcoming',

    -- Financials
    invoice_id TEXT,
    invoice_amount REAL,
    paid_amount REAL DEFAULT 0,
    paid_at TEXT,

    -- Metrics
    tasks_planned INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_overdue INTEGER DEFAULT 0,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(retainer_id, cycle_month)
);

CREATE INDEX IF NOT EXISTS idx_retainer_cycles_retainer ON retainer_cycles(retainer_id);
CREATE INDEX IF NOT EXISTS idx_retainer_cycles_month ON retainer_cycles(cycle_month);
CREATE INDEX IF NOT EXISTS idx_retainer_cycles_status ON retainer_cycles(status);

-- ----------------------------------------------------------------------------
-- 7. TASKS (Enhanced)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS tasks_v5 (
    id TEXT PRIMARY KEY,

    -- Asana link
    asana_gid TEXT UNIQUE,
    asana_project_gid TEXT,
    asana_parent_gid TEXT,

    -- Content
    title TEXT NOT NULL,
    description TEXT,

    -- Assignment
    assignee_id TEXT REFERENCES people(id),
    assignee_name TEXT,
    assignee_email TEXT,

    -- Status
    status TEXT CHECK(status IN (
        'not_started',
        'in_progress',
        'waiting',
        'review',
        'done',
        'cancelled'
    )) DEFAULT 'not_started',

    status_changed_at TEXT,
    completed_at TEXT,

    -- Timeline
    due_date TEXT,
    due_time TEXT,
    start_date TEXT,

    -- Hierarchy links
    project_id TEXT REFERENCES projects_v5(id),
    retainer_cycle_id TEXT REFERENCES retainer_cycles(id),
    brand_id TEXT REFERENCES brands(id),
    client_id TEXT REFERENCES clients(id),

    -- Versioning
    is_deliverable BOOLEAN DEFAULT FALSE,
    current_version INTEGER DEFAULT 0,

    -- Priority
    priority TEXT CHECK(priority IN ('low', 'medium', 'high', 'urgent')) DEFAULT 'medium',
    priority_score INTEGER DEFAULT 50,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    synced_at TEXT
);

-- Generated columns for computed timing (SQLite 3.31+)
-- Note: These are computed in application layer if SQLite version doesn't support GENERATED
-- days_overdue: CASE WHEN due_date IS NOT NULL AND status NOT IN ('done', 'cancelled')
--                    AND date(due_date) < date('now')
--               THEN julianday('now') - julianday(due_date) ELSE 0 END
-- days_until_due: CASE WHEN due_date IS NOT NULL AND status NOT IN ('done', 'cancelled')
--                      AND date(due_date) >= date('now')
--                 THEN julianday(due_date) - julianday('now') ELSE NULL END
-- completed_on_time: CASE WHEN completed_at IS NOT NULL AND due_date IS NOT NULL
--                    THEN date(completed_at) <= date(due_date) ELSE NULL END

CREATE INDEX IF NOT EXISTS idx_tasks_v5_asana ON tasks_v5(asana_gid);
CREATE INDEX IF NOT EXISTS idx_tasks_v5_status ON tasks_v5(status);
CREATE INDEX IF NOT EXISTS idx_tasks_v5_due ON tasks_v5(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_v5_assignee ON tasks_v5(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_v5_project ON tasks_v5(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_v5_retainer ON tasks_v5(retainer_cycle_id);
CREATE INDEX IF NOT EXISTS idx_tasks_v5_client ON tasks_v5(client_id);

-- Partial index for overdue tasks
CREATE INDEX IF NOT EXISTS idx_tasks_v5_overdue ON tasks_v5(due_date)
    WHERE status NOT IN ('done', 'cancelled') AND due_date IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 8. TASK VERSIONS
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS task_versions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks_v5(id) ON DELETE CASCADE,

    -- Version info
    version_number INTEGER NOT NULL,
    version_label TEXT,

    -- Asana link (subtask)
    asana_subtask_gid TEXT UNIQUE,

    -- Status
    status TEXT CHECK(status IN ('draft', 'submitted', 'approved', 'rejected')) DEFAULT 'draft',
    status_changed_at TEXT,

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at TEXT,
    reviewed_at TEXT,

    -- Feedback
    feedback_summary TEXT,
    feedback_sentiment TEXT CHECK(feedback_sentiment IN ('positive', 'neutral', 'negative')),

    UNIQUE(task_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_task_versions_task ON task_versions(task_id);
CREATE INDEX IF NOT EXISTS idx_task_versions_status ON task_versions(status);

-- ============================================================================
-- SIGNALS & ISSUES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 9. SIGNALS (Core V5 Table)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS signals_v5 (
    id TEXT PRIMARY KEY,

    -- Classification
    signal_type TEXT NOT NULL,
    signal_category TEXT NOT NULL CHECK(signal_category IN (
        'schedule',
        'quality',
        'financial',
        'communication',
        'relationship',
        'process'
    )),

    -- Valence (THE KEY FIELD)
    valence INTEGER NOT NULL CHECK(valence IN (-1, 0, 1)),
    magnitude REAL NOT NULL DEFAULT 0.5 CHECK(magnitude >= 0 AND magnitude <= 1),

    -- Entity reference
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,

    -- Scope chain (for aggregation up the hierarchy)
    scope_task_id TEXT,
    scope_project_id TEXT,
    scope_retainer_id TEXT,
    scope_brand_id TEXT,
    scope_client_id TEXT,
    scope_person_id TEXT,

    -- Source evidence
    source_type TEXT NOT NULL CHECK(source_type IN (
        'asana', 'xero', 'gchat', 'calendar', 'gmeet', 'email', 'manual'
    )),
    source_id TEXT,
    source_url TEXT,
    source_excerpt TEXT,

    -- Payload (signal-specific data)
    value_json TEXT NOT NULL,

    -- Confidence
    detection_confidence REAL DEFAULT 0.9 CHECK(detection_confidence >= 0 AND detection_confidence <= 1),
    attribution_confidence REAL DEFAULT 0.9 CHECK(attribution_confidence >= 0 AND attribution_confidence <= 1),

    -- Lifecycle
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN (
        'active',
        'consumed',
        'balanced',
        'expired',
        'archived'
    )),

    balanced_by_signal_id TEXT REFERENCES signals_v5(id),
    consumed_by_issue_id TEXT,

    -- Timing
    occurred_at TEXT NOT NULL,
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    balanced_at TEXT,

    -- Detector info
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Note: decay_multiplier and effective_magnitude are computed in application layer:
-- decay_multiplier = CASE
--     WHEN age_days > 365 THEN 0.1
--     WHEN age_days > 180 THEN 0.25
--     WHEN age_days > 90 THEN 0.5
--     WHEN age_days > 30 THEN 0.8
--     ELSE 1.0 END
-- effective_magnitude = magnitude * decay_multiplier

CREATE INDEX IF NOT EXISTS idx_signals_v5_type ON signals_v5(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_v5_category ON signals_v5(signal_category);
CREATE INDEX IF NOT EXISTS idx_signals_v5_valence ON signals_v5(valence);
CREATE INDEX IF NOT EXISTS idx_signals_v5_status ON signals_v5(status);
CREATE INDEX IF NOT EXISTS idx_signals_v5_entity ON signals_v5(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_signals_v5_client ON signals_v5(scope_client_id);
CREATE INDEX IF NOT EXISTS idx_signals_v5_project ON signals_v5(scope_project_id);
CREATE INDEX IF NOT EXISTS idx_signals_v5_brand ON signals_v5(scope_brand_id);
CREATE INDEX IF NOT EXISTS idx_signals_v5_detected ON signals_v5(detected_at);
CREATE INDEX IF NOT EXISTS idx_signals_v5_active ON signals_v5(status, valence) WHERE status = 'active';

-- ----------------------------------------------------------------------------
-- 10. ISSUES
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS issues_v5 (
    id TEXT PRIMARY KEY,

    -- Classification
    issue_type TEXT NOT NULL CHECK(issue_type IN (
        'schedule_delivery',
        'quality',
        'financial',
        'communication',
        'relationship',
        'process'
    )),
    issue_subtype TEXT NOT NULL,

    -- Scope
    scope_type TEXT NOT NULL CHECK(scope_type IN (
        'task', 'project', 'retainer', 'brand', 'client'
    )),
    scope_id TEXT NOT NULL,

    -- Scope chain (for context)
    scope_task_ids TEXT,
    scope_project_ids TEXT,
    scope_retainer_id TEXT,
    scope_brand_id TEXT,
    scope_client_id TEXT,

    -- Display
    headline TEXT NOT NULL,
    description TEXT,

    -- Severity
    severity TEXT NOT NULL CHECK(severity IN ('critical', 'high', 'medium', 'low')),
    priority_score REAL NOT NULL DEFAULT 0,
    trajectory TEXT CHECK(trajectory IN ('worsening', 'stable', 'improving')) DEFAULT 'stable',

    -- Signal evidence
    signal_ids TEXT NOT NULL,

    -- Signal balance (cached for performance)
    balance_negative_count INTEGER DEFAULT 0,
    balance_negative_magnitude REAL DEFAULT 0,
    balance_neutral_count INTEGER DEFAULT 0,
    balance_positive_count INTEGER DEFAULT 0,
    balance_positive_magnitude REAL DEFAULT 0,
    balance_net_score REAL DEFAULT 0,

    -- Recommended action
    recommended_action TEXT,
    recommended_owner_role TEXT,
    recommended_urgency TEXT CHECK(recommended_urgency IN ('immediate', 'this_week', 'this_month')),

    -- Lifecycle
    state TEXT NOT NULL DEFAULT 'detected' CHECK(state IN (
        'detected',
        'surfaced',
        'acknowledged',
        'addressing',
        'resolved',
        'monitoring',
        'closed'
    )),

    -- Timestamps
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    surfaced_at TEXT,
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    addressing_started_at TEXT,
    resolved_at TEXT,
    monitoring_until TEXT,
    closed_at TEXT,

    -- Resolution
    resolution_method TEXT CHECK(resolution_method IN (
        'signals_balanced',
        'tasks_completed',
        'manual',
        'auto_expired',
        'dismissed'
    )),
    resolution_notes TEXT,
    resolved_by TEXT,

    -- Regression
    regression_count INTEGER DEFAULT 0,
    last_regression_at TEXT,

    -- History
    state_history TEXT,
    score_history TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_issues_v5_type ON issues_v5(issue_type);
CREATE INDEX IF NOT EXISTS idx_issues_v5_subtype ON issues_v5(issue_subtype);
CREATE INDEX IF NOT EXISTS idx_issues_v5_scope ON issues_v5(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_issues_v5_client ON issues_v5(scope_client_id);
CREATE INDEX IF NOT EXISTS idx_issues_v5_state ON issues_v5(state);
CREATE INDEX IF NOT EXISTS idx_issues_v5_severity ON issues_v5(severity);
CREATE INDEX IF NOT EXISTS idx_issues_v5_score ON issues_v5(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_issues_v5_surfaced ON issues_v5(state, priority_score DESC) WHERE state = 'surfaced';

-- ============================================================================
-- INTEGRATION SYNC STATE
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 11. XERO SYNC STATE
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS xero_sync_state (
    id TEXT PRIMARY KEY DEFAULT 'singleton',
    last_sync_at TEXT,
    last_modified_since TEXT,
    contacts_synced INTEGER DEFAULT 0,
    invoices_synced INTEGER DEFAULT 0,
    quotes_synced INTEGER DEFAULT 0,
    payments_synced INTEGER DEFAULT 0,
    errors TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Insert singleton row
INSERT OR IGNORE INTO xero_sync_state (id) VALUES ('singleton');

-- ----------------------------------------------------------------------------
-- 12. GOOGLE CHAT SYNC STATE
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gchat_sync_state (
    space_id TEXT PRIMARY KEY,
    space_name TEXT,
    space_type TEXT,

    -- Mapping
    client_id TEXT REFERENCES clients(id),
    brand_id TEXT REFERENCES brands(id),
    project_id TEXT REFERENCES projects_v5(id),

    -- Sync state
    last_sync_at TEXT,
    last_message_id TEXT,
    last_message_at TEXT,

    -- Metrics (cached)
    message_count_30d INTEGER DEFAULT 0,
    avg_response_time_hours REAL,

    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gchat_sync_client ON gchat_sync_state(client_id);

-- ----------------------------------------------------------------------------
-- 13. CALENDAR SYNC STATE
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS calendar_sync_state (
    calendar_id TEXT PRIMARY KEY,
    calendar_name TEXT,

    last_sync_at TEXT,
    sync_token TEXT,

    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================================
-- XERO ENTITIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 14. XERO INVOICES
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS xero_invoices (
    id TEXT PRIMARY KEY,
    xero_invoice_id TEXT UNIQUE NOT NULL,

    -- Invoice details
    invoice_number TEXT,
    reference TEXT,

    contact_id TEXT,
    client_id TEXT REFERENCES clients(id),

    -- Type (detected)
    invoice_type TEXT CHECK(invoice_type IN ('advance', 'progress', 'final', 'retainer', 'other')),
    type_detection_method TEXT,

    -- Link to our entities
    project_id TEXT REFERENCES projects_v5(id),
    retainer_cycle_id TEXT REFERENCES retainer_cycles(id),

    -- Financials
    subtotal REAL,
    tax REAL,
    total REAL NOT NULL,
    currency TEXT DEFAULT 'AED',

    amount_due REAL,
    amount_paid REAL DEFAULT 0,

    -- Dates
    date_issued TEXT,
    due_date TEXT,
    fully_paid_date TEXT,

    -- Status
    status TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    synced_at TEXT
);

-- Note: days_overdue and aging_bucket are computed in application layer:
-- days_overdue = julianday('now') - julianday(due_date) when overdue
-- aging_bucket = '1-30', '31-60', '61-90', '90+'

CREATE INDEX IF NOT EXISTS idx_xero_invoices_client ON xero_invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_xero_invoices_project ON xero_invoices(project_id);
CREATE INDEX IF NOT EXISTS idx_xero_invoices_status ON xero_invoices(status);
CREATE INDEX IF NOT EXISTS idx_xero_invoices_due ON xero_invoices(due_date);

-- ----------------------------------------------------------------------------
-- 15. XERO PAYMENTS
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS xero_payments (
    id TEXT PRIMARY KEY,
    xero_payment_id TEXT UNIQUE NOT NULL,

    invoice_id TEXT REFERENCES xero_invoices(id),
    xero_invoice_id TEXT,

    amount REAL NOT NULL,
    currency TEXT DEFAULT 'AED',

    payment_date TEXT NOT NULL,

    -- Timing
    days_after_due INTEGER,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_xero_payments_invoice ON xero_payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_xero_payments_date ON xero_payments(payment_date);

-- ============================================================================
-- GOOGLE CHAT ENTITIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 16. GOOGLE CHAT MESSAGES
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gchat_messages (
    id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,

    -- Message info
    message_id TEXT UNIQUE NOT NULL,
    thread_id TEXT,

    sender_email TEXT,
    sender_name TEXT,
    sender_type TEXT CHECK(sender_type IN ('team', 'client', 'unknown')),

    -- Content
    text_snippet TEXT,
    has_attachments BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TEXT NOT NULL,

    -- Analysis
    sentiment TEXT CHECK(sentiment IN ('positive', 'neutral', 'negative')),
    sentiment_keywords TEXT,
    is_escalation BOOLEAN DEFAULT FALSE,

    -- Sync
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gchat_messages_space ON gchat_messages(space_id);
CREATE INDEX IF NOT EXISTS idx_gchat_messages_sender ON gchat_messages(sender_type);
CREATE INDEX IF NOT EXISTS idx_gchat_messages_created ON gchat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_gchat_messages_sentiment ON gchat_messages(sentiment);

-- ============================================================================
-- CALENDAR & MEET ENTITIES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 17. CALENDAR EVENTS
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS calendar_events (
    id TEXT PRIMARY KEY,
    google_event_id TEXT UNIQUE NOT NULL,
    calendar_id TEXT,

    -- Event details
    title TEXT NOT NULL,
    description TEXT,

    -- Time
    start_time TEXT NOT NULL,
    end_time TEXT,
    all_day BOOLEAN DEFAULT FALSE,

    -- Attendees
    attendees_json TEXT,
    organizer_email TEXT,

    -- Client/project link
    client_id TEXT REFERENCES clients(id),
    brand_id TEXT REFERENCES brands(id),
    project_id TEXT REFERENCES projects_v5(id),

    -- Analysis
    title_category TEXT CHECK(title_category IN ('kickoff', 'review', 'sync', 'urgent', 'other')),

    -- Status
    status TEXT CHECK(status IN ('confirmed', 'tentative', 'cancelled')),

    -- Meeting occurred?
    meeting_occurred BOOLEAN,
    gemini_notes_id TEXT,

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_client ON calendar_events(client_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_start ON calendar_events(start_time);
CREATE INDEX IF NOT EXISTS idx_calendar_events_status ON calendar_events(status);
CREATE INDEX IF NOT EXISTS idx_calendar_events_category ON calendar_events(title_category);

-- ----------------------------------------------------------------------------
-- 18. GEMINI MEETING NOTES
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gemini_notes (
    id TEXT PRIMARY KEY,
    event_id TEXT REFERENCES calendar_events(id),
    google_event_id TEXT,

    -- Meeting metadata
    meeting_title TEXT,
    meeting_date TEXT,
    duration_minutes INTEGER,

    -- Attendees
    expected_attendees TEXT,
    actual_attendees TEXT,

    -- Extracted content
    raw_summary TEXT,

    -- Parsed sections
    decisions TEXT,
    action_items TEXT,
    concerns TEXT,
    approvals TEXT,
    blockers TEXT,

    -- Analysis
    overall_sentiment TEXT CHECK(overall_sentiment IN ('positive', 'neutral', 'negative', 'mixed')),

    -- Metadata
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_gemini_notes_event ON gemini_notes(event_id);
CREATE INDEX IF NOT EXISTS idx_gemini_notes_date ON gemini_notes(meeting_date);

-- ============================================================================
-- VIEWS (Computed Columns)
-- ============================================================================

-- View for tasks with computed overdue fields
CREATE VIEW IF NOT EXISTS tasks_v5_computed AS
SELECT
    t.*,
    CASE
        WHEN t.due_date IS NOT NULL AND t.status NOT IN ('done', 'cancelled')
             AND date(t.due_date) < date('now')
        THEN CAST(julianday('now') - julianday(t.due_date) AS INTEGER)
        ELSE 0
    END as days_overdue,
    CASE
        WHEN t.due_date IS NOT NULL AND t.status NOT IN ('done', 'cancelled')
             AND date(t.due_date) >= date('now')
        THEN CAST(julianday(t.due_date) - julianday('now') AS INTEGER)
        ELSE NULL
    END as days_until_due,
    CASE
        WHEN t.completed_at IS NOT NULL AND t.due_date IS NOT NULL
        THEN date(t.completed_at) <= date(t.due_date)
        ELSE NULL
    END as completed_on_time
FROM tasks_v5 t;

-- View for signals with decay
CREATE VIEW IF NOT EXISTS signals_v5_computed AS
SELECT
    s.*,
    CAST(julianday('now') - julianday(s.detected_at) AS INTEGER) as age_days,
    CASE
        WHEN julianday('now') - julianday(s.detected_at) > 365 THEN 0.1
        WHEN julianday('now') - julianday(s.detected_at) > 180 THEN 0.25
        WHEN julianday('now') - julianday(s.detected_at) > 90 THEN 0.5
        WHEN julianday('now') - julianday(s.detected_at) > 30 THEN 0.8
        ELSE 1.0
    END as decay_multiplier,
    s.magnitude * CASE
        WHEN julianday('now') - julianday(s.detected_at) > 365 THEN 0.1
        WHEN julianday('now') - julianday(s.detected_at) > 180 THEN 0.25
        WHEN julianday('now') - julianday(s.detected_at) > 90 THEN 0.5
        WHEN julianday('now') - julianday(s.detected_at) > 30 THEN 0.8
        ELSE 1.0
    END as effective_magnitude
FROM signals_v5 s;

-- View for invoices with aging
CREATE VIEW IF NOT EXISTS xero_invoices_computed AS
SELECT
    i.*,
    CASE
        WHEN i.status NOT IN ('PAID', 'VOIDED') AND i.due_date IS NOT NULL
             AND date(i.due_date) < date('now')
        THEN CAST(julianday('now') - julianday(i.due_date) AS INTEGER)
        ELSE 0
    END as days_overdue,
    CASE
        WHEN i.status IN ('PAID', 'VOIDED') THEN 'paid'
        WHEN i.due_date IS NULL THEN 'no_due_date'
        WHEN date(i.due_date) >= date('now') THEN 'current'
        WHEN julianday('now') - julianday(i.due_date) <= 30 THEN '1-30'
        WHEN julianday('now') - julianday(i.due_date) <= 60 THEN '31-60'
        WHEN julianday('now') - julianday(i.due_date) <= 90 THEN '61-90'
        ELSE '90+'
    END as aging_bucket
FROM xero_invoices i;
