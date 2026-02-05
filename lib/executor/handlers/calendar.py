"""
Calendar Handler - Executes calendar-related actions.
"""

from datetime import datetime
import json


class CalendarHandler:
    """Handles calendar-related action execution."""
    
    def __init__(self, store, config: dict = None):
        self.store = store
        self.config = config or {}
    
    def execute(self, action: dict) -> dict:
        """Execute a calendar action."""
        action_type = action.get('action_type')
        
        handlers = {
            'create': self._create_event,
            'update': self._update_event,
            'delete': self._delete_event,
            'reschedule': self._reschedule_event
        }
        
        handler = handlers.get(action_type)
        if not handler:
            return {'success': False, 'error': f'Unknown action type: {action_type}'}
        
        try:
            return handler(action)
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _create_event(self, action: dict) -> dict:
        data = action.get('data', {})
        event_id = self.store.insert('events', {
            'id': f"event_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'source': 'time_os',
            'title': data['title'],
            'start_time': data['start_time'],
            'end_time': data.get('end_time'),
            'location': data.get('location'),
            'context': json.dumps(data.get('context', {})),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
        return {'success': True, 'event_id': event_id}
    
    def _update_event(self, action: dict) -> dict:
        event_id = action.get('event_id')
        data = action.get('data', {})
        data['updated_at'] = datetime.now().isoformat()
        self.store.update('events', event_id, data)
        return {'success': True, 'event_id': event_id}
    
    def _delete_event(self, action: dict) -> dict:
        event_id = action.get('event_id')
        self.store.delete('events', event_id)
        return {'success': True, 'event_id': event_id}
    
    def _reschedule_event(self, action: dict) -> dict:
        event_id = action.get('event_id')
        data = action.get('data', {})
        self.store.update('events', event_id, {
            'start_time': data['start_time'],
            'end_time': data.get('end_time'),
            'updated_at': datetime.now().isoformat()
        })
        return {'success': True, 'event_id': event_id}
