"""
Anomaly Detector - Detects unusual patterns and potential issues.

Monitors:
- Sudden changes in workload
- Missed deadlines and SLA breaches
- Unusual communication patterns
- System health indicators
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import json


class AnomalyDetector:
    """Detects anomalies and unusual patterns that need attention."""
    
    # Severity levels
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'
    
    def __init__(self, store, config: dict = None):
        """
        Args:
            store: StateStore instance
            config: Anomaly thresholds config
        """
        self.store = store
        self.config = config or {}
        self.thresholds = self._load_thresholds()
    
    def _load_thresholds(self) -> dict:
        """Load anomaly detection thresholds."""
        defaults = {
            'stale_task_days': 7,
            'overdue_response_hours': 48,
            'high_priority_unattended_hours': 4,
            'daily_email_spike_multiplier': 2.0,
            'deadline_miss_lookahead_days': 2,
            'low_completion_rate_pct': 20,
            'max_concurrent_critical': 3
        }
        return {**defaults, **self.config.get('thresholds', {})}
    
    def run_all_checks(self) -> List[dict]:
        """
        Run all anomaly detection checks.
        
        Returns:
            List of anomaly alerts sorted by severity
        """
        anomalies = []
        
        # Run each check
        anomalies.extend(self.check_overdue_tasks())
        anomalies.extend(self.check_deadline_risk())
        anomalies.extend(self.check_stale_items())
        anomalies.extend(self.check_response_sla())
        anomalies.extend(self.check_calendar_conflicts())
        anomalies.extend(self.check_team_blocked())
        anomalies.extend(self.check_priority_queue_health())
        anomalies.extend(self.check_workload_spike())
        
        # Sort by severity
        severity_order = {self.CRITICAL: 0, self.HIGH: 1, self.MEDIUM: 2, self.LOW: 3}
        anomalies.sort(key=lambda x: severity_order.get(x['severity'], 99))
        
        return anomalies
    
    def check_overdue_tasks(self) -> List[dict]:
        """Check for overdue tasks."""
        anomalies = []
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        
        overdue = self.store.query("""
            SELECT id, title, due_date, priority, lane, assignee
            FROM tasks
            WHERE status NOT IN ('completed', 'done', 'cancelled')
            AND due_date IS NOT NULL
            AND due_date < ?
            ORDER BY priority DESC, due_date ASC
        """, [today])
        
        if overdue:
            # Group by severity - priority is a string ('high', 'normal', 'low', 'critical')
            def priority_score(p):
                scores = {'critical': 100, 'high': 80, 'normal': 50, 'low': 20}
                return scores.get(str(p).lower(), 50) if isinstance(p, str) else (int(p) if p else 50)
            
            critical = [t for t in overdue if priority_score(t.get('priority')) >= 80]
            high = [t for t in overdue if 60 <= priority_score(t.get('priority')) < 80]
            
            if critical:
                anomalies.append({
                    'type': 'overdue_critical_tasks',
                    'severity': self.CRITICAL,
                    'message': f"{len(critical)} critical tasks are overdue",
                    'count': len(critical),
                    'items': [{'id': t['id'], 'title': t['title'], 'due': t['due_date']} for t in critical[:5]],
                    'detected_at': now.isoformat()
                })
            
            if high:
                anomalies.append({
                    'type': 'overdue_high_priority_tasks',
                    'severity': self.HIGH,
                    'message': f"{len(high)} high-priority tasks are overdue",
                    'count': len(high),
                    'items': [{'id': t['id'], 'title': t['title'], 'due': t['due_date']} for t in high[:5]],
                    'detected_at': now.isoformat()
                })
            
            if len(overdue) > len(critical) + len(high):
                other_count = len(overdue) - len(critical) - len(high)
                anomalies.append({
                    'type': 'overdue_tasks',
                    'severity': self.MEDIUM,
                    'message': f"{other_count} other tasks are overdue",
                    'count': other_count,
                    'detected_at': now.isoformat()
                })
        
        return anomalies
    
    def check_deadline_risk(self) -> List[dict]:
        """Check for tasks at risk of missing deadline."""
        anomalies = []
        now = datetime.now()
        lookahead = now + timedelta(days=self.thresholds['deadline_miss_lookahead_days'])
        today = now.strftime('%Y-%m-%d')
        lookahead_str = lookahead.strftime('%Y-%m-%d')
        
        at_risk = self.store.query("""
            SELECT id, title, due_date, priority, lane, status
            FROM tasks
            WHERE status NOT IN ('completed', 'done', 'cancelled', 'in_progress')
            AND due_date IS NOT NULL
            AND due_date >= ? AND due_date <= ?
            AND priority >= 60
            ORDER BY due_date ASC
        """, [today, lookahead_str])
        
        if at_risk:
            anomalies.append({
                'type': 'deadline_risk',
                'severity': self.HIGH,
                'message': f"{len(at_risk)} high-priority tasks due in {self.thresholds['deadline_miss_lookahead_days']} days but not started",
                'count': len(at_risk),
                'items': [{'id': t['id'], 'title': t['title'], 'due': t['due_date']} for t in at_risk[:5]],
                'detected_at': now.isoformat()
            })
        
        return anomalies
    
    def check_stale_items(self) -> List[dict]:
        """Check for stale tasks and decisions."""
        anomalies = []
        now = datetime.now()
        stale_cutoff = (now - timedelta(days=self.thresholds['stale_task_days'])).isoformat()
        
        stale_tasks = self.store.query("""
            SELECT id, title, status, updated_at, priority
            FROM tasks
            WHERE status NOT IN ('completed', 'done', 'cancelled')
            AND updated_at < ?
            ORDER BY priority DESC
        """, [stale_cutoff])
        
        if len(stale_tasks) > 10:
            anomalies.append({
                'type': 'many_stale_tasks',
                'severity': self.MEDIUM,
                'message': f"{len(stale_tasks)} tasks haven't been updated in {self.thresholds['stale_task_days']}+ days",
                'count': len(stale_tasks),
                'items': [{'id': t['id'], 'title': t['title']} for t in stale_tasks[:5]],
                'detected_at': now.isoformat()
            })
        
        # Check stale decisions
        stale_decisions = self.store.query("""
            SELECT id, description, approved, created_at
            FROM decisions
            WHERE approved IS NULL
            AND created_at < ?
        """, [stale_cutoff])
        
        if stale_decisions:
            anomalies.append({
                'type': 'stale_decisions',
                'severity': self.HIGH,
                'message': f"{len(stale_decisions)} decisions pending for {self.thresholds['stale_task_days']}+ days",
                'count': len(stale_decisions),
                'items': [{'id': d['id'], 'description': d['description']} for d in stale_decisions[:5]],
                'detected_at': now.isoformat()
            })
        
        return anomalies
    
    def check_response_sla(self) -> List[dict]:
        """Check for SLA breaches on communications."""
        anomalies = []
        now = datetime.now()
        sla_cutoff = (now - timedelta(hours=self.thresholds['overdue_response_hours'])).isoformat()
        
        overdue_comms = self.store.query("""
            SELECT id, from_email, subject, created_at, priority, is_vip
            FROM communications
            WHERE requires_response = 1
            AND processed = 0
            AND created_at < ?
            ORDER BY is_vip DESC, priority DESC, created_at ASC
        """, [sla_cutoff])
        
        if overdue_comms:
            vip_overdue = [c for c in overdue_comms if c.get('is_vip')]
            
            if vip_overdue:
                anomalies.append({
                    'type': 'vip_response_overdue',
                    'severity': self.CRITICAL,
                    'message': f"{len(vip_overdue)} VIP emails awaiting response 48+ hours",
                    'count': len(vip_overdue),
                    'items': [{'from': c['from_email'], 'subject': c['subject']} for c in vip_overdue[:3]],
                    'detected_at': now.isoformat()
                })
            
            non_vip = len(overdue_comms) - len(vip_overdue)
            if non_vip > 0:
                anomalies.append({
                    'type': 'response_sla_breach',
                    'severity': self.HIGH,
                    'message': f"{non_vip} emails awaiting response 48+ hours",
                    'count': non_vip,
                    'detected_at': now.isoformat()
                })
        
        return anomalies
    
    def check_calendar_conflicts(self) -> List[dict]:
        """Check for calendar conflicts."""
        anomalies = []
        now = datetime.now()
        
        # Get upcoming events with conflicts
        conflicts = self.store.query("""
            SELECT id, title, start_time, has_conflict, conflict_with
            FROM events
            WHERE has_conflict = 1
            AND date(start_time) >= date('now')
            ORDER BY start_time
        """)
        
        if conflicts:
            anomalies.append({
                'type': 'calendar_conflicts',
                'severity': self.HIGH if len(conflicts) > 2 else self.MEDIUM,
                'message': f"{len(conflicts)} scheduling conflicts detected",
                'count': len(conflicts),
                'items': [{'id': c['id'], 'title': c['title'], 'time': c['start_time']} for c in conflicts[:5]],
                'detected_at': now.isoformat()
            })
        
        return anomalies
    
    def check_team_blocked(self) -> List[dict]:
        """Check for team members with blocked tasks."""
        anomalies = []
        now = datetime.now()
        
        blocked_by_assignee = self.store.query("""
            SELECT assignee, COUNT(*) as blocked_count
            FROM tasks
            WHERE status = 'blocked'
            AND assignee IS NOT NULL
            AND assignee != ''
            GROUP BY assignee
            HAVING blocked_count > 0
        """)
        
        if blocked_by_assignee:
            total_people = len(blocked_by_assignee)
            total_blocked = sum(r['blocked_count'] for r in blocked_by_assignee)
            
            anomalies.append({
                'type': 'team_blocked',
                'severity': self.HIGH if total_blocked > 5 else self.MEDIUM,
                'message': f"{total_people} team member(s) have {total_blocked} blocked task(s)",
                'count': total_people,
                'items': [{'assignee': b['assignee'], 'blocked': b['blocked_count']} for b in blocked_by_assignee[:5]],
                'detected_at': now.isoformat()
            })
        
        return anomalies
    
    def check_priority_queue_health(self) -> List[dict]:
        """Check priority queue for concerning patterns."""
        anomalies = []
        now = datetime.now()
        
        # Count critical priority items
        critical_count = self.store.count(
            'tasks',
            where="status NOT IN ('completed', 'done', 'cancelled') AND priority >= 90"
        )
        
        if critical_count > self.thresholds['max_concurrent_critical']:
            anomalies.append({
                'type': 'too_many_critical',
                'severity': self.HIGH,
                'message': f"{critical_count} tasks marked critical - prioritization may be inflated",
                'count': critical_count,
                'detected_at': now.isoformat()
            })
        
        return anomalies
    
    def check_workload_spike(self) -> List[dict]:
        """Check for unusual workload spikes."""
        anomalies = []
        now = datetime.now()
        
        # Compare today's new items to 7-day average
        today_start = now.replace(hour=0, minute=0, second=0).isoformat()
        week_ago = (now - timedelta(days=7)).isoformat()
        
        today_count = self.store.count(
            'communications',
            where="created_at >= ?",
            params=[today_start]
        )
        
        week_count = self.store.count(
            'communications',
            where="created_at >= ?",
            params=[week_ago]
        )
        
        daily_avg = week_count / 7 if week_count > 0 else 0
        
        if daily_avg > 0 and today_count > daily_avg * self.thresholds['daily_email_spike_multiplier']:
            anomalies.append({
                'type': 'email_volume_spike',
                'severity': self.MEDIUM,
                'message': f"Unusual email volume today: {today_count} vs {daily_avg:.0f} daily average",
                'count': today_count,
                'average': round(daily_avg, 1),
                'detected_at': now.isoformat()
            })
        
        return anomalies
    
    def save_anomaly(self, anomaly: dict):
        """Persist anomaly to database for tracking."""
        self.store.insert('insights', {
            'id': f"anomaly_{anomaly['type']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'type': 'anomaly',
            'source': 'anomaly_detector',
            'title': anomaly['message'],
            'data': json.dumps(anomaly),
            'priority': {'critical': 100, 'high': 80, 'medium': 50, 'low': 20}.get(anomaly['severity'], 50),
            'status': 'active',
            'created_at': datetime.now().isoformat()
        })
