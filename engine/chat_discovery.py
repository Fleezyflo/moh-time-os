import re
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from .gogcli import run_gog
from .store import insert_raw_event

URGENT_RE = re.compile(r"\b(urgent|asap|today|eod|deadline|pls|please|need|required)\b", re.I)
SENSITIVITY_RE = re.compile(
    r"\b(confidential|private|sensitive|do not share|internal only|nda|salary|termination|legal|hr|complaint|fired|disciplinary)\b",
    re.I,
)
MENTION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9 ]+?)(?=[\s,.:;!?]|$)")  # Captures @Name patterns


def _extract_text(msg: dict) -> str:
    # gog returns Chat message content in different fields depending on type.
    # Prefer plain text when available.
    for k in ("text", "formattedText", "argumentText"):
        v = msg.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _author(msg: dict) -> str:
    a = msg.get("sender") or msg.get("author") or {}
    # Some payloads use a string for sender/author.
    if isinstance(a, str):
        return a
    if not isinstance(a, dict):
        return ""
    # sender.name can be users/...; displayName sometimes present
    return a.get("name") or a.get("email") or a.get("displayName") or ""


def _msg_time(msg: dict) -> str:
    return msg.get("createTime") or msg.get("create_time") or msg.get("updateTime") or ""


def list_spaces(account: str) -> tuple[list[dict], list[str]]:
    spaces: list[dict] = []
    page = None
    errors: list[str] = []
    while True:
        args = ["chat", "spaces", "list", "--max=100"]
        if page:
            args.append(f"--page={page}")
        res = run_gog(args, account=account, timeout=180)
        if not res.ok:
            errors.append(res.error or "unknown error")
            break
        data = res.data or {}
        chunk = data.get("spaces") or data.get("data") or []
        spaces.extend(chunk)
        page = data.get("nextPageToken")
        if not page:
            break
    return spaces, errors


def list_threads(account: str, space: str) -> tuple[list[dict], list[str]]:
    threads: list[dict] = []
    page = None
    errors: list[str] = []
    while True:
        args = ["chat", "threads", "list", space, "--max=50"]
        if page:
            args.append(f"--page={page}")
        res = run_gog(args, account=account, timeout=180)
        if not res.ok:
            errors.append(res.error or "unknown error")
            break
        data = res.data or {}
        chunk = data.get("threads") or data.get("data") or []
        threads.extend(chunk)
        page = data.get("nextPageToken")
        if not page:
            break
    return threads, errors


def _parse_time(ts: str) -> float:
    # returns unix seconds; 0 if parse fails
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def list_messages(
    account: str, space: str, *, max_pages: int = 50, cutoff_utc: float | None = None
) -> tuple[list[dict], list[str]]:
    """Paged message listing per space.

    Messages are ordered newest-first. If cutoff_utc is provided, we stop paging once we reach messages older than cutoff.
    """
    msgs: list[dict] = []
    page = None
    errors: list[str] = []
    pages = 0
    while True:
        args = [
            "chat",
            "messages",
            "list",
            space,
            "--max=50",
            "--order=createTime desc",
        ]
        if page:
            args.append(f"--page={page}")
        res = run_gog(args, account=account, timeout=180)
        if not res.ok:
            errors.append(res.error or "unknown error")
            break
        data = res.data or {}
        chunk = data.get("messages") or data.get("data") or []
        if not chunk:
            break

        # Filter by cutoff if available
        if cutoff_utc is not None:
            kept = []
            for m in chunk:
                ct = m.get("createTime") or m.get("create_time") or ""
                t = _parse_time(ct) if ct else 0.0
                if t == 0.0 or t >= cutoff_utc:
                    kept.append(m)
            msgs.extend(kept)

            # If the oldest message in this page is older than cutoff, stop paging.
            oldest = chunk[-1]
            oct = oldest.get("createTime") or oldest.get("create_time") or ""
            ot = _parse_time(oct) if oct else 0.0
            if ot != 0.0 and ot < cutoff_utc:
                break
        else:
            msgs.extend(chunk)

        page = data.get("nextPageToken")
        pages += 1
        if not page or pages >= max_pages:
            break
    return msgs, errors


def _extract_mentions(txt: str) -> list[str]:
    """Extract @mentions from message text."""
    # Also handle <users/ID> format that Google Chat sometimes uses
    mentions = []
    # Standard @Name pattern
    for match in MENTION_RE.findall(txt):
        mentions.append(match.strip())
    # users/ID pattern (Google Chat internal)
    for match in re.findall(r"<users/(\d+)>", txt):
        mentions.append(f"users/{match}")
    return mentions


def _resolve_author_name(author_id: str, members_cache: dict[str, str]) -> str:
    """Try to resolve user ID to a human-readable name."""
    if not author_id:
        return ""
    # If we have it cached, use it
    if author_id in members_cache:
        return members_cache[author_id]
    # If it's already a name (not users/...), return as-is
    if not author_id.startswith("users/"):
        return author_id
    # Return ID for now; enrichment can happen later
    return author_id


def summarize_chat(
    messages_by_space: dict[str, list[dict]],
    space_names: dict[str, str] | None = None,
    members_cache: dict[str, str] | None = None,
) -> dict[str, Any]:
    total = 0
    urgent = 0
    sensitive = 0
    by_space_count = {}
    by_author = Counter()
    mention_counts = Counter()
    all_mentions: list[str] = []

    if members_cache is None:
        members_cache = {}

    def _label(space: str) -> str:
        if space_names and space in space_names and space_names[space]:
            return space_names[space]
        return ""

    for space, msgs in messages_by_space.items():
        by_space_count[space] = len(msgs)
        for m in msgs:
            total += 1
            txt = _extract_text(m)
            if txt:
                if URGENT_RE.search(txt):
                    urgent += 1
                if SENSITIVITY_RE.search(txt):
                    sensitive += 1
                # Extract mentions
                mentions = _extract_mentions(txt)
                all_mentions.extend(mentions)
                for mention in mentions:
                    mention_counts[mention] += 1

            author_id = _author(m)
            resolved = _resolve_author_name(author_id, members_cache)
            by_author[resolved or author_id] += 1

    top_authors = [{"author": a, "count": n} for a, n in by_author.most_common(15) if a]

    top_mentioned = [
        {"name": name, "count": n} for name, n in mention_counts.most_common(15) if name
    ]

    return {
        "totalMessagesSampled": total,
        "urgentMessageRate": round((urgent / total), 4) if total else 0,
        "urgentMessages": urgent,
        "sensitiveMessages": sensitive,
        "sensitiveMessageRate": round((sensitive / total), 4) if total else 0,
        "spacesSampled": len(messages_by_space),
        "messagesPerSpace": sorted(
            [{"space": s, "name": _label(s), "count": c} for s, c in by_space_count.items()],
            key=lambda x: -x["count"],
        )[:20],
        "topAuthors": top_authors,
        "mentionStats": {
            "totalMentions": len(all_mentions),
            "uniqueMentioned": len(set(all_mentions)),
            "topMentioned": top_mentioned,
        },
        "signals": {
            "urgencyLevel": "high" if urgent > 50 else "moderate" if urgent > 10 else "low",
            "sensitivityFlag": sensitive > 0,
        },
    }


def run_chat_discovery(
    con, *, account: str, days: int, max_spaces: int = 200, per_space_pages: int = 50
) -> dict[str, Any]:
    """Deep Chat baseline.

    Strategy:
    - Enumerate all spaces (paged).
    - For each space, list messages newest-first and STOP once we cross the discovery cutoff.

    This makes an "all spaces" run feasible without requiring a hard-coded message cap.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    cutoff_utc = cutoff.timestamp()

    spaces, space_errors = list_spaces(account)
    spaces = spaces[:max_spaces]

    space_names: dict[str, str] = {}
    for sp in spaces:
        key = sp.get("resource") or sp.get("name") or ""
        nm = sp.get("name") or sp.get("displayName") or sp.get("spaceName") or ""
        if key:
            space_names[key] = nm

    insert_raw_event(
        con,
        id=f"chat:spaces:{account}",
        surface="chat",
        source_ref="spaces",
        payload={
            "spaces": spaces,
            "errors": space_errors,
            "ts": datetime.now(UTC).isoformat(),
            "cutoff": cutoff.isoformat(),
        },
    )

    messages_by_space: dict[str, list[dict]] = {}
    errors: list[dict] = []

    for sp in spaces:
        space_name = sp.get("resource") or sp.get("name") or ""
        if not space_name:
            continue
        msgs, errs = list_messages(
            account, space_name, max_pages=per_space_pages, cutoff_utc=cutoff_utc
        )
        messages_by_space[space_name] = msgs
        if errs:
            errors.append({"space": space_name, "errors": errs})
        insert_raw_event(
            con,
            id=f"chat:messages:{account}:{space_name}",
            surface="chat",
            source_ref=f"messages:{space_name}",
            payload={
                "space": sp,
                "messages": msgs,
                "errors": errs,
                "cutoff": cutoff.isoformat(),
            },
        )

    summary = summarize_chat(messages_by_space, space_names=space_names)
    summary["errors"] = errors
    summary["notes"] = {
        "windowDaysRequested": days,
        "cutoff": cutoff.isoformat(),
        "implementation": "Stops paging per space once oldest message is older than cutoff.",
    }
    return summary
