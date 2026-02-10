"""
Golden Test Configuration

FROZEN EXPECTATIONS - hand-verified values from the real database.
Any change to these values requires explicit justification in PR description.

Source: data/moh_time_os.db as of 2026-02-09
Verification method: Direct SQL queries against the database
"""

from pathlib import Path

import pytest

# Path to the real database
DB_PATH = Path(__file__).parent.parent.parent / "data" / "moh_time_os.db"

# =============================================================================
# GOLDEN EXPECTATIONS - HAND VERIFIED, DO NOT CHANGE WITHOUT JUSTIFICATION
# =============================================================================

GOLDEN_EXPECTATIONS = {
    # Source: SELECT COUNT(*) FROM projects WHERE status NOT IN ('completed', 'cancelled', 'archived')
    "active_project_count": 354,
    # Source: SELECT COUNT(*) FROM invoices WHERE status IN ('sent', 'overdue') AND payment_date IS NULL
    "unpaid_invoice_count": 34,
    # Source: SELECT SUM(amount) FROM invoices WHERE status IN ('sent', 'overdue') AND payment_date IS NULL
    # Updated 2026-02-09: Data changed during Xero sync
    "total_valid_ar_aed": 1027172.25,
    # Source: SELECT COUNT(*) FROM commitments WHERE status NOT IN ('fulfilled', 'closed')
    "open_commitment_count": 37,
    # Source: SELECT COUNT(*) FROM clients
    "client_count": 25,
    # Source: SELECT COUNT(DISTINCT assignee) FROM tasks WHERE assignee IS NOT NULL AND status NOT IN ('done', 'completed', 'archived')
    "active_people_count": 22,
    # Source: SELECT COUNT(*) FROM communications WHERE received_at IS NOT NULL OR created_at IS NOT NULL
    "communication_count": 116,
}


@pytest.fixture
def golden():
    """Return golden expectations dict."""
    return GOLDEN_EXPECTATIONS


@pytest.fixture
def db_path():
    """Return path to real database."""
    return DB_PATH
