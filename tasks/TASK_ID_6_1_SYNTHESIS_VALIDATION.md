# ID-6.1: Synthesis & Validation
> Brief: Intelligence Depth & Cross-Domain Synthesis | Phase: 6 | Sequence: 6.1 | Status: PENDING

## Objective

Integrate all ID-1 through ID-5 modules into a unified intelligence pipeline. Build comprehensive test suite that validates correctness, coherence, and performance of entity profile synthesis across the full portfolio.

## Implementation

### Assembly Function: `lib/intelligence/entity_profile.py`

Complete the `build_entity_profile()` function with full orchestration:

```python
def build_entity_profile(
    entity_type: str,
    entity_id: str,
    entity_name: str,
    db_path: Path,
) -> EntityIntelligenceProfile:
    """
    Single entry point. Internally instantiates all required components.
    This avoids callers needing to wire dependencies manually.

    Performance target: < 500ms per entity

    Step-by-step orchestration:
    """
    # --- Step 1: Health score and dimensions ---
    # Read from score_history (latest entry for this entity)
    # If no score_history: compute live via scorecard
    # score_dimensions = parse dimensions_json from score_history row
    # health_score = weighted average per ID-3.1 formula
    # health_classification = classify_health(health_score)

    # --- Step 2: Score history for trajectory ---
    # Fetch last 30 days of score_history for this entity
    # If < 3 data points: trajectory = "insufficient_data", projected = health_score
    # Else: use RecencyWeighter.weighted_trend() from TC-3.1 if available
    #        fallback: simple linear regression
    # trajectory_direction, projected_score_30d, confidence_band = compute_trajectory(history)

    # --- Step 3: Active signals ---
    # Query signal_state WHERE entity_type=X AND entity_id=Y AND cleared_at IS NULL
    # Convert to list[SignalSnapshot]
    # Compute signal_trend via compute_signal_trend() from ID-3.1 deepened spec
    # Previous cycle signals: query intelligence_events for last cycle

    # --- Step 4: Active patterns ---
    # Query pattern_snapshots for latest cycle WHERE entity_id in entities_json
    # For each pattern: call PatternTrendAnalyzer.classify_direction() from ID-5.1
    # Compute pattern_direction via compute_pattern_direction() from ID-3.1

    # --- Step 5: Compound risks ---
    # Call correlation_engine.detect_compound_risks(entity_type, entity_id)
    # For each: compute confidence via CorrelationConfidenceCalculator from ID-1.1
    # Convert to list[CompoundRisk]

    # --- Step 6: Cross-domain issues ---
    # Group signals by domain (delivery, communication, financial, engagement)
    # If compound risk spans 2+ domains → add to cross_domain_issues
    # Use narrative_builder.build_cross_domain_summary()

    # --- Step 7: Cost profile ---
    # Fetch task data, assignees, threads, invoices, project_count from DB
    # Call ImprovedCostCalculator.calculate() from ID-2.1
    # Map to CostProfile dataclass

    # --- Step 8: Narrative ---
    # Call narrative_builder.build_narrative() with all collected data
    # Call narrative_builder.build_action_recommendations()

    # --- Step 9: Attention level ---
    # Call determine_attention_level() from ID-3.1 deepened spec

    # --- Step 10: Next review date ---
    # Call compute_next_review(attention_level, now)

    # --- Step 11: Assemble and return ---
    return EntityIntelligenceProfile(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        health_score=health_score,
        health_classification=health_classification,
        score_dimensions=score_dimensions,
        active_signals=active_signals,
        signal_trend=signal_trend,
        active_patterns=active_patterns,
        pattern_direction=pattern_direction,
        trajectory_direction=trajectory_direction,
        projected_score_30d=projected_score_30d,
        confidence_band=confidence_band,
        cost_profile=cost_profile,
        compound_risks=compound_risks,
        cross_domain_issues=cross_domain_issues,
        narrative=narrative,
        attention_level=attention_level,
        recommended_actions=recommended_actions,
        as_of=datetime.now(),
        next_review_date=next_review_date,
    )


def build_portfolio_profiles(
    entity_type: str,
    db_path: Path,
    limit: int = 1000,
) -> list[EntityIntelligenceProfile]:
    """Build profiles for all entities of a type.
    Performance target: < 10 seconds for 1000 entities.

    Optimization: batch-load shared data (signals, patterns) once,
    then assemble per-entity. Don't query DB per entity.

    Batch strategy:
    1. Load ALL latest score_history rows for entity_type
    2. Load ALL active signal_state rows for entity_type
    3. Load ALL latest pattern_snapshots
    4. Load ALL cost data (tasks, invoices, threads) grouped by entity_id
    5. For each entity: assemble from pre-loaded data (no additional queries)
    """
```

### Test Fixture Definitions

#### `tests/fixtures/seed_intelligence_data.py`

```python
"""
Seed a test database with comprehensive intelligence data for validation.
All data is deterministic — same seed produces same data.
"""

def seed_intelligence_db(db_path: Path) -> dict:
    """
    Creates and populates a test database with:

    Entities:
      - 5 clients: "Alpha Corp" (critical, score=35), "Beta LLC" (at_risk, score=55),
        "Gamma Inc" (healthy, score=78), "Delta Co" (thriving, score=92), "Epsilon Ltd" (at_risk, score=48)
      - 10 projects: 2 per client, mix of healthy and struggling
      - 5 persons: varying workload levels

    Score History (30 days):
      - Alpha Corp: declining trend (70→35 over 30 days)
      - Beta LLC: stable with recent dip (60→55)
      - Gamma Inc: improving (65→78)
      - Delta Co: consistently high (88→92)
      - Epsilon Ltd: volatile (65→48→55→48)

    Active Signals:
      - Alpha Corp: 3 signals (1 CRITICAL: payment_overdue, 1 WARNING: task_overdue, 1 WATCH: comm_drop)
      - Beta LLC: 2 signals (1 WARNING: invoice_aging, 1 WATCH: response_slow)
      - Gamma Inc: 1 signal (1 WATCH: minor_overdue)
      - Delta Co: 0 signals
      - Epsilon Ltd: 2 signals (1 WARNING: task_overdue, 1 WARNING: scope_creep)

    Patterns (latest cycle):
      - "revenue_concentration" affecting [Alpha, Beta, Gamma] — structural, persistent
      - "delivery_cascade" affecting [Alpha, Epsilon] — operational, worsening
      - "engagement_degradation" affecting [Alpha] — operational, new

    Compound Risks:
      - Alpha Corp: "payment_cascade" (payment_overdue + task_overdue + comm_drop) — CRITICAL confidence ~0.85
      - Epsilon Ltd: "scope_delivery_risk" (task_overdue + scope_creep) — WARNING confidence ~0.65

    Cost Data:
      - Alpha Corp: 45 tasks (12 overdue), 8 assignees, 120 email threads, 3 projects
      - Beta LLC: 20 tasks (3 overdue), 4 assignees, 60 threads, 2 projects
      - Gamma Inc: 30 tasks (1 overdue), 5 assignees, 80 threads, 2 projects
      - Delta Co: 15 tasks (0 overdue), 3 assignees, 40 threads, 1 project
      - Epsilon Ltd: 35 tasks (8 overdue), 6 assignees, 90 threads, 3 projects

    Returns:
      dict mapping entity_id → expected profile values for assertion
    """
```

### Test Files

#### New: `tests/test_entity_profile.py`

```python
import pytest
from datetime import datetime, timedelta
from lib.intelligence.entity_profile import (
    EntityIntelligenceProfile, build_entity_profile, AttentionLevel
)

class TestEntityProfileBuilding:
    """Test entity profile assembly and synthesis."""
    
    def test_profile_instantiation(self):
        """EntityIntelligenceProfile dataclass instantiates with all required fields."""
    
    def test_build_profile_complete_fields(self):
        """build_entity_profile() returns profile with no None values."""
    
    def test_health_score_matches_dimensions(self):
        """health_score aggregation matches computed dimensions."""
    
    def test_health_classification_mapping(self, health_score):
        """Score ranges map to correct classifications:
        90-100: thriving, 70-89: healthy, 50-69: at_risk, 0-49: critical"""
    
    def test_signal_trend_computation(self):
        """signal_trend correctly reflects trajectory:
        increasing signal count or severity → deteriorating
        decreasing → improving
        stable → stable"""
    
    def test_pattern_direction_from_trending(self):
        """active_patterns include direction from PatternTrendAnalyzer."""
    
    def test_compound_risks_included(self):
        """Compound risks appear in profile with computed confidence."""
    
    def test_cross_domain_issues_identified(self):
        """Cross-domain issues correctly identified:
        - Issues spanning multiple signal domains
        - Issues from compound risks linking multiple domains"""
    
    def test_attention_level_logic(self):
        """Attention level correctly determined:
        - URGENT: any CRITICAL signal or structural compound risk
        - ELEVATED: WARNING signal or operational pattern
        - NORMAL: WATCH signals only
        - STABLE: no active findings"""
    
    def test_narrative_coherence(self):
        """Generated narrative:
        - 2-3 sentences
        - References entity name
        - Mentions key findings (health, signals, or risks)
        - Grammatically correct"""
    
    def test_narrative_specificity(self):
        """Narratives are specific to findings, not generic templates."""
    
    def test_recommended_actions_specificity(self):
        """Recommended actions are actionable and specific:
        - Not generic ('monitor health')
        - Reference actual findings ('health declining due to project delays')"""
    
    def test_trajectory_direction_from_trend(self):
        """trajectory_direction aligns with signal_trend and pattern_direction."""
    
    def test_projected_score_30d(self):
        """projected_score_30d uses linear extrapolation:
        if current=70, trend indicates -5 pts/10 days → projected=65"""
    
    def test_confidence_band_reflects_uncertainty(self):
        """confidence_band wider for:
        - Low-confidence signals
        - High volatility patterns
        band narrower for:
        - Stable signals
        - Persistent patterns"""
    
    def test_cost_profile_integration(self):
        """Cost profile correctly imported with drivers identified."""
    
    def test_as_of_timestamp(self):
        """as_of timestamp is recent (within 1 second of build time)."""
    
    def test_next_review_date_logic(self):
        """next_review_date set based on attention_level:
        - URGENT: within 1 day
        - ELEVATED: within 7 days
        - NORMAL: within 30 days
        - STABLE: within 90 days"""


class TestPortfolioSynthesis:
    """Test entity profile generation across full portfolio."""
    
    def test_all_clients_generate_profiles(self, db_with_data):
        """All clients in portfolio generate profiles without error."""
    
    def test_all_projects_generate_profiles(self, db_with_data):
        """All projects in portfolio generate profiles without error."""
    
    def test_all_engagements_generate_profiles(self, db_with_data):
        """All engagements in portfolio generate profiles without error."""
    
    def test_portfolio_completion_time(self, db_with_1000_clients):
        """Full portfolio (1000 clients) completes in < 10 seconds."""
    
    def test_narrative_coverage(self, db_with_data):
        """All generated narratives are non-empty and coherent."""
    
    def test_no_duplicate_narratives(self, db_with_data):
        """Narratives are entity-specific (not duplicated across entities)."""
```

#### New: `tests/test_correlation_confidence.py`

```python
import pytest
from datetime import datetime, timedelta
from lib.intelligence.correlation_confidence import (
    CorrelationConfidenceCalculator, CorrelationSignalEvidence
)

class TestCorrelationConfidence:
    """Test confidence calculation for compound risks."""
    
    def test_full_completeness_high_confidence(self):
        """All required signals present → completeness = 1.0."""
    
    def test_missing_signal_lower_completeness(self):
        """50% signals present → completeness = 0.5."""
    
    def test_same_severity_high_alignment(self):
        """All signals same severity → alignment = 1.0."""
    
    def test_mixed_severity_lower_alignment(self):
        """Mixed severities → alignment < 1.0, scaled down appropriately."""
    
    def test_same_cycle_high_temporal(self):
        """All signals detected in current cycle → temporal = 1.0."""
    
    def test_old_signals_lower_temporal(self):
        """Signals detected 10 cycles ago → temporal close to 0.0."""
    
    def test_temporal_exponential_decay(self):
        """Temporal proximity decays exponentially, not linearly."""
    
    def test_persistent_pattern_high_recurrence(self):
        """Pattern present in 5/5 last cycles → recurrence = 1.0."""
    
    def test_new_pattern_low_recurrence(self):
        """Pattern present in 0/5 last cycles but active now → recurrence = 0.2 or less."""
    
    def test_high_confidence_scenario(self):
        """All factors strong → final confidence > 0.8."""
    
    def test_medium_confidence_scenario(self):
        """Mixed factors → final confidence in [0.4, 0.7]."""
    
    def test_low_confidence_scenario(self):
        """Weak factors → final confidence < 0.5."""
    
    def test_weighted_formula_correct(self):
        """Formula weights: 0.35 completeness, 0.25 alignment, 0.20 temporal, 0.20 recurrence."""
    
    def test_confidence_range_0_to_1(self, all_correlation_scenarios):
        """Confidence always in [0.0, 1.0], never outside bounds."""
    
    def test_factors_breakdown_accessible(self):
        """ConfidenceFactors dataclass accessible for debugging/inspection."""
```

#### New: `tests/test_cost_proxies.py`

```python
import pytest
from datetime import datetime, timedelta
from lib.intelligence.cost_proxies import ImprovedCostCalculator, CostComponents

class TestImprovedCostProxies:
    """Test cost-to-serve proxy calculations."""
    
    def test_weighted_task_age_sum(self):
        """Task age weighted by status:
        completed: 1.0x, active: 1.5x, overdue: 2.0x"""
    
    def test_assignee_diversity_factor(self):
        """sqrt(distinct_assignees) * 2.5."""
    
    def test_assignee_diversity_nonlinear(self):
        """Assignee diversity grows with sqrt, not linearly."""
    
    def test_communication_effort_message_buckets(self):
        """Message count buckets: 1 (0.5x), 2-5 (1.0x), 6-15 (1.5x), 16+ (2.0x)."""
    
    def test_communication_channel_weights(self):
        """Channel weights: email 1.0, slack 0.8, asana_comment 0.6."""
    
    def test_project_overhead_sqrt_scaling(self):
        """Project overhead = sqrt(project_count) * 10, grows sublinearly."""
    
    def test_invoice_overhead_calculation(self):
        """Invoice overhead = (invoice_count / max(total_invoiced, 1)) * 100."""
    
    def test_cost_components_sum(self):
        """Final effort_score = sum of all components."""
    
    def test_low_cost_client(self):
        """Simple client (few tasks, one person, minimal comms) → low score."""
    
    def test_high_cost_client(self):
        """Complex client (many tasks, diverse team, heavy comms) → high score."""
    
    def test_cost_computation_speed(self):
        """Cost calculation per client < 50ms."""
    
    def test_portfolio_cost_speed(self, db_with_1000_clients):
        """Full portfolio cost calculation < 5 seconds."""
    
    def test_component_breakdown_accessible(self):
        """CostComponents dataclass accessible with all factors."""
```

#### New: `tests/test_outcome_tracker.py`

```python
import pytest
from datetime import datetime, timedelta
from lib.intelligence.outcome_tracker import OutcomeTracker, SignalOutcome

class TestOutcomeTracking:
    """Test signal outcome recording and analysis."""
    
    def test_outcome_record_creation(self):
        """Outcome records created when signal clears."""
    
    def test_resolution_type_natural(self):
        """Resolution='natural' when health_after > health_before."""
    
    def test_resolution_type_addressed(self):
        """Resolution='addressed' when actions_taken is not empty."""
    
    def test_resolution_type_expired(self):
        """Resolution='expired' when threshold rules no longer match."""
    
    def test_resolution_type_unknown(self):
        """Resolution='unknown' when no health change and no actions."""
    
    def test_duration_days_calculation(self):
        """duration_days = cleared_at - detected_at."""
    
    def test_health_improved_flag(self):
        """health_improved = 1 iff health_after > health_before."""
    
    def test_get_outcomes_for_entity(self):
        """Retrieve outcomes for specific entity."""
    
    def test_get_outcomes_by_type(self):
        """Retrieve outcomes filtered by signal_type."""
    
    def test_get_outcomes_by_resolution(self):
        """Retrieve outcomes filtered by resolution_type."""
    
    def test_effectiveness_metrics_aggregation(self):
        """Effectiveness metrics correctly aggregate across outcomes."""
    
    def test_improvement_rate(self):
        """improvement_rate = count(health_improved=1) / total_outcomes."""
    
    def test_action_success_rate(self):
        """action_success_rate = among 'addressed' outcomes, fraction with health_improved."""
    
    def test_signal_type_breakdown(self):
        """Effectiveness metrics include per-signal_type breakdown."""
    
    def test_outcome_index_query_performance(self):
        """Outcome queries use indexes, complete in < 100ms."""
```

#### New: `tests/test_pattern_trending.py`

```python
import pytest
from datetime import datetime, timedelta
from lib.intelligence.pattern_trending import PatternTrendAnalyzer

class TestPatternTrending:
    """Test pattern direction classification."""
    
    def test_new_pattern_classification(self):
        """Pattern detected in current cycle only → direction='new'."""
    
    def test_persistent_pattern_classification(self):
        """Pattern in current + 3+ of last 5 cycles → direction='persistent'."""
    
    def test_resolving_pattern_classification(self):
        """Pattern in 3+ of last 5 but NOT current → direction='resolving'."""
    
    def test_worsening_pattern_classification(self):
        """Pattern in current cycle AND metrics increased → direction='worsening'."""
    
    def test_worsening_entity_count_increase(self):
        """Worsening detected when entity_count > avg + std_dev."""
    
    def test_worsening_strength_increase(self):
        """Worsening detected when evidence_strength > avg + std_dev."""
    
    def test_cycle_presence_history_order(self):
        """Presence history ordered most-recent-first: [current, -1, -2, -3, -4, -5]."""
    
    def test_get_entity_pattern_trends(self):
        """Retrieve all pattern trends for an entity."""
    
    def test_get_patterns_by_direction(self):
        """Filter patterns by direction across portfolio."""
    
    def test_pattern_trend_performance(self):
        """Single pattern analysis < 10ms."""
    
    def test_portfolio_refresh_performance(self, db_with_1000_entities):
        """Full portfolio refresh < 5 seconds."""
```

## Validation Checklist

General synthesis validation:
- [ ] All 6 prior modules (ID-1 through ID-5) integrated and callable
- [ ] build_entity_profile() orchestration complete
- [ ] Entity profiles build without errors for 100% of portfolio
- [ ] Narratives are coherent, entity-specific, and informative
- [ ] No null values in returned profiles (all fields populated)
- [ ] Correlation confidence varies meaningfully (not all 0.7)
- [ ] Cost-to-serve formulas shift profitability bands with new proxies
- [ ] Pattern trending correctly classifies new/persistent/resolving/worsening
- [ ] Outcome tracking captures signal lifecycle accurately
- [ ] Attention level logic correctly prioritizes urgent vs. normal findings

Performance validation:
- [ ] Single entity profile build: < 500ms
- [ ] Portfolio (1000 entities): < 10 seconds
- [ ] Confidence calculation: < 1ms per correlation
- [ ] Cost calculation: < 50ms per entity
- [ ] Outcome query (entity history): < 100ms
- [ ] Pattern trend analysis: < 10ms per pattern
- [ ] Portfolio pattern refresh: < 5 seconds

Quality validation:
- [ ] No hardcoded test values in narratives (all from actual data)
- [ ] All entity types (client, project, engagement, invoice) tested
- [ ] Edge cases handled (zero tasks, no signals, no patterns)
- [ ] Confidence bands reflect actual uncertainty
- [ ] No duplicated narratives across entities
- [ ] Recommended actions are specific and actionable
- [ ] Cross-domain issues correctly identify multi-domain correlations

## Files Created
- New: `tests/test_entity_profile.py`
- New: `tests/test_correlation_confidence.py`
- New: `tests/test_cost_proxies.py`
- New: `tests/test_outcome_tracker.py`
- New: `tests/test_pattern_trending.py`

## Files Modified
- Modified: `lib/intelligence/entity_profile.py` (complete build_entity_profile() orchestration)

## Estimated Effort
~300 lines test code, ~100 lines orchestration code — comprehensive test suite, integration validation, performance profiling
