import json
import logging
import os
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from lib import paths

from .chat_discovery import run_chat_discovery
from .gogcli import run_gog
from .store import connect, insert_proposal, insert_raw_event, upsert_config
from .tasks_discovery import run_tasks_discovery


def _default_out_dir() -> str:
    return str(paths.out_dir())


@dataclass
class DiscoveryConfig:
    account: str
    days: int = 90
    out_dir: str = field(default_factory=_default_out_dir)
    include_gmail: bool = True
    include_calendar: bool = True
    include_tasks: bool = True
    include_chat: bool = True
    chat_max_spaces: int = 200
    chat_pages_per_space: int = 10


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _safe_email_domain(addr: str) -> str:
    addr = addr.strip().lower()
    if "@" not in addr:
        return ""
    return addr.split("@", 1)[1]


def run_discovery(db_path: str, cfg: DiscoveryConfig) -> dict[str, Any]:
    os.makedirs(cfg.out_dir, exist_ok=True)
    con = connect(db_path)

    upsert_config(
        con,
        "discovery.lastRun",
        {
            "account": cfg.account,
            "days": cfg.days,
            "ts": datetime.now(UTC).isoformat(),
            "include": {
                "gmail": cfg.include_gmail,
                "calendar": cfg.include_calendar,
                "tasks": cfg.include_tasks,
                "chat": cfg.include_chat,
            },
            "chat": {
                "maxSpaces": cfg.chat_max_spaces,
                "pagesPerSpace": cfg.chat_pages_per_space,
            },
        },
    )

    start = datetime.now(UTC) - timedelta(days=cfg.days)
    end = datetime.now(UTC)

    report: list[str] = []
    report.append("# MOH Time OS — Discovery Report (v0.2)\n")
    report.append(f"Account: `{cfg.account}`\n")
    report.append(f"Window: `{iso(start)}` → `{iso(end)}` (timezone.utc)\n")
    report.append(
        f"Included: gmail={cfg.include_gmail} calendar={cfg.include_calendar} tasks={cfg.include_tasks} chat={cfg.include_chat}\n"
    )

    # Calendar
    if cfg.include_calendar:
        cal_res = run_gog(["calendar", "calendars"], account=cfg.account)
        if not cal_res.ok:
            report.append("\n## Calendar\n")
            report.append("ERROR: unable to list calendars.\n")
            report.append(f"Command: `{' '.join(cal_res.command or [])}`\n")
            report.append(f"Error: `{cal_res.error}`\n")
            con.commit()
            con.close()
            return {"ok": False, "error": "calendar calendars failed"}

        calendars = cal_res.data.get("calendars") or cal_res.data.get("data") or cal_res.data
        insert_raw_event(
            con,
            id=f"calendar:calendars:{cfg.account}",
            surface="calendar",
            source_ref="calendars",
            payload=cal_res.data,
        )

        cal_items = []
        if isinstance(calendars, list):
            for c in calendars:
                cal_items.append(
                    {
                        "id": c.get("id") or c.get("calendarId"),
                        "summary": c.get("summary") or c.get("name"),
                        "primary": c.get("primary"),
                        "accessRole": c.get("accessRole"),
                        "timeZone": c.get("timeZone"),
                    }
                )

        report.append("\n## Calendar inventory\n")
        report.append(f"Calendars found: **{len(cal_items)}**\n")
        for c in cal_items[:50]:
            report.append(
                f"- `{c['id']}` — {c.get('summary')} (role={c.get('accessRole')}, tz={c.get('timeZone')}, primary={c.get('primary')})\n"
            )

        # Paged calendar events (primary calendar)
        events = []
        page = None
        error_res = None
        while True:
            args = [
                "calendar",
                "events",
                "molham@hrmny.co",
                f"--from={iso(start)}",
                f"--to={iso(end)}",
                "--max=250",
            ]
            if page:
                args.append(f"--page={page}")
            ev_res = run_gog(args, account=cfg.account, timeout=180)
            if not ev_res.ok:
                error_res = ev_res
                break
            chunk = (ev_res.data or {}).get("events") or (ev_res.data or {}).get("data") or []
            if not isinstance(chunk, list):
                chunk = []
            events.extend(chunk)
            page = (ev_res.data or {}).get("nextPageToken")
            if not page:
                break

        if error_res is None:
            insert_raw_event(
                con,
                id=f"calendar:events:{cfg.account}:{cfg.days}d",
                surface="calendar",
                source_ref=f"events:{cfg.days}d",
                payload={"events": events},
            )
            report.append("\n## Calendar baseline\n")
            report.append(f"Events returned (paged): **{len(events)}**\n")
            by_day = Counter()
            by_weekday = Counter()  # 0=Mon, 6=Sun
            durations = []
            hours_by_day: dict[str, float] = {}  # date -> total hours blocked
            hours_by_weekday: dict[int, list[float]] = {i: [] for i in range(7)}

            for e in events:
                s = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date")
                en = (e.get("end") or {}).get("dateTime") or (e.get("end") or {}).get("date")
                if s:
                    by_day[s[:10]] += 1
                if s and en and "T" in s and "T" in en:
                    try:
                        sd = datetime.fromisoformat(s.replace("Z", "+00:00"))
                        ed = datetime.fromisoformat(en.replace("Z", "+00:00"))
                        dur_mins = int((ed - sd).total_seconds() / 60)
                        durations.append(dur_mins)
                        # Workload tracking
                        day_str = s[:10]
                        hours = dur_mins / 60
                        hours_by_day[day_str] = hours_by_day.get(day_str, 0) + hours
                        by_weekday[sd.weekday()] += 1
                    except Exception:
                        logging.getLogger(__name__).debug(
                            "Bad event timestamp: s=%s en=%s", s, en, exc_info=True
                        )

            # Compute workload windows
            for day_str, total_hours in hours_by_day.items():
                try:
                    dt = datetime.fromisoformat(day_str)
                    hours_by_weekday[dt.weekday()].append(total_hours)
                except Exception:
                    logging.getLogger(__name__).debug(
                        "Bad day_str for weekday: %s", day_str, exc_info=True
                    )

            avg_hours_by_weekday = {}
            weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for wd in range(7):
                vals = hours_by_weekday[wd]
                if vals:
                    avg_hours_by_weekday[weekday_names[wd]] = round(sum(vals) / len(vals), 1)
                else:
                    avg_hours_by_weekday[weekday_names[wd]] = 0

            # Daily workload stats
            all_daily_hours = list(hours_by_day.values())
            all_daily_hours.sort()

            if durations:
                durations.sort()
                report.append(
                    f"Median event duration (mins, sample): **{durations[len(durations) // 2]}**\n"
                )

            report.append("\n### Workload windows\n")
            if all_daily_hours:
                median_daily = all_daily_hours[len(all_daily_hours) // 2]
                max_daily = max(all_daily_hours)
                report.append(f"Median daily blocked hours: **{median_daily:.1f}h**\n")
                report.append(f"Peak daily blocked hours: **{max_daily:.1f}h**\n")
            report.append("Avg hours blocked by weekday:\n")
            for wd_name in weekday_names:
                report.append(f"- {wd_name}: {avg_hours_by_weekday.get(wd_name, 0)}h\n")

            # Identify overloaded days (>8h blocked)
            overloaded_days = [(d, h) for d, h in hours_by_day.items() if h > 8]
            overloaded_days.sort(key=lambda x: -x[1])
            if overloaded_days:
                report.append(f"\n⚠️ **Overloaded days (>8h blocked):** {len(overloaded_days)}\n")
                for d, h in overloaded_days[:5]:
                    report.append(f"- {d}: {h:.1f}h\n")

            report.append("\nDays with most events (top 10, sample):\n")
            for day, n in by_day.most_common(10):
                report.append(f"- {day}: {n}\n")
        else:
            report.append("\n## Calendar baseline\n")
            report.append("ERROR: unable to list events (paged).\n")
            report.append(f"Command: `{' '.join(error_res.command or [])}`\n")
            report.append(f"Error: `{error_res.error}`\n")

    # Gmail
    if cfg.include_gmail:
        report.append("\n## Gmail baseline (sample)\n")
        gm_res = run_gog(
            [
                "gmail",
                "messages",
                "search",
                f"newer_than:{cfg.days}d",
                "--max=500",
            ],
            account=cfg.account,
            timeout=180,
        )

        if gm_res.ok:
            insert_raw_event(
                con,
                id=f"gmail:messages:{cfg.account}:{cfg.days}d",
                surface="gmail",
                source_ref=f"messages:{cfg.days}d",
                payload=gm_res.data,
            )
            msgs = gm_res.data.get("messages") or gm_res.data.get("data") or []
            report.append(f"Messages sampled: **{len(msgs)}** (capped at 500)\n")

            domains = Counter()
            subj_urgent = 0
            urgent_re = re.compile(r"\b(urgent|asap|today|eod|deadline)\b", re.I)
            for m in msgs:
                frm = m.get("from") or m.get("headers", {}).get("From") or ""
                email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", frm, re.I)
                if email_match:
                    domains[_safe_email_domain(email_match.group(0))] += 1
                subj = m.get("subject") or m.get("headers", {}).get("Subject") or ""
                if subj and urgent_re.search(subj):
                    subj_urgent += 1

            report.append(f"Subjects with urgency tokens (sample): **{subj_urgent}**\n")
            report.append("Top sender domains (sample top 15):\n")
            for dom, n in domains.most_common(15):
                if dom:
                    report.append(f"- {dom}: {n}\n")
        else:
            report.append("ERROR: unable to sample Gmail messages.\n")
            report.append(f"Command: `{' '.join(gm_res.command or [])}`\n")
            report.append(f"Error: `{gm_res.error}`\n")

    # Tasks (optional)
    if cfg.include_tasks:
        report.append("\n## Google Tasks baseline\n")
        tsummary = run_tasks_discovery(con, account=cfg.account, include_completed=False)
        report.append(f"Task lists found: **{len(tsummary.get('tasklists', []))}**\n")
        report.append(f"Open tasks (sample): **{tsummary.get('openTasks')}**\n")

        # Overdue breakdown
        overdue = tsummary.get("overdueOpenTasks", 0)
        overdue_health = tsummary.get("overdueHealth", "unknown")
        health_emoji = {"critical": "🔴", "warning": "🟡", "ok": "🟢"}.get(overdue_health, "⚪")
        report.append(f"Overdue open tasks: **{overdue}** {health_emoji} ({overdue_health})\n")

        overdue_breakdown = tsummary.get("overdueBreakdown", {})
        if overdue > 0:
            report.append("Overdue breakdown:\n")
            for bucket, count in overdue_breakdown.items():
                if count > 0:
                    report.append(f"- {bucket}: {count}\n")

        # Due date coverage
        due_coverage = tsummary.get("dueDateCoverage", {})
        if due_coverage:
            report.append(
                f"\nDue date coverage: **{due_coverage.get('percentage', 0)}%** ({due_coverage.get('withDueDate', 0)} with / {due_coverage.get('withoutDueDate', 0)} without)\n"
            )

        mad = tsummary.get("medianAgeDaysByUpdatedOrCreated")
        if mad is not None:
            report.append(f"Median task age (days): **{mad}**\n")

        # Aging distribution
        aging = tsummary.get("agingDistribution", {})
        if aging:
            aging_health = aging.get("health", "unknown")
            aging_emoji = {
                "good": "🟢",
                "moderate": "🟡",
                "warning": "🟠",
                "poor": "🔴",
            }.get(aging_health, "⚪")
            report.append(f"\n### Aging distribution {aging_emoji} ({aging_health})\n")
            buckets = aging.get("buckets", {})
            percentages = aging.get("percentages", {})
            for bucket in ["0-7d", "8-30d", "31-90d", "91-180d", "180d+"]:
                count = buckets.get(bucket, 0)
                pct = percentages.get(bucket, 0)
                report.append(f"- {bucket}: {count} ({pct}%)\n")

        # Repeated patterns (potential projects/recurring)
        patterns = tsummary.get("repeatedPatterns", [])
        if patterns:
            report.append("\n### Repeated patterns (potential projects/recurring)\n")
            for p in patterns[:15]:
                report.append(f"- {p['token']}: {p['count']} ({p['potential']})\n")

    # Chat (deep baseline, sampled)
    if cfg.include_chat:
        report.append("\n## Google Chat baseline (sampled)\n")
        summary = run_chat_discovery(
            con,
            account=cfg.account,
            days=cfg.days,
            max_spaces=cfg.chat_max_spaces,
            per_space_pages=cfg.chat_pages_per_space,
        )
        report.append(f"Spaces sampled: **{summary.get('spacesSampled')}**\n")
        report.append(f"Messages sampled: **{summary.get('totalMessagesSampled')}**\n")
        report.append(f"Urgent message rate (sample): **{summary.get('urgentMessageRate'):.4f}**\n")
        report.append(f"Urgent messages: **{summary.get('urgentMessages')}**\n")

        # Sensitivity signals
        sens = summary.get("sensitiveMessages", 0)
        if sens > 0:
            report.append(
                f"⚠️ Sensitive messages detected: **{sens}** (rate: {summary.get('sensitiveMessageRate', 0):.4f})\n"
            )

        # Mention stats
        mention_stats = summary.get("mentionStats", {})
        if mention_stats.get("totalMentions"):
            report.append("\n### Mention activity\n")
            report.append(f"Total @mentions: **{mention_stats.get('totalMentions')}**\n")
            report.append(f"Unique people mentioned: **{mention_stats.get('uniqueMentioned')}**\n")
            top_mentioned = mention_stats.get("topMentioned", [])[:10]
            if top_mentioned:
                report.append("Most mentioned:\n")
                for m in top_mentioned:
                    report.append(f"- {m['name']}: {m['count']}\n")

        report.append("\n### Top spaces (by sampled message count)\n")
        for s in summary.get("messagesPerSpace", [])[:10]:
            label = f" — {s['name']}" if s.get("name") else ""
            report.append(f"- {s['space']}{label}: {s['count']}\n")

        # Signal summary
        signals = summary.get("signals", {})
        report.append(f"\n**Urgency level:** {signals.get('urgencyLevel', 'unknown')}\n")
        if signals.get("sensitivityFlag"):
            report.append("⚠️ **Sensitivity flag:** Messages with sensitive content detected\n")

    proposal = {
        "version": "MOHOS_CONFIG/v0.2",
        "account": cfg.account,
        "windowDays": cfg.days,
        "defaults": {
            "scheduling.sew": {"weekday": {"start": "10:00", "end": "20:30", "tz": "Asia/Dubai"}},
            "modes": {
                "calendar": "observe",
                "tasks": "observe",
                "email": "observe",
                "delegation": "observe",
                "alerts": "observe",
            },
        },
        "unknowns": [
            "Calendar event paging implemented for primary; expand to all calendars if needed.",
            "Gmail sampling capped at 500 messages.",
            "Chat baseline is sampled per space; time-window filtering not yet enforced per message.",
        ],
    }
    proposal_id = str(uuid.uuid4())
    insert_proposal(
        con,
        id=proposal_id,
        kind="config_proposal",
        payload=proposal,
        attribution={"generatedBy": "discover"},
        assumptions={"note": "v0.2; expand"},
    )

    report.append("\n## Outputs\n")
    report.append(f"- Inserted config proposal id: `{proposal_id}`\n")

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = os.path.join(cfg.out_dir, f"discovery-report-{ts}.md")
    proposal_path = os.path.join(cfg.out_dir, f"config-proposal-{ts}.json")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("".join(report))

    with open(proposal_path, "w", encoding="utf-8") as f:
        json.dump(proposal, f, ensure_ascii=False, indent=2)

    con.commit()
    con.close()

    return {
        "ok": True,
        "reportPath": report_path,
        "proposalPath": proposal_path,
        "proposalId": proposal_id,
    }
