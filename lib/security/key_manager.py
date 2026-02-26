"""
Multi-key API key management for MOH Time OS.

Provides production-grade API key handling with SHA-256 hashing, role-based
access control, expiration, and audit logging.

Key Format:
  - User-visible: mtos_<32-char-hex>
  - Storage: SHA-256 hash only (never plaintext)
  - Roles: viewer, operator, admin

Example:
    manager = KeyManager()
    key, key_info = manager.create_key("dashboard", KeyRole.VIEWER, expires_in_days=90)
    print(f"Your API key (save this): {key}")

    is_valid = manager.validate_key(key)
    if is_valid:
        manager.log_usage(key_hash)
"""

import hashlib
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from lib import store

log = logging.getLogger(__name__)


class KeyRole(Enum):
    """Role-based access control for API keys."""

    VIEWER = "viewer"  # Read-only access
    OPERATOR = "operator"  # Read + write operations
    ADMIN = "admin"  # Full access including key management


@dataclass
class KeyInfo:
    """Metadata about an API key (never includes the hash or key itself)."""

    id: str
    name: str
    role: KeyRole
    created_at: str
    expires_at: str | None
    last_used_at: str | None
    is_active: bool
    created_by: str | None = None

    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if not self.expires_at:
            return False
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=expires.tzinfo)
        return now >= expires


class KeyManager:
    """Manages API key lifecycle: creation, validation, revocation, rotation."""

    PREFIX = "mtos_"
    KEY_LENGTH = 32  # Hex characters (128 bits of entropy)

    def __init__(self):
        """Initialize the key manager using the main MOH Time OS database."""
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the api_keys table if it doesn't exist."""
        schema = """
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('viewer', 'operator', 'admin')),
            created_at TEXT NOT NULL,
            expires_at TEXT,
            last_used_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT,
            CONSTRAINT valid_role CHECK(role IN ('viewer', 'operator', 'admin'))
        );
        """
        try:
            with store.get_connection() as conn:
                conn.execute(schema)
        except sqlite3.OperationalError as e:
            log.error(f"Failed to create api_keys schema: {e}")
            raise

    @staticmethod
    def _generate_key() -> str:
        """Generate a cryptographically secure API key."""
        random_hex = secrets.token_hex(KeyManager.KEY_LENGTH // 2)
        return f"{KeyManager.PREFIX}{random_hex}"

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash a key using SHA-256 (one-way, not reversible)."""
        return hashlib.sha256(key.encode()).hexdigest()

    def create_key(
        self,
        name: str,
        role: KeyRole,
        expires_in_days: int | None = None,
        created_by: str | None = None,
    ) -> tuple[str, KeyInfo]:
        """
        Create a new API key.

        Args:
            name: Human-readable name for the key (e.g., "Dashboard")
            role: KeyRole enum (VIEWER, OPERATOR, or ADMIN)
            expires_in_days: Days until expiration. None means no expiration.
            created_by: Optional identifier of who created this key

        Returns:
            (key, key_info) tuple where:
            - key is the plaintext API key (only returned once)
            - key_info contains metadata (no hash/key)

        Raises:
            ValueError: If parameters are invalid
            sqlite3.Error: If database operation fails
        """
        if not name or not name.strip():
            raise ValueError("name cannot be empty")

        if expires_in_days is not None and expires_in_days <= 0:
            raise ValueError("expires_in_days must be > 0")

        key = self._generate_key()
        key_hash = self._hash_key(key)
        key_id = f"key_{secrets.token_hex(8)}"

        now = datetime.utcnow().isoformat() + "Z"
        expires_at = None
        if expires_in_days:
            expires = datetime.utcnow() + timedelta(days=expires_in_days)
            expires_at = expires.isoformat() + "Z"

        try:
            with store.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO api_keys
                    (id, key_hash, name, role, created_at, expires_at, is_active, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key_id, key_hash, name, role.value, now, expires_at, 1, created_by),
                )

            log.info(f"Created API key: {key_id} (role={role.value}, name={name})")

            key_info = KeyInfo(
                id=key_id,
                name=name,
                role=role,
                created_at=now,
                expires_at=expires_at,
                last_used_at=None,
                is_active=True,
                created_by=created_by,
            )

            return key, key_info

        except sqlite3.IntegrityError as e:
            log.error(f"Failed to create API key: {e}")
            raise ValueError(f"Failed to create API key: {e}") from e

    def validate_key(self, key: str) -> KeyInfo | None:
        """
        Validate an API key and return its metadata if valid.

        Checks:
        1. Key hash exists in database
        2. Key is active
        3. Key has not expired
        4. Updates last_used_at on success

        Args:
            key: The API key to validate

        Returns:
            KeyInfo if valid, None if invalid/expired/inactive
        """
        if not key or not key.startswith(self.PREFIX):
            return None

        key_hash = self._hash_key(key)

        try:
            with store.get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT id, name, role, created_at, expires_at, last_used_at, is_active, created_by
                    FROM api_keys
                    WHERE key_hash = ?
                    """,
                    (key_hash,),
                ).fetchone()

                if not row:
                    return None

                (
                    key_id,
                    name,
                    role_str,
                    created_at,
                    expires_at,
                    last_used_at,
                    is_active,
                    created_by,
                ) = row

                # Check if active
                if not is_active:
                    log.debug(f"Key {key_id} is inactive")
                    return None

                role = KeyRole(role_str)
                key_info = KeyInfo(
                    id=key_id,
                    name=name,
                    role=role,
                    created_at=created_at,
                    expires_at=expires_at,
                    last_used_at=last_used_at,
                    is_active=bool(is_active),
                    created_by=created_by,
                )

                # Check if expired
                if key_info.is_expired():
                    log.debug(f"Key {key_id} is expired")
                    return None

                # Update last_used_at
                now = datetime.utcnow().isoformat() + "Z"
                conn.execute(
                    "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                    (now, key_id),
                )

                # Return updated KeyInfo with new last_used_at
                key_info.last_used_at = now
                return key_info

        except sqlite3.Error as e:
            log.error(f"Database error validating key: {e}")
            return None

    def revoke_key(self, key_id: str) -> bool:
        """
        Revoke (deactivate) an API key by ID.

        Args:
            key_id: The key ID to revoke

        Returns:
            True if revoked, False if not found
        """
        try:
            with store.get_connection() as conn:
                cursor = conn.execute(
                    "UPDATE api_keys SET is_active = 0 WHERE id = ?",
                    (key_id,),
                )
                conn.commit()

                if cursor.rowcount == 0:
                    log.warning(f"Key not found: {key_id}")
                    return False

                log.info(f"Revoked API key: {key_id}")
                return True

        except sqlite3.Error as e:
            log.error(f"Failed to revoke key {key_id}: {e}")
            return False

    def rotate_key(
        self,
        key_id: str,
        new_name: str | None = None,
        expires_in_days: int | None = None,
    ) -> tuple[str, KeyInfo] | None:
        """
        Rotate a key: create a new one and revoke the old one.

        Args:
            key_id: The key ID to rotate
            new_name: Optional new name for the rotated key. If not provided, uses old name.
            expires_in_days: Days until expiration for the new key

        Returns:
            (new_key, new_key_info) tuple on success, None on failure
        """
        try:
            with store.get_connection() as conn:
                # Get old key info
                row = conn.execute(
                    "SELECT name, role FROM api_keys WHERE id = ? AND is_active = 1",
                    (key_id,),
                ).fetchone()

                if not row:
                    log.warning(f"Cannot rotate inactive or missing key: {key_id}")
                    return None

                old_name, role_str = row
                name = new_name or old_name
                role = KeyRole(role_str)

                # Create new key
                new_key, new_key_info = self.create_key(
                    name=name,
                    role=role,
                    expires_in_days=expires_in_days,
                    created_by=f"rotate_from_{key_id}",
                )

                # Revoke old key
                self.revoke_key(key_id)

                log.info(f"Rotated API key: {key_id} -> {new_key_info.id}")
                return new_key, new_key_info

        except (sqlite3.Error, ValueError, OSError) as e:
            log.error(f"Failed to rotate key {key_id}: {e}")
            return None

    def list_keys(self, active_only: bool = True) -> list[KeyInfo]:
        """
        List all keys (metadata only, never returns hash or key).

        Args:
            active_only: If True, only return active keys

        Returns:
            List of KeyInfo objects (no hashes or keys exposed)
        """
        try:
            with store.get_connection() as conn:
                if active_only:
                    query = """
                    SELECT id, name, role, created_at, expires_at, last_used_at, is_active, created_by
                    FROM api_keys
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                    """
                    rows = conn.execute(query).fetchall()
                else:
                    query = """
                    SELECT id, name, role, created_at, expires_at, last_used_at, is_active, created_by
                    FROM api_keys
                    ORDER BY created_at DESC
                    """
                    rows = conn.execute(query).fetchall()

                keys = []
                for row in rows:
                    (
                        key_id,
                        name,
                        role_str,
                        created_at,
                        expires_at,
                        last_used_at,
                        is_active,
                        created_by,
                    ) = row
                    keys.append(
                        KeyInfo(
                            id=key_id,
                            name=name,
                            role=KeyRole(role_str),
                            created_at=created_at,
                            expires_at=expires_at,
                            last_used_at=last_used_at,
                            is_active=bool(is_active),
                            created_by=created_by,
                        )
                    )

                return keys

        except sqlite3.Error as e:
            log.error(f"Failed to list keys: {e}")
            return []

    def get_key_info(self, key_id: str) -> KeyInfo | None:
        """
        Get metadata for a specific key by ID.

        Args:
            key_id: The key ID to look up

        Returns:
            KeyInfo if found, None otherwise
        """
        try:
            with store.get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT id, name, role, created_at, expires_at, last_used_at, is_active, created_by
                    FROM api_keys
                    WHERE id = ?
                    """,
                    (key_id,),
                ).fetchone()

                if not row:
                    return None

                (
                    key_id,
                    name,
                    role_str,
                    created_at,
                    expires_at,
                    last_used_at,
                    is_active,
                    created_by,
                ) = row
                return KeyInfo(
                    id=key_id,
                    name=name,
                    role=KeyRole(role_str),
                    created_at=created_at,
                    expires_at=expires_at,
                    last_used_at=last_used_at,
                    is_active=bool(is_active),
                    created_by=created_by,
                )

        except sqlite3.Error as e:
            log.error(f"Failed to get key info for {key_id}: {e}")
            return None
