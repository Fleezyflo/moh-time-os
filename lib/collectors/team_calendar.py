"""
Team Calendar Collector - Pulls calendars from ALL team members.
Uses domain-wide delegation via gog CLI.
"""

import subprocess
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List
from pathlib import Path

from .base import BaseCollector


# Active team members (update as needed)
TEAM_MEMBERS = [
    "molham@hrmny.co",
    "ramy@hrmny.co", 
    "youssef.f@hrmny.co",
    "imad@hrmny.co",
    "jessica@hrmny.co",
    "nathan@hrmny.co",
    "aubrey@hrmny.co",
    "dana@hrmny.co",
    "ay@hrmny.co",
    "elnaz@hrmny.co",
    "mark@hrmny.co",
    "maher.c@hrmny.co",
    "raafat@hrmny.co",
    "krystie@hrmny.co",
    "fabina@hrmny.co",
]


class TeamCalendarCollector(BaseCollector):
    """
    Collects calendar events from all team members.
    Computes real capacity based on actual meeting load.
    """
    
    source_name = 'team_calendar'
    target_table = 'team_events'
    
    def __init__(self, config: Dict = None, store=None):
        super().__init__(config or {}, store)
        self.lookback_days = self.config.get('lookback_days', 7)
        self.lookahead_days = self.config.get('lookahead_days', 14)
    
    def collect(self) -> Dict[str, Any]:
        """Fetch calendars for all team members."""
        today = datetime.now()
        from_date = (today - timedelta(days=self.lookback_days)).strftime('%Y-%m-%d')
        to_date = (today + timedelta(days=self.lookahead_days)).strftime('%Y-%m-%d')
        
        all_events = []
        capacity_data = []
        
        for email in TEAM_MEMBERS:
            name = email.split('@')[0]
            self.logger.info(f"Fetching calendar for {name}")
            
            try:
                events = self._fetch_calendar(email, from_date, to_date)
                
                # Tag events with owner
                for event in events:
                    event['_owner_email'] = email
                    event['_owner_name'] = name
                    all_events.append(event)
                
                # Compute capacity for this week
                week_events = self._filter_this_week(events)
                meeting_hours = self._compute_meeting_hours(week_events)
                external_hours = self._compute_external_hours(week_events)
                
                capacity_data.append({
                    'email': email,
                    'name': name,
                    'event_count': len(week_events),
                    'meeting_hours': round(meeting_hours, 1),
                    'external_hours': round(external_hours, 1),
                    'available_hours': round(max(0, 40 - meeting_hours), 1),
                    'utilization_pct': round((meeting_hours / 40) * 100, 1),
                })
                
            except Exception as e:
                self.logger.warning(f"Failed to fetch calendar for {email}: {e}")
        
        return {
            'events': all_events,
            'capacity': capacity_data,
            'from_date': from_date,
            'to_date': to_date,
        }
    
    def _fetch_calendar(self, email: str, from_date: str, to_date: str) -> List[Dict]:
        """Fetch calendar events for a single user via gog CLI."""
        result = subprocess.run(
            ["gog", "calendar", "list", f"--account={email}",
             f"--from={from_date}", f"--to={to_date}", "--max=100", "--json"],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            raise Exception(f"gog failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        return data.get('events', [])
    
    def _filter_this_week(self, events: List[Dict]) -> List[Dict]:
        """Filter events to this week only."""
        today = datetime.now()
        week_start = today
        week_end = today + timedelta(days=7)
        
        filtered = []
        for event in events:
            start = event.get('start', {})
            start_str = start.get('dateTime') or start.get('date')
            if start_str:
                try:
                    if 'T' in start_str:
                        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    else:
                        start_dt = datetime.fromisoformat(start_str)
                    
                    # Remove timezone for comparison
                    start_dt = start_dt.replace(tzinfo=None)
                    
                    if week_start.replace(tzinfo=None) <= start_dt <= week_end.replace(tzinfo=None):
                        filtered.append(event)
                except:
                    pass
        return filtered
    
    def _compute_meeting_hours(self, events: List[Dict]) -> float:
        """Compute total meeting hours from events."""
        total = 0.0
        for event in events:
            start = event.get('start', {})
            end = event.get('end', {})
            
            start_str = start.get('dateTime')
            end_str = end.get('dateTime')
            
            if start_str and end_str:
                try:
                    start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                    hours = (end_dt - start_dt).total_seconds() / 3600
                    total += hours
                except:
                    pass
        return total
    
    def _compute_external_hours(self, events: List[Dict]) -> float:
        """Compute hours spent in external (non-hrmny) meetings."""
        total = 0.0
        for event in events:
            attendees = event.get('attendees', [])
            has_external = any(
                a.get('email', '').split('@')[-1] != 'hrmny.co'
                for a in attendees
                if a.get('email')
            )
            
            if has_external:
                start = event.get('start', {})
                end = event.get('end', {})
                start_str = start.get('dateTime')
                end_str = end.get('dateTime')
                
                if start_str and end_str:
                    try:
                        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                        hours = (end_dt - start_dt).total_seconds() / 3600
                        total += hours
                    except:
                        pass
        return total
    
    def transform(self, raw_data: Dict) -> List[Dict]:
        """Transform calendar events to canonical format."""
        now = datetime.now().isoformat()
        transformed = []
        
        for event in raw_data.get('events', []):
            event_id = event.get('id')
            if not event_id:
                continue
            
            owner_email = event.get('_owner_email', '')
            owner_name = event.get('_owner_name', '')
            
            start = event.get('start', {})
            end = event.get('end', {})
            
            transformed.append({
                'id': f"team_cal_{owner_name}_{event_id}",
                'source': 'team_calendar',
                'source_id': event_id,
                'owner_email': owner_email,
                'owner_name': owner_name,
                'title': event.get('summary', 'No Title'),
                'start_time': start.get('dateTime') or start.get('date'),
                'end_time': end.get('dateTime') or end.get('date'),
                'attendees': json.dumps([a.get('email') for a in event.get('attendees', [])]),
                'is_external': any(
                    a.get('email', '').split('@')[-1] != 'hrmny.co'
                    for a in event.get('attendees', [])
                    if a.get('email')
                ),
                'status': event.get('status', 'confirmed'),
                'organizer': event.get('organizer', {}).get('email', ''),
                'raw': json.dumps(event),
                'created_at': event.get('created', now),
                'updated_at': now,
            })
        
        return transformed
    
    def store(self, records: List[Dict]) -> Dict:
        """Store events and update capacity table."""
        # Store events
        stored = 0
        for record in records:
            try:
                self.store.upsert('team_events', record)
                stored += 1
            except Exception as e:
                self.logger.warning(f"Failed to store event: {e}")
        
        # Update team_capacity table
        capacity_data = self._last_raw_data.get('capacity', [])
        for cap in capacity_data:
            try:
                self.store.upsert('team_capacity', {
                    'email': cap['email'],
                    'name': cap['name'],
                    'event_count': cap['event_count'],
                    'meeting_hours': cap['meeting_hours'],
                    'external_hours': cap['external_hours'],
                    'available_hours': cap['available_hours'],
                    'utilization_pct': cap['utilization_pct'],
                    'computed_at': datetime.now().isoformat(),
                })
            except Exception as e:
                self.logger.warning(f"Failed to store capacity for {cap['email']}: {e}")
        
        return {'stored': stored, 'capacity_updated': len(capacity_data)}
    
    def sync(self) -> Dict:
        """Full sync: collect, transform, store."""
        raw_data = self.collect()
        self._last_raw_data = raw_data  # Store for capacity update
        records = self.transform(raw_data)
        result = self.store(records)
        result['success'] = True
        return result
