"""
Heartbeat Pulse — Surface what matters during heartbeat checks.

Aggregates signals from Financial Pulse, Tasks, Calendar, and Chat
to produce a prioritized list of items that need attention.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from .gogcli import run_gog


@dataclass
class Alert:
    """A single alert to surface."""

    severity: str  # critical, warning, info
    category: str  # financial, tasks, calendar, chat
    title: str
    detail: str
    source_ref: str | None = None
    action_hint: str | None = None


@dataclass
class HeartbeatPulseResult:
    """Result of a heartbeat pulse check."""

    alerts: list[Alert] = field(default_factory=list)
    summary: str = ""
    checked_at: str = ""

    def has_alerts(self) -> bool:
        return len(self.alerts) > 0

    def critical_count(self) -> int:
        return sum(1 for a in self.alerts if a.severity == "critical")

    def warning_count(self) -> int:
        return sum(1 for a in self.alerts if a.severity == "warning")


def _check_financial_pulse(account: str, config_dir: str) -> list[Alert]:
    """Check Financial Pulse for AR alerts."""
    alerts = []

    # Try to import and run financial pulse
    try:
        from .financial_pulse import run_financial_pulse

        result = run_financial_pulse(config_dir)

        if result.get("ok"):
            data = result.get("data", {})
            summary = data.get("summary", {})

            critical_count = summary.get("criticalCount", 0)
            critical_amount = summary.get("criticalAmount", 0)
            warning_count = summary.get("warningCount", 0)

            if critical_count > 0:
                alerts.append(
                    Alert(
                        severity="critical",
                        category="financial",
                        title=f"AR Critical: {critical_count} invoices ({critical_amount:,.0f} AED)",
                        detail=f"{critical_count} invoices are 60+ days overdue or large amounts",
                        action_hint="Review AR aging report",
                    )
                )

            if warning_count > 3:
                alerts.append(
                    Alert(
                        severity="warning",
                        category="financial",
                        title=f"AR Warning: {warning_count} invoices in 30-60 day range",
                        detail="Multiple invoices approaching critical aging",
                        action_hint="Follow up on outstanding payments",
                    )
                )
    except Exception:
        logging.getLogger(__name__).debug("Financial pulse unavailable", exc_info=True)

    return alerts


def _check_tasks_overdue(account: str) -> list[Alert]:
    """Check Google Tasks for overdue items."""
    alerts = []

    try:
        # Get task lists
        res = run_gog(["tasks", "lists", "list"], account=account, timeout=60)
        if not res.ok:
            return alerts

        lists = res.data.get("tasklists") or res.data.get("lists") or []

        now = datetime.now(UTC)
        overdue_tasks = []

        for tl in lists[:10]:  # Limit to first 10 lists
            tlid = tl.get("id") or tl.get("tasklistId")
            if not tlid:
                continue

            tasks_res = run_gog(["tasks", "list", tlid, "--max=50"], account=account, timeout=60)
            if not tasks_res.ok:
                continue

            tasks = tasks_res.data.get("tasks") or tasks_res.data.get("items") or []
            for t in tasks:
                status = (t.get("status") or "").lower()
                if status == "completed":
                    continue

                due = t.get("due")
                if due:
                    try:
                        if due.endswith("Z"):
                            due = due[:-1] + "+00:00"
                        due_dt = datetime.fromisoformat(due)
                        if due_dt < now:
                            days_overdue = (now - due_dt).days
                            overdue_tasks.append(
                                {
                                    "title": t.get("title", "Untitled"),
                                    "days": days_overdue,
                                    "list": tl.get("title", "Unknown"),
                                }
                            )
                    except Exception:
                        logging.getLogger(__name__).debug(
                            "Bad task due date: %s", due, exc_info=True
                        )

        if len(overdue_tasks) > 10:
            alerts.append(
                Alert(
                    severity="critical",
                    category="tasks",
                    title=f"Tasks: {len(overdue_tasks)} overdue items",
                    detail=f"Oldest: {max(t['days'] for t in overdue_tasks)} days overdue",
                    action_hint="Review task backlog",
                )
            )
        elif len(overdue_tasks) > 0:
            alerts.append(
                Alert(
                    severity="warning",
                    category="tasks",
                    title=f"Tasks: {len(overdue_tasks)} overdue",
                    detail=", ".join(t["title"][:30] for t in overdue_tasks[:3]),
                    action_hint="Check due dates",
                )
            )
    except Exception:
        logging.getLogger(__name__).debug("Tasks overdue check failed", exc_info=True)

    return alerts


def _check_chat_urgent(account: str, hours: int = 4) -> list[Alert]:
    """Check Google Chat for recent urgent/sensitive messages."""
    alerts = []

    try:
        import re
        from datetime import datetime, timedelta

        URGENT_RE = re.compile(
            r"\b(urgent|asap|today|eod|deadline|pls|please\s+help|need\s+now|required)\b",
            re.I,
        )
        SENSITIVITY_RE = re.compile(
            r"\b(confidential|private|sensitive|do not share|internal only|salary|termination|legal|hr issue|complaint|fired)\b",
            re.I,
        )
        MENTION_MOLHAM_RE = re.compile(r"@(molham|moh\b)", re.I)

        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        # Get spaces
        spaces_res = run_gog(["chat", "spaces", "list", "--max=20"], account=account, timeout=60)
        if not spaces_res.ok:
            return alerts

        spaces = spaces_res.data.get("spaces") or []

        urgent_msgs = []
        sensitive_msgs = []
        mentions = []

        for sp in spaces[:15]:  # Limit spaces checked
            space_name = sp.get("resource") or sp.get("name")
            space_display = sp.get("name") or sp.get("displayName") or space_name
            if not space_name:
                continue

            # Get recent messages
            msg_res = run_gog(
                [
                    "chat",
                    "messages",
                    "list",
                    space_name,
                    "--max=20",
                    "--order=createTime desc",
                ],
                account=account,
                timeout=60,
            )

            if not msg_res.ok:
                continue

            messages = msg_res.data.get("messages") or []

            for m in messages:
                create_time = m.get("createTime") or ""
                if create_time:
                    try:
                        if create_time.endswith("Z"):
                            create_time = create_time[:-1] + "+00:00"
                        msg_dt = datetime.fromisoformat(create_time)
                        if msg_dt < cutoff:
                            continue  # Skip old messages
                    except Exception:
                        logging.getLogger(__name__).debug(
                            "Bad message createTime: %s", create_time, exc_info=True
                        )
                        continue

                text = m.get("text") or m.get("formattedText") or ""
                if not text:
                    continue

                if URGENT_RE.search(text):
                    urgent_msgs.append({"space": space_display, "text": text[:100]})

                if SENSITIVITY_RE.search(text):
                    sensitive_msgs.append({"space": space_display, "text": text[:50]})

                if MENTION_MOLHAM_RE.search(text):
                    mentions.append({"space": space_display, "text": text[:100]})

        # Generate alerts
        if sensitive_msgs:
            alerts.append(
                Alert(
                    severity="warning",
                    category="chat",
                    title=f"Chat: {len(sensitive_msgs)} sensitive message(s) in last {hours}h",
                    detail=f"Spaces: {', '.join({m['space'] for m in sensitive_msgs[:3]})}",
                    action_hint="Review sensitive communications",
                )
            )

        if len(urgent_msgs) > 3:
            alerts.append(
                Alert(
                    severity="warning",
                    category="chat",
                    title=f"Chat: {len(urgent_msgs)} urgent messages in last {hours}h",
                    detail="High urgency activity across spaces",
                    action_hint="Check Chat for time-sensitive items",
                )
            )

        if mentions:
            alerts.append(
                Alert(
                    severity="info",
                    category="chat",
                    title=f"Chat: {len(mentions)} mention(s) of you",
                    detail=f"In: {', '.join({m['space'] for m in mentions[:3]})}",
                    action_hint="Review mentions",
                )
            )

    except Exception:
        logging.getLogger(__name__).debug("Chat urgent check failed", exc_info=True)

    return alerts


def _check_calendar_workload(account: str) -> list[Alert]:
    """Check calendar for overloaded days in next 3 days."""
    alerts = []

    try:
        now = datetime.now(UTC)
        end = now + timedelta(days=3)

        res = run_gog(
            [
                "calendar",
                "events",
                "primary",
                f"--from={now.isoformat()}",
                f"--to={end.isoformat()}",
                "--max=100",
            ],
            account=account,
            timeout=60,
        )

        if not res.ok:
            return alerts

        events = res.data.get("events") or []
        hours_by_day: dict[str, float] = {}

        for e in events:
            start = (e.get("start") or {}).get("dateTime")
            end_time = (e.get("end") or {}).get("dateTime")

            if start and end_time and "T" in start:
                try:
                    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    en = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    hours = (en - s).total_seconds() / 3600
                    day = start[:10]
                    hours_by_day[day] = hours_by_day.get(day, 0) + hours
                except Exception:
                    logging.getLogger(__name__).debug(
                        "Bad calendar event time: %s", start, exc_info=True
                    )

        overloaded = [(d, h) for d, h in hours_by_day.items() if h > 7]

        if overloaded:
            worst = max(overloaded, key=lambda x: x[1])
            alerts.append(
                Alert(
                    severity="warning",
                    category="calendar",
                    title=f"Calendar: {worst[0]} has {worst[1]:.1f}h blocked",
                    detail=f"{len(overloaded)} day(s) with 7+ hours of meetings in next 3 days",
                    action_hint="Consider rescheduling or blocking focus time",
                )
            )
    except Exception:
        logging.getLogger(__name__).debug("Calendar workload check failed", exc_info=True)

    return alerts


def run_heartbeat_pulse(
    account: str,
    config_dir: str = "moh_time_os/config",
    include_financial: bool = True,
    include_tasks: bool = True,
    include_calendar: bool = True,
    include_chat: bool = True,
    chat_hours: int = 4,
) -> HeartbeatPulseResult:
    """
    Run a heartbeat pulse check across all configured surfaces.

    Returns a HeartbeatPulseResult with prioritized alerts.
    """
    result = HeartbeatPulseResult(
        checked_at=datetime.now(UTC).isoformat(),
    )

    # Collect alerts from each surface
    if include_financial:
        result.alerts.extend(_check_financial_pulse(account, config_dir))

    if include_tasks:
        result.alerts.extend(_check_tasks_overdue(account))

    if include_calendar:
        result.alerts.extend(_check_calendar_workload(account))

    if include_chat:
        result.alerts.extend(_check_chat_urgent(account, hours=chat_hours))

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    result.alerts.sort(key=lambda a: severity_order.get(a.severity, 99))

    # Generate summary
    if not result.alerts:
        result.summary = "All clear — no alerts"
    else:
        parts = []
        crit = result.critical_count()
        warn = result.warning_count()
        info = sum(1 for a in result.alerts if a.severity == "info")
        if crit:
            parts.append(f"🔴 {crit} critical")
        if warn:
            parts.append(f"🟡 {warn} warning")
        if info and not crit and not warn:
            parts.append(f"ℹ️ {info} info")
        result.summary = " • ".join(parts) if parts else "Items to review"

    return result


def format_heartbeat_alerts(result: HeartbeatPulseResult) -> str:
    """Format alerts for human-readable output."""
    if not result.has_alerts():
        return ""

    lines = [f"**Pulse Check** ({result.summary})\n"]

    for alert in result.alerts:
        emoji = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}.get(alert.severity, "•")
        lines.append(f"{emoji} **{alert.title}**")
        if alert.detail:
            lines.append(f"   {alert.detail}")
        if alert.action_hint:
            lines.append(f"   → {alert.action_hint}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    result = run_heartbeat_pulse(
        account="molham@hrmny.co",
        include_financial=False,  # Skip if not configured
        include_chat=True,
        chat_hours=24,  # Check last 24h for test
    )
    print(f"Summary: {result.summary}")
    print()
    print(format_heartbeat_alerts(result) or "No alerts")
