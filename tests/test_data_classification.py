"""
Data Classification System Tests.

Tests for data sensitivity levels, pattern detection, classification,
and compliance reporting.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.governance import (
    ColumnClassification,
    DataCatalog,
    DataCategory,
    DataClassifier,
    DataSensitivity,
    PatternDetector,
    TableClassification,
)


class TestDataSensitivity(TestCase):
    """Test DataSensitivity enum and ordering."""

    def test_sensitivity_values(self):
        """All sensitivity levels have unique values."""
        values = [s.value for s in DataSensitivity]
        self.assertEqual(len(values), len(set(values)))

    def test_sensitivity_ordering(self):
        """Sensitivity levels are properly ordered."""
        self.assertLess(DataSensitivity.PUBLIC, DataSensitivity.INTERNAL)
        self.assertLess(DataSensitivity.INTERNAL, DataSensitivity.CONFIDENTIAL)
        self.assertLess(DataSensitivity.CONFIDENTIAL, DataSensitivity.RESTRICTED)
        self.assertLess(DataSensitivity.RESTRICTED, DataSensitivity.PII)
        self.assertLess(DataSensitivity.PII, DataSensitivity.FINANCIAL)

    def test_sensitivity_comparison_operators(self):
        """Comparison operators work correctly."""
        self.assertTrue(DataSensitivity.PUBLIC <= DataSensitivity.PUBLIC)
        self.assertTrue(DataSensitivity.PUBLIC <= DataSensitivity.INTERNAL)
        self.assertTrue(DataSensitivity.FINANCIAL >= DataSensitivity.PII)
        self.assertFalse(DataSensitivity.FINANCIAL < DataSensitivity.PII)


class TestDataCategory(TestCase):
    """Test DataCategory enum."""

    def test_all_categories_exist(self):
        """All required categories are defined."""
        categories = {
            DataCategory.PERSONAL_IDENTITY,
            DataCategory.CONTACT_INFO,
            DataCategory.FINANCIAL_DATA,
            DataCategory.BUSINESS_DATA,
            DataCategory.OPERATIONAL_DATA,
            DataCategory.COMMUNICATION_CONTENT,
            DataCategory.SYSTEM_DATA,
            DataCategory.HEALTH_DATA,
        }
        self.assertEqual(len(categories), 8)

    def test_category_values_are_strings(self):
        """Category values are strings."""
        for category in DataCategory:
            self.assertIsInstance(category.value, str)


class TestColumnClassification(TestCase):
    """Test ColumnClassification dataclass."""

    def test_column_classification_creation(self):
        """ColumnClassification can be created with all fields."""
        col = ColumnClassification(
            table="users",
            column="email",
            sensitivity=DataSensitivity.PII,
            category=DataCategory.CONTACT_INFO,
            contains_pii=True,
            contains_financial=False,
            retention_required=True,
            anonymizable=True,
            notes="Email address",
        )
        self.assertEqual(col.table, "users")
        self.assertEqual(col.column, "email")
        self.assertEqual(col.sensitivity, DataSensitivity.PII)
        self.assertTrue(col.contains_pii)
        self.assertFalse(col.contains_financial)

    def test_column_classification_defaults(self):
        """ColumnClassification has proper defaults."""
        col = ColumnClassification(
            table="data",
            column="id",
            sensitivity=DataSensitivity.PUBLIC,
            category=DataCategory.OPERATIONAL_DATA,
        )
        self.assertFalse(col.contains_pii)
        self.assertFalse(col.contains_financial)
        self.assertFalse(col.retention_required)
        self.assertFalse(col.anonymizable)
        self.assertEqual(col.notes, "")


class TestTableClassification(TestCase):
    """Test TableClassification dataclass."""

    def test_table_classification_creation(self):
        """TableClassification can be created."""
        table = TableClassification(
            table="users",
            overall_sensitivity=DataSensitivity.PII,
            categories={DataCategory.PERSONAL_IDENTITY, DataCategory.CONTACT_INFO},
            pii_columns=["email", "phone"],
            financial_columns=[],
            total_columns=5,
            classified_columns=5,
        )
        self.assertEqual(table.table, "users")
        self.assertEqual(table.overall_sensitivity, DataSensitivity.PII)
        self.assertEqual(len(table.categories), 2)
        self.assertEqual(len(table.pii_columns), 2)

    def test_table_classification_to_dict(self):
        """TableClassification can be serialized to dict."""
        table = TableClassification(
            table="users",
            overall_sensitivity=DataSensitivity.PII,
            categories={DataCategory.PERSONAL_IDENTITY},
            pii_columns=["email"],
            financial_columns=[],
            total_columns=5,
            classified_columns=5,
        )
        result = table.to_dict()
        self.assertEqual(result["table"], "users")
        self.assertEqual(result["overall_sensitivity"], "PII")
        self.assertIn("personal_identity", result["categories"])
        self.assertEqual(result["pii_columns"], ["email"])


class TestPatternDetector(TestCase):
    """Test PatternDetector pattern matching."""

    def test_email_detection_by_name(self):
        """Email columns detected by name patterns."""
        self.assertTrue(PatternDetector.detect_email("email"))
        self.assertTrue(PatternDetector.detect_email("user_email"))
        self.assertTrue(PatternDetector.detect_email("contact_email"))
        self.assertTrue(PatternDetector.detect_email("email_address"))
        self.assertFalse(PatternDetector.detect_email("name"))

    def test_email_detection_by_value(self):
        """Email addresses detected in sample values."""
        self.assertTrue(PatternDetector.detect_email("contact", ["user@example.com"]))
        self.assertTrue(PatternDetector.detect_email("unknown", ["test@domain.co.uk"]))
        self.assertFalse(PatternDetector.detect_email("unknown", ["not-an-email"]))

    def test_phone_detection_by_name(self):
        """Phone columns detected by name patterns."""
        self.assertTrue(PatternDetector.detect_phone("phone"))
        self.assertTrue(PatternDetector.detect_phone("phone_number"))
        self.assertTrue(PatternDetector.detect_phone("mobile"))
        self.assertTrue(PatternDetector.detect_phone("cell"))
        self.assertFalse(PatternDetector.detect_phone("name"))

    def test_phone_detection_by_value(self):
        """Phone numbers detected in sample values."""
        self.assertTrue(PatternDetector.detect_phone("number", ["555-123-4567"]))
        self.assertTrue(PatternDetector.detect_phone("number", ["(555) 123-4567"]))
        self.assertTrue(PatternDetector.detect_phone("number", ["5551234567"]))
        self.assertFalse(PatternDetector.detect_phone("number", ["not-a-phone"]))

    def test_name_detection(self):
        """Name columns detected by patterns."""
        self.assertTrue(PatternDetector.detect_name("first_name"))
        self.assertTrue(PatternDetector.detect_name("last_name"))
        self.assertTrue(PatternDetector.detect_name("full_name"))
        self.assertTrue(PatternDetector.detect_name("name"))
        self.assertFalse(PatternDetector.detect_name("email"))

    def test_address_detection(self):
        """Address columns detected by patterns."""
        self.assertTrue(PatternDetector.detect_address("address"))
        self.assertTrue(PatternDetector.detect_address("street_address"))
        self.assertTrue(PatternDetector.detect_address("city"))
        self.assertTrue(PatternDetector.detect_address("zip_code"))
        self.assertFalse(PatternDetector.detect_address("name"))

    def test_ssn_detection_by_name(self):
        """SSN columns detected by name patterns."""
        self.assertTrue(PatternDetector.detect_ssn("ssn"))
        self.assertTrue(PatternDetector.detect_ssn("social_security_number"))
        self.assertFalse(PatternDetector.detect_ssn("account_number"))

    def test_ssn_detection_by_value(self):
        """SSN values detected by pattern."""
        self.assertTrue(PatternDetector.detect_ssn("number", ["123-45-6789"]))
        self.assertTrue(PatternDetector.detect_ssn("number", ["123456789"]))
        self.assertFalse(PatternDetector.detect_ssn("number", ["invalid"]))

    def test_birthdate_detection(self):
        """Date of birth columns detected."""
        self.assertTrue(PatternDetector.detect_birthdate("dob"))
        self.assertTrue(PatternDetector.detect_birthdate("date_of_birth"))
        self.assertTrue(PatternDetector.detect_birthdate("birthdate"))
        self.assertFalse(PatternDetector.detect_birthdate("created_at"))

    def test_ip_address_detection_by_name(self):
        """IP columns detected by name."""
        self.assertTrue(PatternDetector.detect_ip_address("ip_address"))
        self.assertTrue(PatternDetector.detect_ip_address("ip_addr"))
        self.assertTrue(PatternDetector.detect_ip_address("ip"))
        self.assertTrue(PatternDetector.detect_ip_address("ipv4"))
        self.assertFalse(PatternDetector.detect_ip_address("address"))

    def test_ip_address_detection_by_value(self):
        """IP addresses detected in values."""
        self.assertTrue(PatternDetector.detect_ip_address("address", ["192.168.1.1"]))
        self.assertTrue(PatternDetector.detect_ip_address("address", ["10.0.0.1"]))

    def test_amount_detection(self):
        """Financial amount columns detected."""
        self.assertTrue(PatternDetector.detect_amount("amount"))
        self.assertTrue(PatternDetector.detect_amount("price"))
        self.assertTrue(PatternDetector.detect_amount("salary"))
        self.assertTrue(PatternDetector.detect_amount("revenue"))
        self.assertFalse(PatternDetector.detect_amount("id"))

    def test_credit_card_detection_by_name(self):
        """Credit card columns detected by name."""
        self.assertTrue(PatternDetector.detect_credit_card("credit_card"))
        self.assertTrue(PatternDetector.detect_credit_card("card_number"))
        self.assertTrue(PatternDetector.detect_credit_card("cc_number"))
        self.assertFalse(PatternDetector.detect_credit_card("account_id"))

    def test_credit_card_detection_by_value(self):
        """Credit card numbers detected in values."""
        self.assertTrue(PatternDetector.detect_credit_card("card", ["1234-5678-9012-3456"]))
        self.assertTrue(PatternDetector.detect_credit_card("card", ["1234 5678 9012 3456"]))


class TestDataClassifier(TestCase):
    """Test DataClassifier classification logic."""

    def setUp(self):
        """Create a test database."""
        self.fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.fd)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # Create test tables
        self.conn.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email TEXT,
                phone TEXT,
                first_name TEXT,
                last_name TEXT,
                ssn TEXT,
                created_at TEXT
            );

            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                credit_card TEXT,
                date TEXT
            );

            CREATE TABLE logs (
                id INTEGER PRIMARY KEY,
                message TEXT,
                ip_addr TEXT,
                timestamp TEXT
            );

            CREATE TABLE empty_table (
                id INTEGER PRIMARY KEY
            );
        """)

        # Insert test data
        self.conn.execute(
            "INSERT INTO users VALUES (1, ?, ?, ?, ?, ?, ?)",
            (
                "user@example.com",
                "555-123-4567",
                "John",
                "Doe",
                "123-45-6789",
                "2024-01-01",
            ),
        )

        self.conn.execute(
            "INSERT INTO transactions VALUES (1, ?, ?, ?, ?)",
            (1, 99.99, "1234-5678-9012-3456", "2024-01-01"),
        )

        self.conn.execute(
            "INSERT INTO logs VALUES (1, ?, ?, ?)",
            ("Test log", "192.168.1.1", "2024-01-01 10:00:00"),
        )

        self.conn.commit()

        self.classifier = DataClassifier(self.db_path)

    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        os.unlink(self.db_path)

    def test_classify_email_column(self):
        """Email columns are correctly classified as PII."""
        col_class = self.classifier.classify_column("users", "email")
        self.assertTrue(col_class.contains_pii)
        self.assertEqual(col_class.sensitivity, DataSensitivity.PII)
        self.assertEqual(col_class.category, DataCategory.CONTACT_INFO)
        self.assertTrue(col_class.anonymizable)

    def test_classify_phone_column(self):
        """Phone columns are correctly classified as PII."""
        col_class = self.classifier.classify_column("users", "phone")
        self.assertTrue(col_class.contains_pii)
        self.assertEqual(col_class.sensitivity, DataSensitivity.PII)

    def test_classify_name_column(self):
        """Name columns are correctly classified as PII."""
        col_class = self.classifier.classify_column("users", "first_name")
        self.assertTrue(col_class.contains_pii)
        self.assertEqual(col_class.sensitivity, DataSensitivity.PII)

    def test_classify_ssn_column(self):
        """SSN columns are correctly classified as PII."""
        col_class = self.classifier.classify_column("users", "ssn")
        self.assertTrue(col_class.contains_pii)
        self.assertEqual(col_class.sensitivity, DataSensitivity.PII)
        self.assertFalse(col_class.anonymizable)

    def test_classify_financial_amount_column(self):
        """Amount columns are classified as financial data."""
        col_class = self.classifier.classify_column("transactions", "amount")
        self.assertTrue(col_class.contains_financial)
        self.assertEqual(col_class.sensitivity, DataSensitivity.FINANCIAL)

    def test_classify_credit_card_column(self):
        """Credit card columns are classified as financial data."""
        col_class = self.classifier.classify_column("transactions", "credit_card")
        self.assertTrue(col_class.contains_financial)
        self.assertEqual(col_class.sensitivity, DataSensitivity.FINANCIAL)
        self.assertFalse(col_class.anonymizable)

    def test_classify_ip_address_column(self):
        """IP address columns are classified as sensitive."""
        col_class = self.classifier.classify_column("logs", "ip_addr")
        self.assertTrue(col_class.contains_pii)
        self.assertGreaterEqual(col_class.sensitivity, DataSensitivity.CONFIDENTIAL)

    def test_classify_normal_column(self):
        """Normal columns are public."""
        col_class = self.classifier.classify_column("logs", "message")
        self.assertFalse(col_class.contains_pii)
        self.assertEqual(col_class.sensitivity, DataSensitivity.PUBLIC)

    def test_classify_table_users(self):
        """Users table classification includes PII columns."""
        table_class = self.classifier.classify_table("users")

        self.assertEqual(table_class.table, "users")
        self.assertEqual(table_class.overall_sensitivity, DataSensitivity.PII)
        self.assertGreater(len(table_class.pii_columns), 0)
        self.assertIn("email", table_class.pii_columns)
        self.assertIn("phone", table_class.pii_columns)
        self.assertEqual(table_class.total_columns, 7)

    def test_classify_table_transactions(self):
        """Transactions table classification includes financial columns."""
        table_class = self.classifier.classify_table("transactions")

        self.assertEqual(table_class.overall_sensitivity, DataSensitivity.FINANCIAL)
        self.assertGreater(len(table_class.financial_columns), 0)
        self.assertIn("amount", table_class.financial_columns)
        self.assertIn("credit_card", table_class.financial_columns)

    def test_classify_empty_table(self):
        """Empty tables are properly classified."""
        table_class = self.classifier.classify_table("empty_table")

        self.assertEqual(table_class.overall_sensitivity, DataSensitivity.PUBLIC)
        self.assertEqual(table_class.pii_columns, [])
        self.assertEqual(table_class.financial_columns, [])

    def test_classify_database(self):
        """Full database classification returns catalog."""
        catalog = self.classifier.classify_database()

        self.assertIsInstance(catalog, DataCatalog)
        self.assertIn("users", catalog.tables)
        self.assertIn("transactions", catalog.tables)
        self.assertIn("logs", catalog.tables)
        self.assertIn("empty_table", catalog.tables)

    def test_get_pii_tables(self):
        """PII tables are correctly identified."""
        pii_tables = self.classifier.get_pii_tables()

        self.assertIn("users", pii_tables)
        self.assertIn("logs", pii_tables)
        self.assertNotIn("empty_table", pii_tables)

    def test_get_financial_tables(self):
        """Financial tables are correctly identified."""
        financial_tables = self.classifier.get_financial_tables()

        self.assertIn("transactions", financial_tables)
        self.assertNotIn("users", financial_tables)


class TestDataCatalog(TestCase):
    """Test DataCatalog query and reporting capabilities."""

    def setUp(self):
        """Create a test database and catalog."""
        self.fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.fd)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # Create test tables
        self.conn.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email TEXT,
                phone TEXT,
                first_name TEXT,
                ssn TEXT
            );

            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY,
                amount REAL,
                credit_card TEXT
            );

            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY,
                ip_addr TEXT,
                message TEXT
            );

            CREATE TABLE public_data (
                id INTEGER PRIMARY KEY,
                title TEXT,
                content TEXT
            );
        """)

        # Insert sample data
        self.conn.execute(
            "INSERT INTO users VALUES (1, ?, ?, ?, ?)",
            ("user@example.com", "555-123-4567", "John", "123-45-6789"),
        )
        self.conn.execute(
            "INSERT INTO transactions VALUES (1, ?, ?)",
            (99.99, "1234-5678-9012-3456"),
        )
        self.conn.execute(
            "INSERT INTO audit_logs VALUES (1, ?, ?)",
            ("192.168.1.1", "Login attempt"),
        )
        self.conn.execute(
            "INSERT INTO public_data VALUES (1, ?, ?)",
            ("Public", "Public data"),
        )
        self.conn.commit()

        classifier = DataClassifier(self.db_path)
        self.catalog = classifier.classify_database()

    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        os.unlink(self.db_path)

    def test_get_sensitive_tables_confidential(self):
        """Get tables with CONFIDENTIAL or higher sensitivity."""
        tables = self.catalog.get_sensitive_tables(DataSensitivity.CONFIDENTIAL)
        self.assertIn("users", tables)
        self.assertIn("transactions", tables)
        self.assertIn("audit_logs", tables)

    def test_get_sensitive_tables_financial(self):
        """Get tables with financial sensitivity."""
        tables = self.catalog.get_sensitive_tables(DataSensitivity.FINANCIAL)
        self.assertIn("transactions", tables)

    def test_get_sensitive_tables_public(self):
        """Get all tables with public data."""
        tables = self.catalog.get_sensitive_tables(DataSensitivity.PUBLIC)
        self.assertGreaterEqual(len(tables), 4)

    def test_get_pii_tables(self):
        """Get all tables containing PII."""
        pii_tables = self.catalog.get_pii_tables()
        self.assertIn("users", pii_tables)
        self.assertIn("audit_logs", pii_tables)
        self.assertNotIn("public_data", pii_tables)

    def test_get_financial_tables(self):
        """Get all tables with financial data."""
        financial_tables = self.catalog.get_financial_tables()
        self.assertIn("transactions", financial_tables)
        self.assertNotIn("users", financial_tables)

    def test_get_pii_report(self):
        """Generate PII report."""
        report = self.catalog.get_pii_report()

        self.assertIn("total_tables_with_pii", report)
        self.assertIn("total_pii_columns", report)
        self.assertIn("tables", report)
        self.assertGreater(report["total_tables_with_pii"], 0)
        self.assertGreater(report["total_pii_columns"], 0)

    def test_get_compliance_summary(self):
        """Generate compliance summary."""
        summary = self.catalog.get_compliance_summary()

        self.assertIn("summary", summary)
        self.assertIn("sensitivity_distribution", summary)
        self.assertIn("high_sensitivity_tables", summary)
        self.assertIn("pii_details", summary)

        self.assertIn("total_tables", summary["summary"])
        self.assertIn("total_columns", summary["summary"])
        self.assertIn("tables_with_pii", summary["summary"])

    def test_catalog_to_dict(self):
        """Catalog can be serialized to dict."""
        result = self.catalog.to_dict()

        self.assertIn("tables", result)
        self.assertIn("summary", result)
        self.assertGreater(len(result["tables"]), 0)

    def test_catalog_to_markdown(self):
        """Catalog can be exported as markdown."""
        markdown = self.catalog.to_markdown()

        self.assertIn("# Data Classification Report", markdown)
        self.assertIn("Executive Summary", markdown)
        self.assertIn("PII Summary", markdown)
        self.assertIn("All Tables", markdown)
        self.assertGreater(len(markdown), 100)


class TestDataGraduationComplexity(TestCase):
    """Test edge cases and complex scenarios."""

    def setUp(self):
        """Create test database with edge cases."""
        self.fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.fd)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        self.conn.executescript("""
            CREATE TABLE mixed_sensitive (
                id INTEGER PRIMARY KEY,
                email TEXT,
                amount REAL,
                ssn TEXT,
                name TEXT
            );

            CREATE TABLE all_null (
                id INTEGER PRIMARY KEY,
                data TEXT
            );

            CREATE TABLE no_sensitive (
                id INTEGER PRIMARY KEY,
                field1 TEXT,
                field2 TEXT
            );
        """)

        # Insert mixed data
        self.conn.execute(
            "INSERT INTO mixed_sensitive VALUES (1, ?, ?, ?, ?)",
            ("user@example.com", 100.50, "123-45-6789", "John Doe"),
        )

        # Insert only nulls
        self.conn.execute("INSERT INTO all_null VALUES (1, NULL)")

        # Insert non-sensitive data
        self.conn.execute(
            "INSERT INTO no_sensitive VALUES (1, ?, ?)",
            ("value1", "value2"),
        )

        self.conn.commit()

        self.classifier = DataClassifier(self.db_path)

    def tearDown(self):
        """Clean up test database."""
        self.conn.close()
        os.unlink(self.db_path)

    def test_classify_mixed_sensitive_table(self):
        """Table with multiple sensitive data types."""
        table_class = self.classifier.classify_table("mixed_sensitive")

        self.assertEqual(table_class.overall_sensitivity, DataSensitivity.FINANCIAL)
        self.assertGreater(len(table_class.pii_columns), 0)
        self.assertGreater(len(table_class.financial_columns), 0)

    def test_classify_all_null_table(self):
        """Table with all null values still gets classified."""
        table_class = self.classifier.classify_table("all_null")
        self.assertIsNotNone(table_class.overall_sensitivity)

    def test_classify_non_sensitive_table(self):
        """Table with no sensitive data."""
        table_class = self.classifier.classify_table("no_sensitive")
        self.assertEqual(table_class.overall_sensitivity, DataSensitivity.PUBLIC)
        self.assertEqual(table_class.pii_columns, [])

    def test_full_database_with_mixed_tables(self):
        """Classify entire database with mixed sensitivity."""
        catalog = self.classifier.classify_database()

        # Check that all tables are present
        self.assertEqual(len(catalog.tables), 3)

        # Check sensitivity levels are correctly assigned
        mixed_table = catalog.tables["mixed_sensitive"]
        self.assertGreaterEqual(mixed_table.overall_sensitivity, DataSensitivity.FINANCIAL)


if __name__ == "__main__":
    main()
