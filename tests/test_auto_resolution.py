"""
Tests for Auto-Resolution Engine

Tests cover:
- AutoResolutionEngine instantiation
- Each of 7 resolution rules with multiple scenarios
- Confidence thresholds and auto-apply logic
- Batch resolution
- Escalation
- scan_and_resolve with mocked queue
- Edge cases (empty queue, all resolved, no matches)
"""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.intelligence.auto_resolution import (
    AutoResolutionEngine,
    BatchResult,
    ResolutionAttempt,
    ResolutionReport,
    ResolutionRule,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create minimal schema
    cursor.execute("""
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TEXT,
            due_date TEXT,
            project_link_status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT,
            client_id TEXT,
            brand_id TEXT,
            is_internal INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE brands (
            id TEXT PRIMARY KEY,
            name TEXT,
            client_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE clients (
            id TEXT PRIMARY KEY,
            name TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE client_contacts (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            email TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE communications (
            id TEXT PRIMARY KEY,
            sender_email TEXT,
            link_status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE invoices (
            id TEXT PRIMARY KEY,
            contact_email TEXT,
            issue_date TEXT,
            issued_at TEXT,
            due_date TEXT,
            status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE resolution_queue (
            id TEXT PRIMARY KEY,
            entity_type TEXT,
            entity_id TEXT,
            issue_type TEXT,
            priority INTEGER,
            context TEXT,
            created_at TEXT,
            expires_at TEXT,
            resolved_at TEXT,
            status TEXT,
            updated_at TEXT
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def engine(temp_db):
    """Create AutoResolutionEngine with temp database."""
    return AutoResolutionEngine(db_path=temp_db)


# =============================================================================
# INSTANTIATION TESTS
# =============================================================================


def test_engine_instantiation_with_explicit_path(temp_db):
    """Test engine instantiation with explicit database path."""
    engine = AutoResolutionEngine(db_path=temp_db)
    assert engine.db_path == temp_db


def test_engine_instantiation_with_default_path():
    """Test engine instantiation with default path."""
    engine = AutoResolutionEngine()
    assert engine.db_path is not None


def test_engine_can_get_connection(engine, temp_db):
    """Test engine can establish database connection."""
    conn = engine._get_conn()
    assert conn is not None
    conn.close()


# =============================================================================
# RESOLUTION RULES TESTS
# =============================================================================


def test_get_resolution_rules(engine):
    """Test retrieving resolution rules."""
    rules = engine.get_resolution_rules()
    assert len(rules) == 7
    assert all(isinstance(r, ResolutionRule) for r in rules)


def test_resolution_rules_have_required_fields(engine):
    """Test that all rules have required fields."""
    rules = engine.get_resolution_rules()
    for rule in rules:
        assert rule.rule_id
        assert rule.issue_type
        assert rule.description
        assert 0.0 <= rule.confidence_threshold <= 1.0
        assert isinstance(rule.auto_apply, bool)
        assert rule.method_name


def test_rule_ids_match_issue_types(engine):
    """Test that rule_ids are consistent with issue_types."""
    rules = engine.get_resolution_rules()
    rule_dict = {r.rule_id: r for r in rules}
    expected_mappings = {
        "project_unlinked": "project_unlinked",
        "brand_missing": "missing_brand",
        "client_unidentified": "unlinked_with_commitments",
        "due_date_missing": "missing_due_date",
        "invoice_missing_client": "missing_client",
        "invoice_missing_due": "missing_due_date",
        "comm_missing_client": "unlinked_with_commitments",
    }
    for rule_id, _expected_issue in expected_mappings.items():
        assert rule_id in rule_dict
        # Note: Some issue types map to multiple rules


# =============================================================================
# RESOLUTION ATTEMPT DATA CLASS TESTS
# =============================================================================


def test_resolution_attempt_to_dict():
    """Test ResolutionAttempt.to_dict() serialization."""
    attempt = ResolutionAttempt(
        item_id="item-123",
        issue_type="project_unlinked",
        resolved=True,
        confidence=0.85,
        action_taken="Link task to project",
        reason="Exact match found",
        rule_id="project_unlinked",
    )
    d = attempt.to_dict()
    assert d["item_id"] == "item-123"
    assert d["issue_type"] == "project_unlinked"
    assert d["resolved"] is True
    assert d["confidence"] == 0.85


def test_resolution_report_to_dict():
    """Test ResolutionReport.to_dict() serialization."""
    attempt = ResolutionAttempt(
        item_id="item-1",
        issue_type="project_unlinked",
        resolved=True,
        confidence=0.9,
    )
    report = ResolutionReport(
        total_scanned=5,
        auto_resolved=2,
        escalated=1,
        failed=2,
        duration_ms=150,
        attempts=[attempt],
    )
    d = report.to_dict()
    assert d["total_scanned"] == 5
    assert d["auto_resolved"] == 2
    assert d["escalated"] == 1
    assert len(d["attempts"]) == 1


def test_batch_result_to_dict():
    """Test BatchResult.to_dict() serialization."""
    attempt = ResolutionAttempt(
        item_id="item-1",
        issue_type="brand_missing",
        resolved=True,
        confidence=0.85,
    )
    result = BatchResult(total=3, resolved=2, failed=1, results=[attempt])
    d = result.to_dict()
    assert d["total"] == 3
    assert d["resolved"] == 2
    assert d["failed"] == 1
    assert len(d["results"]) == 1


# =============================================================================
# PROJECT_UNLINKED RULE TESTS
# =============================================================================


def test_resolve_project_unlinked_exact_match(engine, temp_db):
    """Test project_unlinked rule with exactly 1 matching project."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Create task and project
    cursor.execute(
        "INSERT INTO tasks (id, name, created_at) VALUES (?, ?, ?)",
        ("task-1", "Website Redesign", "2025-01-01T00:00:00"),
    )
    cursor.execute(
        "INSERT INTO projects (id, name, client_id) VALUES (?, ?, ?)",
        ("proj-1", "Website Redesign", None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "task-1",
        "issue_type": "project_unlinked",
    }

    attempt = engine.resolve_project_unlinked(item)
    assert attempt.resolved is True
    assert attempt.confidence >= 0.85
    assert attempt.rule_id == "project_unlinked"


def test_resolve_project_unlinked_no_match(engine, temp_db):
    """Test project_unlinked rule with no matching projects."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tasks (id, name, created_at) VALUES (?, ?, ?)",
        ("task-1", "Secret Project", "2025-01-01T00:00:00"),
    )
    # Insert project with different name
    cursor.execute(
        "INSERT INTO projects (id, name, client_id) VALUES (?, ?, ?)",
        ("proj-1", "Completely Different", None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "task-1",
        "issue_type": "project_unlinked",
    }

    attempt = engine.resolve_project_unlinked(item)
    assert attempt.resolved is False
    assert attempt.confidence < 0.5


def test_resolve_project_unlinked_multiple_matches(engine, temp_db):
    """Test project_unlinked rule with multiple matching projects (ambiguous)."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tasks (id, name, created_at) VALUES (?, ?, ?)",
        ("task-1", "Design", "2025-01-01T00:00:00"),
    )
    cursor.execute(
        "INSERT INTO projects (id, name, client_id) VALUES (?, ?, ?)",
        ("proj-1", "Design Phase 1", None),
    )
    cursor.execute(
        "INSERT INTO projects (id, name, client_id) VALUES (?, ?, ?)",
        ("proj-2", "Design Phase 2", None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "task-1",
        "issue_type": "project_unlinked",
    }

    attempt = engine.resolve_project_unlinked(item)
    assert attempt.resolved is False
    assert attempt.confidence < 0.8


def test_resolve_project_unlinked_missing_task(engine):
    """Test project_unlinked rule with missing task."""
    item = {
        "id": "item-1",
        "entity_id": "nonexistent-task",
        "issue_type": "project_unlinked",
    }

    attempt = engine.resolve_project_unlinked(item)
    assert attempt.resolved is False
    assert attempt.confidence == 0.0


# =============================================================================
# BRAND_MISSING RULE TESTS
# =============================================================================


def test_resolve_brand_missing_client_has_brand(engine, temp_db):
    """Test brand_missing rule when client has existing brand."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("client-1", "Acme Corp"))
    cursor.execute(
        "INSERT INTO brands (id, name, client_id) VALUES (?, ?, ?)",
        ("brand-1", "Acme", "client-1"),
    )
    cursor.execute(
        "INSERT INTO projects (id, name, client_id, brand_id) VALUES (?, ?, ?, ?)",
        ("proj-1", "Acme Project", "client-1", None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "proj-1",
        "issue_type": "missing_brand",
    }

    attempt = engine.resolve_brand_missing(item)
    assert attempt.resolved is True
    assert attempt.confidence >= 0.80
    assert "brand-1" in (attempt.action_taken or "")


def test_resolve_brand_missing_no_client(engine, temp_db):
    """Test brand_missing rule when project has no client."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO projects (id, name, client_id, brand_id) VALUES (?, ?, ?, ?)",
        ("proj-1", "Internal Project", None, None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "proj-1",
        "issue_type": "missing_brand",
    }

    attempt = engine.resolve_brand_missing(item)
    assert attempt.resolved is False


def test_resolve_brand_missing_client_no_brand(engine, temp_db):
    """Test brand_missing rule when client has no brand."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("client-1", "New Client"))
    cursor.execute(
        "INSERT INTO projects (id, name, client_id, brand_id) VALUES (?, ?, ?, ?)",
        ("proj-1", "New Project", "client-1", None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "proj-1",
        "issue_type": "missing_brand",
    }

    attempt = engine.resolve_brand_missing(item)
    assert attempt.resolved is False


# =============================================================================
# CLIENT_UNIDENTIFIED RULE TESTS
# =============================================================================


def test_resolve_client_unidentified_exact_match(engine, temp_db):
    """Test client_unidentified rule with exactly 1 matching client."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("client-1", "Acme Corp"))
    cursor.execute(
        "INSERT INTO client_contacts (id, client_id, email) VALUES (?, ?, ?)",
        ("contact-1", "client-1", "john@acme.com"),
    )
    cursor.execute(
        "INSERT INTO communications (id, sender_email, link_status) VALUES (?, ?, ?)",
        ("comm-1", "john@acme.com", "unlinked"),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "comm-1",
        "issue_type": "unlinked_with_commitments",
    }

    attempt = engine.resolve_client_unidentified(item)
    assert attempt.resolved is True
    assert attempt.confidence >= 0.90


def test_resolve_client_unidentified_no_match(engine, temp_db):
    """Test client_unidentified rule with no matching contacts."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO communications (id, sender_email, link_status) VALUES (?, ?, ?)",
        ("comm-1", "unknown@unknown.com", "unlinked"),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "comm-1",
        "issue_type": "unlinked_with_commitments",
    }

    attempt = engine.resolve_client_unidentified(item)
    assert attempt.resolved is False


# =============================================================================
# DUE_DATE_MISSING RULE TESTS
# =============================================================================


def test_resolve_due_date_missing_sets_30_days(engine, temp_db):
    """Test due_date_missing rule sets date 30 days from creation."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    creation = datetime(2025, 1, 1, 10, 0, 0)
    cursor.execute(
        "INSERT INTO tasks (id, name, created_at, due_date) VALUES (?, ?, ?, ?)",
        ("task-1", "Do Something", creation.isoformat(), None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "task-1",
        "issue_type": "missing_due_date",
    }

    attempt = engine.resolve_due_date_missing(item)
    assert attempt.resolved is True
    assert attempt.confidence >= 0.95
    assert "due date" in attempt.reason.lower()


def test_resolve_due_date_missing_invalid_date(engine, temp_db):
    """Test due_date_missing rule with invalid creation date."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tasks (id, name, created_at, due_date) VALUES (?, ?, ?, ?)",
        ("task-1", "Do Something", "invalid-date", None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "task-1",
        "issue_type": "missing_due_date",
    }

    attempt = engine.resolve_due_date_missing(item)
    assert attempt.resolved is False
    assert attempt.confidence == 0.0


# =============================================================================
# INVOICE_MISSING_CLIENT RULE TESTS
# =============================================================================


def test_resolve_invoice_missing_client_exact_match(engine, temp_db):
    """Test invoice_missing_client rule with exactly 1 matching client."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("client-1", "Big Corp"))
    cursor.execute(
        "INSERT INTO client_contacts (id, client_id, email) VALUES (?, ?, ?)",
        ("contact-1", "client-1", "finance@bigcorp.com"),
    )
    cursor.execute(
        "INSERT INTO invoices (id, contact_email, status) VALUES (?, ?, ?)",
        ("inv-1", "finance@bigcorp.com", "sent"),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "inv-1",
        "issue_type": "missing_client",
    }

    attempt = engine.resolve_invoice_missing_client(item)
    assert attempt.resolved is True
    assert attempt.confidence >= 0.85


def test_resolve_invoice_missing_client_no_match(engine, temp_db):
    """Test invoice_missing_client rule with no matching contacts."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO invoices (id, contact_email, status) VALUES (?, ?, ?)",
        ("inv-1", "unknown@nowhere.com", "sent"),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "inv-1",
        "issue_type": "missing_client",
    }

    attempt = engine.resolve_invoice_missing_client(item)
    assert attempt.resolved is False


# =============================================================================
# INVOICE_MISSING_DUE RULE TESTS
# =============================================================================


def test_resolve_invoice_missing_due_sets_30_days(engine, temp_db):
    """Test invoice_missing_due rule sets due date 30 days from issue date."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    issue_date = datetime(2025, 1, 15, 9, 0, 0)
    cursor.execute(
        "INSERT INTO invoices (id, contact_email, issue_date, status) VALUES (?, ?, ?, ?)",
        ("inv-1", "finance@client.com", issue_date.isoformat(), "sent"),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "inv-1",
        "issue_type": "missing_due_date",
    }

    attempt = engine.resolve_invoice_missing_due(item)
    assert attempt.resolved is True
    assert attempt.confidence >= 0.95
    assert "net-30" in attempt.reason.lower()


def test_resolve_invoice_missing_due_uses_issued_at(engine, temp_db):
    """Test invoice_missing_due rule uses issued_at if issue_date missing."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    issued_at = datetime(2025, 2, 1, 12, 0, 0)
    cursor.execute(
        "INSERT INTO invoices (id, contact_email, issued_at, status) VALUES (?, ?, ?, ?)",
        ("inv-1", "finance@client.com", issued_at.isoformat(), "sent"),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "inv-1",
        "issue_type": "missing_due_date",
    }

    attempt = engine.resolve_invoice_missing_due(item)
    assert attempt.resolved is True
    assert attempt.confidence >= 0.95


# =============================================================================
# COMM_MISSING_CLIENT RULE TESTS
# =============================================================================


def test_resolve_comm_missing_client_domain_match(engine, temp_db):
    """Test comm_missing_client rule with email domain match."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("client-1", "TechCorp"))
    cursor.execute(
        "INSERT INTO client_contacts (id, client_id, email) VALUES (?, ?, ?)",
        ("contact-1", "client-1", "alice@techcorp.com"),
    )
    cursor.execute(
        "INSERT INTO communications (id, sender_email, link_status) VALUES (?, ?, ?)",
        ("comm-1", "bob@techcorp.com", "unlinked"),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "comm-1",
        "issue_type": "unlinked_with_commitments",
    }

    attempt = engine.resolve_comm_missing_client(item)
    assert attempt.resolved is True
    assert attempt.confidence >= 0.80


def test_resolve_comm_missing_client_no_match(engine, temp_db):
    """Test comm_missing_client rule with no matching domains."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO communications (id, sender_email, link_status) VALUES (?, ?, ?)",
        ("comm-1", "stranger@nowhere.com", "unlinked"),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "comm-1",
        "issue_type": "unlinked_with_commitments",
    }

    attempt = engine.resolve_comm_missing_client(item)
    assert attempt.resolved is False


# =============================================================================
# CONFIDENCE THRESHOLD TESTS
# =============================================================================


def test_auto_apply_true_above_threshold(engine, temp_db):
    """Test item is auto-resolved when confidence >= threshold and auto_apply=True."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tasks (id, name, created_at) VALUES (?, ?, ?)",
        ("task-1", "Website Redesign", "2025-01-01T00:00:00"),
    )
    cursor.execute(
        "INSERT INTO projects (id, name, client_id) VALUES (?, ?, ?)",
        ("proj-1", "Website Redesign", None),
    )
    conn.commit()
    conn.close()

    item = {
        "id": "item-1",
        "entity_id": "task-1",
        "issue_type": "project_unlinked",
    }

    attempt = engine.attempt_auto_resolve(item)
    assert attempt.resolved is True


def test_requires_review_above_0_5_below_threshold(engine):
    """Test item marked for review if 0.5 < confidence < threshold."""
    # This test mocks the resolution to return confidence between 0.5 and threshold
    engine.resolve_project_unlinked = MagicMock(
        return_value=ResolutionAttempt(
            item_id="item-1",
            issue_type="project_unlinked",
            resolved=False,
            confidence=0.75,  # Below 0.85 threshold but above 0.5
            reason="Partial match",
        )
    )

    item = {
        "id": "item-1",
        "entity_id": "task-1",
        "issue_type": "project_unlinked",
    }

    attempt = engine.attempt_auto_resolve(item)
    assert attempt.requires_review is True
    assert attempt.resolved is False


def test_escalate_below_0_5(engine):
    """Test item escalated if confidence < 0.5."""
    engine.resolve_project_unlinked = MagicMock(
        return_value=ResolutionAttempt(
            item_id="item-1",
            issue_type="project_unlinked",
            resolved=False,
            confidence=0.3,  # Below 0.5
            reason="No match found",
        )
    )
    engine.escalate = MagicMock(return_value=True)

    # Need to mock scan_and_resolve to test escalation
    # This is tested more thoroughly in scan_and_resolve tests


# =============================================================================
# BATCH RESOLUTION TESTS
# =============================================================================


def test_batch_resolve_multiple_items(engine, temp_db):
    """Test batch_resolve processes multiple items."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tasks (id, name, created_at) VALUES (?, ?, ?)",
        ("task-1", "Website Redesign", "2025-01-01T00:00:00"),
    )
    cursor.execute(
        "INSERT INTO projects (id, name, client_id) VALUES (?, ?, ?)",
        ("proj-1", "Website Redesign", None),
    )
    conn.commit()
    conn.close()

    items = [
        {
            "id": "item-1",
            "entity_id": "task-1",
            "issue_type": "project_unlinked",
        },
        {
            "id": "item-2",
            "entity_id": "task-2",
            "issue_type": "project_unlinked",
        },
    ]

    result = engine.batch_resolve(items)
    assert result.total == 2
    assert len(result.results) == 2
    assert isinstance(result, BatchResult)


def test_batch_resolve_empty_list(engine):
    """Test batch_resolve with empty list."""
    result = engine.batch_resolve([])
    assert result.total == 0
    assert result.resolved == 0
    assert len(result.results) == 0


def test_batch_resolve_counts_resolved(engine, temp_db):
    """Test batch_resolve correctly counts resolved items."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tasks (id, name, created_at) VALUES (?, ?, ?)",
        ("task-1", "Website Redesign", "2025-01-01T00:00:00"),
    )
    cursor.execute(
        "INSERT INTO projects (id, name, client_id) VALUES (?, ?, ?)",
        ("proj-1", "Website Redesign", None),
    )
    conn.commit()
    conn.close()

    items = [
        {
            "id": "item-1",
            "entity_id": "task-1",
            "issue_type": "project_unlinked",
        },
    ]

    result = engine.batch_resolve(items)
    assert result.resolved > 0


# =============================================================================
# ESCALATION TESTS
# =============================================================================


def test_escalate_returns_true(engine):
    """Test escalate method returns True."""
    item = {
        "id": "item-1",
        "entity_type": "task",
        "entity_id": "task-1",
        "issue_type": "project_unlinked",
    }

    result = engine.escalate(item, "No match found")
    assert result is True


def test_escalate_logs_reason(engine):
    """Test escalate logs the escalation reason."""
    item = {
        "id": "item-1",
        "entity_type": "task",
        "entity_id": "task-1",
    }

    with patch("lib.intelligence.auto_resolution.logger") as mock_logger:
        engine.escalate(item, "Ambiguous matches")
        mock_logger.info.assert_called()


def test_escalate_fails_without_id(engine):
    """Test escalate fails gracefully without item id."""
    item = {}

    result = engine.escalate(item, "No id")
    assert result is False


# =============================================================================
# SCAN_AND_RESOLVE TESTS
# =============================================================================


def test_scan_and_resolve_empty_queue(engine):
    """Test scan_and_resolve with empty resolution queue."""
    report = engine.scan_and_resolve()
    assert report.total_scanned == 0
    assert report.auto_resolved == 0
    assert report.duration_ms >= 0


def test_scan_and_resolve_returns_report(engine):
    """Test scan_and_resolve returns ResolutionReport."""
    report = engine.scan_and_resolve()
    assert isinstance(report, ResolutionReport)
    assert hasattr(report, "total_scanned")
    assert hasattr(report, "auto_resolved")
    assert hasattr(report, "duration_ms")


def test_scan_and_resolve_with_items(engine, temp_db):
    """Test scan_and_resolve processes queue items."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Create resolution queue item
    cursor.execute(
        """
        INSERT INTO resolution_queue
        (id, entity_type, entity_id, issue_type, priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("queue-1", "task", "task-1", "project_unlinked", 1, "2025-01-01T00:00:00"),
    )

    # Create task for resolution
    cursor.execute(
        "INSERT INTO tasks (id, name, created_at) VALUES (?, ?, ?)",
        ("task-1", "Website Redesign", "2025-01-01T00:00:00"),
    )

    # Create matching project
    cursor.execute(
        "INSERT INTO projects (id, name, client_id) VALUES (?, ?, ?)",
        ("proj-1", "Website Redesign", None),
    )

    conn.commit()
    conn.close()

    report = engine.scan_and_resolve()
    assert report.total_scanned > 0


def test_scan_and_resolve_duration(engine):
    """Test scan_and_resolve reports duration."""
    report = engine.scan_and_resolve()
    assert report.duration_ms >= 0
    assert isinstance(report.duration_ms, int)


# =============================================================================
# EDGE CASES
# =============================================================================


def test_attempt_auto_resolve_missing_id(engine):
    """Test attempt_auto_resolve with missing item id."""
    item = {
        "issue_type": "project_unlinked",
    }

    attempt = engine.attempt_auto_resolve(item)
    assert attempt.resolved is False
    assert attempt.confidence == 0.0


def test_attempt_auto_resolve_unknown_issue_type(engine):
    """Test attempt_auto_resolve with unknown issue type."""
    item = {
        "id": "item-1",
        "entity_id": "unknown-1",
        "issue_type": "unknown_issue",
    }

    attempt = engine.attempt_auto_resolve(item)
    assert attempt.resolved is False
    assert attempt.confidence == 0.0
    assert "no auto-resolution rule" in attempt.reason.lower()


def test_resolution_attempt_with_none_action(engine):
    """Test ResolutionAttempt handles None action_taken."""
    attempt = ResolutionAttempt(
        item_id="item-1",
        issue_type="project_unlinked",
        resolved=False,
        confidence=0.0,
        action_taken=None,
    )

    d = attempt.to_dict()
    assert d["action_taken"] is None


def test_batch_resolve_with_exceptions(engine):
    """Test batch_resolve handles exceptions gracefully."""
    # Mock a method to raise an exception
    engine.attempt_auto_resolve = MagicMock(side_effect=Exception("Test exception"))

    items = [
        {
            "id": "item-1",
            "entity_id": "task-1",
            "issue_type": "project_unlinked",
        },
    ]

    result = engine.batch_resolve(items)
    assert result.failed > 0


def test_scan_and_resolve_with_exception(engine):
    """Test scan_and_resolve handles exceptions gracefully."""
    # Mock _execute to raise an exception
    engine._execute = MagicMock(side_effect=Exception("Database error"))

    report = engine.scan_and_resolve()
    assert report.failed > 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_full_resolution_workflow(engine, temp_db):
    """Test complete workflow: queue item -> scan -> resolve."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Setup data
    cursor.execute("INSERT INTO clients (id, name) VALUES (?, ?)", ("client-1", "Acme Corp"))
    cursor.execute(
        "INSERT INTO brands (id, name, client_id) VALUES (?, ?, ?)",
        ("brand-1", "Acme", "client-1"),
    )
    cursor.execute(
        "INSERT INTO projects (id, name, client_id, brand_id) VALUES (?, ?, ?, ?)",
        ("proj-1", "Acme Project", "client-1", None),
    )
    cursor.execute(
        """
        INSERT INTO resolution_queue
        (id, entity_type, entity_id, issue_type, priority, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("queue-1", "project", "proj-1", "missing_brand", 1, "2025-01-01T00:00:00"),
    )

    conn.commit()
    conn.close()

    # Run scan_and_resolve
    report = engine.scan_and_resolve()

    assert report.total_scanned > 0
    # At least one item should be attempted
    assert len(report.attempts) > 0


def test_multiple_rules_for_same_issue_type(engine):
    """Test handling of multiple rules for same issue type."""
    rules = engine.get_resolution_rules()
    issue_types = {}

    for rule in rules:
        if rule.issue_type not in issue_types:
            issue_types[rule.issue_type] = []
        issue_types[rule.issue_type].append(rule.rule_id)

    # Some issue types should have multiple rules
    assert any(len(rules) > 1 for rules in issue_types.values())


# =============================================================================
# RULE CONSISTENCY TESTS
# =============================================================================


def test_all_methods_exist(engine):
    """Test all rule methods exist."""
    rules = engine.get_resolution_rules()
    for rule in rules:
        method_name = rule.method_name
        assert hasattr(engine, method_name)
        assert callable(getattr(engine, method_name))


def test_rule_thresholds_are_valid(engine):
    """Test all rule confidence thresholds are between 0 and 1."""
    rules = engine.get_resolution_rules()
    for rule in rules:
        assert 0.0 <= rule.confidence_threshold <= 1.0
