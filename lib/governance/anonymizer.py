"""
Data Anonymization - Type-aware PII redaction with consistent hashing.

Provides deterministic anonymization so:
- Same input always produces same output
- Anonymized data preserves format (email looks like email)
- Can be used for data exports and test data generation
"""

import hashlib
import logging
import re
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


class Anonymizer:
    """
    Type-aware anonymization of sensitive data.

    Uses hash-based consistent pseudonyms to ensure:
    - Same input always produces same output
    - Format is preserved (email, phone, name patterns)
    - All operations are deterministic and reproducible
    """

    def __init__(self, salt: str = "moh_time_os_anon"):
        """Initialize with optional salt for consistent hashing."""
        self.salt = salt

    def _hash(self, value: str) -> str:
        """Generate consistent hash for a value."""
        combined = f"{value}:{self.salt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def anonymize_email(self, email: str) -> str:
        """
        Anonymize email address.

        Replaces local part with hash, keeps domain structure.
        Example: john.doe@example.com -> a1b2c3d4e5f6@example.com
        """
        if not email or "@" not in email:
            return "invalid@example.com"

        try:
            local, domain = email.rsplit("@", 1)
            hash_value = self._hash(local)
            return f"{hash_value}@{domain}"
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error anonymizing email {email}: {e}")
            return "error@example.com"

    def anonymize_phone(self, phone: str) -> str:
        """
        Anonymize phone number.

        Masks all but last 4 digits, preserves format.
        Example: +1 (555) 123-4567 -> +X (XXX) XXX-4567
        """
        if not phone:
            return "0000000000"

        try:
            # Extract digits
            digits = re.sub(r"\D", "", phone)

            # Keep last 4, mask the rest
            if len(digits) >= 4:
                last_four = digits[-4:]
                masked = "X" * (len(digits) - 4) + last_four
            else:
                masked = "X" * len(digits)

            return masked
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error anonymizing phone {phone}: {e}")
            return "0000000000"

    def anonymize_name(self, name: str) -> str:
        """
        Anonymize person's name.

        Replaces with consistent pseudonym based on hash.
        Example: John Doe -> Person_a1b2c3d4
        """
        if not name:
            return "Person_Unknown"

        try:
            hash_value = self._hash(name)[:8]
            return f"Person_{hash_value}"
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error anonymizing name {name}: {e}")
            return "Person_Error"

    def anonymize_value(self, value: Any, column_type: str) -> Any:
        """
        Anonymize a value based on column type.

        Supported types:
        - email: email address
        - phone: phone number
        - name: person name
        - text: generic text (hash-based)
        - url: web URL
        - default: return as-is
        """
        if value is None or value == "":
            return value

        try:
            value_str = str(value)

            if column_type == "email":
                return self.anonymize_email(value_str)
            elif column_type == "phone":
                return self.anonymize_phone(value_str)
            elif column_type == "name":
                return self.anonymize_name(value_str)
            elif column_type == "text":
                # Generic text: replace with hash
                return f"Text_{self._hash(value_str)[:12]}"
            elif column_type == "url":
                # URL: preserve scheme, hash domain and path
                try:
                    if "://" in value_str:
                        scheme, rest = value_str.split("://", 1)
                        return f"{scheme}://anonymized-{self._hash(rest)[:8]}.example.com"
                except (sqlite3.Error, ValueError, OSError) as e:
                    logger.error("handler failed: %s", e, exc_info=True)
                    raise  # re-raise after logging
                return f"https://anonymized-{self._hash(value_str)[:8]}.example.com"
            else:
                # Default: return original
                return value
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error anonymizing value {value} (type {column_type}): {e}")
            return value

    def anonymize_row(self, row: dict, pii_columns: list[str] | None = None) -> dict:
        """
        Anonymize specific columns in a row.

        Args:
            row: Dictionary of column names to values
            pii_columns: List of column names to anonymize
                        Format: ["email:column_name", "phone:column_name", ...]
                        If just column name, infers type from name

        Returns:
            Copy of row with specified columns anonymized
        """
        if not pii_columns:
            return dict(row)

        anonymized = dict(row)

        for pii_spec in pii_columns:
            # Parse "type:column" or just "column"
            if ":" in pii_spec:
                column_type, column_name = pii_spec.split(":", 1)
            else:
                column_name = pii_spec
                # Infer type from column name
                column_type = self._infer_type(column_name)

            if column_name in anonymized and anonymized[column_name] is not None:
                anonymized[column_name] = self.anonymize_value(anonymized[column_name], column_type)

        return anonymized

    @staticmethod
    def _infer_type(column_name: str) -> str:
        """Infer PII type from column name."""
        name_lower = column_name.lower()

        if "email" in name_lower or "mail" in name_lower:
            return "email"
        elif "phone" in name_lower or "mobile" in name_lower or "cell" in name_lower:
            return "phone"
        elif "name" in name_lower:
            return "name"
        elif "url" in name_lower or "website" in name_lower or "link" in name_lower:
            return "url"
        else:
            return "text"
