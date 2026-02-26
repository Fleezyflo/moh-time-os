#!/usr/bin/env python3
"""
Direct Google Contacts/People API access using service account.
"""

import json
import socket
from datetime import datetime
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

from lib import paths


def _patch_ipv4():
    """Force IPv4 to avoid IPv6 timeout issues with Google APIs."""
    _original = socket.getaddrinfo

    def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return _original(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _ipv4_only


_patch_ipv4()

SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
SCOPES = [
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/directory.readonly",
]
DEFAULT_USER = "molham@hrmny.co"

OUT_DIR = paths.out_dir()


def get_people_service(user: str = DEFAULT_USER):
    """Get People API service using service account."""
    creds = service_account.Credentials.from_service_account_file(str(SA_FILE), scopes=SCOPES)
    creds = creds.with_subject(user)
    return build("people", "v1", credentials=creds)


def list_contacts(max_results: int = 1000, user: str = DEFAULT_USER) -> list[dict]:
    """List all contacts."""
    try:
        service = get_people_service(user)

        contacts = []
        page_token = None

        while True:
            results = (
                service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    pageSize=min(max_results - len(contacts), 1000),
                    personFields="names,emailAddresses,phoneNumbers,organizations,biographies,metadata",
                    pageToken=page_token,
                )
                .execute()
            )

            connections = results.get("connections", [])
            contacts.extend(connections)

            page_token = results.get("nextPageToken")
            if not page_token or len(contacts) >= max_results:
                break

        return contacts
    except Exception as e:
        print(f"   Error listing contacts: {e}")
        return []


def list_directory(max_results: int = 500, user: str = DEFAULT_USER) -> list[dict]:
    """List domain directory (coworkers)."""
    try:
        service = get_people_service(user)

        results = (
            service.people()
            .listDirectoryPeople(
                readMask="names,emailAddresses,phoneNumbers,organizations,photos",
                sources=["DIRECTORY_SOURCE_TYPE_DOMAIN_PROFILE"],
                pageSize=min(max_results, 1000),
            )
            .execute()
        )

        return results.get("people", [])
    except Exception as e:
        print(f"   Error listing directory: {e}")
        return []


def extract_contact_info(person: dict) -> dict:
    """Extract relevant info from a person resource."""
    names = person.get("names", [])
    emails = person.get("emailAddresses", [])
    phones = person.get("phoneNumbers", [])
    orgs = person.get("organizations", [])

    return {
        "resourceName": person.get("resourceName", ""),
        "name": names[0].get("displayName", "") if names else "",
        "firstName": names[0].get("givenName", "") if names else "",
        "lastName": names[0].get("familyName", "") if names else "",
        "emails": [e.get("value", "") for e in emails],
        "primaryEmail": emails[0].get("value", "") if emails else "",
        "phones": [p.get("value", "") for p in phones],
        "organization": orgs[0].get("name", "") if orgs else "",
        "title": orgs[0].get("title", "") if orgs else "",
    }


def collect_contacts_full(user: str = DEFAULT_USER) -> dict:
    """
    Collect contacts and directory comprehensively.
    """
    print("👥 Fetching contacts...")

    contacts_raw = list_contacts(max_results=2000, user=user)
    print(f"   Found {len(contacts_raw)} contacts")

    directory_raw = list_directory(max_results=500, user=user)
    print(f"   Found {len(directory_raw)} directory entries")

    # Process contacts
    contacts = [extract_contact_info(c) for c in contacts_raw]
    directory = [extract_contact_info(d) for d in directory_raw]

    # Deduplicate by email
    seen_emails = set()
    all_people = []

    for person in contacts + directory:
        email = person.get("primaryEmail", "").lower()
        if email and email not in seen_emails:
            seen_emails.add(email)
            all_people.append(person)
        elif not email and person.get("name"):
            all_people.append(person)

    print(f"   ✅ Collected {len(all_people)} unique people")

    return {
        "collected_at": datetime.now().isoformat(),
        "user": user,
        "contacts_count": len(contacts),
        "directory_count": len(directory),
        "people": all_people,
    }


def save(data: dict, filename: str = "contacts.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"   Saved to {path}")
    return path


if __name__ == "__main__":
    data = collect_contacts_full()
    save(data)
