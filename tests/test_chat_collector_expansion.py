"""
Tests for expanded Chat Collector (CS-4.2).

Tests the ~85% API coverage implementation including:
- Message collection with reactions and attachments
- Threading depth and message counts
- Space metadata (display name, type, member count, threaded flag)
- Space member roster (display names, emails, roles)
- Multi-table storage in sync()

All tests use mocks - NO live API calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.collectors.chat import ChatCollector
from lib.state_store import StateStore  # noqa: F401

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_store():
    """Mock StateStore for testing."""
    store = MagicMock(spec=StateStore)
    store.insert_many.return_value = 5  # Simulate inserting 5 rows
    return store


@pytest.fixture
def collector(mock_store):
    """Create a ChatCollector with mocked store."""
    config = {"sync_interval": 300, "max_spaces": 50, "max_messages_per_space": 30}
    collector = ChatCollector(config=config, store=mock_store)
    return collector


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================


@pytest.fixture
def mock_space():
    """Mock space object."""
    return {
        "name": "spaces/AAAAgR-nJDI",
        "displayName": "Engineering",
        "spaceType": "SPACE",
        "threaded": True,
        "memberCount": 12,
        "createTime": "2025-01-15T10:00:00Z",
    }


@pytest.fixture
def mock_message_with_reactions_and_attachments():
    """Mock message with reactions and attachments."""
    return {
        "name": "spaces/AAAAgR-nJDI/messages/MTMzNzk5MjQ5NzAz",
        "sender": {
            "name": "users/123456",
            "displayName": "John Doe",
            "email": "john@example.com",
        },
        "text": "Check out the attached report @molham",
        "createTime": "2026-02-21T10:00:00Z",
        "thread": {"name": "spaces/AAAAgR-nJDI/threads/MTMzNzk5MjQ5NzAz"},
        "reactionCounts": [
            {
                "emoji": {"unicode": "👍"},
                "count": 2,
            },
            {
                "emoji": {"unicode": "🎉"},
                "count": 1,
            },
        ],
        "attachments": [
            {
                "name": "Report_Q1_2026.pdf",
                "contentType": "application/pdf",
                "source": {"resourceName": "https://storage.googleapis.com/report.pdf"},
                "thumbnailUri": "https://storage.googleapis.com/report_thumb.png",
            }
        ],
    }


@pytest.fixture
def mock_message_simple():
    """Mock simple message without reactions or attachments."""
    return {
        "name": "spaces/AAAAgR-nJDI/messages/MTMzNzk5MjQ5NzA0",
        "sender": {
            "name": "users/789012",
            "displayName": "Jane Smith",
            "email": "jane@example.com",
        },
        "text": "Great progress on the feature!",
        "createTime": "2026-02-21T09:00:00Z",
        "thread": {},
        "reactionCounts": [],
        "attachments": [],
    }


@pytest.fixture
def mock_member():
    """Mock space member."""
    return {
        "name": "spaces/AAAAgR-nJDI/members/users/123456",
        "member": {
            "name": "users/123456",
            "displayName": "John Doe",
            "email": "john@example.com",
        },
        "role": "MANAGER",
        "memberType": "HUMAN",
    }


@pytest.fixture
def mock_member_bot():
    """Mock space member (bot)."""
    return {
        "name": "spaces/AAAAgR-nJDI/members/users/bot-id",
        "member": {
            "name": "users/bot-id",
            "displayName": "Assistant Bot",
            "email": "bot@example.com",
        },
        "role": "MEMBER",
        "memberType": "BOT",
    }


# =============================================================================
# TESTS: Transform Methods
# =============================================================================


def test_transform_message_with_reactions_and_attachments(
    collector, mock_message_with_reactions_and_attachments
):
    """Test transforming message with reactions and attachments."""
    raw_data = {
        "messages": [mock_message_with_reactions_and_attachments],
        "spaces": [],
        "space_metadata": {},
        "space_members_by_space": {},
    }

    transformed = collector.transform(raw_data)

    assert len(transformed) == 1
    msg = transformed[0]
    assert msg["id"] == "spaces/AAAAgR-nJDI/messages/MTMzNzk5MjQ5NzAz"
    assert msg["sender_name"] == "John Doe"
    assert msg["text"] == "Check out the attached report @molham"
    assert msg["reaction_count"] == 3  # 2 + 1
    assert msg["attachment_count"] == 1
    assert msg["has_attachment"] == 1
    assert msg["thread_id"] == "spaces/AAAAgR-nJDI/threads/MTMzNzk5MjQ5NzAz"


def test_transform_message_simple(collector, mock_message_simple):
    """Test transforming simple message without reactions/attachments."""
    raw_data = {
        "messages": [mock_message_simple],
        "spaces": [],
        "space_metadata": {},
        "space_members_by_space": {},
    }

    transformed = collector.transform(raw_data)

    assert len(transformed) == 1
    msg = transformed[0]
    assert msg["sender_name"] == "Jane Smith"
    assert msg["reaction_count"] == 0
    assert msg["attachment_count"] == 0
    assert msg["has_attachment"] == 0
    assert msg["thread_id"] == ""


def test_transform_multiple_messages(
    collector, mock_message_with_reactions_and_attachments, mock_message_simple
):
    """Test transforming multiple messages."""
    raw_data = {
        "messages": [mock_message_with_reactions_and_attachments, mock_message_simple],
        "spaces": [],
        "space_metadata": {},
        "space_members_by_space": {},
    }

    transformed = collector.transform(raw_data)

    assert len(transformed) == 2


# =============================================================================
# TESTS: Reaction Transformation
# =============================================================================


def test_transform_reactions(collector, mock_message_with_reactions_and_attachments):
    """Test transforming reactions to chat_reactions table."""
    msg_name = "spaces/AAAAgR-nJDI/messages/MTMzNzk5MjQ5NzAz"
    reactions = mock_message_with_reactions_and_attachments.get("reactionCounts", [])

    rows = collector._transform_reactions(msg_name, reactions)

    assert len(rows) == 2
    assert rows[0]["message_id"] == msg_name
    assert rows[0]["emoji"] == "👍"
    assert rows[1]["emoji"] == "🎉"


def test_transform_reactions_empty(collector):
    """Test transforming empty reactions."""
    rows = collector._transform_reactions("msg_id", [])
    assert len(rows) == 0


def test_transform_reactions_none(collector):
    """Test transforming None reactions."""
    rows = collector._transform_reactions("msg_id", None)
    assert len(rows) == 0


# =============================================================================
# TESTS: Attachment Transformation
# =============================================================================


def test_transform_attachments(collector, mock_message_with_reactions_and_attachments):
    """Test transforming attachments to chat_attachments table."""
    msg_name = "spaces/AAAAgR-nJDI/messages/MTMzNzk5MjQ5NzAz"
    attachments = mock_message_with_reactions_and_attachments.get("attachments", [])

    rows = collector._transform_attachments(msg_name, attachments)

    assert len(rows) == 1
    att = rows[0]
    assert att["message_id"] == msg_name
    assert att["name"] == "Report_Q1_2026.pdf"
    assert att["content_type"] == "application/pdf"
    assert att["source_uri"] == "https://storage.googleapis.com/report.pdf"
    assert att["thumbnail_uri"] == "https://storage.googleapis.com/report_thumb.png"


def test_transform_attachments_multiple(collector):
    """Test transforming multiple attachments."""
    msg_name = "spaces/space1/messages/msg1"
    attachments = [
        {
            "name": "file1.pdf",
            "contentType": "application/pdf",
            "source": {"resourceName": "uri1"},
        },
        {
            "name": "file2.png",
            "contentType": "image/png",
            "source": {"resourceName": "uri2"},
        },
    ]

    rows = collector._transform_attachments(msg_name, attachments)

    assert len(rows) == 2
    assert rows[0]["name"] == "file1.pdf"
    assert rows[1]["name"] == "file2.png"


def test_transform_attachments_empty(collector):
    """Test transforming empty attachments."""
    rows = collector._transform_attachments("msg_id", [])
    assert len(rows) == 0


# =============================================================================
# TESTS: Space Metadata Transformation
# =============================================================================


def test_transform_space_metadata(collector, mock_space):
    """Test transforming space to chat_space_metadata table."""
    row = collector._transform_space_metadata(mock_space)

    assert row["space_id"] == "spaces/AAAAgR-nJDI"
    assert row["display_name"] == "Engineering"
    assert row["space_type"] == "SPACE"
    assert row["threaded"] == 1
    assert row["member_count"] == 12
    assert row["created_time"] == "2025-01-15T10:00:00Z"
    assert "last_synced" in row


def test_transform_space_metadata_no_threading(collector):
    """Test transforming space without threading."""
    space = {
        "name": "spaces/space1",
        "displayName": "General",
        "spaceType": "SPACE",
        "threaded": False,
        "memberCount": 5,
    }

    row = collector._transform_space_metadata(space)

    assert row["threaded"] == 0
    assert row["display_name"] == "General"


def test_transform_space_metadata_empty(collector):
    """Test transforming space with no name."""
    space = {"displayName": "No Name"}
    row = collector._transform_space_metadata(space)
    assert row == {}


# =============================================================================
# TESTS: Member Transformation
# =============================================================================


def test_transform_members(collector, mock_member):
    """Test transforming members to chat_space_members table."""
    space_name = "spaces/AAAAgR-nJDI"
    members = [mock_member]

    rows = collector._transform_members(space_name, members)

    assert len(rows) == 1
    member = rows[0]
    assert member["space_id"] == space_name
    assert member["member_id"] == "spaces/AAAAgR-nJDI/members/users/123456"
    assert member["display_name"] == "John Doe"
    assert member["email"] == "john@example.com"
    assert member["role"] == "MANAGER"


def test_transform_members_including_bot(collector, mock_member, mock_member_bot):
    """Test transforming members including bots."""
    space_name = "spaces/AAAAgR-nJDI"
    members = [mock_member, mock_member_bot]

    rows = collector._transform_members(space_name, members)

    assert len(rows) == 2
    assert rows[0]["display_name"] == "John Doe"
    assert rows[1]["display_name"] == "Assistant Bot"


def test_transform_members_empty(collector):
    """Test transforming empty members list."""
    rows = collector._transform_members("space_id", [])
    assert len(rows) == 0


def test_transform_members_none(collector):
    """Test transforming None members."""
    rows = collector._transform_members("space_id", None)
    assert len(rows) == 0


# =============================================================================
# TESTS: Sync Method (Multi-Table Storage)
# =============================================================================


def test_sync_stores_all_tables(
    collector, mock_store, mock_message_with_reactions_and_attachments, mock_space, mock_member
):
    """Test sync stores data in all tables."""
    raw_data = {
        "messages": [mock_message_with_reactions_and_attachments],
        "spaces": [mock_space],
        "space_metadata": {mock_space["name"]: mock_space},
        "space_members_by_space": {"spaces/AAAAgR-nJDI": [mock_member]},
    }

    with patch.object(collector, "collect", return_value=raw_data):
        result = collector.sync()

    assert result["success"] is True
    assert result["source"] == "chat"
    assert result["collected"] == 1
    assert result["transformed"] == 1
    assert result["secondary_tables"]["reactions"] == 5
    assert result["secondary_tables"]["attachments"] == 5
    assert result["secondary_tables"]["space_metadata"] == 5
    assert result["secondary_tables"]["space_members"] == 5

    # Verify insert_many was called for all tables
    assert mock_store.insert_many.call_count == 5  # messages + 4 secondary tables


def test_sync_handles_partial_failure(collector, mock_store):
    """Test sync continues on partial failures."""
    raw_data = {
        "messages": [
            {
                "name": "spaces/space1/messages/msg1",
                "sender": {"name": "user1", "displayName": "User 1"},
                "text": "message",
                "createTime": "2026-02-21T10:00:00Z",
                "reactionCounts": [],
                "attachments": [],
            }
        ],
        "spaces": [],
        "space_metadata": {},
        "space_members_by_space": {},
    }

    # Make one call succeed, others fail
    mock_store.insert_many.side_effect = [5, Exception("DB error"), 0, 0, 0]

    with patch.object(collector, "collect", return_value=raw_data):
        result = collector.sync()

    assert result["success"] is True
    # Should have stored messages, reactions failed, rest are 0


def test_sync_no_messages(collector, mock_store):
    """Test sync with no messages."""
    raw_data = {
        "messages": [],
        "spaces": [],
        "space_metadata": {},
        "space_members_by_space": {},
    }

    with patch.object(collector, "collect", return_value=raw_data):
        result = collector.sync()

    assert result["success"] is True
    assert result["collected"] == 0
    assert result["transformed"] == 0


# =============================================================================
# TESTS: Collect Method
# =============================================================================


@patch("lib.collectors.chat.ChatCollector._list_spaces")
@patch("lib.collectors.chat.ChatCollector._list_messages")
@patch("lib.collectors.chat.ChatCollector._list_members")
def test_collect_basic(mock_members, mock_messages, mock_spaces, collector, mock_space):
    """Test basic collect flow."""
    mock_spaces.return_value = [mock_space]
    mock_messages.return_value = [
        {
            "name": "msg1",
            "sender": {"displayName": "User"},
            "text": "test",
            "createTime": "2026-02-21T10:00:00Z",
            "reactionCounts": [],
            "attachments": [],
        }
    ]
    mock_members.return_value = []

    result = collector.collect()

    assert "messages" in result
    assert "spaces" in result
    assert "space_metadata" in result
    assert "space_members_by_space" in result


# =============================================================================
# TESTS: Edge Cases
# =============================================================================


def test_message_missing_sender(collector):
    """Test handling message with missing sender."""
    raw_data = {
        "messages": [
            {
                "name": "spaces/space1/messages/msg1",
                "sender": None,
                "text": "message",
                "createTime": "2026-02-21T10:00:00Z",
                "reactionCounts": [],
                "attachments": [],
            }
        ],
        "spaces": [],
        "space_metadata": {},
        "space_members_by_space": {},
    }

    transformed = collector.transform(raw_data)

    assert len(transformed) == 1
    assert transformed[0]["sender_name"] == ""
    assert transformed[0]["sender_email"] == ""


def test_message_missing_name(collector):
    """Test handling message with missing name."""
    raw_data = {
        "messages": [
            {
                "sender": {"displayName": "User"},
                "text": "message",
                "createTime": "2026-02-21T10:00:00Z",
                "reactionCounts": [],
                "attachments": [],
            }
        ],
        "spaces": [],
        "space_metadata": {},
        "space_members_by_space": {},
    }

    transformed = collector.transform(raw_data)

    # Should skip message with no name
    assert len(transformed) == 0


def test_reaction_missing_emoji(collector):
    """Test handling reaction with missing emoji."""
    rows = collector._transform_reactions(
        "msg1",
        [
            {"count": 1},  # Missing emoji
        ],
    )

    assert len(rows) == 0


def test_member_missing_name(collector):
    """Test handling member with missing name."""
    rows = collector._transform_members(
        "space1",
        [
            {"member": {"displayName": "User"}},  # Missing name field
        ],
    )

    assert len(rows) == 0
