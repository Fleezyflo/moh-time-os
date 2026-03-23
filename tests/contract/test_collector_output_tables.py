"""
Contract Tests — Collector OUTPUT_TABLES declarations.

Ensures:
- Every collector class has an OUTPUT_TABLES class variable
- OUTPUT_TABLES includes the primary target_table as its first entry
- All declared tables exist in lib/schema.py TABLES
- Multi-table collectors list all secondary tables they write to
"""

import pytest

from lib.collectors import (
    AsanaCollector,
    CalendarCollector,
    ChatCollector,
    ContactsCollector,
    DriveCollector,
    GmailCollector,
    TasksCollector,
    XeroCollector,
)
from lib.schema import TABLES

# All collector classes that must declare OUTPUT_TABLES
COLLECTOR_CLASSES = [
    GmailCollector,
    CalendarCollector,
    AsanaCollector,
    ChatCollector,
    TasksCollector,
    ContactsCollector,
    DriveCollector,
    XeroCollector,
]


class TestCollectorOutputTablesDeclared:
    """Every collector must have an OUTPUT_TABLES class variable."""

    @pytest.mark.parametrize(
        "collector_class",
        COLLECTOR_CLASSES,
        ids=lambda c: c.__name__,
    )
    def test_collector_has_output_tables(self, collector_class):
        """Each collector class declares OUTPUT_TABLES as a list."""
        assert hasattr(collector_class, "OUTPUT_TABLES"), (
            f"{collector_class.__name__} missing OUTPUT_TABLES class variable"
        )
        tables = collector_class.OUTPUT_TABLES
        assert isinstance(tables, list), (
            f"{collector_class.__name__}.OUTPUT_TABLES must be a list, got {type(tables)}"
        )
        assert len(tables) > 0, f"{collector_class.__name__}.OUTPUT_TABLES must not be empty"


class TestCollectorOutputTablesMatchSchema:
    """All declared tables must exist in lib/schema.py TABLES."""

    @pytest.mark.parametrize(
        "collector_class",
        COLLECTOR_CLASSES,
        ids=lambda c: c.__name__,
    )
    def test_declared_tables_exist_in_schema(self, collector_class):
        """Every table in OUTPUT_TABLES must be defined in schema.py."""
        for table_name in collector_class.OUTPUT_TABLES:
            assert table_name in TABLES, (
                f"{collector_class.__name__}.OUTPUT_TABLES declares '{table_name}' "
                f"but it is not defined in lib/schema.py TABLES"
            )


class TestCollectorOutputTablesPrimaryFirst:
    """Primary table (target_table) must be the first entry in OUTPUT_TABLES."""

    @pytest.mark.parametrize(
        "collector_class",
        [c for c in COLLECTOR_CLASSES if hasattr(c, "target_table")],
        ids=lambda c: c.__name__,
    )
    def test_primary_table_is_first(self, collector_class):
        """The target_table must be listed first in OUTPUT_TABLES."""
        target = collector_class.target_table
        tables = collector_class.OUTPUT_TABLES
        assert tables[0] == target, (
            f"{collector_class.__name__}.OUTPUT_TABLES[0] is '{tables[0]}' "
            f"but target_table is '{target}' — primary table must be first"
        )


class TestMultiTableCollectorsComplete:
    """Multi-table collectors must list all secondary tables."""

    def test_gmail_declares_all_secondary_tables(self):
        """Gmail writes to participants, attachments, and labels."""
        tables = GmailCollector.OUTPUT_TABLES
        assert "gmail_participants" in tables
        assert "gmail_attachments" in tables
        assert "gmail_labels" in tables

    def test_calendar_declares_all_secondary_tables(self):
        """Calendar writes to attendees and recurrence rules."""
        tables = CalendarCollector.OUTPUT_TABLES
        assert "calendar_attendees" in tables
        assert "calendar_recurrence_rules" in tables

    def test_asana_declares_all_secondary_tables(self):
        """Asana writes to custom_fields, subtasks, stories, dependencies, attachments, portfolios, goals."""
        tables = AsanaCollector.OUTPUT_TABLES
        for expected in [
            "asana_custom_fields",
            "asana_subtasks",
            "asana_stories",
            "asana_task_dependencies",
            "asana_attachments",
            "asana_portfolios",
            "asana_goals",
        ]:
            assert expected in tables, f"AsanaCollector.OUTPUT_TABLES missing '{expected}'"

    def test_chat_declares_all_secondary_tables(self):
        """Chat writes to reactions, attachments, space_metadata, space_members."""
        tables = ChatCollector.OUTPUT_TABLES
        for expected in [
            "chat_reactions",
            "chat_attachments",
            "chat_space_metadata",
            "chat_space_members",
        ]:
            assert expected in tables, f"ChatCollector.OUTPUT_TABLES missing '{expected}'"

    def test_xero_declares_all_secondary_tables(self):
        """Xero writes to line_items, contacts, credit_notes, bank_transactions, tax_rates."""
        tables = XeroCollector.OUTPUT_TABLES
        for expected in [
            "xero_line_items",
            "xero_contacts",
            "xero_credit_notes",
            "xero_bank_transactions",
            "xero_tax_rates",
        ]:
            assert expected in tables, f"XeroCollector.OUTPUT_TABLES missing '{expected}'"
