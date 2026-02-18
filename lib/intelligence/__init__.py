"""
MOH TIME OS Operational Intelligence Layer.

Single entry point for operational intelligence:
- Entity scoring (clients, projects, persons, portfolio)
- Signal detection (threshold, trend, anomaly, compound)
- Pattern detection (concentration, cascade, degradation, drift, correlation)
- Proposal generation and priority ranking
- Daily briefing generation

Usage:
    # Full intelligence snapshot
    from lib.intelligence import generate_intelligence_snapshot
    snapshot = generate_intelligence_snapshot()

    # Targeted intelligence
    from lib.intelligence import get_client_intelligence
    intel = get_client_intelligence(client_id="client-123")

    # Critical items only
    from lib.intelligence import get_critical_items
    urgent = get_critical_items()

    # Individual components
    from lib.intelligence import score_client, detect_all_signals
"""

# Main engine functions
# Change detection
from .changes import ChangeReport, run_change_detection
from .engine import (
    generate_intelligence_snapshot,
    get_client_intelligence,
    get_critical_items,
    get_person_intelligence,
    get_portfolio_intelligence,
)

# Patterns
from .patterns import (
    PATTERN_LIBRARY,
    detect_all_patterns,
    detect_pattern,
    get_pattern,
)

# Proposals
from .proposals import (
    PriorityScore,
    Proposal,
    ProposalType,
    ProposalUrgency,
    generate_daily_briefing,
    generate_proposals,
    get_top_proposals,
    rank_proposals,
)

# Scoring
from .scorecard import (
    score_all_clients,
    score_all_persons,
    score_all_projects,
    score_client,
    score_person,
    score_portfolio,
    score_project,
)

# Signals
from .signals import (
    detect_all_signals,
    detect_signals_for_entity,
    get_active_signals,
    get_signal_history,
    get_signal_summary,
    update_signal_state,
)

__all__ = [
    # Engine
    "generate_intelligence_snapshot",
    "get_client_intelligence",
    "get_person_intelligence",
    "get_portfolio_intelligence",
    "get_critical_items",
    # Change Detection
    "run_change_detection",
    "ChangeReport",
    # Scoring
    "score_client",
    "score_project",
    "score_person",
    "score_portfolio",
    "score_all_clients",
    "score_all_projects",
    "score_all_persons",
    # Signals
    "detect_all_signals",
    "detect_signals_for_entity",
    "get_active_signals",
    "get_signal_history",
    "get_signal_summary",
    "update_signal_state",
    # Patterns
    "detect_all_patterns",
    "detect_pattern",
    "get_pattern",
    "PATTERN_LIBRARY",
    # Proposals
    "generate_proposals",
    "rank_proposals",
    "get_top_proposals",
    "generate_daily_briefing",
    "Proposal",
    "ProposalType",
    "ProposalUrgency",
    "PriorityScore",
]
