CREATE INDEX idx_actions_status ON actions(status)

CREATE INDEX idx_asana_attachments_task ON asana_attachments(task_id)

CREATE INDEX idx_asana_custom_fields_project ON asana_custom_fields(project_id)

CREATE INDEX idx_asana_custom_fields_task ON asana_custom_fields(task_id)

CREATE INDEX idx_asana_goals_owner ON asana_goals(owner_id)

CREATE INDEX idx_asana_portfolios_owner ON asana_portfolios(owner_id)

CREATE INDEX idx_asana_sections_project ON asana_sections(project_id)

CREATE INDEX idx_asana_stories_task ON asana_stories(task_id)

CREATE INDEX idx_asana_subtasks_parent_task ON asana_subtasks(parent_task_id)

CREATE INDEX idx_asana_task_dependencies_task ON asana_task_dependencies(task_id)

CREATE INDEX idx_calendar_attendees_event ON calendar_attendees(event_id)

CREATE INDEX idx_calendar_recurrence_event ON calendar_recurrence_rules(event_id)

CREATE INDEX idx_chat_attachments_message ON chat_attachments(message_id)

CREATE INDEX idx_chat_reactions_message ON chat_reactions(message_id)

CREATE INDEX idx_chat_space_members_space ON chat_space_members(space_id)

CREATE INDEX idx_client_health_log_client ON client_health_log(client_id)

CREATE INDEX idx_client_projects_client ON client_projects(client_id)

CREATE INDEX idx_client_projects_project ON client_projects(project_id)

CREATE INDEX idx_commitments_client ON commitments(client_id)

CREATE INDEX idx_commitments_source ON commitments(source_id)

CREATE INDEX idx_communications_content_hash ON communications(content_hash)

CREATE INDEX idx_communications_priority ON communications(priority DESC)

CREATE INDEX idx_cost_snap_entity
ON cost_snapshots(entity_id, computed_at DESC)

CREATE INDEX idx_cost_snap_time
ON cost_snapshots(computed_at DESC)

CREATE INDEX idx_cost_snap_type
ON cost_snapshots(snapshot_type, computed_at DESC)

CREATE INDEX idx_decisions_pending ON decisions(approved) WHERE approved IS NULL

CREATE INDEX idx_digest_history_user_bucket ON digest_history(user_id, bucket)

CREATE INDEX idx_digest_queue_user_bucket ON digest_queue(user_id, bucket, processed)

CREATE INDEX idx_events_start ON events(start_time)

CREATE INDEX idx_events_start_at ON events(start_at)

CREATE INDEX idx_gmail_attachments_message ON gmail_attachments(message_id)

CREATE INDEX idx_gmail_labels_message ON gmail_labels(message_id)

CREATE INDEX idx_gmail_participants_message ON gmail_participants(message_id)

CREATE INDEX idx_inbox_items_v29_client ON inbox_items_v29(client_id)

CREATE INDEX idx_inbox_items_v29_state ON inbox_items_v29(state)

CREATE INDEX idx_inbox_items_v29_type ON inbox_items_v29(type)

CREATE INDEX idx_intel_events_entity
ON intelligence_events(entity_type, entity_id, created_at DESC)

CREATE INDEX idx_intel_events_type
ON intelligence_events(event_type, created_at DESC)

CREATE INDEX idx_intel_events_unconsumed
ON intelligence_events(consumed_at, created_at DESC)
WHERE consumed_at IS NULL

CREATE INDEX idx_invoices_due_at ON invoices(due_at)

CREATE INDEX idx_invoices_status ON invoices(status)

CREATE INDEX idx_issue_transitions_v29_issue ON issue_transitions_v29(issue_id)

CREATE INDEX idx_notifications_created ON notifications(created_at DESC)

CREATE INDEX idx_pattern_snap_cycle
ON pattern_snapshots(cycle_id)

CREATE INDEX idx_pattern_snap_pattern
ON pattern_snapshots(pattern_id, detected_at DESC)

CREATE INDEX idx_pattern_snap_time
ON pattern_snapshots(detected_at DESC)

CREATE INDEX idx_suppression_v29_expires ON inbox_suppression_rules_v29(expires_at)

CREATE INDEX idx_suppression_v29_key ON inbox_suppression_rules_v29(suppression_key)

CREATE INDEX idx_tasks_due ON tasks(due_date)

CREATE INDEX idx_tasks_priority ON tasks(priority DESC)

CREATE INDEX idx_tasks_project_id ON tasks(project_id)

CREATE INDEX idx_tasks_status ON tasks(status)

CREATE INDEX idx_time_debt_lane ON time_debt(lane)

CREATE INDEX idx_time_debt_unresolved ON time_debt(resolved_at) WHERE resolved_at IS NULL

CREATE INDEX idx_xero_bank_transactions_contact ON xero_bank_transactions(contact_id)

CREATE INDEX idx_xero_contacts_name ON xero_contacts(name)

CREATE INDEX idx_xero_credit_notes_contact ON xero_credit_notes(contact_id)

CREATE INDEX idx_xero_line_items_invoice ON xero_line_items(invoice_id)

CREATE TABLE actions (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    target_system TEXT,
                    payload TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    requires_approval INTEGER DEFAULT 1,
                    approved_by TEXT,
                    approved_at TEXT,
                    executed_at TEXT,
                    result TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )

CREATE TABLE asana_attachments (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            name TEXT NOT NULL,
            download_url TEXT,
            host TEXT,
            size_bytes INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )

CREATE TABLE asana_custom_fields (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            task_id TEXT,
            field_name TEXT NOT NULL,
            field_type TEXT NOT NULL,
            text_value TEXT,
            number_value REAL,
            enum_value TEXT,
            date_value TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )

CREATE TABLE asana_goals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT,
            owner_name TEXT,
            status TEXT,
            due_on TEXT,
            html_notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )

CREATE TABLE asana_portfolios (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT,
            owner_name TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )

CREATE TABLE asana_sections (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )

CREATE TABLE asana_stories (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            type TEXT NOT NULL,
            text TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL
        )

CREATE TABLE asana_subtasks (
            id TEXT PRIMARY KEY,
            parent_task_id TEXT NOT NULL,
            name TEXT NOT NULL,
            assignee_id TEXT,
            assignee_name TEXT,
            completed INTEGER DEFAULT 0,
            due_on TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )

CREATE TABLE asana_task_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            depends_on_task_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(task_id, depends_on_task_id)
        )

CREATE TABLE calendar_attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            email TEXT NOT NULL,
            display_name TEXT,
            response_status TEXT,
            organizer INTEGER DEFAULT 0,
            self INTEGER DEFAULT 0
        )

CREATE TABLE calendar_recurrence_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            rrule TEXT NOT NULL
        )

CREATE TABLE capacity_lanes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    display_name TEXT,
                    owner TEXT,
                    weekly_hours INTEGER DEFAULT 40,
                    buffer_pct REAL DEFAULT 0.2,
                    color TEXT DEFAULT '#6366f1',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )

CREATE TABLE chat_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            name TEXT,
            content_type TEXT,
            source_uri TEXT,
            thumbnail_uri TEXT
        )

CREATE TABLE chat_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            emoji TEXT NOT NULL,
            user_id TEXT,
            user_name TEXT
        )

CREATE TABLE chat_space_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            space_id TEXT NOT NULL,
            member_id TEXT NOT NULL,
            display_name TEXT,
            email TEXT,
            role TEXT,
            UNIQUE(space_id, member_id)
        )

CREATE TABLE chat_space_metadata (
            space_id TEXT PRIMARY KEY,
            display_name TEXT,
            space_type TEXT,
            threaded INTEGER DEFAULT 0,
            member_count INTEGER,
            created_time TEXT,
            last_synced TEXT
        )

CREATE TABLE client_health_log (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    health_score INTEGER,
                    factors TEXT,
                    computed_at TEXT NOT NULL,
                    FOREIGN KEY (client_id) REFERENCES clients(id)
                )

CREATE TABLE client_projects (
                    client_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    linked_at TEXT NOT NULL,
                    PRIMARY KEY (client_id, project_id),
                    FOREIGN KEY (client_id) REFERENCES clients(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )

CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT CHECK (tier IN ('A', 'B', 'C')),
            type TEXT,
            financial_annual_value REAL,
            financial_ar_outstanding REAL,
            financial_ar_aging TEXT,
            financial_payment_pattern TEXT,
            relationship_health TEXT CHECK (relationship_health IN
                ('excellent', 'good', 'fair', 'poor', 'critical')),
            relationship_trend TEXT CHECK (relationship_trend IN
                ('improving', 'stable', 'declining')),
            relationship_last_interaction TEXT,
            relationship_notes TEXT,
            contacts_json TEXT,
            active_projects_json TEXT,
            xero_contact_id TEXT,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )

CREATE TABLE commitments (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
                    source_type TEXT NOT NULL DEFAULT 'communication',
                    source_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    type TEXT NOT NULL CHECK (type IN ('promise', 'request')),
                    confidence REAL,
                    deadline TEXT,
                    speaker TEXT,
                    target TEXT,
                    client_id TEXT,
                    task_id TEXT,
                    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'fulfilled', 'broken', 'cancelled')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (source_id) REFERENCES communications(id),
                    FOREIGN KEY (client_id) REFERENCES clients(id),
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )

CREATE TABLE communications (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    thread_id TEXT,
                    from_email TEXT,
                    to_emails TEXT,
                    subject TEXT,
                    snippet TEXT,
                    priority INTEGER DEFAULT 50,
                    requires_response INTEGER DEFAULT 0,
                    response_deadline TEXT,
                    sentiment TEXT,
                    labels TEXT,
                    processed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                , content_hash TEXT, body_text_source TEXT, body_text TEXT, received_at TEXT, sensitivity TEXT, stakeholder_tier TEXT, is_read INTEGER, is_starred INTEGER, importance TEXT, has_attachments INTEGER DEFAULT 0, attachment_count INTEGER DEFAULT 0, label_ids TEXT)

CREATE TABLE cost_snapshots (
    id TEXT PRIMARY KEY,
    computed_at TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,       -- 'client' | 'project' | 'portfolio'
    entity_id TEXT,                    -- NULL for portfolio snapshots
    effort_score REAL,
    efficiency_ratio REAL,
    profitability_band TEXT,
    cost_drivers TEXT,                 -- JSON array of driver strings
    data TEXT NOT NULL,                -- Full JSON of CostProfile.to_dict()
    cycle_id TEXT
)

CREATE TABLE cycle_logs (
                    id TEXT PRIMARY KEY,
                    cycle_number INTEGER,
                    phase TEXT,
                    data TEXT,
                    duration_ms REAL,
                    created_at TEXT NOT NULL
                )

CREATE TABLE decisions (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    description TEXT,
                    input_data TEXT,
                    options TEXT,
                    selected_option TEXT,
                    rationale TEXT,
                    confidence REAL DEFAULT 0.5,
                    requires_approval INTEGER DEFAULT 1,
                    approved INTEGER,
                    approved_at TEXT,
                    executed INTEGER DEFAULT 0,
                    executed_at TEXT,
                    outcome TEXT,
                    created_at TEXT NOT NULL
                )

CREATE TABLE digest_history (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    digest_json TEXT NOT NULL,
                    item_count INTEGER NOT NULL,
                    sent_at TEXT NOT NULL
                )

CREATE TABLE digest_queue (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    notification_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    processed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    processed_at TEXT
                )

CREATE TABLE events (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    location TEXT,
                    attendees TEXT,
                    status TEXT DEFAULT 'confirmed',
                    prep_required TEXT,
                    context TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                , prep_notes TEXT, start_at TEXT, end_at TEXT, organizer_email TEXT, organizer_name TEXT, conference_url TEXT, conference_type TEXT, recurrence TEXT, event_type TEXT, calendar_id TEXT DEFAULT 'primary', attendee_count INTEGER DEFAULT 0, accepted_count INTEGER DEFAULT 0, declined_count INTEGER DEFAULT 0)

CREATE TABLE feedback (
                    id TEXT PRIMARY KEY,
                    decision_id TEXT,
                    insight_id TEXT,
                    action_id TEXT,
                    feedback_type TEXT,
                    details TEXT,
                    created_at TEXT NOT NULL
                )

CREATE TABLE gmail_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT,
            size_bytes INTEGER,
            attachment_id TEXT
        )

CREATE TABLE gmail_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            label_id TEXT NOT NULL,
            label_name TEXT
        )

CREATE TABLE gmail_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT NOT NULL,
            name TEXT
        )

CREATE TABLE governance_audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    subject_identifier TEXT NOT NULL,
                    details TEXT NOT NULL,
                    ip_address TEXT,
                    created_at TEXT NOT NULL
                )

CREATE TABLE inbox_items_v29 (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('issue', 'flagged_signal', 'orphan', 'ambiguous')),
    state TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN (
        'proposed', 'snoozed', 'linked_to_issue', 'dismissed'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    proposed_at TEXT NOT NULL,
    last_refreshed_at TEXT NOT NULL,
    read_at TEXT,
    resurfaced_at TEXT,
    resolved_at TEXT,
    snooze_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    dismissed_by TEXT,
    dismissed_at TEXT,
    dismiss_reason TEXT,
    suppression_key TEXT,
    underlying_issue_id TEXT,
    underlying_signal_id TEXT,
    resolved_issue_id TEXT,
    title TEXT NOT NULL,
    client_id TEXT,
    brand_id TEXT,
    engagement_id TEXT,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (underlying_issue_id) REFERENCES issues_v29(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
)

CREATE TABLE inbox_suppression_rules_v29 (
    id TEXT PRIMARY KEY,
    suppression_key TEXT NOT NULL UNIQUE,
    item_type TEXT NOT NULL,
    scope_client_id TEXT,
    scope_engagement_id TEXT,
    scope_source TEXT,
    scope_rule TEXT,
    reason TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
)

CREATE TABLE insights (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    confidence REAL DEFAULT 0.5,
                    data TEXT,
                    actionable INTEGER DEFAULT 0,
                    action_taken INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                )

CREATE TABLE intelligence_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,          -- 'signal_fired' | 'signal_cleared' | 'signal_escalated'
                                      -- 'pattern_detected' | 'pattern_resolved'
                                      -- 'compound_risk_detected' | 'health_threshold_crossed'
    severity TEXT NOT NULL,            -- 'critical' | 'warning' | 'watch' | 'info'
    entity_type TEXT,                  -- 'client' | 'project' | 'person' | 'portfolio'
    entity_id TEXT,
    event_data TEXT NOT NULL,          -- JSON payload with event details
    source_module TEXT,                -- 'signals' | 'patterns' | 'correlation' | 'cost'
    created_at TEXT NOT NULL,
    consumed_at TEXT,                  -- Set when a downstream consumer processes the event
    consumer TEXT                      -- Which consumer processed it
)

CREATE TABLE intelligence_events_archive (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    event_data TEXT NOT NULL,
    source_module TEXT,
    created_at TEXT NOT NULL,
    consumed_at TEXT,
    consumer TEXT,
    archived_at TEXT NOT NULL
)

CREATE TABLE invoices (
            id TEXT PRIMARY KEY,
            source_id TEXT,
            client_id TEXT,
            client_name TEXT,
            status TEXT DEFAULT 'pending',
            total REAL,
            amount_due REAL,
            currency TEXT DEFAULT 'AED',
            issued_at TEXT,
            due_at TEXT,
            paid_at TEXT,
            aging_bucket TEXT,
            created_at TEXT,
            updated_at TEXT
        )

CREATE TABLE issue_transitions_v29 (
    id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    action TEXT,
    actor TEXT,
    reason TEXT,
    transitioned_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (issue_id) REFERENCES issues_v29(id)
)

CREATE TABLE notifications (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'normal',
                    title TEXT NOT NULL,
                    body TEXT,
                    action_url TEXT,
                    action_data TEXT,
                    channels TEXT,
                    sent_at TEXT,
                    read_at TEXT,
                    acted_on_at TEXT,
                    created_at TEXT NOT NULL
                )

CREATE TABLE pattern_snapshots (
    id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    pattern_id TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'medium',
    entities_involved TEXT NOT NULL,   -- JSON array of {type, id, name, role_in_pattern}
    evidence TEXT NOT NULL,            -- JSON: metrics, narrative, signals
    cycle_id TEXT                      -- Links to specific daemon cycle run
)

CREATE TABLE patterns (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    description TEXT,
                    data TEXT,
                    confidence REAL DEFAULT 0.5,
                    occurrences INTEGER DEFAULT 1,
                    last_seen TEXT,
                    created_at TEXT NOT NULL
                )

CREATE TABLE people (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    company TEXT,
                    role TEXT,
                    type TEXT DEFAULT 'external',  -- 'internal' or 'external'
                    relationship TEXT,
                    importance INTEGER DEFAULT 50,
                    last_contact TEXT,
                    contact_frequency_days INTEGER,
                    notes TEXT,
                    context TEXT
                )

CREATE TABLE projects (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    source_id TEXT,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    health TEXT DEFAULT 'green',
                    enrollment_status TEXT DEFAULT 'enrolled',
                    rule_bundles TEXT,
                    owner TEXT,
                    deadline TEXT,
                    tasks_total INTEGER DEFAULT 0,
                    tasks_done INTEGER DEFAULT 0,
                    blockers TEXT,
                    next_milestone TEXT,
                    context TEXT
                , brand_id TEXT)

CREATE TABLE sqlite_sequence(name,seq)

CREATE TABLE subject_access_requests (
                    request_id TEXT PRIMARY KEY,
                    subject_identifier TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    fulfilled_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    requested_by TEXT NOT NULL DEFAULT 'system',
                    reason TEXT,
                    created_at TEXT NOT NULL
                )

CREATE TABLE sync_state (
                    source TEXT PRIMARY KEY,
                    last_sync TEXT,
                    last_success TEXT,
                    items_synced INTEGER DEFAULT 0,
                    error TEXT
                )

CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER DEFAULT 50,
                    due_date TEXT,
                    due_time TEXT,
                    assignee TEXT,
                    project TEXT,
                    tags TEXT,
                    dependencies TEXT,
                    blockers TEXT,
                    context TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    synced_at TEXT
                , description TEXT DEFAULT '', project_id TEXT, notes TEXT, completed_at TEXT, priority_reasons TEXT, section_id TEXT, section_name TEXT, subtask_count INTEGER DEFAULT 0, has_dependencies INTEGER DEFAULT 0, attachment_count INTEGER DEFAULT 0, story_count INTEGER DEFAULT 0, custom_fields_json TEXT)

CREATE TABLE time_debt (
                    id TEXT PRIMARY KEY,
                    lane TEXT NOT NULL,
                    amount_min INTEGER NOT NULL,
                    reason TEXT,
                    source_task_id TEXT,
                    incurred_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (lane) REFERENCES capacity_lanes(id)
                )

CREATE TABLE xero_bank_transactions (
            id TEXT PRIMARY KEY,
            type TEXT,
            contact_id TEXT,
            date TEXT,
            status TEXT,
            total REAL,
            currency_code TEXT,
            reference TEXT,
            last_synced TEXT
        )

CREATE TABLE xero_contacts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            account_number TEXT,
            tax_number TEXT,
            is_supplier INTEGER DEFAULT 0,
            is_customer INTEGER DEFAULT 0,
            default_currency TEXT,
            outstanding_balance REAL,
            overdue_balance REAL,
            last_synced TEXT
        )

CREATE TABLE xero_credit_notes (
            id TEXT PRIMARY KEY,
            contact_id TEXT,
            date TEXT,
            status TEXT,
            total REAL,
            currency_code TEXT,
            remaining_credit REAL,
            allocated_amount REAL,
            last_synced TEXT
        )

CREATE TABLE xero_line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            description TEXT,
            quantity REAL,
            unit_amount REAL,
            line_amount REAL,
            tax_type TEXT,
            tax_amount REAL,
            account_code TEXT,
            tracking_category TEXT,
            tracking_option TEXT
        )

CREATE TABLE xero_tax_rates (
            name TEXT PRIMARY KEY,
            tax_type TEXT,
            effective_rate REAL,
            status TEXT
        )

CREATE VIEW issues_v29 AS
                        SELECT
                            i.issue_id AS id,
                            CASE
                                WHEN lower(i.issue_type) LIKE '%ar%' OR lower(i.issue_type) LIKE '%payment%' OR lower(i.issue_type) LIKE '%invoice%' THEN 'financial'
                                WHEN lower(i.issue_type) LIKE '%deadline%' OR lower(i.issue_type) LIKE '%overdue%' OR lower(i.issue_type) LIKE '%delay%' THEN 'schedule_delivery'
                                WHEN lower(i.issue_type) LIKE '%communication%' OR lower(i.issue_type) LIKE '%response%' THEN 'communication'
                                ELSE 'risk'
                            END AS type,
                            CASE i.state
                                WHEN 'open' THEN 'surfaced'
                                WHEN 'monitoring' THEN 'acknowledged'
                                WHEN 'awaiting' THEN 'awaiting_resolution'
                                WHEN 'blocked' THEN 'addressing'
                                WHEN 'resolved' THEN 'closed'
                                ELSE 'surfaced'
                            END AS state,
                            CASE
                                WHEN i.priority >= 80 THEN 'critical'
                                WHEN i.priority >= 60 THEN 'high'
                                WHEN i.priority >= 40 THEN 'medium'
                                WHEN i.priority >= 20 THEN 'low'
                                ELSE 'info'
                            END AS severity,
                            COALESCE(
                                CASE WHEN i.primary_ref_type = 'client' THEN i.primary_ref_id END,
                                (SELECT t.client_id FROM tasks t WHERE t.id = i.primary_ref_id),
                                'unknown'
                            ) AS client_id,
                            NULL AS brand_id,
                            NULL AS engagement_id,
                            i.headline AS title,
                            COALESCE(i.scope_refs, '{}') AS evidence,
                            'v1' AS evidence_version,
                            i.issue_id AS aggregation_key,
                            COALESCE(i.opened_at, datetime('now')) AS created_at,
                            COALESCE(i.last_activity_at, datetime('now')) AS updated_at,
                            NULL AS snoozed_until, NULL AS snoozed_by, NULL AS snoozed_at, NULL AS snooze_reason,
                            NULL AS tagged_by_user_id, NULL AS tagged_at,
                            NULL AS assigned_to, NULL AS assigned_at, NULL AS assigned_by,
                            0 AS suppressed, NULL AS suppressed_at, NULL AS suppressed_by,
                            0 AS escalated, NULL AS escalated_at, NULL AS escalated_by,
                            NULL AS regression_watch_until,
                            i.closed_at
                        FROM issues i

CREATE VIEW signals_v29 AS
                        SELECT
                            s.signal_id AS id,
                            COALESCE(s.detector_id, 'unknown') AS source,
                            s.signal_id AS source_id,
                            CASE WHEN s.entity_ref_type = 'client' THEN s.entity_ref_id ELSE NULL END AS client_id,
                            NULL AS engagement_id,
                            CASE
                                WHEN lower(s.signal_type) LIKE '%positive%' OR lower(s.signal_type) LIKE '%good%' THEN 'good'
                                WHEN lower(s.signal_type) LIKE '%risk%' OR lower(s.signal_type) LIKE '%overdue%' OR lower(s.signal_type) LIKE '%negative%' THEN 'bad'
                                ELSE 'neutral'
                            END AS sentiment,
                            s.signal_type,
                            COALESCE(s.value, s.signal_type) AS summary,
                            COALESCE(s.detected_at, datetime('now')) AS observed_at,
                            COALESCE(s.detected_at, datetime('now')) AS ingested_at,
                            '{}' AS evidence,
                            s.resolved_at AS dismissed_at,
                            NULL AS dismissed_by,
                            NULL AS analysis_provider,
                            COALESCE(s.created_at, datetime('now')) AS created_at,
                            COALESCE(s.detected_at, datetime('now')) AS updated_at
                        FROM signals s
