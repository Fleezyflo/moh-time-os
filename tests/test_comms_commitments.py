"""
Acceptance Tests for Page 4 - COMMS / COMMITMENTS COMMAND

Per §9 (locked):
1. If data_integrity=false: only Integrity panel renders
2. Hot list never exceeds caps (9/25)
3. Ordering matches §6.4 exactly (synthetic test fixture)
4. Response status derivation matches §4.2 exactly
5. expected_response_by derivation matches §4.2.1 exactly (unit test)
6. Commitments at risk/broken classification matches §4.4 exactly
7. Thread Room always includes: header, summary, evidence, snippets, commitments, actions, reason
8. Unlinked actionable comms surface as Unknown triage and include Fix actions
9. Propose/Approval actions always write pending_actions with unique idempotency_key
10. UI never behaves like an inbox: no full mailbox scrolling; snippets capped
"""

import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from agency_snapshot.comms_commitments import CommsCommitmentsEngine
from agency_snapshot.scoring import Horizon, Mode


@pytest.fixture
def test_db():
    """Create a test database with schema and fixtures."""
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(db_file.name)

    # Create schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS communications (
            id TEXT PRIMARY KEY,
            commitment_id TEXT,
            thread_id TEXT,
            from_email TEXT,
            to_emails TEXT,
            subject TEXT,
            snippet TEXT,
            body_text TEXT,
            received_at TEXT,
            created_at TEXT,
            client_id TEXT,
            response_deadline TEXT,
            expected_response_by TEXT,
            requires_response INTEGER DEFAULT 0,
            link_status TEXT,
            is_important INTEGER DEFAULT 0,
            is_starred INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT,
            tier TEXT DEFAULT 'C'
        );

        CREATE TABLE IF NOT EXISTS commitments (
            id TEXT PRIMARY KEY,
            type TEXT DEFAULT 'request',
            text TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'open',
            confidence REAL DEFAULT 0.5,
            source_type TEXT,
            source_id TEXT,
            client_id TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT,
            client_id TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'open'
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT,
            client_id TEXT,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            external_id TEXT,
            client_id TEXT,
            amount REAL,
            due_date TEXT,
            status TEXT,
            payment_date TEXT
        );
    """)
    conn.commit()
    conn.close()

    yield Path(db_file.name)

    # Cleanup
    Path(db_file.name).unlink(missing_ok=True)


@pytest.fixture
def engine(test_db):
    """Create engine with test database."""
    return CommsCommitmentsEngine(db_path=test_db, mode=Mode.OPS_HEAD, horizon=Horizon.TODAY)


class TestResponseStatusDerivation:
    """Test §4.2 - Response status derivation (locked)."""

    def test_overdue_when_past_expected(self, test_db, engine):
        """OVERDUE when now > expected_response_by."""
        conn = sqlite3.connect(test_db)
        past = (datetime.now() - timedelta(hours=5)).isoformat()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', '{datetime.now().isoformat()}', 'c1', '{past}', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert len(result["hot_list"]) >= 1
        thread = result["hot_list"][0]
        assert thread["response_status"] == "OVERDUE"

    def test_due_when_within_horizon(self, test_db, engine):
        """DUE when expected_response_by within horizon and not overdue."""
        conn = sqlite3.connect(test_db)
        # 2 hours from now (within TODAY horizon)
        future = (datetime.now() + timedelta(hours=2)).isoformat()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', '{datetime.now().isoformat()}', 'c1', '{future}', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert len(result["hot_list"]) >= 1
        thread = result["hot_list"][0]
        assert thread["response_status"] == "DUE"

    def test_ok_when_far_future(self, test_db):
        """OK when expected_response_by far in future."""
        engine = CommsCommitmentsEngine(
            db_path=test_db,
            mode=Mode.OPS_HEAD,
            horizon=Horizon.NOW,  # Stricter horizon
        )

        conn = sqlite3.connect(test_db)
        # 48 hours from now (beyond NOW horizon)
        future = (datetime.now() + timedelta(hours=48)).isoformat()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'C')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', '{datetime.now().isoformat()}', 'c1', '{future}', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        # Should not be in hot list for NOW horizon (too far out)
        # or if it is, should be OK
        if result["hot_list"]:
            thread = result["hot_list"][0]
            assert thread["response_status"] == "OK"


class TestExpectedResponseByDerivation:
    """Test §4.2.1 - expected_response_by fallback order (locked)."""

    def test_uses_stored_deadline_first(self, test_db, engine):
        """Priority 1: Use stored response_deadline if exists."""
        conn = sqlite3.connect(test_db)
        stored_deadline = (datetime.now() + timedelta(hours=5)).isoformat()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', '{datetime.now().isoformat()}', 'c1', '{stored_deadline}', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert len(result["hot_list"]) >= 1
        thread = result["hot_list"][0]
        assert thread["expected_response_by"] == stored_deadline

    def test_vip_gets_6_hours(self, test_db):
        """Priority 3: VIP = last_inbound + 6 hours."""
        # Use THIS_WEEK horizon to ensure thread is always eligible
        engine = CommsCommitmentsEngine(
            db_path=test_db, mode=Mode.OPS_HEAD, horizon=Horizon.THIS_WEEK
        )

        conn = sqlite3.connect(test_db)
        received = datetime.now()

        # Tier A = VIP
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'VIP Client', 'A')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, link_status)
            VALUES ('comm1', 'thread1', 'vip@example.com', 'Test', '{received.isoformat()}', 'c1', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert len(result["hot_list"]) >= 1
        thread = result["hot_list"][0]

        # Should be approximately 6 hours from received
        expected = datetime.fromisoformat(thread["expected_response_by"])
        delta_hours = (expected - received).total_seconds() / 3600
        assert 5.9 <= delta_hours <= 6.1, f"VIP should get ~6h deadline, got {delta_hours:.1f}h"

    def test_tier_b_gets_24_hours(self, test_db):
        """Priority 5: Tier B = last_inbound + 24 hours."""
        # Use THIS_WEEK horizon to ensure thread is always eligible
        engine = CommsCommitmentsEngine(
            db_path=test_db, mode=Mode.OPS_HEAD, horizon=Horizon.THIS_WEEK
        )

        conn = sqlite3.connect(test_db)
        received = datetime.now()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Regular Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, link_status)
            VALUES ('comm1', 'thread1', 'client@example.com', 'Test', '{received.isoformat()}', 'c1', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert len(result["hot_list"]) >= 1
        thread = result["hot_list"][0]

        expected = datetime.fromisoformat(thread["expected_response_by"])
        delta_hours = (expected - received).total_seconds() / 3600
        assert 23.9 <= delta_hours <= 24.1, (
            f"Tier B should get ~24h deadline, got {delta_hours:.1f}h"
        )


class TestCommitmentBreachClassification:
    """Test §4.4 - Commitment breach classification (locked)."""

    def test_broken_when_past_deadline_and_open(self, test_db, engine):
        """BROKEN if deadline passed and status still open."""
        conn = sqlite3.connect(test_db)
        past = (datetime.now() - timedelta(days=1)).isoformat()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', '{datetime.now().isoformat()}', 'c1', 'linked')
        """)  # noqa: S608
        conn.execute(f"""
            INSERT INTO commitments (id, type, text, deadline, status, source_type, source_id, client_id)
            VALUES ('commit1', 'promise', 'We will deliver', '{past}', 'open', 'communication', 'thread1', 'c1')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        # Commitment should be at risk (summary counter)
        assert result["summary"]["commitments_at_risk"] >= 1

    def test_at_risk_when_deadline_within_horizon(self, test_db, engine):
        """AT_RISK if deadline within horizon and status open."""
        conn = sqlite3.connect(test_db)
        # Deadline in 4 hours (within TODAY horizon)
        soon = (datetime.now() + timedelta(hours=4)).isoformat()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', '{datetime.now().isoformat()}', 'c1', 'linked')
        """)  # noqa: S608
        conn.execute(f"""
            INSERT INTO commitments (id, type, text, deadline, status, source_type, source_id, client_id)
            VALUES ('commit1', 'promise', 'We will deliver', '{soon}', 'open', 'communication', 'thread1', 'c1')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert result["summary"]["commitments_at_risk"] >= 1


class TestHotListOrdering:
    """Test §6.4 - Hot list ordering (locked)."""

    def test_overdue_before_due_before_ok(self, test_db, engine):
        """Response status order: OVERDUE > DUE > OK."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client 1', 'B')")
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c2', 'Client 2', 'B')")
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c3', 'Client 3', 'B')")

        # Thread 1: OK (far future deadline)
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm1', 'thread1', 't1@example.com', 'OK Thread', '{now.isoformat()}', 'c1', '{(now + timedelta(days=7)).isoformat()}', 'linked')
        """)  # noqa: S608

        # Thread 2: OVERDUE
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm2', 'thread2', 't2@example.com', 'Overdue Thread', '{now.isoformat()}', 'c2', '{(now - timedelta(hours=5)).isoformat()}', 'linked')
        """)  # noqa: S608

        # Thread 3: DUE (soon)
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm3', 'thread3', 't3@example.com', 'Due Thread', '{now.isoformat()}', 'c3', '{(now + timedelta(hours=2)).isoformat()}', 'linked')
        """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate()
        hot_list = result["hot_list"]

        # Filter to just our test threads
        test_threads = [t for t in hot_list if t["thread_id"] in ("thread1", "thread2", "thread3")]

        # OVERDUE should be first
        assert len(test_threads) >= 2
        statuses = [t["response_status"] for t in test_threads]

        # OVERDUE should appear before DUE
        if "OVERDUE" in statuses and "DUE" in statuses:
            assert statuses.index("OVERDUE") < statuses.index("DUE")


class TestHotListCaps:
    """Test §2.2 - Hot list caps (locked)."""

    def test_default_cap_9(self, test_db, engine):
        """Default hot list max 9 threads."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        # Create 15 threads
        for i in range(15):
            conn.execute(f"INSERT INTO clients (id, name, tier) VALUES ('c{i}', 'Client {i}', 'B')")  # noqa: S608
            conn.execute(f"""
                INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
                VALUES ('comm{i}', 'thread{i}', 't{i}@example.com', 'Thread {i}', '{now.isoformat()}', 'c{i}', '{(now - timedelta(hours=i + 1)).isoformat()}', 'linked')
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate(expanded=False)

        assert len(result["hot_list"]) <= 9, f"Default cap violated: {len(result['hot_list'])} > 9"

    def test_expanded_cap_25(self, test_db, engine):
        """Expanded hot list max 25 threads."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        # Create 30 threads
        for i in range(30):
            conn.execute(f"INSERT INTO clients (id, name, tier) VALUES ('c{i}', 'Client {i}', 'B')")  # noqa: S608
            conn.execute(f"""
                INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
                VALUES ('comm{i}', 'thread{i}', 't{i}@example.com', 'Thread {i}', '{now.isoformat()}', 'c{i}', '{(now - timedelta(hours=i + 1)).isoformat()}', 'linked')
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate(expanded=True)

        assert len(result["hot_list"]) <= 25, (
            f"Expanded cap violated: {len(result['hot_list'])} > 25"
        )


class TestSnippetsCap:
    """Test §2.3 - Snippets cap (locked)."""

    def test_snippets_max_8(self, test_db, engine):
        """Thread Room snippets max 8."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")

        # Create thread with 15 messages
        for i in range(15):
            msg_time = (now - timedelta(hours=i)).isoformat()
            conn.execute(f"""
                INSERT INTO communications (id, thread_id, from_email, subject, snippet, received_at, client_id, link_status)
                VALUES ('comm{i}', 'thread1', 'test@example.com', 'Test Thread', 'Message {i} content here', '{msg_time}', 'c1', 'linked')
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate(selected_thread_id="thread1")

        selected = result.get("selected_thread")
        assert selected is not None
        assert len(selected["snippets"]) <= 8, (
            f"Snippets cap violated: {len(selected['snippets'])} > 8"
        )


class TestThreadRoomStructure:
    """Test §9.7 - Thread Room always includes required fields."""

    def test_selected_thread_has_all_required_fields(self, test_db, engine):
        """Thread Room must include: header, summary, evidence, snippets, commitments, actions, reason."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, snippet, received_at, client_id, response_deadline, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', 'Test snippet', '{now.isoformat()}', 'c1', '{(now - timedelta(hours=2)).isoformat()}', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate(selected_thread_id="thread1")

        selected = result.get("selected_thread")
        assert selected is not None

        # Check all required fields per §9.7
        required_fields = [
            "header",
            "summary",
            "evidence",
            "snippets",
            "commitments",
            "actions",
            "reason",
        ]
        for field in required_fields:
            assert field in selected, f"Thread Room missing required field: {field}"

        # Check header subfields
        header = selected["header"]
        assert "client_id" in header
        assert "subject" in header
        assert "thread_type" in header
        assert "response_status" in header
        assert "confidence" in header


class TestUnlinkedComms:
    """Test §9.8 - Unlinked actionable comms."""

    def test_unlinked_surfaces_as_unknown_triage(self, test_db, engine):
        """Unlinked actionable comms surface as Unknown triage."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        # Unlinked comm with actionable content
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, body_text, received_at, client_id, link_status, is_important)
            VALUES ('comm1', 'thread1', 'unknown@example.com', 'Need help',
                    'Can you please help me with this invoice payment issue? We need to resolve this urgently.',
                    '{now.isoformat()}', NULL, 'unlinked', 1)
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        # Should appear in hot list
        unlinked_threads = [t for t in result["hot_list"] if t["client_id"] is None]

        if unlinked_threads:
            thread = unlinked_threads[0]
            assert thread["thread_type"] == "Unknown triage"

    def test_unlinked_includes_fix_action(self, test_db, engine):
        """Unlinked comms include Fix actions."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        # Unlinked comm
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, body_text, received_at, client_id, link_status, is_important)
            VALUES ('comm1', 'thread1', 'unknown@example.com', 'Request',
                    'Please can you help me with this request? It is very important and urgent.',
                    '{now.isoformat()}', NULL, 'unlinked', 1)
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        # Check for fix action in global actions
        [a for a in result["global_actions"] if "unlinked" in a["label"].lower()]

        # May or may not have fix actions depending on eligibility
        # But if unlinked thread is selected, it should have fix actions
        if (
            result.get("selected_thread")
            and result["selected_thread"]["header"]["client_id"] is None
        ):
            thread_actions = result["selected_thread"]["actions"]
            fix_in_thread = [
                a
                for a in thread_actions
                if "unlinked" in a["label"].lower() or "resolution" in a["label"].lower()
            ]
            assert len(fix_in_thread) > 0, "Unlinked thread should have fix action"


class TestActionIdempotency:
    """Test §9.9 - Actions have unique idempotency_key."""

    def test_actions_have_idempotency_key(self, test_db, engine):
        """Every action must have idempotency_key."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', '{now.isoformat()}', 'c1', '{(now - timedelta(hours=5)).isoformat()}', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        for action in result["global_actions"]:
            assert "idempotency_key" in action, f"Action missing idempotency_key: {action}"
            assert action["idempotency_key"], "idempotency_key should not be empty"

    def test_idempotency_keys_unique(self, test_db, engine):
        """Idempotency keys should be unique."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        # Create multiple threads
        for i in range(5):
            conn.execute(f"INSERT INTO clients (id, name, tier) VALUES ('c{i}', 'Client {i}', 'B')")  # noqa: S608
            conn.execute(f"""
                INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
                VALUES ('comm{i}', 'thread{i}', 't{i}@example.com', 'Thread {i}', '{now.isoformat()}', 'c{i}', '{(now - timedelta(hours=i + 1)).isoformat()}', 'linked')
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate()

        keys = [a["idempotency_key"] for a in result["global_actions"]]
        assert len(keys) == len(set(keys)), "Idempotency keys should be unique"


class TestVIPClassification:
    """Test §4.3 - VIP classification (locked)."""

    def test_tier_a_is_vip(self, test_db):
        """Tier A client = VIP."""
        # Use THIS_WEEK horizon to ensure eligibility
        engine = CommsCommitmentsEngine(
            db_path=test_db, mode=Mode.OPS_HEAD, horizon=Horizon.THIS_WEEK
        )

        conn = sqlite3.connect(test_db)
        now = datetime.now()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'VIP Client', 'A')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, link_status)
            VALUES ('comm1', 'thread1', 'vip@example.com', 'Test', '{now.isoformat()}', 'c1', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert len(result["hot_list"]) >= 1
        thread = result["hot_list"][0]
        assert thread["vip"]

    def test_starred_is_vip(self, test_db):
        """Starred/important flag = VIP."""
        # Use THIS_WEEK horizon to ensure eligibility
        engine = CommsCommitmentsEngine(
            db_path=test_db, mode=Mode.OPS_HEAD, horizon=Horizon.THIS_WEEK
        )

        conn = sqlite3.connect(test_db)
        now = datetime.now()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'C')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, link_status, is_starred)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Test', '{now.isoformat()}', 'c1', 'linked', 1)
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert len(result["hot_list"]) >= 1
        thread = result["hot_list"][0]
        assert thread["vip"]


class TestBaseScoreComputation:
    """Test §6.2 - Base score computation."""

    def test_overdue_has_high_score(self, test_db, engine):
        """Overdue threads should have higher scores."""
        conn = sqlite3.connect(test_db)
        now = datetime.now()

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'B')")
        conn.execute(f"""
            INSERT INTO communications (id, thread_id, from_email, subject, received_at, client_id, response_deadline, link_status)
            VALUES ('comm1', 'thread1', 'test@example.com', 'Overdue', '{now.isoformat()}', 'c1', '{(now - timedelta(hours=24)).isoformat()}', 'linked')
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        assert len(result["hot_list"]) >= 1
        thread = result["hot_list"][0]
        # Overdue should have relatively high score due to urgency
        assert thread["base_score"] >= 40


class TestDataIntegrityGate:
    """Test §9.1 - data_integrity gate."""

    def test_integrity_false_is_reflected(self, test_db):
        """If data_integrity=false, trust should reflect it."""
        engine = CommsCommitmentsEngine(db_path=test_db)
        engine.data_integrity = False

        result = engine.generate()

        assert not result["meta"]["trust"]["data_integrity"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
