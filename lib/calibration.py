"""
Weekly Calibration Loop - Reviews patterns and adjusts weights.

Runs weekly to:
1. Analyze feedback patterns
2. Review priority accuracy
3. Adjust scoring weights
4. Generate calibration report
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from .state_store import StateStore, get_store


class CalibrationEngine:
    """Weekly calibration for priority scoring and anomaly detection."""
    
    def __init__(self, store: StateStore = None):
        self.store = store or get_store()
    
    def run_weekly_calibration(self) -> Dict:
        """
        Run full weekly calibration.
        
        Returns calibration report.
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'period': 'weekly',
            'feedback_analysis': self._analyze_feedback(),
            'priority_accuracy': self._analyze_priority_accuracy(),
            'completion_patterns': self._analyze_completion_patterns(),
            'recommendations': []
        }
        
        # Generate recommendations
        report['recommendations'] = self._generate_recommendations(report)
        
        # Store calibration report
        self._store_report(report)
        
        return report
    
    def _analyze_feedback(self) -> Dict:
        """Analyze user feedback from the past week."""
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        feedback = self.store.query(
            "SELECT feedback_type, COUNT(*) as count FROM feedback WHERE created_at > ? GROUP BY feedback_type",
            [week_ago]
        )
        
        counts = {f['feedback_type']: f['count'] for f in feedback}
        total = sum(counts.values())
        
        return {
            'total': total,
            'positive': counts.get('good', 0),
            'negative': counts.get('bad', 0),
            'satisfaction_rate': counts.get('good', 0) / total if total > 0 else None
        }
    
    def _analyze_priority_accuracy(self) -> Dict:
        """Analyze how well priorities matched actual completion order."""
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        # Get completed tasks with their original priority
        completed = self.store.query("""
            SELECT id, title, priority, updated_at
            FROM tasks 
            WHERE status IN ('completed', 'done')
            AND updated_at > ?
            ORDER BY updated_at
        """, [week_ago])
        
        # Calculate if high-priority items were completed first
        high_priority_first = 0
        total_completed = len(completed)
        
        for i, task in enumerate(completed):
            # If in first half of completions and high priority, that's good
            if i < total_completed / 2 and task.get('priority', 50) >= 70:
                high_priority_first += 1
        
        return {
            'total_completed': total_completed,
            'high_priority_first': high_priority_first,
            'accuracy_estimate': high_priority_first / (total_completed / 2) if total_completed > 1 else None
        }
    
    def _analyze_completion_patterns(self) -> Dict:
        """Analyze task completion patterns."""
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        # Count by day of week
        by_day = self.store.query("""
            SELECT strftime('%w', updated_at) as day, COUNT(*) as count
            FROM tasks
            WHERE status IN ('completed', 'done')
            AND updated_at > ?
            GROUP BY day
        """, [week_ago])
        
        days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        pattern = {days[int(d['day'])]: d['count'] for d in by_day}
        
        # Find peak day
        peak_day = max(pattern, key=pattern.get) if pattern else None
        
        return {
            'by_day': pattern,
            'peak_day': peak_day,
            'total': sum(pattern.values())
        }
    
    def _generate_recommendations(self, report: Dict) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        # Feedback-based recommendations
        feedback = report.get('feedback_analysis', {})
        if feedback.get('satisfaction_rate') and feedback['satisfaction_rate'] < 0.6:
            recommendations.append(
                "Priority accuracy below 60% - consider reviewing scoring weights"
            )
        
        # Completion pattern recommendations
        patterns = report.get('completion_patterns', {})
        if patterns.get('total', 0) < 5:
            recommendations.append(
                "Low task completion this week - review workload or task definitions"
            )
        
        # Priority accuracy recommendations
        accuracy = report.get('priority_accuracy', {})
        if accuracy.get('accuracy_estimate') and accuracy['accuracy_estimate'] < 0.5:
            recommendations.append(
                "High-priority tasks not being completed first - may need calibration"
            )
        
        return recommendations
    
    def _store_report(self, report: Dict):
        """Store calibration report in database."""
        self.store.insert('insights', {
            'id': f"calibration_{datetime.now().strftime('%Y%m%d')}",
            'type': 'calibration',
            'domain': 'system',
            'title': 'Weekly Calibration Report',
            'data': json.dumps(report),
            'confidence': 1.0,
            'actionable': 1 if report.get('recommendations') else 0,
            'created_at': datetime.now().isoformat()
        })
    
    def get_last_calibration(self) -> Dict:
        """Get the most recent calibration report."""
        result = self.store.query(
            "SELECT * FROM insights WHERE type = 'calibration' ORDER BY created_at DESC LIMIT 1"
        )
        if result:
            report = result[0]
            report['data'] = json.loads(report.get('data', '{}'))
            return report
        return None


# CLI interface
if __name__ == "__main__":
    import sys
    
    engine = CalibrationEngine()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'run':
        report = engine.run_weekly_calibration()
        print(json.dumps(report, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == 'last':
        report = engine.get_last_calibration()
        if report:
            print(json.dumps(report, indent=2))
        else:
            print("No calibration reports found")
    else:
        print("Usage: calibration.py [run|last]")
