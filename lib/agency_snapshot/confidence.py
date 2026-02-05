"""
Confidence Model - Per Page 0 §3.3.

Every surfaced item must carry confidence: HIGH | MED | LOW.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import sqlite3
from pathlib import Path


class Confidence(Enum):
    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


@dataclass
class ConfidenceResult:
    """Result of confidence computation."""
    level: Confidence
    why_low: List[str]  # Max 3 bullets


@dataclass
class TrustState:
    """
    Trust state per Page 0 §2.1.
    
    All fields required for trust strip.
    """
    data_integrity: bool = False
    project_brand_required: bool = False
    project_brand_consistency: bool = False
    client_coverage_pct: float = 0.0
    finance_ar_coverage_pct: float = 0.0
    commitment_ready_pct: float = 0.0
    
    # Collector staleness (hours since last sync)
    collector_staleness: Dict[str, float] = None
    last_refresh_at: str = ""
    
    def __post_init__(self):
        if self.collector_staleness is None:
            self.collector_staleness = {
                "gmail_hours": 0,
                "calendar_hours": 0,
                "tasks_hours": 0,
                "xero_hours": 0,
            }
    
    def to_dict(self) -> Dict:
        """Convert to snapshot format."""
        return {
            "data_integrity": self.data_integrity,
            "project_brand_required": self.project_brand_required,
            "project_brand_consistency": self.project_brand_consistency,
            "client_coverage_pct": round(self.client_coverage_pct, 1),
            "finance_ar_coverage_pct": round(self.finance_ar_coverage_pct, 1),
            "commitment_ready_pct": round(self.commitment_ready_pct, 1),
            "collector_staleness": self.collector_staleness,
            "last_refresh_at": self.last_refresh_at,
        }


class ConfidenceModel:
    """
    Computes confidence per Page 0 §3.3.
    
    HIGH when all true:
    - data_integrity=true
    - required chain valid for that domain
    - required fields coverage >= threshold
    
    MED when:
    - integrity OK but some missing/partial mappings
    
    LOW when any true:
    - chain invalid/partial for required domain
    - required fields missing below threshold
    - dependent gate coverage below threshold
    """
    
    # Thresholds per spec
    DUE_DATE_COVERAGE_THRESHOLD = 0.80
    CLIENT_COVERAGE_THRESHOLD = 0.80
    AR_COVERAGE_THRESHOLD = 0.95
    COMMITMENT_THRESHOLD = 0.50
    
    # Staleness thresholds (hours)
    GMAIL_STALE_HOURS = 2
    CALENDAR_STALE_HOURS = 1
    TASKS_STALE_HOURS = 1
    XERO_STALE_HOURS = 4
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or Path(__file__).parent.parent.parent / "data" / "state.db"
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _query_one(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        conn = self._get_conn()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def get_trust_state(self) -> TrustState:
        """
        Compute trust state from current data.
        """
        # Import gates evaluator
        from ..gates import GateEvaluator
        
        evaluator = GateEvaluator(self.db_path)
        gates = evaluator.evaluate_all()
        
        # Get collector staleness
        staleness = self._get_collector_staleness()
        
        # Get last refresh
        last_refresh = self._query_one(
            "SELECT MAX(created_at) as last FROM cycle_logs"
        )
        
        return TrustState(
            data_integrity=gates.get('data_integrity', False),
            project_brand_required=gates.get('project_brand_required', False),
            project_brand_consistency=gates.get('project_brand_consistency', False),
            client_coverage_pct=gates.get('client_coverage_pct', 0),
            finance_ar_coverage_pct=gates.get('finance_ar_coverage_pct', 0),
            commitment_ready_pct=gates.get('commitment_ready_pct', 0),
            collector_staleness=staleness,
            last_refresh_at=last_refresh.get('last', '') if last_refresh else '',
        )
    
    def _get_collector_staleness(self) -> Dict[str, float]:
        """Get hours since last sync for each collector."""
        from datetime import datetime
        
        staleness = {}
        sources = ['gmail', 'calendar', 'asana', 'xero']
        
        for source in sources:
            # Check sync_state table
            row = self._query_one("""
                SELECT last_sync FROM sync_state WHERE source = ?
            """, (source,))
            
            if row and row.get('last_sync'):
                try:
                    last_sync = datetime.fromisoformat(row['last_sync'])
                    hours = (datetime.now() - last_sync).total_seconds() / 3600
                    staleness[f"{source}_hours"] = round(hours, 1)
                except:
                    staleness[f"{source}_hours"] = 999
            else:
                staleness[f"{source}_hours"] = 999  # Never synced
        
        # Map asana to tasks for consistency
        if 'asana_hours' in staleness:
            staleness['tasks_hours'] = staleness.pop('asana_hours')
        
        return staleness
    
    def compute_for_domain(self, domain: str, trust: TrustState) -> ConfidenceResult:
        """
        Compute confidence for a specific domain.
        """
        why_low = []
        
        # Check data integrity (blocking for all)
        if not trust.data_integrity:
            return ConfidenceResult(
                level=Confidence.LOW,
                why_low=["Data integrity check failed"]
            )
        
        # Domain-specific checks
        if domain == "delivery":
            if not trust.project_brand_required:
                why_low.append("Project brand/client chain incomplete")
            if not trust.project_brand_consistency:
                why_low.append("Project brand consistency failed")
        
        elif domain == "clients":
            if trust.client_coverage_pct < self.CLIENT_COVERAGE_THRESHOLD * 100:
                why_low.append(f"Client coverage at {trust.client_coverage_pct:.0f}%")
        
        elif domain == "cash":
            if trust.finance_ar_coverage_pct < self.AR_COVERAGE_THRESHOLD * 100:
                why_low.append(f"AR data coverage at {trust.finance_ar_coverage_pct:.0f}%")
        
        elif domain == "comms":
            if trust.commitment_ready_pct < self.COMMITMENT_THRESHOLD * 100:
                why_low.append(f"Commitment extraction at {trust.commitment_ready_pct:.0f}%")
        
        # Check collector staleness
        staleness_checks = {
            "gmail_hours": (self.GMAIL_STALE_HOURS, "Gmail"),
            "calendar_hours": (self.CALENDAR_STALE_HOURS, "Calendar"),
            "tasks_hours": (self.TASKS_STALE_HOURS, "Tasks"),
            "xero_hours": (self.XERO_STALE_HOURS, "Xero"),
        }
        
        for key, (threshold, name) in staleness_checks.items():
            hours = trust.collector_staleness.get(key, 0)
            if hours > threshold:
                why_low.append(f"Collector stale: {name} > {threshold}h")
        
        # Determine level
        if len(why_low) >= 2:
            return ConfidenceResult(
                level=Confidence.LOW,
                why_low=why_low[:3]
            )
        elif len(why_low) == 1:
            return ConfidenceResult(
                level=Confidence.MED,
                why_low=why_low
            )
        
        return ConfidenceResult(
            level=Confidence.HIGH,
            why_low=[]
        )
    
    def is_blocked(self, trust: TrustState) -> bool:
        """
        Check if page should be blocked per Page 0 §2.2.
        
        If data_integrity=false → page shows only Integrity Failure panel.
        """
        return not trust.data_integrity
    
    def get_partial_domains(self, trust: TrustState) -> Dict[str, List[str]]:
        """
        Get domains that should show PARTIAL badge per Page 0 §2.2.
        
        Returns dict of domain -> reasons for partial.
        """
        partial = {}
        
        if not trust.project_brand_required or not trust.project_brand_consistency:
            partial['delivery'] = ["Project chain incomplete"]
            partial['clients'] = ["Project chain incomplete"]
        
        if trust.finance_ar_coverage_pct < 95:
            reasons = []
            # Would need to query for specific reasons
            reasons.append("AR coverage below 95%")
            partial['cash'] = reasons
        
        if trust.commitment_ready_pct < 50:
            partial['comms'] = ["body_text coverage low"]
        
        return partial
