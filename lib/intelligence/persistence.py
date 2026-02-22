"""
Intelligence Persistence — Store and retrieve intelligence outputs.

Provides typed persistence for:
- Pattern snapshots (from patterns.py detect_all_patterns)
- Cost-to-serve snapshots (from cost_to_serve.py)
- Intelligence events (for downstream consumers)

Signal state persistence already exists in signals.py (update_signal_state, get_active_signals).
This module covers the remaining persistence gaps.
"""

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from lib import paths

logger = logging.getLogger(__name__)


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class PatternSnapshot:
    """A detected pattern persisted for history tracking."""

    id: str
    detected_at: str
    pattern_id: str
    pattern_name: str
    pattern_type: str
    severity: str
    confidence: str
    entities_involved: list[dict]
    evidence: dict
    cycle_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "detected_at": self.detected_at,
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "severity": self.severity,
            "confidence": self.confidence,
            "entities_involved": self.entities_involved,
            "evidence": self.evidence,
            "cycle_id": self.cycle_id,
        }


@dataclass
class CostSnapshotRecord:
    """A cost-to-serve computation persisted for history tracking."""

    id: str
    computed_at: str
    snapshot_type: str  # 'client' | 'project' | 'portfolio'
    entity_id: str | None
    effort_score: float | None
    efficiency_ratio: float | None
    profitability_band: str | None
    cost_drivers: list[str]
    data: dict  # Full CostProfile.to_dict()
    cycle_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "computed_at": self.computed_at,
            "snapshot_type": self.snapshot_type,
            "entity_id": self.entity_id,
            "effort_score": self.effort_score,
            "efficiency_ratio": self.efficiency_ratio,
            "profitability_band": self.profitability_band,
            "cost_drivers": self.cost_drivers,
            "data": self.data,
            "cycle_id": self.cycle_id,
        }


@dataclass
class IntelligenceEvent:
    """An intelligence event for downstream consumption."""

    id: str
    event_type: str
    severity: str
    entity_type: str | None
    entity_id: str | None
    event_data: dict
    source_module: str
    created_at: str
    consumed_at: str | None = None
    consumer: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "severity": self.severity,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "event_data": self.event_data,
            "source_module": self.source_module,
            "created_at": self.created_at,
            "consumed_at": self.consumed_at,
            "consumer": self.consumer,
        }


# =============================================================================
# PATTERN PERSISTENCE
# =============================================================================


class PatternPersistence:
    """Persist and retrieve pattern detection snapshots."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or paths.db_path()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def record_pattern(self, pattern: PatternSnapshot) -> None:
        """Record a detected pattern snapshot."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO pattern_snapshots
                   (id, detected_at, pattern_id, pattern_name, pattern_type,
                    severity, confidence, entities_involved, evidence, cycle_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    pattern.id,
                    pattern.detected_at,
                    pattern.pattern_id,
                    pattern.pattern_name,
                    pattern.pattern_type,
                    pattern.severity,
                    pattern.confidence,
                    json.dumps(pattern.entities_involved),
                    json.dumps(pattern.evidence),
                    pattern.cycle_id,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to record pattern %s: %s", pattern.pattern_id, e)
            raise
        finally:
            conn.close()

    def record_batch(self, patterns: list[PatternSnapshot]) -> dict[str, int]:
        """Record multiple pattern snapshots in a single transaction."""
        conn = self._connect()
        recorded = 0
        errors = 0
        try:
            for p in patterns:
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO pattern_snapshots
                           (id, detected_at, pattern_id, pattern_name, pattern_type,
                            severity, confidence, entities_involved, evidence, cycle_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            p.id,
                            p.detected_at,
                            p.pattern_id,
                            p.pattern_name,
                            p.pattern_type,
                            p.severity,
                            p.confidence,
                            json.dumps(p.entities_involved),
                            json.dumps(p.evidence),
                            p.cycle_id,
                        ),
                    )
                    recorded += 1
                except sqlite3.Error as e:
                    logger.error("Failed to record pattern %s: %s", p.pattern_id, e)
                    errors += 1
            conn.commit()
        finally:
            conn.close()
        return {"recorded": recorded, "errors": errors}

    def get_patterns_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 30,
    ) -> list[PatternSnapshot]:
        """Retrieve patterns involving a specific entity."""
        conn = self._connect()
        try:
            # Search within JSON entities_involved
            rows = conn.execute(
                """SELECT * FROM pattern_snapshots
                   WHERE entities_involved LIKE ?
                     AND detected_at >= datetime('now', ?)
                   ORDER BY detected_at DESC""",
                (f'%"{entity_id}"%', f"-{days} days"),
            ).fetchall()
            return [self._row_to_snapshot(row) for row in rows]
        finally:
            conn.close()

    def get_patterns_in_cycle(self, cycle_id: str) -> list[PatternSnapshot]:
        """Retrieve all patterns detected in a specific cycle."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM pattern_snapshots
                   WHERE cycle_id = ?
                   ORDER BY severity, pattern_name""",
                (cycle_id,),
            ).fetchall()
            return [self._row_to_snapshot(row) for row in rows]
        finally:
            conn.close()

    def get_recent_patterns(self, days: int = 7) -> list[PatternSnapshot]:
        """Retrieve patterns from the last N days."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM pattern_snapshots
                   WHERE detected_at >= datetime('now', ?)
                   ORDER BY detected_at DESC""",
                (f"-{days} days",),
            ).fetchall()
            return [self._row_to_snapshot(row) for row in rows]
        finally:
            conn.close()

    def get_pattern_history(self, pattern_id: str, cycles: int = 10) -> list[PatternSnapshot]:
        """Get history of a specific pattern across recent cycles."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM pattern_snapshots
                   WHERE pattern_id = ?
                   ORDER BY detected_at DESC
                   LIMIT ?""",
                (pattern_id, cycles),
            ).fetchall()
            return [self._row_to_snapshot(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> PatternSnapshot:
        d = dict(row)
        return PatternSnapshot(
            id=d["id"],
            detected_at=d["detected_at"],
            pattern_id=d["pattern_id"],
            pattern_name=d["pattern_name"],
            pattern_type=d["pattern_type"],
            severity=d["severity"],
            confidence=d.get("confidence", "medium"),
            entities_involved=json.loads(d["entities_involved"]),
            evidence=json.loads(d["evidence"]),
            cycle_id=d.get("cycle_id"),
        )


# =============================================================================
# COST PERSISTENCE
# =============================================================================


class CostPersistence:
    """Persist and retrieve cost-to-serve snapshots."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or paths.db_path()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def record_snapshot(self, snapshot: CostSnapshotRecord) -> None:
        """Record a cost snapshot."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO cost_snapshots
                   (id, computed_at, snapshot_type, entity_id,
                    effort_score, efficiency_ratio, profitability_band,
                    cost_drivers, data, cycle_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot.id,
                    snapshot.computed_at,
                    snapshot.snapshot_type,
                    snapshot.entity_id,
                    snapshot.effort_score,
                    snapshot.efficiency_ratio,
                    snapshot.profitability_band,
                    json.dumps(snapshot.cost_drivers),
                    json.dumps(snapshot.data),
                    snapshot.cycle_id,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error(
                "Failed to record cost snapshot for %s: %s",
                snapshot.entity_id,
                e,
            )
            raise
        finally:
            conn.close()

    def record_batch(self, snapshots: list[CostSnapshotRecord]) -> dict[str, int]:
        """Record multiple cost snapshots in a single transaction."""
        conn = self._connect()
        recorded = 0
        errors = 0
        try:
            for s in snapshots:
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO cost_snapshots
                           (id, computed_at, snapshot_type, entity_id,
                            effort_score, efficiency_ratio, profitability_band,
                            cost_drivers, data, cycle_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            s.id,
                            s.computed_at,
                            s.snapshot_type,
                            s.entity_id,
                            s.effort_score,
                            s.efficiency_ratio,
                            s.profitability_band,
                            json.dumps(s.cost_drivers),
                            json.dumps(s.data),
                            s.cycle_id,
                        ),
                    )
                    recorded += 1
                except sqlite3.Error as e:
                    logger.error("Failed to record cost snapshot %s: %s", s.entity_id, e)
                    errors += 1
            conn.commit()
        finally:
            conn.close()
        return {"recorded": recorded, "errors": errors}

    def get_entity_cost_history(self, entity_id: str, days: int = 30) -> list[CostSnapshotRecord]:
        """Get cost history for an entity over time."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM cost_snapshots
                   WHERE entity_id = ?
                     AND computed_at >= datetime('now', ?)
                   ORDER BY computed_at DESC""",
                (entity_id, f"-{days} days"),
            ).fetchall()
            return [self._row_to_snapshot(row) for row in rows]
        finally:
            conn.close()

    def get_latest_portfolio_snapshot(self) -> CostSnapshotRecord | None:
        """Get the most recent portfolio-level cost snapshot."""
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT * FROM cost_snapshots
                   WHERE snapshot_type = 'portfolio'
                   ORDER BY computed_at DESC LIMIT 1"""
            ).fetchone()
            return self._row_to_snapshot(row) if row else None
        finally:
            conn.close()

    def get_latest_entity_snapshot(self, entity_id: str) -> CostSnapshotRecord | None:
        """Get the most recent snapshot for a specific entity."""
        conn = self._connect()
        try:
            row = conn.execute(
                """SELECT * FROM cost_snapshots
                   WHERE entity_id = ?
                   ORDER BY computed_at DESC LIMIT 1""",
                (entity_id,),
            ).fetchone()
            return self._row_to_snapshot(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> CostSnapshotRecord:
        d = dict(row)
        return CostSnapshotRecord(
            id=d["id"],
            computed_at=d["computed_at"],
            snapshot_type=d["snapshot_type"],
            entity_id=d.get("entity_id"),
            effort_score=d.get("effort_score"),
            efficiency_ratio=d.get("efficiency_ratio"),
            profitability_band=d.get("profitability_band"),
            cost_drivers=json.loads(d.get("cost_drivers", "[]")),
            data=json.loads(d["data"]),
            cycle_id=d.get("cycle_id"),
        )


# =============================================================================
# INTELLIGENCE EVENTS
# =============================================================================


class IntelligenceEventStore:
    """Publish and consume intelligence events."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or paths.db_path()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def publish(self, event: IntelligenceEvent) -> None:
        """Publish an intelligence event."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO intelligence_events
                   (id, event_type, severity, entity_type, entity_id,
                    event_data, source_module, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.id,
                    event.event_type,
                    event.severity,
                    event.entity_type,
                    event.entity_id,
                    json.dumps(event.event_data),
                    event.source_module,
                    event.created_at,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to publish event %s: %s", event.event_type, e)
            raise
        finally:
            conn.close()

    def publish_batch(self, events: list[IntelligenceEvent]) -> dict[str, int]:
        """Publish multiple events in a single transaction."""
        conn = self._connect()
        published = 0
        errors = 0
        try:
            for ev in events:
                try:
                    conn.execute(
                        """INSERT INTO intelligence_events
                           (id, event_type, severity, entity_type, entity_id,
                            event_data, source_module, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            ev.id,
                            ev.event_type,
                            ev.severity,
                            ev.entity_type,
                            ev.entity_id,
                            json.dumps(ev.event_data),
                            ev.source_module,
                            ev.created_at,
                        ),
                    )
                    published += 1
                except sqlite3.Error as e:
                    logger.error("Failed to publish event: %s", e)
                    errors += 1
            conn.commit()
        finally:
            conn.close()
        return {"published": published, "errors": errors}

    def get_unconsumed(
        self,
        event_type: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[IntelligenceEvent]:
        """Get unconsumed events, optionally filtered."""
        conn = self._connect()
        try:
            query = "SELECT * FROM intelligence_events WHERE consumed_at IS NULL"
            params: list[Any] = []

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            if severity:
                query += " AND severity = ?"
                params.append(severity)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_event(row) for row in rows]
        finally:
            conn.close()

    def mark_consumed(self, event_id: str, consumer: str) -> bool:
        """Mark an event as consumed by a downstream consumer."""
        conn = self._connect()
        try:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                """UPDATE intelligence_events
                   SET consumed_at = ?, consumer = ?
                   WHERE id = ? AND consumed_at IS NULL""",
                (now, consumer, event_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_entity_events(
        self,
        entity_type: str,
        entity_id: str,
        days: int = 30,
    ) -> list[IntelligenceEvent]:
        """Get all events for an entity in a time range."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM intelligence_events
                   WHERE entity_type = ? AND entity_id = ?
                     AND created_at >= datetime('now', ?)
                   ORDER BY created_at DESC""",
                (entity_type, entity_id, f"-{days} days"),
            ).fetchall()
            return [self._row_to_event(row) for row in rows]
        finally:
            conn.close()

    def archive_old_events(self, days: int = 30) -> int:
        """
        Move consumed events older than N days to the archive table.

        Returns the count of archived events, or 0 if archive table
        does not exist (migration not yet run).
        """
        conn = self._connect()
        try:
            # Check if archive table exists
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "intelligence_events_archive" not in tables:
                logger.debug("Archive table does not exist, skipping cleanup")
                return 0

            cutoff = f"-{days} days"
            archived_at = datetime.now().isoformat()

            # Copy to archive
            conn.execute(
                """INSERT OR IGNORE INTO intelligence_events_archive
                   (id, event_type, severity, entity_type, entity_id,
                    event_data, source_module, created_at, consumed_at,
                    consumer, archived_at)
                   SELECT id, event_type, severity, entity_type, entity_id,
                          event_data, source_module, created_at, consumed_at,
                          consumer, ?
                   FROM intelligence_events
                   WHERE consumed_at IS NOT NULL
                     AND consumed_at < datetime('now', ?)""",
                (archived_at, cutoff),
            )

            # Delete from main table
            cursor = conn.execute(
                """DELETE FROM intelligence_events
                   WHERE consumed_at IS NOT NULL
                     AND consumed_at < datetime('now', ?)""",
                (cutoff,),
            )
            count = cursor.rowcount
            conn.commit()
            if count > 0:
                logger.info(f"Archived {count} consumed events older than {days} days")
            return count
        finally:
            conn.close()

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> IntelligenceEvent:
        d = dict(row)
        return IntelligenceEvent(
            id=d["id"],
            event_type=d["event_type"],
            severity=d["severity"],
            entity_type=d.get("entity_type"),
            entity_id=d.get("entity_id"),
            event_data=json.loads(d["event_data"]),
            source_module=d.get("source_module", "unknown"),
            created_at=d["created_at"],
            consumed_at=d.get("consumed_at"),
            consumer=d.get("consumer"),
        )


# =============================================================================
# HELPERS
# =============================================================================


def make_id() -> str:
    """Generate a unique ID for persistence records."""
    return str(uuid.uuid4())


def snapshot_from_pattern_evidence(
    pattern_dict: dict,
    cycle_id: str | None = None,
) -> PatternSnapshot:
    """Convert a PatternEvidence.to_dict() output to a PatternSnapshot for persistence."""
    return PatternSnapshot(
        id=make_id(),
        detected_at=pattern_dict.get("detected_at", datetime.now().isoformat()),
        pattern_id=pattern_dict["pattern_id"],
        pattern_name=pattern_dict["pattern_name"],
        pattern_type=pattern_dict.get("pattern_type", "unknown"),
        severity=pattern_dict.get("severity", "informational"),
        confidence=pattern_dict.get("confidence", "medium"),
        entities_involved=pattern_dict.get("entities_involved", []),
        evidence={
            "metrics": pattern_dict.get("metrics", {}),
            "evidence_narrative": pattern_dict.get("evidence_narrative", ""),
            "operational_meaning": pattern_dict.get("operational_meaning", ""),
            "implied_action": pattern_dict.get("implied_action", ""),
            "supporting_signals": pattern_dict.get("supporting_signals", []),
        },
        cycle_id=cycle_id,
    )


def snapshot_from_cost_profile(
    cost_dict: dict,
    snapshot_type: str,
    entity_id: str | None = None,
    cycle_id: str | None = None,
) -> CostSnapshotRecord:
    """Convert a CostProfile.to_dict() output to a CostSnapshotRecord."""
    return CostSnapshotRecord(
        id=make_id(),
        computed_at=datetime.now().isoformat(),
        snapshot_type=snapshot_type,
        entity_id=entity_id,
        effort_score=cost_dict.get("effort_score"),
        efficiency_ratio=cost_dict.get("efficiency_ratio"),
        profitability_band=cost_dict.get("profitability_band"),
        cost_drivers=cost_dict.get("cost_drivers", []),
        data=cost_dict,
        cycle_id=cycle_id,
    )


def event_from_signal_change(
    signal_id: str,
    entity_type: str,
    entity_id: str,
    severity: str,
    change_type: str,  # 'new' | 'escalated' | 'cleared'
    details: dict | None = None,
) -> IntelligenceEvent:
    """Create an intelligence event from a signal state change."""
    event_type_map = {
        "new": "signal_fired",
        "escalated": "signal_escalated",
        "cleared": "signal_cleared",
    }
    return IntelligenceEvent(
        id=make_id(),
        event_type=event_type_map.get(change_type, f"signal_{change_type}"),
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        event_data={
            "signal_id": signal_id,
            "change_type": change_type,
            **(details or {}),
        },
        source_module="signals",
        created_at=datetime.now().isoformat(),
    )


def event_from_pattern(
    pattern_dict: dict,
    change_type: str = "detected",  # 'detected' | 'resolved'
) -> IntelligenceEvent:
    """Create an intelligence event from a pattern detection."""
    event_type_map = {
        "detected": "pattern_detected",
        "resolved": "pattern_resolved",
    }
    # Derive entity from first entity involved
    entities = pattern_dict.get("entities_involved", [])
    entity_type = entities[0].get("type") if entities else None
    entity_id = entities[0].get("id") if entities else None

    return IntelligenceEvent(
        id=make_id(),
        event_type=event_type_map.get(change_type, f"pattern_{change_type}"),
        severity=pattern_dict.get("severity", "informational"),
        entity_type=entity_type,
        entity_id=entity_id,
        event_data={
            "pattern_id": pattern_dict.get("pattern_id"),
            "pattern_name": pattern_dict.get("pattern_name"),
            "change_type": change_type,
            "confidence": pattern_dict.get("confidence"),
        },
        source_module="patterns",
        created_at=datetime.now().isoformat(),
    )
