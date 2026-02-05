"""
Calendar Sync - Synchronize calendar events and generate time blocks.

This bridges external calendar (Google Calendar) with the Time Truth layer.
Creates protected blocks for meetings and available blocks in gaps.
"""

from datetime import datetime, date, timedelta
from typing import List, Tuple, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.state_store import get_store
from lib.time_truth.block_manager import BlockManager, TimeBlock


class CalendarSync:
    """
    Synchronizes calendar events and generates time blocks.
    
    Responsibilities:
    - Pull events from calendar (via existing events table)
    - Generate protected blocks for meetings
    - Generate available blocks in gaps
    - Detect and report conflicts
    """
    
    def __init__(self, store=None):
        self.store = store or get_store()
        self.block_manager = BlockManager(self.store)
    
    def sync_events(self, start_date: str, end_date: str) -> Dict:
        """
        Sync events from the events table for a date range.
        
        The events table is populated by the calendar collector.
        This method reads from there and creates time blocks.
        
        Args:
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
            
        Returns:
            Dict with sync results
        """
        # Get events from the events table (already synced by collector)
        events = self.store.query("""
            SELECT * FROM events 
            WHERE date(start_time) >= ? AND date(start_time) <= ?
            ORDER BY start_time
        """, [start_date, end_date])
        
        results = {
            'events_found': len(events),
            'blocks_created': 0,
            'dates_processed': [],
            'errors': []
        }
        
        # Group events by date
        events_by_date = {}
        for event in events:
            event_date = event['start_time'][:10] if event.get('start_time') else None
            if event_date:
                if event_date not in events_by_date:
                    events_by_date[event_date] = []
                events_by_date[event_date].append(event)
        
        # Process each date
        current = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        while current <= end:
            date_str = current.isoformat()
            day_events = events_by_date.get(date_str, [])
            
            try:
                blocks = self.generate_available_blocks(date_str, day_events)
                results['blocks_created'] += len(blocks)
                results['dates_processed'].append(date_str)
            except Exception as e:
                results['errors'].append(f"{date_str}: {str(e)}")
            
            current += timedelta(days=1)
        
        return results
    
    def generate_available_blocks(
        self, 
        date: str, 
        events: List[dict] = None,
        lane: str = 'ops',
        lanes: List[str] = None
    ) -> List[TimeBlock]:
        """
        Generate time blocks for a date, working around calendar events.
        
        Creates:
        - Protected blocks for calendar events
        - Available blocks in the gaps
        
        Args:
            date: Date string YYYY-MM-DD
            events: Optional list of events (fetched if not provided)
            lane: Default lane for available blocks
            lanes: If provided, create blocks for multiple lanes
            
        Returns:
            List of created TimeBlock objects
        """
        # Fetch events if not provided
        if events is None:
            events = self.store.query("""
                SELECT * FROM events 
                WHERE date(start_time) = ?
                ORDER BY start_time
            """, [date])
        
        # Check if blocks already exist for this date
        existing_blocks = self.block_manager.get_all_blocks(date)
        if existing_blocks:
            # Already processed - return existing
            return existing_blocks
        
        # Use block manager to create blocks from calendar
        created = self.block_manager.create_blocks_from_calendar(date, events, lane)
        
        # If multiple lanes requested, copy the available (non-protected) blocks
        if lanes:
            for extra_lane in lanes:
                if extra_lane == lane:
                    continue
                # Create same block pattern for other lanes
                for block in created:
                    if not block.is_protected:
                        self.block_manager.create_block(
                            date=date,
                            start_time=block.start_time,
                            end_time=block.end_time,
                            lane=extra_lane,
                            is_protected=False
                        )
        
        return self.block_manager.get_all_blocks(date)
    
    def mark_protected_blocks(self, date: str) -> int:
        """
        Ensure all calendar events have protected blocks.
        
        This is idempotent - won't create duplicates.
        
        Returns:
            Number of blocks marked/created as protected
        """
        events = self.store.query("""
            SELECT * FROM events 
            WHERE date(start_time) = ?
        """, [date])
        
        protected_count = 0
        
        for event in events:
            start = event.get('start_time', '')
            end = event.get('end_time', '')
            
            if not start or not end:
                continue
            
            # Extract time portion
            start_time = start.split('T')[1][:5] if 'T' in start else start
            end_time = end.split('T')[1][:5] if 'T' in end else end
            
            # Check if protected block already exists
            existing = self.store.query("""
                SELECT * FROM time_blocks 
                WHERE date = ? AND start_time = ? AND is_protected = 1
            """, [date, start_time])
            
            if not existing:
                # Create protected block
                block, msg = self.block_manager.create_block(
                    date=date,
                    start_time=start_time,
                    end_time=end_time,
                    lane='ops',  # Protected blocks don't really have a lane
                    is_protected=True
                )
                if block:
                    protected_count += 1
        
        return protected_count
    
    def get_day_summary(self, date: str) -> Dict:
        """
        Get a summary of the day's blocks and events.
        
        Returns:
            Dict with summary info
        """
        blocks = self.block_manager.get_all_blocks(date)
        available = [b for b in blocks if b.is_available]
        protected = [b for b in blocks if b.is_protected]
        scheduled = [b for b in blocks if b.task_id]
        
        # Calculate time
        total_available_min = sum(b.duration_min for b in available)
        total_protected_min = sum(b.duration_min for b in protected)
        total_scheduled_min = sum(b.duration_min for b in scheduled)
        
        return {
            'date': date,
            'total_blocks': len(blocks),
            'available_blocks': len(available),
            'protected_blocks': len(protected),
            'scheduled_blocks': len(scheduled),
            'available_minutes': total_available_min,
            'meeting_minutes': total_protected_min,
            'scheduled_minutes': total_scheduled_min,
            'conflicts': len(self.block_manager.get_conflicts(date))
        }
    
    def ensure_blocks_for_week(self, start_date: str = None) -> Dict:
        """
        Ensure time blocks exist for the next 7 days.
        
        This is the main entry point for scheduled sync.
        
        Args:
            start_date: Start date (defaults to today)
            
        Returns:
            Summary of blocks created
        """
        if not start_date:
            start_date = date.today().isoformat()
        
        end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
        
        return self.sync_events(start_date, end_date)


# Test
if __name__ == "__main__":
    sync = CalendarSync()
    today = date.today().isoformat()
    
    print(f"Testing CalendarSync for {today}")
    print("-" * 40)
    
    # Generate blocks for today
    blocks = sync.generate_available_blocks(today)
    print(f"Generated {len(blocks)} blocks")
    
    # Get summary
    summary = sync.get_day_summary(today)
    print(f"Summary: {summary}")
