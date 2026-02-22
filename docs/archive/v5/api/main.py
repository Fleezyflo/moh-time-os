"""
Time OS V5 — API Main

FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import health, issues, signals

# =============================================================================
# Application
# =============================================================================

app = FastAPI(
    title="Time OS V5 API",
    description="Signal-based client health monitoring",
    version="5.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Routes
# =============================================================================

app.include_router(issues.router, prefix="/api/v5")
app.include_router(signals.router, prefix="/api/v5")
app.include_router(health.router, prefix="/api/v5")


# =============================================================================
# Root
# =============================================================================


@app.get("/")
async def root():
    """API root."""
    return {"name": "Time OS V5 API", "version": "5.0.0", "docs": "/docs"}


@app.get("/api/v5/status")
async def status():
    """API status."""
    from ..database import get_db

    db = get_db()

    # Get counts
    signal_count = db.fetch_value("SELECT COUNT(*) FROM signals_v5") or 0
    issue_count = db.fetch_value("SELECT COUNT(*) FROM issues_v5") or 0
    active_issues = (
        db.fetch_value(
            "SELECT COUNT(*) FROM issues_v5 WHERE state IN ('surfaced', 'acknowledged', 'addressing')"
        )
        or 0
    )

    return {
        "status": "ok",
        "signals": signal_count,
        "issues": issue_count,
        "active_issues": active_issues,
    }
