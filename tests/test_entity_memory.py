"""
Tests for EntityMemory — interaction tracking and timeline.

Brief 22 (SM), Task SM-2.1
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lib.intelligence.entity_memory import (
    EntityInteraction,
    EntityMemory,
    EntityMemoryState,
    classify_attention,
)


@pytest.fixture
def memory(tmp_path):
    db_path = tmp_path / "test_memory.db"
    return EntityMemory(db_path=db_path)


class TestClassifyAttention:
    def test_high(self):
        assert classify_attention(0) == "high"
        assert classify_attention(3) == "high"

    def test_normal(self):
        assert classify_attention(4) == "normal"
        assert classify_attention(14) == "normal"

    def test_low(self):
        assert classify_attention(15) == "low"
        assert classify_attention(30) == "low"

    def test_stale(self):
        assert classify_attention(31) == "stale"
        assert classify_attention(100) == "stale"


class TestRecordInteraction:
    def test_basic_record(self, memory):
        interaction = memory.record_interaction(
            entity_type="client",
            entity_id="client_a",
            interaction_type="review",
            summary="Weekly health review",
            details={"health_score": 82},
        )
        assert interaction.id is not None
        assert interaction.entity_type == "client"
        assert interaction.entity_id == "client_a"
        assert interaction.interaction_type == "review"
        assert interaction.summary == "Weekly health review"
        assert interaction.details == {"health_score": 82}

    def test_default_source(self, memory):
        interaction = memory.record_interaction(
            entity_type="client",
            entity_id="c1",
            interaction_type="action",
            summary="Cleared overdue tasks",
        )
        assert interaction.source == "system"

    def test_custom_source(self, memory):
        interaction = memory.record_interaction(
            entity_type="client",
            entity_id="c1",
            interaction_type="note",
            summary="Manual note",
            source="user",
        )
        assert interaction.source == "user"


class TestMemoryState:
    def test_fresh_entity(self, memory):
        state = memory.get_memory_state("client", "nonexistent")
        assert state.review_count == 0
        assert state.action_count == 0
        assert state.attention_level == "stale"

    def test_with_interactions(self, memory):
        memory.record_interaction("client", "c1", "review", "Review 1")
        memory.record_interaction("client", "c1", "review", "Review 2")
        memory.record_interaction("client", "c1", "action", "Action 1")
        memory.record_interaction("client", "c1", "escalation", "Escalated")

        state = memory.get_memory_state("client", "c1")
        assert state.review_count == 2
        assert state.action_count == 1
        assert state.escalation_count == 1
        assert state.attention_level == "high"  # just interacted
        assert state.days_since_last_interaction == 0

    def test_to_dict(self, memory):
        memory.record_interaction("client", "c1", "review", "Review")
        state = memory.get_memory_state("client", "c1")
        d = state.to_dict()
        assert d["entity_type"] == "client"
        assert d["review_count"] == 1
        assert "attention_level" in d


class TestTimeline:
    def test_timeline_order(self, memory):
        memory.record_interaction("client", "c1", "review", "First")
        memory.record_interaction("client", "c1", "action", "Second")
        memory.record_interaction("client", "c1", "note", "Third")

        timeline = memory.get_timeline("client", "c1")
        assert len(timeline) == 3
        # Most recent first
        assert timeline[0].summary == "Third"
        assert timeline[2].summary == "First"

    def test_timeline_limit(self, memory):
        for i in range(10):
            memory.record_interaction("client", "c1", "review", f"Review {i}")

        timeline = memory.get_timeline("client", "c1", limit=5)
        assert len(timeline) == 5

    def test_timeline_filter_by_type(self, memory):
        memory.record_interaction("client", "c1", "review", "Review")
        memory.record_interaction("client", "c1", "action", "Action")
        memory.record_interaction("client", "c1", "note", "Note")

        timeline = memory.get_timeline("client", "c1", interaction_types=["review", "action"])
        assert len(timeline) == 2
        types = {t.interaction_type for t in timeline}
        assert types == {"review", "action"}

    def test_timeline_empty(self, memory):
        timeline = memory.get_timeline("client", "nonexistent")
        assert timeline == []


class TestStaleEntities:
    def test_no_stale(self, memory):
        memory.record_interaction("client", "c1", "review", "Fresh")
        stale = memory.get_stale_entities("client", days_threshold=30)
        assert len(stale) == 0

    def test_finds_stale(self, memory):
        # Record and then manually backdate
        import sqlite3

        memory.record_interaction("client", "c1", "review", "Old review")
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        conn = sqlite3.connect(str(memory.db_path))
        conn.execute(
            "UPDATE entity_interactions SET created_at = ? WHERE entity_id = 'c1'",
            (old_date,),
        )
        conn.commit()
        conn.close()

        stale = memory.get_stale_entities("client", days_threshold=30)
        assert len(stale) == 1
        assert stale[0].entity_id == "c1"
        assert stale[0].attention_level == "stale"


class TestInteractionSummary:
    def test_summary_with_data(self, memory):
        memory.record_interaction("client", "c1", "review", "Review 1")
        memory.record_interaction("client", "c1", "action", "Action 1")
        memory.record_interaction("client", "c2", "review", "Review 2")

        summary = memory.get_interaction_summary(entity_type="client")
        assert summary["total_interactions"] == 3
        assert summary["unique_entities"] == 2
        assert summary["by_type"]["review"] == 2
        assert summary["by_type"]["action"] == 1

    def test_summary_empty(self, memory):
        summary = memory.get_interaction_summary()
        assert summary["total_interactions"] == 0
        assert summary["unique_entities"] == 0

    def test_summary_all_types(self, memory):
        memory.record_interaction("client", "c1", "review", "R")
        memory.record_interaction("project", "p1", "action", "A")

        summary = memory.get_interaction_summary()
        assert summary["total_interactions"] == 2
        assert summary["unique_entities"] == 2


class TestInteractionToDict:
    def test_to_dict(self, memory):
        interaction = memory.record_interaction(
            "client", "c1", "review", "Test", details={"key": "val"}
        )
        d = interaction.to_dict()
        assert d["entity_type"] == "client"
        assert d["interaction_type"] == "review"
        assert d["details"] == {"key": "val"}
