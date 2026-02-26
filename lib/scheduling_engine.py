#!/usr/bin/env python3
"""
MOH Time OS — Scheduling & Capacity Engine

Per MOH_TIME_OS_SCHEDULING.md spec:
- AEC (Available Execution Capacity) calculation
- Block proposal algorithm
- Fragmentation constraints
- Infeasibility handling
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from datetime import UTC

from .config_store import get, get_all_lanes, get_lane

logger = logging.getLogger(__name__)


# Default scheduling parameters
DEFAULT_SEW = {
    "start": time(10, 0),  # 10:00
    "end": time(20, 30),  # 20:30
    "timezone": "Asia/Dubai",
}

DEFAULT_BUFFERS = {
    "before_meeting": 10,
    "after_meeting": 10,
}

DEFAULT_FRAGMENTATION = {
    "min_block_minutes": 30,
    "target_deep_work_minutes": 90,
    "max_blocks_per_day": 4,
    "max_context_switches": 6,
}


@dataclass
class TimeSlot:
    """A time slot in the schedule."""

    start: datetime
    end: datetime
    duration_minutes: int = 0

    def __post_init__(self):
        if not self.duration_minutes:
            self.duration_minutes = int((self.end - self.start).total_seconds() / 60)

    def overlaps(self, other: "TimeSlot") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class CalendarEvent:
    """A calendar event."""

    id: str
    summary: str
    start: datetime
    end: datetime
    is_system_owned: bool = False
    mohos_dedupe_key: str = None

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() / 60)


@dataclass
class BlockProposal:
    """A proposed execution block."""

    item_id: str
    item_title: str
    lane: str
    start: datetime
    end: datetime
    duration_minutes: int
    confidence: float
    reason: str
    alternatives: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "item_title": self.item_title,
            "lane": self.lane,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_minutes": self.duration_minutes,
            "confidence": self.confidence,
            "reason": self.reason,
            "alternatives": self.alternatives,
        }


def get_sew_for_date(target_date: date) -> tuple[datetime, datetime]:
    """Get Schedulable Execution Window for a date."""
    sew = get("scheduling.sew", DEFAULT_SEW)

    # Parse start/end times
    if isinstance(sew.get("start"), str):
        start_time = datetime.strptime(sew["start"], "%H:%M").time()
    else:
        start_time = sew.get("start", time(10, 0))

    if isinstance(sew.get("end"), str):
        end_time = datetime.strptime(sew["end"], "%H:%M").time()
    else:
        end_time = sew.get("end", time(20, 30))

    # Combine with date
    start = datetime.combine(target_date, start_time, tzinfo=UTC)
    end = datetime.combine(target_date, end_time, tzinfo=UTC)

    return start, end


def calculate_aec(
    target_date: date,
    events: list[CalendarEvent],
) -> dict:
    """
    Calculate Available Execution Capacity for a date.

    AEC = SEW - meetings - buffers - protected blocks
    """
    sew_start, sew_end = get_sew_for_date(target_date)
    sew_minutes = int((sew_end - sew_start).total_seconds() / 60)

    # Filter events for this date
    day_events = []
    for event in events:
        if event.start.date() == target_date:
            day_events.append(event)

    # Calculate meeting time + buffers
    meeting_minutes = 0
    buffer_before = get("scheduling.buffers.before_meeting", 10)
    buffer_after = get("scheduling.buffers.after_meeting", 10)

    for event in day_events:
        if not event.is_system_owned:  # Non-system events are meetings
            meeting_minutes += event.duration_minutes
            meeting_minutes += buffer_before + buffer_after

    # Calculate protected block time (system-owned blocks already scheduled)
    protected_minutes = 0
    for event in day_events:
        if event.is_system_owned:
            protected_minutes += event.duration_minutes

    # Calculate AEC
    aec_minutes = sew_minutes - meeting_minutes - protected_minutes
    aec_minutes = max(0, aec_minutes)

    return {
        "date": target_date.isoformat(),
        "sew_minutes": sew_minutes,
        "meeting_minutes": meeting_minutes,
        "protected_minutes": protected_minutes,
        "aec_minutes": aec_minutes,
        "events_count": len(day_events),
        "is_weekend": target_date.weekday() >= 5,
    }


def find_available_slots(
    target_date: date,
    events: list[CalendarEvent],
    min_duration: int = 30,
) -> list[TimeSlot]:
    """Find available time slots in a day."""
    sew_start, sew_end = get_sew_for_date(target_date)

    # Sort events by start time
    day_events = [e for e in events if e.start.date() == target_date]
    day_events.sort(key=lambda e: e.start)

    # Get buffers
    buffer_before = get("scheduling.buffers.before_meeting", 10)
    buffer_after = get("scheduling.buffers.after_meeting", 10)

    # Find gaps
    slots = []
    current = sew_start

    for event in day_events:
        # Add buffer before event
        event_start_with_buffer = event.start - timedelta(minutes=buffer_before)

        if current < event_start_with_buffer:
            # Found a gap
            gap_minutes = int((event_start_with_buffer - current).total_seconds() / 60)
            if gap_minutes >= min_duration:
                slots.append(TimeSlot(current, event_start_with_buffer))

        # Move current past event + buffer
        current = event.end + timedelta(minutes=buffer_after)

    # Check remaining time until SEW end
    if current < sew_end:
        gap_minutes = int((sew_end - current).total_seconds() / 60)
        if gap_minutes >= min_duration:
            slots.append(TimeSlot(current, sew_end))

    return slots


def allocate_lane_budgets(aec_minutes: int, lanes: list[str] = None) -> dict[str, int]:
    """Allocate AEC minutes to lanes based on budgets."""
    all_lanes = get_all_lanes()

    if lanes:
        all_lanes = {k: v for k, v in all_lanes.items() if k in lanes}

    # Calculate total daily budget
    total_budget = sum(
        lane.get("capacity_budget", {}).get("daily_minutes", 60) for lane in all_lanes.values()
    )

    # Proportionally allocate AEC
    allocation = {}
    for lane_id, lane in all_lanes.items():
        budget = lane.get("capacity_budget", {}).get("daily_minutes", 60)
        share = (budget / total_budget) if total_budget > 0 else 0
        allocation[lane_id] = int(aec_minutes * share)

    return allocation


def propose_blocks(
    items: list[dict],
    events: list[CalendarEvent],
    horizon_days: int = 7,
) -> dict:
    """
    Propose execution blocks for items.

    Returns proposal bundle with blocks and infeasibility report.
    """
    proposals = []
    infeasible = []

    # Calculate AEC for each day in horizon
    today = date.today()
    aec_by_date = {}
    slots_by_date = {}

    for i in range(horizon_days):
        target_date = today + timedelta(days=i)
        aec = calculate_aec(target_date, events)
        aec_by_date[target_date] = aec
        slots_by_date[target_date] = find_available_slots(target_date, events)

    # Sort items by priority (assuming they have a score)
    items_sorted = sorted(items, key=lambda x: x.get("priority_score", 0), reverse=True)

    # Allocate blocks
    max_blocks_per_day = get("scheduling.fragmentation.max_blocks_per_day", 4)
    blocks_per_day = {today + timedelta(days=i): 0 for i in range(horizon_days)}

    for item in items_sorted:
        item_id = item.get("id")
        title = item.get("what") or item.get("title", "Untitled")
        lane = item.get("lane", "ops")

        # Get preferred block length from lane config
        lane_config = get_lane(lane)
        block_templates = (
            lane_config.get("block_templates", [30, 60, 90]) if lane_config else [30, 60, 90]
        )

        # Try to find a slot
        scheduled = False

        for target_date in sorted(slots_by_date.keys()):
            if blocks_per_day[target_date] >= max_blocks_per_day:
                continue

            slots = slots_by_date[target_date]

            for slot in slots:
                # Find best block length that fits
                for block_len in sorted(block_templates, reverse=True):
                    if slot.duration_minutes >= block_len:
                        # Create proposal
                        proposal = BlockProposal(
                            item_id=item_id,
                            item_title=title,
                            lane=lane,
                            start=slot.start,
                            end=slot.start + timedelta(minutes=block_len),
                            duration_minutes=block_len,
                            confidence=0.8,
                            reason=f"Scheduled in {lane} lane slot",
                        )
                        proposals.append(proposal)

                        # Update slot (reduce available time)
                        slot.start = proposal.end
                        slot.duration_minutes = int((slot.end - slot.start).total_seconds() / 60)

                        blocks_per_day[target_date] += 1
                        scheduled = True
                        break

                if scheduled:
                    break

            if scheduled:
                break

        if not scheduled:
            # Item is infeasible within horizon
            infeasible.append(
                {
                    "item_id": item_id,
                    "title": title,
                    "reason": "No available slot within horizon",
                    "options": ["defer", "delegate", "reduce_scope", "drop"],
                }
            )

    return {
        "proposals": [p.to_dict() for p in proposals],
        "infeasible": infeasible,
        "aec_summary": {d.isoformat(): aec for d, aec in aec_by_date.items()},
        "horizon_days": horizon_days,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def check_infeasibility(item: dict, aec_minutes: int) -> dict | None:
    """
    Check if an item is infeasible to schedule.

    Returns infeasibility report if infeasible, None otherwise.
    """
    effort_min = item.get("effort_min", 30)

    if effort_min > aec_minutes:
        return {
            "item_id": item.get("id"),
            "reason": f"Effort ({effort_min} min) exceeds available capacity ({aec_minutes} min)",
            "options": [
                {"action": "defer", "desc": "Move to later date"},
                {"action": "delegate", "desc": "Assign to someone else"},
                {"action": "reduce_scope", "desc": "Break into smaller tasks"},
                {"action": "drop", "desc": "Consciously abandon"},
                {"action": "renegotiate", "desc": "Extend deadline"},
            ],
        }

    return None


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage: scheduling_engine.py <command> [args]")
        logger.info("Commands: aec [date], slots [date], propose <items_json>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "aec":
        target = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
        aec = calculate_aec(target, [])
        logger.info(json.dumps(aec, indent=2))
    elif cmd == "slots":
        target = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
        slots = find_available_slots(target, [])
        for slot in slots:
            logger.info(
                f"{slot.start.strftime('%H:%M')} - {slot.end.strftime('%H:%M')} ({slot.duration_minutes} min)"
            )
    elif cmd == "propose" and len(sys.argv) >= 3:
        try:
            items = json.loads(sys.argv[2])
        except json.JSONDecodeError as e:
            logger.error(f"Error: Invalid JSON in argument: {e}")
            sys.exit(1)
        result = propose_blocks(items, [])
        logger.info(json.dumps(result, indent=2))
    else:
        logger.info(f"Unknown command: {cmd}")
