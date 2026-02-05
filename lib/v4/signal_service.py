"""
Time OS V4 - Signal Service

Manages signal definitions, detector runs, and signal storage.
Signals are the atomic intelligence units that feed into Proposals.
"""

import sqlite3
import json
import uuid
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import os

log = logging.getLogger("moh_time_os.v4.signal_service")

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'moh_time_os.db')


class SignalService:
    """
    Service for managing signals - detected patterns/events from artifacts.
    
    Signal types include:
    - risk: potential problems
    - opportunity: potential value
    - anomaly: unexpected patterns
    - commitment: detected promises
    - deadline: approaching/missed deadlines
    - health: relationship/project health indicators
    - protocol_violation: process violations
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_tables()
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)
    
    def _generate_id(self, prefix: str = 'sig') -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"
    
    def _ensure_tables(self):
        """Ensure signal tables exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Signal definitions (types of signals we can detect)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signal_definitions (
                    signal_type TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,  -- risk, opportunity, health, protocol, deadline, commitment
                    required_evidence_types TEXT NOT NULL,  -- JSON array
                    formula_version TEXT NOT NULL,
                    min_link_confidence REAL NOT NULL DEFAULT 0.7,
                    min_interpretation_confidence REAL NOT NULL DEFAULT 0.6,
                    priority_weight REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            
            # Detector versions (versioned detection algorithms)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detector_versions (
                    detector_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    description TEXT,
                    parameters TEXT NOT NULL,  -- JSON
                    released_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (detector_id, version)
                )
            """)
            
            # Detector runs (audit of when detectors ran)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detector_runs (
                    run_id TEXT PRIMARY KEY,
                    detector_id TEXT NOT NULL,
                    detector_version TEXT NOT NULL,
                    scope TEXT NOT NULL,  -- JSON: what entities/time window
                    inputs_hash TEXT NOT NULL,
                    ran_at TEXT NOT NULL DEFAULT (datetime('now')),
                    duration_ms INTEGER,
                    output_counts TEXT NOT NULL,  -- JSON
                    status TEXT NOT NULL DEFAULT 'completed'
                )
            """)
            
            # Signals (detected instances)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    signal_type TEXT NOT NULL,
                    entity_ref_type TEXT NOT NULL,
                    entity_ref_id TEXT NOT NULL,
                    value TEXT NOT NULL,  -- JSON with signal-specific data
                    severity TEXT NOT NULL DEFAULT 'medium',  -- low, medium, high, critical
                    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
                    interpretation_confidence REAL NOT NULL,
                    linkage_confidence_floor REAL NOT NULL,
                    evidence_excerpt_ids TEXT NOT NULL,  -- JSON array
                    evidence_artifact_ids TEXT NOT NULL,  -- JSON array
                    detector_id TEXT NOT NULL,
                    detector_version TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',  -- active, consumed, dismissed, expired
                    consumed_by_proposal_id TEXT,
                    expires_at TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_entity ON signals(entity_ref_type, entity_ref_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_severity ON signals(severity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_detected ON signals(detected_at)")
            
            # Signal feedback (for learning)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signal_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,  -- confirmed, rejected, adjusted
                    actor TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    # ===========================================
    # Signal Definition Management
    # ===========================================
    
    def register_signal_type(
        self,
        signal_type: str,
        description: str,
        category: str,
        required_evidence_types: List[str],
        formula_version: str = '1.0',
        min_link_confidence: float = 0.7,
        min_interpretation_confidence: float = 0.6,
        priority_weight: float = 1.0
    ) -> Dict[str, Any]:
        """Register a new signal type definition."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO signal_definitions
                (signal_type, description, category, required_evidence_types, 
                 formula_version, min_link_confidence, min_interpretation_confidence,
                 priority_weight, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                signal_type, description, category, 
                json.dumps(required_evidence_types), formula_version,
                min_link_confidence, min_interpretation_confidence, priority_weight
            ))
            conn.commit()
            return {'status': 'registered', 'signal_type': signal_type}
        finally:
            conn.close()
    
    def get_signal_definitions(self) -> List[Dict[str, Any]]:
        """Get all signal type definitions."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT signal_type, description, category, required_evidence_types,
                       formula_version, min_link_confidence, min_interpretation_confidence,
                       priority_weight
                FROM signal_definitions
            """)
            return [{
                'signal_type': row[0],
                'description': row[1],
                'category': row[2],
                'required_evidence_types': json.loads(row[3]),
                'formula_version': row[4],
                'min_link_confidence': row[5],
                'min_interpretation_confidence': row[6],
                'priority_weight': row[7]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    # ===========================================
    # Detector Management
    # ===========================================
    
    def register_detector_version(
        self,
        detector_id: str,
        version: str,
        description: str,
        parameters: Dict
    ) -> Dict[str, Any]:
        """Register a detector version."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO detector_versions
                (detector_id, version, description, parameters, released_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (detector_id, version, description, json.dumps(parameters)))
            conn.commit()
            return {'status': 'registered', 'detector_id': detector_id, 'version': version}
        finally:
            conn.close()
    
    def log_detector_run(
        self,
        detector_id: str,
        detector_version: str,
        scope: Dict,
        inputs_hash: str,
        output_counts: Dict,
        duration_ms: int = None,
        status: str = 'completed'
    ) -> str:
        """Log a detector run for audit."""
        run_id = self._generate_id('run')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO detector_runs
                (run_id, detector_id, detector_version, scope, inputs_hash,
                 ran_at, duration_ms, output_counts, status)
                VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?)
            """, (
                run_id, detector_id, detector_version, json.dumps(scope),
                inputs_hash, duration_ms, json.dumps(output_counts), status
            ))
            conn.commit()
            return run_id
        finally:
            conn.close()
    
    # ===========================================
    # Signal Creation & Retrieval
    # ===========================================
    
    def create_signal(
        self,
        signal_type: str,
        entity_ref_type: str,
        entity_ref_id: str,
        value: Dict,
        severity: str,
        interpretation_confidence: float,
        linkage_confidence_floor: float,
        evidence_excerpt_ids: List[str],
        evidence_artifact_ids: List[str],
        detector_id: str,
        detector_version: str,
        expires_at: str = None
    ) -> Dict[str, Any]:
        """
        Create a new signal.
        
        Args:
            signal_type: Type of signal (must be registered)
            entity_ref_type: Type of entity this signal is about
            entity_ref_id: ID of entity
            value: Signal-specific data (JSON-serializable)
            severity: low, medium, high, critical
            interpretation_confidence: How confident we are in the interpretation
            linkage_confidence_floor: Minimum confidence of links used
            evidence_excerpt_ids: List of excerpt IDs as proof
            evidence_artifact_ids: List of artifact IDs as proof
            detector_id: Which detector created this
            detector_version: Version of detector
            expires_at: Optional expiration time
            
        Returns:
            Created signal record
        """
        signal_id = self._generate_id('sig')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO signals
                (signal_id, signal_type, entity_ref_type, entity_ref_id, value,
                 severity, interpretation_confidence, linkage_confidence_floor,
                 evidence_excerpt_ids, evidence_artifact_ids, detector_id,
                 detector_version, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                signal_id, signal_type, entity_ref_type, entity_ref_id,
                json.dumps(value), severity, interpretation_confidence,
                linkage_confidence_floor, json.dumps(evidence_excerpt_ids),
                json.dumps(evidence_artifact_ids), detector_id, detector_version,
                expires_at
            ))
            conn.commit()
            
            return {
                'signal_id': signal_id,
                'status': 'created',
                'signal_type': signal_type,
                'severity': severity
            }
        finally:
            conn.close()
    
    def get_signal(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """Get a signal by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT signal_id, signal_type, entity_ref_type, entity_ref_id, value,
                       severity, detected_at, interpretation_confidence, linkage_confidence_floor,
                       evidence_excerpt_ids, evidence_artifact_ids, detector_id,
                       detector_version, status, consumed_by_proposal_id, expires_at
                FROM signals WHERE signal_id = ?
            """, (signal_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'signal_id': row[0],
                'signal_type': row[1],
                'entity_ref_type': row[2],
                'entity_ref_id': row[3],
                'value': json.loads(row[4]),
                'severity': row[5],
                'detected_at': row[6],
                'interpretation_confidence': row[7],
                'linkage_confidence_floor': row[8],
                'evidence_excerpt_ids': json.loads(row[9]),
                'evidence_artifact_ids': json.loads(row[10]),
                'detector_id': row[11],
                'detector_version': row[12],
                'status': row[13],
                'consumed_by_proposal_id': row[14],
                'expires_at': row[15]
            }
        finally:
            conn.close()
    
    def find_signals(
        self,
        signal_type: str = None,
        entity_ref_type: str = None,
        entity_ref_id: str = None,
        status: str = 'active',
        severity: str = None,
        category: str = None,
        since: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for signals with filters."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT s.signal_id, s.signal_type, s.entity_ref_type, s.entity_ref_id,
                       s.value, s.severity, s.detected_at, s.interpretation_confidence,
                       s.status, d.category
                FROM signals s
                LEFT JOIN signal_definitions d ON s.signal_type = d.signal_type
                WHERE 1=1
            """
            params = []
            
            if signal_type:
                query += " AND s.signal_type = ?"
                params.append(signal_type)
            if entity_ref_type:
                query += " AND s.entity_ref_type = ?"
                params.append(entity_ref_type)
            if entity_ref_id:
                query += " AND s.entity_ref_id = ?"
                params.append(entity_ref_id)
            if status:
                query += " AND s.status = ?"
                params.append(status)
            if severity:
                query += " AND s.severity = ?"
                params.append(severity)
            if category:
                query += " AND d.category = ?"
                params.append(category)
            if since:
                query += " AND s.detected_at >= ?"
                params.append(since)
            
            query += " ORDER BY s.detected_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            return [{
                'signal_id': row[0],
                'signal_type': row[1],
                'entity_ref_type': row[2],
                'entity_ref_id': row[3],
                'value': json.loads(row[4]),
                'severity': row[5],
                'detected_at': row[6],
                'interpretation_confidence': row[7],
                'status': row[8],
                'category': row[9]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_active_signals_for_entity(
        self,
        entity_type: str,
        entity_id: str
    ) -> List[Dict[str, Any]]:
        """Get all active signals for an entity."""
        return self.find_signals(
            entity_ref_type=entity_type,
            entity_ref_id=entity_id,
            status='active'
        )
    
    def mark_signal_consumed(
        self,
        signal_id: str,
        proposal_id: str
    ) -> Dict[str, Any]:
        """Mark a signal as consumed by a proposal."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE signals
                SET status = 'consumed', consumed_by_proposal_id = ?
                WHERE signal_id = ? AND status = 'active'
            """, (proposal_id, signal_id))
            
            if cursor.rowcount == 0:
                return {'status': 'error', 'error': 'Signal not found or not active'}
            
            conn.commit()
            return {'status': 'consumed', 'signal_id': signal_id}
        finally:
            conn.close()
    
    def dismiss_signal(
        self,
        signal_id: str,
        actor: str,
        note: str = None
    ) -> Dict[str, Any]:
        """Dismiss a signal (user feedback)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE signals SET status = 'dismissed'
                WHERE signal_id = ? AND status = 'active'
            """, (signal_id,))
            
            if cursor.rowcount == 0:
                return {'status': 'error', 'error': 'Signal not found or not active'}
            
            # Log feedback
            feedback_id = self._generate_id('fb')
            cursor.execute("""
                INSERT INTO signal_feedback
                (feedback_id, signal_id, feedback_type, actor, note, created_at)
                VALUES (?, ?, 'rejected', ?, ?, datetime('now'))
            """, (feedback_id, signal_id, actor, note))
            
            conn.commit()
            return {'status': 'dismissed', 'signal_id': signal_id}
        finally:
            conn.close()
    
    # ===========================================
    # Statistics
    # ===========================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get signal statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Count by status
            cursor.execute("""
                SELECT status, COUNT(*) FROM signals GROUP BY status
            """)
            stats['by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Count by type
            cursor.execute("""
                SELECT signal_type, COUNT(*) FROM signals
                WHERE status = 'active'
                GROUP BY signal_type ORDER BY COUNT(*) DESC
            """)
            stats['active_by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Count by severity
            cursor.execute("""
                SELECT severity, COUNT(*) FROM signals
                WHERE status = 'active'
                GROUP BY severity
            """)
            stats['active_by_severity'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Detector runs
            cursor.execute("SELECT COUNT(*) FROM detector_runs")
            stats['total_detector_runs'] = cursor.fetchone()[0]
            
            # Signal definitions
            cursor.execute("SELECT COUNT(*) FROM signal_definitions")
            stats['registered_signal_types'] = cursor.fetchone()[0]
            
            return stats
        finally:
            conn.close()
    
    # ===========================================
    # Commitment Persistence (Gap Fix #2)
    # ===========================================
    
    def persist_commitment_signals(self) -> Dict[str, Any]:
        """
        Persist commitment signals to the commitments table.
        Extracts commitment data from signals and creates commitment records.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        stats = {'processed': 0, 'created': 0, 'skipped': 0, 'errors': 0}
        
        try:
            # Find commitment signals not yet persisted
            cursor.execute("""
                SELECT s.signal_id, s.signal_type, s.entity_ref_type, s.entity_ref_id,
                       s.value, s.interpretation_confidence, s.evidence_excerpt_ids
                FROM signals s
                WHERE s.signal_type IN ('commitment_made', 'commitment_detected')
                  AND s.status = 'active'
                  AND NOT EXISTS (
                      SELECT 1 FROM commitments c 
                      WHERE c.scope_ref_id = s.entity_ref_id
                        AND c.commitment_text = json_extract(s.value, '$.commitment_text')
                  )
            """)
            
            for row in cursor.fetchall():
                signal_id, signal_type, ref_type, ref_id, value_json, confidence, evidence_json = row
                stats['processed'] += 1
                
                try:
                    value = json.loads(value_json)
                    evidence_ids = json.loads(evidence_json) if evidence_json else []
                    
                    commitment_text = value.get('commitment_text', '')
                    if not commitment_text or len(commitment_text) < 3:
                        stats['skipped'] += 1
                        continue
                    
                    # Extract actor
                    actor_id = value.get('actor_id', '')
                    actor_type = 'person' if actor_id.startswith('idp_') else 'unknown'
                    
                    # Parse due date if present
                    due_at = value.get('due_at') or value.get('due_date')
                    
                    commitment_id = f"cmt_{uuid.uuid4().hex[:16]}"
                    
                    cursor.execute("""
                        INSERT INTO commitments
                        (commitment_id, scope_ref_type, scope_ref_id, committed_by_type,
                         committed_by_id, commitment_text, due_at, confidence,
                         evidence_excerpt_ids, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', datetime('now'))
                    """, (
                        commitment_id, ref_type, ref_id, actor_type, actor_id,
                        commitment_text, due_at, confidence, json.dumps(evidence_ids)
                    ))
                    stats['created'] += 1
                    
                except Exception as e:
                    log.warning(f"Error persisting commitment from signal {signal_id}: {e}")
                    stats['errors'] += 1
            
            conn.commit()
            log.info(f"Commitment persistence: {stats}")
            return stats
            
        finally:
            conn.close()
    
    # ===========================================
    # Feedback Capture (Gap Fix #3)
    # ===========================================
    
    def record_feedback(
        self,
        signal_id: str,
        feedback_type: str,  # dismiss, snooze, confirm, reject
        actor: str,
        reason: str = None,
        snooze_until: str = None
    ) -> Dict[str, Any]:
        """
        Record feedback on a signal (dismiss/snooze/confirm/reject).
        Persists to signal_feedback table for audit trail.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            feedback_id = f"fb_{uuid.uuid4().hex[:16]}"
            
            cursor.execute("""
                INSERT INTO signal_feedback
                (feedback_id, signal_id, feedback_type, actor, reason, 
                 snooze_until, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (feedback_id, signal_id, feedback_type, actor, reason, snooze_until))
            
            # Update signal status based on feedback
            if feedback_type == 'dismiss':
                cursor.execute(
                    "UPDATE signals SET status = 'dismissed' WHERE signal_id = ?",
                    (signal_id,)
                )
            elif feedback_type == 'snooze':
                cursor.execute(
                    "UPDATE signals SET status = 'snoozed', expires_at = ? WHERE signal_id = ?",
                    (snooze_until, signal_id)
                )
            elif feedback_type == 'confirm':
                cursor.execute(
                    "UPDATE signals SET status = 'confirmed' WHERE signal_id = ?",
                    (signal_id,)
                )
            elif feedback_type == 'reject':
                cursor.execute(
                    "UPDATE signals SET status = 'rejected' WHERE signal_id = ?",
                    (signal_id,)
                )
            
            conn.commit()
            
            return {
                'status': 'recorded',
                'feedback_id': feedback_id,
                'signal_id': signal_id,
                'feedback_type': feedback_type
            }
            
        finally:
            conn.close()
    
    def get_feedback_for_signal(self, signal_id: str) -> List[Dict[str, Any]]:
        """Get all feedback recorded for a signal."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT feedback_id, feedback_type, actor, reason, 
                       snooze_until, created_at
                FROM signal_feedback
                WHERE signal_id = ?
                ORDER BY created_at DESC
            """, (signal_id,))
            
            return [{
                'feedback_id': row[0],
                'feedback_type': row[1],
                'actor': row[2],
                'reason': row[3],
                'snooze_until': row[4],
                'created_at': row[5]
            } for row in cursor.fetchall()]
            
        finally:
            conn.close()


# Singleton
_signal_service = None

def get_signal_service() -> SignalService:
    global _signal_service
    if _signal_service is None:
        _signal_service = SignalService()
    return _signal_service
