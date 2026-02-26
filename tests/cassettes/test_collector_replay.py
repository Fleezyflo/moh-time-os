"""
Collector Record/Replay Tests.

Tests that collectors produce consistent output from recorded cassettes.
"""

import json
from pathlib import Path

from lib.collectors.recorder import (
    Cassette,
    CassetteEntry,
    RecordingSession,
    ReplaySession,
    redact_secrets,
    save_cassette,
    validate_cassettes,
)

CASSETTES_DIR = Path(__file__).parent


class TestSecretRedaction:
    """Test secret redaction."""

    def test_redacts_access_token(self):
        text = '{"access_token": "secret123"}'
        result = redact_secrets(text)
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redact_secrets(text)
        assert "eyJ" not in result
        assert "[REDACTED]" in result

    def test_redacts_api_key(self):
        text = '{"api_key": "sk-1234567890abcdef"}'
        result = redact_secrets(text)
        assert "sk-1234567890" not in result


class TestCassette:
    """Test cassette serialization."""

    def test_cassette_roundtrip(self, tmp_path):
        entry = CassetteEntry(
            request_method="GET",
            request_url="https://api.example.com/data",
            request_headers={"Accept": "application/json"},
            request_body=None,
            response_status=200,
            response_headers={"Content-Type": "application/json"},
            response_body='{"data": "test"}',
            recorded_at="2024-01-01T00:00:00Z",
            expires_at="2024-02-01T00:00:00Z",
        )

        cassette = Cassette(name="test", entries=[entry])

        # Serialize and deserialize
        data = cassette.to_dict()
        restored = Cassette.from_dict(data)

        assert restored.name == cassette.name
        assert len(restored.entries) == 1
        assert restored.entries[0].request_url == entry.request_url
        assert restored.entries[0].response_body == entry.response_body


class TestRecordingSession:
    """Test recording sessions."""

    def test_records_interaction(self, tmp_path, monkeypatch):
        # Use temp dir for cassettes
        monkeypatch.setattr("lib.collectors.recorder.CASSETTES_DIR", tmp_path)

        with RecordingSession("test_recording") as session:
            session.record(
                method="GET",
                url="https://api.example.com/users",
                request_headers={"Accept": "application/json"},
                request_body=None,
                response_status=200,
                response_headers={"Content-Type": "application/json"},
                response_body='[{"id": 1, "name": "Test"}]',
            )

        # Verify cassette was saved
        cassette_path = tmp_path / "test_recording.json"
        assert cassette_path.exists()

        data = json.loads(cassette_path.read_text())
        assert data["name"] == "test_recording"
        assert len(data["entries"]) == 1


class TestReplaySession:
    """Test replay sessions."""

    def test_matches_request(self, tmp_path, monkeypatch):
        monkeypatch.setattr("lib.collectors.recorder.CASSETTES_DIR", tmp_path)

        # Create a cassette
        cassette = Cassette(
            name="test_replay",
            entries=[
                CassetteEntry(
                    request_method="GET",
                    request_url="https://api.example.com/users",
                    request_headers={},
                    request_body=None,
                    response_status=200,
                    response_headers={},
                    response_body='[{"id": 1}]',
                    recorded_at="2024-01-01T00:00:00Z",
                    expires_at="2099-01-01T00:00:00Z",  # Far future
                )
            ],
        )
        save_cassette(cassette)

        # Replay
        with ReplaySession("test_replay") as session:
            match = session.match("GET", "https://api.example.com/users")

        assert match is not None
        assert match.response_status == 200
        assert match.response_body == '[{"id": 1}]'

    def test_no_match_for_different_method(self, tmp_path, monkeypatch):
        monkeypatch.setattr("lib.collectors.recorder.CASSETTES_DIR", tmp_path)

        cassette = Cassette(
            name="test_method",
            entries=[
                CassetteEntry(
                    request_method="GET",
                    request_url="https://api.example.com/users",
                    request_headers={},
                    request_body=None,
                    response_status=200,
                    response_headers={},
                    response_body="{}",
                    recorded_at="2024-01-01T00:00:00Z",
                    expires_at="2099-01-01T00:00:00Z",
                )
            ],
        )
        save_cassette(cassette)

        with ReplaySession("test_method") as session:
            match = session.match("POST", "https://api.example.com/users")

        assert match is None


class TestCassetteValidation:
    """Test cassette validation."""

    def test_validate_detects_expired(self, tmp_path, monkeypatch):
        monkeypatch.setattr("lib.collectors.recorder.CASSETTES_DIR", tmp_path)

        # Create expired cassette
        cassette = Cassette(
            name="expired",
            entries=[
                CassetteEntry(
                    request_method="GET",
                    request_url="https://api.example.com/users",
                    request_headers={},
                    request_body=None,
                    response_status=200,
                    response_headers={},
                    response_body="{}",
                    recorded_at="2020-01-01T00:00:00Z",
                    expires_at="2020-02-01T00:00:00Z",  # Past
                )
            ],
        )
        save_cassette(cassette)

        issues = validate_cassettes()
        assert len(issues) == 1
        assert "expired" in issues[0].lower()
