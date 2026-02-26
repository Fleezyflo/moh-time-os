"""
Data Classification System for MOH Time OS.

Classifies database tables and columns by sensitivity level and data category.
Detects PII, financial data, and sensitive information through:
- Column name pattern matching
- Sample value analysis (email, phone, SSN, credit card patterns)
- Configurable sensitivity rules
"""

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from lib.db import validate_identifier

if TYPE_CHECKING:
    from lib.governance.data_catalog import DataCatalog

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================


class DataSensitivity(Enum):
    """Data sensitivity levels, ordered from least to most sensitive."""

    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3
    PII = 4
    FINANCIAL = 5

    def __lt__(self, other):
        """Allow comparison for ordering."""
        if not isinstance(other, DataSensitivity):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other):
        if not isinstance(other, DataSensitivity):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other):
        if not isinstance(other, DataSensitivity):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other):
        if not isinstance(other, DataSensitivity):
            return NotImplemented
        return self.value >= other.value


class DataCategory(Enum):
    """Data categories describing the type of data."""

    PERSONAL_IDENTITY = "personal_identity"
    CONTACT_INFO = "contact_info"
    FINANCIAL_DATA = "financial_data"
    BUSINESS_DATA = "business_data"
    OPERATIONAL_DATA = "operational_data"
    COMMUNICATION_CONTENT = "communication_content"
    SYSTEM_DATA = "system_data"
    HEALTH_DATA = "health_data"


# ============================================================================
# DATACLASSES
# ============================================================================


@dataclass
class ColumnClassification:
    """Classification information for a single column."""

    table: str
    column: str
    sensitivity: DataSensitivity
    category: DataCategory
    contains_pii: bool = False
    contains_financial: bool = False
    retention_required: bool = False
    anonymizable: bool = False
    notes: str = ""


@dataclass
class TableClassification:
    """Classification information for an entire table."""

    table: str
    overall_sensitivity: DataSensitivity
    categories: set[DataCategory] = field(default_factory=set)
    pii_columns: list[str] = field(default_factory=list)
    financial_columns: list[str] = field(default_factory=list)
    total_columns: int = 0
    classified_columns: int = 0

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "table": self.table,
            "overall_sensitivity": self.overall_sensitivity.name,
            "categories": [c.value for c in self.categories],
            "pii_columns": self.pii_columns,
            "financial_columns": self.financial_columns,
            "total_columns": self.total_columns,
            "classified_columns": self.classified_columns,
        }


# ============================================================================
# PATTERN DETECTION
# ============================================================================


class PatternDetector:
    """Detects PII and financial data patterns in column names and values."""

    # Column name patterns (case-insensitive)
    EMAIL_PATTERNS = re.compile(
        r"(^|_)(email|e_mail|mail|address|contact_email)($|_)", re.IGNORECASE
    )
    PHONE_PATTERNS = re.compile(
        r"(^|_)(phone|phone_number|phonenumber|mobile|cellular|cell)($|_)",
        re.IGNORECASE,
    )
    NAME_PATTERNS = re.compile(
        r"(^|_)(first_?name|last_?name|full_?name|name|given_?name|family_?name)($|_)",
        re.IGNORECASE,
    )
    ADDRESS_PATTERNS = re.compile(
        r"(^|_)(address|street|city|state|province|postal|zip|zipcode|zip_code)($|_)",
        re.IGNORECASE,
    )
    SSN_PATTERNS = re.compile(
        r"(^|_)(ssn|social_?security|social_security_number|ss_?number)($|_)",
        re.IGNORECASE,
    )
    BIRTHDATE_PATTERNS = re.compile(
        r"(^|_)(dob|date_?of_?birth|birthdate|birth_?date)($|_)", re.IGNORECASE
    )
    IP_PATTERNS = re.compile(r"(^|_)(ip|ip_?address|ipv4|ipv6)($|_)", re.IGNORECASE)
    AMOUNT_PATTERNS = re.compile(
        r"(^|_)(amount|price|cost|fee|salary|wage|income|revenue)($|_)",
        re.IGNORECASE,
    )
    CARD_PATTERNS = re.compile(
        r"(^|_)(credit_?card|card_?number|cc_?number|pan|payment_method)($|_)",
        re.IGNORECASE,
    )

    # Sample value patterns
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    PHONE_REGEX = re.compile(
        r"^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$|^[0-9]{10,}$"
    )
    SSN_REGEX = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
    CREDIT_CARD_REGEX = re.compile(r"^\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}$")
    IP_ADDRESS_REGEX = re.compile(
        r"^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-fA-F]{0,4}(:[0-9a-fA-F]{0,4}){2,}$"
    )

    @staticmethod
    def detect_email(column_name: str, sample_values: list[str] = None) -> bool:
        """Detect if column contains email addresses."""
        if PatternDetector.EMAIL_PATTERNS.search(column_name):
            return True
        if sample_values:
            for val in sample_values:
                if val and PatternDetector.EMAIL_REGEX.match(str(val)):
                    return True
        return False

    @staticmethod
    def detect_phone(column_name: str, sample_values: list[str] = None) -> bool:
        """Detect if column contains phone numbers."""
        if PatternDetector.PHONE_PATTERNS.search(column_name):
            return True
        if sample_values:
            for val in sample_values:
                if val and PatternDetector.PHONE_REGEX.match(str(val)):
                    return True
        return False

    @staticmethod
    def detect_name(column_name: str) -> bool:
        """Detect if column contains names."""
        return bool(PatternDetector.NAME_PATTERNS.search(column_name))

    @staticmethod
    def detect_address(column_name: str) -> bool:
        """Detect if column contains address information."""
        return bool(PatternDetector.ADDRESS_PATTERNS.search(column_name))

    @staticmethod
    def detect_ssn(column_name: str, sample_values: list[str] = None) -> bool:
        """Detect if column contains SSN data."""
        if PatternDetector.SSN_PATTERNS.search(column_name):
            return True
        if sample_values:
            for val in sample_values:
                if val and PatternDetector.SSN_REGEX.match(str(val)):
                    return True
        return False

    @staticmethod
    def detect_birthdate(column_name: str) -> bool:
        """Detect if column contains date of birth."""
        return bool(PatternDetector.BIRTHDATE_PATTERNS.search(column_name))

    @staticmethod
    def detect_ip_address(column_name: str, sample_values: list[str] = None) -> bool:
        """Detect if column contains IP addresses."""
        if PatternDetector.IP_PATTERNS.search(column_name):
            return True
        if sample_values:
            for val in sample_values:
                if val and PatternDetector.IP_ADDRESS_REGEX.match(str(val)):
                    return True
        return False

    @staticmethod
    def detect_amount(column_name: str) -> bool:
        """Detect if column contains financial amounts."""
        return bool(PatternDetector.AMOUNT_PATTERNS.search(column_name))

    @staticmethod
    def detect_credit_card(column_name: str, sample_values: list[str] = None) -> bool:
        """Detect if column contains credit card numbers."""
        if PatternDetector.CARD_PATTERNS.search(column_name):
            return True
        if sample_values:
            for val in sample_values:
                if val and PatternDetector.CREDIT_CARD_REGEX.match(str(val)):
                    return True
        return False


# ============================================================================
# DATA CLASSIFIER
# ============================================================================


class DataClassifier:
    """Classifies database tables and columns for data governance."""

    def __init__(self, db_path: str):
        """Initialize classifier with database path."""
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)

    def _get_connection(self):
        """Create a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_table_schema(self, table: str) -> list[str]:
        """Get list of column names for a table."""
        try:
            safe_table = validate_identifier(table)
            conn = self._get_connection()
            cursor = conn.execute(f"PRAGMA table_info({safe_table})")  # noqa: S608
            columns = [row[1] for row in cursor.fetchall()]
            conn.close()
            return columns
        except sqlite3.Error as e:
            self.logger.error(f"Error getting schema for {table}: {e}")
            return []

    def _get_sample_values(self, table: str, column: str, limit: int = 5) -> list:
        """Get sample values from a column for pattern analysis."""
        try:
            safe_table = validate_identifier(table)
            safe_col = validate_identifier(column)
            conn = self._get_connection()
            cursor = conn.execute(f'SELECT "{safe_col}" FROM {safe_table} LIMIT ?', (limit,))  # noqa: S608
            values = [row[0] for row in cursor.fetchall() if row[0] is not None]
            conn.close()
            return values
        except sqlite3.Error as e:
            self.logger.debug(f"Error getting samples from {table}.{column}: {e}")
            return []

    def classify_column(
        self,
        table: str,
        column: str,
        sample_values: list = None,
    ) -> ColumnClassification:
        """Classify a single column based on name and sample values."""
        if sample_values is None:
            sample_values = self._get_sample_values(table, column)

        # Initialize classification
        sensitivity = DataSensitivity.PUBLIC
        categories = set()
        contains_pii = False
        contains_financial = False
        anonymizable = False
        notes = []

        # Check for PII patterns
        if PatternDetector.detect_email(column, sample_values):
            contains_pii = True
            categories.add(DataCategory.CONTACT_INFO)
            sensitivity = DataSensitivity.PII
            anonymizable = True
            notes.append("Email address")

        if PatternDetector.detect_phone(column, sample_values):
            contains_pii = True
            categories.add(DataCategory.CONTACT_INFO)
            sensitivity = DataSensitivity.PII
            anonymizable = True
            notes.append("Phone number")

        if PatternDetector.detect_name(column):
            contains_pii = True
            categories.add(DataCategory.PERSONAL_IDENTITY)
            sensitivity = DataSensitivity.PII
            anonymizable = True
            notes.append("Name field")

        if PatternDetector.detect_address(column):
            contains_pii = True
            categories.add(DataCategory.CONTACT_INFO)
            sensitivity = DataSensitivity.PII
            anonymizable = True
            notes.append("Address field")

        if PatternDetector.detect_ssn(column, sample_values):
            contains_pii = True
            categories.add(DataCategory.PERSONAL_IDENTITY)
            sensitivity = DataSensitivity.PII
            anonymizable = False
            notes.append("Social Security Number")

        if PatternDetector.detect_birthdate(column):
            contains_pii = True
            categories.add(DataCategory.PERSONAL_IDENTITY)
            sensitivity = DataSensitivity.PII
            anonymizable = True
            notes.append("Date of birth")

        if PatternDetector.detect_ip_address(column, sample_values):
            contains_pii = True
            categories.add(DataCategory.SYSTEM_DATA)
            sensitivity = DataSensitivity.CONFIDENTIAL
            anonymizable = True
            notes.append("IP address")

        # Check for financial patterns
        if PatternDetector.detect_amount(column):
            contains_financial = True
            categories.add(DataCategory.FINANCIAL_DATA)
            if sensitivity < DataSensitivity.FINANCIAL:
                sensitivity = DataSensitivity.FINANCIAL
            notes.append("Financial amount")

        if PatternDetector.detect_credit_card(column, sample_values):
            contains_financial = True
            categories.add(DataCategory.FINANCIAL_DATA)
            sensitivity = DataSensitivity.FINANCIAL
            anonymizable = False
            notes.append("Credit card number")

        # If no specific category detected, use OPERATIONAL_DATA as default
        if not categories:
            categories.add(DataCategory.OPERATIONAL_DATA)

        return ColumnClassification(
            table=table,
            column=column,
            sensitivity=sensitivity,
            category=list(categories)[0],  # Use first category for now
            contains_pii=contains_pii,
            contains_financial=contains_financial,
            retention_required=contains_pii or contains_financial,
            anonymizable=anonymizable,
            notes="; ".join(notes) if notes else "",
        )

    def classify_table(self, table: str) -> TableClassification:
        """Classify all columns in a table."""
        columns = self._get_table_schema(table)

        if not columns:
            return TableClassification(
                table=table,
                overall_sensitivity=DataSensitivity.PUBLIC,
                categories=set(),
                pii_columns=[],
                financial_columns=[],
                total_columns=0,
                classified_columns=0,
            )

        pii_columns = []
        financial_columns = []
        max_sensitivity = DataSensitivity.PUBLIC
        categories = set()

        for column in columns:
            col_class = self.classify_column(table, column)

            if col_class.contains_pii:
                pii_columns.append(column)
            if col_class.contains_financial:
                financial_columns.append(column)

            categories.add(col_class.category)

            # Update max sensitivity
            if col_class.sensitivity > max_sensitivity:
                max_sensitivity = col_class.sensitivity

        return TableClassification(
            table=table,
            overall_sensitivity=max_sensitivity,
            categories=categories,
            pii_columns=pii_columns,
            financial_columns=financial_columns,
            total_columns=len(columns),
            classified_columns=len(columns),
        )

    def classify_database(self) -> "DataCatalog":
        """Classify the entire database."""
        from lib.governance.data_catalog import DataCatalog

        try:
            conn = self._get_connection()
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
        except sqlite3.Error as e:
            self.logger.error(f"Error listing tables: {e}")
            return DataCatalog({})

        classifications = {}
        for table in tables:
            classifications[table] = self.classify_table(table)

        return DataCatalog(classifications)

    def get_pii_tables(self) -> list[str]:
        """Get all tables containing PII data."""
        catalog = self.classify_database()
        return catalog.get_pii_tables()

    def get_financial_tables(self) -> list[str]:
        """Get all tables containing financial data."""
        catalog = self.classify_database()
        return catalog.get_financial_tables()
