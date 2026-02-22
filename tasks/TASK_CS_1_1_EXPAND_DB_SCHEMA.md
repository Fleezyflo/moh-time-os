# CS-1.1: Expand DB Schema for Full API Coverage

## Objective
Create all new tables and columns needed to store the full data payload from every collector expansion (CS-3.1 through CS-5.2).

## Context
Current schema stores only what was initially needed (~30% of available API fields). Before expanding collectors, the schema must be ready to receive all new data. This is a prerequisite for every subsequent task in Brief 9.

## Implementation

### New Tables

```sql
-- Asana expansions
CREATE TABLE IF NOT EXISTS asana_custom_fields (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_id TEXT,
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL,  -- text, number, enum, multi_enum, date, people
    text_value TEXT,
    number_value REAL,
    enum_value TEXT,
    date_value TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS asana_subtasks (
    id TEXT PRIMARY KEY,
    parent_task_id TEXT NOT NULL,
    name TEXT NOT NULL,
    assignee_id TEXT,
    assignee_name TEXT,
    completed INTEGER DEFAULT 0,
    due_on TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (parent_task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS asana_sections (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sort_order INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS asana_stories (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- comment, system
    text TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS asana_task_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(task_id, depends_on_task_id)
);

CREATE TABLE IF NOT EXISTS asana_portfolios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT,
    owner_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS asana_goals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id TEXT,
    owner_name TEXT,
    status TEXT,
    due_on TEXT,
    html_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS asana_attachments (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    name TEXT NOT NULL,
    download_url TEXT,
    host TEXT,  -- asana, gdrive, dropbox, etc
    size_bytes INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- Gmail expansions
CREATE TABLE IF NOT EXISTS gmail_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- from, to, cc, bcc
    email TEXT NOT NULL,
    name TEXT,
    FOREIGN KEY (message_id) REFERENCES communications(id)
);

CREATE TABLE IF NOT EXISTS gmail_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    attachment_id TEXT,
    FOREIGN KEY (message_id) REFERENCES communications(id)
);

CREATE TABLE IF NOT EXISTS gmail_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    label_id TEXT NOT NULL,
    label_name TEXT,
    FOREIGN KEY (message_id) REFERENCES communications(id)
);

-- Calendar expansions
CREATE TABLE IF NOT EXISTS calendar_attendees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT,
    response_status TEXT,  -- accepted, declined, tentative, needsAction
    organizer INTEGER DEFAULT 0,
    self INTEGER DEFAULT 0,
    FOREIGN KEY (event_id) REFERENCES calendar_events(id)
);

CREATE TABLE IF NOT EXISTS calendar_recurrence_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    rrule TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES calendar_events(id)
);

-- Chat expansions
CREATE TABLE IF NOT EXISTS chat_reactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    emoji TEXT NOT NULL,
    user_id TEXT,
    user_name TEXT
);

CREATE TABLE IF NOT EXISTS chat_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    name TEXT,
    content_type TEXT,
    source_uri TEXT,
    thumbnail_uri TEXT
);

CREATE TABLE IF NOT EXISTS chat_space_metadata (
    space_id TEXT PRIMARY KEY,
    display_name TEXT,
    space_type TEXT,  -- ROOM, DM, GROUP_CHAT
    threaded INTEGER DEFAULT 0,
    member_count INTEGER,
    created_time TEXT,
    last_synced TEXT
);

CREATE TABLE IF NOT EXISTS chat_space_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    space_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    display_name TEXT,
    email TEXT,
    role TEXT,  -- ROLE_MEMBER, ROLE_MANAGER
    UNIQUE(space_id, member_id)
);

-- Xero expansions
CREATE TABLE IF NOT EXISTS xero_line_items (
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
);

CREATE TABLE IF NOT EXISTS xero_contacts (
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
);

CREATE TABLE IF NOT EXISTS xero_credit_notes (
    id TEXT PRIMARY KEY,
    contact_id TEXT,
    date TEXT,
    status TEXT,
    total REAL,
    currency_code TEXT,
    remaining_credit REAL,
    allocated_amount REAL,
    last_synced TEXT
);

CREATE TABLE IF NOT EXISTS xero_bank_transactions (
    id TEXT PRIMARY KEY,
    type TEXT,  -- RECEIVE, SPEND
    contact_id TEXT,
    date TEXT,
    status TEXT,
    total REAL,
    currency_code TEXT,
    reference TEXT,
    last_synced TEXT
);

CREATE TABLE IF NOT EXISTS xero_tax_rates (
    name TEXT PRIMARY KEY,
    tax_type TEXT,
    effective_rate REAL,
    status TEXT
);
```

### Column Additions to Existing Tables

```sql
-- communications table
ALTER TABLE communications ADD COLUMN is_read INTEGER;
ALTER TABLE communications ADD COLUMN is_starred INTEGER;
ALTER TABLE communications ADD COLUMN importance TEXT;  -- high, normal, low
ALTER TABLE communications ADD COLUMN has_attachments INTEGER DEFAULT 0;
ALTER TABLE communications ADD COLUMN attachment_count INTEGER DEFAULT 0;
ALTER TABLE communications ADD COLUMN label_ids TEXT;  -- JSON array

-- calendar_events table
ALTER TABLE calendar_events ADD COLUMN organizer_email TEXT;
ALTER TABLE calendar_events ADD COLUMN organizer_name TEXT;
ALTER TABLE calendar_events ADD COLUMN conference_url TEXT;
ALTER TABLE calendar_events ADD COLUMN conference_type TEXT;  -- hangoutsMeet, zoom, teams
ALTER TABLE calendar_events ADD COLUMN recurrence TEXT;  -- RRULE string
ALTER TABLE calendar_events ADD COLUMN event_type TEXT;  -- default, focusTime, outOfOffice, workingLocation
ALTER TABLE calendar_events ADD COLUMN calendar_id TEXT DEFAULT 'primary';
ALTER TABLE calendar_events ADD COLUMN attendee_count INTEGER DEFAULT 0;
ALTER TABLE calendar_events ADD COLUMN accepted_count INTEGER DEFAULT 0;
ALTER TABLE calendar_events ADD COLUMN declined_count INTEGER DEFAULT 0;

-- tasks table (Asana)
ALTER TABLE tasks ADD COLUMN section_id TEXT;
ALTER TABLE tasks ADD COLUMN section_name TEXT;
ALTER TABLE tasks ADD COLUMN subtask_count INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN has_dependencies INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN attachment_count INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN story_count INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN custom_fields_json TEXT;  -- full JSON for quick access

-- chat_messages or equivalent
ALTER TABLE chat_messages ADD COLUMN thread_id TEXT;
ALTER TABLE chat_messages ADD COLUMN thread_reply_count INTEGER DEFAULT 0;
ALTER TABLE chat_messages ADD COLUMN reaction_count INTEGER DEFAULT 0;
ALTER TABLE chat_messages ADD COLUMN has_attachment INTEGER DEFAULT 0;
ALTER TABLE chat_messages ADD COLUMN attachment_count INTEGER DEFAULT 0;
```

## Approach
1. Read existing schema via `lib/db/schema.py` or migration files to confirm exact current state
2. Create migration function in `lib/db/migrations/` following existing patterns
3. Use `ALTER TABLE` for additive changes (safe, no data loss)
4. Use `CREATE TABLE IF NOT EXISTS` for new tables
5. Add indexes on foreign keys and frequently queried columns
6. Run migration, verify with `.schema` checks

## Validation
- [ ] All new tables exist with correct columns
- [ ] All ALTER TABLE columns added without data loss
- [ ] Foreign key references valid
- [ ] Indexes created on all foreign key columns
- [ ] Existing queries still work (no breaking changes)
- [ ] Migration is idempotent (safe to run twice)

## Files Modified
- `lib/db/migrations/` — new migration file
- `lib/db/schema.py` — if schema definitions are centralized there

## Estimated Effort
Large — ~300 lines of SQL, careful validation needed
