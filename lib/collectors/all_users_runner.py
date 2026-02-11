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
CHAT_SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# All supported services
ALL_SERVICES = ["gmail", "calendar", "chat", "drive", "docs"]

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


def get_chat_service(user: str):
    """Get Chat API service with SA+DWD."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if AUTH_DEBUG:
        with open(SA_FILE) as f:
            sa_data = json.load(f)
        debug_print(f"SA_EMAIL: {sa_data.get('client_email')}")
        debug_print(f"SUBJECT: {user}")
        debug_print(f"SCOPES: {CHAT_SCOPES}")

    creds = service_account.Credentials.from_service_account_file(str(SA_FILE), scopes=CHAT_SCOPES)
    creds = creds.with_subject(user)
    return build("chat", "v1", credentials=creds)


def get_drive_service(user: str):
    """Get Drive API service with SA+DWD."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if AUTH_DEBUG:
        with open(SA_FILE) as f:
            sa_data = json.load(f)
        debug_print(f"SA_EMAIL: {sa_data.get('client_email')}")
        debug_print(f"SUBJECT: {user}")
        debug_print(f"SCOPES: {DRIVE_SCOPES}")

    creds = service_account.Credentials.from_service_account_file(str(SA_FILE), scopes=DRIVE_SCOPES)
    creds = creds.with_subject(user)
    return build("drive", "v3", credentials=creds)


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


def collect_chat_for_user(
    user: str,
    since: str,
    until: str,
    limit: int,
    db_path: Path,
) -> dict[str, Any]:
    """
    Collect Chat spaces and messages for a single user.
    Returns: {ok: bool, count: int, spaces_count: int, error: str|None, is_invalid_subject: bool}
    """
    result: dict[str, Any] = {
        "ok": False,
        "count": 0,
        "spaces_count": 0,
        "error": None,
        "is_invalid_subject": False,
    }

    try:
        svc = get_chat_service(user)

        # Parse since/until for local filtering
        since_dt = datetime.fromisoformat(
            since.replace("Z", "+00:00") if "T" in since else since + "T00:00:00+00:00"
        )
        until_dt = datetime.fromisoformat(
            until.replace("Z", "+00:00") if "T" in until else until + "T23:59:59+00:00"
        )

        # Step 1: List all spaces with pagination
        debug_print("ENDPOINT: chat.spaces.list")
        spaces: list[dict[str, Any]] = []
        page_token = None

        while len(spaces) < limit:
            list_params = {"pageSize": min(100, limit - len(spaces))}
            if page_token:
                list_params["pageToken"] = page_token

            response = svc.spaces().list(**list_params).execute()
            items = response.get("spaces", [])
            spaces.extend(items)

            debug_print(f"STATUS: 200 OK, {len(items)} spaces this page (total: {len(spaces)})")

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
            page_token = next_page_token
            debug_print("nextPageToken present for spaces, continuing...")

        result["spaces_count"] = len(spaces)

        # Step 2: For each space, get messages with pagination
        total_messages = 0
        messages_per_space = max(1, limit // max(1, len(spaces))) if spaces else limit

        for space in spaces:
            if total_messages >= limit:
                break

            space_name = space.get("name", "")
            debug_print(f"ENDPOINT: chat.spaces.messages.list({space_name[:30]}...)")

            space_messages = 0
            page_token = None
            pages_fetched = 0
            max_pages_per_space = 5  # Limit pagination to avoid runaway loops

            while (
                space_messages < messages_per_space
                and total_messages < limit
                and pages_fetched < max_pages_per_space
            ):
                msg_params = {
                    "parent": space_name,
                    "pageSize": min(100, limit - total_messages),
                }
                if page_token:
                    msg_params["pageToken"] = page_token

                try:
                    msg_response = svc.spaces().messages().list(**msg_params).execute()
                    messages = msg_response.get("messages", [])
                    pages_fetched += 1

                    # Filter by createTime within since/until window
                    filtered_count = 0
                    for msg in messages:
                        create_time = msg.get("createTime", "")
                        if create_time:
                            try:
                                msg_dt = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                                if since_dt <= msg_dt <= until_dt:
                                    filtered_count += 1
                            except ValueError:
                                filtered_count += 1  # Include if can't parse
                        else:
                            filtered_count += 1

                    space_messages += filtered_count
                    total_messages += filtered_count

                    debug_print(
                        f"STATUS: 200 OK, {len(messages)} messages ({filtered_count} in window) from {space_name[:20]}..."
                    )

                    next_page_token = msg_response.get("nextPageToken")
                    if not next_page_token:
                        break
                    page_token = next_page_token

                except Exception as e:
                    debug_print(f"ERROR fetching messages from {space_name[:20]}...: {e}")
                    break

        # Store cursor
        set_cursor(db_path, "chat", user, "last_until", until)

        result["ok"] = True
        result["count"] = total_messages

    except Exception as e:
        error_str = str(e)
        result["error"] = error_str
        debug_print(f"ERROR: {error_str}")

        if "invalid_grant" in error_str.lower():
            result["is_invalid_subject"] = True
            add_to_blocklist(db_path, user, "invalid_grant", error_str[:500])

    return result


def collect_drive_for_user(
    user: str,
    since: str,
    until: str,
    limit: int,
    db_path: Path,
) -> dict[str, Any]:
    """
    Collect Drive files for a single user with date range and pagination.
    Returns: {ok: bool, count: int, docs_count: int, doc_ids: list, error: str|None, is_invalid_subject: bool}
    """
    result: dict[str, Any] = {
        "ok": False,
        "count": 0,
        "docs_count": 0,
        "doc_ids": [],
        "error": None,
        "is_invalid_subject": False,
    }

    try:
        svc = get_drive_service(user)

        # Build query with modifiedTime filter
        since_rfc = since if "T" in since else since + "T00:00:00Z"
        until_rfc = until if "T" in until else until + "T23:59:59Z"

        query = (
            f"modifiedTime >= '{since_rfc}' and modifiedTime <= '{until_rfc}' and trashed = false"
        )

        debug_print(f"ENDPOINT: drive.files.list(q='{query[:50]}...')")

        files: list[dict[str, Any]] = []
        doc_ids: list[str] = []
        page_token = None

        while len(files) < limit:
            list_params = {
                "pageSize": min(100, limit - len(files)),
                "q": query,
                "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, owners)",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }
            if page_token:
                list_params["pageToken"] = page_token

            response = svc.files().list(**list_params).execute()
            items = response.get("files", [])
            files.extend(items)

            # Track Google Docs for docs extraction
            for f in items:
                if f.get("mimeType") == "application/vnd.google-apps.document":
                    doc_ids.append(f.get("id"))

            debug_print(f"STATUS: 200 OK, {len(items)} files this page (total: {len(files)})")

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
            page_token = next_page_token
            debug_print("nextPageToken present for files, continuing...")

        # Store cursor
        set_cursor(db_path, "drive", user, "last_until", until)

        result["ok"] = True
        result["count"] = len(files)
        result["docs_count"] = len(doc_ids)
        result["doc_ids"] = doc_ids[:limit]  # Limit doc IDs for docs extraction

    except Exception as e:
        error_str = str(e)
        result["error"] = error_str
        debug_print(f"ERROR: {error_str}")

        if "invalid_grant" in error_str.lower():
            result["is_invalid_subject"] = True
            add_to_blocklist(db_path, user, "invalid_grant", error_str[:500])

    return result


def collect_docs_for_user(
    user: str,
    doc_ids: list[str],
    limit: int,
    db_path: Path,
) -> dict[str, Any]:
    """
    Extract text content from Google Docs using drive.readonly export.
    Returns: {ok: bool, count: int, sample_text: str|None, error: str|None, is_invalid_subject: bool}
    """
    result: dict[str, Any] = {
        "ok": False,
        "count": 0,
        "sample_text": None,
        "error": None,
        "is_invalid_subject": False,
    }

    if not doc_ids:
        result["ok"] = True
        return result

    try:
        svc = get_drive_service(user)  # Reuse drive.readonly for export

        debug_print(f"ENDPOINT: drive.files.export (docs extraction for {len(doc_ids)} docs)")

        extracted_count = 0
        sample_text = None

        for doc_id in doc_ids[:limit]:
            try:
                # Export as plain text
                response = svc.files().export(fileId=doc_id, mimeType="text/plain").execute()
                text = response.decode("utf-8") if isinstance(response, bytes) else str(response)
                extracted_count += 1

                # Keep first sample for proof
                if sample_text is None and len(text) > 100:
                    sample_text = text[:500]

                debug_print(f"STATUS: 200 OK, exported doc {doc_id[:15]}... ({len(text)} chars)")

            except Exception as e:
                debug_print(f"ERROR exporting doc {doc_id[:15]}...: {e}")
                continue

        result["ok"] = True
        result["count"] = extracted_count
        result["sample_text"] = sample_text

    except Exception as e:
        error_str = str(e)
        result["error"] = error_str
        debug_print(f"ERROR: {error_str}")

        if "invalid_grant" in error_str.lower():
            result["is_invalid_subject"] = True

    return result


def run_all_users(
    since: str,
    until: str,
    limit_users: int | None = None,
    limit_per_user: int = 50,
    dry_run: bool = False,
    services: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run collection for all internal users across specified services.
    Returns coverage report JSON with detailed categorization.
    """
    db_path = paths.db_path()
    ensure_tables(db_path)

    # Default to all services if none specified
    if services is None:
        services = ALL_SERVICES.copy()

    users = get_internal_users(db_path)
    people_inventory_count = len(users)

    if limit_users:
        users = users[:limit_users]

    logger.info(
        f"Running collection for {len(users)} users, services={services}, since={since}, until={until}"
    )

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
                    "services": services,
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
        "services": services,
        "people_inventory_count": people_inventory_count,
        "per_user": {},
        "totals": {
            "attempted_count": 0,
            "succeeded_count": 0,
            "skipped_invalid_subject_count": 0,
            "failed_other_count": 0,
            "gmail_count": 0,
            "calendar_event_count": 0,
            "chat_message_count": 0,
            "chat_space_count": 0,
            "drive_file_count": 0,
            "docs_extracted_count": 0,
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

        user_report: dict[str, Any] = {"status": "attempted"}
        is_invalid = False
        any_success = False
        doc_ids: list[str] = []

        # Gmail collection
        if "gmail" in services:
            gmail_result = collect_gmail_for_user(user, since, until, limit_per_user, db_path)
            user_report["gmail"] = {
                "ok": gmail_result["ok"],
                "count": gmail_result["count"],
                "error": gmail_result.get("error"),
            }
            if gmail_result.get("is_invalid_subject"):
                is_invalid = True
            elif gmail_result["ok"]:
                any_success = True
                report["totals"]["gmail_count"] += gmail_result["count"]

        # Calendar collection
        if "calendar" in services:
            calendar_result = collect_calendar_for_user(user, since, until, limit_per_user, db_path)
            user_report["calendar"] = {
                "ok": calendar_result["ok"],
                "count": calendar_result["count"],
                "error": calendar_result.get("error"),
            }
            if calendar_result.get("is_invalid_subject"):
                is_invalid = True
            elif calendar_result["ok"]:
                any_success = True
                report["totals"]["calendar_event_count"] += calendar_result["count"]

        # Chat collection
        if "chat" in services:
            chat_result = collect_chat_for_user(user, since, until, limit_per_user, db_path)
            user_report["chat"] = {
                "ok": chat_result["ok"],
                "count": chat_result["count"],
                "spaces_count": chat_result.get("spaces_count", 0),
                "error": chat_result.get("error"),
            }
            if chat_result.get("is_invalid_subject"):
                is_invalid = True
            elif chat_result["ok"]:
                any_success = True
                report["totals"]["chat_message_count"] += chat_result["count"]
                report["totals"]["chat_space_count"] += chat_result.get("spaces_count", 0)

        # Drive collection
        if "drive" in services:
            drive_result = collect_drive_for_user(user, since, until, limit_per_user, db_path)
            user_report["drive"] = {
                "ok": drive_result["ok"],
                "count": drive_result["count"],
                "docs_count": drive_result.get("docs_count", 0),
                "error": drive_result.get("error"),
            }
            if drive_result.get("is_invalid_subject"):
                is_invalid = True
            elif drive_result["ok"]:
                any_success = True
                report["totals"]["drive_file_count"] += drive_result["count"]
                doc_ids = drive_result.get("doc_ids", [])

        # Docs extraction (depends on drive results)
        if "docs" in services and doc_ids:
            docs_result = collect_docs_for_user(user, doc_ids, limit_per_user, db_path)
            user_report["docs"] = {
                "ok": docs_result["ok"],
                "count": docs_result["count"],
                "sample_text": docs_result.get("sample_text"),
                "error": docs_result.get("error"),
            }
            if docs_result.get("is_invalid_subject"):
                is_invalid = True
            elif docs_result["ok"]:
                any_success = True
                report["totals"]["docs_extracted_count"] += docs_result["count"]

        # Categorize outcome
        if is_invalid:
            user_report["status"] = "invalid_subject"
            report["totals"]["skipped_invalid_subject_count"] += 1
        elif any_success:
            user_report["status"] = "succeeded"
            report["totals"]["succeeded_count"] += 1
        else:
            user_report["status"] = "failed"
            report["totals"]["failed_other_count"] += 1

        report["per_user"][user] = user_report

    # Add blocklist count to report
    report["totals"]["blocklist_total"] = get_blocklist_count(db_path)

    return report


def main():
    parser = argparse.ArgumentParser(description="All-Users Multi-Service Collector")
    parser.add_argument("--since", default="2025-06-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument(
        "--until", default=datetime.now(UTC).strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)"
    )
    parser.add_argument("--limit-users", type=int, help="Limit number of users to process")
    parser.add_argument(
        "--limit-per-user", type=int, default=50, help="Limit items per user per service"
    )
    parser.add_argument(
        "--services",
        default=",".join(ALL_SERVICES),
        help=f"Comma-separated list of services ({','.join(ALL_SERVICES)})",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print planned users without calling APIs"
    )

    args = parser.parse_args()

    # Parse services
    services = [s.strip() for s in args.services.split(",") if s.strip()]
    invalid_services = [s for s in services if s not in ALL_SERVICES]
    if invalid_services:
        logger.error(f"Invalid services: {invalid_services}. Valid: {ALL_SERVICES}")
        sys.exit(1)

    report = run_all_users(
        since=args.since,
        until=args.until,
        limit_users=args.limit_users,
        limit_per_user=args.limit_per_user,
        dry_run=args.dry_run,
        services=services,
    )

    if report:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
