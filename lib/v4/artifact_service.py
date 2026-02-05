"""
Time OS V4 - Artifact Service

Handles creation and retrieval of artifacts (normalized evidence stream).
Wraps raw data from collectors into trackable, linkable artifacts.
"""

import sqlite3
import hashlib
import json
import uuid
import base64
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import os

from cryptography.fernet import Fernet

log = logging.getLogger("moh_time_os.v4.artifact_service")

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'moh_time_os.db')
KEY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.blob_key')


def _get_or_create_key() -> bytes:
    """Get encryption key, creating if needed."""
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, 'rb') as f:
            return f.read()
    
    # Create new key
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    with open(KEY_PATH, 'wb') as f:
        f.write(key)
    os.chmod(KEY_PATH, 0o600)  # Owner read/write only
    log.info("Created new blob encryption key")
    return key


# Initialize encryption
_FERNET = None

def _get_fernet() -> Fernet:
    """Get Fernet instance (lazy init)."""
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_get_or_create_key())
    return _FERNET


def decrypt_blob_payload(payload_data: str) -> str:
    """
    Decrypt a blob payload if encrypted, otherwise return as-is.
    Module-level function for use by other services.
    """
    # Check if encrypted (Fernet tokens start with gAAAAA)
    if payload_data.startswith('Z0FBQUFB') or payload_data.startswith('gAAAAA'):
        fernet = _get_fernet()
        encrypted = base64.b64decode(payload_data.encode('utf-8'))
        return fernet.decrypt(encrypted).decode('utf-8')
    return payload_data


class ArtifactService:
    """Service for managing artifacts and evidence."""
    
    VALID_SOURCES = {
        'gmail', 'gchat', 'calendar', 'asana', 'docs', 'sheets', 
        'drive', 'xero', 'minutes_gemini', 'manual', 'system'
    }
    
    VALID_TYPES = {
        'message', 'thread', 'calendar_event', 'meeting', 'minutes',
        'task', 'task_update', 'doc_update', 'invoice', 'payment',
        'project_update', 'client_update', 'person_update', 'note'
    }
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
    
    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)
    
    def _hash_content(self, content: str) -> str:
        """Generate SHA256 hash of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _generate_id(self) -> str:
        """Generate a unique artifact ID."""
        return f"art_{uuid.uuid4().hex[:16]}"
    
    def _encrypt_payload(self, payload_json: str) -> str:
        """Encrypt payload for storage. Returns base64-encoded ciphertext."""
        fernet = _get_fernet()
        encrypted = fernet.encrypt(payload_json.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')
    
    def _decrypt_payload(self, encrypted_b64: str) -> str:
        """Decrypt payload from storage."""
        fernet = _get_fernet()
        encrypted = base64.b64decode(encrypted_b64.encode('utf-8'))
        return fernet.decrypt(encrypted).decode('utf-8')
    
    def _is_encrypted(self, payload: str) -> bool:
        """Check if payload appears to be encrypted (base64 Fernet token)."""
        try:
            # Fernet tokens start with 'gAAAAA' when base64 encoded
            return payload.startswith('Z0FBQUFB') or payload.startswith('gAAAAA')
        except:
            return False
    
    def get_blob_payload(self, blob_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt a blob payload by ID.
        Use this instead of direct SQL queries to handle encryption.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "SELECT payload FROM artifact_blobs WHERE blob_id = ?",
                (blob_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            payload_data = row[0]
            # Decrypt if encrypted
            if self._is_encrypted(payload_data):
                payload_data = self._decrypt_payload(payload_data)
            
            return json.loads(payload_data)
        finally:
            conn.close()
    
    def create_artifact(
        self,
        source: str,
        source_id: str,
        artifact_type: str,
        occurred_at: str,
        payload: Dict[str, Any],
        actor_person_id: Optional[str] = None,
        visibility_tags: Optional[List[str]] = None,
        store_blob: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new artifact from raw data.
        
        Args:
            source: Source system (gmail, asana, etc.)
            source_id: Stable upstream identifier
            artifact_type: Type of artifact
            occurred_at: When the event occurred (ISO format)
            payload: Raw payload data
            actor_person_id: Optional identity profile ID of actor
            visibility_tags: Optional ACL tags
            store_blob: Whether to store raw payload as blob
            
        Returns:
            Created artifact record with artifact_id
        """
        if source not in self.VALID_SOURCES:
            raise ValueError(f"Invalid source: {source}. Must be one of {self.VALID_SOURCES}")
        if artifact_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid type: {artifact_type}. Must be one of {self.VALID_TYPES}")
        
        artifact_id = self._generate_id()
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        content_hash = self._hash_content(payload_json)
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Check for existing artifact with same source/source_id
            cursor.execute(
                "SELECT artifact_id FROM artifacts WHERE source = ? AND source_id = ?",
                (source, source_id)
            )
            existing = cursor.fetchone()
            if existing:
                # Update existing artifact if content changed
                cursor.execute(
                    "SELECT content_hash FROM artifacts WHERE artifact_id = ?",
                    (existing[0],)
                )
                old_hash = cursor.fetchone()[0]
                if old_hash == content_hash:
                    # No change
                    return {'artifact_id': existing[0], 'status': 'unchanged'}
                
                # Update with new content
                cursor.execute("""
                    UPDATE artifacts 
                    SET content_hash = ?, payload_ref = ?, occurred_at = ?
                    WHERE artifact_id = ?
                """, (content_hash, payload_json if not store_blob else f"blob:{content_hash}", 
                      occurred_at, existing[0]))
                
                conn.commit()
                return {'artifact_id': existing[0], 'status': 'updated'}
            
            # Store blob if requested (encrypted)
            payload_ref = payload_json
            if store_blob:
                blob_id = f"blob_{content_hash[:16]}"
                # Encrypt payload before storage
                encrypted_payload = self._encrypt_payload(payload_json)
                cursor.execute("""
                    INSERT OR IGNORE INTO artifact_blobs 
                    (blob_id, content_hash, payload, size_bytes, created_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (blob_id, content_hash, encrypted_payload, len(encrypted_payload)))
                payload_ref = f"blob:{blob_id}"
            
            # Create artifact
            cursor.execute("""
                INSERT INTO artifacts 
                (artifact_id, source, source_id, type, occurred_at, actor_person_id, 
                 payload_ref, content_hash, visibility_tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                artifact_id, source, source_id, artifact_type, occurred_at,
                actor_person_id, payload_ref, content_hash,
                json.dumps(visibility_tags or [])
            ))
            
            conn.commit()
            return {'artifact_id': artifact_id, 'status': 'created', 'content_hash': content_hash}
            
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ValueError(f"Failed to create artifact: {e}")
        finally:
            conn.close()
    
    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an artifact by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT artifact_id, source, source_id, type, occurred_at, 
                       actor_person_id, payload_ref, content_hash, visibility_tags, created_at
                FROM artifacts WHERE artifact_id = ?
            """, (artifact_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            artifact = {
                'artifact_id': row[0],
                'source': row[1],
                'source_id': row[2],
                'type': row[3],
                'occurred_at': row[4],
                'actor_person_id': row[5],
                'payload_ref': row[6],
                'content_hash': row[7],
                'visibility_tags': json.loads(row[8] or '[]'),
                'created_at': row[9]
            }
            
            # Resolve payload if it's a blob reference
            if artifact['payload_ref'].startswith('blob:'):
                blob_ref = artifact['payload_ref'].replace('blob:', '')
                
                # Handle both formats:
                # 1. blob:blob_XXXX (blob_id prefix format)
                # 2. blob:FULLHASH (raw content_hash format)
                if blob_ref.startswith('blob_'):
                    blob_id = blob_ref
                else:
                    # Convert full hash to blob_id format
                    blob_id = f"blob_{blob_ref[:16]}"
                
                cursor.execute(
                    "SELECT payload FROM artifact_blobs WHERE blob_id = ?",
                    (blob_id,)
                )
                blob_row = cursor.fetchone()
                
                # Fallback: try content_hash lookup if blob_id didn't work
                if not blob_row and not blob_ref.startswith('blob_'):
                    cursor.execute(
                        "SELECT payload FROM artifact_blobs WHERE content_hash = ?",
                        (blob_ref,)
                    )
                    blob_row = cursor.fetchone()
                
                if blob_row:
                    payload_data = blob_row[0]
                    # Decrypt if encrypted
                    if self._is_encrypted(payload_data):
                        payload_data = self._decrypt_payload(payload_data)
                    artifact['payload'] = json.loads(payload_data)
            else:
                artifact['payload'] = json.loads(artifact['payload_ref'])
            
            return artifact
        finally:
            conn.close()
    
    def create_excerpt(
        self,
        artifact_id: str,
        excerpt_text: str,
        anchor_type: str = 'message_quote',
        anchor_start: str = '0',
        anchor_end: str = '-1'
    ) -> Dict[str, Any]:
        """
        Create an excerpt (anchored proof) from an artifact.
        
        Args:
            artifact_id: Source artifact
            excerpt_text: The extracted text
            anchor_type: Type of anchor (byte_span, line_span, json_path, message_quote)
            anchor_start: Start position/path
            anchor_end: End position/path
            
        Returns:
            Created excerpt record
        """
        excerpt_id = f"exc_{uuid.uuid4().hex[:16]}"
        excerpt_hash = self._hash_content(excerpt_text)
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO artifact_excerpts
                (excerpt_id, artifact_id, anchor_type, anchor_start, anchor_end,
                 excerpt_text, excerpt_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (excerpt_id, artifact_id, anchor_type, anchor_start, anchor_end,
                  excerpt_text, excerpt_hash))
            
            conn.commit()
            return {
                'excerpt_id': excerpt_id,
                'artifact_id': artifact_id,
                'excerpt_hash': excerpt_hash
            }
        finally:
            conn.close()
    
    def get_excerpts_for_artifact(self, artifact_id: str) -> List[Dict[str, Any]]:
        """Get all excerpts for an artifact."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT excerpt_id, artifact_id, anchor_type, anchor_start, anchor_end,
                       excerpt_text, excerpt_hash, redaction_status, created_at
                FROM artifact_excerpts WHERE artifact_id = ?
            """, (artifact_id,))
            
            return [{
                'excerpt_id': row[0],
                'artifact_id': row[1],
                'anchor_type': row[2],
                'anchor_start': row[3],
                'anchor_end': row[4],
                'excerpt_text': row[5],
                'excerpt_hash': row[6],
                'redaction_status': row[7],
                'created_at': row[8]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def find_artifacts(
        self,
        source: Optional[str] = None,
        artifact_type: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for artifacts with filters."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            query = "SELECT artifact_id, source, source_id, type, occurred_at, content_hash, created_at FROM artifacts WHERE 1=1"
            params = []
            
            if source:
                query += " AND source = ?"
                params.append(source)
            if artifact_type:
                query += " AND type = ?"
                params.append(artifact_type)
            if since:
                query += " AND occurred_at >= ?"
                params.append(since)
            if until:
                query += " AND occurred_at <= ?"
                params.append(until)
            
            query += " ORDER BY occurred_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            return [{
                'artifact_id': row[0],
                'source': row[1],
                'source_id': row[2],
                'type': row[3],
                'occurred_at': row[4],
                'content_hash': row[5],
                'created_at': row[6]
            } for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get artifact statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Total counts
            cursor.execute("SELECT COUNT(*) FROM artifacts")
            stats['total_artifacts'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM artifact_blobs")
            stats['total_blobs'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM artifact_excerpts")
            stats['total_excerpts'] = cursor.fetchone()[0]
            
            # By source
            cursor.execute("""
                SELECT source, COUNT(*) as cnt 
                FROM artifacts GROUP BY source ORDER BY cnt DESC
            """)
            stats['by_source'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # By type
            cursor.execute("""
                SELECT type, COUNT(*) as cnt 
                FROM artifacts GROUP BY type ORDER BY cnt DESC
            """)
            stats['by_type'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            return stats
        finally:
            conn.close()


# Singleton instance
_artifact_service = None

def get_artifact_service() -> ArtifactService:
    """Get the singleton artifact service instance."""
    global _artifact_service
    if _artifact_service is None:
        _artifact_service = ArtifactService()
    return _artifact_service
