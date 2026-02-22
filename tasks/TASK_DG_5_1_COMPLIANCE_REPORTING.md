# DG-5.1: Compliance Reporting

## Objective
Generate compliance audit reports on demand: data inventory, retention status, access patterns, deletion requests processed, policy violations, and overall governance health.

## Context
Brief 13 adds security audit, Brief 16 adds governance. This task ties it all together into a single compliance report that answers: "Are we handling data responsibly?"

## Implementation

### Compliance Report Structure
```python
@dataclass
class ComplianceReport:
    generated_at: str
    report_period: str  # "2025-01-01 to 2025-12-31"
    report_id: str

    # Data Inventory
    total_tables: int
    classified_tables: int
    unclassified_tables: int
    tables_with_pii: int
    pii_column_count: int
    sensitivity_breakdown: dict[str, int]  # sensitivity → table count

    # Retention Compliance
    tables_with_policy: int
    tables_without_policy: int
    policies_enforced_count: int
    last_enforcement_run: str
    overdue_enforcements: list[str]  # tables past retention but not cleaned
    legal_holds_active: int
    deletion_certificates_issued: int

    # Subject Access
    subject_requests_total: int
    subject_exports_completed: int
    subject_deletions_completed: int
    avg_request_response_time: float  # seconds

    # Access Audit
    api_keys_active: int
    api_keys_expired: int
    total_api_requests: int
    requests_by_role: dict[str, int]
    failed_auth_attempts: int

    # Governance Health Score
    health_score: float  # 0-100
    issues: list[str]  # specific problems found
    recommendations: list[str]
```

### Report Generator
```python
class ComplianceReportGenerator:
    def generate(self, period_start: str, period_end: str) -> ComplianceReport:
        report = ComplianceReport(
            generated_at=utc_now(),
            report_period=f"{period_start} to {period_end}",
            report_id=f"CR-{uuid4().hex[:8]}",
        )
        self._fill_data_inventory(report)
        self._fill_retention_compliance(report)
        self._fill_subject_access(report)
        self._fill_access_audit(report)
        self._compute_health_score(report)
        return report

    def _compute_health_score(self, report: ComplianceReport):
        """Score 0-100 based on governance posture."""
        score = 100
        if report.unclassified_tables > 0:
            score -= min(20, report.unclassified_tables * 2)
        if report.tables_without_policy > 0:
            score -= min(20, report.tables_without_policy * 2)
        if report.overdue_enforcements:
            score -= min(20, len(report.overdue_enforcements) * 5)
        if report.api_keys_expired > 0:
            score -= min(10, report.api_keys_expired * 2)
        if report.failed_auth_attempts > 100:
            score -= 10
        report.health_score = max(0, score)

        # Generate issues and recommendations
        if report.unclassified_tables > 0:
            report.issues.append(f"{report.unclassified_tables} tables unclassified")
            report.recommendations.append("Run 'moh governance classify' to classify all tables")
        if report.overdue_enforcements:
            report.issues.append(f"{len(report.overdue_enforcements)} tables overdue for retention enforcement")
            report.recommendations.append("Run retention enforcement or review policies")
```

### API Endpoints
```
GET /api/v1/governance/compliance-report?from=2025-01-01&to=2025-12-31
  → Generate and return compliance report (admin only)

GET /api/v1/governance/compliance-report/latest
  → Return most recently generated report

GET /api/v1/governance/health
  → Quick health score + top issues (all roles)
```

### Export Formats
- JSON (API response)
- CSV summary (for spreadsheet import)
- Markdown (for documentation / sharing)

## Validation
- [ ] Report includes all 5 sections (inventory, retention, subject access, access audit, health)
- [ ] Health score accurately reflects governance gaps
- [ ] Issues and recommendations are actionable
- [ ] Report generation completes in <10 seconds
- [ ] Historical reports stored and retrievable
- [ ] Admin-only access enforced
- [ ] Markdown export produces readable document

## Files Created
- `lib/governance/compliance.py` — ComplianceReportGenerator, ComplianceReport

## Estimated Effort
Medium — ~200 lines, mostly aggregation queries + health scoring
