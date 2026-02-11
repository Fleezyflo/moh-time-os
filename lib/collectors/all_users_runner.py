#!/usr/bin/env python3
"""
All-Users Runner - Collects Gmail + Calendar for all internal users.

Usage:
    AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner --since 2025-06-01 --until 2026-02-11
    AUTH_DEBUG=1 uv run python -m lib.collectors.all_users_runner --since 2025-06-01 --limit-users 2 --limit-per-user 10
    uv run python -m lib.collectors.all_users_runner --dry-run
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lib import paths

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Service account configuration
SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

AUTH_DEBUG = os.environ.get("AUTH_DEBUG", "0") == "1"


def debug_print(msg: str) -> None:
    """Print debug message if AUTH_DEBUG is enabled."""
    if AUTH_DEBUG:
        print(f"[AUTH_DEBUG] {msg}", file=sys.stderr)


def get_internal_users(db_path: Path) -> list[str]:
    """Get all internal user emails from people table."""
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return []

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM people WHERE type='internal' AND email IS NOT NULL")
    emails = [row[0] for row in cursor.fetchall()]
    conn.close()
    return emails


def ensure_tables(db_path: Path) -> None:
    """Create required tables if not exist."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_cursor (
            service TEXT NOT NULL,
            subject TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            updated_at TEXT,
            PRIMARY KEY (service, subject, key)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subject_blocklist (
            subject TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            error_detail TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def is_blocklisted(db_path: Path, subject: str) -> tuple[bool, str | None]:
    """Check if subject is blocklisted. Returns (is_blocked, reason)."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT reason FROM subject_blocklist WHERE subject=?",
        (subject,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return True, row[0]
    return False, None


def add_to_blocklist(
    db_path: Path, subject: str, reason: str, error_detail: str | None = None
) -> None:
    """Add subject to blocklist."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT OR REPLACE INTO subject_blocklist (subject, reason, error_detail, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (subject, reason, error_detail, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()


def get_blocklist_count(db_path: Path) -> int:
    """Get count of blocklisted subjects."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT COUNT(*) FROM subject_blocklist")
    row = cursor.fetchone()
    count: int = row[0] if row else 0
    conn.close()
    return count


def get_cursor(db_path: Path, service: str, subject: str, key: str) -> str | None:
    """Get stored cursor value."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT value FROM sync_cursor WHERE service=? AND subject=? AND key=?",
        (service, subject, key),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def set_cursor(db_path: Path, service: str, subject: str, key: str, value: str) -> None:
    """Store cursor value."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT OR REPLACE INTO sync_cursor (service, subject, key, value, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (service, subject, key, value, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()


def get_gmail_service(user: str):
    """Get Gmail API service with SA+DWD."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if AUTH_DEBUG:
        with open(SA_FILE) as f:
            sa_data = json.load(f)
        debug_print(f"SA_EMAIL: {sa_data.get('client_email')}")
        debug_print(f"SUBJECT: {user}")
        debug_print(f"SCOPES: {GMAIL_SCOPES}")

    creds = service_account.Credentials.from_service_account_file(str(SA_FILE), scopes=GMAIL_SCOPES)
    creds = creds.with_subject(user)
    return build("gmail", "v1", credentials=creds)


def get_calendar_service(user: str):
    """Get Calendar API service with SA+DWD."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if AUTH_DEBUG:
        with open(SA_FILE) as f:
            sa_data = json.load(f)
        debug_print(f"SA_EMAIL: {sa_data.get('client_email')}")
        debug_print(f"SUBJECT: {user}")
        debug_print(f"SCOPES: {CALENDAR_SCOPES}")

    creds = service_account.Credentials.from_service_account_file(
        str(SA_FILE), scopes=CALENDAR_SCOPES
    )
    creds = creds.with_subject(user)
    return build("calendar", "v3", credentials=creds)


def collect_gmail_for_user(
    user: str,
    since: str,
    until: str,
    limit: int,
    db_path: Path,
) -> dict[str, Any]:
    """
    Collect Gmail for a single user with date range and pagination.
    Returns: {ok: bool, count: int, error: str|None, is_invalid_subject: bool}
    """
    result: dict[str, Any] = {"ok": False, "count": 0, "error": None, "is_invalid_subject": False}

    try:
        svc = get_gmail_service(user)

        # Convert dates to Gmail query format: after:YYYY/MM/DD before:YYYY/MM/DD
        since_dt = datetime.fromisoformat(
            since.replace("Z", "+00:00") if "T" in since else since + "T00:00:00+00:00"
        )
        until_dt = datetime.fromisoformat(
            until.replace("Z", "+00:00") if "T" in until else until + "T23:59:59+00:00"
        )

        query = f"after:{since_dt.strftime('%Y/%m/%d')} before:{until_dt.strftime('%Y/%m/%d')}"

        debug_print(f"ENDPOINT: gmail.users.messages.list(userId='me', q='{query}')")

        total_count = 0
        page_token = None
        page_num = 0

        while True:
            page_num += 1
            request_params = {
                "userId": "me",
                "maxResults": min(limit - total_count, 100),
                "q": query,
            }
            if page_token:
                request_params["pageToken"] = page_token

            response = svc.users().messages().list(**request_params).execute()
            messages = response.get("messages", [])
            count_this_page = len(messages)
            total_count += count_this_page

            debug_print(
                f"STATUS: 200 OK, page {page_num}, {count_this_page} messages (total: {total_count})"
            )

            next_page_token = response.get("nextPageToken")

            if not next_page_token or total_count >= limit:
                break

            page_token = next_page_token
            debug_print("nextPageToken present, continuing pagination...")

        # Store cursor (last_until timestamp)
        set_cursor(db_path, "gmail", user, "last_until", until)

        result["ok"] = True
        result["count"] = total_count

    except Exception as e:
        error_str = str(e)
        result["error"] = error_str
        debug_print(f"ERROR: {error_str}")

        # Detect invalid_grant (not a valid workspace user)
        if "invalid_grant" in error_str.lower():
            result["is_invalid_subject"] = True
            add_to_blocklist(db_path, user, "invalid_grant", error_str[:500])
        elif "403" in error_str or "401" in error_str:
            logger.error(f"Gmail auth error for {user}: {error_str}")

    return result


def collect_calendar_for_user(
    user: str,
    since: str,
    until: str,
    limit: int,
    db_path: Path,
) -> dict[str, Any]:
    """
    Collect Calendar events for ALL calendars for a single user.
    Returns: {ok: bool, count: int, calendars: list[str], error: str|None, is_invalid_subject: bool}
    """
    result: dict[str, Any] = {
        "ok": False,
        "count": 0,
        "calendars": [],
        "error": None,
        "is_invalid_subject": False,
    }

    try:
        svc = get_calendar_service(user)

        # Convert dates to RFC3339
        since_rfc = since if "T" in since else since + "T00:00:00Z"
        until_rfc = until if "T" in until else until + "T23:59:59Z"

        # Step 1: Get all calendars for this user (with pagination)
        debug_print("ENDPOINT: calendar.calendarList.list")

        calendar_ids = []
        page_token = None

        while True:
            list_params = {"maxResults": 250}
            if page_token:
                list_params["pageToken"] = page_token

            cal_response = svc.calendarList().list(**list_params).execute()
            items = cal_response.get("items", [])

            for cal in items:
                calendar_ids.append(cal.get("id"))

            debug_print(
                f"STATUS: 200 OK, {len(items)} calendars this page (total: {len(calendar_ids)})"
            )

            next_page_token = cal_response.get("nextPageToken")
            if not next_page_token:
                break
            page_token = next_page_token
            debug_print("nextPageToken present for calendarList, continuing...")

        result["calendars"] = calendar_ids

        # Step 2: For each calendar, get events (with pagination)
        total_events = 0
        events_per_calendar = max(1, limit // max(1, len(calendar_ids))) if calendar_ids else limit

        for cal_id in calendar_ids:
            if total_events >= limit:
                break

            debug_print(f"ENDPOINT: calendar.events.list(calendarId='{cal_id[:30]}...')")

            cal_events = 0
            page_token = None

            while cal_events < events_per_calendar and total_events < limit:
                event_params = {
                    "calendarId": cal_id,
                    "timeMin": since_rfc,
                    "timeMax": until_rfc,
                    "maxResults": min(250, limit - total_events),
                    "singleEvents": True,
                    "orderBy": "startTime",
                }
                if page_token:
                    event_params["pageToken"] = page_token

                try:
                    events_response = svc.events().list(**event_params).execute()
                    events = events_response.get("items", [])
                    cal_events += len(events)
                    total_events += len(events)

                    debug_print(
                        f"STATUS: 200 OK, {len(events)} events from {cal_id[:30]}... (cal total: {cal_events}, user total: {total_events})"
                    )

                    next_page_token = events_response.get("nextPageToken")
                    if not next_page_token:
                        break
                    page_token = next_page_token
                    debug_print("nextPageToken present for events, continuing...")

                except Exception as e:
                    # Some calendars may not be accessible; log and continue
                    debug_print(f"ERROR fetching events from {cal_id[:30]}...: {e}")
                    break

            # Store cursor per calendar
            set_cursor(db_path, "calendar", user, f"calendar:{cal_id}:last_until", until)

        result["ok"] = True
        result["count"] = total_events

    except Exception as e:
        error_str = str(e)
        result["error"] = error_str
        debug_print(f"ERROR: {error_str}")

        # Detect invalid_grant (not a valid workspace user)
        if "invalid_grant" in error_str.lower():
            result["is_invalid_subject"] = True
            add_to_blocklist(db_path, user, "invalid_grant", error_str[:500])
        elif "403" in error_str or "401" in error_str:
            logger.error(f"Calendar auth error for {user}: {error_str}")

    return result


def run_all_users(
    since: str,
    until: str,
    limit_users: int | None = None,
    limit_per_user: int = 50,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Run Gmail + Calendar collection for all internal users.
    Returns coverage report JSON with detailed categorization.
    """
    db_path = paths.db_path()
    ensure_tables(db_path)

    users = get_internal_users(db_path)
    people_inventory_count = len(users)

    if limit_users:
        users = users[:limit_users]

    logger.info(f"Running collection for {len(users)} users, since={since}, until={until}")

    if dry_run:
        # Check blocklist status for each user
        blocklisted = []
        active = []
        for u in users:
            blocked, reason = is_blocklisted(db_path, u)
            if blocked:
                blocklisted.append({"email": u, "reason": reason})
            else:
                active.append(u)

        print(
            json.dumps(
                {
                    "dry_run": True,
                    "since": since,
                    "until": until,
                    "people_inventory_count": people_inventory_count,
                    "users_to_attempt": len(active),
                    "users_blocklisted": len(blocklisted),
                    "active_users": active,
                    "blocklisted_users": blocklisted,
                },
                indent=2,
            )
        )
        return {}

    report: dict[str, Any] = {
        "since": since,
        "until": until,
        "people_inventory_count": people_inventory_count,
        "per_user": {},
        "totals": {
            "attempted_count": 0,
            "succeeded_count": 0,
            "skipped_invalid_subject_count": 0,
            "failed_other_count": 0,
            "gmail_count": 0,
            "calendar_event_count": 0,
        },
    }

    for i, user in enumerate(users):
        # Check blocklist first
        blocked, block_reason = is_blocklisted(db_path, user)
        if blocked:
            logger.info(f"[{i+1}/{len(users)}] SKIP (blocklisted): {user} - {block_reason}")
            report["per_user"][user] = {
                "status": "skipped",
                "reason": f"blocklisted: {block_reason}",
            }
            report["totals"]["skipped_invalid_subject_count"] += 1
            continue

        logger.info(f"[{i+1}/{len(users)}] Processing: {user}")
        report["totals"]["attempted_count"] += 1

        user_report: dict[str, Any] = {
            "status": "attempted",
            "gmail": {"ok": False, "count": 0, "error": None},
            "calendar": {"ok": False, "count": 0, "error": None},
        }

        # Gmail collection
        gmail_result = collect_gmail_for_user(user, since, until, limit_per_user, db_path)
        user_report["gmail"] = {
            "ok": gmail_result["ok"],
            "count": gmail_result["count"],
            "error": gmail_result.get("error"),
        }

        # Calendar collection
        calendar_result = collect_calendar_for_user(user, since, until, limit_per_user, db_path)
        user_report["calendar"] = {
            "ok": calendar_result["ok"],
            "count": calendar_result["count"],
            "error": calendar_result.get("error"),
        }

        # Categorize outcome
        gmail_invalid = gmail_result.get("is_invalid_subject", False)
        cal_invalid = calendar_result.get("is_invalid_subject", False)

        if gmail_invalid or cal_invalid:
            # Invalid subject - already added to blocklist by collect functions
            user_report["status"] = "invalid_subject"
            report["totals"]["skipped_invalid_subject_count"] += 1
        elif gmail_result["ok"] and calendar_result["ok"]:
            user_report["status"] = "succeeded"
            report["totals"]["succeeded_count"] += 1
            report["totals"]["gmail_count"] += gmail_result["count"]
            report["totals"]["calendar_event_count"] += calendar_result["count"]
        elif gmail_result["ok"] or calendar_result["ok"]:
            # Partial success
            user_report["status"] = "partial"
            report["totals"]["succeeded_count"] += 1
            if gmail_result["ok"]:
                report["totals"]["gmail_count"] += gmail_result["count"]
            if calendar_result["ok"]:
                report["totals"]["calendar_event_count"] += calendar_result["count"]
        else:
            # Both failed for other reasons
            user_report["status"] = "failed"
            report["totals"]["failed_other_count"] += 1

        report["per_user"][user] = user_report

    # Add blocklist count to report
    report["totals"]["blocklist_total"] = get_blocklist_count(db_path)

    return report


def main():
    parser = argparse.ArgumentParser(description="All-Users Gmail + Calendar Collector")
    parser.add_argument("--since", default="2025-06-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument(
        "--until", default=datetime.now(UTC).strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)"
    )
    parser.add_argument("--limit-users", type=int, help="Limit number of users to process")
    parser.add_argument(
        "--limit-per-user", type=int, default=50, help="Limit items per user per service"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print planned users without calling APIs"
    )

    args = parser.parse_args()

    report = run_all_users(
        since=args.since,
        until=args.until,
        limit_users=args.limit_users,
        limit_per_user=args.limit_per_user,
        dry_run=args.dry_run,
    )

    if report:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
