"""
Attendance Analyzer - Scores meeting attendance with instrumentality heuristic.

Key insight: Raw "no-show" data overstates absence because ~80% of the time
people attend meetings in-room without joining the video call action.

Instrumentality scoring:
- Higher instrumentality = more likely to have attended in-room
- Lower instrumentality = more likely genuinely absent

The result is an "adjusted_attendance_prob" that reflects reality better than
raw calendar-joined data.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


# Instrumentality weights by role
INSTRUMENTALITY_SCORES = {
    'organizer': 100,           # They organized it - almost certainly there
    'subject_of_review': 95,    # Performance review, 1:1 about them
    'direct_report_1on1': 90,   # 1:1 with their manager
    'required_attendee': 80,    # Explicitly required
    'key_stakeholder': 75,      # Inferred critical to agenda
    'small_meeting': 70,        # <4 people meetings, everyone matters
    'project_lead': 70,         # Leads for project meetings
    'team_member': 60,          # Regular team member in team meeting
    'optional_attendee': 50,    # Marked optional
    'large_meeting': 40,        # >6 people, easy to be absent
    'cc_fyi': 30,               # CC'd for visibility only
}

# Base probability that someone was physically present despite no-show
IN_ROOM_BASE_PROB = 0.80

# Meeting type patterns
MEETING_PATTERNS = {
    'performance_review': r'(?i)(performance|annual)\s*review|appraisal',
    '1on1': r'(?i)1[:\-\s]?1|one[:\-\s]?on[:\-\s]?one|catch[:\-\s]?up',
    'client_meeting': r'(?i)client|external|kick[:\-\s]?off|presentation',
    'team_standup': r'(?i)stand[:\-\s]?up|daily|sync|huddle',
    'all_hands': r'(?i)all[:\-\s]?hands|town[:\-\s]?hall|company[:\-\s]?wide',
    'project_meeting': r'(?i)project|sprint|planning|retro|review',
}


class AttendanceAnalyzer:
    """
    Analyzes meeting attendance with instrumentality-adjusted scoring.
    """
    
    def __init__(self, store):
        """
        Args:
            store: StateStore instance with team_events and meet_attendance tables
        """
        self.store = store
    
    def analyze_all(self, days_back: int = 30) -> Dict:
        """
        Run full attendance analysis for the past N days.
        
        Returns:
            Dict with:
            - meetings: List of analyzed meetings
            - person_stats: Per-person attendance stats
            - team_summary: Overall team metrics
            - flags: Issues requiring attention
        """
        cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # Get calendar meetings
        meetings = self._get_meetings(cutoff)
        
        # Get actual attendance data
        attendance_data = self._get_attendance_data(cutoff)
        
        # Match and analyze
        analyzed = []
        for meeting in meetings:
            result = self._analyze_meeting(meeting, attendance_data)
            if result:
                analyzed.append(result)
        
        # Compute per-person stats
        person_stats = self._compute_person_stats(analyzed)
        
        # Compute team summary
        team_summary = self._compute_team_summary(person_stats)
        
        # Flag issues
        flags = self._flag_issues(person_stats, analyzed)
        
        return {
            'meetings': analyzed,
            'person_stats': person_stats,
            'team_summary': team_summary,
            'flags': flags,
            'analyzed_count': len(analyzed),
            'period_days': days_back,
        }
    
    def _get_meetings(self, cutoff: str) -> List[Dict]:
        """Get unique calendar meetings from team_events."""
        # Get distinct meetings (not per-owner duplicates)
        rows = self.store.query("""
            SELECT 
                MIN(id) as id,
                title,
                organizer,
                start_time,
                end_time,
                attendees,
                GROUP_CONCAT(DISTINCT owner_email) as all_owners
            FROM team_events
            WHERE start_time >= ?
            AND status = 'confirmed'
            GROUP BY title, organizer, date(start_time)
            ORDER BY start_time DESC
        """, [cutoff])
        
        meetings = []
        for row in rows:
            attendees = []
            if row.get('attendees'):
                try:
                    attendees = json.loads(row['attendees'])
                except:
                    pass
            
            meetings.append({
                'id': row['id'],
                'title': row['title'],
                'organizer': row.get('organizer', ''),
                'start_time': row['start_time'],
                'end_time': row.get('end_time'),
                'invited': attendees,
                'meeting_type': self._classify_meeting_type(row['title']),
            })
        
        return meetings
    
    def _get_attendance_data(self, cutoff: str) -> Dict[str, List[Dict]]:
        """
        Get actual attendance data grouped by date+organizer for matching.
        Returns dict keyed by 'YYYY-MM-DD|organizer_email' with list of participants.
        """
        rows = self.store.query("""
            SELECT 
                meeting_code,
                organizer,
                participant_email,
                duration_seconds,
                strftime('%Y-%m-%d', joined_time) as date
            FROM meet_attendance
            WHERE date >= ?
            ORDER BY date, meeting_code
        """, [cutoff])
        
        # Group by date|organizer
        grouped = defaultdict(list)
        for row in rows:
            key = f"{row['date']}|{row.get('organizer', 'unknown')}"
            grouped[key].append({
                'meeting_code': row['meeting_code'],
                'participant': row['participant_email'],
                'duration': row['duration_seconds'],
            })
        
        return grouped
    
    def _analyze_meeting(self, meeting: Dict, attendance_data: Dict) -> Optional[Dict]:
        """
        Analyze a single meeting with instrumentality scoring.
        """
        if not meeting.get('start_time'):
            return None
        
        try:
            date = meeting['start_time'][:10]  # YYYY-MM-DD
        except:
            return None
        
        organizer = meeting.get('organizer', '')
        invited = meeting.get('invited', [])
        meeting_type = meeting.get('meeting_type', 'unknown')
        title = meeting.get('title', '')
        
        if not invited:
            return None
        
        # Find matching attendance data
        key = f"{date}|{organizer}"
        actual_attendees = self._find_actual_attendees(key, attendance_data, invited)
        
        # Score each invited person
        attendee_analysis = []
        for email in invited:
            if not email or '@' not in email:
                continue
            
            name = email.split('@')[0]
            
            # Calculate instrumentality score
            instrumentality = self._calculate_instrumentality(
                email, organizer, invited, meeting_type, title
            )
            
            # Check if they actually joined
            actually_joined = email in actual_attendees
            join_duration = actual_attendees.get(email, 0)
            
            # Calculate adjusted attendance probability
            if actually_joined and join_duration > 60:
                # Definitely attended
                adjusted_prob = 1.0
                status = 'confirmed_attended'
            elif actually_joined and join_duration <= 60:
                # Brief join - might have been checking in
                adjusted_prob = 0.9
                status = 'likely_attended'
            else:
                # No-show in data - use instrumentality to estimate
                adjusted_prob = self._estimate_in_room_probability(instrumentality)
                status = 'likely_in_room' if adjusted_prob >= 0.7 else 'likely_absent'
            
            attendee_analysis.append({
                'email': email,
                'name': name,
                'instrumentality': instrumentality,
                'instrumentality_reason': self._get_instrumentality_reason(
                    email, organizer, invited, meeting_type, title
                ),
                'raw_joined': actually_joined,
                'join_duration_sec': join_duration,
                'adjusted_attendance_prob': adjusted_prob,
                'status': status,
            })
        
        # Calculate meeting-level metrics
        total_invited = len(attendee_analysis)
        confirmed = sum(1 for a in attendee_analysis if a['status'] == 'confirmed_attended')
        likely_attended = sum(1 for a in attendee_analysis if a['adjusted_attendance_prob'] >= 0.7)
        likely_absent = sum(1 for a in attendee_analysis if a['adjusted_attendance_prob'] < 0.5)
        
        return {
            'meeting_id': meeting['id'],
            'title': title,
            'date': date,
            'organizer': organizer,
            'meeting_type': meeting_type,
            'invited_count': total_invited,
            'confirmed_attended': confirmed,
            'likely_attended': likely_attended,
            'likely_absent': likely_absent,
            'raw_attendance_rate': confirmed / total_invited if total_invited > 0 else 0,
            'adjusted_attendance_rate': likely_attended / total_invited if total_invited > 0 else 0,
            'attendees': attendee_analysis,
            'no_shows': [a for a in attendee_analysis if a['status'] == 'likely_absent'],
        }
    
    def _find_actual_attendees(self, key: str, attendance_data: Dict, invited: List[str]) -> Dict[str, int]:
        """
        Find actual attendees for a meeting.
        Returns dict of email -> duration_seconds.
        """
        result = {}
        
        if key not in attendance_data:
            # Try finding by partial organizer match
            for k, v in attendance_data.items():
                if k.startswith(key.split('|')[0]):  # Same date
                    # Check if any invited people are in this meeting
                    participants = {p['participant'].lower() for p in v}
                    invited_lower = {e.lower() for e in invited if e}
                    if len(participants & invited_lower) >= 2:
                        # Likely match
                        for p in v:
                            email = p['participant']
                            result[email] = max(result.get(email, 0), p['duration'])
        else:
            for p in attendance_data[key]:
                email = p['participant']
                result[email] = max(result.get(email, 0), p['duration'])
        
        return result
    
    def _classify_meeting_type(self, title: str) -> str:
        """Classify meeting type from title."""
        for mtype, pattern in MEETING_PATTERNS.items():
            if re.search(pattern, title):
                return mtype
        return 'general'
    
    def _calculate_instrumentality(
        self, 
        email: str, 
        organizer: str, 
        invited: List[str], 
        meeting_type: str,
        title: str
    ) -> int:
        """Calculate instrumentality score for an attendee."""
        email_lower = email.lower()
        organizer_lower = (organizer or '').lower()
        name = email_lower.split('@')[0]
        
        # Organizer gets highest score
        if email_lower == organizer_lower:
            return INSTRUMENTALITY_SCORES['organizer']
        
        # Performance review - check if name is in title
        if meeting_type == 'performance_review':
            if name in title.lower() or any(part in title.lower() for part in name.split('.')):
                return INSTRUMENTALITY_SCORES['subject_of_review']
        
        # 1:1 meetings - both parties are critical
        if meeting_type == '1on1':
            if len(invited) <= 3:  # Account for occasional CC
                return INSTRUMENTALITY_SCORES['direct_report_1on1']
        
        # Small meetings - everyone matters
        if len(invited) <= 3:
            return INSTRUMENTALITY_SCORES['small_meeting']
        
        # Client meetings - all internal attendees are key
        if meeting_type == 'client_meeting':
            if '@hrmny.co' in email_lower:
                return INSTRUMENTALITY_SCORES['key_stakeholder']
        
        # Large meetings - lower instrumentality
        if len(invited) > 6:
            return INSTRUMENTALITY_SCORES['large_meeting']
        
        # Default team member score
        return INSTRUMENTALITY_SCORES['team_member']
    
    def _get_instrumentality_reason(
        self,
        email: str,
        organizer: str,
        invited: List[str],
        meeting_type: str,
        title: str
    ) -> str:
        """Get human-readable reason for instrumentality score."""
        email_lower = email.lower()
        organizer_lower = (organizer or '').lower()
        name = email_lower.split('@')[0]
        
        if email_lower == organizer_lower:
            return 'organizer'
        
        if meeting_type == 'performance_review':
            if name in title.lower():
                return 'subject_of_review'
        
        if meeting_type == '1on1' and len(invited) <= 3:
            return 'direct_participant_1on1'
        
        if len(invited) <= 3:
            return 'small_meeting_critical'
        
        if meeting_type == 'client_meeting' and '@hrmny.co' in email_lower:
            return 'key_stakeholder_client_meeting'
        
        if len(invited) > 6:
            return 'large_meeting_attendee'
        
        return 'team_member'
    
    def _estimate_in_room_probability(self, instrumentality: int) -> float:
        """
        Estimate probability person was physically present despite no video join.
        
        Formula: base_prob * (instrumentality / 100)
        
        High instrumentality + no-show → probably in room
        Low instrumentality + no-show → probably absent
        """
        if instrumentality >= 90:
            # Very high instrumentality - almost certainly in room
            return IN_ROOM_BASE_PROB * 1.0
        elif instrumentality >= 70:
            # High instrumentality - likely in room
            return IN_ROOM_BASE_PROB * 0.95
        elif instrumentality >= 50:
            # Medium instrumentality - 50/50 but lean toward present
            return IN_ROOM_BASE_PROB * 0.75
        elif instrumentality >= 30:
            # Low instrumentality - probably actually absent
            return IN_ROOM_BASE_PROB * 0.4
        else:
            # Very low - likely absent
            return IN_ROOM_BASE_PROB * 0.2
    
    def _compute_person_stats(self, analyzed_meetings: List[Dict]) -> Dict[str, Dict]:
        """Compute per-person attendance statistics."""
        stats = defaultdict(lambda: {
            'invited_count': 0,
            'confirmed_attended': 0,
            'likely_attended': 0,
            'likely_absent': 0,
            'total_instrumentality': 0,
            'no_show_meetings': [],
        })
        
        for meeting in analyzed_meetings:
            for attendee in meeting.get('attendees', []):
                email = attendee['email']
                stats[email]['invited_count'] += 1
                stats[email]['total_instrumentality'] += attendee['instrumentality']
                
                if attendee['status'] == 'confirmed_attended':
                    stats[email]['confirmed_attended'] += 1
                
                if attendee['adjusted_attendance_prob'] >= 0.7:
                    stats[email]['likely_attended'] += 1
                elif attendee['adjusted_attendance_prob'] < 0.5:
                    stats[email]['likely_absent'] += 1
                    stats[email]['no_show_meetings'].append({
                        'title': meeting['title'],
                        'date': meeting['date'],
                        'instrumentality': attendee['instrumentality'],
                    })
        
        # Calculate averages
        for email, data in stats.items():
            n = data['invited_count']
            if n > 0:
                data['avg_instrumentality'] = round(data['total_instrumentality'] / n, 1)
                data['raw_attendance_rate'] = round(data['confirmed_attended'] / n * 100, 1)
                data['adjusted_attendance_rate'] = round(data['likely_attended'] / n * 100, 1)
                data['true_absence_rate'] = round(data['likely_absent'] / n * 100, 1)
        
        return dict(stats)
    
    def _compute_team_summary(self, person_stats: Dict[str, Dict]) -> Dict:
        """Compute team-level summary statistics."""
        if not person_stats:
            return {}
        
        total_invited = sum(p['invited_count'] for p in person_stats.values())
        total_confirmed = sum(p['confirmed_attended'] for p in person_stats.values())
        total_likely = sum(p['likely_attended'] for p in person_stats.values())
        total_absent = sum(p['likely_absent'] for p in person_stats.values())
        
        return {
            'total_meeting_slots': total_invited,
            'raw_attendance_rate': round(total_confirmed / total_invited * 100, 1) if total_invited else 0,
            'adjusted_attendance_rate': round(total_likely / total_invited * 100, 1) if total_invited else 0,
            'true_absence_rate': round(total_absent / total_invited * 100, 1) if total_invited else 0,
            'people_analyzed': len(person_stats),
        }
    
    def _flag_issues(self, person_stats: Dict[str, Dict], meetings: List[Dict]) -> List[Dict]:
        """Flag attendance issues requiring attention."""
        flags = []
        
        # Flag people with high true absence rate
        for email, stats in person_stats.items():
            if stats['invited_count'] >= 5 and stats['true_absence_rate'] > 30:
                flags.append({
                    'type': 'high_absence_rate',
                    'severity': 'high' if stats['true_absence_rate'] > 50 else 'medium',
                    'person': email,
                    'rate': stats['true_absence_rate'],
                    'count': stats['likely_absent'],
                    'meetings': stats['no_show_meetings'][:5],
                })
        
        # Flag meetings with low attendance
        for meeting in meetings:
            if meeting['invited_count'] >= 3 and meeting['adjusted_attendance_rate'] < 0.5:
                flags.append({
                    'type': 'low_meeting_attendance',
                    'severity': 'medium',
                    'meeting': meeting['title'],
                    'date': meeting['date'],
                    'rate': round(meeting['adjusted_attendance_rate'] * 100, 1),
                    'no_shows': [ns['name'] for ns in meeting['no_shows']],
                })
        
        return sorted(flags, key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x['severity'], 3))
    
    def print_report(self, analysis: Dict):
        """Print a formatted attendance report."""
        print("=" * 70)
        print("MEETING ATTENDANCE ANALYSIS (Instrumentality-Adjusted)")
        print("=" * 70)
        
        summary = analysis.get('team_summary', {})
        print(f"\n📊 TEAM SUMMARY ({analysis.get('period_days', 30)} days)")
        print(f"   Total meeting slots analyzed: {summary.get('total_meeting_slots', 0)}")
        print(f"   Raw attendance rate (joined call): {summary.get('raw_attendance_rate', 0)}%")
        print(f"   Adjusted attendance rate (with in-room): {summary.get('adjusted_attendance_rate', 0)}%")
        print(f"   True absence rate: {summary.get('true_absence_rate', 0)}%")
        
        # Top issues
        flags = analysis.get('flags', [])
        if flags:
            print(f"\n⚠️  FLAGGED ISSUES ({len(flags)} total)")
            for flag in flags[:10]:
                if flag['type'] == 'high_absence_rate':
                    print(f"   🔴 {flag['person']}: {flag['rate']}% true absence rate ({flag['count']} meetings)")
                elif flag['type'] == 'low_meeting_attendance':
                    print(f"   🟡 {flag['meeting']} ({flag['date']}): only {flag['rate']}% attendance")
        
        # Per-person breakdown (top absentees)
        person_stats = analysis.get('person_stats', {})
        if person_stats:
            print(f"\n👥 PER-PERSON STATS (sorted by true absence)")
            sorted_people = sorted(
                person_stats.items(),
                key=lambda x: x[1].get('true_absence_rate', 0),
                reverse=True
            )
            for email, stats in sorted_people[:15]:
                name = email.split('@')[0]
                if stats['invited_count'] >= 3:
                    print(f"   {name:20} | invited: {stats['invited_count']:3} | "
                          f"attended: {stats['adjusted_attendance_rate']:5.1f}% | "
                          f"true absent: {stats['true_absence_rate']:5.1f}%")
        
        print("\n" + "=" * 70)


# CLI entry point
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from lib.state_store import StateStore
    
    store = StateStore()
    analyzer = AttendanceAnalyzer(store)
    
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    analysis = analyzer.analyze_all(days_back=days)
    analyzer.print_report(analysis)
