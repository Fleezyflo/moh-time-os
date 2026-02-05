"""
Time OS V4 - Entity Link Service

Handles explicit linking between artifacts and domain entities.
Provides confidence scoring and Fix Data queue generation.
"""

import sqlite3
import json
import uuid
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'moh_time_os.db')


class EntityLinkService:
    """Service for managing entity links and Fix Data queue."""
    
    ENTITY_TYPES = {
        'client', 'brand', 'engagement', 'project', 'task',
        'person', 'invoice', 'thread', 'meeting', 'document'
    }
    
    LINK_METHODS = {
        'headers',       # Email/message headers (To, From, CC)
        'participants',  # Meeting/chat participants
        'naming',        # Pattern matching in subject/title
        'rules',         # Explicit rules/recognizers
        'embedding',     # Semantic similarity
        'nlp',           # NLP extraction
        'user_confirmed' # Manual confirmation
    }
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.6
    LOW_CONFIDENCE = 0.4
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)
    
    def _generate_id(self, prefix: str = 'lnk') -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"
    
    # ===========================================
    # Link Creation
    # ===========================================
    
    def create_link(
        self,
        from_artifact_id: str,
        to_entity_type: str,
        to_entity_id: str,
        method: str,
        confidence: float,
        confidence_reasons: Optional[List[str]] = None,
        auto_confirm: bool = False
    ) -> Dict[str, Any]:
        """
        Create a link between an artifact and an entity.
        
        Args:
            from_artifact_id: Source artifact
            to_entity_type: Target entity type
            to_entity_id: Target entity ID
            method: How the link was determined
            confidence: Confidence score 0-1
            confidence_reasons: Explanations for confidence
            auto_confirm: Auto-confirm if high confidence
            
        Returns:
            Created or updated link
        """
        if to_entity_type not in self.ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {to_entity_type}")
        if method not in self.LINK_METHODS:
            raise ValueError(f"Invalid method: {method}")
        
        link_id = self._generate_id('lnk')
        status = 'confirmed' if (auto_confirm and confidence >= self.HIGH_CONFIDENCE) else 'proposed'
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Check for existing link
            cursor.execute("""
                SELECT link_id, confidence, status, method
                FROM entity_links
                WHERE from_artifact_id = ? AND to_entity_type = ? AND to_entity_id = ?
            """, (from_artifact_id, to_entity_type, to_entity_id))
            
            existing = cursor.fetchone()
            if existing:
                # Update if new confidence is higher
                if confidence > existing[1]:
                    cursor.execute("""
                        UPDATE entity_links 
                        SET confidence = ?, confidence_reasons = ?, method = ?, updated_at = datetime('now')
                        WHERE link_id = ?
                    """, (confidence, json.dumps(confidence_reasons or []), method, existing[0]))
                    conn.commit()
                    return {
                        'link_id': existing[0], 
                        'status': 'updated', 
                        'confidence': confidence,
                        'link_status': existing[2]
                    }
                return {
                    'link_id': existing[0], 
                    'status': 'existing', 
                    'confidence': existing[1],
                    'link_status': existing[2]
                }
            
            # Create new link
            cursor.execute("""
                INSERT INTO entity_links
                (link_id, from_artifact_id, to_entity_type, to_entity_id, method,
                 confidence, confidence_reasons, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                link_id, from_artifact_id, to_entity_type, to_entity_id, method,
                confidence, json.dumps(confidence_reasons or []), status
            ))
            
            # Generate Fix Data if low confidence
            if confidence < self.MEDIUM_CONFIDENCE:
                self._create_fix_data_item(
                    cursor, 'ambiguous_link',
                    f"Low confidence ({confidence:.0%}) link from artifact to {to_entity_type}",
                    {
                        'artifact_id': from_artifact_id,
                        'entity_type': to_entity_type,
                        'entity_id': to_entity_id,
                        'confidence': confidence,
                        'method': method,
                        'reasons': confidence_reasons
                    },
                    artifact_id=from_artifact_id,
                    entity_type=to_entity_type,
                    entity_id=to_entity_id
                )
            
            conn.commit()
            return {
                'link_id': link_id,
                'status': 'created',
                'confidence': confidence,
                'link_status': status
            }
            
        finally:
            conn.close()
    
    def confirm_link(self, link_id: str, confirmed_by: str) -> Dict[str, Any]:
        """Confirm a proposed link."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE entity_links
                SET status = 'confirmed', confirmed_by = ?, confirmed_at = datetime('now'), updated_at = datetime('now')
                WHERE link_id = ? AND status = 'proposed'
            """, (confirmed_by, link_id))
            
            if cursor.rowcount == 0:
                return {'status': 'error', 'error': 'Link not found or already confirmed'}
            
            conn.commit()
            return {'status': 'confirmed', 'link_id': link_id}
        finally:
            conn.close()
    
    def reject_link(self, link_id: str, rejected_by: str) -> Dict[str, Any]:
        """Reject a proposed link."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE entity_links
                SET status = 'rejected', confirmed_by = ?, confirmed_at = datetime('now'), updated_at = datetime('now')
                WHERE link_id = ? AND status = 'proposed'
            """, (rejected_by, link_id))
            
            if cursor.rowcount == 0:
                return {'status': 'error', 'error': 'Link not found or not in proposed state'}
            
            conn.commit()
            return {'status': 'rejected', 'link_id': link_id}
        finally:
            conn.close()
    
    # ===========================================
    # Link Retrieval
    # ===========================================
    
    def get_links_for_artifact(
        self, 
        artifact_id: str,
        status: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Get all links from an artifact."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT link_id, to_entity_type, to_entity_id, method, 
                       confidence, confidence_reasons, status, created_at
                FROM entity_links 
                WHERE from_artifact_id = ? AND confidence >= ?
            """
            params = [artifact_id, min_confidence]
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY confidence DESC"
            cursor.execute(query, params)
            
            return [{
                'link_id': row[0],
                'to_entity_type': row[1],
                'to_entity_id': row[2],
                'method': row[3],
                'confidence': row[4],
                'confidence_reasons': json.loads(row[5] or '[]'),
                'status': row[6],
                'created_at': row[7]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_links_to_entity(
        self,
        entity_type: str,
        entity_id: str,
        status: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Get all links to an entity."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT l.link_id, l.from_artifact_id, l.method, l.confidence,
                       l.confidence_reasons, l.status, l.created_at,
                       a.source, a.type, a.occurred_at
                FROM entity_links l
                JOIN artifacts a ON l.from_artifact_id = a.artifact_id
                WHERE l.to_entity_type = ? AND l.to_entity_id = ? AND l.confidence >= ?
            """
            params = [entity_type, entity_id, min_confidence]
            
            if status:
                query += " AND l.status = ?"
                params.append(status)
            
            query += " ORDER BY a.occurred_at DESC"
            cursor.execute(query, params)
            
            return [{
                'link_id': row[0],
                'from_artifact_id': row[1],
                'method': row[2],
                'confidence': row[3],
                'confidence_reasons': json.loads(row[4] or '[]'),
                'status': row[5],
                'created_at': row[6],
                'artifact_source': row[7],
                'artifact_type': row[8],
                'artifact_occurred_at': row[9]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_proposed_links(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get links awaiting confirmation."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT l.link_id, l.from_artifact_id, l.to_entity_type, l.to_entity_id,
                       l.method, l.confidence, l.confidence_reasons, l.created_at,
                       a.source, a.type
                FROM entity_links l
                JOIN artifacts a ON l.from_artifact_id = a.artifact_id
                WHERE l.status = 'proposed'
                ORDER BY l.confidence DESC, l.created_at DESC
                LIMIT ?
            """, (limit,))
            
            return [{
                'link_id': row[0],
                'from_artifact_id': row[1],
                'to_entity_type': row[2],
                'to_entity_id': row[3],
                'method': row[4],
                'confidence': row[5],
                'confidence_reasons': json.loads(row[6] or '[]'),
                'created_at': row[7],
                'artifact_source': row[8],
                'artifact_type': row[9]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    # ===========================================
    # Fix Data Queue
    # ===========================================
    
    def _create_fix_data_item(
        self,
        cursor,
        fix_type: str,
        description: str,
        context: Dict,
        severity: str = 'medium',
        artifact_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None
    ):
        """Internal: Create a fix data queue item."""
        fix_id = self._generate_id('fix')
        
        cursor.execute("""
            INSERT INTO fix_data_queue
            (fix_id, fix_type, severity, entity_type, entity_id, artifact_id,
             description, context, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """, (
            fix_id, fix_type, severity, entity_type, entity_id, artifact_id,
            description, json.dumps(context)
        ))
        
        return fix_id
    
    def create_fix_data(
        self,
        fix_type: str,
        description: str,
        context: Dict,
        severity: str = 'medium',
        artifact_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        suggested_actions: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create a Fix Data queue item.
        
        Args:
            fix_type: Type of fix needed
            description: Human-readable description
            context: Detailed context
            severity: low, medium, high, critical
            artifact_id: Related artifact
            entity_type: Related entity type
            entity_id: Related entity ID
            suggested_actions: Possible fixes
            
        Returns:
            Created fix data item
        """
        fix_id = self._generate_id('fix')
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO fix_data_queue
                (fix_id, fix_type, severity, entity_type, entity_id, artifact_id,
                 description, context, suggested_actions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                fix_id, fix_type, severity, entity_type, entity_id, artifact_id,
                description, json.dumps(context), json.dumps(suggested_actions or [])
            ))
            
            conn.commit()
            return {'fix_id': fix_id, 'status': 'created'}
        finally:
            conn.close()
    
    def get_fix_data_queue(
        self,
        status: str = 'open',
        fix_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get Fix Data queue items."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT fix_id, fix_type, severity, entity_type, entity_id, artifact_id,
                       description, context, suggested_actions, status, created_at
                FROM fix_data_queue WHERE status = ?
            """
            params = [status]
            
            if fix_type:
                query += " AND fix_type = ?"
                params.append(fix_type)
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            
            query += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            return [{
                'fix_id': row[0],
                'fix_type': row[1],
                'severity': row[2],
                'entity_type': row[3],
                'entity_id': row[4],
                'artifact_id': row[5],
                'description': row[6],
                'context': json.loads(row[7] or '{}'),
                'suggested_actions': json.loads(row[8] or '[]'),
                'status': row[9],
                'created_at': row[10]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def resolve_fix_data(
        self,
        fix_id: str,
        resolved_by: str,
        resolution_notes: str
    ) -> Dict[str, Any]:
        """Mark a fix data item as resolved."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE fix_data_queue
                SET status = 'resolved', resolved_by = ?, resolved_at = datetime('now'),
                    resolution_notes = ?, updated_at = datetime('now')
                WHERE fix_id = ? AND status = 'open'
            """, (resolved_by, resolution_notes, fix_id))
            
            if cursor.rowcount == 0:
                return {'status': 'error', 'error': 'Fix item not found or already resolved'}
            
            conn.commit()
            return {'status': 'resolved', 'fix_id': fix_id}
        finally:
            conn.close()
    
    # ===========================================
    # Statistics
    # ===========================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get entity link statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Link counts by status
            cursor.execute("""
                SELECT status, COUNT(*) FROM entity_links GROUP BY status
            """)
            stats['links_by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Link counts by entity type
            cursor.execute("""
                SELECT to_entity_type, COUNT(*) FROM entity_links 
                WHERE status != 'rejected'
                GROUP BY to_entity_type ORDER BY COUNT(*) DESC
            """)
            stats['links_by_entity_type'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Link counts by method
            cursor.execute("""
                SELECT method, COUNT(*) FROM entity_links 
                WHERE status != 'rejected'
                GROUP BY method ORDER BY COUNT(*) DESC
            """)
            stats['links_by_method'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Confidence distribution
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN confidence >= 0.85 THEN 'high'
                        WHEN confidence >= 0.6 THEN 'medium'
                        WHEN confidence >= 0.4 THEN 'low'
                        ELSE 'very_low'
                    END as band,
                    COUNT(*)
                FROM entity_links WHERE status != 'rejected'
                GROUP BY band
            """)
            stats['links_by_confidence_band'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Fix data queue
            cursor.execute("""
                SELECT status, COUNT(*) FROM fix_data_queue GROUP BY status
            """)
            stats['fix_data_by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT fix_type, COUNT(*) FROM fix_data_queue WHERE status = 'open'
                GROUP BY fix_type ORDER BY COUNT(*) DESC
            """)
            stats['open_fixes_by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            return stats
        finally:
            conn.close()


# Singleton
_entity_link_service = None

def get_entity_link_service() -> EntityLinkService:
    global _entity_link_service
    if _entity_link_service is None:
        _entity_link_service = EntityLinkService()
    return _entity_link_service
