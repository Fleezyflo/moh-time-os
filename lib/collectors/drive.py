"""
Drive Collector - Pulls files from Google Drive via Service Account API.
Uses direct Google API with service account for domain-wide delegation.
"""

import json
import logging
import os
import socket
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .base import BaseCollector

logger = logging.getLogger(__name__)

# Service account configuration
SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DEFAULT_USER = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")


class DriveCollector(BaseCollector):
    """Collects files from Google Drive using Service Account."""

    source_name = "drive"
    target_table = "drive_files"

    def __init__(self, config: dict, store=None):
        super().__init__(config, store)
        self._service = None

    def _set_ipv4_only(self):
        """Force IPv4 to avoid IPv6 timeout issues."""
        original_getaddrinfo = socket.getaddrinfo

        def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
            return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = getaddrinfo_ipv4

    def _get_service(self, user: str = DEFAULT_USER):
        """Get Drive API service using service account."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                str(SA_FILE), scopes=SCOPES
            )
            creds = creds.with_subject(user)
            self._service = build("drive", "v3", credentials=creds)
            return self._service
        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            self.logger.error(f"Failed to get Drive service: {e}")
            raise

    def collect(self) -> dict[str, Any]:
        """Fetch files from Google Drive."""
        self._set_ipv4_only()

        try:
            service = self._get_service()
            days = self.config.get("lookback_days", 60)
            max_results = self.config.get("max_results", 300)

            threshold = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

            # Recent files
            recent_result = (
                service.files()
                .list(
                    pageSize=max_results,
                    q=f"modifiedTime > '{threshold}' and trashed = false",
                    fields="files(id, name, mimeType, modifiedTime, createdTime, owners,"
                    " lastModifyingUser, webViewLink, parents, shared, size)",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )
            recent = recent_result.get("files", [])

            # Shared with me
            shared_result = (
                service.files()
                .list(
                    pageSize=min(max_results, 100),
                    q="sharedWithMe = true and trashed = false",
                    fields="files(id, name, mimeType, modifiedTime, createdTime, owners,"
                    " lastModifyingUser, webViewLink, shared)",
                    orderBy="modifiedTime desc",
                )
                .execute()
            )
            shared = shared_result.get("files", [])

            # Deduplicate
            seen_ids = set()
            all_files = []
            for f in recent + shared:
                fid = f.get("id")
                if fid and fid not in seen_ids:
                    seen_ids.add(fid)
                    all_files.append(f)

            return {"files": all_files}

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            self.logger.error(f"Drive collection failed: {e}")
            return {"files": []}

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform Drive files to canonical format."""
        now = datetime.now().isoformat()
        transformed = []

        for f in raw_data.get("files", []):
            file_id = f.get("id")
            if not file_id:
                continue

            owners = f.get("owners", [])
            owner_emails = [
                o.get("emailAddress", o.get("displayName", ""))
                for o in owners
                if isinstance(o, dict)
            ]
            last_modifier = ""
            lmu = f.get("lastModifyingUser")
            if isinstance(lmu, dict):
                last_modifier = lmu.get("emailAddress", "")

            transformed.append(
                {
                    "id": f"drive_{file_id}",
                    "source": "drive",
                    "source_id": file_id,
                    "name": f.get("name", ""),
                    "mime_type": f.get("mimeType", ""),
                    "modified_time": f.get("modifiedTime", ""),
                    "created_time": f.get("createdTime", ""),
                    "owners": json.dumps(owner_emails),
                    "last_modifying_user": last_modifier,
                    "web_view_link": f.get("webViewLink", ""),
                    "shared": 1 if f.get("shared") else 0,
                    "size": int(f.get("size", 0) or 0),
                    "created_at": now,
                    "updated_at": now,
                }
            )

        return transformed
