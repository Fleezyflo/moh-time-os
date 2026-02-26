import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from .gogcli import run_gog
from .store import insert_raw_event

WORD_RE = re.compile(r"[A-Za-z0-9']+")


def _parse_rfc3339(ts: str) -> float:
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def list_tasklists(account: str) -> tuple[list[dict], list[str]]:
    res = run_gog(["tasks", "lists", "list"], account=account, timeout=120)
    if not res.ok:
        return [], [res.error or "unknown error"]
    data = res.data or {}
    lists = (
        data.get("tasklists") or data.get("lists") or data.get("items") or data.get("data") or []
    )
    if not isinstance(lists, list):
        lists = []
    return lists, []


def list_tasks_paged(
    account: str,
    tasklist_id: str,
    *,
    include_completed: bool = False,
    max_pages: int = 50,
) -> tuple[list[dict], list[str]]:
    tasks: list[dict] = []
    page = None
    pages = 0
    errors: list[str] = []
    while True:
        args = ["tasks", "list", tasklist_id, "--max=100"]
        if include_completed:
            args += ["--show-completed", "--show-hidden"]
        if page:
            args.append(f"--page={page}")
        res = run_gog(args, account=account, timeout=180)
        if not res.ok:
            errors.append(res.error or "unknown error")
            break
        data = res.data or {}
        chunk = data.get("tasks") or data.get("items") or data.get("data") or []
        if not isinstance(chunk, list):
            chunk = []
        tasks.extend(chunk)
        page = data.get("nextPageToken")
        pages += 1
        if not page or pages >= max_pages:
            break
    return tasks, errors


def _compute_aging_distribution(ages_days: list[int]) -> dict[str, Any]:
    """Compute aging buckets for tasks."""
    buckets = {
        "0-7d": 0,
        "8-30d": 0,
        "31-90d": 0,
        "91-180d": 0,
        "180d+": 0,
    }
    for age in ages_days:
        if age <= 7:
            buckets["0-7d"] += 1
        elif age <= 30:
            buckets["8-30d"] += 1
        elif age <= 90:
            buckets["31-90d"] += 1
        elif age <= 180:
            buckets["91-180d"] += 1
        else:
            buckets["180d+"] += 1

    total = len(ages_days)
    distribution = {
        "buckets": buckets,
        "percentages": {k: round(v / total * 100, 1) if total else 0 for k, v in buckets.items()},
    }

    # Health indicator based on aging
    if total == 0:
        distribution["health"] = "unknown"
    elif buckets["180d+"] / total > 0.3:
        distribution["health"] = "poor"  # >30% ancient tasks
    elif buckets["91-180d"] / total > 0.25:
        distribution["health"] = "warning"  # >25% stale
    elif buckets["0-7d"] / total > 0.4:
        distribution["health"] = "good"  # >40% fresh
    else:
        distribution["health"] = "moderate"

    return distribution


def _find_repeated_patterns(token_counts: Counter, min_count: int = 3) -> list[dict[str, Any]]:
    """Identify repeated tokens that might indicate recurring task types or projects."""
    patterns = []
    # Common noise words to filter
    noise = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "have",
        "will",
        "been",
        "but",
        "not",
        "are",
        "was",
    }

    for token, count in token_counts.most_common(50):
        if count >= min_count and token not in noise:
            patterns.append(
                {
                    "token": token,
                    "count": count,
                    "potential": "project"
                    if count >= 10
                    else "recurring"
                    if count >= 5
                    else "pattern",
                }
            )
    return patterns[:30]


def summarize_tasks(now_utc: float, tasks_by_list: dict[str, list[dict]]) -> dict[str, Any]:
    total = 0
    completed = 0
    overdue = 0
    overdue_by_days: dict[str, int] = {"1-7d": 0, "8-30d": 0, "31-90d": 0, "90d+": 0}
    ages_days: list[int] = []
    token_counts = Counter()
    has_due_date = 0
    no_due_date = 0

    for _list_id, tasks in tasks_by_list.items():
        for t in tasks:
            total += 1
            status = (t.get("status") or "").lower()
            if status == "completed":
                completed += 1

            title = (t.get("title") or "").strip()
            for w in WORD_RE.findall(title.lower()):
                if len(w) >= 3:
                    token_counts[w] += 1

            updated = t.get("updated") or ""
            created = t.get("created") or ""
            ts = _parse_rfc3339(updated) or _parse_rfc3339(created)
            if ts:
                ages_days.append(int((now_utc - ts) // 86400))

            due = t.get("due") or ""
            if due:
                has_due_date += 1
                due_ts = _parse_rfc3339(due)
                if due_ts and due_ts < now_utc and status != "completed":
                    overdue += 1
                    overdue_days = int((now_utc - due_ts) // 86400)
                    if overdue_days <= 7:
                        overdue_by_days["1-7d"] += 1
                    elif overdue_days <= 30:
                        overdue_by_days["8-30d"] += 1
                    elif overdue_days <= 90:
                        overdue_by_days["31-90d"] += 1
                    else:
                        overdue_by_days["90d+"] += 1
            else:
                no_due_date += 1

    ages_days.sort()
    median_age = ages_days[len(ages_days) // 2] if ages_days else None
    aging_distribution = _compute_aging_distribution(ages_days)
    repeated_patterns = _find_repeated_patterns(token_counts)

    open_tasks = total - completed

    return {
        "totalTasksSampled": total,
        "completedTasks": completed,
        "openTasks": open_tasks,
        "overdueOpenTasks": overdue,
        "overdueBreakdown": overdue_by_days,
        "overdueHealth": "critical" if overdue > 20 else "warning" if overdue > 5 else "ok",
        "dueDateCoverage": {
            "withDueDate": has_due_date,
            "withoutDueDate": no_due_date,
            "percentage": round(has_due_date / total * 100, 1) if total else 0,
        },
        "medianAgeDaysByUpdatedOrCreated": median_age,
        "agingDistribution": aging_distribution,
        "repeatedPatterns": repeated_patterns,
        "topTitleTokens": [{"token": t, "count": n} for t, n in token_counts.most_common(30)],
    }


def run_tasks_discovery(con, *, account: str, include_completed: bool = False) -> dict[str, Any]:
    lists, list_errors = list_tasklists(account)
    insert_raw_event(
        con,
        id=f"tasks:lists:{account}",
        surface="tasks",
        source_ref="lists",
        payload={
            "tasklists": lists,
            "errors": list_errors,
            "ts": datetime.now(UTC).isoformat(),
        },
    )

    tasks_by_list: dict[str, list[dict]] = {}
    errors: list[dict] = []

    for tl in lists:
        tlid = tl.get("id") or tl.get("tasklistId")
        if not tlid:
            continue
        tasks, errs = list_tasks_paged(account, tlid, include_completed=include_completed)
        tasks_by_list[tlid] = tasks
        if errs:
            errors.append({"tasklistId": tlid, "title": tl.get("title"), "errors": errs})
        insert_raw_event(
            con,
            id=f"tasks:list:{account}:{tlid}",
            surface="tasks",
            source_ref=f"list:{tlid}",
            payload={"tasklist": tl, "tasks": tasks, "errors": errs},
        )

    now_utc = datetime.now(UTC).timestamp()
    summary = summarize_tasks(now_utc, tasks_by_list)
    summary["tasklists"] = [
        {
            "id": (tl.get("id") or tl.get("tasklistId")),
            "title": tl.get("title") or tl.get("name"),
        }
        for tl in lists
        if (tl.get("id") or tl.get("tasklistId"))
    ]
    summary["errors"] = errors
    return summary
