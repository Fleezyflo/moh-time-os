# DG-4.1: Retention Policy Enforcement

## Objective
Governance-grade retention enforcement with per-table policies, automatic archival, deletion certificates, legal hold support, and audit trail. Builds on Brief 10's data lifecycle (AO-4.1) with compliance rigor.

## Context
AO-4.1 defines retention windows (collector 365d, bundles 30d, snapshots 90d, signals 180d, logs 30d). This task upgrades that from "cleanup job" to "governed retention system" with per-table config, archive-before-delete, legal holds, and certificates.

## Implementation

### Retention Policy Configuration
```python
@dataclass
class RetentionPolicy:
    table_name: str
    retention_days: int
    archive_before_delete: bool = True
    date_column: str = "created_at"  # column used for age calculation
    legal_hold: bool = False  # overrides deletion when True
    policy_id: str = ""
    last_enforced: str | None = None

# Stored in retention_policies table
DEFAULT_POLICIES = {
    "communications": RetentionPolicy("communications", 730, archive_before_delete=True),
    "tasks": RetentionPolicy("tasks", 730, archive_before_delete=True),
    "calendar_events": RetentionPolicy("calendar_events", 365, archive_before_delete=True),
    "invoices": RetentionPolicy("invoices", 1825, archive_before_delete=True),  # 5 years financial
    "chat_messages": RetentionPolicy("chat_messages", 365, archive_before_delete=True),
    "signals_unified": RetentionPolicy("signals_unified", 180, archive_before_delete=False),
    "change_bundles": RetentionPolicy("change_bundles", 30, archive_before_delete=False),
    "cycle_snapshots": RetentionPolicy("cycle_snapshots", 90, archive_before_delete=False),
    "cycle_logs": RetentionPolicy("cycle_logs", 30, archive_before_delete=False),
    "db_write_audit_v1": RetentionPolicy("db_write_audit_v1", 365, archive_before_delete=True),
    "actions": RetentionPolicy("actions", 365, archive_before_delete=True),
}
```

### Enforcement Engine
```python
class RetentionEnforcer:
    def enforce_all(self, dry_run: bool = False) -> EnforcementReport:
        """Run retention policies on all configured tables."""
        report = EnforcementReport()
        for policy in self.get_active_policies():
            if policy.legal_hold:
                report.skipped.append((policy.table_name, "legal_hold"))
                continue
            result = self.enforce_table(policy, dry_run)
            report.results.append(result)
        report.completed_at = utc_now()
        self.store_report(report)
        return report

    def enforce_table(self, policy: RetentionPolicy, dry_run: bool) -> TableResult:
        """Archive (if configured) then delete expired rows."""
        expired_count = self.count_expired(policy)
        if dry_run:
            return TableResult(policy.table_name, expired_count, archived=0, deleted=0, dry_run=True)

        archived = 0
        if policy.archive_before_delete:
            archived = self.archive_rows(policy)

        deleted = self.delete_expired(policy)
        self.issue_certificate(policy, deleted)
        return TableResult(policy.table_name, expired_count, archived, deleted)
```

### Deletion Certificates
```python
@dataclass
class DeletionCertificate:
    certificate_id: str
    table_name: str
    rows_deleted: int
    date_range: str  # "records older than 2024-02-21"
    policy_id: str
    issued_at: str
    enforced_by: str  # "retention_system" or "manual"

# Stored in deletion_certificates table for compliance audit
```

### Legal Hold
```
POST /api/v1/governance/legal-hold
  body: {"table_name": "communications", "reason": "Pending audit", "hold_until": "2026-06-01"}
  → Sets legal_hold=True, preventing deletion until hold expires or is lifted

DELETE /api/v1/governance/legal-hold/{hold_id}
  → Lifts legal hold (admin only)
```

## Validation
- [ ] All tables have retention policies configured
- [ ] Dry-run mode shows what would be deleted without acting
- [ ] Archive-before-delete creates export before removal
- [ ] Legal hold prevents deletion even when policy triggers
- [ ] Deletion certificates generated for every enforcement run
- [ ] Enforcement report shows per-table results
- [ ] Invoices have 5-year retention (financial compliance)
- [ ] Enforcement runs automatically in maintenance cycle

## Files Created
- `lib/governance/retention.py` — RetentionEnforcer, DeletionCertificate, LegalHold

## Estimated Effort
Medium — ~200 lines, builds on AO-4.1 infrastructure
