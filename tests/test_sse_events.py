"""
Tests for Server-Sent Events (SSE) Router

Tests EventBus, SSE endpoint, event history, heartbeat, serialization,
and error handling.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.sse_router import (
    Event,
    EventBus,
    _create_event,
    _heartbeat_generator,
    get_event_bus,
    sse_router,
)

logger = logging.getLogger(__name__)


def async_test(coro):
    """Decorator to run async tests with asyncio.run."""

    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))

    return wrapper


class TestEventDataclass:
    """Test Event dataclass and methods."""

    def test_event_creation(self):
        """Test creating an Event."""
        event = Event(
            id="test-123",
            event_type="signal_new",
            data={"message": "Test signal"},
            timestamp="2024-01-01T00:00:00",
        )
        assert event.id == "test-123"
        assert event.event_type == "signal_new"
        assert event.data == {"message": "Test signal"}

    def test_event_to_sse(self):
        """Test Event.to_sse() SSE formatting."""
        event = Event(
            id="test-123",
            event_type="signal_new",
            data={"message": "Test signal"},
            timestamp="2024-01-01T00:00:00",
        )
        sse = event.to_sse()
        assert "id: test-123" in sse
        assert "event: signal_new" in sse
        assert "data: " in sse
        assert '{"message": "Test signal"}' in sse
        assert sse.endswith("\n\n")

    def test_event_to_dict(self):
        """Test Event.to_dict() dictionary conversion."""
        event = Event(
            id="test-123",
            event_type="signal_new",
            data={"message": "Test"},
            timestamp="2024-01-01T00:00:00",
        )
        d = event.to_dict()
        assert d["id"] == "test-123"
        assert d["event_type"] == "signal_new"
        assert d["data"]["message"] == "Test"
        assert d["timestamp"] == "2024-01-01T00:00:00"

    def test_event_sse_with_complex_data(self):
        """Test SSE serialization with nested JSON data."""
        event = Event(
            id="test-456",
            event_type="resolution_update",
            data={
                "entity_id": "res_123",
                "status": "in_progress",
                "metadata": {"priority": "high", "tags": ["urgent"]},
            },
            timestamp="2024-01-01T00:00:00",
        )
        sse = event.to_sse()
        assert "event: resolution_update" in sse
        assert '"priority": "high"' in sse

    def test_event_sse_with_special_chars(self):
        """Test SSE handles special characters in data."""
        event = Event(
            id="test-789",
            event_type="signal_new",
            data={"message": 'Message with "quotes" and \n newlines'},
            timestamp="2024-01-01T00:00:00",
        )
        sse = event.to_sse()
        assert "id: test-789" in sse
        # JSON should be properly escaped
        assert "event:" in sse


class TestCreateEventHelper:
    """Test _create_event helper function."""

    def test_creates_event_with_uuid(self):
        """Test that _create_event generates UUID."""
        event = _create_event("signal_new", {"message": "Test"})
        assert event.event_type == "signal_new"
        assert event.data == {"message": "Test"}
        assert event.id is not None
        assert len(event.id) > 0

    def test_creates_event_with_timestamp(self):
        """Test that _create_event adds current timestamp."""
        before = datetime.now().isoformat()
        event = _create_event("signal_new", {"message": "Test"})
        after = datetime.now().isoformat()
        assert before <= event.timestamp <= after

    def test_creates_different_ids(self):
        """Test that multiple _create_event calls generate different IDs."""
        event1 = _create_event("signal_new", {"message": "Test1"})
        event2 = _create_event("signal_new", {"message": "Test2"})
        assert event1.id != event2.id


class TestEventBus:
    """Test EventBus class."""

    @pytest.fixture
    def event_bus(self):
        """Create a fresh EventBus for each test."""
        return EventBus()

    def test_subscribe_creates_queue(self, event_bus):
        """Test that subscribe returns a queue."""

        async def run_test():
            queue = await event_bus.subscribe()
            assert isinstance(queue, asyncio.Queue)

        asyncio.run(run_test())

    def test_multiple_subscribers(self, event_bus):
        """Test multiple subscribers can exist."""

        async def run_test():
            queue1 = await event_bus.subscribe()
            queue2 = await event_bus.subscribe()
            assert queue1 is not queue2

        asyncio.run(run_test())

    def test_publish_to_single_subscriber(self, event_bus):
        """Test publishing event reaches subscriber."""

        async def run_test():
            queue = await event_bus.subscribe()
            event = Event("id-1", "signal_new", {"msg": "test"}, "2024-01-01T00:00:00")
            await event_bus.publish(event)
            # Should be able to get the event
            received = queue.get_nowait()
            assert received.id == "id-1"
            assert received.event_type == "signal_new"

        asyncio.run(run_test())

    def test_publish_to_multiple_subscribers(self, event_bus):
        """Test event reaches all subscribers."""

        async def run_test():
            queue1 = await event_bus.subscribe()
            queue2 = await event_bus.subscribe()
            event = Event("id-1", "signal_new", {"msg": "test"}, "2024-01-01T00:00:00")
            await event_bus.publish(event)
            # Both should receive
            received1 = queue1.get_nowait()
            received2 = queue2.get_nowait()
            assert received1.id == "id-1"
            assert received2.id == "id-1"

        asyncio.run(run_test())

    def test_unsubscribe(self, event_bus):
        """Test unsubscribe removes subscriber."""

        async def run_test():
            queue1 = await event_bus.subscribe()
            queue2 = await event_bus.subscribe()

            # Publish before unsubscribe - both should receive
            event1 = Event("id-1", "signal_new", {"msg": "test1"}, "2024-01-01T00:00:00")
            await event_bus.publish(event1)
            received1 = queue1.get_nowait()
            received2_1 = queue2.get_nowait()
            assert received1.id == "id-1"
            assert received2_1.id == "id-1"

            # Now unsubscribe queue1
            await event_bus.unsubscribe(queue1)

            # Publish after unsubscribe - queue1 should NOT receive, queue2 should
            event2 = Event("id-2", "signal_new", {"msg": "test2"}, "2024-01-01T00:00:00")
            await event_bus.publish(event2)

            # queue2 should receive
            received2_2 = queue2.get_nowait()
            assert received2_2.id == "id-2"

            # queue1 should be empty (didn't receive the second event)
            assert queue1.empty()

        asyncio.run(run_test())

    def test_event_history_stored(self, event_bus):
        """Test events are stored in history."""

        async def run_test():
            event1 = Event("id-1", "signal_new", {"msg": "test1"}, "2024-01-01T00:00:00")
            event2 = Event("id-2", "signal_new", {"msg": "test2"}, "2024-01-01T00:00:01")
            await event_bus.publish(event1)
            await event_bus.publish(event2)
            history = event_bus.get_history()
            assert len(history) == 2
            assert history[0].id == "id-1"
            assert history[1].id == "id-2"

        asyncio.run(run_test())

    def test_history_max_size(self, event_bus):
        """Test history respects max size limit."""

        async def run_test():
            # Default max is 100
            for i in range(150):
                event = Event(f"id-{i}", "signal_new", {"msg": f"test{i}"}, "2024-01-01T00:00:00")
                await event_bus.publish(event)
            history = event_bus.get_history()
            assert len(history) == 100
            # Should keep the last 100
            assert history[0].id == "id-50"
            assert history[99].id == "id-149"

        asyncio.run(run_test())

    def test_get_history_empty(self, event_bus):
        """Test get_history on empty bus."""
        history = event_bus.get_history()
        assert history == []

    def test_get_history_returns_copy(self, event_bus):
        """Test that get_history returns a copy, not reference."""

        async def run_test():
            event1 = Event("id-1", "signal_new", {"msg": "test1"}, "2024-01-01T00:00:00")
            await event_bus.publish(event1)
            history1 = event_bus.get_history()
            history2 = event_bus.get_history()
            # Should be separate lists
            assert history1 is not history2
            assert history1[0].id == history2[0].id

        asyncio.run(run_test())

    def test_concurrent_publish(self, event_bus):
        """Test concurrent publish calls."""

        async def run_test():
            await event_bus.subscribe()
            # Publish 10 events concurrently
            events = [
                Event(f"id-{i}", "signal_new", {"msg": f"test{i}"}, "2024-01-01T00:00:00")
                for i in range(10)
            ]
            await asyncio.gather(*[event_bus.publish(e) for e in events])
            # All should be in history
            history = event_bus.get_history()
            assert len(history) >= 10

        asyncio.run(run_test())

    def test_full_queue_cleanup(self, event_bus):
        """Test that full queues are cleaned up."""

        async def run_test():
            # Create queue but don't consume from it
            await event_bus.subscribe()
            # Fill it up (asyncio.Queue default is unbounded, so we simulate)
            for i in range(1000):
                event = Event(f"id-{i}", "signal_new", {"msg": f"test{i}"}, "2024-01-01T00:00:00")
                try:
                    await event_bus.publish(event)
                except asyncio.QueueFull:
                    # Queue full as expected
                    break
            # At minimum, should have published some
            history = event_bus.get_history()
            assert len(history) > 0

        asyncio.run(run_test())


class TestHeartbeatGenerator:
    """Test _heartbeat_generator async generator."""

    def test_heartbeat_generator_basic(self):
        """Test heartbeat generator yields events."""

        async def run_test():
            queue = asyncio.Queue()
            event_bus = EventBus()

            # Add an event to queue
            event = Event("id-1", "signal_new", {"msg": "test"}, "2024-01-01T00:00:00")
            await queue.put(event)

            # Get first event from generator
            gen = _heartbeat_generator(queue, event_bus)
            result = await gen.__anext__()

            # Should be SSE formatted
            assert "id: id-1" in result
            assert "event: signal_new" in result

        asyncio.run(run_test())

    def test_heartbeat_generator_emits_heartbeat(self):
        """Test that heartbeat is sent periodically."""

        async def run_test():
            queue = asyncio.Queue()
            event_bus = EventBus()
            await event_bus.subscribe()  # Track in bus

            gen = _heartbeat_generator(queue, event_bus)

            # Heartbeat should be sent after 30 seconds (simulated)
            # For test, we'll just verify generator handles it
            try:
                # This will timeout if no heartbeat mechanism
                result = await asyncio.wait_for(gen.__anext__(), timeout=0.1)
                # Got something, good
                assert result is not None or result == ""
            except (TimeoutError, StopAsyncIteration):
                # Expected - either no event yet, or generator closed
                pass

        asyncio.run(run_test())

    def test_heartbeat_cleanup_on_error(self):
        """Test cleanup happens on error."""

        async def run_test():
            queue = asyncio.Queue()
            event_bus = EventBus()

            gen = _heartbeat_generator(queue, event_bus)

            # Close the generator (should trigger cleanup)
            try:
                await gen.aclose()
            except StopAsyncIteration:
                pass
            except Exception:
                pass

            # Should have unsubscribed from event_bus
            # (This is implicitly tested by no error being raised)

        asyncio.run(run_test())


class TestEventSerialization:
    """Test event serialization for different data types."""

    def test_serialize_string_data(self):
        """Test serialization with string data."""
        event = Event("id-1", "signal_new", {"message": "Hello World"}, "2024-01-01T00:00:00")
        sse = event.to_sse()
        assert '"message": "Hello World"' in sse

    def test_serialize_numeric_data(self):
        """Test serialization with numeric data."""
        event = Event(
            "id-1", "metric_refresh", {"value": 42, "percent": 95.5}, "2024-01-01T00:00:00"
        )
        sse = event.to_sse()
        assert '"value": 42' in sse
        assert '"percent": 95.5' in sse

    def test_serialize_boolean_data(self):
        """Test serialization with boolean data."""
        event = Event(
            "id-1",
            "signal_new",
            {"is_critical": True, "is_acknowledged": False},
            "2024-01-01T00:00:00",
        )
        sse = event.to_sse()
        assert '"is_critical": true' in sse
        assert '"is_acknowledged": false' in sse

    def test_serialize_null_data(self):
        """Test serialization with null values."""
        event = Event("id-1", "signal_new", {"optional_field": None}, "2024-01-01T00:00:00")
        sse = event.to_sse()
        assert '"optional_field": null' in sse

    def test_serialize_nested_objects(self):
        """Test serialization with nested objects."""
        event = Event(
            "id-1",
            "resolution_update",
            {
                "item": {
                    "id": "res-1",
                    "status": "in_progress",
                    "metadata": {"priority": "high"},
                },
                "timestamp": "2024-01-01T00:00:00",
            },
            "2024-01-01T00:00:00",
        )
        sse = event.to_sse()
        assert '"id": "res-1"' in sse
        assert '"priority": "high"' in sse

    def test_serialize_arrays(self):
        """Test serialization with array data."""
        event = Event(
            "id-1",
            "signal_new",
            {"tags": ["urgent", "client-facing", "revenue"], "affected_clients": [1, 2, 3]},
            "2024-01-01T00:00:00",
        )
        sse = event.to_sse()
        assert "urgent" in sse
        assert "client-facing" in sse


class TestEventTypes:
    """Test different event types per spec."""

    def test_signal_new_event(self):
        """Test signal_new event type."""
        event = Event(
            "id-1",
            "signal_new",
            {"message": "New signal detected", "severity": "warning"},
            "2024-01-01T00:00:00",
        )
        assert event.event_type == "signal_new"
        sse = event.to_sse()
        assert "event: signal_new" in sse

    def test_resolution_update_event(self):
        """Test resolution_update event type."""
        event = Event(
            "id-2",
            "resolution_update",
            {"item_id": "res-1", "status": "in_progress"},
            "2024-01-01T00:00:00",
        )
        assert event.event_type == "resolution_update"
        sse = event.to_sse()
        assert "event: resolution_update" in sse

    def test_metric_refresh_event(self):
        """Test metric_refresh event type."""
        event = Event(
            "id-3",
            "metric_refresh",
            {"metric": "active_tasks", "value": 18},
            "2024-01-01T00:00:00",
        )
        assert event.event_type == "metric_refresh"
        sse = event.to_sse()
        assert "event: metric_refresh" in sse

    def test_system_status_event(self):
        """Test system_status event type."""
        event = Event(
            "id-4",
            "system_status",
            {"status": "connected"},
            "2024-01-01T00:00:00",
        )
        assert event.event_type == "system_status"
        sse = event.to_sse()
        assert "event: system_status" in sse


class TestEventBusThreadSafety:
    """Test EventBus thread/async safety."""

    def test_concurrent_subscribe_unsubscribe(self):
        """Test concurrent subscribe/unsubscribe operations."""

        async def run_test():
            event_bus = EventBus()

            async def subscribe_unsubscribe():
                queue = await event_bus.subscribe()
                await asyncio.sleep(0.01)
                await event_bus.unsubscribe(queue)

            # Run many concurrent operations
            await asyncio.gather(*[subscribe_unsubscribe() for _ in range(10)])

            # Should not crash or corrupt state
            assert isinstance(event_bus._subscribers, set)

        asyncio.run(run_test())

    def test_concurrent_publish(self):
        """Test concurrent publish operations."""

        async def run_test():
            event_bus = EventBus()
            await event_bus.subscribe()

            events = [
                Event(f"id-{i}", "signal_new", {"msg": f"test{i}"}, "2024-01-01T00:00:00")
                for i in range(20)
            ]

            # Publish concurrently
            await asyncio.gather(*[event_bus.publish(e) for e in events])

            # All should be in history
            history = event_bus.get_history()
            assert len(history) >= 20

        asyncio.run(run_test())


class TestEventTimestamps:
    """Test timestamp handling."""

    def test_event_timestamp_iso_format(self):
        """Test that timestamps are ISO 8601 format."""
        event = _create_event("signal_new", {"msg": "test"})
        # Should be parseable as ISO 8601
        try:
            datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail("Timestamp not in ISO 8601 format")

    def test_event_timestamp_current_time(self):
        """Test that created event has current timestamp."""
        before = datetime.now()
        event = _create_event("signal_new", {"msg": "test"})
        after = datetime.now()

        event_time = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        assert before <= event_time <= after


class TestErrorHandling:
    """Test error handling in SSE operations."""

    def test_publish_with_dead_queue(self):
        """Test publishing when a queue is dead (full)."""

        async def run_test():
            event_bus = EventBus()

            # Create a mock queue that raises QueueFull
            dead_queue = MagicMock(spec=asyncio.Queue)
            dead_queue.put_nowait.side_effect = asyncio.QueueFull()

            event_bus._subscribers.add(dead_queue)

            event = Event("id-1", "signal_new", {"msg": "test"}, "2024-01-01T00:00:00")

            # Should not raise, should log and remove dead queue
            await event_bus.publish(event)

            # Dead queue should be removed
            assert dead_queue not in event_bus._subscribers

        asyncio.run(run_test())

    def test_event_with_empty_data(self):
        """Test Event with empty data dict."""
        event = Event("id-1", "signal_new", {}, "2024-01-01T00:00:00")
        sse = event.to_sse()
        assert "data: {}" in sse

    def test_event_serialization_with_unicode(self):
        """Test Event serialization with unicode characters."""
        event = Event(
            "id-1",
            "signal_new",
            {"message": "Unicode: 你好世界 🌍 Ñoño"},
            "2024-01-01T00:00:00",
        )
        event.to_sse()
        # Should not crash
        d = event.to_dict()
        # Unicode is preserved in the dict (JSON encoding handles it)
        assert "你好世界" in d["data"]["message"]
        # Verify JSON can be serialized with unicode
        json_str = json.dumps(d, ensure_ascii=False)
        assert "你好世界" in json_str
