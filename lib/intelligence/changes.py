"""
Change Detection for Intelligence Layer.

Tracks deltas between intelligence runs to highlight:
- New signals
- Cleared signals
- Escalated signals
- New proposals
- Score changes
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class IntelligenceSnapshot:
    """Point-in-time snapshot of intelligence state."""
    timestamp: str
    signal_count: int
    signal_ids: list[str]
    proposal_count: int
    proposal_ids: list[str]
    portfolio_score: float
    critical_count: int
    pattern_count: int


@dataclass
class ChangeReport:
    """Changes detected between two snapshots."""
    from_timestamp: str
    to_timestamp: str
    
    # Signals
    new_signals: list[str]
    cleared_signals: list[str]
    signal_delta: int
    
    # Proposals
    new_proposals: list[str]
    resolved_proposals: list[str]
    proposal_delta: int
    
    # Scores
    portfolio_score_delta: float
    portfolio_score_direction: str  # 'up', 'down', 'stable'
    
    # Critical items
    critical_delta: int
    
    # Patterns
    pattern_delta: int
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @property
    def has_changes(self) -> bool:
        """Check if any significant changes occurred."""
        return (
            len(self.new_signals) > 0 or
            len(self.cleared_signals) > 0 or
            len(self.new_proposals) > 0 or
            abs(self.portfolio_score_delta) > 5 or
            self.critical_delta != 0
        )
    
    @property
    def summary(self) -> str:
        """Human-readable summary of changes."""
        parts = []
        
        if self.new_signals:
            parts.append(f"+{len(self.new_signals)} signals")
        if self.cleared_signals:
            parts.append(f"-{len(self.cleared_signals)} signals")
        if self.new_proposals:
            parts.append(f"+{len(self.new_proposals)} proposals")
        if self.critical_delta > 0:
            parts.append(f"+{self.critical_delta} critical")
        elif self.critical_delta < 0:
            parts.append(f"{self.critical_delta} critical")
        if abs(self.portfolio_score_delta) > 5:
            direction = "↑" if self.portfolio_score_delta > 0 else "↓"
            parts.append(f"score {direction}{abs(self.portfolio_score_delta):.0f}")
        
        if not parts:
            return "No significant changes"
        
        return ", ".join(parts)


# Storage path for snapshots
SNAPSHOT_DIR = Path(__file__).parent.parent.parent / "data" / "snapshots"


def _ensure_snapshot_dir():
    """Ensure snapshot directory exists."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def save_snapshot(snapshot: IntelligenceSnapshot) -> Path:
    """Save a snapshot to disk."""
    _ensure_snapshot_dir()
    
    filename = f"snapshot_{snapshot.timestamp.replace(':', '-').replace('.', '-')}.json"
    path = SNAPSHOT_DIR / filename
    
    with open(path, 'w') as f:
        json.dump(asdict(snapshot), f, indent=2)
    
    return path


def load_latest_snapshot() -> Optional[IntelligenceSnapshot]:
    """Load the most recent snapshot."""
    _ensure_snapshot_dir()
    
    snapshots = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"), reverse=True)
    
    if not snapshots:
        return None
    
    try:
        with open(snapshots[0]) as f:
            data = json.load(f)
        return IntelligenceSnapshot(**data)
    except Exception as e:
        logger.warning(f"Failed to load snapshot: {e}")
        return None


def create_snapshot_from_intelligence(intel_data: dict) -> IntelligenceSnapshot:
    """Create a snapshot from intelligence data."""
    signals = intel_data.get("signals", {})
    proposals = intel_data.get("proposals", {})
    scores = intel_data.get("scores", {})
    patterns = intel_data.get("patterns", {})
    
    # Extract signal IDs
    signal_list = signals.get("by_severity", {})
    all_signals = (
        signal_list.get("critical", []) +
        signal_list.get("warning", []) +
        signal_list.get("watch", [])
    )
    signal_ids = [s.get("signal_id", str(i)) for i, s in enumerate(all_signals)]
    
    # Extract proposal IDs
    proposal_list = proposals.get("ranked", [])
    proposal_ids = [p.get("id", str(i)) for i, p in enumerate(proposal_list)]
    
    # Portfolio score
    portfolio = scores.get("portfolio", {})
    portfolio_score = portfolio.get("composite_score", 0) if isinstance(portfolio, dict) else 0
    
    # Critical count
    by_urgency = proposals.get("by_urgency", {})
    critical_count = len(by_urgency.get("immediate", []))
    
    return IntelligenceSnapshot(
        timestamp=datetime.now().isoformat(),
        signal_count=signals.get("total_active", 0),
        signal_ids=signal_ids,
        proposal_count=proposals.get("total", 0),
        proposal_ids=proposal_ids,
        portfolio_score=portfolio_score,
        critical_count=critical_count,
        pattern_count=patterns.get("total_detected", 0),
    )


def detect_changes(
    current: IntelligenceSnapshot,
    previous: Optional[IntelligenceSnapshot] = None
) -> ChangeReport:
    """
    Detect changes between current state and previous snapshot.
    
    If no previous snapshot, returns a report treating everything as new.
    """
    if previous is None:
        previous = IntelligenceSnapshot(
            timestamp="",
            signal_count=0,
            signal_ids=[],
            proposal_count=0,
            proposal_ids=[],
            portfolio_score=0,
            critical_count=0,
            pattern_count=0,
        )
    
    # Signal changes
    current_signals = set(current.signal_ids)
    previous_signals = set(previous.signal_ids)
    new_signals = list(current_signals - previous_signals)
    cleared_signals = list(previous_signals - current_signals)
    
    # Proposal changes
    current_proposals = set(current.proposal_ids)
    previous_proposals = set(previous.proposal_ids)
    new_proposals = list(current_proposals - previous_proposals)
    resolved_proposals = list(previous_proposals - current_proposals)
    
    # Score change
    score_delta = current.portfolio_score - previous.portfolio_score
    if score_delta > 2:
        score_direction = "up"
    elif score_delta < -2:
        score_direction = "down"
    else:
        score_direction = "stable"
    
    return ChangeReport(
        from_timestamp=previous.timestamp,
        to_timestamp=current.timestamp,
        new_signals=new_signals,
        cleared_signals=cleared_signals,
        signal_delta=current.signal_count - previous.signal_count,
        new_proposals=new_proposals,
        resolved_proposals=resolved_proposals,
        proposal_delta=current.proposal_count - previous.proposal_count,
        portfolio_score_delta=score_delta,
        portfolio_score_direction=score_direction,
        critical_delta=current.critical_count - previous.critical_count,
        pattern_delta=current.pattern_count - previous.pattern_count,
    )


def run_change_detection(intel_data: dict) -> ChangeReport:
    """
    Run change detection on intelligence data.
    
    1. Load previous snapshot
    2. Create current snapshot
    3. Detect changes
    4. Save current snapshot for next run
    5. Return change report
    """
    # Load previous
    previous = load_latest_snapshot()
    
    # Create current
    current = create_snapshot_from_intelligence(intel_data)
    
    # Detect changes
    changes = detect_changes(current, previous)
    
    # Save current for next run
    try:
        save_snapshot(current)
    except Exception as e:
        logger.warning(f"Failed to save snapshot: {e}")
    
    return changes
