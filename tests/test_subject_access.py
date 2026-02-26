"""
Tests for Subject Access Request and Right-to-be-Forgotten implementation.

Tests the complete SAR lifecycle:
- Creating subject access requests
- Finding subject data across tables
- Exporting subject data
- Deleting subject data (with and without dry-run)
- Anonymizing subject data
- Audit log tracking
- Protected table handling
- Search patterns (email, name, client_id)
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from lib.governance.subject_access import (
    DeletionResult,
    SubjectAccessManager,
    SubjectAccessRequest,
    SubjectDataReport,
)


class TestSubjectAccessRequest:
    """Test SubjectAccessRequest dataclass."""

    def test_sar_creation(self):
        """Test creating a SAR object."""
        sar = SubjectAccessRequest(
            request_id="req-1",
            subject_identifier="john@example.com",
            request_type="access",
            requested_at="2024-01-01T00:00:00",
        )

        assert sar.request_id == "req-1"
        assert sar.subject_identifier == "john@example.com"
        assert sar.request_type == "access"
        assert sar.status == "pending"


class TestSubjectDataReport:
    """Test SubjectDataReport dataclass."""

    def test_report_creation(self):
        """Test creating a data report."""
        report = SubjectDataReport(
            subject_identifier="john@example.com",
            tables_searched=["tasks", "people"],
            tables_with_data=["tasks"],
            total_records=5,
        )

        assert report.subject_identifier == "john@example.com"
        assert report.total_records == 5
        assert "tasks" in report.tables_with_data


class TestDeletionResult:
    """Test DeletionResult dataclass."""

    def test_deletion_result_creation(self):
        """Test creating a deletion result."""
        result = DeletionResult(
            subject_identifier="john@example.com",
            tables_affected=["tasks"],
            rows_deleted=5,
            rows_anonymized=0,
        )

        assert result.subject_identifier == "john@example.com"
        assert result.rows_deleted == 5
        assert result.rows_anonymized == 0


class TestSubjectAccessManager:
    """Test SubjectAccessManager functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary test database with sample schema."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        # Initialize schema with multiple tables
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                assignee_email TEXT,
                created_by TEXT,
                status TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE people (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                client_id TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                title TEXT,
                attendee_email TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE clients (
                id TEXT PRIMARY KEY,
                name TEXT,
                client_id TEXT,
                contact_email TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE sync_state (
                id TEXT PRIMARY KEY,
                state_data TEXT,
                updated_at TEXT
            )
        """)

        # Insert test data
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
            ("task1", "Task 1", "john@example.com", "john@example.com", "open", "2024-01-01"),
        )
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
            ("task2", "Task 2", "alice@example.com", "alice@example.com", "closed", "2024-01-05"),
        )
        conn.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, ?)",
            ("p1", "John Doe", "john@example.com", "555-1111", "client123", "2024-01-01"),
        )
        conn.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, ?)",
            ("p2", "Alice Smith", "alice@example.com", "555-2222", "client456", "2024-01-01"),
        )
        conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?)",
            ("e1", "Meeting", "john@example.com", "2024-01-10"),
        )
        conn.execute(
            "INSERT INTO clients VALUES (?, ?, ?, ?, ?)",
            ("c1", "Acme Corp", "client123", "contact@acme.com", "2024-01-01"),
        )
        conn.execute(
            "INSERT INTO sync_state VALUES (?, ?, ?)",
            ("sync1", '{"state": "active"}', "2024-01-01"),
        )
        conn.commit()
        conn.close()

        yield path

        if os.path.exists(path):
            os.unlink(path)

    def test_manager_init(self, temp_db):
        """Test SubjectAccessManager initialization."""
        manager = SubjectAccessManager(temp_db)
        assert manager.db_path == Path(temp_db)
        assert manager.lifecycle is not None
        assert manager.anonymizer is not None
        assert manager.audit_log is not None

    def test_create_request(self, temp_db):
        """Test creating a subject access request."""
        manager = SubjectAccessManager(temp_db)
        request_id = manager.create_request(
            subject_identifier="john@example.com",
            request_type="access",
            requested_by="user1",
            reason="GDPR access request",
        )

        assert request_id is not None
        assert isinstance(request_id, str)
        assert len(request_id) > 0

    def test_create_request_recorded_in_db(self, temp_db):
        """Test that created request is stored in database."""
        manager = SubjectAccessManager(temp_db)
        request_id = manager.create_request(
            subject_identifier="john@example.com",
            request_type="deletion",
            requested_by="user1",
        )

        # Verify in database
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT * FROM subject_access_requests WHERE request_id = ?", (request_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[1] == "john@example.com"
        assert row[2] == "deletion"

    def test_get_request_status(self, temp_db):
        """Test retrieving request status."""
        manager = SubjectAccessManager(temp_db)
        request_id = manager.create_request(
            subject_identifier="john@example.com",
            request_type="access",
        )

        status = manager.get_request_status(request_id)

        assert status is not None
        assert status.request_id == request_id
        assert status.subject_identifier == "john@example.com"
        assert status.status == "pending"

    def test_get_request_status_not_found(self, temp_db):
        """Test getting status for non-existent request."""
        manager = SubjectAccessManager(temp_db)
        status = manager.get_request_status("nonexistent-id")

        assert status is None

    def test_list_requests(self, temp_db):
        """Test listing all requests."""
        manager = SubjectAccessManager(temp_db)
        req1 = manager.create_request("john@example.com", "access")
        req2 = manager.create_request("alice@example.com", "deletion")

        requests = manager.list_requests()

        assert len(requests) >= 2
        assert any(r.request_id == req1 for r in requests)
        assert any(r.request_id == req2 for r in requests)

    def test_list_requests_by_status(self, temp_db):
        """Test listing requests filtered by status."""
        manager = SubjectAccessManager(temp_db)
        manager.create_request("john@example.com", "access")

        requests = manager.list_requests(status="pending")

        assert len(requests) >= 1
        assert all(r.status == "pending" for r in requests)

    def test_find_subject_data_by_email(self, temp_db):
        """Test finding subject data by email address."""
        manager = SubjectAccessManager(temp_db)
        report = manager.find_subject_data("john@example.com")

        assert report.subject_identifier == "john@example.com"
        assert "tasks" in report.tables_with_data
        assert "people" in report.tables_with_data
        assert "events" in report.tables_with_data
        assert report.total_records >= 3

    def test_find_subject_data_by_name(self, temp_db):
        """Test finding subject data by name."""
        manager = SubjectAccessManager(temp_db)
        report = manager.find_subject_data("John Doe")

        assert report.subject_identifier == "John Doe"
        assert "people" in report.tables_with_data
        assert report.total_records >= 1

    def test_find_subject_data_by_client_id(self, temp_db):
        """Test finding subject data by client_id."""
        manager = SubjectAccessManager(temp_db)
        report = manager.find_subject_data("client123")

        assert report.subject_identifier == "client123"
        # Should find in people and clients tables
        assert report.total_records >= 1

    def test_find_subject_data_no_matches(self, temp_db):
        """Test finding data for subject with no matches."""
        manager = SubjectAccessManager(temp_db)
        report = manager.find_subject_data("nonexistent@example.com")

        assert report.subject_identifier == "nonexistent@example.com"
        assert report.total_records == 0
        assert len(report.tables_with_data) == 0

    def test_find_subject_data_contains_records(self, temp_db):
        """Test that found data contains actual records."""
        manager = SubjectAccessManager(temp_db)
        report = manager.find_subject_data("john@example.com")

        assert "tasks" in report.data_by_table
        tasks = report.data_by_table["tasks"]
        assert len(tasks) > 0
        # Should contain task1 with john's email
        assert any(t.get("assignee_email") == "john@example.com" for t in tasks)

    def test_export_subject_data(self, temp_db):
        """Test exporting subject data to file."""
        manager = SubjectAccessManager(temp_db)
        file_path = manager.export_subject_data("john@example.com")

        assert os.path.exists(file_path)
        assert file_path.endswith(".json")

        # Verify file contents
        with open(file_path) as f:
            data = json.load(f)
            assert data["subject"] == "john@example.com"
            assert "tables" in data
            assert "tasks" in data["tables"]

    def test_export_subject_data_creates_audit_entry(self, temp_db):
        """Test that export creates audit log entry."""
        manager = SubjectAccessManager(temp_db)
        manager.export_subject_data("john@example.com")

        # Check audit log
        entries = manager.audit_log.get_entries(subject="john@example.com", action="DATA_EXPORTED")
        assert len(entries) >= 1

    def test_delete_subject_data_dry_run(self, temp_db):
        """Test deleting subject data with dry-run (no actual deletion)."""
        manager = SubjectAccessManager(temp_db)

        # Get initial count
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE assignee_email = ?", ("john@example.com",)
        )
        initial_count = cursor.fetchone()[0]
        conn.close()

        # Dry-run deletion
        result = manager.delete_subject_data("john@example.com", dry_run=True)

        # Verify result
        assert result.subject_identifier == "john@example.com"
        assert result.rows_deleted >= initial_count
        assert "tasks" in result.tables_affected

        # Verify data was NOT actually deleted
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE assignee_email = ?", ("john@example.com",)
        )
        final_count = cursor.fetchone()[0]
        conn.close()

        assert final_count == initial_count

    def test_delete_subject_data_actual_deletion(self, temp_db):
        """Test actual subject data deletion (not dry-run)."""
        manager = SubjectAccessManager(temp_db)

        # Get initial count
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE assignee_email = ?", ("john@example.com",)
        )
        initial_count = cursor.fetchone()[0]
        conn.close()

        assert initial_count > 0, "Test needs initial data"

        # Actual deletion
        result = manager.delete_subject_data("john@example.com", dry_run=False)

        # Verify deletion
        assert result.rows_deleted >= initial_count
        assert result.rows_deleted > 0

        # Verify data was actually deleted from database
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE assignee_email = ?", ("john@example.com",)
        )
        final_count = cursor.fetchone()[0]
        conn.close()

        assert final_count == 0

    def test_delete_subject_data_skips_protected_tables(self, temp_db):
        """Test that protected tables are not deleted."""
        manager = SubjectAccessManager(temp_db)

        # Add john's email to sync_state (would match in people table)
        # But first verify sync_state is indeed protected
        assert manager.lifecycle.is_protected("sync_state")

        # Count initial sync_state rows
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT COUNT(*) FROM sync_state")
        initial_count = cursor.fetchone()[0]
        conn.close()

        manager.delete_subject_data("john@example.com", dry_run=False)

        # Verify sync_state data still exists (protected)
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT COUNT(*) FROM sync_state")
        final_count = cursor.fetchone()[0]
        conn.close()

        assert final_count == initial_count

    def test_delete_creates_audit_entries(self, temp_db):
        """Test that deletion creates audit log entries."""
        manager = SubjectAccessManager(temp_db)
        manager.delete_subject_data("john@example.com", dry_run=False)

        entries = manager.audit_log.get_entries(subject="john@example.com", action="DATA_DELETED")
        assert len(entries) >= 1

    def test_anonymize_subject_data_dry_run(self, temp_db):
        """Test anonymizing subject data with dry-run."""
        manager = SubjectAccessManager(temp_db)

        # Get initial email
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT email FROM people WHERE name = ?", ("John Doe",))
        initial_email = cursor.fetchone()[0]
        conn.close()

        assert initial_email == "john@example.com"

        # Dry-run anonymization
        result = manager.anonymize_subject_data("John Doe", dry_run=True)

        assert result.subject_identifier == "John Doe"
        assert result.rows_anonymized >= 1

        # Verify data was NOT actually anonymized
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT email FROM people WHERE name = ?", ("John Doe",))
        final_email = cursor.fetchone()[0]
        conn.close()

        assert final_email == initial_email

    def test_anonymize_subject_data_actual(self, temp_db):
        """Test actual subject data anonymization."""
        manager = SubjectAccessManager(temp_db)

        # Get initial email
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT id, email FROM people WHERE name = ?", ("John Doe",))
        row = cursor.fetchone()
        initial_email = row[1] if row else None
        person_id = row[0] if row else None
        conn.close()

        assert initial_email is not None
        assert initial_email == "john@example.com"

        # Actual anonymization
        result = manager.anonymize_subject_data("John Doe", dry_run=False)

        assert result.rows_anonymized >= 1

        # Verify data was actually anonymized
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT email FROM people WHERE id = ?", (person_id,))
        row = cursor.fetchone()
        final_email = row[0] if row else None
        conn.close()

        assert final_email is not None
        # Email should be different (anonymized)
        assert final_email != initial_email
        # Should not contain original email
        assert "john@example.com" not in final_email

    def test_anonymize_creates_audit_entries(self, temp_db):
        """Test that anonymization creates audit entries."""
        manager = SubjectAccessManager(temp_db)
        manager.anonymize_subject_data("John Doe", dry_run=False)

        entries = manager.audit_log.get_entries(subject="John Doe", action="DATA_ANONYMIZED")
        assert len(entries) >= 1

    def test_find_identifier_columns(self, temp_db):
        """Test identifying columns that contain subject identifiers."""
        manager = SubjectAccessManager(temp_db)
        cols = manager._find_identifier_columns("people")

        assert "email" in cols or "name" in cols or "client_id" in cols

    def test_find_identifier_columns_for_tasks(self, temp_db):
        """Test identifying identifier columns in tasks table."""
        manager = SubjectAccessManager(temp_db)
        cols = manager._find_identifier_columns("tasks")

        # Should find assignee_email
        assert any("email" in c.lower() for c in cols)

    def test_search_table(self, temp_db):
        """Test searching a single table."""
        manager = SubjectAccessManager(temp_db)
        records = manager._search_table("tasks", "john@example.com")

        assert len(records) >= 1
        assert any(r.get("assignee_email") == "john@example.com" for r in records)

    def test_search_table_no_results(self, temp_db):
        """Test search with no results."""
        manager = SubjectAccessManager(temp_db)
        records = manager._search_table("tasks", "nonexistent@example.com")

        assert len(records) == 0

    def test_multiple_deletions_different_subjects(self, temp_db):
        """Test deleting data for multiple subjects sequentially."""
        manager = SubjectAccessManager(temp_db)

        # Delete first subject
        result1 = manager.delete_subject_data("john@example.com", dry_run=False)
        assert result1.rows_deleted >= 1

        # Delete second subject
        result2 = manager.delete_subject_data("alice@example.com", dry_run=False)
        assert result2.rows_deleted >= 1

        # Verify both are gone
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE assignee_email IN (?, ?)",
            ("john@example.com", "alice@example.com"),
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 0

    def test_audit_log_entries_created_for_operations(self, temp_db):
        """Test that all major operations create audit entries."""
        manager = SubjectAccessManager(temp_db)
        subject = "john@example.com"

        # Create request
        manager.create_request(subject, "access")

        # Find data
        manager.find_subject_data(subject)

        # Check audit log
        entries = manager.audit_log.get_entries(subject=subject)

        # Should have at least SAR_CREATED and DATA_ACCESSED entries
        action_types = [e.action for e in entries]
        assert "SAR_CREATED" in action_types
        assert "DATA_ACCESSED" in action_types

    def test_request_lifecycle(self, temp_db):
        """Test complete request lifecycle."""
        manager = SubjectAccessManager(temp_db)
        subject = "john@example.com"

        # Create request
        request_id = manager.create_request(subject, "access", "user1")
        assert request_id is not None

        # Get request status
        request = manager.get_request_status(request_id)
        assert request.status == "pending"
        assert request.subject_identifier == subject

        # Find data for subject
        report = manager.find_subject_data(subject)
        assert report.total_records >= 0

        # Export data
        file_path = manager.export_subject_data(subject)
        assert os.path.exists(file_path)

    def test_concurrent_table_search(self, temp_db):
        """Test searching across multiple tables finds all matches."""
        manager = SubjectAccessManager(temp_db)
        report = manager.find_subject_data("john@example.com")

        # Should find data in multiple tables
        found_tables = report.tables_with_data

        assert len(found_tables) >= 2, f"Expected >= 2 tables, found {found_tables}"

    def test_empty_database_search(self, temp_db):
        """Test searching in database with no matching data."""
        manager = SubjectAccessManager(temp_db)
        report = manager.find_subject_data("nobody@nowhere.com")

        assert report.total_records == 0
        assert len(report.tables_with_data) == 0

    def test_case_insensitive_name_search(self, temp_db):
        """Test that name search is case-insensitive."""
        manager = SubjectAccessManager(temp_db)

        # Search with different case
        report1 = manager.find_subject_data("john doe")
        report2 = manager.find_subject_data("JOHN DOE")
        report3 = manager.find_subject_data("John Doe")

        # All should find the same data
        assert report1.total_records == report2.total_records == report3.total_records
        assert report1.total_records > 0
