"""
Safety + Provenance + Parity Tests

Part 5 of the safety implementation.
These tests prevent regressions and ensure the safety system is working.
"""

import os
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path
from unittest import TestCase, main

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.safety import WriteContext, generate_request_id, run_safety_migrations
from lib.safety.audit import query_who_changed
from lib.safety.schema import SchemaAssertion, assert_no_legacy_writes


def create_test_db() -> tuple[sqlite3.Connection, Path]:
    """Create a fresh test database with all migrations."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    # Create base tables (inbox_items_v29, issues_v29, etc.)
    conn.executescript("""
        -- Core tables
        CREATE TABLE IF NOT EXISTS inbox_items_v29 (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'proposed',
            severity TEXT DEFAULT 'medium',
            proposed_at TEXT NOT NULL,
            read_at TEXT,
            read_by TEXT,
            dismissed_at TEXT,
            dismissed_by TEXT,
            suppression_key TEXT,
            resolved_at TEXT,
            resolved_issue_id TEXT,
            snooze_until TEXT,
            snoozed_by TEXT,
            assigned_to TEXT,
            client_id TEXT,
            signal_id TEXT,
            engagement_id TEXT,
            payload_json TEXT,
            note TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_state ON inbox_items_v29(state);
        CREATE INDEX IF NOT EXISTS idx_inbox_items_v29_type ON inbox_items_v29(type);

        CREATE TABLE IF NOT EXISTS issues_v29 (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            type TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'open',
            severity TEXT DEFAULT 'medium',
            created_at TEXT NOT NULL,
            assigned_to TEXT,
            snooze_until TEXT,
            closed_at TEXT,
            payload_json TEXT
        );

        CREATE TABLE IF NOT EXISTS issue_transitions_v29 (
            id TEXT PRIMARY KEY,
            issue_id TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            at TEXT NOT NULL,
            note TEXT,
            FOREIGN KEY (issue_id) REFERENCES issues_v29(id)
        );

        CREATE TABLE IF NOT EXISTS inbox_suppression_rules_v29 (
            id TEXT PRIMARY KEY,
            suppression_key TEXT NOT NULL UNIQUE,
            item_type TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            reason TEXT
        );

        CREATE TABLE IF NOT EXISTS signals_v29 (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            type TEXT NOT NULL,
            source TEXT,
            sentiment TEXT,
            state TEXT NOT NULL DEFAULT 'active',
            occurred_at TEXT NOT NULL,
            payload_json TEXT
        );
    """)

    # Run safety migrations
    run_safety_migrations(conn, verbose=False)

    return conn, Path(path)


class TestSchemaParity(TestCase):
    """Part 5.1: Schema parity tests."""

    def setUp(self):
        self.conn, self.db_path = create_test_db()

    def tearDown(self):
        self.conn.close()
        self.db_path.unlink(missing_ok=True)

    def test_required_tables_exist(self):
        """Assert required tables exist."""
        assertion = SchemaAssertion(self.conn)
        violations = assertion.assert_tables_exist()
        self.assertEqual(violations, [], f"Missing tables: {violations}")

    def test_required_triggers_exist(self):
        """Assert required triggers exist."""
        assertion = SchemaAssertion(self.conn)
        violations = assertion.assert_triggers_exist()
        self.assertEqual(violations, [], f"Missing triggers: {violations}")

    def test_required_columns_exist(self):
        """Assert required columns exist."""
        assertion = SchemaAssertion(self.conn)
        violations = assertion.assert_columns_exist()
        self.assertEqual(violations, [], f"Missing columns: {violations}")

    def test_required_indexes_exist(self):
        """Assert required indexes exist."""
        assertion = SchemaAssertion(self.conn)
        violations = assertion.assert_indexes_exist()
        # This may fail for test DB - that's OK, we just need the safety indexes
        # Filter to only safety-required indexes
        safety_violations = [v for v in violations if "audit" in v.name.lower()]
        self.assertEqual(
            safety_violations, [], f"Missing safety indexes: {safety_violations}"
        )

    def test_inbox_items_is_view_or_absent(self):
        """Assert legacy inbox_items is VIEW (not writable table)."""
        assertion = SchemaAssertion(self.conn)
        # In test DB, inbox_items doesn't exist - that's fine
        violations = assertion.assert_inbox_items_is_view()
        self.assertEqual(violations, [], f"Legacy inbox_items issues: {violations}")

    def test_no_legacy_writes_in_codebase(self):
        """Assert no code writes to legacy inbox_items table."""
        violations = assert_no_legacy_writes(str(PROJECT_ROOT))
        self.assertEqual(violations, [], f"Found legacy writes: {violations}")


class TestDBInvariants(TestCase):
    """Part 5.4: DB-level invariant tests."""

    def setUp(self):
        self.conn, self.db_path = create_test_db()

    def tearDown(self):
        self.conn.close()
        self.db_path.unlink(missing_ok=True)

    def test_terminal_state_requires_resolved_at(self):
        """State=dismissed without resolved_at must ABORT."""
        item_id = str(uuid.uuid4())

        # Insert a proposed item
        with WriteContext(self.conn, actor="test", source="test"):
            self.conn.execute(
                """
                INSERT INTO inbox_items_v29 (id, type, state, proposed_at)
                VALUES (?, 'issue', 'proposed', datetime('now'))
            """,
                (item_id,),
            )
            self.conn.commit()

        # Try to set dismissed without resolved_at
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            with WriteContext(self.conn, actor="test", source="test"):
                self.conn.execute(
                    """
                    UPDATE inbox_items_v29
                    SET state = 'dismissed',
                        dismissed_at = datetime('now'),
                        dismissed_by = 'test',
                        suppression_key = 'test-key'
                    WHERE id = ?
                """,
                    (item_id,),
                )

        self.assertIn("SAFETY", str(ctx.exception))

    def test_dismissed_requires_audit_fields(self):
        """State=dismissed without dismissed_by must ABORT."""
        item_id = str(uuid.uuid4())

        with WriteContext(self.conn, actor="test", source="test"):
            self.conn.execute(
                """
                INSERT INTO inbox_items_v29 (id, type, state, proposed_at)
                VALUES (?, 'issue', 'proposed', datetime('now'))
            """,
                (item_id,),
            )
            self.conn.commit()

        # Try to set dismissed without dismissed_by
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            with WriteContext(self.conn, actor="test", source="test"):
                self.conn.execute(
                    """
                    UPDATE inbox_items_v29
                    SET state = 'dismissed',
                        dismissed_at = datetime('now'),
                        resolved_at = datetime('now'),
                        suppression_key = 'test-key'
                    WHERE id = ?
                """,
                    (item_id,),
                )

        self.assertIn("SAFETY", str(ctx.exception))

    def test_linked_requires_issue_id(self):
        """State=linked_to_issue without resolved_issue_id must ABORT."""
        item_id = str(uuid.uuid4())

        with WriteContext(self.conn, actor="test", source="test"):
            self.conn.execute(
                """
                INSERT INTO inbox_items_v29 (id, type, state, proposed_at)
                VALUES (?, 'issue', 'proposed', datetime('now'))
            """,
                (item_id,),
            )
            self.conn.commit()

        # Try to set linked_to_issue without resolved_issue_id
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            with WriteContext(self.conn, actor="test", source="test"):
                self.conn.execute(
                    """
                    UPDATE inbox_items_v29
                    SET state = 'linked_to_issue',
                        resolved_at = datetime('now')
                    WHERE id = ?
                """,
                    (item_id,),
                )

        self.assertIn("SAFETY", str(ctx.exception))

    def test_write_without_context_aborts(self):
        """Direct SQL write without context must ABORT."""
        item_id = str(uuid.uuid4())

        # First insert with context
        with WriteContext(self.conn, actor="test", source="test"):
            self.conn.execute(
                """
                INSERT INTO inbox_items_v29 (id, type, state, proposed_at)
                VALUES (?, 'issue', 'proposed', datetime('now'))
            """,
                (item_id,),
            )
            self.conn.commit()

        # Clear context explicitly
        self.conn.execute("DELETE FROM write_context_v1")
        self.conn.commit()

        # Try direct write without context
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            self.conn.execute(
                """
                UPDATE inbox_items_v29 SET note = 'test' WHERE id = ?
            """,
                (item_id,),
            )

        self.assertIn("SAFETY", str(ctx.exception))


class TestAuditLogging(TestCase):
    """Part 5.3: Audit logging tests."""

    def setUp(self):
        self.conn, self.db_path = create_test_db()

    def tearDown(self):
        self.conn.close()
        self.db_path.unlink(missing_ok=True)

    def test_insert_creates_audit_entry(self):
        """INSERT creates audit entry with actor/request_id."""
        item_id = str(uuid.uuid4())
        request_id = generate_request_id()

        with WriteContext(
            self.conn, actor="test-user", source="test", request_id=request_id
        ):
            self.conn.execute(
                """
                INSERT INTO inbox_items_v29 (id, type, state, proposed_at)
                VALUES (?, 'issue', 'proposed', datetime('now'))
            """,
                (item_id,),
            )
            self.conn.commit()

        # Check audit entry
        cursor = self.conn.execute(
            """
            SELECT actor, request_id, source, op, table_name, row_id
            FROM db_write_audit_v1
            WHERE row_id = ?
        """,
            (item_id,),
        )
        row = cursor.fetchone()

        self.assertIsNotNone(row, "No audit entry created")
        self.assertEqual(row["actor"], "test-user")
        self.assertEqual(row["request_id"], request_id)
        self.assertEqual(row["source"], "test")
        self.assertEqual(row["op"], "INSERT")
        self.assertEqual(row["table_name"], "inbox_items_v29")

    def test_update_creates_audit_entry(self):
        """UPDATE creates audit entry with before/after."""
        item_id = str(uuid.uuid4())

        with WriteContext(self.conn, actor="creator", source="test"):
            self.conn.execute(
                """
                INSERT INTO inbox_items_v29 (id, type, state, proposed_at)
                VALUES (?, 'issue', 'proposed', datetime('now'))
            """,
                (item_id,),
            )
            self.conn.commit()

        with WriteContext(self.conn, actor="updater", source="test"):
            self.conn.execute(
                """
                UPDATE inbox_items_v29 SET note = 'updated' WHERE id = ?
            """,
                (item_id,),
            )
            self.conn.commit()

        # Check UPDATE audit entry
        cursor = self.conn.execute(
            """
            SELECT actor, op, before_json, after_json
            FROM db_write_audit_v1
            WHERE row_id = ? AND op = 'UPDATE'
        """,
            (item_id,),
        )
        row = cursor.fetchone()

        self.assertIsNotNone(row, "No UPDATE audit entry created")
        self.assertEqual(row["actor"], "updater")
        self.assertIsNotNone(row["before_json"])
        self.assertIsNotNone(row["after_json"])

    def test_query_who_changed(self):
        """Query audit trail for a row."""
        item_id = str(uuid.uuid4())

        with WriteContext(self.conn, actor="alice", source="api"):
            self.conn.execute(
                """
                INSERT INTO inbox_items_v29 (id, type, state, proposed_at)
                VALUES (?, 'issue', 'proposed', datetime('now'))
            """,
                (item_id,),
            )
            self.conn.commit()

        with WriteContext(self.conn, actor="bob", source="tooling"):
            self.conn.execute(
                """
                UPDATE inbox_items_v29 SET note = 'updated' WHERE id = ?
            """,
                (item_id,),
            )
            self.conn.commit()

        trail = query_who_changed(self.conn, "inbox_items_v29", item_id)

        self.assertIn("alice", trail)
        self.assertIn("bob", trail)
        self.assertIn("INSERT", trail)
        self.assertIn("UPDATE", trail)


class TestWriteContext(TestCase):
    """Test write context management."""

    def setUp(self):
        self.conn, self.db_path = create_test_db()

    def tearDown(self):
        self.conn.close()
        self.db_path.unlink(missing_ok=True)

    def test_context_is_set_and_cleared(self):
        """WriteContext sets and clears context."""
        from lib.safety import get_write_context

        # Before context
        ctx = get_write_context(self.conn)
        self.assertIsNone(ctx)

        # During context
        with WriteContext(self.conn, actor="test", source="unit-test") as ctx_data:
            ctx = get_write_context(self.conn)
            self.assertIsNotNone(ctx)
            self.assertEqual(ctx.actor, "test")
            self.assertEqual(ctx.source, "unit-test")

        # After context
        ctx = get_write_context(self.conn)
        self.assertIsNone(ctx)

    def test_context_requires_actor(self):
        """WriteContext requires actor."""
        with self.assertRaises(ValueError), WriteContext(
            self.conn, actor="", source="test"
        ):
            pass

    def test_context_requires_source(self):
        """WriteContext requires source."""
        with self.assertRaises(ValueError), WriteContext(
            self.conn, actor="test", source=""
        ):
            pass


class TestSuppressionIdempotency(TestCase):
    """Part 4: Dismiss idempotency tests."""

    def setUp(self):
        self.conn, self.db_path = create_test_db()

    def tearDown(self):
        self.conn.close()
        self.db_path.unlink(missing_ok=True)

    def test_suppression_rule_is_idempotent(self):
        """Creating same suppression rule twice returns existing ID."""
        from lib.ui_spec_v21.suppression import insert_suppression_rule

        suppression_key = f"test-key-{uuid.uuid4()}"

        with WriteContext(self.conn, actor="test", source="test"):
            # First insert
            rule_id_1 = insert_suppression_rule(
                self.conn,
                suppression_key=suppression_key,
                item_type="issue",
                created_by="test",
                reason="test",
            )
            self.conn.commit()

        with WriteContext(self.conn, actor="test", source="test"):
            # Second insert (should return existing)
            rule_id_2 = insert_suppression_rule(
                self.conn,
                suppression_key=suppression_key,
                item_type="issue",
                created_by="test",
                reason="test",
            )
            self.conn.commit()

        # Should return same ID
        self.assertEqual(rule_id_1, rule_id_2)

        # Should only have one row
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM inbox_suppression_rules_v29 WHERE suppression_key = ?",
            (suppression_key,),
        )
        self.assertEqual(cursor.fetchone()[0], 1)


class TestEvidenceEnrichment(TestCase):
    """Tests for evidence enrichment in inbox endpoints (body_text regression prevention)."""

    def setUp(self):
        """Set up test database with communications data."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row

        # Create minimal schema for testing
        self.conn.execute("""
            CREATE TABLE communications (
                id TEXT PRIMARY KEY,
                source TEXT,
                source_id TEXT,
                thread_id TEXT,
                from_email TEXT,
                subject TEXT,
                snippet TEXT,
                body_text TEXT,
                received_at TEXT,
                created_at TEXT,
                priority INTEGER,
                requires_response INTEGER
            )
        """)

        # Insert test data: email with body_text different from subject
        self.conn.execute("""
            INSERT INTO communications (
                id, source, source_id, thread_id, from_email, subject, snippet,
                body_text, received_at, created_at, priority, requires_response
            ) VALUES (
                'test_signal_1', 'gmail', 'abc123', 'thread123', 'sender@example.com',
                'Test Subject Line',
                'Test Subject Line',
                'This is the full body text with actual content that differs from the subject.',
                '2026-01-01T10:00:00Z', '2026-01-01T10:00:00Z', 95, 0
            )
        """)

        # Insert test data: email with only snippet (no body_text)
        self.conn.execute("""
            INSERT INTO communications (
                id, source, source_id, thread_id, from_email, subject, snippet,
                body_text, received_at, created_at, priority, requires_response
            ) VALUES (
                'test_signal_2', 'gmail', 'xyz789', 'thread789', 'other@example.com',
                'Another Subject',
                'This snippet has different content from the subject line.',
                NULL,
                '2026-01-01T11:00:00Z', '2026-01-01T11:00:00Z', 80, 0
            )
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_enrich_evidence_uses_body_text_when_snippet_equals_subject(self):
        """Evidence enrichment should use body_text when snippet == subject."""
        from lib.ui_spec_v21.endpoints import InboxEndpoints

        endpoints = InboxEndpoints(self.conn)

        # Test with signal that has body_text
        evidence = endpoints._enrich_evidence(
            evidence={"source": "gmail"},
            item_type="flagged_signal",
            signal_id="test_signal_1",
            title="Test Subject Line",
        )

        # Should have rich content from body_text
        self.assertEqual(evidence["version"], "v1")
        self.assertEqual(evidence["payload"]["sender"], "sender@example.com")
        self.assertIsNotNone(evidence["payload"]["snippet"])
        self.assertIn("actual content", evidence["payload"]["snippet"])
        self.assertEqual(
            evidence["payload"]["flagged_reason"],
            "High priority email requiring attention",
        )
        self.assertIn("thread123", evidence["url"])

    def test_enrich_evidence_falls_back_to_snippet(self):
        """Evidence enrichment should use snippet when body_text is empty."""
        from lib.ui_spec_v21.endpoints import InboxEndpoints

        endpoints = InboxEndpoints(self.conn)

        # Test with signal that only has snippet (no body_text)
        evidence = endpoints._enrich_evidence(
            evidence={"source": "gmail"},
            item_type="flagged_signal",
            signal_id="test_signal_2",
            title="Another Subject",
        )

        # Should have content from snippet
        self.assertEqual(evidence["version"], "v1")
        self.assertEqual(evidence["payload"]["sender"], "other@example.com")
        self.assertIsNotNone(evidence["payload"]["snippet"])
        self.assertIn("different content", evidence["payload"]["snippet"])

    def test_enrich_evidence_prefers_body_text_over_snippet(self):
        """When both body_text and snippet exist, body_text should be preferred."""
        from lib.ui_spec_v21.endpoints import InboxEndpoints

        # Insert email with BOTH body_text and different snippet
        self.conn.execute("""
            INSERT INTO communications (
                id, source, source_id, thread_id, from_email, subject, snippet,
                body_text, received_at, created_at, priority, requires_response
            ) VALUES (
                'test_signal_3', 'gmail', 'both123', 'thread_both', 'both@example.com',
                'Subject Line',
                'This is the snippet content that is different.',
                'This is the body text which is even richer and more detailed.',
                '2026-01-01T12:00:00Z', '2026-01-01T12:00:00Z', 90, 0
            )
        """)
        self.conn.commit()

        endpoints = InboxEndpoints(self.conn)

        evidence = endpoints._enrich_evidence(
            evidence={"source": "gmail"},
            item_type="flagged_signal",
            signal_id="test_signal_3",
            title="Subject Line",
        )

        # Should prefer body_text content
        self.assertIsNotNone(evidence["payload"]["snippet"])
        self.assertIn("richer and more detailed", evidence["payload"]["snippet"])


class TestSafeJsonParsing(TestCase):
    """Tests for safe JSON parsing with trust tracking."""

    def test_safe_json_loads_success(self):
        """Valid JSON should parse successfully."""
        from lib.safety import safe_json_loads

        result = safe_json_loads('{"key": "value"}', default={}, item_id="test1")
        self.assertTrue(result.success)
        self.assertEqual(result.value, {"key": "value"})
        self.assertIsNone(result.error)

    def test_safe_json_loads_malformed_json(self):
        """Malformed JSON should return default with error."""
        from lib.safety import safe_json_loads

        result = safe_json_loads(
            "{malformed json}", default={}, item_id="test2", field_name="why"
        )
        self.assertFalse(result.success)
        self.assertEqual(result.value, {})
        self.assertIsNotNone(result.error)
        self.assertIn("JSONDecodeError", result.error)
        self.assertIsNotNone(result.raw_value)

    def test_safe_json_loads_null_input(self):
        """None input should return default without error."""
        from lib.safety import safe_json_loads

        result = safe_json_loads(None, default=[], item_id="test3")
        self.assertTrue(result.success)
        self.assertEqual(result.value, [])

    def test_trust_meta_tracks_errors(self):
        """TrustMeta should accumulate parse errors."""
        from lib.safety import TrustMeta

        trust = TrustMeta()
        self.assertTrue(trust.data_integrity)

        trust.add_parse_error("why", "JSONDecodeError at pos 5", raw_length=100)
        self.assertFalse(trust.data_integrity)
        self.assertEqual(len(trust.errors), 1)
        self.assertIn("why:", trust.errors[0])

    def test_parse_json_field_with_trust(self):
        """parse_json_field should update TrustMeta on failure."""
        from lib.safety import TrustMeta, parse_json_field

        item = {
            "id": "coupling_123",
            "entity_refs": "{invalid json[",
            "why": '{"valid": "json"}',
        }
        trust = TrustMeta()

        # Parse entity_refs (malformed)
        refs = parse_json_field(
            item, "entity_refs", default=[], trust=trust, item_id_field="id"
        )
        self.assertEqual(refs, [])
        self.assertFalse(trust.data_integrity)
        self.assertEqual(len(trust.errors), 1)

        # Parse why (valid)
        why = parse_json_field(item, "why", default={}, trust=trust, item_id_field="id")
        self.assertEqual(why, {"valid": "json"})
        # Still has the previous error
        self.assertEqual(len(trust.errors), 1)

    def test_api_response_includes_trust_failure(self):
        """API should include meta.trust when parse fails."""
        from lib.safety import TrustMeta, parse_json_field

        # Simulate an API item with malformed JSON
        item = {
            "coupling_id": "link_456",
            "entity_refs": "not valid json",
            "why": "also not valid",
        }
        trust = TrustMeta()

        item["entity_refs"] = parse_json_field(
            item, "entity_refs", default=[], trust=trust, item_id_field="coupling_id"
        )
        item["why"] = parse_json_field(
            item, "why", default={}, trust=trust, item_id_field="coupling_id"
        )

        # Add trust metadata to item
        if not trust.data_integrity:
            item["meta"] = {"trust": trust.to_dict()}

        # Verify trust failure is indicated
        self.assertIn("meta", item)
        self.assertIn("trust", item["meta"])
        self.assertFalse(item["meta"]["trust"]["data_integrity"])
        self.assertEqual(len(item["meta"]["trust"]["errors"]), 2)

    def test_no_silent_empty_defaults(self):
        """Ensure malformed data does NOT silently become {} or []."""
        from lib.safety import TrustMeta, parse_json_field

        # This is the key test: malformed data must NOT silently default
        item = {
            "id": "test_789",
            "entity_refs": "{broken",
        }
        trust = TrustMeta()

        result = parse_json_field(item, "entity_refs", default=[], trust=trust)

        # Result is default, but trust failure MUST be recorded
        self.assertEqual(result, [])
        self.assertFalse(
            trust.data_integrity, "Parse failure must be recorded, not silent!"
        )
        self.assertGreater(len(trust.errors), 0, "Error must be recorded!")


if __name__ == "__main__":
    main()
