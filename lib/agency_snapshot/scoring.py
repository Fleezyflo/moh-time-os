"""
Scoring Engine - BaseScore, ModeWeights, Eligibility Gates.

Per Page 0 spec §3, §5, §8.
"""

from dataclasses import dataclass
from enum import Enum


class Mode(Enum):
    OPS_HEAD = "Ops Head"
    CO_FOUNDER = "Co-Founder"
    ARTIST = "Artist"


class Horizon(Enum):
    NOW = "NOW"  # 4h
    TODAY = "TODAY"
    THIS_WEEK = "THIS_WEEK"


class Confidence(Enum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


class Domain(Enum):
    DELIVERY = "delivery"
    MONEY = "money"
    CLIENTS = "clients"
    CAPACITY = "capacity"
    COMMS = "comms"
    BLOCKED = "blocked"
    COMMITMENT = "commitment"
    UNKNOWN = "unknown"


# Mode weights per Page 0 §1.1 (locked)
MODE_WEIGHTS = {
    Mode.OPS_HEAD: {
        Domain.DELIVERY: 0.40,
        Domain.MONEY: 0.10,
        Domain.CLIENTS: 0.10,
        Domain.CAPACITY: 0.25,
        Domain.COMMS: 0.15,
        Domain.BLOCKED: 0.15,  # Same as comms
        Domain.COMMITMENT: 0.15,  # Treated as delivery in Ops Head unless blocking
        Domain.UNKNOWN: 0.05,
    },
    Mode.CO_FOUNDER: {
        Domain.DELIVERY: 0.15,
        Domain.MONEY: 0.35,
        Domain.CLIENTS: 0.35,
        Domain.CAPACITY: 0.05,
        Domain.COMMS: 0.10,
        Domain.BLOCKED: 0.10,
        Domain.COMMITMENT: 0.10,
        Domain.UNKNOWN: 0.05,
    },
    Mode.ARTIST: {
        Domain.DELIVERY: 0.25,
        Domain.MONEY: 0.10,
        Domain.CLIENTS: 0.10,
        Domain.CAPACITY: 0.35,
        Domain.COMMS: 0.20,
        Domain.BLOCKED: 0.20,
        Domain.COMMITMENT: 0.20,
        Domain.UNKNOWN: 0.05,
    },
}

# Confidence scalar per Page 0 §8.1
CONFIDENCE_SCALAR = {
    Confidence.HIGH: 1.0,
    Confidence.MED: 0.6,
    Confidence.LOW: 0.3,
}


def clamp01(value: float) -> float:
    """Clamp value to 0..1 range."""
    return max(0.0, min(1.0, value))


@dataclass
class ScoredItem:
    """A scored item for ranking."""

    entity_type: str  # project, client, lane, person, ar, thread
    entity_id: str
    domain: Domain

    # Base dimensions (0..1 each)
    impact: float
    urgency: float
    controllability: float
    confidence: Confidence

    # Computed
    time_to_consequence_hours: float | None = None

    # Flags for eligibility
    dependency_breaker: bool = False
    capacity_blocker_today: bool = False
    tomorrow_starts_broken: bool = False
    critical_path: bool = False
    compounding_damage: bool = False
    ar_severe: bool = False

    # Additional context
    title: str = ""
    top_driver: str = ""
    why_low: list = None

    def __post_init__(self):
        if self.why_low is None:
            self.why_low = []


class BaseScorer:
    """
    Computes BaseScore per Page 0 §8.1.

    BaseScore = 0.30*Impact + 0.30*Urgency + 0.20*Controllability + 0.20*ConfidenceScalar
    """

    # Weights per Page 0 §8.1 (locked)
    W_IMPACT = 0.30
    W_URGENCY = 0.30
    W_CONTROLLABILITY = 0.20
    W_CONFIDENCE = 0.20

    @classmethod
    def compute(cls, item: ScoredItem) -> float:
        """Compute base score for an item."""
        confidence_scalar = CONFIDENCE_SCALAR.get(item.confidence, 0.6)

        base_score = (
            cls.W_IMPACT * clamp01(item.impact)
            + cls.W_URGENCY * clamp01(item.urgency)
            + cls.W_CONTROLLABILITY * clamp01(item.controllability)
            + cls.W_CONFIDENCE * confidence_scalar
        )

        return clamp01(base_score)

    @classmethod
    def compute_urgency_from_ttc(cls, ttc_hours: float | None) -> float:
        """
        Convert time_to_consequence (hours) to urgency score (0..1).

        Uses inverse mapping:
        - 0h (now/overdue) → 1.0
        - 12h → 0.7
        - 24h → 0.5
        - 168h (1 week) → 0.1
        - >168h → approaches 0
        """
        if ttc_hours is None:
            return 0.0

        if ttc_hours <= 0:
            return 1.0  # Overdue or now

        if ttc_hours <= 12:
            return 1.0 - (ttc_hours / 12) * 0.3  # 1.0 → 0.7

        if ttc_hours <= 24:
            return 0.7 - ((ttc_hours - 12) / 12) * 0.2  # 0.7 → 0.5

        if ttc_hours <= 168:  # 1 week
            return 0.5 - ((ttc_hours - 24) / 144) * 0.4  # 0.5 → 0.1

        # Beyond 1 week, decay slowly
        return max(0.0, 0.1 - (ttc_hours - 168) / 1000)


class ModeWeights:
    """
    Apply mode weights to compute ModeWeightedScore.

    ModeWeightedScore = BaseScore * DomainWeight(mode, domain)
    """

    @classmethod
    def compute(cls, item: ScoredItem, mode: Mode) -> float:
        """Compute mode-weighted score."""
        base_score = BaseScorer.compute(item)
        domain_weight = MODE_WEIGHTS.get(mode, MODE_WEIGHTS[Mode.OPS_HEAD]).get(item.domain, 0.1)
        return base_score * domain_weight

    @classmethod
    def get_domain_weight(cls, mode: Mode, domain: Domain) -> float:
        """Get weight for a domain in given mode."""
        return MODE_WEIGHTS.get(mode, MODE_WEIGHTS[Mode.OPS_HEAD]).get(domain, 0.1)


class EligibilityGates:
    """
    Eligibility gates per Page 0 §5.

    Filter-before-rank: items must pass eligibility to surface.
    """

    @classmethod
    def is_eligible(cls, item: ScoredItem, horizon: Horizon) -> bool:
        """Check if item is eligible for the given horizon."""
        ttc = item.time_to_consequence_hours

        # High impact items are always eligible (slip risk >= 0.5 or impact >= 0.5)
        high_impact = item.impact >= 0.5

        if horizon == Horizon.NOW:
            # NOW: ttc ≤ 12h OR dependency_breaker OR capacity_blocker_today OR high_impact
            if ttc is not None and ttc <= 12:
                return True
            if item.dependency_breaker:
                return True
            if item.capacity_blocker_today:
                return True
            return bool(high_impact and (ttc is None or ttc <= 24))

        if horizon == Horizon.TODAY:
            # TODAY: ttc ≤ EOD (~16h assumed) OR tomorrow_starts_broken OR high_impact
            if ttc is not None and ttc <= 16:
                return True
            if item.tomorrow_starts_broken:
                return True
            # Include high impact items or those with TTC within 48h
            if high_impact:
                return True
            if ttc is not None and ttc <= 48:
                return True
            # Also include items with no TTC but high urgency (overdue tasks, etc)
            if ttc is not None and ttc < 0:  # Overdue
                return True
            return False

        if horizon == Horizon.THIS_WEEK:
            # THIS_WEEK: critical_path OR compounding_damage OR ar_severe OR has TTC
            if item.critical_path:
                return True
            if item.compounding_damage:
                return True
            if item.ar_severe:
                return True
            # Include if TTC within week or no TTC but has impact
            if ttc is not None and ttc <= 168:
                return True
            return bool(ttc is None and item.impact > 0.3)

        return False

    @classmethod
    def is_unknown_triage_eligible(cls, item: ScoredItem) -> bool:
        """
        Check if unknown triage item can surface per §5.2.

        Unknown triage can surface only if:
        - blocks an eligible item (dependency_breaker=true), OR
        - is in resolution queue P1, OR
        - is finance AR with money-impact above threshold
        """
        if item.dependency_breaker:
            return True
        # P1 and finance checks would need additional context
        return False


def rank_items(
    items: list[ScoredItem], mode: Mode, horizon: Horizon, max_items: int = 7
) -> list[ScoredItem]:
    """
    Rank items per Page 0 §8.

    1. Filter by eligibility
    2. Compute ModeWeightedScore
    3. Sort descending
    4. Apply tie-breakers: shortest TTC → highest controllability → highest confidence
    5. Cap at max_items
    """
    # Filter eligible
    eligible = [item for item in items if EligibilityGates.is_eligible(item, horizon)]

    # Compute scores
    scored = []
    for item in eligible:
        mode_score = ModeWeights.compute(item, mode)
        scored.append((mode_score, item))

    # Sort with tie-breakers
    def sort_key(pair):
        score, item = pair
        # Primary: score desc (negative for desc)
        # Tie-breaker 1: shortest TTC (ascending, None is worst)
        ttc = (
            item.time_to_consequence_hours if item.time_to_consequence_hours is not None else 99999
        )
        # Tie-breaker 2: highest controllability (desc)
        # Tie-breaker 3: highest confidence (desc)
        conf_order = {Confidence.HIGH: 0, Confidence.MED: 1, Confidence.LOW: 2}
        return (-score, ttc, -item.controllability, conf_order.get(item.confidence, 2))

    scored.sort(key=sort_key)

    return [item for _, item in scored[:max_items]]
