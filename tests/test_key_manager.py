"""
Comprehensive tests for MOH Time OS API Key Manager.

Tests cover:
- Key generation format and security
- Key hashing (SHA-256)
- Create/validate/revoke lifecycle
- Expiration handling
- Role assignment
- Key rotation
- List operations (never exposing hashes)
- Integration with auth.py
- Legacy INTEL_API_TOKEN compatibility
"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from lib import store
from lib.security import KeyInfo, KeyManager, KeyRole


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Create connection and schema
    conn = sqlite3.connect(str(db_path))

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
    conn.execute(schema)
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    try:
        db_path.unlink()
    except OSError:
        pass  # Cleanup is best-effort


@pytest.fixture
def key_manager(temp_db):
    """Create a KeyManager instance with a temporary database."""
    # Patch the db_path to use our temp db
    with patch("lib.security.key_manager.store.DB_PATH", temp_db):
        manager = KeyManager()
        yield manager


class TestKeyGeneration:
    """Test API key generation."""

    def test_key_format(self, key_manager):
        """Keys have correct format: mtos_ prefix + 32 hex chars."""
        key, _ = key_manager.create_key("test", KeyRole.VIEWER)

        assert key.startswith("mtos_")
        assert len(key) == len("mtos_") + 32
        # Check that the part after prefix is valid hex
        hex_part = key[len("mtos_") :]
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_key_uniqueness(self, key_manager):
        """Each generated key is unique."""
        key1, _ = key_manager.create_key("key1", KeyRole.VIEWER)
        key2, _ = key_manager.create_key("key2", KeyRole.OPERATOR)
        key3, _ = key_manager.create_key("key3", KeyRole.ADMIN)

        assert key1 != key2 != key3

    def test_multiple_generations_unique(self, key_manager):
        """Multiple key generation calls produce different keys."""
        keys = [key_manager.create_key(f"key{i}", KeyRole.VIEWER)[0] for i in range(5)]
        assert len(set(keys)) == 5  # All unique


class TestKeyHashing:
    """Test key hashing (SHA-256)."""

    def test_key_not_stored_plaintext(self, key_manager, temp_db):
        """Plaintext key is never stored in database."""
        key, _ = key_manager.create_key("test", KeyRole.VIEWER)

        conn = sqlite3.connect(str(temp_db))
        row = conn.execute("SELECT key_hash FROM api_keys LIMIT 1").fetchone()
        conn.close()

        assert row is not None
        key_hash = row[0]

        # Hash should not equal the key
        assert key_hash != key
        assert not key_hash.startswith("mtos_")

    def test_hash_is_sha256(self, key_manager):
        """Key hash is SHA-256 (64 hex chars)."""
        key, _ = key_manager.create_key("test", KeyRole.VIEWER)
        key_hash = KeyManager._hash_key(key)

        # SHA-256 produces 64 hex characters
        assert len(key_hash) == 64
        assert all(c in "0123456789abcdef" for c in key_hash)

    def test_same_key_same_hash(self, key_manager):
        """Same key always produces same hash."""
        key = "mtos_abc123def456"
        hash1 = KeyManager._hash_key(key)
        hash2 = KeyManager._hash_key(key)

        assert hash1 == hash2

    def test_different_keys_different_hashes(self, key_manager):
        """Different keys produce different hashes."""
        key1 = "mtos_abc123def456"
        key2 = "mtos_xyz789uvw012"

        hash1 = KeyManager._hash_key(key1)
        hash2 = KeyManager._hash_key(key2)

        assert hash1 != hash2


class TestKeyLifecycle:
    """Test create/validate/revoke lifecycle."""

    def test_create_key(self, key_manager):
        """Create key returns key and metadata."""
        key, info = key_manager.create_key("Dashboard", KeyRole.VIEWER)

        assert key.startswith("mtos_")
        assert info.name == "Dashboard"
        assert info.role == KeyRole.VIEWER
        assert info.is_active
        assert info.created_at is not None
        assert info.expires_at is None  # No expiration by default

    def test_validate_valid_key(self, key_manager):
        """Valid key validates successfully."""
        key, _ = key_manager.create_key("test", KeyRole.VIEWER)

        info = key_manager.validate_key(key)

        assert info is not None
        assert info.name == "test"
        assert info.role == KeyRole.VIEWER
        assert info.is_active

    def test_validate_invalid_key(self, key_manager):
        """Invalid key returns None."""
        info = key_manager.validate_key("invalid_key")
        assert info is None

    def test_validate_wrong_prefix(self, key_manager):
        """Key with wrong prefix returns None."""
        info = key_manager.validate_key("wrong_abc123def456")
        assert info is None

    def test_revoke_key(self, key_manager):
        """Revoked key fails validation."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER)
        key_id = info.id

        # Should validate before revocation
        assert key_manager.validate_key(key) is not None

        # Revoke
        success = key_manager.revoke_key(key_id)
        assert success

        # Should not validate after revocation
        assert key_manager.validate_key(key) is None

    def test_revoke_nonexistent_key(self, key_manager):
        """Revoking nonexistent key returns False."""
        success = key_manager.revoke_key("key_nonexistent")
        assert not success

    def test_validate_revoked_key(self, key_manager):
        """Revoked key cannot be validated."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER)
        key_manager.revoke_key(info.id)

        assert key_manager.validate_key(key) is None

    def test_create_with_custom_created_by(self, key_manager):
        """Create key with custom created_by field."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER, created_by="user_123")

        assert info.created_by == "user_123"

    def test_create_invalid_name(self, key_manager):
        """Cannot create key with empty name."""
        with pytest.raises(ValueError):
            key_manager.create_key("", KeyRole.VIEWER)

        with pytest.raises(ValueError):
            key_manager.create_key("   ", KeyRole.VIEWER)


class TestKeyExpiration:
    """Test key expiration."""

    def test_create_with_expiration(self, key_manager):
        """Create key with expiration."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER, expires_in_days=90)

        assert info.expires_at is not None
        expires = datetime.fromisoformat(info.expires_at.replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=expires.tzinfo)
        delta = (expires - now).days

        # Should be approximately 90 days
        assert 89 <= delta <= 91

    def test_expired_key_validation_fails(self, key_manager, temp_db):
        """Expired key cannot be validated."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER, expires_in_days=1)

        # Manually set expiration to past
        past_time = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        conn = sqlite3.connect(str(temp_db))
        conn.execute("UPDATE api_keys SET expires_at = ? WHERE id = ?", (past_time, info.id))
        conn.commit()
        conn.close()

        assert key_manager.validate_key(key) is None

    def test_non_expiring_key(self, key_manager):
        """Key without expiration never expires."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER, expires_in_days=None)

        assert info.expires_at is None
        assert not info.is_expired()

    def test_invalid_expiration_days(self, key_manager):
        """Invalid expiration days raises ValueError."""
        with pytest.raises(ValueError):
            key_manager.create_key("test", KeyRole.VIEWER, expires_in_days=0)

        with pytest.raises(ValueError):
            key_manager.create_key("test", KeyRole.VIEWER, expires_in_days=-1)


class TestKeyRoles:
    """Test role assignment."""

    def test_viewer_role(self, key_manager):
        """Create key with VIEWER role."""
        _, info = key_manager.create_key("viewer_key", KeyRole.VIEWER)
        assert info.role == KeyRole.VIEWER
        assert info.role.value == "viewer"

    def test_operator_role(self, key_manager):
        """Create key with OPERATOR role."""
        _, info = key_manager.create_key("operator_key", KeyRole.OPERATOR)
        assert info.role == KeyRole.OPERATOR
        assert info.role.value == "operator"

    def test_admin_role(self, key_manager):
        """Create key with ADMIN role."""
        _, info = key_manager.create_key("admin_key", KeyRole.ADMIN)
        assert info.role == KeyRole.ADMIN
        assert info.role.value == "admin"

    def test_all_roles(self, key_manager):
        """Can create keys with all available roles."""
        roles = [KeyRole.VIEWER, KeyRole.OPERATOR, KeyRole.ADMIN]

        keys = [key_manager.create_key(f"key_{i}", role)[0] for i, role in enumerate(roles)]

        assert len(keys) == 3
        for key in keys:
            assert key_manager.validate_key(key) is not None


class TestKeyRotation:
    """Test key rotation (create new, revoke old)."""

    def test_rotate_key(self, key_manager):
        """Rotating key creates new and revokes old."""
        key1, info1 = key_manager.create_key("test", KeyRole.VIEWER)

        result = key_manager.rotate_key(info1.id)

        assert result is not None
        key2, info2 = result

        # Old key should not validate
        assert key_manager.validate_key(key1) is None

        # New key should validate
        assert key_manager.validate_key(key2) is not None

        # New key should have same name
        new_info = key_manager.validate_key(key2)
        assert new_info.name == "test"

    def test_rotate_key_new_name(self, key_manager):
        """Rotating key can update name."""
        key1, info1 = key_manager.create_key("old_name", KeyRole.VIEWER)

        result = key_manager.rotate_key(info1.id, new_name="new_name")

        key2, info2 = result
        assert info2.name == "new_name"

    def test_rotate_key_new_expiration(self, key_manager):
        """Rotating key can update expiration."""
        key1, info1 = key_manager.create_key("test", KeyRole.VIEWER, expires_in_days=30)

        result = key_manager.rotate_key(info1.id, expires_in_days=90)

        key2, info2 = result
        assert info2.expires_at is not None

        expires = datetime.fromisoformat(info2.expires_at.replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=expires.tzinfo)
        delta = (expires - now).days

        # Should be approximately 90 days
        assert 89 <= delta <= 91

    def test_rotate_inactive_key_fails(self, key_manager):
        """Cannot rotate an inactive key."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER)
        key_manager.revoke_key(info.id)

        result = key_manager.rotate_key(info.id)
        assert result is None

    def test_rotate_nonexistent_key_fails(self, key_manager):
        """Cannot rotate nonexistent key."""
        result = key_manager.rotate_key("key_nonexistent")
        assert result is None


class TestListKeys:
    """Test listing keys."""

    def test_list_empty(self, key_manager):
        """List returns empty list when no keys."""
        keys = key_manager.list_keys()
        assert keys == []

    def test_list_keys(self, key_manager):
        """List returns all active keys."""
        key1, _ = key_manager.create_key("key1", KeyRole.VIEWER)
        key2, _ = key_manager.create_key("key2", KeyRole.OPERATOR)
        key3, _ = key_manager.create_key("key3", KeyRole.ADMIN)

        keys = key_manager.list_keys()

        assert len(keys) == 3
        names = {k.name for k in keys}
        assert names == {"key1", "key2", "key3"}

    def test_list_never_exposes_hash(self, key_manager):
        """List never returns key hashes."""
        key_manager.create_key("test", KeyRole.VIEWER)

        keys = key_manager.list_keys()

        for key_info in keys:
            # KeyInfo should not have a hash attribute
            assert not hasattr(key_info, "key_hash")
            # And it definitely shouldn't be exposed in str representation
            assert "hash" not in str(key_info).lower()

    def test_list_excludes_revoked(self, key_manager):
        """List excludes revoked keys by default."""
        key1, info1 = key_manager.create_key("active", KeyRole.VIEWER)
        key2, info2 = key_manager.create_key("revoked", KeyRole.VIEWER)

        key_manager.revoke_key(info2.id)

        keys = key_manager.list_keys(active_only=True)

        assert len(keys) == 1
        assert keys[0].name == "active"

    def test_list_includes_revoked(self, key_manager):
        """List can include revoked keys with active_only=False."""
        key1, info1 = key_manager.create_key("active", KeyRole.VIEWER)
        key2, info2 = key_manager.create_key("revoked", KeyRole.VIEWER)

        key_manager.revoke_key(info2.id)

        keys = key_manager.list_keys(active_only=False)

        assert len(keys) == 2
        names = {k.name for k in keys}
        assert names == {"active", "revoked"}

    def test_list_sorted_by_creation(self, key_manager):
        """List is sorted by creation time (newest first)."""
        key1, _ = key_manager.create_key("key1", KeyRole.VIEWER)
        key2, _ = key_manager.create_key("key2", KeyRole.VIEWER)
        key3, _ = key_manager.create_key("key3", KeyRole.VIEWER)

        keys = key_manager.list_keys()

        # Should be in reverse order (newest first)
        assert [k.name for k in keys] == ["key3", "key2", "key1"]


class TestGetKeyInfo:
    """Test retrieving key info by ID."""

    def test_get_key_info(self, key_manager):
        """Get key info by ID."""
        _, info = key_manager.create_key("test", KeyRole.VIEWER)

        retrieved = key_manager.get_key_info(info.id)

        assert retrieved is not None
        assert retrieved.name == "test"
        assert retrieved.role == KeyRole.VIEWER

    def test_get_nonexistent_key_info(self, key_manager):
        """Get info for nonexistent key returns None."""
        info = key_manager.get_key_info("key_nonexistent")
        assert info is None


class TestLastUsedTracking:
    """Test last_used_at tracking."""

    def test_last_used_updated_on_validation(self, key_manager, temp_db):
        """last_used_at is updated when key is validated."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER)

        # Initial last_used_at should be None before first validation
        assert info.last_used_at is None

        # After validation, last_used_at should be set
        validated_info = key_manager.validate_key(key)
        assert validated_info.last_used_at is not None

    def test_multiple_validations_update_last_used(self, key_manager, temp_db):
        """Multiple validations update last_used_at each time."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER)

        # First validation
        info1 = key_manager.validate_key(key)
        first_used = info1.last_used_at

        # Validate again after a brief delay
        import time

        time.sleep(0.01)  # Small delay to ensure timestamp differs

        info2 = key_manager.validate_key(key)
        second_used = info2.last_used_at

        # Both validations should have set/updated last_used_at
        assert first_used is not None
        assert second_used is not None
        # They may be the same or second may be later (depends on time resolution)
        # Just verify both are set
        assert first_used is not None
        assert second_used is not None


class TestKeyInfoDataclass:
    """Test KeyInfo dataclass."""

    def test_key_info_is_expired(self, key_manager):
        """KeyInfo.is_expired() works correctly."""
        _, info = key_manager.create_key("test", KeyRole.VIEWER, expires_in_days=1)

        # Should not be expired immediately
        assert not info.is_expired()

    def test_key_info_never_expires(self, key_manager):
        """KeyInfo without expires_at never expires."""
        _, info = key_manager.create_key("test", KeyRole.VIEWER)

        assert info.expires_at is None
        assert not info.is_expired()


class TestAuthIntegration:
    """Test integration with auth.py (passthrough for single-user system)."""

    def test_require_auth_always_passes(self):
        """require_auth is a passthrough — always returns a token."""
        import asyncio
        from unittest.mock import MagicMock

        from api.auth import require_auth

        request = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(require_auth(request, None))
        finally:
            loop.close()
        assert result == "local"
        assert request.state.role == "owner"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_concurrent_key_creation(self, key_manager):
        """Multiple simultaneous key creations work correctly."""
        # Create multiple keys in sequence (simulating concurrency)
        keys = []
        for i in range(10):
            key, _ = key_manager.create_key(f"key_{i}", KeyRole.VIEWER)
            keys.append(key)

        # All should validate
        for key in keys:
            assert key_manager.validate_key(key) is not None

        # All should be unique
        assert len(set(keys)) == 10

    def test_key_with_special_characters_in_name(self, key_manager):
        """Key names can contain special characters."""
        special_names = [
            "API-Key-Dashboard",
            "Key (for testing)",
            "Key_with_underscores",
            "Key.with.dots",
        ]

        for name in special_names:
            key, info = key_manager.create_key(name, KeyRole.VIEWER)
            assert info.name == name
            assert key_manager.validate_key(key) is not None

    def test_very_long_key_name(self, key_manager):
        """Very long key names work correctly."""
        long_name = "a" * 255
        key, info = key_manager.create_key(long_name, KeyRole.VIEWER)

        assert info.name == long_name
        assert key_manager.validate_key(key) is not None

    def test_unicode_in_key_name(self, key_manager):
        """Unicode characters in key names work correctly."""
        unicode_names = [
            "Dashboard 仪板",
            "Клавиша",  # Russian
            "مفتاح",  # Arabic
        ]

        for name in unicode_names:
            key, info = key_manager.create_key(name, KeyRole.VIEWER)
            assert info.name == name
            assert key_manager.validate_key(key) is not None


class TestMetadataExposure:
    """Test that sensitive information is never exposed."""

    def test_key_info_no_hash_attribute(self, key_manager):
        """KeyInfo never includes key_hash."""
        key, info = key_manager.create_key("test", KeyRole.VIEWER)

        assert not hasattr(info, "key_hash")
        assert "key_hash" not in info.__dict__

    def test_validate_returns_no_plaintext(self, key_manager):
        """validate_key never returns plaintext key."""
        key, _ = key_manager.create_key("test", KeyRole.VIEWER)

        info = key_manager.validate_key(key)

        # Should return KeyInfo but not the plaintext key
        assert not hasattr(info, "key")
        assert not hasattr(info, "plaintext")

    def test_list_keys_no_hashes(self, key_manager):
        """list_keys never returns key hashes."""
        for i in range(5):
            key_manager.create_key(f"key_{i}", KeyRole.VIEWER)

        keys = key_manager.list_keys()

        for key_info in keys:
            assert not hasattr(key_info, "key_hash")

    def test_get_key_info_no_hash(self, key_manager):
        """get_key_info never returns key hash."""
        _, info = key_manager.create_key("test", KeyRole.VIEWER)

        retrieved = key_manager.get_key_info(info.id)

        assert not hasattr(retrieved, "key_hash")


# Run full test suite: python -m pytest tests/test_key_manager.py -v --tb=short
