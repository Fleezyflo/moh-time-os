"""
Time Analyzer - Analyzes time allocation, capacity, and scheduling patterns.

Provides insights on:
- Time spent per lane/project
- Capacity utilization
- Scheduling conflicts
- Buffer time analysis
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


class TimeAnalyzer:
    """Analyzes time allocation and capacity across lanes and projects."""
    
    def __init__(self, store, config: dict = None):
        """
        Args:
            store: StateStore instance
            config: Lane capacity config from config/lanes.yaml
        """
        self.store = store
        self.config = config or {}
        self.lane_budgets = self._load_lane_budgets()
    
    def _load_lane_budgets(self) -> Dict[str, dict]:
        """Load lane capacity budgets from config."""
        lanes = self.config.get('lanes', {})
        budgets = {}
        for lane_name, lane_config in lanes.items():
            capacity = lane_config.get('capacity_budget', {})
            budgets[lane_name] = {
                'daily_minutes': capacity.get('daily_minutes', 120),
                'weekly_minutes': capacity.get('weekly_minutes', 600)
            }
        return budgets
    
    def analyze_day(self, date: str = None) -> dict:
        """
        Analyze time allocation for a specific day.
        
        Args:
            date: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            {
                'date': str,
                'total_scheduled_minutes': int,
                'total_available_minutes': int,
                'utilization_pct': float,
                'by_lane': {lane: minutes},
                'gaps': [{start, end, minutes}],
                'conflicts': [{event1, event2, overlap_minutes}]
            }
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # Get events for the day
        day_start = f"{date}T00:00:00"
        day_end = f"{date}T23:59:59"
        
        events = self.store.query("""
            SELECT id, title, start_time, end_time, context
            FROM events
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time
        """, [day_start, day_end])
        
        # Calculate totals
        total_minutes = 0
        by_lane = {}
        event_blocks = []
        
        for event in events:
            start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
            end_str = event['end_time']
            if end_str:
                end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            else:
                end = start + timedelta(hours=1)  # Default 1 hour
            
            duration = int((end - start).total_seconds() / 60)
            total_minutes += duration
            
            # Get lane from context
            context = json.loads(event['context']) if event['context'] else {}
            lane = context.get('lane', 'ops')
            by_lane[lane] = by_lane.get(lane, 0) + duration
            
            event_blocks.append({
                'id': event['id'],
                'title': event['title'],
                'start': start,
                'end': end,
                'minutes': duration
            })
        
        # Find gaps (assuming 10:00-20:00 work hours, Dubai timezone)
        work_start = datetime.fromisoformat(f"{date}T10:00:00+04:00")
        work_end = datetime.fromisoformat(f"{date}T20:00:00+04:00")
        available_minutes = 600  # 10 hours
        
        gaps = self._find_gaps(event_blocks, work_start, work_end)
        conflicts = self._find_conflicts(event_blocks)
        
        utilization = (total_minutes / available_minutes * 100) if available_minutes > 0 else 0
        
        return {
            'date': date,
            'total_scheduled_minutes': total_minutes,
            'total_available_minutes': available_minutes,
            'utilization_pct': round(utilization, 1),
            'by_lane': by_lane,
            'gaps': gaps,
            'conflicts': conflicts,
            'event_count': len(events)
        }
    
    def analyze_week(self, start_date: str = None) -> dict:
        """
        Analyze time allocation for a week.
        
        Args:
            start_date: Monday of the week (YYYY-MM-DD), defaults to current week
            
        Returns:
            Weekly summary with daily breakdowns and lane utilization vs budget
        """
        if start_date is None:
            today = datetime.now()
            monday = today - timedelta(days=today.weekday())
            start_date = monday.strftime('%Y-%m-%d')
        
        start = datetime.fromisoformat(start_date)
        days = []
        weekly_by_lane = {}
        total_scheduled = 0
        total_available = 0
        
        for i in range(7):
            day = start + timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            day_analysis = self.analyze_day(day_str)
            days.append(day_analysis)
            
            total_scheduled += day_analysis['total_scheduled_minutes']
            total_available += day_analysis['total_available_minutes']
            
            for lane, minutes in day_analysis['by_lane'].items():
                weekly_by_lane[lane] = weekly_by_lane.get(lane, 0) + minutes
        
        # Compare to budgets
        budget_status = {}
        for lane, minutes in weekly_by_lane.items():
            budget = self.lane_budgets.get(lane, {}).get('weekly_minutes', 600)
            budget_status[lane] = {
                'used': minutes,
                'budget': budget,
                'remaining': budget - minutes,
                'pct_used': round(minutes / budget * 100, 1) if budget > 0 else 0
            }
        
        return {
            'week_start': start_date,
            'total_scheduled_minutes': total_scheduled,
            'total_available_minutes': total_available,
            'utilization_pct': round(total_scheduled / total_available * 100, 1) if total_available > 0 else 0,
            'by_lane': weekly_by_lane,
            'budget_status': budget_status,
            'days': days
        }
    
    def get_capacity_forecast(self, days: int = 7) -> dict:
        """
        Forecast available capacity for upcoming days.
        
        Returns:
            {date: available_minutes} for each day
        """
        forecast = {}
        today = datetime.now()
        
        for i in range(days):
            day = today + timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            analysis = self.analyze_day(day_str)
            
            forecast[day_str] = {
                'scheduled': analysis['total_scheduled_minutes'],
                'available': analysis['total_available_minutes'] - analysis['total_scheduled_minutes'],
                'gaps': analysis['gaps']
            }
        
        return forecast
    
    def _find_gaps(self, blocks: List[dict], work_start: datetime, work_end: datetime) -> List[dict]:
        """Find gaps between scheduled blocks."""
        if not blocks:
            return [{
                'start': work_start.isoformat(),
                'end': work_end.isoformat(),
                'minutes': int((work_end - work_start).total_seconds() / 60)
            }]
        
        gaps = []
        sorted_blocks = sorted(blocks, key=lambda x: x['start'])
        
        # Gap before first event
        if sorted_blocks[0]['start'] > work_start:
            gap_minutes = int((sorted_blocks[0]['start'] - work_start).total_seconds() / 60)
            if gap_minutes >= 15:  # Only count gaps >= 15 min
                gaps.append({
                    'start': work_start.isoformat(),
                    'end': sorted_blocks[0]['start'].isoformat(),
                    'minutes': gap_minutes
                })
        
        # Gaps between events
        for i in range(len(sorted_blocks) - 1):
            current_end = sorted_blocks[i]['end']
            next_start = sorted_blocks[i + 1]['start']
            
            if next_start > current_end:
                gap_minutes = int((next_start - current_end).total_seconds() / 60)
                if gap_minutes >= 15:
                    gaps.append({
                        'start': current_end.isoformat(),
                        'end': next_start.isoformat(),
                        'minutes': gap_minutes
                    })
        
        # Gap after last event
        if sorted_blocks[-1]['end'] < work_end:
            gap_minutes = int((work_end - sorted_blocks[-1]['end']).total_seconds() / 60)
            if gap_minutes >= 15:
                gaps.append({
                    'start': sorted_blocks[-1]['end'].isoformat(),
                    'end': work_end.isoformat(),
                    'minutes': gap_minutes
                })
        
        return gaps
    
    def _find_conflicts(self, blocks: List[dict]) -> List[dict]:
        """Find overlapping events."""
        conflicts = []
        sorted_blocks = sorted(blocks, key=lambda x: x['start'])
        
        for i in range(len(sorted_blocks)):
            for j in range(i + 1, len(sorted_blocks)):
                block1 = sorted_blocks[i]
                block2 = sorted_blocks[j]
                
                # Check overlap
                if block1['end'] > block2['start']:
                    overlap_minutes = int((block1['end'] - block2['start']).total_seconds() / 60)
                    conflicts.append({
                        'event1': {'id': block1['id'], 'title': block1['title']},
                        'event2': {'id': block2['id'], 'title': block2['title']},
                        'overlap_minutes': overlap_minutes
                    })
        
        return conflicts
