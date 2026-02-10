#!/usr/bin/env python3
"""
Direct Google Drive API access using service account.
"""

import json
import socket
from datetime import datetime, timedelta
from pathlib import Path

# Force IPv4
_original_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _getaddrinfo_ipv4

from google.oauth2 import service_account
from googleapiclient.discovery import build

from lib import paths

SA_FILE = (
    Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
)
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DEFAULT_USER = "molham@hrmny.co"

OUT_DIR = paths.out_dir()


def get_drive_service(user: str = DEFAULT_USER):
    """Get Drive API service using service account."""
    creds = service_account.Credentials.from_service_account_file(
        str(SA_FILE), scopes=SCOPES
    )
    creds = creds.with_subject(user)
    return build("drive", "v3", credentials=creds)


def list_recent_files(
    days: int = 60, max_results: int = 200, user: str = DEFAULT_USER
) -> list[dict]:
    """List recently modified files."""
    try:
        service = get_drive_service(user)

        # Calculate date threshold
        threshold = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

        results = (
            service.files()
            .list(
                pageSize=max_results,
                q=f"modifiedTime > '{threshold}' and trashed = false",
                fields="files(id, name, mimeType, modifiedTime, createdTime, owners, lastModifyingUser, webViewLink, parents, shared, size)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        return results.get("files", [])
    except Exception as e:
        print(f"   Error listing files: {e}")
        return []


def list_shared_with_me(max_results: int = 100, user: str = DEFAULT_USER) -> list[dict]:
    """List files shared with me."""
    try:
        service = get_drive_service(user)

        results = (
            service.files()
            .list(
                pageSize=max_results,
                q="sharedWithMe = true and trashed = false",
                fields="files(id, name, mimeType, modifiedTime, createdTime, owners, lastModifyingUser, webViewLink, shared)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        return results.get("files", [])
    except Exception as e:
        print(f"   Error listing shared files: {e}")
        return []


def list_my_files(max_results: int = 100, user: str = DEFAULT_USER) -> list[dict]:
    """List files owned by me."""
    try:
        service = get_drive_service(user)

        results = (
            service.files()
            .list(
                pageSize=max_results,
                q="'me' in owners and trashed = false",
                fields="files(id, name, mimeType, modifiedTime, createdTime, owners, lastModifyingUser, webViewLink, parents, shared, size)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        return results.get("files", [])
    except Exception as e:
        print(f"   Error listing my files: {e}")
        return []


def collect_drive_full(days: int = 60, user: str = DEFAULT_USER) -> dict:
    """
    Collect Drive files comprehensively.
    """
    print(f"📁 Fetching Drive files (last {days} days)...")

    recent = list_recent_files(days, max_results=300, user=user)
    print(f"   Found {len(recent)} recent files")

    shared = list_shared_with_me(max_results=100, user=user)
    print(f"   Found {len(shared)} shared files")

    # Deduplicate
    seen_ids = set()
    all_files = []

    for f in recent + shared:
        if f["id"] not in seen_ids:
            seen_ids.add(f["id"])
            all_files.append(
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "mimeType": f.get("mimeType"),
                    "modifiedTime": f.get("modifiedTime"),
                    "createdTime": f.get("createdTime"),
                    "owners": [
                        o.get("emailAddress", o.get("displayName", ""))
                        for o in f.get("owners", [])
                    ],
                    "lastModifyingUser": f.get("lastModifyingUser", {}).get(
                        "emailAddress", ""
                    ),
                    "webViewLink": f.get("webViewLink"),
                    "shared": f.get("shared", False),
                    "size": f.get("size", 0),
                }
            )

    print(f"   ✅ Collected {len(all_files)} unique files")

    return {
        "collected_at": datetime.now().isoformat(),
        "user": user,
        "days": days,
        "files": all_files,
    }


def save(data: dict, filename: str = "drive-files.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"   Saved to {path}")
    return path


if __name__ == "__main__":
    import sys

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    data = collect_drive_full(days)
    save(data)
