"""
Collector HTTP Record/Replay Harness.

Features:
- Record HTTP responses to cassettes
- Replay from cassettes in tests
- Secret redaction
- Expiry policy
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import sqlite3

CASSETTES_DIR = Path(__file__).parent.parent.parent / "tests" / "cassettes"

# Patterns for secret redaction
SECRET_PATTERNS = [
    (r'"access_token"\s*:\s*"[^"]*"', '"access_token": "[REDACTED]"'),
    (r'"refresh_token"\s*:\s*"[^"]*"', '"refresh_token": "[REDACTED]"'),
    (r'"api_key"\s*:\s*"[^"]*"', '"api_key": "[REDACTED]"'),
    (r'"password"\s*:\s*"[^"]*"', '"password": "[REDACTED]"'),
    (r'"secret"\s*:\s*"[^"]*"', '"secret": "[REDACTED]"'),
    (r"Bearer\s+[A-Za-z0-9\-._~+/=]+", "Bearer [REDACTED]"),
    (r'"Authorization"\s*:\s*"[^"]*"', '"Authorization": "[REDACTED]"'),
]

# Default cassette expiry
DEFAULT_EXPIRY_DAYS = 30


@dataclass
class CassetteEntry:
    """A single recorded HTTP interaction."""

    request_method: str
    request_url: str
    request_headers: dict[str, str]
    request_body: str | None
    response_status: int
    response_headers: dict[str, str]
    response_body: str
    recorded_at: str
    expires_at: str


@dataclass
class Cassette:
    """A collection of recorded HTTP interactions."""

    name: str
    version: int = 1
    entries: list[CassetteEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "entries": [
                {
                    "request": {
                        "method": e.request_method,
                        "url": e.request_url,
                        "headers": e.request_headers,
                        "body": e.request_body,
                    },
                    "response": {
                        "status": e.response_status,
                        "headers": e.response_headers,
                        "body": e.response_body,
                    },
                    "recorded_at": e.recorded_at,
                    "expires_at": e.expires_at,
                }
                for e in self.entries
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Cassette":
        entries = []
        for e in data.get("entries", []):
            entries.append(
                CassetteEntry(
                    request_method=e["request"]["method"],
                    request_url=e["request"]["url"],
                    request_headers=e["request"]["headers"],
                    request_body=e["request"].get("body"),
                    response_status=e["response"]["status"],
                    response_headers=e["response"]["headers"],
                    response_body=e["response"]["body"],
                    recorded_at=e["recorded_at"],
                    expires_at=e["expires_at"],
                )
            )
        return cls(
            name=data["name"],
            version=data.get("version", 1),
            entries=entries,
            metadata=data.get("metadata", {}),
        )


def redact_secrets(text: str) -> str:
    """Redact secrets from text."""
    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def get_cassette_path(name: str) -> Path:
    """Get path for a cassette file."""
    return CASSETTES_DIR / f"{name}.json"


def save_cassette(cassette: Cassette) -> Path:
    """Save cassette to disk."""
    path = get_cassette_path(cassette.name)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Redact secrets before saving
    data = cassette.to_dict()
    data_str = json.dumps(data, indent=2)
    data_str = redact_secrets(data_str)
    data = json.loads(data_str)

    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def load_cassette(name: str) -> Cassette | None:
    """Load cassette from disk."""
    path = get_cassette_path(name)
    if not path.exists():
        return None

    data = json.loads(path.read_text())
    return Cassette.from_dict(data)


def generate_request_key(method: str, url: str, body: str | None = None) -> str:
    """Generate a unique key for a request."""
    parsed = urlparse(url)
    key_data = f"{method}:{parsed.path}:{parsed.query}:{body or ''}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


class RecordingSession:
    """Context manager for recording HTTP interactions."""

    def __init__(self, name: str, expiry_days: int = DEFAULT_EXPIRY_DAYS):
        self.name = name
        self.expiry_days = expiry_days
        self.cassette = Cassette(name=name)

    def record(
        self,
        method: str,
        url: str,
        request_headers: dict[str, str],
        request_body: str | None,
        response_status: int,
        response_headers: dict[str, str],
        response_body: str,
    ) -> None:
        """Record an HTTP interaction."""
        now = datetime.utcnow()
        expires = now + timedelta(days=self.expiry_days)

        entry = CassetteEntry(
            request_method=method,
            request_url=url,
            request_headers=request_headers,
            request_body=request_body,
            response_status=response_status,
            response_headers=dict(response_headers),
            response_body=response_body,
            recorded_at=now.isoformat() + "Z",
            expires_at=expires.isoformat() + "Z",
        )
        self.cassette.entries.append(entry)

    def __enter__(self) -> "RecordingSession":
        return self

    def __exit__(self, *args: Any) -> None:
        if self.cassette.entries:
            save_cassette(self.cassette)


class ReplaySession:
    """Context manager for replaying HTTP interactions."""

    def __init__(self, name: str):
        self.name = name
        self.cassette = load_cassette(name)
        self._index = 0

    def match(self, method: str, url: str) -> CassetteEntry | None:
        """Find matching response for a request."""
        if not self.cassette:
            return None

        for entry in self.cassette.entries:
            if entry.request_method == method and self._urls_match(entry.request_url, url):
                # Check expiry
                expires = datetime.fromisoformat(entry.expires_at.rstrip("Z"))
                if datetime.utcnow() > expires:
                    continue  # Expired
                return entry

        return None

    def _urls_match(self, recorded: str, actual: str) -> bool:
        """Check if URLs match (ignoring query param order)."""
        r = urlparse(recorded)
        a = urlparse(actual)
        return r.path == a.path and r.netloc == a.netloc

    def __enter__(self) -> "ReplaySession":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def validate_cassettes() -> list[str]:
    """Validate all cassettes for expiry and schema."""
    issues = []

    for path in CASSETTES_DIR.glob("*.json"):
        try:
            cassette = load_cassette(path.stem)
            if not cassette:
                issues.append(f"{path.name}: Failed to load")
                continue

            # Check for expired entries
            expired_count = 0
            for entry in cassette.entries:
                expires = datetime.fromisoformat(entry.expires_at.rstrip("Z"))
                if datetime.utcnow() > expires:
                    expired_count += 1

            if expired_count > 0:
                issues.append(f"{path.name}: {expired_count} expired entries")

        except (sqlite3.Error, ValueError, OSError, KeyError) as e:
            issues.append(f"{path.name}: {e}")

    return issues
