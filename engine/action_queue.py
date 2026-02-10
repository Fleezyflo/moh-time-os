import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class ActionItem:
    id: str
    surface: str  # chat|gmail|calendar
    title: str
    who: str | None
    when: str | None
    ask: str
    source: dict[str, Any]


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def build_from_chat_unread(chat_path: str) -> list[ActionItem]:
    data = json.loads(open(chat_path, encoding="utf-8").read())
    items: list[ActionItem] = []

    # Only include messages that explicitly @mention Moh (Molham Homsi) in text.
    for space_id, info in data.items():
        space_name = info.get("name") or ""
        for m in info.get("messages") or []:
            txt = (m.get("text") or "").strip()
            if not txt:
                continue
            if (
                "@Molham Homsi" not in txt
                and "@molham" not in txt.lower()
                and "molham homsi" not in txt.lower()
            ):
                continue

            items.append(
                ActionItem(
                    id=m.get("resource") or f"{space_id}:{m.get('createTime')}",
                    surface="chat",
                    title=f"Chat: {space_name or space_id}",
                    who=m.get("sender") or m.get("author"),
                    when=m.get("createTime"),
                    ask=txt,
                    source={
                        "space": space_id,
                        "spaceName": space_name,
                        "thread": m.get("thread"),
                        "uri": f"https://chat.google.com/room/{space_id.split('/')[-1]}?cls=11",
                    },
                )
            )

    # Most recent first
    items.sort(key=lambda x: x.when or "", reverse=True)
    return items


def build_from_calendar_next24h(cal_path: str) -> list[ActionItem]:
    events = json.loads(open(cal_path, encoding="utf-8").read())
    items: list[ActionItem] = []
    for e in events:
        s = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date")
        en = (e.get("end") or {}).get("dateTime") or (e.get("end") or {}).get("date")
        items.append(
            ActionItem(
                id=e.get("id") or (e.get("iCalUID") or ""),
                surface="calendar",
                title=f"Calendar: {e.get('summary')}",
                who=(e.get("organizer") or {}).get("email"),
                when=s,
                ask=f"Upcoming event: {e.get('summary')} ({s} → {en})",
                source={
                    "htmlLink": e.get("htmlLink"),
                    "hangoutLink": e.get("hangoutLink"),
                },
            )
        )
    items.sort(key=lambda x: x.when or "")
    return items


def build_from_gmail_unread_threads(gmail_path: str) -> list[ActionItem]:
    threads = json.loads(open(gmail_path, encoding="utf-8").read())
    items: list[ActionItem] = []
    for t in threads:
        tid = t.get("id")
        if not tid:
            continue
        items.append(
            ActionItem(
                id=tid,
                surface="gmail",
                title=f"Email: {t.get('subject')}",
                who=t.get("from"),
                when=t.get("date"),
                ask=f"Unread thread: {t.get('subject')}",
                source={
                    "labels": t.get("labels"),
                    "messageCount": t.get("messageCount"),
                    "threadId": tid,
                },
            )
        )
    return items


def write_operator_view(
    out_md: str,
    *,
    chat_items: list[ActionItem],
    cal_items: list[ActionItem],
    gmail_items: list[ActionItem],
    meta: dict[str, Any],
) -> None:
    lines: list[str] = []
    lines.append("# Time OS — Operator Queue\n")
    lines.append(f"Generated: {_now_iso()} (UTC)\n")
    lines.append("\nThis file is meant to be the *one page* you read.\n")

    lines.append("\n## Calendar (next 24h)\n")
    for it in cal_items:
        link = it.source.get("htmlLink") if isinstance(it.source, dict) else None
        lines.append(f"- {it.ask}{(' — ' + link) if link else ''}\n")

    lines.append("\n## Chat: direct mentions (unread)\n")
    for it in chat_items:
        lines.append(f"- [{it.title}] {it.ask} (from {it.who}, at {it.when})\n")
        lines.append(f"  - open: {it.source.get('uri')}\n")

    lines.append("\n## Gmail: unread threads (raw list)\n")
    lines.append(f"Count: {len(gmail_items)} (capped by collector)\n")
    for it in gmail_items[:30]:
        lines.append(f"- {it.title} — from {it.who} — {it.when}\n")

    lines.append("\n---\n")
    lines.append("## Build status\n")
    lines.append(f"- inputs: {meta}\n")
    lines.append(
        "- next: enable People API to resolve chat user ids to names (optional but improves UX)\n"
    )

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("".join(lines))
