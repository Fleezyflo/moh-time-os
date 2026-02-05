-- ==============================================================================
-- 03_SCHEMA_ATLAS.sql — MOH Time OS Complete Database Schema
-- ==============================================================================
-- Phase A Deliverable | Generated: 2026-02-04
-- Database: /Users/molhamhomsi/clawd/moh_time_os/data/state.db
-- 36 Tables + 1 View | SQLite 3.x with WAL mode
-- ==============================================================================

-- ==============================================================================
-- CORE ENTITY TABLES
-- ==============================================================================

-- -----------------------------------------------------------------------------
-- clients: Master client/customer records
-- Source: Xero (via collector), manual entry
-- UI Meaning: Who we work for; anchor for AR, projects, communications
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "clients" (
    -- §12 REQUIRED COLUMNS
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT DEFAULT 'C',                          -- 'A', 'B', 'C' (VIP level)
    health_score REAL,                              -- 0-100 computed health
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- LEGACY/EXTENSION COLUMNS
    type TEXT,                                      -- 'agency_client', 'partner', etc.
    financial_annual_value REAL,                    -- Annual contract value
    financial_ar_outstanding REAL,                  -- Current AR (from Xero sync)
    financial_ar_aging TEXT,                        -- 'current', '30', '60', '90+'
    financial_payment_pattern TEXT,                 -- 'on_time', 'slow', 'problematic'
    relationship_health TEXT,                       -- 'excellent'..'critical'
    relationship_trend TEXT,                        -- 'improving', 'stable', 'declining'
    relationship_last_interaction TEXT,             -- ISO timestamp
    relationship_notes TEXT,
    contacts_json TEXT,                             -- JSON array of contact objects
    active_projects_json TEXT,                      -- JSON array of project refs
    xero_contact_id TEXT                            -- FK to Xero contact
);
CREATE INDEX IF NOT EXISTS idx_clients_tier ON clients(tier);
CREATE INDEX IF NOT EXISTS idx_clients_health ON clients(relationship_health);
CREATE INDEX IF NOT EXISTS idx_clients_xero ON clients(xero_contact_id);

-- -----------------------------------------------------------------------------
-- brands: Client brands (child of clients)
-- Source: Manual setup
-- UI Meaning: Sub-entity of client for project grouping
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brands (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    UNIQUE(client_id, name)
);

-- -----------------------------------------------------------------------------
-- projects: Work projects (linked to brands/clients)
-- Source: Asana (collector), manual
-- UI Meaning: Delivery units; containers for tasks; key to delivery health
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "projects" (
    -- §12 REQUIRED COLUMNS
    id TEXT PRIMARY KEY,
    brand_id TEXT,                                  -- FK to brands
    client_id TEXT,                                 -- FK to clients (derived via brand)
    is_internal INTEGER NOT NULL DEFAULT 0,         -- 1 = internal project (no client)
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'project' CHECK (type IN ('project', 'retainer')),
    status TEXT DEFAULT 'active',                   -- 'active', 'completed', 'on_hold'
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- LEGACY/EXTENSION COLUMNS
    source TEXT,                                    -- 'asana', 'manual'
    source_id TEXT,                                 -- External system ID
    health TEXT DEFAULT 'green',                    -- 'green', 'yellow', 'red'
    owner TEXT,                                     -- Project owner name
    deadline TEXT,                                  -- ISO date
    tasks_total INTEGER DEFAULT 0,                  -- Total task count
    tasks_done INTEGER DEFAULT 0,                   -- Completed task count
    blockers TEXT,                                  -- JSON array of blockers
    next_milestone TEXT,                            -- Next milestone description
    context TEXT,                                   -- JSON context blob
    involvement_type TEXT DEFAULT 'mixed',          -- 'managed', 'advisory', 'mixed'
    aliases TEXT,                                   -- Alternative names (JSON array)
    recognizers TEXT,                               -- Patterns for auto-matching
    lane_mapping TEXT,                              -- Default lane assignments
    routing_rules TEXT,                             -- Routing configuration
    delegation_policy TEXT,                         -- Delegation rules
    reporting_cadence TEXT DEFAULT 'weekly',        -- 'daily', 'weekly', 'monthly'
    sensitivity_profile TEXT,                       -- Sensitivity classification
    enrollment_evidence TEXT,                       -- How project was enrolled
    enrolled_at TEXT,                               -- Enrollment timestamp
    health_reasons TEXT,                            -- JSON reasons for health status
    owner_id TEXT,                                  -- FK to team_members
    owner_name TEXT,                                -- Denormalized owner name
    lane TEXT,                                      -- Default lane
    client TEXT,                                    -- Legacy client name field
    days_to_deadline INTEGER,                       -- Computed: days until deadline
    tasks_completed INTEGER DEFAULT 0,              -- Alias for tasks_done
    tasks_overdue INTEGER DEFAULT 0,                -- Overdue task count
    tasks_blocked INTEGER DEFAULT 0,                -- Blocked task count
    completion_pct REAL DEFAULT 0,                  -- tasks_done/tasks_total * 100
    velocity_trend TEXT,                            -- 'increasing', 'stable', 'decreasing'
    next_milestone_date TEXT,                       -- ISO date
    last_activity_at TEXT,                          -- Last task update
    enrollment_status TEXT,                         -- 'enrolled', 'proposed', 'rejected'
    rule_bundles TEXT,                              -- Applied rule bundles
    start_date TEXT,                                -- Project start
    target_end_date TEXT,                           -- Target completion
    value REAL,                                     -- Project value (AED)
    stakes TEXT,                                    -- Stakes description
    description TEXT,                               -- Project description
    milestones TEXT,                                -- JSON array of milestones
    team TEXT,                                      -- JSON array of team members
    asana_project_id TEXT,                          -- Asana GID
    proposed_at TEXT,                               -- Proposal timestamp
    
    -- FOREIGN KEYS
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);
CREATE INDEX IF NOT EXISTS idx_projects_brand ON projects(brand_id);
CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- -----------------------------------------------------------------------------
-- tasks: Work items from Google Tasks and Asana
-- Source: TasksCollector, AsanaCollector
-- UI Meaning: The work; drives delivery, capacity, and urgency metrics
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "tasks" (
    -- §12 REQUIRED COLUMNS
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,                           -- 'google_tasks', 'asana', 'manual'
    source_id TEXT,                                 -- Original system ID
    title TEXT NOT NULL,
    notes TEXT,                                     -- Task description/notes
    status TEXT DEFAULT 'active',                   -- 'active', 'pending', 'done', 'overdue'
    project_id TEXT,                                -- FK to projects
    brand_id TEXT,                                  -- FK to brands (derived)
    client_id TEXT,                                 -- FK to clients (derived)
    project_link_status TEXT DEFAULT 'unlinked' 
        CHECK (project_link_status IN ('linked', 'partial', 'unlinked')),
    client_link_status TEXT DEFAULT 'unlinked' 
        CHECK (client_link_status IN ('linked', 'unlinked', 'n/a')),
    assignee_id TEXT,                               -- FK to team_members
    assignee_raw TEXT,                              -- Raw assignee string
    lane TEXT DEFAULT 'ops',                        -- Work lane
    due_date TEXT,                                  -- ISO datetime
    duration_min INTEGER DEFAULT 60,                -- Estimated duration (minutes)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- LEGACY/EXTENSION COLUMNS
    project TEXT,                                   -- Legacy: project name/id string
    priority INTEGER DEFAULT 50,                    -- 0-100 priority score
    due_time TEXT,                                  -- Time portion if separate
    assignee TEXT,                                  -- Legacy assignee name
    tags TEXT,                                      -- JSON array of tags
    dependencies TEXT,                              -- JSON array of task IDs
    blockers TEXT,                                  -- JSON array of blockers
    context TEXT,                                   -- JSON context blob
    synced_at TEXT,                                 -- Last sync timestamp
    urgency TEXT DEFAULT 'medium',                  -- 'low', 'medium', 'high', 'critical'
    impact TEXT DEFAULT 'medium',                   -- 'low', 'medium', 'high'
    sensitivity TEXT,                               -- Sensitivity flags
    effort_min INTEGER,                             -- Min effort estimate (minutes)
    effort_max INTEGER,                             -- Max effort estimate (minutes)
    waiting_for TEXT,                               -- Who/what we're waiting for
    deadline_type TEXT DEFAULT 'soft',              -- 'soft', 'hard', 'contractual'
    dedupe_key TEXT,                                -- Deduplication key
    conflict_markers TEXT,                          -- Conflict detection markers
    delegated_by TEXT,                              -- Who delegated this
    delegated_at TEXT,                              -- When delegated
    assignee_name TEXT,                             -- Denormalized assignee name
    priority_reasons TEXT,                          -- JSON reasons for priority
    is_supervised INTEGER DEFAULT 0,                -- 1 if under supervision
    last_activity_at TEXT,                          -- Last update
    stale_days INTEGER DEFAULT 0,                   -- Days since last activity
    scheduled_block_id TEXT,                        -- FK to time_blocks
    
    -- FOREIGN KEYS
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (assignee_id) REFERENCES team_members(id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_client ON tasks(client_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project_link_status ON tasks(project_link_status);
CREATE INDEX IF NOT EXISTS idx_tasks_client_link_status ON tasks(client_link_status);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC);

-- -----------------------------------------------------------------------------
-- communications: Emails from Gmail
-- Source: GmailCollector
-- UI Meaning: External comms; drives response urgency and commitment tracking
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "communications" (
    -- §12 REQUIRED COLUMNS
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,                           -- 'gmail'
    source_id TEXT,                                 -- Gmail thread ID
    thread_id TEXT,                                 -- For threading
    from_email TEXT,                                -- Sender email
    from_domain TEXT,                               -- Extracted domain (derived)
    to_emails TEXT,                                 -- Recipients (JSON array)
    subject TEXT,
    snippet TEXT,                                   -- Preview snippet
    body_text TEXT,                                 -- Full message body
    content_hash TEXT,                              -- SHA256 for dedup
    received_at TEXT,                               -- Email timestamp
    client_id TEXT,                                 -- FK to clients (derived)
    link_status TEXT DEFAULT 'unlinked' 
        CHECK (link_status IN ('linked', 'unlinked')),
    processed INTEGER DEFAULT 0,                    -- 1 if processed for commitments
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- LEGACY/EXTENSION COLUMNS
    priority INTEGER DEFAULT 50,                    -- 0-100 priority
    requires_response INTEGER DEFAULT 0,            -- 1 if response needed
    response_deadline TEXT,                         -- When response is due
    sentiment TEXT,                                 -- 'positive', 'neutral', 'negative'
    labels TEXT,                                    -- Gmail labels (JSON)
    sensitivity TEXT,                               -- Sensitivity classification
    stakeholder_tier TEXT DEFAULT 'significant',    -- 'vip', 'significant', 'routine'
    lane TEXT,                                      -- Routing lane
    is_vip INTEGER DEFAULT 0,                       -- 1 if from VIP
    from_name TEXT,                                 -- Sender display name
    is_unread INTEGER DEFAULT 0,                    -- 1 if unread in Gmail
    is_starred INTEGER DEFAULT 0,                   -- 1 if starred
    is_important INTEGER DEFAULT 0,                 -- 1 if marked important
    priority_reasons TEXT,                          -- JSON reasons
    response_urgency TEXT,                          -- 'immediate', 'today', 'this_week'
    expected_response_by TEXT,                      -- SLA timestamp
    processed_at TEXT,                              -- When processed
    action_taken TEXT,                              -- What action was taken
    linked_task_id TEXT,                            -- FK to tasks if task created
    age_hours REAL,                                 -- Hours since received
    body_text_source TEXT DEFAULT 'unknown',        -- How body was obtained
    
    -- FOREIGN KEY
    FOREIGN KEY (client_id) REFERENCES clients(id)
);
CREATE INDEX IF NOT EXISTS idx_communications_client ON communications(client_id);
CREATE INDEX IF NOT EXISTS idx_communications_processed ON communications(processed);
CREATE INDEX IF NOT EXISTS idx_communications_content_hash ON communications(content_hash);
CREATE INDEX IF NOT EXISTS idx_communications_from_email ON communications(from_email);
CREATE INDEX IF NOT EXISTS idx_communications_from_domain ON communications(from_domain);
CREATE INDEX IF NOT EXISTS idx_communications_priority ON communications(priority DESC);

-- -----------------------------------------------------------------------------
-- invoices: AR invoices from Xero
-- Source: XeroCollector
-- UI Meaning: Money owed; drives cash flow health and collection actions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "invoices" (
    -- §12 REQUIRED COLUMNS
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,                           -- 'xero'
    external_id TEXT NOT NULL,                      -- Invoice number
    client_id TEXT,                                 -- FK to clients
    client_name TEXT,                               -- Denormalized client name
    brand_id TEXT,                                  -- FK to brands (if applicable)
    project_id TEXT,                                -- FK to projects (if applicable)
    amount REAL NOT NULL,                           -- Invoice amount
    currency TEXT NOT NULL,                         -- 'AED', 'USD', etc.
    issue_date TEXT NOT NULL,                       -- Issue date
    due_date TEXT,                                  -- Due date
    status TEXT NOT NULL 
        CHECK (status IN ('draft', 'sent', 'paid', 'overdue', 'void')),
    paid_date TEXT,                                 -- When paid (if paid)
    aging_bucket TEXT 
        CHECK (aging_bucket IN ('current', '1-30', '31-60', '61-90', '90+', NULL)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    -- FOREIGN KEYS
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (brand_id) REFERENCES brands(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_ar ON invoices(status, paid_date) 
    WHERE status IN ('sent', 'overdue') AND paid_date IS NULL;

-- -----------------------------------------------------------------------------
-- commitments: Promises/requests extracted from communications
-- Source: commitment_extractor.py
-- UI Meaning: Tracked obligations; drives relationship and trust
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "commitments" (
    -- §12 REQUIRED COLUMNS
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    source_type TEXT NOT NULL DEFAULT 'communication',  -- 'communication', 'meeting'
    source_id TEXT NOT NULL,                        -- FK to source (communications.id)
    text TEXT NOT NULL,                             -- Commitment text
    type TEXT NOT NULL 
        CHECK (type IN ('promise', 'request')),     -- We promised vs they requested
    confidence REAL,                                -- Extraction confidence 0-1
    deadline TEXT,                                  -- Commitment deadline
    speaker TEXT,                                   -- Who made the commitment
    target TEXT,                                    -- Who it's to
    client_id TEXT,                                 -- FK to clients
    task_id TEXT,                                   -- FK to tasks if task created
    status TEXT DEFAULT 'open' 
        CHECK (status IN ('open', 'fulfilled', 'broken', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    extraction_model TEXT,                          -- Model used for extraction
    extraction_prompt_version TEXT,                 -- Prompt version
    extraction_timestamp TEXT,                      -- When extracted
    
    -- FOREIGN KEYS
    FOREIGN KEY (source_id) REFERENCES communications(id),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_commitments_source ON commitments(source_id);
CREATE INDEX IF NOT EXISTS idx_commitments_client ON commitments(client_id);
CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);

-- ==============================================================================
-- CALENDAR & TIME TABLES
-- ==============================================================================

-- -----------------------------------------------------------------------------
-- events: Calendar events from Google Calendar
-- Source: CalendarCollector
-- UI Meaning: Time commitments; drives capacity and scheduling
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,                           -- 'calendar'
    source_id TEXT,                                 -- Google Calendar event ID
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,                       -- ISO datetime
    end_time TEXT,                                  -- ISO datetime
    location TEXT,
    attendees TEXT,                                 -- JSON array of emails
    status TEXT DEFAULT 'confirmed',                -- 'confirmed', 'tentative', 'cancelled'
    prep_required TEXT,                             -- Legacy prep notes
    context TEXT,                                   -- JSON context blob
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sensitivity TEXT,                               -- 'public', 'private', 'confidential'
    is_system_owned INTEGER DEFAULT 0,              -- 1 if system-created
    linked_task_id TEXT,                            -- FK to tasks
    all_day INTEGER DEFAULT 0,                      -- 1 if all-day event
    has_conflict INTEGER DEFAULT 0,                 -- 1 if conflict detected
    conflict_with TEXT,                             -- Conflicting event ID
    prep_notes TEXT                                 -- JSON prep requirements
);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_time);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date(start_time));
CREATE INDEX IF NOT EXISTS idx_events_conflict ON events(has_conflict);

-- -----------------------------------------------------------------------------
-- time_blocks: Scheduled time blocks for tasks
-- Source: scheduling_engine.py
-- UI Meaning: How time is allocated to work
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS time_blocks (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,                             -- ISO date
    start_time TEXT NOT NULL,                       -- ISO datetime
    end_time TEXT NOT NULL,                         -- ISO datetime
    lane TEXT NOT NULL,                             -- Work lane
    task_id TEXT REFERENCES tasks(id),              -- FK to tasks
    is_protected INTEGER DEFAULT 0,                 -- 1 if can't be moved
    is_buffer INTEGER DEFAULT 0,                    -- 1 if buffer time
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_blocks_date ON time_blocks(date);
CREATE INDEX IF NOT EXISTS idx_blocks_lane ON time_blocks(lane, date);
CREATE INDEX IF NOT EXISTS idx_blocks_task ON time_blocks(task_id);

-- -----------------------------------------------------------------------------
-- capacity_lanes: Work lane definitions
-- Source: Manual setup
-- UI Meaning: Categories of work with capacity limits
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS capacity_lanes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT,
    owner TEXT,                                     -- Default owner
    weekly_hours INTEGER DEFAULT 40,                -- Weekly capacity
    buffer_pct REAL DEFAULT 0.2,                    -- Buffer percentage
    color TEXT DEFAULT '#6366f1',                   -- UI color
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    working_hours INTEGER DEFAULT 1,                -- Working hours per day
    description TEXT
);

-- -----------------------------------------------------------------------------
-- lanes: Alternative lane storage (simpler)
-- Source: lane_assigner.py
-- UI Meaning: Discovered/assigned lanes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lanes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    weekly_hours REAL DEFAULT 0,
    owner TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- time_debt: Accumulated time debt per lane
-- Source: scheduling_engine.py
-- UI Meaning: How much capacity we've borrowed
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS time_debt (
    id TEXT PRIMARY KEY,
    lane TEXT NOT NULL,                             -- FK to capacity_lanes
    amount_min INTEGER NOT NULL,                    -- Debt in minutes
    reason TEXT,
    source_task_id TEXT,                            -- FK to tasks
    incurred_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (lane) REFERENCES capacity_lanes(id)
);
CREATE INDEX IF NOT EXISTS idx_time_debt_lane ON time_debt(lane);
CREATE INDEX IF NOT EXISTS idx_time_debt_unresolved ON time_debt(resolved_at) 
    WHERE resolved_at IS NULL;

-- ==============================================================================
-- TEAM TABLES
-- ==============================================================================

-- -----------------------------------------------------------------------------
-- team_members: Team member registry
-- Source: build_team_registry.py
-- UI Meaning: Who does the work; assignees for tasks
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_members (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    asana_gid TEXT,                                 -- Asana user GID
    default_lane TEXT DEFAULT 'ops',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- -----------------------------------------------------------------------------
-- people: Contact/person records (broader than team)
-- Source: Manual, contacts sync
-- UI Meaning: External contacts, stakeholders
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS people (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    company TEXT,
    role TEXT,
    relationship TEXT,                              -- 'client', 'vendor', 'partner'
    importance INTEGER DEFAULT 50,                  -- 0-100 importance score
    last_contact TEXT,                              -- Last contact timestamp
    contact_frequency_days INTEGER,                 -- Expected contact frequency
    notes TEXT,
    context TEXT,                                   -- JSON context
    priority_tier TEXT DEFAULT 'significant',       -- 'vip', 'significant', 'routine'
    lanes_owned TEXT,                               -- JSON array of lanes
    can_delegate_to INTEGER DEFAULT 0,              -- 1 if can delegate
    escalation_path TEXT,                           -- Who to escalate to
    turnaround_days INTEGER DEFAULT 3,              -- Expected response time
    disclosure_restrictions TEXT,                   -- What can't be shared
    is_vip INTEGER DEFAULT 0,                       -- 1 if VIP
    is_internal INTEGER DEFAULT 0                   -- 1 if internal person
);
CREATE INDEX IF NOT EXISTS idx_people_vip ON people(is_vip);

-- -----------------------------------------------------------------------------
-- team_events: Team calendar events (aggregated)
-- Source: TeamCalendarCollector
-- UI Meaning: Where team time is going
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    owner_email TEXT NOT NULL,                      -- Calendar owner
    owner_name TEXT,
    title TEXT,
    start_time TEXT,
    end_time TEXT,
    attendees TEXT,                                 -- JSON array
    is_external INTEGER DEFAULT 0,                  -- 1 if external attendees
    status TEXT,
    organizer TEXT,
    raw TEXT,                                       -- Full JSON
    created_at TEXT,
    updated_at TEXT,
    client_id TEXT,                                 -- FK to clients
    client_match_source TEXT,                       -- How client was matched
    project_id TEXT,                                -- FK to projects
    project_match_source TEXT,                      -- How project was matched
    actual_attendees TEXT,                          -- Who actually attended
    invited_count INTEGER,
    attended_count INTEGER,
    attendance_rate REAL,                           -- attended/invited
    meet_code TEXT                                  -- Google Meet code
);
CREATE INDEX IF NOT EXISTS idx_team_events_owner ON team_events(owner_email);
CREATE INDEX IF NOT EXISTS idx_team_events_start ON team_events(start_time);

-- -----------------------------------------------------------------------------
-- team_capacity: Computed team capacity
-- Source: TeamCalendarCollector
-- UI Meaning: How loaded is each person
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_capacity (
    email TEXT PRIMARY KEY,
    name TEXT,
    event_count INTEGER,
    meeting_hours REAL,
    external_hours REAL,
    available_hours REAL,
    utilization_pct REAL,
    computed_at TEXT
);

-- -----------------------------------------------------------------------------
-- meet_attendance: Google Meet attendance
-- Source: TeamCalendarCollector
-- UI Meaning: Meeting participation tracking
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meet_attendance (
    id TEXT PRIMARY KEY,
    meeting_code TEXT,
    calendar_event_id TEXT,
    title TEXT,
    organizer TEXT,
    participant_email TEXT,
    duration_seconds INTEGER,
    joined_time TEXT,
    created_at TEXT
);

-- ==============================================================================
-- REFERENCE/LINKING TABLES
-- ==============================================================================

-- -----------------------------------------------------------------------------
-- client_identities: Email/domain → client mapping
-- Source: build_client_identities.py
-- UI Meaning: How we match emails to clients
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS client_identities (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    client_id TEXT NOT NULL,
    identity_type TEXT NOT NULL 
        CHECK (identity_type IN ('email', 'domain')),
    identity_value TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    UNIQUE(identity_type, identity_value)
);

-- -----------------------------------------------------------------------------
-- client_projects: M:N client-project links (legacy)
-- Source: Manual
-- UI Meaning: Project-client relationships
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS client_projects (
    client_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    PRIMARY KEY (client_id, project_id),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_client_projects_client ON client_projects(client_id);
CREATE INDEX IF NOT EXISTS idx_client_projects_project ON client_projects(project_id);

-- -----------------------------------------------------------------------------
-- client_health_log: Historical client health scores
-- Source: health scoring engine
-- UI Meaning: Client health trends over time
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS client_health_log (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    health_score INTEGER,                           -- 0-100
    factors TEXT,                                   -- JSON factors breakdown
    computed_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);
CREATE INDEX IF NOT EXISTS idx_client_health_log_client ON client_health_log(client_id);

-- -----------------------------------------------------------------------------
-- asana_project_map: Asana GID → project mapping
-- Source: AsanaCollector
-- UI Meaning: Link between Asana and internal projects
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asana_project_map (
    asana_gid TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    asana_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- -----------------------------------------------------------------------------
-- asana_user_map: Asana GID → team_member mapping
-- Source: AsanaCollector
-- UI Meaning: Link between Asana users and team members
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asana_user_map (
    asana_gid TEXT PRIMARY KEY,
    team_member_id TEXT NOT NULL,
    asana_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (team_member_id) REFERENCES team_members(id)
);

-- ==============================================================================
-- SYSTEM/OPERATIONAL TABLES
-- ==============================================================================

-- -----------------------------------------------------------------------------
-- resolution_queue: Items needing human resolution
-- Source: resolution_queue.py
-- UI Meaning: The "inbox" of issues requiring attention
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resolution_queue (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    entity_type TEXT NOT NULL,                      -- 'task', 'project', 'client', etc.
    entity_id TEXT NOT NULL,
    issue_type TEXT NOT NULL,                       -- 'missing_link', 'overdue', etc.
    priority INTEGER NOT NULL DEFAULT 2,            -- 1=highest, 5=lowest
    context TEXT,                                   -- JSON context
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    resolved_at TEXT,
    resolved_by TEXT,                               -- Who resolved
    resolution_action TEXT,                         -- What was done
    UNIQUE(entity_type, entity_id, issue_type)
);
CREATE INDEX IF NOT EXISTS idx_resolution_queue_pending 
    ON resolution_queue(priority, created_at) 
    WHERE resolved_at IS NULL;

-- -----------------------------------------------------------------------------
-- resolved_queue_items: Audit of resolved items
-- Source: resolution_queue.py
-- UI Meaning: History of resolutions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resolved_queue_items (
    item_id TEXT PRIMARY KEY,
    resolution TEXT,
    resolved_at TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- pending_actions: Actions awaiting approval
-- Source: governance.py, move_executor.py
-- UI Meaning: System-proposed actions waiting for human approval
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    idempotency_key TEXT UNIQUE NOT NULL,
    action_type TEXT NOT NULL,                      -- 'create_task', 'send_email', etc.
    entity_type TEXT,
    entity_id TEXT,
    payload TEXT NOT NULL,                          -- JSON action payload
    risk_level TEXT NOT NULL,                       -- 'low', 'medium', 'high'
    approval_mode TEXT NOT NULL,                    -- 'auto', 'human'
    status TEXT NOT NULL DEFAULT 'pending',         -- 'pending', 'approved', 'rejected', 'executed'
    proposed_at TEXT NOT NULL DEFAULT (datetime('now')),
    proposed_by TEXT,                               -- System/agent that proposed
    decided_at TEXT,
    decided_by TEXT,
    executed_at TEXT,
    execution_result TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status);

-- -----------------------------------------------------------------------------
-- actions: General action log
-- Source: Various
-- UI Meaning: Actions taken by the system
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS actions (
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
);
CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);

-- -----------------------------------------------------------------------------
-- decisions: Logged system decisions
-- Source: governance.py
-- UI Meaning: Decisions made by the system for audit
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    description TEXT,
    input_data TEXT,                                -- JSON input
    options TEXT,                                   -- JSON options considered
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
);
CREATE INDEX IF NOT EXISTS idx_decisions_pending ON decisions(approved) 
    WHERE approved IS NULL;

-- -----------------------------------------------------------------------------
-- notifications: System notifications
-- Source: Various
-- UI Meaning: Messages sent to the user
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    title TEXT NOT NULL,
    body TEXT,
    action_url TEXT,
    action_data TEXT,
    channels TEXT,                                  -- JSON array of channels
    sent_at TEXT,
    read_at TEXT,
    acted_on_at TEXT,
    created_at TEXT NOT NULL,
    delivery_channel TEXT,                          -- Actual delivery channel
    delivery_id TEXT                                -- External delivery ID
);
CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);

-- -----------------------------------------------------------------------------
-- insights: System-generated insights
-- Source: Various analyzers
-- UI Meaning: Patterns and anomalies detected
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    domain TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    confidence REAL DEFAULT 0.5,
    data TEXT,                                      -- JSON payload
    actionable INTEGER DEFAULT 0,
    action_taken INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

-- -----------------------------------------------------------------------------
-- patterns: Detected behavior patterns
-- Source: Pattern detection
-- UI Meaning: Learned patterns about work
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patterns (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    description TEXT,
    data TEXT,
    confidence REAL DEFAULT 0.5,
    occurrences INTEGER DEFAULT 1,
    last_seen TEXT,
    created_at TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- feedback: User feedback on system outputs
-- Source: UI
-- UI Meaning: How users respond to system suggestions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    decision_id TEXT,
    insight_id TEXT,
    action_id TEXT,
    feedback_type TEXT,                             -- 'helpful', 'not_helpful', 'wrong'
    details TEXT,
    created_at TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- cycle_logs: Autonomous loop execution logs
-- Source: autonomous_loop.py
-- UI Meaning: System health and performance
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cycle_logs (
    id TEXT PRIMARY KEY,
    cycle_number INTEGER,
    phase TEXT,
    data TEXT,
    duration_ms REAL,
    created_at TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- sync_state: Collector sync state
-- Source: Collectors
-- UI Meaning: Data freshness tracking
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_state (
    source TEXT PRIMARY KEY,
    last_sync TEXT,
    last_success TEXT,
    items_synced INTEGER DEFAULT 0,
    error TEXT
);

-- -----------------------------------------------------------------------------
-- dismissed_moves: User-dismissed move suggestions
-- Source: UI
-- UI Meaning: What user doesn't want to see
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dismissed_moves (
    move_key TEXT PRIMARY KEY,
    dismissed_at TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- snoozed_moves: User-snoozed move suggestions
-- Source: UI
-- UI Meaning: What user wants to see later
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS snoozed_moves (
    move_key TEXT PRIMARY KEY,
    snoozed_at TEXT NOT NULL,
    snooze_until TEXT NOT NULL
);

-- -----------------------------------------------------------------------------
-- item_history: Audit trail for items
-- Source: Various
-- UI Meaning: Change history
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS item_history (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES items(id),
    timestamp TEXT NOT NULL,
    change TEXT NOT NULL,
    changed_by TEXT NOT NULL
);

-- ==============================================================================
-- VIEWS
-- ==============================================================================

-- -----------------------------------------------------------------------------
-- items: Unified view over tasks (legacy compatibility)
-- UI Meaning: Normalized task view for generic queries
-- -----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS items AS
SELECT 
    id,
    title AS what,
    status,
    assignee_raw AS owner,
    assignee_id AS owner_id,
    NULL AS counterparty,
    NULL AS counterparty_id,
    due_date AS due,
    waiting_for AS waiting_since,
    client_id,
    project_id,
    context AS context_snapshot_json,
    NULL AS stakes,
    NULL AS history_context,
    source AS source_type,
    source_id AS source_ref,
    created_at AS captured_at,
    NULL AS resolution_outcome,
    NULL AS resolution_notes,
    NULL AS resolved_at,
    created_at,
    updated_at,
    lane,
    urgency,
    impact,
    deadline_type,
    effort_min,
    effort_max,
    dependencies,
    sensitivity AS sensitivity_flags,
    NULL AS recommended_action,
    dedupe_key,
    conflict_markers,
    NULL AS delegated_to,
    delegated_at
FROM tasks;

-- ==============================================================================
-- END OF SCHEMA
-- ==============================================================================
