"""
Contacts Collector - Pulls contacts from Google People API via Service Account.
Uses direct Google API with service account for domain-wide delegation.
"""

import json
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Any

from lib.credential_paths import google_sa_file

from .base import BaseCollector
from .resilience import COLLECTOR_ERRORS

logger = logging.getLogger(__name__)


def _sa_file():
    """Resolve SA file at call time to respect env overrides."""
    return google_sa_file()


# Service account configuration
SCOPES = [
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/directory.readonly",
]
DEFAULT_USER = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")


class ContactsCollector(BaseCollector):
    """Collects contacts from Google People API using Service Account."""

    source_name = "contacts"
    target_table = "contacts"
    OUTPUT_TABLES = ["contacts"]

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
        """Get People API service using service account."""
        if self._service:
            return self._service

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                str(_sa_file()), scopes=SCOPES
            )
            creds = creds.with_subject(user)
            self._service = build("people", "v1", credentials=creds)
            return self._service
        except COLLECTOR_ERRORS as e:
            self.logger.error(f"Failed to get People service: {e}")
            raise

    def collect(self) -> dict[str, Any]:
        """Fetch contacts and directory entries."""
        self._set_ipv4_only()

        try:
            service = self._get_service()
            max_results = self.config.get("max_results", 2000)

            # Personal contacts
            contacts: list[dict] = []
            page_token = None
            while True:
                results = (
                    service.people()
                    .connections()
                    .list(
                        resourceName="people/me",
                        pageSize=min(max_results - len(contacts), 1000),
                        personFields="names,emailAddresses,phoneNumbers,organizations,"
                        "biographies,metadata",
                        pageToken=page_token,
                    )
                    .execute()
                )
                contacts.extend(results.get("connections", []))
                page_token = results.get("nextPageToken")
                if not page_token or len(contacts) >= max_results:
                    break

            # Domain directory
            directory = []
            try:
                dir_results = (
                    service.people()
                    .listDirectoryPeople(
                        readMask="names,emailAddresses,phoneNumbers,organizations,photos",
                        sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
                        pageSize=min(self.config.get("max_directory", 500), 1000),
                    )
                    .execute()
                )
                directory = dir_results.get("people", [])
            except COLLECTOR_ERRORS as e:
                self.logger.warning(f"Directory listing failed: {e}")

            return {"contacts": contacts, "directory": directory}

        except COLLECTOR_ERRORS as e:
            self.logger.error(f"Contacts collection failed: {e}")
            raise  # Propagate to sync() — never return empty data as success

    def _extract_person(self, person: dict) -> dict:
        """Extract relevant info from a person resource."""
        names = person.get("names", [])
        emails = person.get("emailAddresses", [])
        phones = person.get("phoneNumbers", [])
        orgs = person.get("organizations", [])

        return {
            "resource_name": person.get("resourceName", ""),
            "name": names[0].get("displayName", "") if names else "",
            "first_name": names[0].get("givenName", "") if names else "",
            "last_name": names[0].get("familyName", "") if names else "",
            "emails": json.dumps([e.get("value", "") for e in emails]),
            "primary_email": emails[0].get("value", "") if emails else "",
            "phones": json.dumps([p.get("value", "") for p in phones]),
            "organization": orgs[0].get("name", "") if orgs else "",
            "title": orgs[0].get("title", "") if orgs else "",
        }

    def transform(self, raw_data: dict) -> list[dict]:
        """Transform contacts to canonical format, deduplicated by email."""
        now = datetime.now(timezone.utc).isoformat()
        seen_emails: set[str] = set()
        transformed = []

        all_people = raw_data.get("contacts", []) + raw_data.get("directory", [])

        for person in all_people:
            info = self._extract_person(person)
            email = info["primary_email"].lower()

            # Deduplicate by email
            if email and email in seen_emails:
                continue
            if email:
                seen_emails.add(email)

            transformed.append(
                {
                    "id": f"contact_{info['resource_name'].replace('/', '_')}",
                    "source": "contacts",
                    "source_id": info["resource_name"],
                    "name": info["name"],
                    "first_name": info["first_name"],
                    "last_name": info["last_name"],
                    "primary_email": info["primary_email"],
                    "emails": info["emails"],
                    "phones": info["phones"],
                    "organization": info["organization"],
                    "title": info["title"],
                    "created_at": now,
                    "updated_at": now,
                }
            )

        return transformed
