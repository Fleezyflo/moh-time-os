"""
Capacity Calculator - Compute lane capacity and utilization.

Tracks:
- Weekly capacity per lane
- Current utilization (scheduled / capacity)
- Forecast for upcoming days
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.state_store import get_store


@dataclass
class LaneCapacity:
    lane_id: str
    lane_name: str
    weekly_hours: int
    buffer_pct: float
    effective_hours: float  # weekly_hours * (1 - buffer_pct)
    daily_hours: float      # effective_hours / 5 (workdays)


@dataclass
class LaneUtilization:
    lane_id: str
    date: str
    capacity_min: int
    scheduled_min: int
    available_min: int
    utilization_pct: float
    is_overloaded: bool


class CapacityCalculator:
    """
    Calculates capacity and utilization for work lanes.
    
    Responsibilities:
    - Get lane capacity configuration
    - Calculate utilization for a date range
    - Forecast capacity based on scheduled work
    - Alert on overutilization
    """
    
    def __init__(self, store=None):
        self.store = store or get_store()
    
    def get_lanes(self) -> List[Dict]:
        """Get all configured lanes."""
        return self.store.query("SELECT * FROM capacity_lanes ORDER BY name")
    
    def get_lane(self, lane_id: str) -> Optional[Dict]:
        """Get a specific lane."""
        rows = self.store.query(
            "SELECT * FROM capacity_lanes WHERE id = ?",
            [lane_id]
        )
        return rows[0] if rows else None
    
    def get_lane_capacity(self, lane_id: str) -> Optional[LaneCapacity]:
        """
        Get capacity configuration for a lane.
        
        Returns effective daily/weekly hours after buffer.
        """
        lane = self.get_lane(lane_id)
        if not lane:
            return None
        
        weekly_hours = lane.get('weekly_hours', 40)
        buffer_pct = lane.get('buffer_pct', 0.2)
        effective_hours = weekly_hours * (1 - buffer_pct)
        daily_hours = effective_hours / 5  # Assume 5 workdays
        
        return LaneCapacity(
            lane_id=lane_id,
            lane_name=lane.get('display_name', lane_id),
            weekly_hours=weekly_hours,
            buffer_pct=buffer_pct,
            effective_hours=effective_hours,
            daily_hours=daily_hours
        )
    
    def get_lane_utilization(self, lane_id: str, target_date: str = None) -> LaneUtilization:
        """
        Calculate utilization for a lane on a specific date.
        
        Utilization = scheduled_time / effective_capacity
        """
        if not target_date:
            target_date = date.today().isoformat()
        
        capacity = self.get_lane_capacity(lane_id)
        if not capacity:
            # Unknown lane - return empty utilization
            return LaneUtilization(
                lane_id=lane_id,
                date=target_date,
                capacity_min=0,
                scheduled_min=0,
                available_min=0,
                utilization_pct=0,
                is_overloaded=False
            )
        
        # Get scheduled time from time_blocks for this lane
        scheduled_blocks = self.store.query("""
            SELECT SUM(
                (CAST(substr(end_time, 1, 2) AS INTEGER) * 60 + CAST(substr(end_time, 4, 2) AS INTEGER)) -
                (CAST(substr(start_time, 1, 2) AS INTEGER) * 60 + CAST(substr(start_time, 4, 2) AS INTEGER))
            ) as total_min
            FROM time_blocks
            WHERE date = ? AND lane = ? AND task_id IS NOT NULL
        """, [target_date, lane_id])
        
        scheduled_min = scheduled_blocks[0]['total_min'] or 0
        capacity_min = int(capacity.daily_hours * 60)
        available_min = max(0, capacity_min - scheduled_min)
        
        utilization_pct = (scheduled_min / capacity_min * 100) if capacity_min > 0 else 0
        
        return LaneUtilization(
            lane_id=lane_id,
            date=target_date,
            capacity_min=capacity_min,
            scheduled_min=scheduled_min,
            available_min=available_min,
            utilization_pct=round(utilization_pct, 1),
            is_overloaded=utilization_pct > 100
        )
    
    def get_all_utilization(self, target_date: str = None) -> List[LaneUtilization]:
        """Get utilization for all lanes on a date."""
        if not target_date:
            target_date = date.today().isoformat()
        
        lanes = self.get_lanes()
        return [self.get_lane_utilization(lane['id'], target_date) for lane in lanes]
    
    def forecast_capacity(self, lane_id: str, days_ahead: int = 7) -> List[LaneUtilization]:
        """
        Forecast capacity utilization for upcoming days.
        
        Returns list of utilization for each day.
        """
        results = []
        start = date.today()
        
        for i in range(days_ahead):
            forecast_date = (start + timedelta(days=i)).isoformat()
            util = self.get_lane_utilization(lane_id, forecast_date)
            results.append(util)
        
        return results
    
    def get_time_debt(self, lane_id: str) -> int:
        """
        Get total unresolved time debt for a lane (in minutes).
        """
        result = self.store.query("""
            SELECT SUM(amount_min) as total
            FROM time_debt
            WHERE lane = ? AND resolved_at IS NULL
        """, [lane_id])
        
        return result[0]['total'] or 0
    
    def get_capacity_summary(self, target_date: str = None) -> Dict:
        """
        Get a summary of capacity across all lanes.
        """
        if not target_date:
            target_date = date.today().isoformat()
        
        utilizations = self.get_all_utilization(target_date)
        
        total_capacity = sum(u.capacity_min for u in utilizations)
        total_scheduled = sum(u.scheduled_min for u in utilizations)
        total_available = sum(u.available_min for u in utilizations)
        
        overloaded_lanes = [u.lane_id for u in utilizations if u.is_overloaded]
        high_util_lanes = [u.lane_id for u in utilizations if u.utilization_pct >= 80 and not u.is_overloaded]
        
        return {
            'date': target_date,
            'total_capacity_min': total_capacity,
            'total_scheduled_min': total_scheduled,
            'total_available_min': total_available,
            'overall_utilization_pct': round(total_scheduled / total_capacity * 100, 1) if total_capacity > 0 else 0,
            'overloaded_lanes': overloaded_lanes,
            'high_utilization_lanes': high_util_lanes,
            'lanes': [
                {
                    'lane': u.lane_id,
                    'utilization_pct': u.utilization_pct,
                    'scheduled_min': u.scheduled_min,
                    'available_min': u.available_min,
                    'is_overloaded': u.is_overloaded
                }
                for u in utilizations
            ]
        }


# Test
if __name__ == "__main__":
    calc = CapacityCalculator()
    today = date.today().isoformat()
    
    print(f"Capacity Calculator Test for {today}")
    print("-" * 50)
    
    # Get all lanes
    lanes = calc.get_lanes()
    print(f"Configured lanes: {len(lanes)}")
    for lane in lanes:
        print(f"  - {lane['name']}: {lane['weekly_hours']}h/week (buffer: {lane['buffer_pct']*100}%)")
    
    # Get utilization for ops lane
    util = calc.get_lane_utilization('ops', today)
    print(f"\nOps lane utilization:")
    print(f"  Capacity: {util.capacity_min} min")
    print(f"  Scheduled: {util.scheduled_min} min")
    print(f"  Available: {util.available_min} min")
    print(f"  Utilization: {util.utilization_pct}%")
    
    # Summary
    summary = calc.get_capacity_summary(today)
    print(f"\nOverall summary:")
    print(f"  Total utilization: {summary['overall_utilization_pct']}%")
    print(f"  Overloaded lanes: {summary['overloaded_lanes']}")
