# Exception Handling Audit — RESOLVED

**Date:** 2025-02-08
**Status:** All Category B/C issues fixed

---

## Summary

6 files were audited and properly fixed with:
- Specific exception types (not broad `except Exception`)
- Appropriate log levels (debug/warning/error)
- `exc_info=True` for actual errors that need stack traces
- Clear error messages with context

---

## Files Reviewed and Fixed

### 1. lib/sync.py
| Fix | Description |
|-----|-------------|
| Line 116 | `print()` → `logger.warning()` for Xero API fallback |
| Lines 100-128 | Split by exception type (FileNotFoundError, JSONDecodeError, KeyError/TypeError, Exception) |
| Lines 150-210 | Same pattern for API sync loops |
| Lines 356-380 | Asana sync with ImportError handling |
| All loops | Inner exceptions: KeyError/TypeError (debug) vs Exception (warning with exc_info) |

### 2. lib/backup.py
| Fix | Description |
|-----|-------------|
| Line 28-30 | Added `exc_info=True` to WAL checkpoint warning |
| Line 46-52 | Split: PermissionError, OSError (with exc_info), Exception (with exc_info) |
| Line 63-66 | Narrowed to OSError |
| Line 89-92 | Added `exc_info=True` to WAL checkpoint warning |
| Line 103-112 | Split: PermissionError, OSError (with exc_info), Exception (with exc_info) |
| Line 125-128 | Split: PermissionError, OSError |

### 3. lib/move_executor.py
| Fix | Description |
|-----|-------------|
| Line 78-82 | Split: sqlite3.Error (with exc_info), Exception (with exc_info) |
| Line 106-114 | Split: sqlite3.Error, KeyError/TypeError, Exception (all with appropriate logging) |

### 4. lib/sync_xero.py
| Fix | Description |
|-----|-------------|
| Line 127-136 | Split: KeyError/TypeError (debug), Exception (error with exc_info), ImportError |

### 5. lib/integrations/tasks_integration.py
| Fix | Description |
|-----|-------------|
| Lines 136-142 | Split: TimeoutExpired, OSError/SubprocessError (both with logging) |
| Lines 183-189 | Same pattern |
| Lines 196-204 | Same pattern |
| Lines 231-239 | Same pattern |
| Lines 266-274 | Same pattern |

### 6. lib/integrations/email_integration.py
| Fix | Description |
|-----|-------------|
| Lines 162-170 | Split: TimeoutExpired, OSError/SubprocessError (both with logging) |
| Lines 174-184 | Same pattern |

---

## Exception Handling Patterns Applied

### Pattern 1: File/JSON operations
```python
except FileNotFoundError:
    logger.warning(f"File not found: {path}")
except json.JSONDecodeError as e:
    logger.error(f"Corrupt file: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
```

### Pattern 2: Batch operations (loops)
```python
except (KeyError, TypeError) as e:
    # Expected data issues - skip and continue
    logger.debug(f"Skipping item: {e}")
except Exception as e:
    # Unexpected - log with stack trace but continue batch
    logger.warning(f"Failed to process: {e}", exc_info=True)
```

### Pattern 3: Subprocess/CLI calls
```python
except subprocess.TimeoutExpired:
    logger.warning(f"Timeout: {operation}")
    return False, "Operation timed out"
except (OSError, subprocess.SubprocessError) as e:
    logger.warning(f"Subprocess error: {e}")
    return False, f"Error: {e}"
```

### Pattern 4: Critical operations (backup/restore)
```python
except PermissionError as e:
    logger.error(f"Permission denied: {e}")
except OSError as e:
    logger.error(f"Filesystem error: {e}", exc_info=True)
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
```

---

## Verification

All files compile:
```
✓ lib/sync.py
✓ lib/backup.py
✓ lib/move_executor.py
✓ lib/sync_xero.py
✓ lib/integrations/tasks_integration.py
✓ lib/integrations/email_integration.py
```
