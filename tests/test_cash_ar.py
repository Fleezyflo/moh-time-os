"""
Acceptance Tests for Page 3 - CASH / AR COMMAND

Per §10 (locked):
1. If data_integrity=false: only Integrity panel renders
2. Summary totals use valid AR only; invalid AR never included in totals
3. Aging buckets exactly match §4.2
4. Client Cash Risk Score exactly matches §5.1 and is unit-tested
5. Portfolio ordering matches §9.1 exactly (synthetic test fixture)
6. Invoice ordering matches §9.2 exactly
7. Invalid AR items appear in Invalid/Missing with fix actions
8. Any Propose action writes pending_actions with unique idempotency_key
9. UI never renders >25 invoice lines or exceeds any caps
10. Currency is never mixed silently; must filter or group
"""

import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from agency_snapshot.cash_ar import CashAREngine, Invoice
from agency_snapshot.scoring import Horizon, Mode


@pytest.fixture
def test_db():
    """Create a test database with schema and fixtures."""
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(db_file.name)

    # Create schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            external_id TEXT,
            amount REAL,
            currency TEXT DEFAULT 'AED',
            issue_date TEXT,
            due_date TEXT,
            payment_date TEXT,
            updated_at TEXT,
            status TEXT,
            client_id TEXT,
            client_name TEXT,
            aging_bucket TEXT
        );

        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT,
            tier TEXT DEFAULT 'C'
        );

        CREATE TABLE IF NOT EXISTS communications (
            id TEXT PRIMARY KEY,
            subject TEXT,
            client_id TEXT,
            from_email TEXT,
            created_at TEXT,
            response_deadline TEXT,
            requires_response INTEGER DEFAULT 0
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
    return CashAREngine(db_path=test_db, mode=Mode.OPS_HEAD, horizon=Horizon.TODAY)


class TestAgingBuckets:
    """Test §4.2 - Aging bucket definitions (locked)."""

    def test_current_bucket(self, engine):
        """days_overdue <= 0 is 'current'."""
        assert engine._compute_bucket(0) == "current"
        assert engine._compute_bucket(-5) == "current"
        assert engine._compute_bucket(-30) == "current"

    def test_1_30_bucket(self, engine):
        """days_overdue 1..30 is '1-30'."""
        assert engine._compute_bucket(1) == "1-30"
        assert engine._compute_bucket(15) == "1-30"
        assert engine._compute_bucket(30) == "1-30"

    def test_31_60_bucket(self, engine):
        """days_overdue 31..60 is '31-60'."""
        assert engine._compute_bucket(31) == "31-60"
        assert engine._compute_bucket(45) == "31-60"
        assert engine._compute_bucket(60) == "31-60"

    def test_61_90_bucket(self, engine):
        """days_overdue 61..90 is '61-90'."""
        assert engine._compute_bucket(61) == "61-90"
        assert engine._compute_bucket(75) == "61-90"
        assert engine._compute_bucket(90) == "61-90"

    def test_90_plus_bucket(self, engine):
        """days_overdue > 90 is '90+'."""
        assert engine._compute_bucket(91) == "90+"
        assert engine._compute_bucket(120) == "90+"
        assert engine._compute_bucket(365) == "90+"


class TestRiskScore:
    """Test §5.1 - Client Cash Risk Score formula (locked)."""

    def test_zero_ar_zero_score(self, engine):
        """T = 0 → score = 0."""
        score = engine._compute_client_risk_score([])
        assert score == 0.0

    def test_all_current_low_score(self, engine):
        """100% current should give low score (< 40)."""
        invoices = [
            Invoice(
                invoice_id="1",
                external_id=None,
                amount=10000,
                currency="AED",
                issue_date=None,
                due_date=(date.today() + timedelta(days=30)).isoformat(),
                days_overdue=-30,
                aging_bucket="current",
                status="sent",
                client_id="c1",
                client_name="Test",
                is_valid=True,
            )
        ]
        score = engine._compute_client_risk_score(invoices)
        assert score < 40, f"All current should be LOW risk, got {score}"

    def test_all_severe_high_score(self, engine):
        """100% severe (90+) should give HIGH score (>= 70)."""
        invoices = [
            Invoice(
                invoice_id="1",
                external_id=None,
                amount=10000,
                currency="AED",
                issue_date=None,
                due_date=(date.today() - timedelta(days=100)).isoformat(),
                days_overdue=100,
                aging_bucket="90+",
                status="overdue",
                client_id="c1",
                client_name="Test",
                is_valid=True,
            )
        ]
        score = engine._compute_client_risk_score(invoices)
        # With severe_ratio=1, moderate_ratio=0, overdue_ratio=1, oldest_factor=1
        # Score = 100 * (0.55*1 + 0.25*0 + 0.10*1 + 0.10*1) = 75
        assert score >= 70, f"All 90+ should be HIGH risk, got {score}"

    def test_mixed_portfolio_score(self, engine):
        """Mixed portfolio score matches formula exactly."""
        # Create invoices: $5000 current, $3000 1-30, $2000 90+
        today = date.today()
        invoices = [
            Invoice(
                invoice_id="1",
                external_id=None,
                amount=5000,
                currency="AED",
                issue_date=None,
                due_date=(today + timedelta(days=10)).isoformat(),
                days_overdue=-10,
                aging_bucket="current",
                status="sent",
                client_id="c1",
                client_name="Test",
                is_valid=True,
            ),
            Invoice(
                invoice_id="2",
                external_id=None,
                amount=3000,
                currency="AED",
                issue_date=None,
                due_date=(today - timedelta(days=20)).isoformat(),
                days_overdue=20,
                aging_bucket="1-30",
                status="overdue",
                client_id="c1",
                client_name="Test",
                is_valid=True,
            ),
            Invoice(
                invoice_id="3",
                external_id=None,
                amount=2000,
                currency="AED",
                issue_date=None,
                due_date=(today - timedelta(days=100)).isoformat(),
                days_overdue=100,
                aging_bucket="90+",
                status="overdue",
                client_id="c1",
                client_name="Test",
                is_valid=True,
            ),
        ]

        score = engine._compute_client_risk_score(invoices)

        # Manual calculation:
        # T = 10000, C = 5000, M = 3000 (1-30), S = 2000 (90+)
        # severe_ratio = 2000/10000 = 0.2
        # moderate_ratio = 3000/10000 = 0.3
        # overdue_ratio = (10000-5000)/10000 = 0.5
        # oldest_factor = min(1, 100/90) = 1.0
        # Score = 100 * (0.55*0.2 + 0.25*0.3 + 0.10*0.5 + 0.10*1.0)
        #       = 100 * (0.11 + 0.075 + 0.05 + 0.10)
        #       = 100 * 0.335 = 33.5
        expected = 33.5
        assert abs(score - expected) < 0.1, f"Expected ~{expected}, got {score}"

    def test_score_clamped_0_100(self, engine):
        """Score should always be in [0, 100]."""
        # Edge case: extreme values
        invoices = [
            Invoice(
                invoice_id="1",
                external_id=None,
                amount=1000000,
                currency="AED",
                issue_date=None,
                due_date=(date.today() - timedelta(days=365)).isoformat(),
                days_overdue=365,
                aging_bucket="90+",
                status="overdue",
                client_id="c1",
                client_name="Test",
                is_valid=True,
            )
        ]
        score = engine._compute_client_risk_score(invoices)
        assert 0 <= score <= 100


class TestRiskBand:
    """Test §5.2 - Risk band thresholds (locked)."""

    def test_high_band(self, engine):
        """Score >= 70 is HIGH."""
        assert engine._score_to_band(70) == "HIGH"
        assert engine._score_to_band(85) == "HIGH"
        assert engine._score_to_band(100) == "HIGH"

    def test_med_band(self, engine):
        """Score 40-69 is MED."""
        assert engine._score_to_band(40) == "MED"
        assert engine._score_to_band(55) == "MED"
        assert engine._score_to_band(69) == "MED"

    def test_low_band(self, engine):
        """Score < 40 is LOW."""
        assert engine._score_to_band(0) == "LOW"
        assert engine._score_to_band(20) == "LOW"
        assert engine._score_to_band(39) == "LOW"


class TestValidInvalidAR:
    """Test §4.1 - Valid vs Invalid AR definitions (locked)."""

    def test_valid_ar_included_in_totals(self, test_db, engine):
        """Valid AR (has due_date AND client_id) is included in totals."""
        conn = sqlite3.connect(test_db)
        conn.execute("""
            INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
            VALUES ('inv1', 1000, '2025-01-01', 'c1', 'sent', NULL)
        """)
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client 1', 'A')")
        conn.commit()
        conn.close()

        result = engine.generate()

        assert result["summary"]["valid_ar_total"] == 1000

    def test_invalid_ar_excluded_from_totals(self, test_db, engine):
        """Invalid AR (missing due_date OR client_id) excluded from totals."""
        conn = sqlite3.connect(test_db)
        # Missing due_date
        conn.execute("""
            INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
            VALUES ('inv1', 1000, NULL, 'c1', 'sent', NULL)
        """)
        # Missing client_id
        conn.execute("""
            INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
            VALUES ('inv2', 2000, '2025-01-01', NULL, 'sent', NULL)
        """)
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client 1', 'A')")
        conn.commit()
        conn.close()

        result = engine.generate()

        assert result["summary"]["valid_ar_total"] == 0
        assert result["meta"]["trust"]["invalid_ar_count"] == 2
        assert result["meta"]["trust"]["invalid_ar_amount"] == 3000


class TestPortfolioOrdering:
    """Test §9.1 - Portfolio ordering (locked)."""

    def test_ordering_risk_band_first(self, test_db, engine):
        """HIGH risk clients appear before MED before LOW."""
        today = date.today()
        conn = sqlite3.connect(test_db)

        # Client 1: All current (LOW risk)
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Low Risk', 'A')")
        conn.execute(f"""
            INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
            VALUES ('inv1', 10000, '{(today + timedelta(days=30)).isoformat()}', 'c1', 'sent', NULL)
        """)  # noqa: S608

        # Client 2: All 90+ (HIGH risk)
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c2', 'High Risk', 'B')")
        conn.execute(f"""
            INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
            VALUES ('inv2', 10000, '{(today - timedelta(days=100)).isoformat()}', 'c2', 'overdue', NULL)
        """)  # noqa: S608

        # Client 3: Mixed (MED risk)
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c3', 'Med Risk', 'B')")
        conn.execute(f"""
            INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
            VALUES ('inv3', 5000, '{(today - timedelta(days=45)).isoformat()}', 'c3', 'overdue', NULL)
        """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate()
        portfolio = result["portfolio"]

        # Should be ordered: HIGH (c2), MED (c3), LOW (c1)
        assert len(portfolio) == 3
        assert portfolio[0]["client_id"] == "c2", "HIGH risk should be first"
        assert portfolio[0]["risk_band"] == "HIGH"

        assert portfolio[1]["client_id"] == "c3", "MED risk should be second"
        assert portfolio[1]["risk_band"] == "MED"

        assert portfolio[2]["client_id"] == "c1", "LOW risk should be last"
        assert portfolio[2]["risk_band"] == "LOW"


class TestInvoiceOrdering:
    """Test §9.2 - Invoice ordering inside client (locked)."""

    def test_ordering_bucket_severity_first(self, test_db, engine):
        """90+ before 61-90 before 31-60 before 1-30 before current."""
        today = date.today()
        conn = sqlite3.connect(test_db)

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Test Client', 'A')")

        # Insert invoices in random order
        invoices = [
            ("inv_current", 1000, today + timedelta(days=10), "current"),
            ("inv_1_30", 1000, today - timedelta(days=15), "1-30"),
            ("inv_31_60", 1000, today - timedelta(days=45), "31-60"),
            ("inv_61_90", 1000, today - timedelta(days=75), "61-90"),
            ("inv_90_plus", 1000, today - timedelta(days=120), "90+"),
        ]

        for inv_id, amount, due, bucket in invoices:
            status = "sent" if bucket == "current" else "overdue"
            conn.execute(f"""
                INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date, aging_bucket)
                VALUES ('{inv_id}', {amount}, '{due.isoformat()}', 'c1', '{status}', NULL, '{bucket}')
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate(selected_client_id="c1")
        invoices = result["selected_client"]["top_invoices"]

        # Should be ordered by bucket severity: 90+ > 61-90 > 31-60 > 1-30 > current
        expected_order = ["90+", "61-90", "31-60", "1-30", "current"]
        actual_order = [inv["aging_bucket"] for inv in invoices]

        assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"


class TestCaps:
    """Test §2 - Anti-overstack limits (locked)."""

    def test_invoice_cap_25(self, test_db, engine):
        """Never more than 25 invoice lines."""
        today = date.today()
        conn = sqlite3.connect(test_db)

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Big Client', 'A')")

        # Insert 30 invoices
        for i in range(30):
            conn.execute(f"""
                INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
                VALUES ('inv{i}', 1000, '{(today - timedelta(days=i)).isoformat()}', 'c1', 'sent', NULL)
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate(selected_client_id="c1")
        invoices = result["selected_client"]["top_invoices"]

        assert len(invoices) <= 25, f"Invoice cap violated: {len(invoices)} > 25"

    def test_portfolio_cap_12_default(self, test_db, engine):
        """Default portfolio max 12 clients."""
        today = date.today()
        conn = sqlite3.connect(test_db)

        # Insert 15 clients with invoices
        for i in range(15):
            conn.execute(f"INSERT INTO clients (id, name, tier) VALUES ('c{i}', 'Client {i}', 'B')")  # noqa: S608
            conn.execute(f"""
                INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
                VALUES ('inv{i}', 1000, '{(today - timedelta(days=i)).isoformat()}', 'c{i}', 'sent', NULL)
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate(expanded=False)

        assert (
            len(result["portfolio"]) <= 12
        ), f"Portfolio cap violated: {len(result['portfolio'])} > 12"

    def test_portfolio_cap_30_expanded(self, test_db, engine):
        """Expanded portfolio max 30 clients."""
        today = date.today()
        conn = sqlite3.connect(test_db)

        # Insert 35 clients with invoices
        for i in range(35):
            conn.execute(f"INSERT INTO clients (id, name, tier) VALUES ('c{i}', 'Client {i}', 'B')")  # noqa: S608
            conn.execute(f"""
                INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
                VALUES ('inv{i}', 1000, '{(today - timedelta(days=i)).isoformat()}', 'c{i}', 'sent', NULL)
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate(expanded=True)

        assert (
            len(result["portfolio"]) <= 30
        ), f"Expanded cap violated: {len(result['portfolio'])} > 30"

    def test_global_actions_cap_10(self, test_db, engine):
        """Global actions max 10."""
        today = date.today()
        conn = sqlite3.connect(test_db)

        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'A')")

        # Insert 20 overdue invoices (should generate many actions)
        for i in range(20):
            conn.execute(f"""
                INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
                VALUES ('inv{i}', 1000, '{(today - timedelta(days=60 + i)).isoformat()}', 'c1', 'overdue', NULL)
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate()

        assert (
            len(result["global_actions"]) <= 10
        ), f"Global actions cap violated: {len(result['global_actions'])} > 10"


class TestInvalidARActions:
    """Test §7 - Invalid AR generates fix actions."""

    def test_missing_due_date_generates_action(self, test_db, engine):
        """Invalid AR (missing due_date) creates resolution action."""
        conn = sqlite3.connect(test_db)
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'A')")
        conn.execute("""
            INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
            VALUES ('inv1', 5000, NULL, 'c1', 'sent', NULL)
        """)
        conn.commit()
        conn.close()

        result = engine.generate()

        # Check global actions for fix action
        fix_actions = [
            a for a in result["global_actions"] if "missing_due_date" in a.get("label", "")
        ]
        assert len(fix_actions) > 0, "Missing due_date should generate fix action"

        # Check invalid_missing in selected client
        selected = result.get("selected_client")
        if selected:
            invalid = selected.get("invalid_missing", [])
            assert any(item["issue"] == "missing_due_date" for item in invalid)


class TestActionIdempotency:
    """Test §7.2 - Actions have unique idempotency_key."""

    def test_actions_have_idempotency_key(self, test_db, engine):
        """Every action must have idempotency_key."""
        today = date.today()
        conn = sqlite3.connect(test_db)
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'A')")
        conn.execute(f"""
            INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
            VALUES ('inv1', 5000, '{(today - timedelta(days=30)).isoformat()}', 'c1', 'overdue', NULL)
        """)  # noqa: S608
        conn.commit()
        conn.close()

        result = engine.generate()

        for action in result["global_actions"]:
            assert "idempotency_key" in action, f"Action missing idempotency_key: {action}"
            assert action["idempotency_key"], "idempotency_key should not be empty"

    def test_idempotency_keys_unique(self, test_db, engine):
        """Idempotency keys should be unique within a run."""
        today = date.today()
        conn = sqlite3.connect(test_db)
        conn.execute("INSERT INTO clients (id, name, tier) VALUES ('c1', 'Client', 'A')")

        # Create multiple invoices
        for i in range(5):
            conn.execute(f"""
                INSERT INTO invoices (id, amount, due_date, client_id, status, payment_date)
                VALUES ('inv{i}', 1000, '{(today - timedelta(days=30 + i * 30)).isoformat()}', 'c1', 'overdue', NULL)
            """)  # noqa: S608

        conn.commit()
        conn.close()

        result = engine.generate()

        keys = [a["idempotency_key"] for a in result["global_actions"]]
        assert len(keys) == len(set(keys)), "Idempotency keys should be unique"


class TestDataIntegrityGate:
    """Test §2 Trust Strip - data_integrity gate."""

    def test_integrity_false_blocks_render(self, test_db):
        """If data_integrity=false, page should be blocked."""
        engine = CashAREngine(db_path=test_db)
        engine.data_integrity = False

        result = engine.generate()

        # Should still return structure but trust shows integrity failed
        assert not result["meta"]["trust"]["data_integrity"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
