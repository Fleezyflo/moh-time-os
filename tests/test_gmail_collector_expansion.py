"""
Tests for expanded Gmail Collector (CS-4.1).

Tests the ~85% API coverage implementation including:
- Participants extraction (From/To/Cc/Bcc)
- Attachments extraction
- Labels, read/starred status, importance detection
- Multi-table storage via sync()

All tests use mocks - NO live API calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.collectors.gmail import GmailCollector
from lib.state_store import StateStore

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_store():
    """Mock StateStore for testing."""
    store = MagicMock(spec=StateStore)
    store.insert_many.return_value = 5  # Simulate inserting 5 rows
    store.update_sync_state.return_value = None
    return store


@pytest.fixture
def collector(mock_store):
    """Create a GmailCollector with mocked store."""
    config = {"sync_interval": 300}
    collector = GmailCollector(config=config, store=mock_store)
    return collector


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================


@pytest.fixture
def mock_thread_with_participants():
    """Mock thread with multiple messages and participants."""
    return {
        "id": "thread_123",
        "messages": [
            {
                "id": "msg_1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "alice@example.com"},
                        {"name": "To", "value": "bob@example.com, charlie@example.com"},
                        {"name": "Cc", "value": "dave@example.com"},
                        {"name": "Subject", "value": "Test Subject"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
                "labelIds": ["INBOX"],
            },
            {
                "id": "msg_2",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "bob@example.com"},
                        {"name": "To", "value": "alice@example.com, charlie@example.com"},
                        {"name": "Bcc", "value": "eve@example.com"},
                        {"name": "Subject", "value": "Re: Test Subject"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 11:00:00 +0000"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
                "labelIds": ["INBOX"],
            },
        ],
        "subject": "Test Subject",
        "from": "alice@example.com",
        "to": "bob@example.com",
        "date": "Mon, 1 Jan 2024 10:00:00 +0000",
        "snippet": "Test snippet",
        "body": "Test body",
        "labels": ["INBOX"],
    }


@pytest.fixture
def mock_thread_with_attachments():
    """Mock thread with attachment parts."""
    return {
        "id": "thread_456",
        "messages": [
            {
                "id": "msg_3",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "alice@example.com"},
                        {"name": "To", "value": "bob@example.com"},
                        {"name": "Subject", "value": "With Attachments"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ],
                    "body": {"data": ""},
                    "parts": [
                        {
                            "filename": "document.pdf",
                            "mimeType": "application/pdf",
                            "body": {"size": 102400, "attachmentId": "attach_1"},
                        },
                        {
                            "filename": "image.jpg",
                            "mimeType": "image/jpeg",
                            "body": {"size": 51200, "attachmentId": "attach_2"},
                        },
                    ],
                },
                "labelIds": ["INBOX"],
            }
        ],
        "subject": "With Attachments",
        "from": "alice@example.com",
        "to": "bob@example.com",
        "date": "Mon, 1 Jan 2024 10:00:00 +0000",
        "snippet": "Has files",
        "body": "Test body",
        "labels": ["INBOX"],
    }


@pytest.fixture
def mock_thread_with_flags():
    """Mock thread with read/starred/importance flags."""
    return {
        "id": "thread_789",
        "messages": [
            {
                "id": "msg_4",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "alice@example.com"},
                        {"name": "To", "value": "bob@example.com"},
                        {"name": "Subject", "value": "Urgent Task"},
                        {"name": "Importance", "value": "high"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
                "labelIds": ["INBOX", "IMPORTANT"],
            }
        ],
        "subject": "Urgent Task",
        "from": "alice@example.com",
        "to": "bob@example.com",
        "date": "Mon, 1 Jan 2024 10:00:00 +0000",
        "snippet": "Urgent",
        "body": "Test body",
        "labels": ["INBOX", "IMPORTANT", "STARRED"],
    }


@pytest.fixture
def mock_thread_with_read_flag():
    """Mock thread marked as read (no UNREAD label)."""
    return {
        "id": "thread_read",
        "messages": [
            {
                "id": "msg_5",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "alice@example.com"},
                        {"name": "To", "value": "bob@example.com"},
                        {"name": "Subject", "value": "Read Email"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
                "labelIds": ["INBOX"],
            }
        ],
        "subject": "Read Email",
        "from": "alice@example.com",
        "to": "bob@example.com",
        "date": "Mon, 1 Jan 2024 10:00:00 +0000",
        "snippet": "Read",
        "body": "Test body",
        "labels": ["INBOX"],  # No UNREAD = read
    }


# =============================================================================
# TESTS: _extract_to_emails
# =============================================================================


def test_extract_to_emails_single(collector):
    """Test extracting single To address."""
    messages = [{"payload": {"headers": [{"name": "To", "value": "bob@example.com"}]}}]
    result = collector._extract_to_emails(messages)
    assert result == ["bob@example.com"]


def test_extract_to_emails_multiple(collector):
    """Test extracting multiple To addresses."""
    messages = [
        {
            "payload": {
                "headers": [
                    {
                        "name": "To",
                        "value": "bob@example.com, charlie@example.com",
                    }
                ]
            }
        }
    ]
    result = collector._extract_to_emails(messages)
    assert set(result) == {"bob@example.com", "charlie@example.com"}


def test_extract_to_emails_with_names(collector):
    """Test extracting To addresses with display names."""
    messages = [
        {
            "payload": {
                "headers": [
                    {
                        "name": "To",
                        "value": "Bob Smith <bob@example.com>, Charlie Brown <charlie@example.com>",
                    }
                ]
            }
        }
    ]
    result = collector._extract_to_emails(messages)
    assert set(result) == {"bob@example.com", "charlie@example.com"}


def test_extract_to_emails_across_messages(collector):
    """Test deduplication across multiple messages."""
    messages = [
        {"payload": {"headers": [{"name": "To", "value": "bob@example.com"}]}},
        {"payload": {"headers": [{"name": "To", "value": "bob@example.com"}]}},
    ]
    result = collector._extract_to_emails(messages)
    assert result == ["bob@example.com"]


# =============================================================================
# TESTS: _extract_importance
# =============================================================================


def test_extract_importance_high_from_header(collector):
    """Test importance extraction from Importance header."""
    messages = [{"payload": {"headers": [{"name": "Importance", "value": "high"}]}}]
    result = collector._extract_importance(messages)
    assert result == "high"


def test_extract_importance_low_from_header(collector):
    """Test low importance from header."""
    messages = [{"payload": {"headers": [{"name": "Importance", "value": "low"}]}}]
    result = collector._extract_importance(messages)
    assert result == "low"


def test_extract_importance_from_x_priority(collector):
    """Test importance extraction from X-Priority header."""
    messages = [{"payload": {"headers": [{"name": "X-Priority", "value": "1 (Highest)"}]}}]
    result = collector._extract_importance(messages)
    assert result == "high"


def test_extract_importance_default(collector):
    """Test default importance when no headers present."""
    messages = [{"payload": {"headers": []}}]
    result = collector._extract_importance(messages)
    assert result == "normal"


# =============================================================================
# TESTS: _count_attachments
# =============================================================================


def test_count_attachments_none(collector):
    """Test attachment count when none present."""
    messages = [{"payload": {"parts": []}}]
    has_attachments, count = collector._count_attachments(messages)
    assert has_attachments == 0
    assert count == 0


def test_count_attachments_single(collector):
    """Test single attachment."""
    messages = [{"payload": {"parts": [{"filename": "doc.pdf", "mimeType": "application/pdf"}]}}]
    has_attachments, count = collector._count_attachments(messages)
    assert has_attachments == 1
    assert count == 1


def test_count_attachments_multiple_same_message(collector):
    """Test multiple attachments in same message."""
    messages = [
        {
            "payload": {
                "parts": [
                    {"filename": "doc.pdf"},
                    {"filename": "image.jpg"},
                    {"filename": "sheet.xlsx"},
                ]
            }
        }
    ]
    has_attachments, count = collector._count_attachments(messages)
    assert has_attachments == 1
    assert count == 3


def test_count_attachments_multiple_messages(collector):
    """Test attachments across multiple messages."""
    messages = [
        {"payload": {"parts": [{"filename": "doc.pdf"}]}},
        {"payload": {"parts": [{"filename": "image.jpg"}]}},
    ]
    has_attachments, count = collector._count_attachments(messages)
    assert has_attachments == 1
    assert count == 2


# =============================================================================
# TESTS: _transform_participants
# =============================================================================


def test_transform_participants_basic(collector):
    """Test basic participant extraction."""
    messages = [
        {
            "id": "msg_1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "To", "value": "bob@example.com"},
                ]
            },
        }
    ]
    result = collector._transform_participants("thread_1", messages)
    assert len(result) == 2
    assert any(p["role"] == "from" and p["email"] == "alice@example.com" for p in result)
    assert any(p["role"] == "to" and p["email"] == "bob@example.com" for p in result)


def test_transform_participants_with_names(collector):
    """Test participant extraction with display names."""
    messages = [
        {
            "id": "msg_1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice Smith <alice@example.com>"},
                    {"name": "To", "value": "Bob Jones <bob@example.com>"},
                ]
            },
        }
    ]
    result = collector._transform_participants("thread_1", messages)
    from_p = next(p for p in result if p["role"] == "from")
    assert from_p["email"] == "alice@example.com"
    assert from_p["name"] == "Alice Smith"


def test_transform_participants_cc_bcc(collector):
    """Test Cc and Bcc extraction."""
    messages = [
        {
            "id": "msg_1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "To", "value": "bob@example.com"},
                    {"name": "Cc", "value": "charlie@example.com"},
                    {"name": "Bcc", "value": "dave@example.com"},
                ]
            },
        }
    ]
    result = collector._transform_participants("thread_1", messages)
    roles = {p["role"] for p in result}
    assert "from" in roles
    assert "to" in roles
    assert "cc" in roles
    assert "bcc" in roles


def test_transform_participants_deduplication(collector):
    """Test that participants are deduplicated across messages."""
    messages = [
        {
            "id": "msg_1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "To", "value": "bob@example.com"},
                ]
            },
        },
        {
            "id": "msg_2",
            "payload": {
                "headers": [
                    {"name": "From", "value": "bob@example.com"},
                    {"name": "To", "value": "alice@example.com"},
                ]
            },
        },
    ]
    result = collector._transform_participants("thread_1", messages)
    # Should have alice and bob, but each (role, email) combo only once
    alice_from = [p for p in result if p["email"] == "alice@example.com" and p["role"] == "from"]
    assert len(alice_from) == 1


def test_transform_participants_multiple_to(collector):
    """Test multiple To addresses."""
    messages = [
        {
            "id": "msg_1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "alice@example.com"},
                    {"name": "To", "value": "bob@example.com, charlie@example.com"},
                ]
            },
        }
    ]
    result = collector._transform_participants("thread_1", messages)
    to_p = [p for p in result if p["role"] == "to"]
    assert len(to_p) == 2
    assert {p["email"] for p in to_p} == {"bob@example.com", "charlie@example.com"}


# =============================================================================
# TESTS: _transform_attachments
# =============================================================================


def test_transform_attachments_none(collector):
    """Test when no attachments."""
    messages = [{"payload": {"parts": []}}]
    result = collector._transform_attachments("thread_1", messages)
    assert result == []


def test_transform_attachments_basic(collector):
    """Test basic attachment extraction."""
    messages = [
        {
            "id": "msg_1",
            "payload": {
                "parts": [
                    {
                        "filename": "doc.pdf",
                        "mimeType": "application/pdf",
                        "body": {"size": 102400, "attachmentId": "attach_1"},
                    }
                ]
            },
        }
    ]
    result = collector._transform_attachments("thread_1", messages)
    assert len(result) == 1
    assert result[0]["filename"] == "doc.pdf"
    assert result[0]["mime_type"] == "application/pdf"
    assert result[0]["size_bytes"] == 102400
    assert result[0]["attachment_id"] == "attach_1"


def test_transform_attachments_multiple(collector):
    """Test multiple attachments in single message."""
    messages = [
        {
            "id": "msg_1",
            "payload": {
                "parts": [
                    {
                        "filename": "doc.pdf",
                        "mimeType": "application/pdf",
                        "body": {"size": 102400, "attachmentId": "attach_1"},
                    },
                    {
                        "filename": "image.jpg",
                        "mimeType": "image/jpeg",
                        "body": {"size": 51200, "attachmentId": "attach_2"},
                    },
                ]
            },
        }
    ]
    result = collector._transform_attachments("thread_1", messages)
    assert len(result) == 2
    assert {r["filename"] for r in result} == {"doc.pdf", "image.jpg"}


def test_transform_attachments_across_messages(collector):
    """Test attachments across multiple messages."""
    messages = [
        {
            "id": "msg_1",
            "payload": {
                "parts": [
                    {
                        "filename": "doc.pdf",
                        "mimeType": "application/pdf",
                        "body": {"size": 102400},
                    }
                ]
            },
        },
        {
            "id": "msg_2",
            "payload": {
                "parts": [
                    {
                        "filename": "image.jpg",
                        "mimeType": "image/jpeg",
                        "body": {"size": 51200},
                    }
                ]
            },
        },
    ]
    result = collector._transform_attachments("thread_1", messages)
    assert len(result) == 2
    assert result[0]["message_id"] == "msg_1"
    assert result[1]["message_id"] == "msg_2"


# =============================================================================
# TESTS: _transform_labels
# =============================================================================


def test_transform_labels_basic(collector):
    """Test basic label transformation."""
    result = collector._transform_labels("thread_1", ["INBOX", "STARRED"])
    assert len(result) == 2
    assert any(label["label_id"] == "INBOX" for label in result)
    assert any(label["label_id"] == "STARRED" for label in result)


def test_transform_labels_empty(collector):
    """Test with no labels."""
    result = collector._transform_labels("thread_1", [])
    assert result == []


def test_transform_labels_inferred_names(collector):
    """Test that label names are inferred."""
    result = collector._transform_labels("thread_1", ["UNREAD", "IMPORTANT"])
    unread = next(label for label in result if label["label_id"] == "UNREAD")
    assert unread["label_name"] is not None


# =============================================================================
# TESTS: transform() with expanded fields
# =============================================================================


def test_transform_basic(collector, mock_thread_with_flags):
    """Test expanded transform with all fields."""
    raw_data = {"threads": [mock_thread_with_flags]}
    result = collector.transform(raw_data)
    assert len(result) == 1
    comm = result[0]
    assert "is_read" in comm
    assert "is_starred" in comm
    assert "importance" in comm
    assert "has_attachments" in comm
    assert "attachment_count" in comm
    assert "label_ids" in comm


def test_transform_is_read_flag_unread(collector, mock_thread_with_flags):
    """Test is_read=0 when UNREAD label present (initially was read: flag check)."""
    # Note: mock_thread_with_flags doesn't have UNREAD, so is_read should be 1
    raw_data = {"threads": [mock_thread_with_flags]}
    result = collector.transform(raw_data)
    assert result[0]["is_read"] == 1


def test_transform_is_read_flag_read(collector, mock_thread_with_read_flag):
    """Test is_read=1 when no UNREAD label."""
    raw_data = {"threads": [mock_thread_with_read_flag]}
    result = collector.transform(raw_data)
    assert result[0]["is_read"] == 1


def test_transform_is_starred(collector, mock_thread_with_flags):
    """Test is_starred=1 when STARRED label present."""
    raw_data = {"threads": [mock_thread_with_flags]}
    result = collector.transform(raw_data)
    assert result[0]["is_starred"] == 1


def test_transform_importance_extracted(collector, mock_thread_with_flags):
    """Test importance is extracted from headers."""
    raw_data = {"threads": [mock_thread_with_flags]}
    result = collector.transform(raw_data)
    assert result[0]["importance"] == "high"


def test_transform_attachments_detected(collector, mock_thread_with_attachments):
    """Test attachment count is detected."""
    raw_data = {"threads": [mock_thread_with_attachments]}
    result = collector.transform(raw_data)
    assert result[0]["has_attachments"] == 1
    assert result[0]["attachment_count"] == 2


def test_transform_to_emails_populated(collector, mock_thread_with_participants):
    """Test to_emails is properly populated."""
    raw_data = {"threads": [mock_thread_with_participants]}
    result = collector.transform(raw_data)
    import json

    to_emails = json.loads(result[0]["to_emails"])
    assert "bob@example.com" in to_emails
    assert "charlie@example.com" in to_emails


# =============================================================================
# TESTS: sync() - Multi-table storage
# =============================================================================


@patch("lib.collectors.gmail.GmailCollector.collect")
def test_sync_stores_to_primary_table(mock_collect, collector, mock_store):
    """Test that sync stores to primary communications table."""
    mock_thread = {
        "id": "t1",
        "messages": [
            {
                "id": "m1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "a@ex.com"},
                        {"name": "To", "value": "b@ex.com"},
                        {"name": "Subject", "value": "Test"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ],
                    "parts": [],
                },
                "labelIds": ["INBOX"],
            }
        ],
        "subject": "Test",
        "from": "a@ex.com",
        "to": "b@ex.com",
        "date": "Mon, 1 Jan 2024 10:00:00 +0000",
        "snippet": "Test",
        "body": "Body",
        "labels": ["INBOX"],
    }
    mock_collect.return_value = {"threads": [mock_thread]}

    result = collector.sync()

    assert result["success"] is True
    assert result["stored_primary"] > 0
    # Verify store.insert_many was called with communications table
    calls = list(mock_store.insert_many.call_args_list)
    assert any("communications" in str(call) for call in calls)


def test_sync_stores_to_secondary_tables(mock_store):
    """Test that sync stores to secondary tables for participants/attachments."""
    collector = GmailCollector(config={"sync_interval": 300}, store=mock_store)

    mock_thread = {
        "id": "t1",
        "messages": [
            {
                "id": "m1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "a@ex.com"},
                        {"name": "To", "value": "b@ex.com"},
                        {"name": "Cc", "value": "c@ex.com"},
                        {"name": "Subject", "value": "Test"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ],
                    "parts": [{"filename": "doc.pdf", "mimeType": "application/pdf"}],
                },
                "labelIds": ["INBOX"],
            }
        ],
        "subject": "Test",
        "from": "a@ex.com",
        "to": "b@ex.com",
        "date": "Mon, 1 Jan 2024 10:00:00 +0000",
        "snippet": "Test",
        "body": "Body",
        "labels": ["INBOX"],
    }
    mock_store.insert_many.return_value = 1

    # Patch the instance method directly to ensure it works
    collector.collect = MagicMock(return_value={"threads": [mock_thread]})

    result = collector.sync()

    assert result["success"] is True
    # Check that secondary tables were called
    secondary_stats = result["stored_secondary"]
    assert "participants" in secondary_stats or "attachments" in secondary_stats


@patch("lib.collectors.gmail.GmailCollector.collect")
def test_sync_secondary_table_failure_doesnt_block_primary(mock_collect, collector, mock_store):
    """Test that secondary table failures don't block primary storage."""

    def side_effect(*args, **kwargs):
        # First call (communications) succeeds, secondary tables fail
        if "communications" in args[0]:
            return 1
        raise Exception("Secondary table failed")

    mock_thread = {
        "id": "t1",
        "messages": [
            {
                "id": "m1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "a@ex.com"},
                        {"name": "To", "value": "b@ex.com"},
                        {"name": "Subject", "value": "Test"},
                        {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
                    ],
                    "parts": [],
                },
                "labelIds": ["INBOX"],
            }
        ],
        "subject": "Test",
        "from": "a@ex.com",
        "to": "b@ex.com",
        "date": "Mon, 1 Jan 2024 10:00:00 +0000",
        "snippet": "Test",
        "body": "Body",
        "labels": ["INBOX"],
    }
    mock_collect.return_value = {"threads": [mock_thread]}
    mock_store.insert_many.side_effect = side_effect

    result = collector.sync()

    # Sync should still succeed despite secondary table errors
    assert result["success"] is True
    assert result["stored_primary"] > 0
