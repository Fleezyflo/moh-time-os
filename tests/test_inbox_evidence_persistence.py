"""
Tests for inbox evidence persistence at write-time.

Ensures that inbox_items_v29 rows have rich drill-down fields persisted
directly in evidence.payload at creation time.
"""

import json
import sqlite3

import pytest


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with required tables."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Create minimal schema
    conn.executescript("""
        CREATE TABLE communications (
            id TEXT PRIMARY KEY,
            source TEXT,
            source_id TEXT,
            thread_id TEXT,
            from_email TEXT,
            subject TEXT,
            snippet TEXT,
            body_text TEXT,
            priority INTEGER DEFAULT 50,
            requires_response INTEGER DEFAULT 0,
            processed INTEGER DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE inbox_items_v29 (
            id TEXT PRIMARY KEY,
            type TEXT,
            state TEXT DEFAULT 'proposed',
            severity TEXT,
            proposed_at TEXT,
            last_refreshed_at TEXT,
            title TEXT,
            evidence TEXT,
            evidence_version TEXT,
            underlying_signal_id TEXT,
            created_at TEXT,
            updated_at TEXT
        );
    """)
    conn.commit()

    yield conn
    conn.close()


class TestDetectorWriteTime:
    """Test that detector writes complete evidence at creation time."""

    def test_flagged_signal_has_complete_payload(self, test_db):
        """New flagged signal should have all payload fields persisted."""
        # Insert a communication
        test_db.execute("""
            INSERT INTO communications (
                id, source, source_id, thread_id, from_email, subject, snippet,
                body_text, priority, processed, created_at
            ) VALUES (
                'gmail_123', 'gmail', '123', '123', 'test@example.com',
                'Test Subject', 'This is a test snippet',
                'This is a much longer body text with more content for testing purposes.',
                80, 0, '2026-02-10T10:00:00Z'
            )
        """)
        test_db.commit()

        # Run the detector
        from lib.ui_spec_v21.detectors import DetectorRunner

        detector = DetectorRunner(test_db)
        detector.run_communications_detector()
        test_db.commit()

        # Check the created inbox item
        cursor = test_db.execute(
            "SELECT evidence FROM inbox_items_v29 WHERE underlying_signal_id = 'gmail_123'"
        )
        row = cursor.fetchone()

        assert row is not None, "Inbox item should be created"

        evidence = json.loads(row["evidence"])
        assert "payload" in evidence, "Evidence should have payload"

        payload = evidence["payload"]
        assert payload["sender"] == "test@example.com"
        assert payload["subject"] == "Test Subject"
        assert "body text" in payload["snippet"].lower(), "Snippet should be derived from body_text"
        assert payload["thread_id"] == "123"
        assert payload["received_at"] == "2026-02-10T10:00:00Z"
        assert "Priority 80" in payload["flagged_reason"]

        # Check URL
        assert evidence["url"] == "https://mail.google.com/mail/u/0/#inbox/123"

    def test_snippet_from_body_text_when_meaningful(self, test_db):
        """When body_text is meaningful, snippet should be derived from it."""
        # Note: snippet must differ from subject to pass has_meaningful_snippet check
        test_db.execute("""
            INSERT INTO communications (
                id, source, source_id, from_email, subject, snippet,
                body_text, priority, processed, created_at
            ) VALUES (
                'gmail_456', 'gmail', '456', 'test@example.com',
                'Subject Line', 'Different snippet content here for checking',
                'This is the actual body content that should be used for the snippet field because it is longer.',
                60, 0, '2026-02-10T11:00:00Z'
            )
        """)
        test_db.commit()

        from lib.ui_spec_v21.detectors import DetectorRunner

        detector = DetectorRunner(test_db)
        detector.run_communications_detector()
        test_db.commit()

        cursor = test_db.execute(
            "SELECT evidence FROM inbox_items_v29 WHERE underlying_signal_id = 'gmail_456'"
        )
        row = cursor.fetchone()
        assert row is not None, "Inbox item should be created"
        evidence = json.loads(row["evidence"])

        # Should use body_text since it's longer and meaningful
        assert "actual body content" in evidence["payload"]["snippet"].lower()

    def test_snippet_from_snippet_when_body_empty(self, test_db):
        """When body_text is empty but snippet != subject, use snippet."""
        test_db.execute("""
            INSERT INTO communications (
                id, source, source_id, from_email, subject, snippet,
                body_text, priority, processed, created_at
            ) VALUES (
                'gmail_789', 'gmail', '789', 'test@example.com',
                'Different Subject', 'This is a meaningful snippet that differs from subject',
                '',  -- empty body
                60, 0, '2026-02-10T12:00:00Z'
            )
        """)
        test_db.commit()

        from lib.ui_spec_v21.detectors import DetectorRunner

        detector = DetectorRunner(test_db)
        detector.run_communications_detector()
        test_db.commit()

        cursor = test_db.execute(
            "SELECT evidence FROM inbox_items_v29 WHERE underlying_signal_id = 'gmail_789'"
        )
        row = cursor.fetchone()
        evidence = json.loads(row["evidence"])

        assert "meaningful snippet" in evidence["payload"]["snippet"].lower()


class TestEnricherSafetyNet:
    """Test that enricher fills in missing fields as safety net."""

    def test_enricher_fills_missing_fields(self, test_db):
        """Enricher should fill in any missing payload fields."""
        # Insert communication
        test_db.execute("""
            INSERT INTO communications (
                id, source, source_id, thread_id, from_email, subject, snippet,
                body_text, priority, created_at
            ) VALUES (
                'gmail_aaa', 'gmail', 'aaa', 'aaa', 'sender@test.com',
                'Enrichment Test', 'Test snippet content here',
                'Body text for enrichment testing with sufficient length.',
                70, '2026-02-10T13:00:00Z'
            )
        """)

        # Insert inbox item with INCOMPLETE evidence (simulating old data)
        incomplete_evidence = json.dumps(
            {
                "source": "gmail",
                "from": "sender@test.com",
                "snippet": "",  # Missing most fields
            }
        )
        test_db.execute(
            """
            INSERT INTO inbox_items_v29 (
                id, type, state, severity, title, evidence,
                underlying_signal_id, created_at, updated_at
            ) VALUES (
                'inbox_gmail_aaa', 'flagged_signal', 'proposed', 'medium',
                'Enrichment Test', ?, 'gmail_aaa',
                '2026-02-10T13:00:00Z', '2026-02-10T13:00:00Z'
            )
        """,
            (incomplete_evidence,),
        )
        test_db.commit()

        # Run enricher
        from lib.ui_spec_v21.inbox_enricher import enrich_inbox_item

        enrich_inbox_item(test_db, "inbox_gmail_aaa", use_llm=False)
        test_db.commit()

        # Check result
        cursor = test_db.execute(
            "SELECT evidence FROM inbox_items_v29 WHERE id = 'inbox_gmail_aaa'"
        )
        row = cursor.fetchone()
        evidence = json.loads(row["evidence"])

        # All core fields should now be present
        assert evidence["payload"]["sender"] == "sender@test.com"
        assert evidence["payload"]["subject"] == "Enrichment Test"
        assert len(evidence["payload"]["snippet"]) > 0
        assert evidence["payload"]["thread_id"] == "aaa"
        assert evidence["url"] == "https://mail.google.com/mail/u/0/#inbox/aaa"


class TestMalformedJsonHandling:
    """Test that malformed JSON is handled with proper error reporting."""

    def test_malformed_evidence_reports_error(self, test_db):
        """Malformed evidence JSON should report error in meta.trust."""
        # Insert communication
        test_db.execute("""
            INSERT INTO communications (
                id, source, source_id, from_email, subject, snippet, priority, created_at
            ) VALUES (
                'gmail_bad', 'gmail', 'bad', 'test@test.com',
                'Bad JSON Test', 'Snippet', 50, '2026-02-10T14:00:00Z'
            )
        """)

        # Insert inbox item with MALFORMED evidence
        test_db.execute("""
            INSERT INTO inbox_items_v29 (
                id, type, state, severity, title, evidence,
                underlying_signal_id, created_at, updated_at
            ) VALUES (
                'inbox_gmail_bad', 'flagged_signal', 'proposed', 'low',
                'Bad JSON Test', '{invalid json here',
                'gmail_bad', '2026-02-10T14:00:00Z', '2026-02-10T14:00:00Z'
            )
        """)
        test_db.commit()

        # Run enricher
        from lib.ui_spec_v21.inbox_enricher import enrich_inbox_item

        enrich_inbox_item(test_db, "inbox_gmail_bad", use_llm=False)
        test_db.commit()

        # Check result
        cursor = test_db.execute(
            "SELECT evidence FROM inbox_items_v29 WHERE id = 'inbox_gmail_bad'"
        )
        row = cursor.fetchone()
        evidence = json.loads(row["evidence"])

        # Should have meta.trust with error info
        assert "meta" in evidence
        assert evidence["meta"]["trust"]["data_integrity"] is False
        assert len(evidence["meta"]["trust"]["errors"]) > 0
        assert "parse" in evidence["meta"]["trust"]["errors"][0].lower()


class TestEndpointsSafeParseEvidence:
    """Test safe_parse_evidence in endpoints.py."""

    def test_safe_parse_valid_json(self):
        """Valid JSON should parse normally."""
        from lib.ui_spec_v21.endpoints import safe_parse_evidence

        result = safe_parse_evidence('{"payload": {"sender": "test@test.com"}}', "test_id")
        assert result["payload"]["sender"] == "test@test.com"
        assert "meta" not in result or result.get("meta", {}).get("trust", {}).get(
            "data_integrity", True
        )

    def test_safe_parse_malformed_json(self):
        """Malformed JSON should return trust failure structure."""
        from lib.ui_spec_v21.endpoints import safe_parse_evidence

        result = safe_parse_evidence("{invalid json here", "test_id_123")

        # Should have meta.trust with data_integrity=False
        assert "meta" in result
        assert result["meta"]["trust"]["data_integrity"] is False
        assert len(result["meta"]["trust"]["errors"]) > 0
        assert "parse failed" in result["meta"]["trust"]["errors"][0].lower()

        # Should have debug info
        assert "debug" in result["meta"]["trust"]
        assert result["meta"]["trust"]["debug"]["raw_length"] == len("{invalid json here")

    def test_safe_parse_empty_string(self):
        """Empty string should return empty dict."""
        from lib.ui_spec_v21.endpoints import safe_parse_evidence

        result = safe_parse_evidence("", "test_id")
        assert result == {}

    def test_safe_parse_none(self):
        """None should return empty dict."""
        from lib.ui_spec_v21.endpoints import safe_parse_evidence

        result = safe_parse_evidence(None, "test_id")
        assert result == {}


class TestBackfillScript:
    """Test the backfill script functionality."""

    def test_backfill_updates_missing_fields(self, test_db):
        """Backfill should update rows with missing payload fields."""
        # Insert communication
        test_db.execute("""
            INSERT INTO communications (
                id, source, source_id, thread_id, from_email, subject, snippet,
                body_text, priority, created_at
            ) VALUES (
                'gmail_fill', 'gmail', 'fill', 'fill', 'backfill@test.com',
                'Backfill Subject', 'Backfill snippet',
                'Backfill body text content.',
                60, '2026-02-10T15:00:00Z'
            )
        """)

        # Insert inbox item missing payload fields
        incomplete_evidence = json.dumps({"source": "gmail"})
        test_db.execute(
            """
            INSERT INTO inbox_items_v29 (
                id, type, state, title, evidence, underlying_signal_id, created_at
            ) VALUES (
                'inbox_gmail_fill', 'flagged_signal', 'proposed',
                'Backfill Subject', ?, 'gmail_fill', '2026-02-10T15:00:00Z'
            )
        """,
            (incomplete_evidence,),
        )
        test_db.commit()

        # Run backfill
        from scripts.backfill_inbox_evidence import backfill_inbox_items

        stats = backfill_inbox_items(test_db, dry_run=False)
        test_db.commit()

        assert stats["updated"] >= 1

        # Verify fields were populated
        cursor = test_db.execute(
            "SELECT evidence FROM inbox_items_v29 WHERE id = 'inbox_gmail_fill'"
        )
        row = cursor.fetchone()
        evidence = json.loads(row["evidence"])

        assert evidence["payload"]["sender"] == "backfill@test.com"
        assert evidence["payload"]["subject"] == "Backfill Subject"
        assert evidence["url"] == "https://mail.google.com/mail/u/0/#inbox/fill"
        assert "backfilled_at" in evidence.get("meta", {})
