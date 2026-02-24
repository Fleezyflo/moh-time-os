CREATE TABLE IF NOT EXISTS [clients] (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT,
    tier TEXT DEFAULT 'C',
    health_score REAL,
    type TEXT,
    financial_annual_value REAL,
    financial_ar_outstanding REAL,
    financial_ar_aging TEXT,
    financial_payment_pattern TEXT,
    relationship_health TEXT,
    relationship_trend TEXT,
    relationship_last_interaction TEXT,
    relationship_notes TEXT,
    contacts_json TEXT,
    active_projects_json TEXT,
    xero_contact_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [brands] (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [projects] (
    id TEXT PRIMARY KEY,
    source TEXT,
    source_id TEXT,
    name TEXT NOT NULL,
    name_normalized TEXT,
    brand_id TEXT,
    client_id TEXT,
    is_internal INTEGER NOT NULL DEFAULT 0,
    type TEXT NOT NULL DEFAULT 'project',
    engagement_type TEXT,
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
    context TEXT,
    involvement_type TEXT,
    aliases TEXT,
    recognizers TEXT,
    lane_mapping TEXT,
    routing_rules TEXT,
    delegation_policy TEXT,
    reporting_cadence TEXT,
    sensitivity_profile TEXT,
    enrollment_evidence TEXT,
    enrolled_at TEXT,
    health_reasons TEXT,
    owner_id TEXT,
    owner_name TEXT,
    lane TEXT,
    client TEXT,
    days_to_deadline INTEGER,
    tasks_completed INTEGER,
    tasks_overdue INTEGER,
    tasks_blocked INTEGER,
    completion_pct REAL,
    velocity_trend TEXT,
    next_milestone_date TEXT,
    last_activity_at TEXT,
    start_date TEXT,
    target_end_date TEXT,
    value REAL,
    stakes TEXT,
    description TEXT,
    milestones TEXT,
    team TEXT,
    asana_project_id TEXT,
    proposed_at TEXT
)

CREATE TABLE IF NOT EXISTS [tasks] (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'system',
    source_id TEXT,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    priority INTEGER DEFAULT 50,
    project_id TEXT,
    brand_id TEXT,
    client_id TEXT,
    project_link_status TEXT DEFAULT 'unlinked',
    client_link_status TEXT DEFAULT 'unlinked',
    assignee_id TEXT,
    assignee_raw TEXT,
    lane TEXT DEFAULT 'ops',
    due_date TEXT,
    due_time TEXT,
    duration_min INTEGER DEFAULT 60,
    assignee TEXT,
    project TEXT,
    tags TEXT,
    dependencies TEXT,
    blockers TEXT,
    context TEXT,
    notes TEXT,
    description TEXT DEFAULT '',
    priority_reasons TEXT,
    synced_at TEXT,
    completed_at TEXT,
    section_id TEXT,
    section_name TEXT,
    subtask_count INTEGER DEFAULT 0,
    has_dependencies INTEGER DEFAULT 0,
    attachment_count INTEGER DEFAULT 0,
    story_count INTEGER DEFAULT 0,
    custom_fields_json TEXT,
    urgency INTEGER,
    impact INTEGER,
    sensitivity TEXT,
    effort_min INTEGER,
    effort_max INTEGER,
    waiting_for TEXT,
    deadline_type TEXT,
    dedupe_key TEXT,
    conflict_markers TEXT,
    delegated_by TEXT,
    delegated_at TEXT,
    assignee_name TEXT,
    is_supervised INTEGER DEFAULT 0,
    last_activity_at TEXT,
    stale_days INTEGER,
    scheduled_block_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [events] (
    id TEXT PRIMARY KEY,
    source TEXT,
    source_id TEXT,
    title TEXT,
    start_time TEXT,
    end_time TEXT,
    start_at TEXT,
    end_at TEXT,
    location TEXT,
    attendees TEXT,
    status TEXT DEFAULT 'confirmed',
    prep_required TEXT,
    prep_notes TEXT,
    context TEXT,
    organizer_email TEXT,
    organizer_name TEXT,
    conference_url TEXT,
    conference_type TEXT,
    recurrence TEXT,
    event_type TEXT,
    calendar_id TEXT DEFAULT 'primary',
    attendee_count INTEGER DEFAULT 0,
    accepted_count INTEGER DEFAULT 0,
    declined_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
)

CREATE TABLE IF NOT EXISTS [communications] (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'system',
    source_id TEXT,
    thread_id TEXT,
    from_email TEXT,
    from_domain TEXT,
    to_emails TEXT,
    subject TEXT,
    snippet TEXT,
    body_text TEXT,
    body_text_source TEXT,
    content_hash TEXT,
    received_at TEXT,
    client_id TEXT,
    link_status TEXT DEFAULT 'unlinked',
    priority INTEGER DEFAULT 50,
    requires_response INTEGER DEFAULT 0,
    response_deadline TEXT,
    sentiment TEXT,
    labels TEXT,
    processed INTEGER DEFAULT 0,
    sensitivity TEXT,
    stakeholder_tier TEXT,
    is_read INTEGER,
    is_starred INTEGER,
    importance TEXT,
    has_attachments INTEGER DEFAULT 0,
    attachment_count INTEGER DEFAULT 0,
    label_ids TEXT,
    lane TEXT,
    is_vip INTEGER DEFAULT 0,
    from_name TEXT,
    is_unread INTEGER,
    is_important INTEGER,
    priority_reasons TEXT,
    response_urgency TEXT,
    expected_response_by TEXT,
    processed_at TEXT,
    action_taken TEXT,
    linked_task_id TEXT,
    age_hours REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [people] (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT,
    email TEXT,
    phone TEXT,
    company TEXT,
    role TEXT,
    type TEXT DEFAULT 'external',
    relationship TEXT,
    importance INTEGER DEFAULT 50,
    last_contact TEXT,
    contact_frequency_days INTEGER,
    notes TEXT,
    context TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [invoices] (
    id TEXT PRIMARY KEY,
    source TEXT,
    source_id TEXT,
    external_id TEXT,
    client_id TEXT,
    client_name TEXT,
    brand_id TEXT,
    project_id TEXT,
    amount REAL,
    currency TEXT DEFAULT 'AED',
    issue_date TEXT,
    due_date TEXT,
    paid_date TEXT,
    payment_date TEXT,
    total REAL,
    amount_due REAL,
    issued_at TEXT,
    due_at TEXT,
    paid_at TEXT,
    status TEXT DEFAULT 'pending',
    aging_bucket TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [team_members] (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    asana_gid TEXT,
    default_lane TEXT DEFAULT 'ops',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [client_identities] (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    client_id TEXT NOT NULL REFERENCES clients(id),
    identity_type TEXT NOT NULL,
    identity_value TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [commitments] (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    source_type TEXT NOT NULL DEFAULT 'communication',
    source_id TEXT NOT NULL,
    text TEXT NOT NULL,
    type TEXT NOT NULL,
    confidence REAL,
    deadline TEXT,
    speaker TEXT,
    target TEXT,
    client_id TEXT,
    task_id TEXT,
    status TEXT DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [capacity_lanes] (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT,
    owner TEXT,
    weekly_hours INTEGER DEFAULT 40,
    buffer_pct REAL DEFAULT 0.2,
    color TEXT DEFAULT '#6366f1',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [resolution_queue] (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 2,
    context TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    resolution_action TEXT
)

CREATE TABLE IF NOT EXISTS [pending_actions] (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    idempotency_key TEXT NOT NULL,
    action_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    payload TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    approval_mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    proposed_at TEXT NOT NULL DEFAULT (datetime('now')),
    proposed_by TEXT,
    decided_at TEXT,
    decided_by TEXT,
    executed_at TEXT,
    execution_result TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [asana_project_map] (
    asana_gid TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asana_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [asana_user_map] (
    asana_gid TEXT PRIMARY KEY,
    team_member_id TEXT NOT NULL,
    asana_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [issues_v29] (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'detected',
    severity TEXT NOT NULL,
    client_id TEXT NOT NULL,
    brand_id TEXT,
    engagement_id TEXT,
    title TEXT NOT NULL,
    evidence TEXT,
    evidence_version TEXT DEFAULT 'v1',
    aggregation_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    snoozed_until TEXT,
    snoozed_by TEXT,
    snoozed_at TEXT,
    snooze_reason TEXT,
    tagged_by_user_id TEXT,
    tagged_at TEXT,
    assigned_to TEXT,
    assigned_at TEXT,
    assigned_by TEXT,
    suppressed INTEGER NOT NULL DEFAULT 0,
    suppressed_at TEXT,
    suppressed_by TEXT,
    escalated INTEGER NOT NULL DEFAULT 0,
    escalated_at TEXT,
    escalated_by TEXT,
    regression_watch_until TEXT,
    closed_at TEXT
)

CREATE TABLE IF NOT EXISTS [issue_transitions_v29] (
    id TEXT PRIMARY KEY,
    issue_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    action TEXT,
    actor TEXT,
    reason TEXT,
    transitioned_at TEXT NOT NULL,
    created_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [inbox_items_v29] (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'proposed',
    severity TEXT NOT NULL,
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
    updated_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [signals_v29] (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    client_id TEXT,
    engagement_id TEXT,
    sentiment TEXT,
    signal_type TEXT,
    summary TEXT,
    observed_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    evidence TEXT,
    dismissed_at TEXT,
    dismissed_by TEXT,
    analysis_provider TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [inbox_suppression_rules_v29] (
    id TEXT PRIMARY KEY,
    suppression_key TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS [issues] (
    issue_id TEXT PRIMARY KEY,
    source_proposal_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open',
    primary_ref_type TEXT NOT NULL,
    primary_ref_id TEXT NOT NULL,
    scope_refs TEXT NOT NULL,
    headline TEXT NOT NULL,
    priority INTEGER NOT NULL,
    resolution_criteria TEXT NOT NULL,
    opened_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_activity_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT,
    closed_reason TEXT,
    visibility TEXT NOT NULL DEFAULT 'tagged_only'
)

CREATE TABLE IF NOT EXISTS [signals] (
    signal_id TEXT PRIMARY KEY,
    detector_id TEXT,
    signal_type TEXT NOT NULL,
    entity_ref_type TEXT,
    entity_ref_id TEXT,
    value TEXT,
    detected_at TEXT,
    status TEXT,
    resolved_at TEXT,
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [proposals_v4] (
    id TEXT PRIMARY KEY,
    type TEXT,
    scope_level TEXT DEFAULT 'project',
    scope_name TEXT,
    client_id TEXT,
    client_name TEXT,
    client_tier TEXT,
    brand_id TEXT,
    brand_name TEXT,
    engagement_type TEXT,
    signal_summary_json TEXT,
    score_breakdown_json TEXT,
    affected_task_ids_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [insights] (
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

CREATE TABLE IF NOT EXISTS [decisions] (
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

CREATE TABLE IF NOT EXISTS [notifications] (
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

CREATE TABLE IF NOT EXISTS [actions] (
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

CREATE TABLE IF NOT EXISTS [feedback] (
    id TEXT PRIMARY KEY,
    decision_id TEXT,
    insight_id TEXT,
    action_id TEXT,
    feedback_type TEXT,
    details TEXT,
    created_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [patterns] (
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

CREATE TABLE IF NOT EXISTS [cycle_logs] (
    id TEXT PRIMARY KEY,
    cycle_number INTEGER,
    phase TEXT,
    data TEXT,
    duration_ms REAL,
    created_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [sync_state] (
    source TEXT PRIMARY KEY,
    last_sync TEXT,
    last_success TEXT,
    items_synced INTEGER DEFAULT 0,
    error TEXT
)

CREATE TABLE IF NOT EXISTS [client_projects] (
    client_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    linked_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [client_health_log] (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    health_score INTEGER,
    factors TEXT,
    computed_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [time_debt] (
    id TEXT PRIMARY KEY,
    lane TEXT NOT NULL,
    amount_min INTEGER NOT NULL,
    reason TEXT,
    source_task_id TEXT,
    incurred_at TEXT NOT NULL,
    resolved_at TEXT
)

CREATE TABLE IF NOT EXISTS [asana_custom_fields] (
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

CREATE TABLE IF NOT EXISTS [asana_subtasks] (
    id TEXT PRIMARY KEY,
    parent_task_id TEXT NOT NULL,
    name TEXT NOT NULL,
    assignee_id TEXT,
    assignee_name TEXT,
    completed INTEGER DEFAULT 0,
    due_on TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [asana_sections] (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sort_order INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [asana_stories] (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    type TEXT NOT NULL,
    text TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [asana_task_dependencies] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [asana_portfolios] (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT,
    owner_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [asana_goals] (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT,
    owner_name TEXT,
    status TEXT,
    due_on TEXT,
    html_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [asana_attachments] (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    name TEXT NOT NULL,
    download_url TEXT,
    host TEXT,
    size_bytes INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [gmail_participants] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    role TEXT NOT NULL,
    email TEXT NOT NULL,
    name TEXT
)

CREATE TABLE IF NOT EXISTS [gmail_attachments] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    attachment_id TEXT
)

CREATE TABLE IF NOT EXISTS [gmail_labels] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    label_id TEXT NOT NULL,
    label_name TEXT
)

CREATE TABLE IF NOT EXISTS [calendar_attendees] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT,
    response_status TEXT,
    organizer INTEGER DEFAULT 0,
    self INTEGER DEFAULT 0
)

CREATE TABLE IF NOT EXISTS [calendar_recurrence_rules] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    rrule TEXT NOT NULL
)

CREATE TABLE IF NOT EXISTS [chat_messages] (
    id TEXT PRIMARY KEY,
    space_id TEXT,
    sender_id TEXT,
    sender_name TEXT,
    text TEXT,
    thread_id TEXT,
    thread_reply_count INTEGER DEFAULT 0,
    reaction_count INTEGER DEFAULT 0,
    has_attachment INTEGER DEFAULT 0,
    attachment_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [chat_reactions] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    emoji TEXT NOT NULL,
    user_id TEXT,
    user_name TEXT
)

CREATE TABLE IF NOT EXISTS [chat_attachments] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    name TEXT,
    content_type TEXT,
    source_uri TEXT,
    thumbnail_uri TEXT
)

CREATE TABLE IF NOT EXISTS [chat_space_metadata] (
    space_id TEXT PRIMARY KEY,
    display_name TEXT,
    space_type TEXT,
    threaded INTEGER DEFAULT 0,
    member_count INTEGER,
    created_time TEXT,
    last_synced TEXT
)

CREATE TABLE IF NOT EXISTS [chat_space_members] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    display_name TEXT,
    email TEXT,
    role TEXT
)

CREATE TABLE IF NOT EXISTS [xero_line_items] (
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

CREATE TABLE IF NOT EXISTS [xero_contacts] (
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

CREATE TABLE IF NOT EXISTS [xero_credit_notes] (
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

CREATE TABLE IF NOT EXISTS [xero_bank_transactions] (
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

CREATE TABLE IF NOT EXISTS [xero_tax_rates] (
    name TEXT PRIMARY KEY,
    tax_type TEXT,
    effective_rate REAL,
    status TEXT
)

CREATE TABLE IF NOT EXISTS [governance_audit_log] (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    action TEXT,
    actor TEXT,
    subject_identifier TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TEXT
)

CREATE TABLE IF NOT EXISTS [api_keys] (
    id TEXT PRIMARY KEY,
    key_hash TEXT,
    name TEXT,
    role TEXT,
    created_at TEXT,
    expires_at TEXT,
    last_used_at TEXT,
    is_active INTEGER DEFAULT 1,
    created_by TEXT
)

CREATE TABLE IF NOT EXISTS [subject_access_requests] (
    request_id TEXT PRIMARY KEY,
    subject_identifier TEXT,
    request_type TEXT,
    requested_at TEXT,
    fulfilled_at TEXT,
    status TEXT,
    requested_by TEXT,
    reason TEXT,
    created_at TEXT
)

CREATE TABLE IF NOT EXISTS [write_context_v1] (
    id INTEGER PRIMARY KEY,
    request_id TEXT,
    actor TEXT,
    source TEXT,
    git_sha TEXT
)

CREATE TABLE IF NOT EXISTS [maintenance_mode_v1] (
    id INTEGER PRIMARY KEY,
    flag INTEGER DEFAULT 0
)

CREATE TABLE IF NOT EXISTS [intelligence_events] (
    id TEXT PRIMARY KEY,
    event_type TEXT,
    severity TEXT,
    entity_type TEXT,
    entity_id TEXT,
    event_data TEXT,
    source_module TEXT,
    created_at TEXT,
    consumed_at TEXT,
    consumer TEXT
)

CREATE TABLE IF NOT EXISTS [intelligence_events_archive] (
    id TEXT PRIMARY KEY,
    event_type TEXT,
    severity TEXT,
    entity_type TEXT,
    entity_id TEXT,
    event_data TEXT,
    source_module TEXT,
    created_at TEXT,
    consumed_at TEXT,
    consumer TEXT,
    archived_at TEXT
)

CREATE TABLE IF NOT EXISTS [cost_snapshots] (
    id TEXT PRIMARY KEY,
    computed_at TEXT,
    snapshot_type TEXT,
    entity_id TEXT,
    effort_score REAL,
    efficiency_ratio REAL,
    profitability_band TEXT,
    cost_drivers TEXT,
    data TEXT,
    cycle_id TEXT
)

CREATE TABLE IF NOT EXISTS [pattern_snapshots] (
    id TEXT PRIMARY KEY,
    detected_at TEXT,
    pattern_id TEXT,
    pattern_name TEXT,
    pattern_type TEXT,
    severity TEXT,
    confidence REAL,
    entities_involved TEXT,
    evidence TEXT,
    cycle_id TEXT
)

CREATE TABLE IF NOT EXISTS [digest_history] (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    bucket TEXT,
    digest_json TEXT,
    item_count INTEGER,
    sent_at TEXT
)

CREATE TABLE IF NOT EXISTS [digest_queue] (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    notification_id TEXT,
    event_type TEXT,
    category TEXT,
    severity TEXT,
    bucket TEXT,
    processed INTEGER DEFAULT 0,
    created_at TEXT,
    processed_at TEXT
)

CREATE TABLE IF NOT EXISTS [decision_options] (
    id TEXT PRIMARY KEY,
    decision_id TEXT,
    label TEXT,
    description TEXT,
    data TEXT,
    created_at TEXT
)

CREATE TABLE IF NOT EXISTS [signal_state] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    original_severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    evidence_json TEXT,
    first_detected_at TEXT NOT NULL,
    last_evaluated_at TEXT NOT NULL,
    escalated_at TEXT,
    cleared_at TEXT,
    acknowledged_at TEXT,
    evaluation_count INTEGER DEFAULT 1,
    UNIQUE(signal_id, entity_type, entity_id, status)
)

CREATE TABLE IF NOT EXISTS [artifacts] (
    artifact_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    source TEXT,
    occurred_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

CREATE TABLE IF NOT EXISTS [entity_links] (
    id INTEGER PRIMARY KEY,
    from_artifact_id TEXT,
    to_entity_type TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    method TEXT DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
