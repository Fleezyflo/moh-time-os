"""
Schema Module — Pydantic Models for Agency Snapshot Shape Validation.

These models define the REQUIRED shape of the agency snapshot.
All critical sections are NON-OPTIONAL. Missing sections = validation failure.

Per IMPLEMENTATION_PLAN_V4_FROZEN.md:
- No Optional for critical sections
- Schema validation is a HARD GATE
- Production generator must validate before emit

UI SPEC VERSION: 2.9.0
This contract is bound to the frontend UI spec v2.9.0.
Any schema changes must be coordinated with frontend.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# =============================================================================
# CONTRACT VERSION — MUST MATCH FRONTEND UI SPEC
# =============================================================================

SCHEMA_VERSION = "2.9.0"


# =============================================================================
# CASH/AR SECTION (Page 3)
# =============================================================================


class AgingBucket(BaseModel):
    """Aging bucket for AR analysis."""

    bucket: Literal["current", "1-30", "31-60", "61-90", "90+"]
    amount: float
    count: int


class DebtorEntry(BaseModel):
    """Single debtor (client with unpaid invoices)."""

    client_id: str
    client_name: str
    currency: str = "AED"
    total_valid_ar: float
    severe_ar: float = 0.0
    aging_bucket: str
    days_overdue_max: int = 0
    invoice_count: int = 1
    risk_score: float = Field(ge=0.0, le=1.0, default=0.0)


class CashARTiles(BaseModel):
    """Tiles summary for Cash/AR command."""

    valid_ar: dict[str, float]  # by_currency
    severe_ar: dict[str, float]  # by_currency
    badge: Literal["RED", "YELLOW", "GREEN", "PARTIAL"]
    summary: str


class CashARSection(BaseModel):
    """
    Cash/AR Command section — REQUIRED.

    Must be present whenever unpaid invoices exist.
    Empty debtors with existing invoices = validation failure.
    """

    tiles: CashARTiles
    debtors: list[DebtorEntry] = Field(min_length=0)  # Can be empty if no AR
    aging_distribution: list[AgingBucket] = Field(default_factory=list)


# =============================================================================
# DELIVERY COMMAND SECTION (Page 1)
# =============================================================================


class PortfolioProject(BaseModel):
    """Project entry in delivery portfolio."""

    project_id: str
    name: str
    status: Literal["RED", "YELLOW", "GREEN", "UNKNOWN"]
    slip_risk_score: float = Field(ge=0.0, le=1.0, default=0.0)
    time_to_slip_hours: float | None = None
    overdue_count: int = 0
    total_tasks: int = 0
    top_driver: str | None = None
    confidence: Literal["HIGH", "MED", "LOW"] = "MED"


class DeliveryCommandSection(BaseModel):
    """Delivery Command section — REQUIRED."""

    portfolio: list[PortfolioProject] = Field(min_length=0)
    selected_project: dict | None = None


# =============================================================================
# HEATSTRIP (Page 0)
# =============================================================================


class HeatstripProject(BaseModel):
    """Project entry in heatstrip (top 25 at-risk)."""

    project_id: str
    name: str
    status: Literal["RED", "YELLOW", "GREEN", "UNKNOWN"]
    slip_risk_score: float = Field(ge=0.0, le=1.0, default=0.0)
    time_to_slip_hours: float | None = None
    top_driver: str | None = None
    confidence: Literal["HIGH", "MED", "LOW"] = "MED"
    overdue_count: int = 0
    total_tasks: int = 0


# =============================================================================
# CLIENT 360 SECTION (Page 2)
# =============================================================================


class ClientEntry(BaseModel):
    """Client entry in Client 360."""

    client_id: str
    name: str
    tier: Literal["A", "B", "C", "D", "untiered"] = "untiered"
    health_score: float = Field(ge=0.0, le=1.0, default=0.5)
    health_status: Literal["critical", "poor", "fair", "good", "excellent"] = "fair"
    total_ar: float = 0.0
    overdue_tasks: int = 0
    at_risk: bool = False


class Client360Section(BaseModel):
    """Client 360 section — REQUIRED."""

    portfolio: list[ClientEntry] = Field(default_factory=list)
    at_risk_count: int = 0
    drawer: dict = Field(default_factory=dict)


# =============================================================================
# COMMS/COMMITMENTS SECTION (Page 4)
# =============================================================================


class CommitmentEntry(BaseModel):
    """Single commitment (promise made to client)."""

    commitment_id: str
    content: str
    scope_ref_type: str  # client, project, thread, invoice, task
    scope_ref_id: str
    resolved_client_id: str | None = None
    unresolved_reason: str | None = None
    due_date: str | None = None
    is_overdue: bool = False


class ThreadEntry(BaseModel):
    """Communication thread entry."""

    thread_id: str
    subject: str
    client_id: str | None = None
    client_name: str | None = None
    last_activity: str | None = None
    commitment_count: int = 0


class CommsCommitmentsSection(BaseModel):
    """Comms/Commitments section — REQUIRED."""

    threads: list[ThreadEntry] = Field(default_factory=list)
    commitments: list[CommitmentEntry] = Field(default_factory=list)
    overdue_count: int = 0


# =============================================================================
# CAPACITY COMMAND SECTION (Page 5)
# =============================================================================


class PersonEntry(BaseModel):
    """Person in capacity overview."""

    person_id: str | None = None
    name: str
    hours_assigned: float = 0.0
    hours_capacity: float = 0.0
    utilization: float = Field(ge=0.0, default=0.0)
    gap_hours: float = 0.0
    is_overloaded: bool = False


class CapacityCommandSection(BaseModel):
    """Capacity Command section — REQUIRED."""

    people_overview: list[PersonEntry] = Field(default_factory=list)
    total_assigned: float = 0.0
    total_capacity: float = 0.0
    utilization_rate: float = Field(ge=0.0, le=2.0, default=0.0)  # Can exceed 1.0 if overloaded
    drawer: dict = Field(default_factory=dict)


# =============================================================================
# META & TRUST
# =============================================================================


class MetaSection(BaseModel):
    """Snapshot metadata."""

    generated_at: str
    finished_at: str | None = None
    duration_ms: float | None = None  # Renamed from duration_seconds for consistency
    mode: str = "Ops Head"
    horizon: str = "THIS_WEEK"
    scope: dict = Field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION  # MUST match UI spec version


class TrustSection(BaseModel):
    """Trust/confidence state."""

    coverage: dict[str, float] = Field(default_factory=dict)
    partial_domains: list[str] = Field(default_factory=list)
    gate_states: dict[str, bool] = Field(default_factory=dict)


# =============================================================================
# TOP-LEVEL CONTRACT
# =============================================================================


class AgencySnapshotContract(BaseModel):
    """
    Agency Snapshot Contract — The REQUIRED shape of agency_snapshot.json.

    ALL major sections are REQUIRED (not Optional).
    Missing sections = validation failure = generator error.

    Per IMPLEMENTATION_PLAN_V4_FROZEN.md Amendment 4:
    This validation runs in PRODUCTION, not just tests.

    Extra fields are FORBIDDEN - any unknown top-level key fails validation.
    """

    model_config = {"extra": "forbid"}  # Reject unknown fields

    # Required metadata (Page 0 spec)
    meta: MetaSection
    trust: TrustSection

    # Page 0 LOCKED STRUCTURE — ALL REQUIRED per spec lines 513-559
    narrative: dict  # REQUIRED: first_to_break + deltas (deltas is INSIDE narrative per spec)
    tiles: dict  # REQUIRED: 5 tiles (delivery, cash, clients, churn_x_money, delivery_x_capacity)
    heatstrip_projects: list[HeatstripProject]  # REQUIRED: max 25
    constraints: list  # REQUIRED: max 12
    exceptions: list  # REQUIRED: max 7
    drawers: dict  # REQUIRED: drawer data keyed by ref

    # Page 1+ Extensions — REQUIRED for full dashboard
    cash_ar: CashARSection
    delivery_command: DeliveryCommandSection
    client_360: Client360Section
    comms_commitments: CommsCommitmentsSection
    capacity_command: CapacityCommandSection

    # NOTE: No top-level 'deltas' field. Per spec, deltas lives inside narrative.deltas

    @field_validator("heatstrip_projects", mode="before")
    @classmethod
    def validate_heatstrip_not_none(cls, v):
        """Heatstrip cannot be None — use empty list if no projects."""
        if v is None:
            raise ValueError("heatstrip_projects cannot be None (use empty list)")
        return v

    @field_validator("cash_ar", mode="before")
    @classmethod
    def validate_cash_ar_not_none(cls, v):
        """Cash AR cannot be None — this is a critical section."""
        if v is None:
            raise ValueError("cash_ar cannot be None")
        return v

    @model_validator(mode="after")
    def validate_schema_version(self):
        """Ensure snapshot schema_version matches expected UI spec version."""
        actual = self.meta.schema_version
        if actual != SCHEMA_VERSION:
            raise ValueError(
                f"Schema version mismatch: snapshot has '{actual}', "
                f"but contract requires '{SCHEMA_VERSION}'. "
                f"Update generator or contract to align with frontend UI spec."
            )
        return self


# =============================================================================
# VALIDATION HELPER
# =============================================================================


def validate_snapshot_shape(snapshot: dict) -> AgencySnapshotContract:
    """
    Validate snapshot against contract schema.

    Raises:
        ValidationError: If snapshot shape is invalid

    Returns:
        Validated AgencySnapshotContract instance
    """
    return AgencySnapshotContract.model_validate(snapshot)
