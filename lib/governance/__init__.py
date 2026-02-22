"""
Data Governance module for MOH Time OS.

Provides governance engine, data classification, cataloging, compliance reporting,
export capabilities, and production-grade data retention enforcement.
"""

from lib.governance.anonymizer import Anonymizer
from lib.governance.audit_log import AuditEntry, AuditLog
from lib.governance.data_catalog import DataCatalog
from lib.governance.data_classification import (
    ColumnClassification,
    DataCategory,
    DataClassifier,
    DataSensitivity,
    PatternDetector,
    TableClassification,
)
from lib.governance.data_export import (
    DataExporter,
    ExportFormat,
    ExportRequest,
    ExportResult,
)
from lib.governance.retention_engine import (
    ActionType,
    RetentionAction,
    RetentionEngine,
    RetentionPolicy,
    RetentionReport,
)
from lib.governance.retention_scheduler import RetentionScheduler
from lib.governance.subject_access import (
    DeletionResult,
    RequestStatus,
    RequestType,
    SubjectAccessManager,
    SubjectAccessRequest,
    SubjectDataReport,
)

__all__ = [
    # Classification
    "DataSensitivity",
    "DataCategory",
    "ColumnClassification",
    "TableClassification",
    "DataClassifier",
    "PatternDetector",
    "DataCatalog",
    # Export
    "DataExporter",
    "ExportFormat",
    "ExportRequest",
    "ExportResult",
    # Anonymization
    "Anonymizer",
    # Retention
    "RetentionPolicy",
    "RetentionAction",
    "RetentionReport",
    "ActionType",
    "RetentionEngine",
    "RetentionScheduler",
    # Subject Access & Audit
    "SubjectAccessManager",
    "SubjectAccessRequest",
    "SubjectDataReport",
    "DeletionResult",
    "RequestType",
    "RequestStatus",
    "AuditLog",
    "AuditEntry",
]

# Re-export original GovernanceEngine for backward compat
from lib.governance.governance_engine import GovernanceEngine, get_governance

__all__ += [
    "GovernanceEngine",
    "get_governance",
]
from lib.governance.governance_engine import (
    DomainMode,
    get_domain_mode,
    set_domain_mode,
)

__all__ += [
    "DomainMode",
    "get_domain_mode",
    "set_domain_mode",
]
