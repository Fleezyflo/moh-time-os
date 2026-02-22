"""Tests for the TruthCycle orchestrator."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.truth_cycle import StageResult, TruthCycle, TruthCycleResult


@pytest.fixture()
def db_path(tmp_path):
    """Create a minimal test database."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS time_blocks (
            id TEXT PRIMARY KEY,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            lane TEXT,
            status TEXT DEFAULT 'available',
            task_id TEXT,
            source TEXT DEFAULT 'manual',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT,
            project_id TEXT,
            lane TEXT,
            status TEXT DEFAULT 'open',
            priority INTEGER DEFAULT 0,
            due_date TEXT,
            completed_at TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS commitments (
            commitment_id TEXT PRIMARY KEY,
            scope_ref_type TEXT,
            scope_ref_id TEXT,
            committed_by_type TEXT NOT NULL,
            committed_by_id TEXT,
            commitment_text TEXT,
            due_at TEXT,
            confidence REAL,
            evidence_excerpt_ids TEXT,
            status TEXT DEFAULT 'open',
            created_at TEXT,
            client_id TEXT,
            speaker TEXT,
            target TEXT,
            type TEXT,
            source_id TEXT
        );
        CREATE TABLE IF NOT EXISTS capacity_lanes (
            id TEXT PRIMARY KEY,
            name TEXT,
            hours_per_week REAL DEFAULT 8,
            priority INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT,
            tier TEXT,
            status TEXT DEFAULT 'active'
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT,
            client_id TEXT,
            brand_id TEXT,
            status TEXT DEFAULT 'active',
            is_internal INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS communications (
            id TEXT PRIMARY KEY,
            source TEXT,
            from_email TEXT,
            subject TEXT,
            body_text TEXT,
            received_at TEXT,
            client_id TEXT
        );
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            type TEXT,
            source TEXT,
            entity_type TEXT,
            entity_id TEXT,
            severity TEXT,
            created_at TEXT
        );
    """)
    conn.close()
    return str(db)


class TestTruthCycleResult:
    """Tests for the TruthCycleResult dataclass."""

    def test_all_ok_when_all_pass(self):
        result = TruthCycleResult(
            stages={
                "a": StageResult(name="a", ok=True),
                "b": StageResult(name="b", ok=True),
            }
        )
        assert result.all_ok is True
        assert result.passed == 2
        assert result.failed == 0

    def test_not_all_ok_when_one_fails(self):
        result = TruthCycleResult(
            stages={
                "a": StageResult(name="a", ok=True),
                "b": StageResult(name="b", ok=False, error="boom"),
            }
        )
        assert result.all_ok is False
        assert result.passed == 1
        assert result.failed == 1

    def test_empty_stages(self):
        result = TruthCycleResult()
        assert result.all_ok is True
        assert result.passed == 0


class TestTruthCycle:
    """Tests for the TruthCycle orchestrator."""

    def test_import(self):
        from lib.truth_cycle import TruthCycle

        assert TruthCycle is not None

    def test_runs_all_4_stages(self, db_path):
        tc = TruthCycle(db_path)
        result = tc.run()
        assert isinstance(result, TruthCycleResult)
        assert "time" in result.stages
        assert "commitments" in result.stages
        assert "capacity" in result.stages
        assert "client_health" in result.stages
        assert len(result.stages) == 4

    def test_each_stage_returns_typed_result(self, db_path):
        tc = TruthCycle(db_path)
        result = tc.run()
        for name, stage in result.stages.items():
            assert isinstance(stage, StageResult), f"{name} not StageResult"
            assert stage.name == name or stage.name in (
                "time",
                "commitments",
                "capacity",
                "client_health",
            )
            assert isinstance(stage.counts, dict)

    def test_graceful_degradation(self, db_path):
        """One stage failure doesn't block others."""
        tc = TruthCycle(db_path)

        # Patch time truth to fail
        with patch.object(
            tc,
            "_run_time_truth",
            return_value=StageResult(name="time", ok=False, error="simulated"),
        ):
            result = tc.run()
            assert result.stages["time"].ok is False
            assert result.stages["time"].error == "simulated"
            # Other stages still ran
            assert "commitments" in result.stages
            assert "capacity" in result.stages
            assert "client_health" in result.stages

    def test_errors_collected(self, db_path):
        tc = TruthCycle(db_path)
        with patch.object(
            tc,
            "_run_time_truth",
            return_value=StageResult(name="time", ok=False, error="time broke"),
        ):
            with patch.object(
                tc,
                "_run_commitment_truth",
                return_value=StageResult(name="commitments", ok=True, counts={"total": 0}),
            ):
                with patch.object(
                    tc,
                    "_run_capacity_truth",
                    return_value=StageResult(name="capacity", ok=False, error="capacity broke"),
                ):
                    with patch.object(
                        tc,
                        "_run_client_truth",
                        return_value=StageResult(name="client_health", ok=True, counts={}),
                    ):
                        result = tc.run()
                        assert len(result.errors) == 2
                        assert any("time" in e for e in result.errors)
                        assert any("capacity" in e for e in result.errors)

    def test_timestamp_set(self, db_path):
        tc = TruthCycle(db_path)
        result = tc.run()
        assert result.timestamp is not None
