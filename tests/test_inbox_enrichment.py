"""
Tests for inbox drill-down enrichment.

Regression test to ensure inbox items include drill-down context:
- entities: Extracted people, organizations, projects, dates
- rationale: Why this item needs attention
- suggested_actions: Possible actions the user can take
- thread_context: Summary of thread history and status

Per AGENTS.md: "given a comm/email fixture, generated inbox item must include
non-empty drill-down fields"
"""

import json
import sqlite3
from pathlib import Path
from unittest import TestCase

# Add project root to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestInboxEnrichment(TestCase):
    """Tests for inbox item drill-down enrichment."""

    @classmethod
    def setUpClass(cls):
        """Create in-memory database with test fixtures."""
        cls.conn = sqlite3.connect(":memory:")
        cls.conn.row_factory = sqlite3.Row

        # Create required tables
        cls.conn.executescript("""
            -- Communications table
            CREATE TABLE IF NOT EXISTS communications (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_id TEXT,
                thread_id TEXT,
                from_email TEXT,
                to_emails TEXT,
                subject TEXT,
                snippet TEXT,
                body_text TEXT,
                priority INTEGER DEFAULT 50,
                requires_response INTEGER DEFAULT 0,
                response_deadline TEXT,
                sentiment TEXT,
                labels TEXT,
                processed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                received_at TEXT
            );

            -- Inbox items table (v29)
            CREATE TABLE IF NOT EXISTS inbox_items_v29 (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'proposed',
                severity TEXT NOT NULL,
                proposed_at TEXT NOT NULL,
                last_refreshed_at TEXT NOT NULL,
                read_at TEXT,
                resurfaced_at TEXT,
                resolved_at TEXT,
                snooze_until TEXT,
                snoozed_by TEXT,
                snoozed_at TEXT,
                snooze_reason TEXT,
                dismissed_by TEXT,
                dismissed_at TEXT,
                dismiss_reason TEXT,
                suppression_key TEXT,
                underlying_issue_id TEXT,
                underlying_signal_id TEXT,
                resolved_issue_id TEXT,
                title TEXT NOT NULL,
                client_id TEXT,
                brand_id TEXT,
                engagement_id TEXT,
                evidence TEXT,
                evidence_version TEXT DEFAULT 'v1',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Insert test communication fixture
        cls.conn.execute("""
            INSERT INTO communications (
                id, source, source_id, thread_id, from_email, subject, snippet,
                body_text, priority, requires_response, created_at, received_at
            ) VALUES (
                'comm_test_001',
                'gmail',
                'gmail_123',
                'thread_abc',
                'john.smith@acme.com',
                'URGENT: Q1 Report due by Friday',
                'Hi team, please review the attached Q1 report...',
                'Hi team,

Please review the attached Q1 report by this Friday (Feb 14).

Key points:
- Revenue increased 15%
- New client Globex signed
- Meeting scheduled with Sarah on Monday

Let me know if you have questions.

Best,
John Smith
VP Operations
Acme Corp',
                90,
                1,
                datetime('now'),
                datetime('now')
            )
        """)

        # Insert inbox item for the communication
        cls.conn.execute("""
            INSERT INTO inbox_items_v29 (
                id, type, state, severity, proposed_at, last_refreshed_at,
                title, evidence, evidence_version, underlying_signal_id,
                created_at, updated_at
            ) VALUES (
                'inbox_test_001',
                'flagged_signal',
                'proposed',
                'high',
                datetime('now'),
                datetime('now'),
                'URGENT: Q1 Report due by Friday',
                '{"source": "gmail", "from": "john.smith@acme.com"}',
                'v1',
                'comm_test_001',
                datetime('now'),
                datetime('now')
            )
        """)
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_heuristic_enrichment_populates_drill_down_fields(self):
        """
        Heuristic enrichment should populate all drill-down fields.

        Tests: enrich_from_heuristics() produces non-empty drill-down context.
        """
        from lib.ui_spec_v21.inbox_enricher import enrich_from_heuristics

        enrichment = enrich_from_heuristics(
            sender="john.smith@acme.com",
            subject="URGENT: Q1 Report due by Friday",
            body="Hi team, please review the attached Q1 report by Friday. Let me know if you have questions.",
            priority=90,
            requires_response=True,
        )

        # Verify all drill-down fields are populated
        self.assertIn("entities", enrichment)
        self.assertIn("rationale", enrichment)
        self.assertIn("suggested_actions", enrichment)
        self.assertIn("thread_context", enrichment)

        # Rationale should be non-empty for high priority email
        self.assertIsNotNone(enrichment["rationale"])
        self.assertIn("High priority", enrichment["rationale"])

        # Suggested actions should be non-empty
        self.assertIsInstance(enrichment["suggested_actions"], list)
        self.assertGreater(len(enrichment["suggested_actions"]), 0)

        # Thread context should be non-empty
        self.assertIsNotNone(enrichment["thread_context"])

    def test_enrich_inbox_item_updates_evidence(self):
        """
        enrich_inbox_item() should update the evidence JSON with drill-down fields.

        This is the integration test for the enrichment pipeline.
        """
        from lib.ui_spec_v21.inbox_enricher import enrich_inbox_item

        # Run enrichment (without LLM)
        result = enrich_inbox_item(self.conn, "inbox_test_001", use_llm=False)
        self.conn.commit()

        # Verify enrichment was applied
        self.assertIn("rationale", result)
        self.assertIn("suggested_actions", result)

        # Check the stored evidence
        cursor = self.conn.execute(
            "SELECT evidence FROM inbox_items_v29 WHERE id = ?",
            ("inbox_test_001",),
        )
        row = cursor.fetchone()
        evidence = json.loads(row[0])

        # Verify drill-down fields are in the stored evidence
        payload = evidence.get("payload", {})
        self.assertIn("rationale", payload)
        self.assertIn("suggested_actions", payload)
        self.assertIn("thread_context", payload)
        self.assertIn("enriched_at", payload)

        # Rationale should reflect the urgent nature
        self.assertIn("urgent", payload["rationale"].lower())

    def test_evidence_enrichment_at_api_response_preserves_drill_down(self):
        """
        _enrich_evidence() in endpoints should preserve stored drill-down fields.

        Tests: API response includes drill-down context from stored evidence.
        """
        from lib.ui_spec_v21.endpoints import InboxEndpoints

        # First, ensure the item is enriched
        from lib.ui_spec_v21.inbox_enricher import enrich_inbox_item

        enrich_inbox_item(self.conn, "inbox_test_001", use_llm=False)
        self.conn.commit()

        # Now test the API endpoint's evidence enrichment
        endpoints = InboxEndpoints(self.conn)

        # Get the stored evidence
        cursor = self.conn.execute(
            "SELECT evidence FROM inbox_items_v29 WHERE id = ?",
            ("inbox_test_001",),
        )
        row = cursor.fetchone()
        stored_evidence = json.loads(row[0])

        # Call _enrich_evidence (simulating API response)
        enriched = endpoints._enrich_evidence(
            evidence=stored_evidence,
            item_type="flagged_signal",
            signal_id="comm_test_001",
            title="URGENT: Q1 Report due by Friday",
        )

        # Verify drill-down fields are preserved in the API response
        payload = enriched.get("payload", {})
        self.assertIn("rationale", payload)
        self.assertIn("suggested_actions", payload)
        self.assertIn("thread_context", payload)
        self.assertIsNotNone(payload.get("rationale"))

    def test_entity_extraction_from_body_text(self):
        """
        Heuristic enrichment should extract entities from body text.

        Tests: Dates, email addresses, and other entities are extracted.
        """
        from lib.ui_spec_v21.inbox_enricher import enrich_from_heuristics

        enrichment = enrich_from_heuristics(
            sender="john@example.com",
            subject="Meeting on Friday",
            body="Hi Sarah, let's meet on Friday to discuss the project. CC: mike@acme.com",
            priority=50,
            requires_response=False,
        )

        entities = enrichment.get("entities", [])

        # Should extract at least one entity
        self.assertIsInstance(entities, list)
        # Should find email addresses
        entity_values = [e.get("value") for e in entities]
        self.assertTrue(any("mike@acme.com" in str(v) for v in entity_values))


class TestDrillDownRegressionPrevention(TestCase):
    """
    Regression test: Inbox items must include drill-down fields.

    This test ensures the enrichment pipeline is wired correctly and
    drill-down context is never silently dropped.
    """

    def test_inbox_response_includes_drill_down_fields(self):
        """
        GET /api/inbox response must include drill-down fields for enriched items.

        This is the canonical regression test per the bug report.
        """
        conn = sqlite3.connect(":memory:")
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
                priority INTEGER,
                requires_response INTEGER,
                created_at TEXT,
                received_at TEXT
            );

            CREATE TABLE inbox_items_v29 (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'proposed',
                severity TEXT NOT NULL,
                proposed_at TEXT NOT NULL,
                last_refreshed_at TEXT NOT NULL,
                read_at TEXT,
                resurfaced_at TEXT,
                resolved_at TEXT,
                snooze_until TEXT,
                snoozed_by TEXT,
                snoozed_at TEXT,
                snooze_reason TEXT,
                dismissed_by TEXT,
                dismissed_at TEXT,
                dismiss_reason TEXT,
                suppression_key TEXT,
                underlying_issue_id TEXT,
                underlying_signal_id TEXT,
                resolved_issue_id TEXT,
                title TEXT NOT NULL,
                client_id TEXT,
                brand_id TEXT,
                engagement_id TEXT,
                evidence TEXT,
                evidence_version TEXT DEFAULT 'v1',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE clients (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE issues_v29 (
                id TEXT PRIMARY KEY,
                type TEXT,
                state TEXT,
                severity TEXT,
                assigned_to TEXT
            );

            CREATE TABLE team_members (
                id TEXT PRIMARY KEY,
                name TEXT
            );
        """)

        # Insert test data with pre-enriched evidence
        enriched_evidence = json.dumps(
            {
                "source": "gmail",
                "payload": {
                    "entities": [{"type": "date", "value": "Friday"}],
                    "rationale": "Urgent client request requiring immediate response.",
                    "suggested_actions": ["Reply to confirm receipt", "Check calendar"],
                    "thread_context": "New conversation from known client.",
                    "enriched_at": "2026-02-10T12:00:00Z",
                },
            }
        )

        conn.execute("""
            INSERT INTO communications (id, source, from_email, subject, body_text, priority, created_at)
            VALUES ('comm_1', 'gmail', 'client@example.com', 'Urgent Request', 'Please respond ASAP', 95, datetime('now'))
        """)

        conn.execute(
            """
            INSERT INTO inbox_items_v29 (
                id, type, state, severity, proposed_at, last_refreshed_at,
                title, underlying_signal_id, evidence, created_at, updated_at
            ) VALUES (
                'inbox_1', 'flagged_signal', 'proposed', 'high',
                datetime('now'), datetime('now'),
                'Urgent Request', 'comm_1', ?, datetime('now'), datetime('now')
            )
        """,
            (enriched_evidence,),
        )
        conn.commit()

        # Call the inbox endpoint
        from lib.ui_spec_v21.endpoints import InboxEndpoints

        endpoints = InboxEndpoints(conn)
        response = endpoints.get_inbox()

        # Verify response structure
        self.assertIn("items", response)
        self.assertGreater(len(response["items"]), 0)

        # Verify drill-down fields are present in the response
        item = response["items"][0]
        evidence = item.get("evidence", {})
        payload = evidence.get("payload", {})

        # REGRESSION CHECK: These fields must be present and non-empty
        self.assertIn("rationale", payload, "Missing rationale in API response")
        self.assertIn(
            "suggested_actions", payload, "Missing suggested_actions in API response"
        )
        self.assertIn("entities", payload, "Missing entities in API response")
        self.assertIn(
            "thread_context", payload, "Missing thread_context in API response"
        )

        # Verify values are not None/empty
        self.assertIsNotNone(payload["rationale"], "rationale is None")
        self.assertIsInstance(
            payload["suggested_actions"], list, "suggested_actions is not a list"
        )
        self.assertGreater(
            len(payload["suggested_actions"]), 0, "suggested_actions is empty"
        )

        conn.close()


if __name__ == "__main__":
    import unittest

    unittest.main()
