# SH-1.1: API Key Management System

## Objective
Replace the single `INTEL_API_TOKEN` env var with a proper API key system — generate, store, rotate, revoke, and audit keys.

## Context
Current auth (`api/auth.py`, 144 lines): single token compared via `secrets.compare_digest`. If env var unset, auth is bypassed entirely (lines 75-81). No key rotation, no per-purpose keys, no expiry.

## Implementation

### Key Storage
```sql
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,  -- SHA-256 of key, never store raw
    key_prefix TEXT NOT NULL,       -- first 8 chars for identification
    name TEXT NOT NULL,             -- human label: "dashboard", "cli", "webhook"
    role TEXT NOT NULL DEFAULT 'viewer',  -- admin, operator, viewer
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,                -- NULL = never expires
    last_used_at TEXT,
    revoked_at TEXT,                -- NULL = active
    created_by TEXT,
    rate_limit_per_min INTEGER DEFAULT 100
);
```

### Key Generation
```python
import secrets
import hashlib

def generate_api_key(name: str, role: str, expires_days: int | None = None) -> str:
    """Generate a new API key. Returns the raw key (shown once, never stored)."""
    raw_key = f"moh_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]
    # Store key_hash, key_prefix, name, role, expires_at
    return raw_key  # Show to user ONCE
```

### Auth Flow Update
```python
# api/auth.py — replace single-token check:
def authenticate(request) -> APIKeyInfo:
    token = extract_token(request)  # from Bearer header or X-API-Token
    if not token:
        raise HTTPException(401, "API key required")
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    key_record = db.get_active_key(key_hash)
    if not key_record:
        raise HTTPException(401, "Invalid API key")
    if key_record.expires_at and key_record.expires_at < now():
        raise HTTPException(401, "API key expired")
    db.update_last_used(key_record.id)
    return APIKeyInfo(key_id=key_record.id, role=key_record.role, ...)
```

### CLI Commands
```bash
moh keys generate --name "dashboard" --role viewer --expires 90d
moh keys list
moh keys revoke --prefix "moh_abc12..."
moh keys rotate --prefix "moh_abc12..."  # revoke old, generate new
```

### Migration
- Existing `INTEL_API_TOKEN` auto-migrated as admin key on first boot
- Fallback: if no keys exist and env var set, create initial admin key from it
- After migration: env var no longer checked, only DB keys

## Validation
- [ ] Key generation returns unique moh_* prefixed keys
- [ ] Keys stored as SHA-256 hash only (raw never persisted)
- [ ] Expired keys rejected
- [ ] Revoked keys rejected
- [ ] last_used_at updated on every auth
- [ ] CLI commands work for generate/list/revoke/rotate
- [ ] Backward compat: existing INTEL_API_TOKEN migrated

## Files Modified
- `api/auth.py` — major rewrite
- `lib/db/migrations/` — new migration for api_keys table
- `cli.py` — add keys subcommand

## Estimated Effort
Medium-Large — ~250 lines, auth rewrite + CLI + migration
