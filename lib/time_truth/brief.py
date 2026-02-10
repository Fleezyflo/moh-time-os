"""
Time Brief Generator - Generate the Time Truth portion of the daily brief.

This produces the time-focused section of the morning brief:
- Today's scheduled blocks
- Unscheduled tasks that need attention
- Meeting schedule
- Available time
"""

import logging
from datetime import date, datetime

from lib.state_store import get_store
from lib.time_truth.block_manager import BlockManager
from lib.time_truth.calendar_sync import CalendarSync
from lib.time_truth.scheduler import Scheduler

logger = logging.getLogger(__name__)


def generate_time_brief(target_date: str = None, format: str = "markdown") -> str:
    """
    Generate the Time Truth section of the daily brief.

    Args:
        target_date: Date to generate for (defaults to today)
        format: Output format ('markdown' or 'plain')

    Returns:
        Formatted brief string
    """
    if not target_date:
        target_date = date.today().isoformat()

    store = get_store()
    block_manager = BlockManager(store)
    calendar_sync = CalendarSync(store)
    Scheduler(store)

    # Ensure blocks exist
    calendar_sync.generate_available_blocks(target_date)

    # Get all blocks
    blocks = block_manager.get_all_blocks(target_date)

    # Categorize blocks
    scheduled_blocks = []
    available_blocks = []
    protected_blocks = []

    for block in blocks:
        if block.is_protected:
            protected_blocks.append(block)
        elif block.task_id:
            scheduled_blocks.append(block)
        else:
            available_blocks.append(block)

    # Get task details for scheduled blocks
    scheduled_with_tasks = []
    for block in scheduled_blocks:
        task = store.get("tasks", block.task_id)
        if task:
            scheduled_with_tasks.append({"block": block, "task": task})

    # Get events for the day (for protected blocks context)
    events = store.query(
        """
        SELECT * FROM events
        WHERE date(start_time) = ?
        ORDER BY start_time
    """,
        [target_date],
    )

    # Get unscheduled tasks due today or overdue
    unscheduled_urgent = store.query(
        """
        SELECT * FROM tasks
        WHERE status = 'pending'
        AND (scheduled_block_id IS NULL OR scheduled_block_id = '')
        AND due_date <= ?
        ORDER BY priority DESC
        LIMIT 10
    """,
        [target_date],
    )

    # Get untracked commitments (Tier 1)
    try:
        from lib.commitment_truth import CommitmentManager

        cm = CommitmentManager(store)
        untracked_commitments = cm.get_untracked_commitments(limit=5)
        commitments_due = cm.get_commitments_due(target_date, include_overdue=True)[:5]
    except Exception:
        untracked_commitments = []
        commitments_due = []

    # Get capacity summary (Tier 2)
    try:
        from lib.capacity_truth import CapacityCalculator

        calc = CapacityCalculator(store)
        capacity_summary = calc.get_capacity_summary(target_date)
    except Exception:
        capacity_summary = None

    # Get at-risk clients (Tier 3)
    try:
        from lib.client_truth import HealthCalculator

        hc = HealthCalculator(store)
        at_risk_clients = hc.get_at_risk_clients(threshold=50)[:5]
    except Exception:
        at_risk_clients = []

    # Calculate totals
    total_scheduled_min = sum(b.duration_min for b in scheduled_blocks)
    total_available_min = sum(b.duration_min for b in available_blocks)
    total_meeting_min = sum(b.duration_min for b in protected_blocks)

    # Build the brief
    if format == "markdown":
        return _format_markdown(
            target_date,
            scheduled_with_tasks,
            available_blocks,
            events,
            unscheduled_urgent,
            untracked_commitments,
            commitments_due,
            capacity_summary,
            at_risk_clients,
            total_scheduled_min,
            total_available_min,
            total_meeting_min,
        )
    return _format_plain(
        target_date,
        scheduled_with_tasks,
        available_blocks,
        events,
        unscheduled_urgent,
        untracked_commitments,
        commitments_due,
        capacity_summary,
        at_risk_clients,
        total_scheduled_min,
        total_available_min,
        total_meeting_min,
    )


def _format_markdown(
    target_date: str,
    scheduled: list[dict],
    available: list,
    events: list[dict],
    unscheduled: list[dict],
    untracked_commitments: list,
    commitments_due: list,
    capacity_summary: dict | None,
    at_risk_clients: list,
    scheduled_min: int,
    available_min: int,
    meeting_min: int,
) -> str:
    """Format brief as markdown (for WhatsApp, Telegram, etc.)"""
    lines = []

    # Header
    day_name = datetime.strptime(target_date, "%Y-%m-%d").strftime("%A")
    lines.append(f"*🎯 {day_name}'s Schedule*")
    lines.append("")

    # Time summary
    lines.append("📊 *Time Overview*")
    lines.append(f"• Meetings: {meeting_min // 60}h {meeting_min % 60}m")
    lines.append(f"• Scheduled work: {scheduled_min // 60}h {scheduled_min % 60}m")
    lines.append(f"• Available: {available_min // 60}h {available_min % 60}m")
    lines.append("")

    # Today's blocks (chronological)
    all_items = []

    # Add events
    for event in events:
        start = event.get("start_time", "")
        time_str = (
            start.split("T")[1][:5] if "T" in start else start[:5] if start else "??:??"
        )
        all_items.append(
            {
                "time": time_str,
                "type": "meeting",
                "title": event.get("title", "Meeting"),
                "lane": None,
            }
        )

    # Add scheduled tasks
    for item in scheduled:
        block = item["block"]
        task = item["task"]
        all_items.append(
            {
                "time": block.start_time,
                "type": "task",
                "title": task.get("title", "")[:40],
                "lane": block.lane,
            }
        )

    # Sort by time
    all_items.sort(key=lambda x: x["time"])

    if all_items:
        lines.append("*📅 Today's Blocks*")
        for item in all_items:
            icon = "📞" if item["type"] == "meeting" else "✏️"
            lane_tag = f" [{item['lane']}]" if item["lane"] else ""
            lines.append(f"• {item['time']} {icon} {item['title']}{lane_tag}")
        lines.append("")

    # Unscheduled urgent
    if unscheduled:
        lines.append(f"*⚠️ {len(unscheduled)} Unscheduled (Due Today)*")
        for task in unscheduled[:5]:
            lines.append(f"• {task.get('title', '')[:40]}")
        if len(unscheduled) > 5:
            lines.append(f"  _...and {len(unscheduled) - 5} more_")
        lines.append("")

    # Commitments (Tier 1)
    if commitments_due or untracked_commitments:
        lines.append("*🤝 Commitments*")

        if commitments_due:
            lines.append(f"_Due today ({len(commitments_due)}):_")
            for c in commitments_due[:3]:
                text = c.text[:40] if hasattr(c, "text") else str(c)[:40]
                lines.append(f"• {text}")

        if untracked_commitments:
            lines.append(f"_Untracked ({len(untracked_commitments)}):_")
            for c in untracked_commitments[:3]:
                text = c.text[:40] if hasattr(c, "text") else str(c)[:40]
                lines.append(f"• {text}")

        lines.append("")

    # Capacity (Tier 2)
    if capacity_summary:
        util = capacity_summary.get("overall_utilization_pct", 0)
        overloaded = capacity_summary.get("overloaded_lanes", [])
        high_util = capacity_summary.get("high_utilization_lanes", [])

        if overloaded or high_util or util > 70:
            lines.append("*📊 Capacity*")
            lines.append(f"• Overall: {util}% utilized")
            if overloaded:
                lines.append(f"• ⚠️ Overloaded: {', '.join(overloaded)}")
            if high_util:
                lines.append(f"• ⚡ High load: {', '.join(high_util)}")
            lines.append("")

    # At-risk clients (Tier 3)
    if at_risk_clients:
        lines.append(f"*🚨 {len(at_risk_clients)} At-Risk Clients*")
        for client in at_risk_clients[:3]:
            name = (
                client.client_name
                if hasattr(client, "client_name")
                else str(client)[:20]
            )
            score = client.health_score if hasattr(client, "health_score") else "?"
            lines.append(f"• {name}: {score}/100")
        if len(at_risk_clients) > 3:
            lines.append(f"  _...and {len(at_risk_clients) - 3} more_")
        lines.append("")

    # Available slots
    if available:
        lines.append(f"*✅ {len(available)} Available Slots*")
        for block in available[:3]:
            lines.append(f"• {block.start_time}-{block.end_time} ({block.lane})")
        if len(available) > 3:
            lines.append(f"  _...and {len(available) - 3} more_")

    return "\n".join(lines)


def _format_plain(
    target_date: str,
    scheduled: list[dict],
    available: list,
    events: list[dict],
    unscheduled: list[dict],
    untracked_commitments: list,
    commitments_due: list,
    capacity_summary: dict | None,
    at_risk_clients: list,
    scheduled_min: int,
    available_min: int,
    meeting_min: int,
) -> str:
    """Format brief as plain text."""
    lines = []

    day_name = datetime.strptime(target_date, "%Y-%m-%d").strftime("%A")
    lines.append(f"{day_name}'s Schedule")
    lines.append("=" * 40)
    lines.append("")

    lines.append("TIME OVERVIEW")
    lines.append(f"  Meetings: {meeting_min} min")
    lines.append(f"  Scheduled: {scheduled_min} min")
    lines.append(f"  Available: {available_min} min")
    lines.append("")

    if events or scheduled:
        lines.append("TODAY'S BLOCKS")
        for event in events:
            start = (
                event.get("start_time", "")[:5] if event.get("start_time") else "??:??"
            )
            lines.append(f"  {start} [MEETING] {event.get('title', '')}")
        for item in scheduled:
            block = item["block"]
            task = item["task"]
            lines.append(
                f"  {block.start_time} [{block.lane}] {task.get('title', '')[:40]}"
            )
        lines.append("")

    if unscheduled:
        lines.append(f"UNSCHEDULED ({len(unscheduled)} due today)")
        for task in unscheduled[:5]:
            lines.append(f"  - {task.get('title', '')[:40]}")
        lines.append("")

    return "\n".join(lines)


def get_time_truth_status(target_date: str = None) -> dict:
    """
    Get a structured status of Time Truth for the date.

    Returns dict suitable for API response.
    """
    if not target_date:
        target_date = date.today().isoformat()

    store = get_store()
    scheduler = Scheduler(store)

    summary = scheduler.get_scheduling_summary(target_date)
    validation = scheduler.validate_schedule(target_date)

    return {
        "date": target_date,
        "tier": 0,
        "tier_name": "Time Truth",
        "stable": validation.valid,
        "summary": summary,
        "validation": {"valid": validation.valid, "issues": validation.issues},
    }


# Test
if __name__ == "__main__":
    today = date.today().isoformat()

    logger.info(f"Time Brief for {today}")
    logger.info("=" * 50)
    # (newline for readability)

    brief = generate_time_brief(today, format="markdown")
    logger.info(brief)
    # (newline for readability)
    logger.info("=" * 50)
    logger.info("Status:")
    status = get_time_truth_status(today)
    logger.info(f"  Stable: {status['stable']}")
    logger.info(f"  Issues: {len(status['validation']['issues'])}")
