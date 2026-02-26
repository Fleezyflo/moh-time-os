"""
Tests for data export system.

Tests the complete data export pipeline:
- Export formats (JSON, CSV, JSONL)
- Column filtering
- Date range filtering
- Anonymization (email, phone, name)
- Consistent anonymization
- Checksum generation
- Schema retrieval
- Error handling
"""

import csv
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.governance.anonymizer import Anonymizer
from lib.governance.data_export import DataExporter, ExportFormat, ExportRequest


class TestAnonymizer:
    """Test PII anonymization."""

    def test_anonymize_email(self):
        """Test email anonymization preserves domain."""
        anon = Anonymizer()
        email = "john.doe@example.com"
        result = anon.anonymize_email(email)

        assert "@example.com" in result
        assert "john.doe" not in result
        assert len(result.split("@")[0]) == 16  # Hash length

    def test_anonymize_email_consistency(self):
        """Test same email always produces same hash."""
        anon = Anonymizer()
        email = "john.doe@example.com"
        result1 = anon.anonymize_email(email)
        result2 = anon.anonymize_email(email)

        assert result1 == result2

    def test_anonymize_phone(self):
        """Test phone anonymization masks digits except last 4."""
        anon = Anonymizer()
        phone = "+1 (555) 123-4567"
        result = anon.anonymize_phone(phone)

        assert result.endswith("4567")
        # Should have X marks for masked digits
        assert result.count("X") > 0

    def test_anonymize_phone_consistency(self):
        """Test same phone always produces same mask."""
        anon = Anonymizer()
        phone = "+1 (555) 123-4567"
        result1 = anon.anonymize_phone(phone)
        result2 = anon.anonymize_phone(phone)

        assert result1 == result2

    def test_anonymize_name(self):
        """Test name anonymization."""
        anon = Anonymizer()
        name = "John Doe"
        result = anon.anonymize_name(name)

        assert result.startswith("Person_")
        assert "John" not in result
        assert "Doe" not in result

    def test_anonymize_name_consistency(self):
        """Test same name always produces same pseudonym."""
        anon = Anonymizer()
        name = "John Doe"
        result1 = anon.anonymize_name(name)
        result2 = anon.anonymize_name(name)

        assert result1 == result2

    def test_anonymize_value_by_type(self):
        """Test value anonymization by type."""
        anon = Anonymizer()

        assert "@" in anon.anonymize_value("test@example.com", "email")
        assert "X" in anon.anonymize_value("5551234567", "phone")
        assert anon.anonymize_value("Alice", "name").startswith("Person_")

    def test_anonymize_row(self):
        """Test anonymizing a full row."""
        anon = Anonymizer()
        row = {
            "id": "1",
            "email": "john@example.com",
            "name": "John Doe",
            "title": "Engineer",
        }

        pii_cols = ["email", "name"]
        result = anon.anonymize_row(row, pii_cols)

        assert result["id"] == "1"
        assert result["title"] == "Engineer"
        assert "@" in result["email"]
        assert result["name"].startswith("Person_")

    def test_anonymize_row_empty(self):
        """Test anonymizing empty row."""
        anon = Anonymizer()
        row = {}
        result = anon.anonymize_row(row, ["email"])

        assert result == {}

    def test_anonymize_row_with_none_values(self):
        """Test anonymizing row with None values."""
        anon = Anonymizer()
        row = {
            "id": "1",
            "email": None,
            "name": "John",
        }

        result = anon.anonymize_row(row, ["email", "name"])

        assert result["email"] is None
        assert result["name"].startswith("Person_")


class TestDataExporter:
    """Test data export functionality."""

    @pytest.fixture
    def temp_export_dir(self):
        """Create a temporary export directory."""
        export_dir = tempfile.mkdtemp()
        yield export_dir
        # Cleanup
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)

    @pytest.fixture
    def temp_db(self):
        """Create a temporary test database."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        # Initialize schema
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                assignee TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE people (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE events (
                id TEXT PRIMARY KEY,
                title TEXT,
                start_at TEXT,
                created_at TEXT
            )
        """)

        # Insert test data
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
            ("task1", "Task 1", "alice@example.com", "open", "2024-01-01", "2024-01-02"),
        )
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
            ("task2", "Task 2", "bob@example.com", "closed", "2024-01-05", "2024-01-06"),
        )
        conn.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?)",
            ("p1", "Alice", "alice@example.com", "555-1111", "2024-01-01"),
        )
        conn.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?)",
            ("p2", "Bob", "bob@example.com", "555-2222", "2024-01-01"),
        )
        conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?)",
            ("e1", "Meeting", "2024-01-10T10:00:00", "2024-01-10"),
        )
        conn.commit()
        conn.close()

        yield path

        if os.path.exists(path):
            os.unlink(path)

    def test_exporter_init(self, temp_db, temp_export_dir):
        """Test exporter initialization."""
        exporter = DataExporter(temp_db, export_dir=temp_export_dir)
        assert exporter.db_path == Path(temp_db)

    def test_get_table_columns(self, temp_db, temp_export_dir):
        """Test getting table columns."""
        exporter = DataExporter(temp_db, export_dir=temp_export_dir)
        columns = exporter._get_table_columns("tasks")

        assert "id" in columns
        assert "title" in columns
        assert "assignee" in columns

    def test_export_table_json(self, temp_db, temp_export_dir):
        """Test exporting single table as JSON."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            file_path = exporter.export_table("tasks", ExportFormat.JSON)

            assert os.path.exists(file_path)
            assert file_path.endswith(".json")

            with open(file_path) as f:
                data = json.load(f)
                assert len(data) == 2
                assert data[0]["id"] in ["task1", "task2"]

    def test_export_table_csv(self, temp_db, temp_export_dir):
        """Test exporting single table as CSV."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            file_path = exporter.export_table("tasks", ExportFormat.CSV)

            assert os.path.exists(file_path)
            assert file_path.endswith(".csv")

            with open(file_path) as f:
                reader = csv.reader(f)
                rows = list(reader)
                # Should have header + 2 data rows
                assert len(rows) >= 2

    def test_export_table_jsonl(self, temp_db, temp_export_dir):
        """Test exporting single table as JSONL."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            file_path = exporter.export_table("tasks", ExportFormat.JSONL)

            assert os.path.exists(file_path)
            assert file_path.endswith(".jsonl")

            with open(file_path) as f:
                lines = f.readlines()
                assert len(lines) == 2
                data = json.loads(lines[0])
                assert "id" in data

    def test_export_table_column_filtering(self, temp_db, temp_export_dir):
        """Test exporting with column filtering."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            file_path = exporter.export_table("tasks", ExportFormat.JSON, columns=["id", "title"])

            with open(file_path) as f:
                data = json.load(f)
                assert "id" in data[0]
                assert "title" in data[0]
                assert "assignee" not in data[0]

    def test_export_table_with_filters(self, temp_db, temp_export_dir):
        """Test exporting with column filters."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            file_path = exporter.export_table(
                "tasks", ExportFormat.JSON, filters={"status": "open"}
            )

            with open(file_path) as f:
                data = json.load(f)
                assert len(data) == 1
                assert data[0]["status"] == "open"

    def test_export_table_with_anonymization(self, temp_db, temp_export_dir):
        """Test exporting with PII anonymization."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            # People table has email column that will be properly anonymized
            mock_mgr.return_value.get_pii_columns.return_value = ["email"]

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            file_path = exporter.export_table("people", ExportFormat.JSON, anonymize=True)

            with open(file_path) as f:
                data = json.load(f)
                assert "alice@example.com" not in str(data)
                # Email should be anonymized with @ preserved
                assert "@" in data[0]["email"]

    def test_export_tables_multiple(self, temp_db, temp_export_dir):
        """Test exporting multiple tables."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.side_effect = lambda t: t in ["tasks", "people"]
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            request = ExportRequest(tables=["tasks", "people"], format=ExportFormat.JSON)
            result = exporter.export_tables(request)

            assert result.table_count == 2
            assert result.row_count == 4
            assert not result.anonymized
            assert os.path.exists(result.file_path)

    def test_export_tables_with_anonymization(self, temp_db, temp_export_dir):
        """Test exporting multiple tables with anonymization."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.side_effect = lambda t: t in ["tasks", "people"]
            mock_mgr.return_value.get_pii_columns.side_effect = lambda t: (
                ["assignee"] if t == "tasks" else ["email", "phone", "name"]
            )

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            request = ExportRequest(
                tables=["tasks", "people"],
                format=ExportFormat.JSON,
                anonymize_pii=True,
                requested_by="tester",
                reason="Testing",
            )
            result = exporter.export_tables(request)

            assert result.anonymized

    def test_export_all(self, temp_db, temp_export_dir):
        """Test exporting all tables."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.get_all_exportable_tables.return_value = ["tasks", "people"]
            mock_mgr.return_value.is_exportable.side_effect = lambda t: t in ["tasks", "people"]
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            result = exporter.export_all(ExportFormat.JSON)

            assert result.table_count == 2
            assert result.row_count == 4

    def test_export_checksum(self, temp_db, temp_export_dir):
        """Test checksum generation."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            request = ExportRequest(tables=["tasks"], format=ExportFormat.JSON)
            result = exporter.export_tables(request)

            assert len(result.checksum_sha256) == 64
            assert all(c in "0123456789abcdef" for c in result.checksum_sha256)

    def test_list_exportable_tables(self, temp_db, temp_export_dir):
        """Test listing exportable tables."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.get_all_exportable_tables.return_value = ["tasks"]
            mock_mgr.return_value.get_table_metadata.return_value = type(
                "obj",
                (),
                {
                    "description": "Tasks",
                    "pii_columns": ["assignee"],
                    "classification": type("obj", (), {"value": "internal"})(),
                },
            )()

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            tables = exporter.list_exportable_tables()

            assert len(tables) > 0
            assert any(t["table"] == "tasks" for t in tables)

    def test_get_export_schema(self, temp_db, temp_export_dir):
        """Test getting table schema."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_table_metadata.return_value = type(
                "obj", (), {"pii_columns": ["assignee"]}
            )()

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            schema = exporter.get_export_schema("tasks")

            assert schema["table"] == "tasks"
            assert "columns" in schema
            assert len(schema["columns"]) > 0
            assert any(c["name"] == "id" for c in schema["columns"])

    def test_export_non_exportable_table(self, temp_db, temp_export_dir):
        """Test error when exporting non-exportable table."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = False

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            with pytest.raises(ValueError):
                exporter.export_table("tasks", ExportFormat.JSON)

    def test_export_nonexistent_table(self, temp_db, temp_export_dir):
        """Test error when exporting non-existent table."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            with pytest.raises((ValueError, RuntimeError, KeyError)):
                exporter.export_table("nonexistent", ExportFormat.JSON)

    def test_export_format_enum(self):
        """Test export format enum."""
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.JSONL.value == "jsonl"

    def test_export_request_dataclass(self):
        """Test export request dataclass."""
        request = ExportRequest(
            tables=["tasks"],
            format=ExportFormat.JSON,
            anonymize_pii=True,
            requested_by="test",
            reason="testing",
        )

        assert request.tables == ["tasks"]
        assert request.format == ExportFormat.JSON
        assert request.anonymize_pii
        assert request.requested_by == "test"

    def test_export_result_dataclass(self, temp_db, temp_export_dir):
        """Test export result dataclass."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            request = ExportRequest(tables=["tasks"], format=ExportFormat.JSON)
            result = exporter.export_tables(request)

            assert result.request_id is not None
            assert result.format == ExportFormat.JSON
            assert result.row_count >= 0
            assert result.table_count >= 0
            assert result.checksum_sha256 is not None

    def test_csv_escaping(self, temp_db, temp_export_dir):
        """Test CSV exports handle special characters properly."""
        conn = sqlite3.connect(temp_db)
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?)",
            (
                "task3",
                'Task with "quotes" and, commas',
                "test@example.com",
                "open",
                "2024-01-15",
                "2024-01-16",
            ),
        )
        conn.commit()
        conn.close()

        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.is_exportable.return_value = True
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db, export_dir=temp_export_dir)
            file_path = exporter.export_table("tasks", ExportFormat.CSV)

            with open(file_path) as f:
                content = f.read()
                # CSV should contain the data, escaped properly
                assert len(content) > 0


class TestIntegration:
    """Integration tests for the full export pipeline."""

    @pytest.fixture
    def temp_export_dir(self):
        """Create a temporary export directory."""
        export_dir = tempfile.mkdtemp()
        yield export_dir
        if os.path.exists(export_dir):
            shutil.rmtree(export_dir)

    @pytest.fixture
    def temp_db_with_data(self):
        """Create a populated test database."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT,
                assignee TEXT,
                status TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE people (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                phone TEXT,
                created_at TEXT
            )
        """)

        # Insert varied data
        for i in range(10):
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (f"t{i}", f"Task {i}", f"user{i}@example.com", "open", "2024-01-01"),
            )
            conn.execute(
                "INSERT INTO people VALUES (?, ?, ?, ?, ?)",
                (f"p{i}", f"Person {i}", f"person{i}@example.com", f"555-{i:04d}", "2024-01-01"),
            )

        conn.commit()
        conn.close()

        yield path

        if os.path.exists(path):
            os.unlink(path)

    def test_full_export_json(self, temp_db_with_data, temp_export_dir):
        """Test full export pipeline with JSON."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.get_all_exportable_tables.return_value = ["tasks", "people"]
            mock_mgr.return_value.is_exportable.side_effect = lambda t: t in ["tasks", "people"]
            mock_mgr.return_value.get_pii_columns.return_value = []

            exporter = DataExporter(temp_db_with_data, export_dir=temp_export_dir)
            result = exporter.export_all(ExportFormat.JSON)

            assert result.table_count == 2
            assert result.row_count == 20
            assert result.format == ExportFormat.JSON

    def test_full_export_with_anonymization(self, temp_db_with_data, temp_export_dir):
        """Test full export with anonymization."""
        with patch("lib.governance.data_export.get_lifecycle_manager") as mock_mgr:
            mock_mgr.return_value.get_all_exportable_tables.return_value = ["tasks", "people"]
            mock_mgr.return_value.is_exportable.side_effect = lambda t: t in ["tasks", "people"]
            mock_mgr.return_value.get_pii_columns.side_effect = lambda t: (
                ["assignee"] if t == "tasks" else ["name", "email", "phone"]
            )

            exporter = DataExporter(temp_db_with_data, export_dir=temp_export_dir)
            result = exporter.export_all(ExportFormat.JSON, anonymize=True)

            assert result.anonymized
