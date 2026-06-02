"""
Shared Pydantic response models for API endpoints.

These models give FastAPI the type information it needs to generate
accurate OpenAPI schemas instead of empty `schema: {}`.

Usage:
    from api.response_models import IntelligenceResponse, ListResponse

    @router.get("/endpoint", response_model=IntelligenceResponse)
    async def my_endpoint(): ...
"""

from typing import Any

from pydantic import BaseModel, Field

# ==== Intelligence Envelope ====
# Used by intelligence_router.py and spec_router.py intelligence endpoints.
# Shape: {status, data, computed_at, params, error?, error_code?}


class IntelligenceResponse(BaseModel):
    """Standard intelligence endpoint envelope."""

    status: str = Field(description="ok or error")
    data: Any = Field(default=None, description="Response payload")
    computed_at: str = Field(description="ISO timestamp of computation")
    params: dict[str, Any] = Field(default_factory=dict, description="Echo of request params")
    error: str | None = Field(default=None, description="Error message if status=error")
    error_code: str | None = Field(default=None, description="Error code if status=error")


# ==== List Envelope ====
# Used by dozens of list/index endpoints.
# Shape: {items, total}


class ListResponse(BaseModel):
    """Standard list endpoint response."""

    items: list[Any] = Field(default_factory=list, description="Result items")
    total: int = Field(description="Total count")


# ==== Mutation Result ====
# Used by POST/PATCH/DELETE endpoints that return {success: bool, ...}.


class MutationResponse(BaseModel):
    """Standard mutation result."""

    success: bool = Field(description="Whether the operation succeeded")

    model_config = {"extra": "allow"}


# ==== Health Check ====


class HealthResponse(BaseModel):
    """Health check result."""

    status: str = Field(description="healthy or error")
    spec_version: str = Field(description="Spec version string")
    timestamp: str = Field(description="ISO timestamp")


# ==== Collector Sync Status ====
# One per-collector entry in CollectorOrchestrator.get_status() / /api/sync/status.
# Represents BOTH a healthy collector (init_failed=False) and one that failed to
# initialize (init_failed=True, init_error set). Healthy entries carry freshness
# and circuit-breaker signals; failed-init entries carry only enabled/healthy/init_*.


class CollectorStatusEntry(BaseModel):
    """Status of a single collector, healthy or init-failed."""

    enabled: bool = Field(description="Whether the collector is enabled")
    healthy: bool = Field(description="True only when no error, data fresh, breaker closed")
    status: str | None = Field(
        default=None, description="healthy, degraded, failed, or None for init-failed"
    )
    items_synced: int = Field(default=0, description="Items synced on the last cycle")
    last_sync: str | None = Field(default=None, description="ISO timestamp of last sync attempt")
    last_success: str | None = Field(default=None, description="ISO timestamp of last success")
    error: str | None = Field(default=None, description="Last sync error, if any")
    stale: bool = Field(default=False, description="True if data freshness has lapsed")
    circuit_breaker_state: str | None = Field(default=None, description="Circuit breaker state")
    sync_interval: int | None = Field(
        default=None, description="Configured sync interval (seconds)"
    )
    init_failed: bool = Field(
        default=False, description="True if the collector failed to initialize"
    )
    init_error: str | None = Field(default=None, description="Initialization error message, if any")


# ==== Client Index ====
# /clients returns grouped client buckets, not a flat list.


class ClientCountsResponse(BaseModel):
    """Counts breakdown for client index."""

    active: int = 0
    recently_active: int = 0
    cold: int = 0


class ClientIndexResponse(BaseModel):
    """Client index grouped by status."""

    active: list[Any] = Field(default_factory=list)
    recently_active: list[Any] = Field(default_factory=list)
    cold: list[Any] = Field(default_factory=list)
    counts: ClientCountsResponse = Field(default_factory=ClientCountsResponse)


# ==== Detail / Single-Item Responses ====
# Endpoints that return a single entity dict with varying fields.


class DetailResponse(BaseModel):
    """Single entity detail — shape varies per entity type."""

    model_config = {"extra": "allow"}


# ==== Paginated Variants ====
# Some domain-specific list endpoints use non-standard keys and pagination
# patterns that diverge from ListResponse (which uses `items` + `total`).
#
# Variance from ListResponse:
# - InvoiceListResponse: key='invoices', adds page/limit for offset pagination
# - EngagementListResponse: key='engagements', uses offset/limit (not page)
# - SignalListResponse: key='signals', adds summary dict and page (no limit)
# - TeamInvolvementResponse: key='involvement', total-only (no pagination params)
#
# These divergences exist because each domain endpoint evolved with its own
# consumer requirements. Consolidation was deferred to avoid breaking the UI.
# See also: ListResponse above for the standard pattern.


class InvoiceListResponse(BaseModel):
    """Client invoices — uses 'invoices' key with page/limit offset pagination."""

    invoices: list[Any] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    limit: int = Field(default=10)


class EngagementListResponse(BaseModel):
    """Engagement list — uses 'engagements' key with offset/limit pagination."""

    engagements: list[Any] = Field(default_factory=list)
    total: int = Field(default=0)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class SignalListResponse(BaseModel):
    """Client signals — uses 'signals' key with summary dict and page-only pagination."""

    summary: dict[str, Any] = Field(default_factory=dict)
    signals: list[Any] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)


class TeamInvolvementResponse(BaseModel):
    """Client team involvement — uses 'involvement' key with total-only (no pagination params)."""

    involvement: list[Any] = Field(default_factory=list)
    total: int = Field(default=0)


# ==== Inbox ====


class InboxResponse(BaseModel):
    """Inbox with counts and items."""

    counts: dict[str, Any] = Field(default_factory=dict)
    items: list[Any] = Field(default_factory=list)


class InboxRecentResponse(BaseModel):
    """Recently-actioned inbox items."""

    items: list[Any] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)


class InboxCountsResponse(BaseModel):
    """Inbox counts breakdown."""

    model_config = {"extra": "allow"}


# ==== Fix-Data ====


class FixDataResponse(BaseModel):
    """Data quality issues for manual resolution."""

    identity_conflicts: list[Any] = Field(default_factory=list)
    ambiguous_links: list[Any] = Field(default_factory=list)
    missing_mappings: list[Any] = Field(default_factory=list)
    total: int = Field(default=0)


# ==== Pattern Detection ====
# Typed contract for /intelligence/patterns endpoint.
# detect_all_patterns() returns {success, detection_errors, errors, patterns, ...}.
# This model surfaces detection health alongside results.


class PatternDetectionData(BaseModel):
    """Typed payload for pattern detection results."""

    patterns: list[Any] = Field(default_factory=list)
    total_detected: int = Field(default=0)
    detection_success: bool = Field(default=True)
    detection_errors: int = Field(default=0)
    detection_error_details: list[str] = Field(default_factory=list)


class PatternDetectionResponse(BaseModel):
    """Typed envelope for /intelligence/patterns — extends IntelligenceResponse shape."""

    status: str = Field(description="ok or error")
    data: PatternDetectionData | None = Field(default=None)
    computed_at: str = Field(description="ISO timestamp of computation")
    params: dict[str, Any] = Field(default_factory=dict, description="Echo of request params")
    error: str | None = Field(default=None, description="Error message if status=error")
    error_code: str | None = Field(default=None, description="Error code if status=error")
