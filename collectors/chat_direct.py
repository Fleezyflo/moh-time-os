#!/usr/bin/env python3
"""
Direct Google Chat API access using service account.
Bypasses gog CLI to avoid IPv6 timeout issues.
"""

import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Force IPv4 to avoid IPv6 timeout issues
_original_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _getaddrinfo_ipv4

from google.oauth2 import service_account
from googleapiclient.discovery import build

from lib import paths

SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
SCOPES = [
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
]
DEFAULT_USER = "molham@hrmny.co"

OUT_DIR = paths.out_dir()


def get_chat_service(user: str = DEFAULT_USER):
    """Get Chat API service using service account."""
    creds = service_account.Credentials.from_service_account_file(str(SA_FILE), scopes=SCOPES)
    creds = creds.with_subject(user)
    return build("chat", "v1", credentials=creds)


def list_spaces(max_spaces: int = 50, user: str = DEFAULT_USER) -> list[dict]:
    """List chat spaces."""
    import socket

    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(30)  # 30 second timeout
        service = get_chat_service(user)
        results = service.spaces().list(pageSize=max_spaces).execute()
        return results.get("spaces", [])
    except Exception as e:
        print(f"   Error listing spaces: {e}")
        return []
    finally:
        socket.setdefaulttimeout(old_timeout)


def list_messages(space_name: str, max_messages: int = 20, user: str = DEFAULT_USER) -> list[dict]:
    """List messages in a space."""
    try:
        service = get_chat_service(user)
        results = (
            service.spaces().messages().list(parent=space_name, pageSize=max_messages).execute()
        )
        return results.get("messages", [])
    except Exception:
        # Silently skip spaces we can't access
        return []


def collect_chat_full(
    max_spaces: int = 30, max_messages_per_space: int = 20, user: str = DEFAULT_USER
) -> dict:
    """
    Collect Google Chat spaces and messages.

    Returns dict with spaces and messages ready for V4 ingestion.
    """
    print(f"💬 Fetching Chat spaces (max: {max_spaces})...")

    spaces = list_spaces(max_spaces, user)
    print(f"   Found {len(spaces)} spaces")

    all_messages = []
    mentions = []

    def fetch_space(space):
        space_name = space.get("name", "")
        display_name = space.get("displayName", space_name)
        space_type = space.get("type", "UNKNOWN")

        messages = list_messages(space_name, max_messages_per_space, user)

        processed = []
        space_mentions = []

        for msg in messages:
            msg_data = {
                "name": msg.get("name", ""),
                "space_name": space_name,
                "space_display_name": display_name,
                "space_type": space_type,
                "sender": msg.get("sender", {}).get("displayName", ""),
                "sender_email": msg.get("sender", {}).get("name", ""),
                "text": msg.get("text", ""),
                "create_time": msg.get("createTime", ""),
                "thread_name": msg.get("thread", {}).get("name", ""),
            }
            processed.append(msg_data)

            # Check for mentions
            text = msg.get("text", "").lower()
            if "@molham" in text or "molham" in text:
                space_mentions.append(msg_data)

        return processed, space_mentions

    # Fetch all spaces in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_space, s): s for s in spaces}
        for i, future in enumerate(as_completed(futures)):
            try:
                msgs, ments = future.result()
                all_messages.extend(msgs)
                mentions.extend(ments)
            except Exception:
                pass

            if (i + 1) % 10 == 0:
                print(f"   Processed {i + 1}/{len(spaces)} spaces...")

    print(f"   ✅ Collected {len(all_messages)} messages, {len(mentions)} mentions")

    return {
        "collected_at": datetime.now().isoformat(),
        "user": user,
        "spaces_count": len(spaces),
        "spaces": [
            {
                "name": s.get("name"),
                "displayName": s.get("displayName"),
                "type": s.get("type"),
            }
            for s in spaces
        ],
        "messages": all_messages,
        "mentions": mentions,
    }


def save(data: dict, filename: str = "chat-full.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"   Saved to {path}")
    return path


if __name__ == "__main__":
    import sys

    max_spaces = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    max_messages = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    data = collect_chat_full(max_spaces, max_messages)
    save(data)
