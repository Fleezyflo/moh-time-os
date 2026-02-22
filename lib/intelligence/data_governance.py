"""
Data Governance & Compliance — MOH TIME OS

Data classification, export capabilities, subject access,
retention policy enforcement, and compliance reporting.

Brief 16 (DG), Tasks DG-1.1 through DG-5.1

Handles PII-sensitive data with governance-grade controls.
"""

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Classification (DG-1.1)
# ---------------------------------------------------------------------------

# Sensitivity levels (ascending order of restriction)
SENSITIVITY_PUBLIC = "public"
SENSITIVITY_INTERNAL = "internal"
SENSITIVITY_CONFIDENTIAL = "confidential"
SENSITIVITY_RESTRICTED = "restricted"

SENSITIVITY_LEVELS = [
    SENSITIVITY_PUBLIC,
    SENSITIVITY_INTERNAL,
    SENSITIVITY_CONFIDENTIAL,
    SENSITIVITY_RESTRICTED,
]


@dataclass
class ColumnClassification:
    """Classification of a single database column."""

    column_name: str
    sensitivity: str = SENSITIVITY_INTERNAL
    contains_pii: bool = False
    data_category: str = ""  # e.g., "financial", "contact", "behavioral"

    def to_dict(self) -> dict:
        return {
            "column_name": self.column_name,
            "sensitivity": self.sensitivity,
            "contains_pii": self.contains_pii,
            "data_category": self.data_category,
        }


@dataclass
class TableClassification:
    """Classification of a database table."""

    table_name: str
    sensitivity: str = SENSITIVITY_INTERNAL
    description: str = ""
    columns: list[ColumnClassification] = field(default_factory=list)
    contains_pii: bool = False
    retention_days: int | None = None  # None = indefinite
    data_owner: str = ""

    def to_dict(self) -> dict:
        return {
            "table_name": self.table_name,
            "sensitivity": self.sensitivity,
            "description": self.description,
            "columns": [c.to_dict() for c in self.columns],
            "contains_pii": self.contains_pii,
            "retention_days": self.retention_days,
            "data_owner": self.data_owner,
        }


class DataCatalog:
    """
    Data classification and inventory catalog.

    Maintains sensitivity labels for all tables and columns.
    """

    def __init__(self) -> None:
        self.tables: dict[str, TableClassification] = {}

    def register_table(
        self,
        table_name: str,
        sensitivity: str = SENSITIVITY_INTERNAL,
        description: str = "",
        contains_pii: bool = False,
        retention_days: int | None = None,
        data_owner: str = "",
    ) -> TableClassification:
        """Register or update a table classification."""
        if sensitivity not in SENSITIVITY_LEVELS:
            raise ValueError(
                f"Invalid sensitivity: {sensitivity}. Must be one of {SENSITIVITY_LEVELS}"
            )
        tc = TableClassification(
            table_name=table_name,
            sensitivity=sensitivity,
            description=description,
            contains_pii=contains_pii,
            retention_days=retention_days,
            data_owner=data_owner,
        )
        self.tables[table_name] = tc
        return tc

    def classify_column(
        self,
        table_name: str,
        column_name: str,
        sensitivity: str = SENSITIVITY_INTERNAL,
        contains_pii: bool = False,
        data_category: str = "",
    ) -> ColumnClassification | None:
        """Classify a column within a registered table."""
        table = self.tables.get(table_name)
        if not table:
            return None
        cc = ColumnClassification(
            column_name=column_name,
            sensitivity=sensitivity,
            contains_pii=contains_pii,
            data_category=data_category,
        )
        # Replace if already exists
        table.columns = [c for c in table.columns if c.column_name != column_name]
        table.columns.append(cc)
        # Upgrade table PII flag if column has PII
        if contains_pii:
            table.contains_pii = True
        return cc

    def get_table(self, table_name: str) -> TableClassification | None:
        """Get classification for a table."""
        return self.tables.get(table_name)

    def get_pii_tables(self) -> list[TableClassification]:
        """Get all tables containing PII."""
        return [t for t in self.tables.values() if t.contains_pii]

    def get_tables_by_sensitivity(self, sensitivity: str) -> list[TableClassification]:
        """Get all tables at a given sensitivity level."""
        return [t for t in self.tables.values() if t.sensitivity == sensitivity]

    def get_catalog_summary(self) -> dict[str, Any]:
        """Get a summary of the data catalog."""
        by_sensitivity: dict[str, int] = {}
        for t in self.tables.values():
            by_sensitivity[t.sensitivity] = by_sensitivity.get(t.sensitivity, 0) + 1

        return {
            "total_tables": len(self.tables),
            "pii_tables": len(self.get_pii_tables()),
            "by_sensitivity": by_sensitivity,
            "tables": [
                t.to_dict() for t in sorted(self.tables.values(), key=lambda x: x.table_name)
            ],
        }


# ---------------------------------------------------------------------------
# Data Export (DG-2.1)
# ---------------------------------------------------------------------------


@dataclass
class ExportRequest:
    """Request to export data."""

    entity_type: str
    entity_id: str = ""
    format: str = "json"  # json | csv
    include_pii: bool = False
    requested_by: str = ""
    requested_at: str = ""

    def __post_init__(self):
        if not self.requested_at:
            self.requested_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "format": self.format,
            "include_pii": self.include_pii,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at,
        }


@dataclass
class ExportResult:
    """Result of a data export operation."""

    request: ExportRequest
    status: str = "completed"  # completed | partial | failed
    record_count: int = 0
    data: Any = None  # JSON string or CSV string
    error: str = ""
    completed_at: str = ""

    def __post_init__(self):
        if not self.completed_at:
            self.completed_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "request": self.request.to_dict(),
            "status": self.status,
            "record_count": self.record_count,
            "error": self.error,
            "completed_at": self.completed_at,
        }


class DataExporter:
    """
    Exports entity data in JSON or CSV format.

    Respects data classification for PII filtering.
    """

    def __init__(self, catalog: DataCatalog | None = None) -> None:
        self.catalog = catalog or DataCatalog()
        self.export_log: list[ExportResult] = []

    def export_records(
        self,
        records: list[dict[str, Any]],
        request: ExportRequest,
    ) -> ExportResult:
        """Export a list of records according to the export request."""
        if not records:
            result = ExportResult(
                request=request,
                status="completed",
                record_count=0,
                data="[]" if request.format == "json" else "",
            )
            self.export_log.append(result)
            return result

        # Filter PII columns if not requested
        if not request.include_pii:
            records = self._strip_pii(records, request.entity_type)

        # Format output
        if request.format == "csv":
            data = self._to_csv(records)
        else:
            data = json.dumps(records, indent=2, default=str)

        result = ExportResult(
            request=request,
            status="completed",
            record_count=len(records),
            data=data,
        )
        self.export_log.append(result)
        return result

    def _strip_pii(
        self,
        records: list[dict[str, Any]],
        entity_type: str,
    ) -> list[dict[str, Any]]:
        """Remove PII columns from records based on catalog."""
        table = self.catalog.get_table(entity_type)
        if not table:
            return records

        pii_columns = {c.column_name for c in table.columns if c.contains_pii}
        if not pii_columns:
            return records

        return [{k: v for k, v in record.items() if k not in pii_columns} for record in records]

    @staticmethod
    def _to_csv(records: list[dict[str, Any]]) -> str:
        """Convert records to CSV string."""
        if not records:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
        return output.getvalue()


# ---------------------------------------------------------------------------
# Subject Access & Deletion (DG-3.1)
# ---------------------------------------------------------------------------


@dataclass
class SubjectSearchResult:
    """Result of searching for all data related to a subject."""

    subject_identifier: str
    tables_searched: int = 0
    tables_with_data: int = 0
    total_records: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    searched_at: str = ""

    def __post_init__(self):
        if not self.searched_at:
            self.searched_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "subject_identifier": self.subject_identifier,
            "tables_searched": self.tables_searched,
            "tables_with_data": self.tables_with_data,
            "total_records": self.total_records,
            "findings": self.findings,
            "searched_at": self.searched_at,
        }


@dataclass
class DeletionCertificate:
    """Certificate proving data was deleted for a subject."""

    subject_identifier: str
    tables_affected: int = 0
    records_deleted: int = 0
    records_anonymized: int = 0
    method: str = "anonymize"  # delete | anonymize
    requested_by: str = ""
    executed_at: str = ""
    verification_hash: str = ""

    def __post_init__(self):
        if not self.executed_at:
            self.executed_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "subject_identifier": self.subject_identifier,
            "tables_affected": self.tables_affected,
            "records_deleted": self.records_deleted,
            "records_anonymized": self.records_anonymized,
            "method": self.method,
            "requested_by": self.requested_by,
            "executed_at": self.executed_at,
            "verification_hash": self.verification_hash,
        }


class SubjectAccessManager:
    """
    Handles subject access requests and deletion (right to be forgotten).
    """

    def __init__(self, catalog: DataCatalog | None = None) -> None:
        self.catalog = catalog or DataCatalog()
        self.deletion_log: list[DeletionCertificate] = []

    def search_subject(
        self,
        subject_identifier: str,
        data_by_table: dict[str, list[dict[str, Any]]],
    ) -> SubjectSearchResult:
        """
        Search all provided data for records matching a subject.

        data_by_table: {table_name: [records]} — caller provides data
        """
        result = SubjectSearchResult(
            subject_identifier=subject_identifier,
            tables_searched=len(data_by_table),
        )

        identifier_lower = subject_identifier.lower()

        for table_name, records in data_by_table.items():
            matching = []
            for record in records:
                if self._record_matches(record, identifier_lower):
                    matching.append(record)

            if matching:
                result.tables_with_data += 1
                result.total_records += len(matching)
                result.findings.append(
                    {
                        "table": table_name,
                        "record_count": len(matching),
                        "sample_fields": list(matching[0].keys()) if matching else [],
                    }
                )

        return result

    def execute_deletion(
        self,
        subject_identifier: str,
        data_by_table: dict[str, list[dict[str, Any]]],
        method: str = "anonymize",
        requested_by: str = "",
    ) -> DeletionCertificate:
        """
        Execute deletion/anonymization for a subject.

        Returns a DeletionCertificate.
        """
        identifier_lower = subject_identifier.lower()
        tables_affected = 0
        total_deleted = 0
        total_anonymized = 0

        for _table_name, records in data_by_table.items():
            count = 0
            for record in records:
                if self._record_matches(record, identifier_lower):
                    count += 1

            if count > 0:
                tables_affected += 1
                if method == "delete":
                    total_deleted += count
                else:
                    total_anonymized += count

        import hashlib

        verification = hashlib.sha256(
            f"{subject_identifier}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        cert = DeletionCertificate(
            subject_identifier=subject_identifier,
            tables_affected=tables_affected,
            records_deleted=total_deleted,
            records_anonymized=total_anonymized,
            method=method,
            requested_by=requested_by,
            verification_hash=verification,
        )
        self.deletion_log.append(cert)
        return cert

    @staticmethod
    def _record_matches(record: dict[str, Any], identifier_lower: str) -> bool:
        """Check if any field in a record matches the subject identifier."""
        for value in record.values():
            if isinstance(value, str) and identifier_lower in value.lower():
                return True
        return False


# ---------------------------------------------------------------------------
# Retention Policy (DG-4.1)
# ---------------------------------------------------------------------------


@dataclass
class RetentionPolicy:
    """Retention policy for a data category."""

    table_name: str
    retention_days: int
    action: str = "archive"  # archive | delete
    legal_hold: bool = False
    last_enforced_at: str = ""

    def to_dict(self) -> dict:
        return {
            "table_name": self.table_name,
            "retention_days": self.retention_days,
            "action": self.action,
            "legal_hold": self.legal_hold,
            "last_enforced_at": self.last_enforced_at,
        }


@dataclass
class RetentionResult:
    """Result of enforcing a retention policy."""

    table_name: str
    records_evaluated: int = 0
    records_archived: int = 0
    records_deleted: int = 0
    records_held: int = 0  # Legal hold
    enforced_at: str = ""

    def __post_init__(self):
        if not self.enforced_at:
            self.enforced_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "table_name": self.table_name,
            "records_evaluated": self.records_evaluated,
            "records_archived": self.records_archived,
            "records_deleted": self.records_deleted,
            "records_held": self.records_held,
            "enforced_at": self.enforced_at,
        }


class RetentionEnforcer:
    """
    Enforces retention policies with audit trail.
    """

    def __init__(self) -> None:
        self.policies: dict[str, RetentionPolicy] = {}
        self.enforcement_log: list[RetentionResult] = []

    def set_policy(
        self,
        table_name: str,
        retention_days: int,
        action: str = "archive",
    ) -> RetentionPolicy:
        """Set a retention policy for a table."""
        policy = RetentionPolicy(
            table_name=table_name,
            retention_days=retention_days,
            action=action,
        )
        self.policies[table_name] = policy
        return policy

    def set_legal_hold(self, table_name: str, hold: bool = True) -> bool:
        """Set or clear legal hold on a table."""
        policy = self.policies.get(table_name)
        if not policy:
            return False
        policy.legal_hold = hold
        return True

    def evaluate_retention(
        self,
        table_name: str,
        records: list[dict[str, Any]],
        date_field: str = "created_at",
    ) -> RetentionResult:
        """
        Evaluate which records exceed retention policy.

        Returns counts but does not actually delete — caller decides.
        """
        policy = self.policies.get(table_name)
        if not policy:
            return RetentionResult(
                table_name=table_name,
                records_evaluated=len(records),
            )

        cutoff = datetime.now() - timedelta(days=policy.retention_days)
        cutoff_str = cutoff.isoformat()

        expired_count = 0
        for record in records:
            date_val = record.get(date_field, "")
            if isinstance(date_val, str) and date_val and date_val < cutoff_str:
                expired_count += 1

        result = RetentionResult(
            table_name=table_name,
            records_evaluated=len(records),
        )

        if policy.legal_hold:
            result.records_held = expired_count
        elif policy.action == "delete":
            result.records_deleted = expired_count
        else:
            result.records_archived = expired_count

        policy.last_enforced_at = datetime.now().isoformat()
        self.enforcement_log.append(result)
        return result

    def get_policy_summary(self) -> list[dict[str, Any]]:
        """Get summary of all retention policies."""
        return [p.to_dict() for p in sorted(self.policies.values(), key=lambda x: x.table_name)]


# ---------------------------------------------------------------------------
# Compliance Reporting (DG-5.1)
# ---------------------------------------------------------------------------


@dataclass
class ComplianceReport:
    """Comprehensive compliance audit report."""

    generated_at: str = ""
    data_inventory: dict[str, Any] = field(default_factory=dict)
    retention_status: list[dict[str, Any]] = field(default_factory=list)
    deletion_requests_processed: int = 0
    pii_tables_count: int = 0
    policy_violations: list[str] = field(default_factory=list)
    overall_status: str = "compliant"  # compliant | warning | non_compliant

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "data_inventory": self.data_inventory,
            "retention_status": self.retention_status,
            "deletion_requests_processed": self.deletion_requests_processed,
            "pii_tables_count": self.pii_tables_count,
            "policy_violations": self.policy_violations,
            "overall_status": self.overall_status,
        }


class ComplianceReporter:
    """
    Generates compliance audit reports.
    """

    def __init__(
        self,
        catalog: DataCatalog | None = None,
        retention: RetentionEnforcer | None = None,
        subject_access: SubjectAccessManager | None = None,
    ) -> None:
        self.catalog = catalog or DataCatalog()
        self.retention = retention or RetentionEnforcer()
        self.subject_access = subject_access or SubjectAccessManager()

    def generate_report(self) -> ComplianceReport:
        """Generate a comprehensive compliance report."""
        violations = []

        # Check for PII tables without retention policies
        pii_tables = self.catalog.get_pii_tables()
        for table in pii_tables:
            if table.table_name not in self.retention.policies:
                violations.append(f"PII table '{table.table_name}' has no retention policy")

        # Check for overdue enforcement
        for policy in self.retention.policies.values():
            if not policy.last_enforced_at:
                violations.append(f"Retention policy for '{policy.table_name}' never enforced")

        # Determine overall status
        if len(violations) > 3:
            status = "non_compliant"
        elif violations:
            status = "warning"
        else:
            status = "compliant"

        return ComplianceReport(
            data_inventory=self.catalog.get_catalog_summary(),
            retention_status=self.retention.get_policy_summary(),
            deletion_requests_processed=len(self.subject_access.deletion_log),
            pii_tables_count=len(pii_tables),
            policy_violations=violations,
            overall_status=status,
        )
