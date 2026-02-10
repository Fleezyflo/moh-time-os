#!/usr/bin/env python3
"""
Gmail Multi-User Collector

Collects Gmail from all team members incrementally.
- Processes one user per run (round-robin)
- Stores per-user state to track progress
- Aggregates into gmail-full.json
- Designed to run frequently via cron (every 5-10 min)
"""

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta

from lib import paths

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Paths
OUT_DIR = paths.out_dir()
STATE_DB = paths.data_dir() / "gmail_collector_state.db"
MAIN_DB = paths.db_path()

# Config
MAX_MESSAGES_PER_USER = 50
DAYS_LOOKBACK = 14
COOLDOWN_MINUTES = 30  # Wait before re-collecting from same user


def init_state_db():
    """Initialize state tracking database."""
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(STATE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_state (
            email TEXT PRIMARY KEY,
            last_collected_at TEXT,
            message_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            last_error TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            collected_from TEXT,
            from_addr TEXT,
            to_addr TEXT,
            subject TEXT,
            date TEXT,
            labels TEXT,
            collected_at TEXT
        )
    """)
    conn.commit()
    return conn


def get_valid_users() -> list[str]:
    """Get list of valid Gmail users from team_members."""
    if not MAIN_DB.exists():
        return ["molham@hrmny.co"]

    conn = sqlite3.connect(str(MAIN_DB))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT email FROM team_members
        WHERE email LIKE '%@hrmny.co'
        AND email NOT IN ('me@hrmny.co', 'test@hrmny.co')
    """)
    emails = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Filter to known-valid users (tested with delegation)
    valid = [
        "molham@hrmny.co",
        "fady@hrmny.co",
        "zeiad@hrmny.co",
        "noura@hrmny.co",
        "elija@hrmny.co",
        "eifel@hrmny.co",
        "raafat@hrmny.co",
        "mostafa@hrmny.co",
        "ramy@hrmny.co",
        "mark@hrmny.co",
        "joshua@hrmny.co",
        "elnaz@hrmny.co",
        "youssef.f@hrmny.co",
        "imad@hrmny.co",
        "jessica@hrmny.co",
        "nathan@hrmny.co",
        "aubrey@hrmny.co",
        "dana@hrmny.co",
        "ay@hrmny.co",
        "maher.c@hrmny.co",
        "krystie@hrmny.co",
        "fabina@hrmny.co",
    ]
    return [e for e in emails if e in valid] or valid


def get_next_user(conn: sqlite3.Connection) -> str | None:
    """Get next user to collect from (round-robin with cooldown)."""
    users = get_valid_users()
    cutoff = (datetime.now(UTC) - timedelta(minutes=COOLDOWN_MINUTES)).isoformat()

    # Find user not collected recently
    cursor = conn.execute(
        """
        SELECT email FROM user_state
        WHERE last_collected_at < ?
        ORDER BY last_collected_at ASC
        LIMIT 1
    """,
        (cutoff,),
    )
    row = cursor.fetchone()

    if row:
        return row[0]

    # Find user never collected
    cursor = conn.execute("SELECT email FROM user_state")
    collected = {r[0] for r in cursor.fetchall()}
    uncollected = [u for u in users if u not in collected]

    if uncollected:
        return uncollected[0]

    # All users on cooldown, pick oldest
    cursor = conn.execute("""
        SELECT email FROM user_state
        ORDER BY last_collected_at ASC
        LIMIT 1
    """)
    row = cursor.fetchone()
    return row[0] if row else users[0] if users else None


def collect_user_gmail(user: str) -> dict:
    """Collect Gmail for a single user."""
    from collectors.gmail_direct import get_gmail_service

    result = {"messages": [], "error": None}

    try:
        svc = get_gmail_service(user)
        query = f"in:inbox newer_than:{DAYS_LOOKBACK}d"

        response = (
            svc.users()
            .messages()
            .list(userId="me", maxResults=MAX_MESSAGES_PER_USER, q=query)
            .execute()
        )

        msg_refs = response.get("messages", [])

        for ref in msg_refs:
            try:
                msg = (
                    svc.users()
                    .messages()
                    .get(
                        userId="me",
                        id=ref["id"],
                        format="metadata",
                        metadataHeaders=["From", "To", "Subject", "Date"],
                    )
                    .execute()
                )

                headers = {
                    h["name"]: h["value"]
                    for h in msg.get("payload", {}).get("headers", [])
                }

                result["messages"].append(
                    {
                        "id": ref["id"],
                        "from": headers.get("From", ""),
                        "to": headers.get("To", ""),
                        "subject": headers.get("Subject", ""),
                        "date": headers.get("Date", ""),
                        "labels": msg.get("labelIds", []),
                    }
                )
            except Exception as e:
                logger.warning(f"Error fetching message {ref['id']}: {e}")

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error collecting from {user}: {e}")

    return result


def store_messages(conn: sqlite3.Connection, user: str, messages: list[dict]):
    """Store messages in state database."""
    now = datetime.now(UTC).isoformat()

    for msg in messages:
        conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, collected_from, from_addr, to_addr, subject, date, labels, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                msg["id"],
                user,
                msg["from"],
                msg["to"],
                msg["subject"],
                msg["date"],
                json.dumps(msg["labels"]),
                now,
            ),
        )

    conn.commit()


def update_user_state(
    conn: sqlite3.Connection, user: str, count: int, error: str | None
):
    """Update user collection state."""
    now = datetime.now(UTC).isoformat()

    if error:
        conn.execute(
            """
            INSERT INTO user_state (email, last_collected_at, message_count, error_count, last_error)
            VALUES (?, ?, 0, 1, ?)
            ON CONFLICT(email) DO UPDATE SET
                last_collected_at = ?,
                error_count = error_count + 1,
                last_error = ?
        """,
            (user, now, error, now, error),
        )
    else:
        conn.execute(
            """
            INSERT INTO user_state (email, last_collected_at, message_count, error_count, last_error)
            VALUES (?, ?, ?, 0, NULL)
            ON CONFLICT(email) DO UPDATE SET
                last_collected_at = ?,
                message_count = ?,
                error_count = 0,
                last_error = NULL
        """,
            (user, now, count, now, count),
        )

    conn.commit()


def export_aggregated_json(conn: sqlite3.Connection):
    """Export all messages to gmail-full.json."""
    cursor = conn.execute("""
        SELECT id, collected_from, from_addr, to_addr, subject, date, labels
        FROM messages
        ORDER BY collected_at DESC
    """)

    messages = []
    for row in cursor:
        messages.append(
            {
                "id": row[0],
                "_collected_from": row[1],
                "from": row[2],
                "to": row[3],
                "subject": row[4],
                "date": row[5],
                "labels": json.loads(row[6]) if row[6] else [],
            }
        )

    # Get user stats
    cursor = conn.execute("SELECT COUNT(DISTINCT collected_from) FROM messages")
    user_count = cursor.fetchone()[0]

    data = {
        "collected_at": datetime.now(UTC).isoformat(),
        "messages": messages,
        "user_count": user_count,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "gmail-full.json").write_text(json.dumps(data, indent=2))

    return len(messages), user_count


def run_collection_cycle():
    """Run one collection cycle (one user)."""
    conn = init_state_db()

    user = get_next_user(conn)
    if not user:
        logger.info("No users to collect from")
        return

    logger.info(f"Collecting from: {user}")

    result = collect_user_gmail(user)

    if result["error"]:
        update_user_state(conn, user, 0, result["error"])
        logger.error(f"Collection failed: {result['error']}")
    else:
        messages = result["messages"]
        store_messages(conn, user, messages)
        update_user_state(conn, user, len(messages), None)
        logger.info(f"Collected {len(messages)} messages from {user}")

    # Export aggregated JSON
    total_msgs, total_users = export_aggregated_json(conn)
    logger.info(f"Exported {total_msgs} messages from {total_users} users")

    conn.close()


def run_full_collection():
    """Run collection for all users (for initial population)."""
    conn = init_state_db()
    users = get_valid_users()

    for i, user in enumerate(users):
        logger.info(f"[{i + 1}/{len(users)}] Collecting from: {user}")

        result = collect_user_gmail(user)

        if result["error"]:
            update_user_state(conn, user, 0, result["error"])
            logger.error(f"  Error: {result['error'][:50]}")
        else:
            messages = result["messages"]
            store_messages(conn, user, messages)
            update_user_state(conn, user, len(messages), None)
            logger.info(f"  Collected {len(messages)} messages")

    total_msgs, total_users = export_aggregated_json(conn)
    logger.info(f"Total: {total_msgs} messages from {total_users} users")

    conn.close()


def get_status():
    """Get collection status."""
    if not STATE_DB.exists():
        return {"status": "not_initialized"}

    conn = sqlite3.connect(str(STATE_DB))

    cursor = conn.execute("SELECT COUNT(*) FROM messages")
    msg_count = cursor.fetchone()[0]

    cursor = conn.execute("SELECT COUNT(DISTINCT collected_from) FROM messages")
    user_count = cursor.fetchone()[0]

    cursor = conn.execute("""
        SELECT email, last_collected_at, message_count, error_count
        FROM user_state
        ORDER BY last_collected_at DESC
    """)
    user_states = [
        {"email": r[0], "last_collected": r[1], "messages": r[2], "errors": r[3]}
        for r in cursor.fetchall()
    ]

    conn.close()

    return {
        "total_messages": msg_count,
        "users_collected": user_count,
        "user_states": user_states,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "full":
            run_full_collection()
        elif cmd == "status":
            import pprint

            pprint.pprint(get_status())
        elif cmd == "cycle":
            run_collection_cycle()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: gmail_multi_user.py [cycle|full|status]")
    else:
        # Default: run one cycle
        run_collection_cycle()
