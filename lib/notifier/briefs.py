"""
Brief Generator - Creates and sends scheduled briefings.

Generates:
- Daily morning brief
- Midday pulse check
- End of day summary
"""

import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.state_store import get_store
from lib.analyzers import AnalyzerOrchestrator
from lib.notifier.engine import NotificationEngine


class BriefGenerator:
    """Generates scheduled briefings."""
    
    def __init__(self):
        self.store = get_store()
        self.analyzers = AnalyzerOrchestrator(self.store)
        self.notifier = NotificationEngine(self.store, self._load_config())
    
    def _load_config(self) -> dict:
        """Load notification config."""
        config_path = Path(__file__).parent.parent.parent / 'config' / 'governance.yaml'
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
                return config.get('notification_settings', {})
        return {}
    
    def generate_daily_brief(self) -> str:
        """Generate morning daily brief."""
        analysis = self.analyzers.run_full_analysis()
        
        # Build brief
        lines = ["☀️ **Daily Brief**\n"]
        
        # Today's schedule
        today = analysis['time_analysis']['today']
        lines.append(f"📅 **Today:** {today['event_count']} events, {today['utilization_pct']}% scheduled")
        
        if today['conflicts']:
            lines.append(f"⚠️ {len(today['conflicts'])} scheduling conflicts")
        
        # Top priorities
        priorities = self.store.query("""
            SELECT title, priority, due_date FROM tasks
            WHERE status NOT IN ('completed', 'done', 'cancelled')
            ORDER BY priority DESC, due_date ASC
            LIMIT 5
        """)
        
        if priorities:
            lines.append("\n🎯 **Top Priorities:**")
            for i, p in enumerate(priorities, 1):
                due = f" (due {p['due_date']})" if p['due_date'] else ""
                lines.append(f"{i}. {p['title']}{due}")
        
        # Anomalies
        if analysis['anomalies']:
            critical = [a for a in analysis['anomalies'] if a['severity'] in ('critical', 'high')]
            if critical:
                lines.append(f"\n🚨 **{len(critical)} issues need attention**")
                for a in critical[:3]:
                    lines.append(f"• {a['message']}")
        
        # Pending responses
        pending = self.store.count(
            'communications',
            where="requires_response = 1 AND processed = 0"
        )
        if pending > 0:
            lines.append(f"\n📧 {pending} emails awaiting response")
        
        return "\n".join(lines)
    
    def generate_midday_pulse(self) -> str:
        """Generate midday pulse check."""
        lines = ["🕐 **Midday Pulse**\n"]
        
        # Progress check
        completed_today = self.store.count(
            'tasks',
            where="status IN ('completed', 'done') AND updated_at >= date('now', 'start of day')"
        )
        
        lines.append(f"✅ {completed_today} tasks completed today")
        
        # Upcoming events
        now = datetime.now()
        later = (now + timedelta(hours=4)).isoformat()
        
        upcoming = self.store.query("""
            SELECT title, start_time FROM events
            WHERE start_time >= ? AND start_time <= ?
            ORDER BY start_time
            LIMIT 3
        """, [now.isoformat(), later])
        
        if upcoming:
            lines.append("\n📅 **Coming up:**")
            for e in upcoming:
                time = datetime.fromisoformat(e['start_time']).strftime('%H:%M')
                lines.append(f"• {time} - {e['title']}")
        
        # Any blockers?
        blockers = self.store.query("""
            SELECT title FROM tasks
            WHERE status = 'blocked' AND priority >= 70
            LIMIT 3
        """)
        
        if blockers:
            lines.append(f"\n🚧 {len(blockers)} blocked high-priority items")
        
        return "\n".join(lines)
    
    def generate_eod_summary(self) -> str:
        """Generate end of day summary."""
        lines = ["🌙 **End of Day**\n"]
        
        # Today's stats
        completed = self.store.count(
            'tasks',
            where="status IN ('completed', 'done') AND updated_at >= date('now', 'start of day')"
        )
        created = self.store.count(
            'tasks',
            where="created_at >= date('now', 'start of day')"
        )
        
        lines.append(f"✅ Completed: {completed}")
        lines.append(f"📥 New: {created}")
        
        # Tomorrow preview
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        tomorrow_events = self.store.count(
            'events',
            where="date(start_time) = ?",
            params=[tomorrow]
        )
        tomorrow_due = self.store.count(
            'tasks',
            where="due_date = ? AND status NOT IN ('completed', 'done', 'cancelled')",
            params=[tomorrow]
        )
        
        lines.append(f"\n📅 **Tomorrow:** {tomorrow_events} events, {tomorrow_due} tasks due")
        
        # Reminders
        overdue = self.store.count(
            'tasks',
            where="due_date < date('now') AND status NOT IN ('completed', 'done', 'cancelled')"
        )
        if overdue > 0:
            lines.append(f"\n⚠️ {overdue} overdue tasks")
        
        return "\n".join(lines)
    
    def send_brief(self, brief_type: str):
        """Generate and send a brief."""
        generators = {
            'daily': self.generate_daily_brief,
            'midday': self.generate_midday_pulse,
            'eod': self.generate_eod_summary
        }
        
        generator = generators.get(brief_type)
        if not generator:
            print(f"Unknown brief type: {brief_type}")
            return
        
        content = generator()
        
        # Create notification
        self.notifier.create_notification(
            type='insight',
            priority='normal',
            title=f"{brief_type.title()} Brief",
            body=content
        )
        
        # Process immediately
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(self.notifier.process_pending())
        
        print(f"Sent {brief_type} brief")


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m lib.notifier.briefs <daily|midday|eod>")
        sys.exit(1)
    
    brief_type = sys.argv[1]
    generator = BriefGenerator()
    generator.send_brief(brief_type)


if __name__ == '__main__':
    main()
