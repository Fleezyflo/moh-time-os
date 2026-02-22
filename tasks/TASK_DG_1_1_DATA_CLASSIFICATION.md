# DG-1.1: Data Classification & Inventory

## Objective
Classify every table and column in the MOH Time OS database by sensitivity level. Build a queryable data catalog that answers: "What data do we hold, where did it come from, and how sensitive is it?"

## Context
80+ tables, no classification. Some contain PII (emails, names), financial data (invoices, payments), and operational data (tasks, capacity). Need to know what's what before we can export, delete, or report on it.

## Implementation

### Sensitivity Levels
```python
class DataSensitivity(Enum):
    PUBLIC = "public"          # Aggregated metrics, system health
    INTERNAL = "internal"      # Task counts, project names, capacity %
    CONFIDENTIAL = "confidential"  # Client names, team emails, invoice amounts
    RESTRICTED = "restricted"  # Full email bodies, financial details, credentials
```

### Data Catalog Schema
```sql
CREATE TABLE data_catalog (
    id INTEGER PRIMARY KEY,
    table_name TEXT NOT NULL,
    column_name TEXT,  -- NULL = table-level classification
    sensitivity TEXT NOT NULL,
    data_category TEXT,  -- 'pii', 'financial', 'operational', 'system'
    source_system TEXT,  -- 'asana', 'gmail', 'calendar', 'xero', 'chat', 'derived'
    retention_policy TEXT,  -- reference to retention config
    contains_pii BOOLEAN DEFAULT FALSE,
    pii_type TEXT,  -- 'email', 'name', 'phone', 'address', 'financial_id'
    notes TEXT,
    classified_at TEXT NOT NULL,
    classified_by TEXT DEFAULT 'system'
);

CREATE INDEX idx_catalog_table ON data_catalog(table_name);
CREATE INDEX idx_catalog_sensitivity ON data_catalog(sensitivity);
CREATE INDEX idx_catalog_pii ON data_catalog(contains_pii);
```

### Classification Engine
```python
class DataClassifier:
    # Auto-classification rules based on column names and table context
    PII_PATTERNS = {
        "email": ("email", "confidential", "pii", "email"),
        "name": ("name", "confidential", "pii", "name"),
        "phone": ("phone", "confidential", "pii", "phone"),
        "body": ("body|content|text", "restricted", "pii", None),
        "amount": ("amount|total|price|cost", "confidential", "financial", "financial_id"),
    }

    SOURCE_MAP = {
        "communications": "gmail",
        "tasks": "asana",
        "calendar_events": "calendar",
        "chat_messages": "chat",
        "invoices": "xero",
    }

    def classify_database(self) -> list[CatalogEntry]:
        """Scan all tables, apply rules, return classifications."""

    def get_inventory(self, sensitivity: str = None) -> dict:
        """Return summary: tables by sensitivity, PII locations, source breakdown."""
```

### CLI Command
```
moh governance classify          # Run classification on all tables
moh governance inventory         # Print data inventory summary
moh governance inventory --pii   # Show only PII-containing tables/columns
```

## Validation
- [ ] Every table in database has a catalog entry
- [ ] PII columns identified across all collector tables
- [ ] Financial data columns flagged in xero-sourced tables
- [ ] Classification queryable via API: GET /api/v1/governance/catalog
- [ ] Inventory summary shows counts by sensitivity and source

## Files Created
- `lib/governance/catalog.py` — DataClassifier, CatalogEntry, inventory queries

## Estimated Effort
Medium — ~200 lines, mostly classification rules + schema introspection
