"""
Server-Sent Events (SSE) Router — Real-Time Event Streaming

This router provides real-time event streaming via Server-Sent Events (SSE).
Events include:
  - signal_new: New signal detected
  - resolution_update: Resolution queue item changed
  - metric_refresh: Dashboard metrics updated
  - system_status: Heartbeat/connection status

AUTHENTICATION: All endpoints require a valid Bearer token.
Set INTEL_API_TOKEN environment variable to enable auth.
Without this env var, auth is disabled (development mode).

Usage in server.py:
    from api.sse_router import sse_router
    app.include_router(sse_router, prefix="/api/v2")
"""

import asyncio
import json
import logging
import sqlite3
from collections.abc import AsyncGenerator
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.auth import require_auth
from api.response_models import DetailResponse

logger = logging.getLogger(__name__)

# Router - ALL endpoints require authentication
sse_router = APIRouter(
    tags=["Events"],
    dependencies=[Depends(require_auth)],  # Auth required for all endpoints
)


@dataclass
class Event:
    """Represents a single event in the system."""

    id: str
    event_type: str
    data: dict
    timestamp: str

    def to_sse(self) -> str:
        """Format event as SSE message."""
        lines = [
            f"id: {self.id}",
            f"event: {self.event_type}",
            f"data: {json.dumps(self.data)}",
        ]
        return "\n".join(lines) + "\n\n"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON responses."""
        return asdict(self)


class EventBus:
    """Manages event broadcasting to multiple subscribers."""

    def __init__(self):
        """Initialize event bus with empty subscribers."""
        self._subscribers: set[asyncio.Queue] = set()
        self._event_history: list[Event] = []
        self._max_history = 100
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to events, returns a queue to receive them."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from events."""
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        async with self._lock:
            # Store in history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)

            # Publish to all subscribers
            dead_queues = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Event queue full, dropping subscriber")
                    dead_queues.append(queue)

            # Clean up dead subscribers
            for queue in dead_queues:
                self._subscribers.discard(queue)

    def get_history(self) -> list[Event]:
        """Get event history."""
        return self._event_history.copy()


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get or create event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def _create_event(event_type: str, data: dict) -> Event:
    """Create an event with timestamp and ID."""
    return Event(
        id=str(uuid4()),
        event_type=event_type,
        data=data,
        timestamp=datetime.now().isoformat(),
    )


async def _heartbeat_generator(
    queue: asyncio.Queue, event_bus: EventBus
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream with heartbeat.

    Emits events from the queue and sends a heartbeat every 30 seconds
    to keep the connection alive.
    """
    heartbeat_task = None
    try:

        async def send_heartbeat():
            """Send heartbeat events every 30 seconds."""
            while True:
                try:
                    await asyncio.sleep(30)
                    event = _create_event("system_status", {"status": "connected"})
                    await queue.put(event)
                except asyncio.CancelledError:
                    break
                except (sqlite3.Error, ValueError) as e:
                    logger.error(f"Heartbeat error: {e}")

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(send_heartbeat())

        # Stream events from queue
        while True:
            try:
                # Wait for event with timeout to handle cleanup
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
                yield event.to_sse()
            except TimeoutError:
                # Connection idle, check if we should close
                logger.debug("SSE stream idle timeout")
                break
            except asyncio.CancelledError:
                break
            except (sqlite3.Error, ValueError) as e:
                logger.error(f"SSE stream error: {e}")
                break
    finally:
        # Clean up
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        await event_bus.unsubscribe(queue)


@sse_router.get("/events/stream")
async def stream_events() -> StreamingResponse:
    """
    Server-Sent Events endpoint for real-time data push.

    Returns SSE stream with events:
    - signal_new: New signal detected
    - resolution_update: Resolution queue item changed
    - metric_refresh: Dashboard metrics updated
    - system_status: Heartbeat/connection status

    Keep-alive heartbeat sent every 30 seconds.
    """
    event_bus = get_event_bus()
    try:
        queue = await event_bus.subscribe()
        return StreamingResponse(
            _heartbeat_generator(queue, event_bus),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"SSE stream setup failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to establish SSE stream") from e


@sse_router.get("/events/history", response_model=DetailResponse)
def get_event_history(limit: int = Query(100, description="Maximum events to return")):
    """
    Get recent event history.

    Returns the last N events (default 100).
    Useful for initial state sync or when SSE unavailable.
    """
    try:
        if limit < 1 or limit > 500:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

        event_bus = get_event_bus()
        history = event_bus.get_history()

        # Return last N events
        events = history[-limit:] if limit else history
        return {
            "status": "ok",
            "data": [event.to_dict() for event in events],
            "count": len(events),
            "computed_at": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"get_event_history failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@sse_router.post("/events/publish", response_model=DetailResponse)
async def publish_event(
    event_type: str = Query(..., description="Type of event"),
    message: str = Query(..., description="Event message"),
    severity: str | None = Query(None, description="Optional: severity level"),
):
    """
    Publish a test event to the stream.

    For testing/demo purposes. In production, events are published
    by the system's internal event producers.
    """
    try:
        event = _create_event(
            event_type,
            {
                "message": message,
                "severity": severity or "info",
            },
        )
        event_bus = get_event_bus()
        await event_bus.publish(event)
        return {
            "status": "ok",
            "event_id": event.id,
            "timestamp": event.timestamp,
        }
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"publish_event failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
