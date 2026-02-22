# DG-3.1: Subject Access & Deletion

## Objective
Implement "right to be forgotten" and subject access requests. Given a person identifier (email, name, client name), find all related records across all tables, export them, then anonymize or delete with verification.

## Context
System holds data across 80+ tables from 5 external sources. A single person's data might appear in: communications (sender/recipient), tasks (assignee), calendar_events (attendee), invoices (client), chat_messages (sender), and derived tables (patterns, signals, health scores). Need cross-table entity resolution.

## Implementation

### Entity Resolution
```python
class SubjectResolver:
    """Find all records related to a person across all tables."""

    def resolve(self, identifier: str) -> SubjectProfile:
        """
        identifier: email, name, or client name
        Returns: SubjectProfile with all table references
        """
        profile = SubjectProfile(identifier=identifier)

        # Direct matches
        profile.communications = self._find_in_communications(identifier)
        profile.tasks = self._find_in_tasks(identifier)
        profile.calendar_events = self._find_in_calendar(identifier)
        profile.invoices = self._find_in_invoices(identifier)
        profile.chat_messages = self._find_in_chat(identifier)

        # Derived data
        profile.patterns = self._find_in_patterns(identifier)
        profile.signals = self._find_in_signals(identifier)
        profile.health_scores = self._find_in_health(identifier)
        profile.actions = self._find_in_actions(identifier)

        profile.total_records = sum(len(v) for v in profile.__dict__.values() if isinstance(v, list))
        return profile
```

### Anonymization Engine
```python
class DataAnonymizer:
    """Anonymize or delete personal data across all tables."""

    ANONYMIZE_STRATEGIES = {
        "email": lambda v: f"anon_{hash(v)[:8]}@redacted.local",
        "name": lambda v: f"Person_{hash(v)[:8]}",
        "body": lambda v: "[REDACTED]",
        "phone": lambda v: "000-000-0000",
        "amount": lambda v: v,  # financial amounts kept for aggregate accuracy
    }

    def anonymize_subject(self, profile: SubjectProfile, mode: str = "anonymize") -> DeletionReport:
        """
        mode: 'anonymize' (replace PII with placeholders) or 'delete' (remove rows)
        Returns: DeletionReport with counts per table and verification status
        """

    def verify_deletion(self, identifier: str) -> VerificationResult:
        """Re-run subject search to confirm no traces remain."""
```

### Deletion Report
```python
@dataclass
class DeletionReport:
    identifier: str
    mode: str  # "anonymize" or "delete"
    requested_at: str
    completed_at: str
    tables_affected: dict[str, int]  # table_name → row count
    total_records_processed: int
    verification_passed: bool
    certificate_id: str  # unique ID for compliance records
```

### API Endpoints
```
POST /api/v1/governance/subject-search
  body: {"identifier": "john@example.com"}
  → returns SubjectProfile with record counts per table

POST /api/v1/governance/subject-export
  body: {"identifier": "john@example.com"}
  → returns full data export for that subject (JSON)

POST /api/v1/governance/subject-delete
  body: {"identifier": "john@example.com", "mode": "anonymize", "confirm": true}
  → executes anonymization/deletion, returns DeletionReport
  → requires admin role + confirmation flag
```

## Validation
- [ ] Subject search finds records across all 5 source systems
- [ ] Subject export produces complete data package
- [ ] Anonymization replaces PII but preserves aggregate data
- [ ] Deletion removes all records for subject
- [ ] Verification confirms no traces remain post-deletion
- [ ] Deletion report generated with certificate ID
- [ ] Audit log captures all subject access/deletion requests
- [ ] Admin role required for deletion operations

## Files Created
- `lib/governance/subject_access.py` — SubjectResolver, DataAnonymizer, DeletionReport

## Estimated Effort
Large — ~250 lines, cross-table resolution is the complexity driver
