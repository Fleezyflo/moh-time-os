"""Backup and restore functionality for MOH Time OS."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from .store import DB_PATH, checkpoint_wal, db_exists

log = logging.getLogger("moh_time_os")

BACKUP_DIR = DB_PATH.parent / "backups"


def create_backup(label: str = None) -> Path | None:
    """
    Create a backup of the database.
    Returns backup path or None if failed.
    """
    if not db_exists():
        log.warning("Cannot backup: database does not exist")
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Checkpoint WAL first to ensure consistency
    try:
        checkpoint_wal()
    except Exception as e:
        # Non-critical - proceed with backup anyway
        log.warning(f"WAL checkpoint failed before backup: {e}", exc_info=True)

    # Generate backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = (
        f"moh_time_os_{timestamp}_{label}.db"
        if label
        else f"moh_time_os_{timestamp}.db"
    )

    backup_path = BACKUP_DIR / filename

    try:
        shutil.copy2(DB_PATH, backup_path)
        log.info(f"Created backup: {backup_path}")
        return backup_path
    except PermissionError as e:
        log.error(f"Backup failed - permission denied: {e}")
        return None
    except OSError as e:
        log.error(f"Backup failed - filesystem error: {e}", exc_info=True)
        return None
    except Exception as e:
        log.error(f"Backup failed - unexpected error: {e}", exc_info=True)
        return None


def list_backups() -> list[tuple[Path, datetime, int]]:
    """
    List available backups.
    Returns list of (path, modified_time, size_bytes).
    """
    if not BACKUP_DIR.exists():
        return []

    backups = []
    for f in BACKUP_DIR.glob("*.db"):
        try:
            stat = f.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            backups.append((f, mtime, stat.st_size))
        except OSError as e:
            # File may have been deleted/moved - skip it
            log.warning(f"Could not stat backup {f}: {e}")

    # Sort by modified time, newest first
    backups.sort(key=lambda x: x[1], reverse=True)
    return backups


def get_latest_backup() -> Path | None:
    """Get path to the most recent backup."""
    backups = list_backups()
    return backups[0][0] if backups else None


def restore_backup(backup_path: Path, create_safety_backup: bool = True) -> bool:
    """
    Restore database from a backup.
    Optionally creates a safety backup of current state first.
    Returns True if successful.
    """
    if not backup_path.exists():
        log.error(f"Backup file does not exist: {backup_path}")
        return False

    # Safety backup of current state
    if create_safety_backup and db_exists():
        safety = create_backup(label="pre_restore")
        if safety:
            log.info(f"Created safety backup: {safety}")

    try:
        # Checkpoint current WAL if exists
        if db_exists():
            try:
                checkpoint_wal()
            except Exception as e:
                # Non-critical - proceed with restore anyway
                log.warning(f"WAL checkpoint failed during restore: {e}", exc_info=True)

        # Copy backup to main path
        shutil.copy2(backup_path, DB_PATH)

        # Also remove any leftover WAL/SHM files
        wal_file = Path(str(DB_PATH) + "-wal")
        shm_file = Path(str(DB_PATH) + "-shm")
        for f in [wal_file, shm_file]:
            if f.exists():
                f.unlink()

        log.info(f"Restored from backup: {backup_path}")
        return True
    except PermissionError as e:
        log.error(f"Restore failed - permission denied: {e}")
        return False
    except OSError as e:
        log.error(f"Restore failed - filesystem error: {e}", exc_info=True)
        return False
    except Exception as e:
        log.error(f"Restore failed - unexpected error: {e}", exc_info=True)
        return False


def restore_latest() -> bool:
    """Restore from the most recent backup."""
    latest = get_latest_backup()
    if not latest:
        log.error("No backups available to restore")
        return False
    return restore_backup(latest)


def prune_backups(keep: int = 7) -> int:
    """
    Prune old backups, keeping the N most recent.
    Returns number of backups deleted.
    """
    backups = list_backups()
    to_delete = backups[keep:]

    deleted = 0
    for path, _, _ in to_delete:
        try:
            path.unlink()
            deleted += 1
            log.info(f"Pruned backup: {path.name}")
        except PermissionError as e:
            log.warning(f"Failed to prune {path} - permission denied: {e}")
        except OSError as e:
            log.warning(f"Failed to prune {path}: {e}")

    return deleted


def backup_status() -> str:
    """Get a formatted backup status string."""
    backups = list_backups()

    if not backups:
        return "No backups available"

    lines = [f"**Backups:** {len(backups)} available\n"]

    for path, mtime, size in backups[:5]:
        size_kb = size / 1024
        age = datetime.now() - mtime
        if age.days > 0:
            age_str = f"{age.days}d ago"
        elif age.seconds > 3600:
            age_str = f"{age.seconds // 3600}h ago"
        else:
            age_str = f"{age.seconds // 60}m ago"

        lines.append(f"- {path.name} ({size_kb:.0f}KB, {age_str})")

    if len(backups) > 5:
        lines.append(f"- ... and {len(backups) - 5} more")

    return "\n".join(lines)
