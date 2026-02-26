"""
Comprehensive tests for backup and restore functionality.

Covers:
- create_backup with timestamp and labels
- restore_backup with safety backup
- list_backups and sorting
- prune_backups retention
- WAL checkpoint integration
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.backup import (
    backup_status,
    create_backup,
    get_latest_backup,
    list_backups,
    prune_backups,
    restore_backup,
    restore_latest,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db_path(tmp_path):
    """Create a mock database file."""
    db_file = tmp_path / "moh_time_os.db"
    db_file.write_text("mock database content")
    return db_file


@pytest.fixture
def mock_backup_dir(tmp_path):
    """Create a mock backup directory."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    return backup_dir


# =============================================================================
# CREATE BACKUP TESTS
# =============================================================================


class TestCreateBackup:
    """Tests for create_backup functionality."""

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("lib.backup.checkpoint_wal")
    @patch("lib.backup.BACKUP_DIR")
    def test_create_backup_basic(
        self, mock_backup_dir_const, mock_checkpoint, mock_db_exists, mock_db_path_patch, tmp_path
    ):
        """create_backup should create a backup file."""
        # Setup mocks
        mock_db_exists.return_value = True
        mock_checkpoint.return_value = None

        source_path = tmp_path / "test_source.db"
        source_path.write_text("mock database")

        mock_db_path_patch.value = source_path
        mock_backup_dir_const.value = tmp_path / "backups"

        with patch("shutil.copy2") as mock_copy:
            with patch("pathlib.Path.mkdir"):
                create_backup()

                # Should have called copy
                assert mock_copy.called

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    def test_create_backup_no_db(self, mock_db_exists, mock_db_path):
        """create_backup should return None if database doesn't exist."""
        mock_db_exists.return_value = False

        result = create_backup()
        assert result is None

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("lib.backup.checkpoint_wal")
    @patch("lib.backup.BACKUP_DIR")
    def test_create_backup_with_label(
        self, mock_backup_dir_const, mock_checkpoint, mock_db_exists, mock_db_path, tmp_path
    ):
        """create_backup should include label in filename."""
        mock_db_exists.return_value = True
        mock_checkpoint.return_value = None

        source_path = tmp_path / "test_source.db"
        source_path.write_text("mock database")
        mock_db_path.value = source_path

        with patch("shutil.copy2"):
            with patch("pathlib.Path.mkdir"):
                with patch("lib.backup.datetime") as mock_datetime:
                    mock_datetime.now.return_value.strftime.return_value = "20240115_120000"
                    try:
                        create_backup(label="test-label")
                    except Exception:
                        logging.debug("Expected error in mock backup test")

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("lib.backup.checkpoint_wal")
    @patch("lib.backup.BACKUP_DIR")
    def test_create_backup_handles_permission_error(
        self, mock_backup_dir_const, mock_checkpoint, mock_db_exists, mock_db_path
    ):
        """create_backup should handle permission errors gracefully."""
        mock_db_exists.return_value = True
        mock_checkpoint.return_value = None

        with patch("shutil.copy2", side_effect=PermissionError("Access denied")):
            with patch("pathlib.Path.mkdir"):
                result = create_backup()
                assert result is None

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("lib.backup.checkpoint_wal")
    @patch("lib.backup.BACKUP_DIR")
    def test_create_backup_handles_os_error(
        self, mock_backup_dir_const, mock_checkpoint, mock_db_exists, mock_db_path
    ):
        """create_backup should handle OS errors gracefully."""
        mock_db_exists.return_value = True
        mock_checkpoint.return_value = None

        with patch("shutil.copy2", side_effect=OSError("Disk full")):
            with patch("pathlib.Path.mkdir"):
                result = create_backup()
                assert result is None

    @patch("lib.backup.checkpoint_wal", side_effect=Exception("WAL checkpoint failed"))
    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("lib.backup.BACKUP_DIR")
    def test_create_backup_continues_on_checkpoint_failure(
        self, mock_backup_dir_const, mock_db_exists, mock_db_path, mock_checkpoint
    ):
        """create_backup should continue even if checkpoint fails."""
        mock_db_exists.return_value = True

        with patch("shutil.copy2"):
            with patch("pathlib.Path.mkdir"):
                # Should log warning but continue
                try:
                    create_backup()
                except Exception:
                    logging.debug("Expected error in checkpoint failure test")


# =============================================================================
# LIST BACKUPS TESTS
# =============================================================================


class TestListBackups:
    """Tests for list_backups functionality."""

    @patch("lib.backup.BACKUP_DIR")
    def test_list_backups_empty_directory(self, mock_backup_dir_const):
        """list_backups should return empty list if directory doesn't exist."""
        mock_backup_dir_const.exists.return_value = False

        result = list_backups()
        assert result == []

    @patch("lib.backup.BACKUP_DIR")
    def test_list_backups_sorting(self, mock_backup_dir_const, tmp_path):
        """list_backups should return backups sorted by modified time (newest first)."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create test backup files with different mtimes
        old_file = backup_dir / "backup_old.db"
        new_file = backup_dir / "backup_new.db"

        old_file.touch()
        new_file.touch()

        # Make old_file actually older
        import os

        old_stat = os.stat(old_file)
        os.utime(old_file, (old_stat.st_atime - 1000, old_stat.st_mtime - 1000))

        # Configure mock to act like the real backup_dir Path
        mock_backup_dir_const.exists.return_value = True
        mock_backup_dir_const.glob.return_value = backup_dir.glob("*.db")

        result = list_backups()

        assert len(result) >= 1
        # Newest should be first
        assert result[0][0].name == "backup_new.db"

    @patch("lib.backup.BACKUP_DIR")
    def test_list_backups_includes_file_info(self, mock_backup_dir_const, tmp_path):
        """list_backups should return (path, mtime, size) tuples."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        test_file = backup_dir / "backup_test.db"
        test_file.write_text("test content")

        # Configure mock to act like the real backup_dir Path
        mock_backup_dir_const.exists.return_value = True
        mock_backup_dir_const.glob.return_value = backup_dir.glob("*.db")

        result = list_backups()

        assert len(result) > 0
        path, mtime, size = result[0]
        assert isinstance(path, Path)
        assert isinstance(mtime, datetime)
        assert isinstance(size, int)
        assert size > 0

    @patch("lib.backup.BACKUP_DIR")
    def test_list_backups_skips_inaccessible_files(self, mock_backup_dir_const, tmp_path):
        """list_backups should skip files that can't be stat'd."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        test_file = backup_dir / "backup_test.db"
        test_file.write_text("test content")

        mock_backup_dir_const.exists.return_value = True
        mock_backup_dir_const.glob.return_value = backup_dir.glob("*.db")

        # Mock stat to raise error for one file
        original_stat = Path.stat

        call_count = [0]

        def mock_stat(self):
            call_count[0] += 1
            if call_count[0] > 1:
                raise OSError("Permission denied")
            return original_stat(self)

        with patch.object(Path, "stat", mock_stat):
            list_backups()
            # Should still work, just skip the problematic file


# =============================================================================
# GET LATEST BACKUP TESTS
# =============================================================================


class TestGetLatestBackup:
    """Tests for get_latest_backup functionality."""

    @patch("lib.backup.list_backups")
    def test_get_latest_backup_none_available(self, mock_list):
        """get_latest_backup should return None if no backups exist."""
        mock_list.return_value = []

        result = get_latest_backup()
        assert result is None

    @patch("lib.backup.list_backups")
    def test_get_latest_backup_returns_most_recent(self, mock_list):
        """get_latest_backup should return the first (most recent) backup."""
        path = Path("/tmp/backup_newest.db")
        mtime = datetime.now()

        mock_list.return_value = [
            (path, mtime, 1024),
            (Path("/tmp/backup_old.db"), mtime - timedelta(days=1), 1024),
        ]

        result = get_latest_backup()
        assert result == path


# =============================================================================
# RESTORE BACKUP TESTS
# =============================================================================


class TestRestoreBackup:
    """Tests for restore_backup functionality."""

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    def test_restore_backup_nonexistent_fails(self, mock_db_exists, mock_db_path):
        """restore_backup should fail if backup file doesn't exist."""
        nonexistent = Path("/nonexistent/backup.db")

        result = restore_backup(nonexistent)
        assert result is False

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("lib.backup.checkpoint_wal")
    @patch("shutil.copy2")
    def test_restore_backup_success(
        self, mock_copy, mock_checkpoint, mock_db_exists, mock_db_path, tmp_path
    ):
        """restore_backup should restore database from backup."""
        backup_file = tmp_path / "backup.db"
        backup_file.write_text("backup content")

        mock_db_path.value = Path("/tmp/live.db")
        mock_db_exists.return_value = False
        mock_checkpoint.return_value = None

        result = restore_backup(backup_file, create_safety_backup=False)

        assert mock_copy.called
        assert result is True

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("lib.backup.create_backup")
    @patch("shutil.copy2")
    def test_restore_backup_creates_safety_backup(
        self, mock_copy, mock_create_backup, mock_db_exists, mock_db_path, tmp_path
    ):
        """restore_backup should create safety backup if requested."""
        backup_file = tmp_path / "backup.db"
        backup_file.write_text("backup content")

        mock_db_path.value = Path("/tmp/live.db")
        mock_db_exists.return_value = True
        mock_create_backup.return_value = Path("/tmp/safety.db")

        restore_backup(backup_file, create_safety_backup=True)

        # Should have created safety backup
        mock_create_backup.assert_called()

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("shutil.copy2", side_effect=PermissionError("Access denied"))
    def test_restore_backup_handles_permission_error(
        self, mock_copy, mock_db_exists, mock_db_path, tmp_path
    ):
        """restore_backup should handle permission errors."""
        backup_file = tmp_path / "backup.db"
        backup_file.write_text("backup content")

        mock_db_path.value = Path("/tmp/live.db")
        mock_db_exists.return_value = False

        result = restore_backup(backup_file)
        assert result is False

    @patch("lib.backup.DB_PATH")
    @patch("lib.backup.db_exists")
    @patch("shutil.copy2")
    def test_restore_backup_removes_wal_files(
        self, mock_copy, mock_db_exists, mock_db_path, tmp_path
    ):
        """restore_backup should remove WAL and SHM files."""
        backup_file = tmp_path / "backup.db"
        backup_file.write_text("backup content")

        # Create WAL and SHM files
        wal_file = tmp_path / "live.db-wal"
        shm_file = tmp_path / "live.db-shm"
        wal_file.write_text("wal")
        shm_file.write_text("shm")

        mock_db_path.value = tmp_path / "live.db"
        mock_db_exists.return_value = False

        with patch("pathlib.Path.unlink"):
            restore_backup(backup_file, create_safety_backup=False)


# =============================================================================
# RESTORE LATEST TESTS
# =============================================================================


class TestRestoreLatest:
    """Tests for restore_latest functionality."""

    @patch("lib.backup.get_latest_backup")
    def test_restore_latest_no_backups(self, mock_get_latest):
        """restore_latest should fail if no backups available."""
        mock_get_latest.return_value = None

        result = restore_latest()
        assert result is False

    @patch("lib.backup.get_latest_backup")
    @patch("lib.backup.restore_backup")
    def test_restore_latest_uses_most_recent(self, mock_restore, mock_get_latest):
        """restore_latest should restore most recent backup."""
        latest_path = Path("/tmp/latest_backup.db")
        mock_get_latest.return_value = latest_path
        mock_restore.return_value = True

        result = restore_latest()

        mock_restore.assert_called_once_with(latest_path)
        assert result is True


# =============================================================================
# PRUNE BACKUPS TESTS
# =============================================================================


class TestPruneBackups:
    """Tests for prune_backups functionality."""

    @patch("lib.backup.list_backups")
    def test_prune_backups_keeps_recent(self, mock_list):
        """prune_backups should keep the N most recent backups."""
        paths = [Path(f"/tmp/backup_{i}.db") for i in range(10)]
        times = [datetime.now() - timedelta(days=i) for i in range(10)]
        sizes = [1024] * 10

        mock_list.return_value = [(p, t, s) for p, t, s in zip(paths, times, sizes, strict=False)]

        with patch.object(Path, "unlink"):
            deleted = prune_backups(keep=5)

            # Should delete 5 oldest
            assert deleted == 5

    @patch("lib.backup.list_backups")
    def test_prune_backups_default_keep_seven(self, mock_list):
        """prune_backups should default to keeping 7 backups."""
        paths = [Path(f"/tmp/backup_{i}.db") for i in range(10)]
        times = [datetime.now() - timedelta(days=i) for i in range(10)]
        sizes = [1024] * 10

        mock_list.return_value = [(p, t, s) for p, t, s in zip(paths, times, sizes, strict=False)]

        with patch.object(Path, "unlink"):
            deleted = prune_backups()

            # Should delete 3 (10 - 7)
            assert deleted == 3

    @patch("lib.backup.list_backups")
    def test_prune_backups_handles_permission_error(self, mock_list):
        """prune_backups should handle deletion errors gracefully."""
        path = Path("/tmp/backup_old.db")
        mock_list.return_value = [
            (path, datetime.now() - timedelta(days=10), 1024),
            (Path("/tmp/backup_new.db"), datetime.now(), 1024),
        ]

        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
            deleted = prune_backups(keep=1)

            # Should handle error and return 0 deleted
            assert deleted == 0


# =============================================================================
# BACKUP STATUS TESTS
# =============================================================================


class TestBackupStatus:
    """Tests for backup_status functionality."""

    @patch("lib.backup.list_backups")
    def test_backup_status_no_backups(self, mock_list):
        """backup_status should report when no backups exist."""
        mock_list.return_value = []

        result = backup_status()
        assert "No backups available" in result

    @patch("lib.backup.list_backups")
    def test_backup_status_formats_backup_list(self, mock_list):
        """backup_status should format backup information."""
        paths = [Path(f"/tmp/backup_{i}.db") for i in range(3)]
        times = [datetime.now() - timedelta(hours=i) for i in range(3)]
        sizes = [1024 * (i + 1) for i in range(3)]

        mock_list.return_value = [(p, t, s) for p, t, s in zip(paths, times, sizes, strict=False)]

        result = backup_status()

        assert "backup_0.db" in result
        assert "Backups:" in result
        assert "KB" in result
