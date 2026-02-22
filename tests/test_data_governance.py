"""
Tests for DataGovernance — classification, export, retention, compliance.

Brief 16 (DG), Task DG-1.1
"""

import pytest

from lib.intelligence.data_governance import (
    SENSITIVITY_CONFIDENTIAL,
    SENSITIVITY_INTERNAL,
    SENSITIVITY_PUBLIC,
    SENSITIVITY_RESTRICTED,
    ComplianceReport,
    ComplianceReporter,
    DataCatalog,
    DataExporter,
    DeletionCertificate,
    ExportRequest,
    ExportResult,
    RetentionEnforcer,
    RetentionPolicy,
    SubjectAccessManager,
    SubjectSearchResult,
)


class TestDataCatalog:
    def test_register_table(self):
        catalog = DataCatalog()
        tc = catalog.register_table(
            "clients",
            sensitivity=SENSITIVITY_CONFIDENTIAL,
            contains_pii=True,
            description="Client entities",
        )
        assert tc.table_name == "clients"
        assert tc.sensitivity == SENSITIVITY_CONFIDENTIAL

    def test_invalid_sensitivity(self):
        catalog = DataCatalog()
        with pytest.raises(ValueError, match="Invalid sensitivity"):
            catalog.register_table("test", sensitivity="top_secret")

    def test_classify_column(self):
        catalog = DataCatalog()
        catalog.register_table("clients")
        cc = catalog.classify_column(
            "clients",
            "email",
            sensitivity=SENSITIVITY_RESTRICTED,
            contains_pii=True,
            data_category="contact",
        )
        assert cc.column_name == "email"
        assert cc.contains_pii is True

    def test_classify_column_upgrades_pii(self):
        catalog = DataCatalog()
        catalog.register_table("clients", contains_pii=False)
        catalog.classify_column("clients", "email", contains_pii=True)
        table = catalog.get_table("clients")
        assert table.contains_pii is True

    def test_classify_column_unknown_table(self):
        catalog = DataCatalog()
        assert catalog.classify_column("unknown", "col") is None

    def test_get_pii_tables(self):
        catalog = DataCatalog()
        catalog.register_table("clients", contains_pii=True)
        catalog.register_table("logs", contains_pii=False)
        pii = catalog.get_pii_tables()
        assert len(pii) == 1
        assert pii[0].table_name == "clients"

    def test_get_tables_by_sensitivity(self):
        catalog = DataCatalog()
        catalog.register_table("clients", sensitivity=SENSITIVITY_CONFIDENTIAL)
        catalog.register_table("logs", sensitivity=SENSITIVITY_INTERNAL)
        confidential = catalog.get_tables_by_sensitivity(SENSITIVITY_CONFIDENTIAL)
        assert len(confidential) == 1

    def test_catalog_summary(self):
        catalog = DataCatalog()
        catalog.register_table("clients", sensitivity=SENSITIVITY_CONFIDENTIAL)
        catalog.register_table("logs", sensitivity=SENSITIVITY_INTERNAL)
        summary = catalog.get_catalog_summary()
        assert summary["total_tables"] == 2
        assert SENSITIVITY_CONFIDENTIAL in summary["by_sensitivity"]


class TestDataExporter:
    def test_export_json(self):
        exporter = DataExporter()
        records = [{"id": "1", "name": "Acme"}, {"id": "2", "name": "Beta"}]
        request = ExportRequest(entity_type="clients", format="json")
        result = exporter.export_records(records, request)
        assert result.status == "completed"
        assert result.record_count == 2
        assert '"Acme"' in result.data

    def test_export_csv(self):
        exporter = DataExporter()
        records = [{"id": "1", "name": "Acme"}]
        request = ExportRequest(entity_type="clients", format="csv")
        result = exporter.export_records(records, request)
        assert result.status == "completed"
        assert "id,name" in result.data

    def test_export_empty(self):
        exporter = DataExporter()
        request = ExportRequest(entity_type="clients")
        result = exporter.export_records([], request)
        assert result.record_count == 0

    def test_pii_stripping(self):
        catalog = DataCatalog()
        catalog.register_table("clients")
        catalog.classify_column("clients", "email", contains_pii=True)

        exporter = DataExporter(catalog=catalog)
        records = [{"id": "1", "name": "Acme", "email": "a@b.com"}]
        request = ExportRequest(entity_type="clients", include_pii=False)
        result = exporter.export_records(records, request)
        assert "email" not in result.data

    def test_pii_included(self):
        catalog = DataCatalog()
        catalog.register_table("clients")
        catalog.classify_column("clients", "email", contains_pii=True)

        exporter = DataExporter(catalog=catalog)
        records = [{"id": "1", "email": "a@b.com"}]
        request = ExportRequest(entity_type="clients", include_pii=True)
        result = exporter.export_records(records, request)
        assert "email" in result.data

    def test_to_dict(self):
        exporter = DataExporter()
        request = ExportRequest(entity_type="clients")
        result = exporter.export_records([], request)
        d = result.to_dict()
        assert "status" in d
        assert "request" in d


class TestSubjectAccessManager:
    def test_search_finds_matches(self):
        mgr = SubjectAccessManager()
        data = {
            "clients": [
                {"id": "1", "name": "John Doe", "email": "john@example.com"},
                {"id": "2", "name": "Jane Smith"},
            ],
            "invoices": [
                {"id": "inv1", "client_name": "John Doe", "amount": 5000},
            ],
        }
        result = mgr.search_subject("John Doe", data)
        assert result.tables_with_data == 2
        assert result.total_records == 2

    def test_search_no_matches(self):
        mgr = SubjectAccessManager()
        data = {
            "clients": [{"id": "1", "name": "Alice"}],
        }
        result = mgr.search_subject("Bob", data)
        assert result.tables_with_data == 0
        assert result.total_records == 0

    def test_search_case_insensitive(self):
        mgr = SubjectAccessManager()
        data = {
            "clients": [{"id": "1", "name": "JOHN DOE"}],
        }
        result = mgr.search_subject("john doe", data)
        assert result.total_records == 1

    def test_execute_deletion(self):
        mgr = SubjectAccessManager()
        data = {
            "clients": [{"id": "1", "name": "John Doe"}],
            "invoices": [{"id": "inv1", "client_name": "John Doe"}],
        }
        cert = mgr.execute_deletion("John Doe", data, method="anonymize")
        assert cert.tables_affected == 2
        assert cert.records_anonymized == 2
        assert cert.verification_hash != ""

    def test_deletion_log(self):
        mgr = SubjectAccessManager()
        mgr.execute_deletion("John", {"t": [{"name": "John"}]})
        assert len(mgr.deletion_log) == 1

    def test_to_dict(self):
        result = SubjectSearchResult(subject_identifier="test")
        d = result.to_dict()
        assert "subject_identifier" in d
        assert "tables_searched" in d


class TestRetentionEnforcer:
    def test_set_policy(self):
        enforcer = RetentionEnforcer()
        policy = enforcer.set_policy("logs", retention_days=90, action="delete")
        assert policy.retention_days == 90
        assert policy.action == "delete"

    def test_legal_hold(self):
        enforcer = RetentionEnforcer()
        enforcer.set_policy("logs", retention_days=90)
        assert enforcer.set_legal_hold("logs", True) is True
        assert enforcer.policies["logs"].legal_hold is True

    def test_legal_hold_unknown_table(self):
        enforcer = RetentionEnforcer()
        assert enforcer.set_legal_hold("unknown") is False

    def test_evaluate_retention_archive(self):
        enforcer = RetentionEnforcer()
        enforcer.set_policy("logs", retention_days=30, action="archive")
        records = [
            {"id": "1", "created_at": "2020-01-01T00:00:00"},  # old
            {"id": "2", "created_at": "2099-01-01T00:00:00"},  # future
        ]
        result = enforcer.evaluate_retention("logs", records)
        assert result.records_archived == 1
        assert result.records_deleted == 0

    def test_evaluate_retention_delete(self):
        enforcer = RetentionEnforcer()
        enforcer.set_policy("logs", retention_days=30, action="delete")
        records = [
            {"id": "1", "created_at": "2020-01-01T00:00:00"},
        ]
        result = enforcer.evaluate_retention("logs", records)
        assert result.records_deleted == 1

    def test_evaluate_with_legal_hold(self):
        enforcer = RetentionEnforcer()
        enforcer.set_policy("logs", retention_days=30)
        enforcer.set_legal_hold("logs", True)
        records = [
            {"id": "1", "created_at": "2020-01-01T00:00:00"},
        ]
        result = enforcer.evaluate_retention("logs", records)
        assert result.records_held == 1
        assert result.records_archived == 0

    def test_no_policy(self):
        enforcer = RetentionEnforcer()
        result = enforcer.evaluate_retention("unknown", [{"id": 1}])
        assert result.records_evaluated == 1
        assert result.records_archived == 0

    def test_policy_summary(self):
        enforcer = RetentionEnforcer()
        enforcer.set_policy("a", 30)
        enforcer.set_policy("b", 90)
        summary = enforcer.get_policy_summary()
        assert len(summary) == 2


class TestComplianceReporter:
    def test_compliant_report(self):
        catalog = DataCatalog()
        retention = RetentionEnforcer()
        reporter = ComplianceReporter(catalog=catalog, retention=retention)
        report = reporter.generate_report()
        assert report.overall_status == "compliant"
        assert len(report.policy_violations) == 0

    def test_warning_pii_no_retention(self):
        catalog = DataCatalog()
        catalog.register_table("clients", contains_pii=True)
        retention = RetentionEnforcer()
        reporter = ComplianceReporter(catalog=catalog, retention=retention)
        report = reporter.generate_report()
        assert report.overall_status == "warning"
        assert any("no retention policy" in v for v in report.policy_violations)

    def test_non_compliant_many_violations(self):
        catalog = DataCatalog()
        for i in range(5):
            catalog.register_table(f"table_{i}", contains_pii=True)
        retention = RetentionEnforcer()
        reporter = ComplianceReporter(catalog=catalog, retention=retention)
        report = reporter.generate_report()
        assert report.overall_status == "non_compliant"

    def test_unenforced_policy_violation(self):
        catalog = DataCatalog()
        retention = RetentionEnforcer()
        retention.set_policy("logs", retention_days=30)
        reporter = ComplianceReporter(catalog=catalog, retention=retention)
        report = reporter.generate_report()
        assert any("never enforced" in v for v in report.policy_violations)

    def test_to_dict(self):
        reporter = ComplianceReporter()
        report = reporter.generate_report()
        d = report.to_dict()
        assert "overall_status" in d
        assert "data_inventory" in d
        assert "generated_at" in d
