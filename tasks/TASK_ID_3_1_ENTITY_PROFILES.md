# ID-3.1: Entity Intelligence Profiles
> Brief: Intelligence Depth & Cross-Domain Synthesis | Phase: 3 | Sequence: 3.1 | Status: PENDING

## Objective

Build EntityIntelligenceProfile dataclass that synthesizes all intelligence dimensions for a single entity (client, project, engagement, invoice) into one coherent view. This provides a unified interface for accessing health, cost, risk, and cross-domain insights about any entity.

## Implementation

### New File: `lib/intelligence/entity_profile.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Literal
from enum import Enum

class AttentionLevel(Enum):
    """Entity attention priority level."""
    URGENT = "urgent"       # Any CRITICAL signal or structural compound risk
    ELEVATED = "elevated"   # WARNING signal or operational pattern
    NORMAL = "normal"       # WATCH signals only
    STABLE = "stable"       # No active findings


@dataclass
class ScoreDimension:
    """One dimension of entity health."""
    dimension: str  # 'delivery' | 'communication' | 'financial' | 'engagement' | 'structural'
    score: float    # 0.0 to 100.0
    trend: str      # 'improving' | 'stable' | 'declining'


@dataclass
class SignalSnapshot:
    """Current state of one active signal."""
    signal_key: str
    signal_type: str
    severity: str  # 'CRITICAL' | 'WARNING' | 'WATCH'
    detected_at: datetime
    latest_value: float


@dataclass
class PatternSnapshot:
    """Current state of one active pattern."""
    pattern_key: str
    pattern_type: str
    direction: str  # 'new' | 'persistent' | 'resolving' | 'worsening'
    entity_count: int  # How many entities exhibit this pattern
    confidence: float  # 0.0 to 1.0


@dataclass
class CompoundRisk:
    """Cross-domain risk from correlation of signals."""
    correlation_id: str
    title: str  # Human-readable title: "Chronic understaffing driven by project overload"
    signals: List[str]  # signal_keys that contribute
    severity: str  # 'CRITICAL' | 'WARNING' | 'WATCH'
    confidence: float  # 0.0 to 1.0 (computed per ID-1.1)
    is_structural: bool  # True = structural issue (affects future potential)


@dataclass
class CostProfile:
    """Cost-to-serve and profitability metrics."""
    effort_score: float
    profitability_band: str  # 'very_profitable' | 'profitable' | 'breakeven' | 'unprofitable' | 'unknown'
    estimated_cost_per_month: float
    cost_drivers: List[str]  # Top 2-3: "high task aging", "diverse team", "invoice overhead"


@dataclass
class EntityIntelligenceProfile:
    """Complete intelligence view of an entity."""
    
    # Identity
    entity_type: str  # 'client' | 'project' | 'engagement' | 'invoice'
    entity_id: str
    entity_name: str
    
    # Health
    health_score: float  # 0.0 to 100.0, aggregated from dimensions
    health_classification: str  # 'thriving' | 'healthy' | 'at_risk' | 'critical'
    score_dimensions: List[ScoreDimension]  # Breakdown by category
    
    # Signals
    active_signals: List[SignalSnapshot]  # Currently active signals
    signal_trend: str  # 'improving' | 'stable' | 'deteriorating'
    
    # Patterns
    active_patterns: List[PatternSnapshot]  # Currently detected patterns
    pattern_direction: str  # 'stabilizing' | 'neutral' | 'destabilizing'
    
    # Trajectory
    trajectory_direction: str  # 'toward_health' | 'stable' | 'toward_risk'
    projected_score_30d: float  # Estimated health score 30 days from now
    confidence_band: tuple  # (lower_bound, upper_bound) for projection uncertainty
    
    # Costs
    cost_profile: CostProfile
    
    # Cross-domain risks
    compound_risks: List[CompoundRisk] = field(default_factory=list)
    cross_domain_issues: List[str] = field(default_factory=list)  # Issues spanning multiple domains
    
    # Narrative
    narrative: str  # 2-3 sentence human-readable summary
    attention_level: AttentionLevel  # Urgency for human review
    recommended_actions: List[str] = field(default_factory=list)  # Top 2-3 recommended next steps
    
    # Metadata
    as_of: datetime = field(default_factory=datetime.now)
    next_review_date: Optional[datetime] = None


def build_entity_profile(
    entity_type: str,
    entity_id: str,
    entity_name: str,
    health_calculator,
    signal_repository,
    pattern_repository,
    correlation_engine,
    cost_calculator,
    narrative_builder
) -> EntityIntelligenceProfile:
    """
    Assemble complete EntityIntelligenceProfile from all intelligence sources.
    
    Orchestration function that:
    1. Fetches health score and dimensions
    2. Fetches active signals and computes trend
    3. Fetches active patterns and computes direction
    4. Computes trajectory and projects 30-day score
    5. Fetches cost profile and identifies drivers
    6. Fetches compound risks and cross-domain issues
    7. Generates narrative using NarrativeBuilder
    8. Determines attention_level
    9. Recommends actions
    
    Performance target: < 500ms per entity
    """
```

### New File: `lib/intelligence/narrative.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

class NarrativeBuilder:
    """Generates human-readable narratives from intelligence profiles."""

    def build_narrative(
        self,
        entity_type: str,
        entity_name: str,
        health_score: float,
        active_signals: List[dict],  # [{'type': ..., 'severity': ...}, ...]
        active_patterns: List[dict],  # [{'type': ..., 'direction': ...}, ...]
        compound_risks: List[dict],   # [{'title': ..., 'severity': ...}, ...]
        cost_profile: dict,
        trajectory_direction: str,
        projected_score_30d: float
    ) -> str:
        """
        Generate 2-3 sentence summary of entity intelligence.
        
        Example outputs:
        - "Client health declining due to project delays and staff turnover. Cost-to-serve rising 
           with diverse team but profitability stable. Recommend immediate scope review."
        - "Project tracking well with stable delivery and communication. Cost structure efficient. 
           No action required."
        - "Critical risk: understaffing compounded by scope creep. Health projected to 
           deteriorate further in 30 days without intervention."
        """

    def build_action_recommendations(
        self,
        health_classification: str,
        active_signals: List[dict],
        compound_risks: List[dict],
        cost_profile: dict,
        trajectory_direction: str
    ) -> List[str]:
        """
        Generate 2-3 recommended next actions based on intelligence.
        
        Returns list of strings like:
        - "Schedule client check-in: health below 60 and declining"
        - "Review project scope: compound risk of understaffing + scope creep"
        - "Increase invoice frequency: cost-to-serve exceeds profitability"
        """

    def build_cross_domain_summary(
        self,
        signals_by_domain: dict,      # domain -> [signals]
        patterns_by_domain: dict,      # domain -> [patterns]
        compound_risks: List[dict]
    ) -> List[str]:
        """
        Identify and describe issues spanning multiple domains.
        
        Returns list of cross-domain issues:
        - "Communication breakdown manifesting as late deliveries and client escalation"
        - "Resource constraint affecting both delivery timeline and invoice frequency"
        """

    def _format_signal_summary(self, signals: List[dict]) -> str:
        """Convert signal list to sentence fragment."""

    def _format_pattern_summary(self, patterns: List[dict]) -> str:
        """Convert pattern list to sentence fragment."""

    def _format_risk_summary(self, risks: List[dict]) -> str:
        """Convert compound risk list to sentence fragment."""
```

## Deepened Specifications

### Health Score Aggregation Formula

```
health_score = weighted average of score_dimensions

Weights by entity_type:
  CLIENT:
    delivery: 0.30
    communication: 0.25
    financial: 0.25
    engagement: 0.20

  PROJECT:
    delivery: 0.40
    communication: 0.20
    financial: 0.20
    engagement: 0.20

  PERSON:
    delivery: 0.35
    communication: 0.25
    engagement: 0.25
    financial: 0.15

health_score = Σ(dimension.score × weight) / Σ(weight)
```

### Health Classification Mapping

```python
def classify_health(score: float) -> str:
    if score >= 90: return "thriving"
    if score >= 70: return "healthy"
    if score >= 50: return "at_risk"
    return "critical"
```

### Trajectory Computation Algorithm

```python
def compute_trajectory(score_history: list[tuple[date, float]], days: int = 30) -> dict:
    """
    Uses recency-weighted linear regression from TC-3.1 if available,
    falls back to simple linear regression.

    1. Fetch score_history for entity over last `days` business days
    2. If fewer than 3 data points → trajectory = "insufficient_data"
    3. Compute weighted linear regression (slope, intercept, R²)
    4. projected_score_30d = current_score + (slope × 30)
    5. Clamp projected_score_30d to [0, 100]

    Direction:
      slope > +0.3 per business day → "toward_health"
      slope < -0.3 per business day → "toward_risk"
      else → "stable"

    Confidence band:
      std_residual = standard deviation of regression residuals
      confidence_band = (
          max(0, projected_score_30d - 2 × std_residual),
          min(100, projected_score_30d + 2 × std_residual)
      )

    If std_residual > 15 → confidence = "low"
    If std_residual 5-15 → confidence = "moderate"
    If std_residual < 5 → confidence = "high"
    """
```

### Signal Trend Computation

```python
def compute_signal_trend(current_signals: list, previous_cycle_signals: list) -> str:
    """
    Compare active signals between current and previous cycle.

    count_change = len(current) - len(previous)
    severity_change = sum(severity_to_int(s) for s in current) - sum(severity_to_int(s) for s in previous)

    where severity_to_int: CRITICAL=3, WARNING=2, WATCH=1

    if severity_change > 0 or count_change > 2: return "deteriorating"
    if severity_change < 0 or count_change < -2: return "improving"
    return "stable"
    """
```

### Pattern Direction Aggregation

```python
def compute_pattern_direction(patterns: list[PatternSnapshot]) -> str:
    """
    Aggregate individual pattern directions into entity-level assessment.

    worsening_count = count where direction == "worsening"
    resolving_count = count where direction == "resolving"

    if worsening_count > resolving_count: return "destabilizing"
    if resolving_count > worsening_count: return "stabilizing"
    return "neutral"
    """
```

### Attention Level Determination

```python
def determine_attention_level(
    signals: list[SignalSnapshot],
    compound_risks: list[CompoundRisk],
    health_classification: str
) -> AttentionLevel:
    """
    Priority order (first match wins):
    1. Any CRITICAL signal → URGENT
    2. Any structural compound risk → URGENT
    3. health_classification == "critical" → URGENT
    4. Any WARNING signal → ELEVATED
    5. Any operational pattern (not informational) → ELEVATED
    6. health_classification == "at_risk" → ELEVATED
    7. Any WATCH signal → NORMAL
    8. No active findings → STABLE
    """
```

### Next Review Date Logic

```python
def compute_next_review(attention_level: AttentionLevel, as_of: datetime) -> datetime:
    review_intervals = {
        AttentionLevel.URGENT: timedelta(days=1),
        AttentionLevel.ELEVATED: timedelta(days=7),
        AttentionLevel.NORMAL: timedelta(days=30),
        AttentionLevel.STABLE: timedelta(days=90),
    }
    return as_of + review_intervals[attention_level]
```

### Narrative Generation Rules (Template-Driven, No LLM)

```python
class NarrativeBuilder:
    """
    Rule-based narrative construction. Each narrative has 2-3 sentences:

    Sentence 1: Health status summary
      Template: "{entity_name} is {classification} with a health score of {score}."
      If trajectory != stable:
        Append: "Score is {direction} (projected {projected_score_30d} in 30 days)."

    Sentence 2: Key findings (pick the most significant)
      If CRITICAL signals exist:
        "Critical: {signal_summary}."
      Elif compound_risks with confidence > 0.7:
        "Cross-domain risk: {risk_title}."
      Elif WARNING signals:
        "Warning: {signal_summary}."
      Elif worsening patterns:
        "Pattern detected: {pattern_summary}."
      Else:
        "No significant issues detected."

    Sentence 3: Cost context (only if relevant)
      If cost_profile.profitability_band in ("breakeven", "unprofitable"):
        "Cost-to-serve {band}: driven by {top_driver}."

    Signal summary format:
      1 signal: "{signal_type} ({severity})"
      2 signals: "{sig1} and {sig2}"
      3+ signals: "{sig1}, {sig2}, and {count-2} more"
    """

    # Action Recommendation Rules:
    # 1. If attention_level == URGENT:
    #    → "Immediate review needed: {top_critical_signal_or_risk}"
    # 2. If trajectory == "toward_risk":
    #    → "Schedule check-in: health trending downward"
    # 3. If any overdue-related signal:
    #    → "Review and prioritize {count} overdue tasks"
    # 4. If communication_drop signal:
    #    → "Re-engage: communication volume declining"
    # 5. If cost_profile.profitability_band == "unprofitable":
    #    → "Review pricing: cost-to-serve exceeds revenue"
    # 6. If no issues:
    #    → "Continue monitoring — no action needed"
    #
    # Return top 3 recommendations, deduplicated.
```

## Validation

- [ ] EntityIntelligenceProfile instantiates with all required fields
- [ ] build_entity_profile() returns complete profile with no None values
- [ ] health_score matches aggregated dimensions
- [ ] health_classification correctly maps score ranges (90-100: thriving, 70-89: healthy, etc.)
- [ ] signal_trend computed from signal trajectory (improving/stable/deteriorating)
- [ ] pattern_direction reflects prevalence and direction changes (new/persistent/resolving/worsening)
- [ ] trajectory_direction aligns with signal_trend and pattern_direction
- [ ] projected_score_30d uses linear extrapolation from trend (not just guessing)
- [ ] confidence_band reflects uncertainty (wider if low-confidence signals, narrow if stable)
- [ ] attention_level logic: urgent for CRITICAL signals, elevated for WARNING, normal for WATCH only
- [ ] Narratives are coherent and reference actual findings (not template garbage)
- [ ] Narratives mention entity name, health status, and one key finding
- [ ] Recommended actions are specific and actionable (not generic)
- [ ] build_entity_profile() completes in < 500ms per entity
- [ ] Full portfolio (1000 entities) profiles in < 10 seconds

## Files Created
- New: `lib/intelligence/entity_profile.py`
- New: `lib/intelligence/narrative.py`

## Files Modified
- None (this is a new module, not a refactor)

## Estimated Effort
~300 lines — dataclass definitions, build orchestration, narrative templates and logic

