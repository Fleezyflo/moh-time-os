CREATE TABLE IF NOT EXISTS clients (
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

CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            source TEXT,
            source_id TEXT,
            title TEXT,
            start_at TEXT,
            end_at TEXT,
            location TEXT,
            attendees TEXT,
            status TEXT DEFAULT 'confirmed',
            prep_required TEXT,
            prep_notes TEXT,
            context TEXT,
            created_at TEXT,
            updated_at TEXT
        )

CREATE TABLE IF NOT EXISTS invoices (
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
