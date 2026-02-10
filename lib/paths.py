from __future__ import annotations

import os
from pathlib import Path

APP_ENV_HOME = "MOH_TIME_OS_HOME"
APP_ENV_DB = "MOH_TIME_OS_DB"


def project_root() -> Path:
    """
    Repository/project root directory.
    Contains lib/, cli/, collectors/, engine/, dashboard/, etc.
    """
    return Path(__file__).parent.parent.resolve()


def app_home() -> Path:
    """
    User-writable home for Moh Time OS.
    Override with MOH_TIME_OS_HOME.
    """
    if os.environ.get(APP_ENV_HOME):
        return Path(os.environ[APP_ENV_HOME]).expanduser().resolve()
    # pragmatic default without new deps:
    return (Path.home() / ".moh_time_os").resolve()


def config_dir() -> Path:
    d = app_home() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_dir() -> Path:
    d = app_home() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    """
    Canonical DB path for moh_time_os.

    Resolution order:
    1. MOH_TIME_OS_DB env var (explicit override)
    2. ~/.moh_time_os/data/moh_time_os.db (default)
    """
    if os.environ.get(APP_ENV_DB):
        return Path(os.environ[APP_ENV_DB]).expanduser().resolve()
    return data_dir() / "moh_time_os.db"


def out_dir() -> Path:
    """Output directory for generated artifacts (snapshots, reports)."""
    d = app_home() / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def v5_db_path() -> Path:
    """V5 database path (separate from main db)."""
    return data_dir() / "time_os_v5.db"
