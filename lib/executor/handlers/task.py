"""
Task Handler - Executes task-related actions.

Handles:
- Task creation/updates in external systems (Asana, etc.)
- Status changes
- Assignment changes
- Priority updates
"""

from datetime import datetime
from typing import Dict, Optional
import json
import subprocess


class TaskHandler:
    """Handles task-related action execution."""
    
    def __init__(self, store, config: dict = None):
        self.store = store
        self.config = config or {}
    
    def execute(self, action: dict) -> dict:
        """
        Execute a task action.
        
        Args:
            action: {
                'action_type': 'create'|'update'|'complete'|'assign'|'prioritize',
                'task_id': str (for updates),
                'data': {...}
            }
        
        Returns:
            {success: bool, result?: any, error?: str}
        """
        action_type = action.get('action_type')
        
        handlers = {
            'create': self._create_task,
            'update': self._update_task,
            'complete': self._complete_task,
            'assign': self._assign_task,
            'prioritize': self._prioritize_task,
            'snooze': self._snooze_task
        }
        
        handler = handlers.get(action_type)
        if not handler:
            return {'success': False, 'error': f'Unknown action type: {action_type}'}
        
        try:
            result = handler(action)
            
            # Log the action
            self._log_action(action, result)
            
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _create_task(self, action: dict) -> dict:
        """Create a new task."""
        data = action.get('data', {})
        
        # Create in local store
        task_id = self.store.insert('tasks', {
            'id': data.get('id') or f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'source': data.get('source', 'time_os'),
            'title': data['title'],
            'status': 'pending',
            'priority': data.get('priority', 50),
            'due_date': data.get('due_date'),
            'due_time': data.get('due_time'),
            'assignee': data.get('assignee'),
            'project': data.get('project'),
            'lane': data.get('lane', 'ops'),
            'tags': json.dumps(data.get('tags', [])),
            'context': json.dumps(data.get('context', {})),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        })
        
        # Sync to external system if configured
        if data.get('sync_to_asana') and self.config.get('asana_enabled'):
            self._sync_to_asana(task_id, data)
        
        return {'success': True, 'task_id': task_id}
    
    def _update_task(self, action: dict) -> dict:
        """Update an existing task."""
        task_id = action.get('task_id')
        data = action.get('data', {})
        
        if not task_id:
            return {'success': False, 'error': 'task_id required'}
        
        # Update local store
        data['updated_at'] = datetime.now().isoformat()
        self.store.update('tasks', task_id, data)
        
        return {'success': True, 'task_id': task_id}
    
    def _complete_task(self, action: dict) -> dict:
        """Mark a task as complete."""
        task_id = action.get('task_id')
        
        if not task_id:
            return {'success': False, 'error': 'task_id required'}
        
        self.store.update('tasks', task_id, {
            'status': 'completed',
            'updated_at': datetime.now().isoformat()
        })
        
        # Sync to external system
        task = self.store.get('tasks', task_id)
        if task and task.get('source') == 'asana' and task.get('source_id'):
            self._complete_in_asana(task['source_id'])
        
        return {'success': True, 'task_id': task_id}
    
    def _assign_task(self, action: dict) -> dict:
        """Assign a task to someone."""
        task_id = action.get('task_id')
        assignee = action.get('data', {}).get('assignee')
        
        if not task_id or not assignee:
            return {'success': False, 'error': 'task_id and assignee required'}
        
        self.store.update('tasks', task_id, {
            'assignee': assignee,
            'updated_at': datetime.now().isoformat()
        })
        
        return {'success': True, 'task_id': task_id, 'assignee': assignee}
    
    def _prioritize_task(self, action: dict) -> dict:
        """Update task priority."""
        task_id = action.get('task_id')
        priority = action.get('data', {}).get('priority')
        
        if not task_id or priority is None:
            return {'success': False, 'error': 'task_id and priority required'}
        
        self.store.update('tasks', task_id, {
            'priority': priority,
            'updated_at': datetime.now().isoformat()
        })
        
        return {'success': True, 'task_id': task_id, 'priority': priority}
    
    def _snooze_task(self, action: dict) -> dict:
        """Snooze a task until a later date."""
        task_id = action.get('task_id')
        until = action.get('data', {}).get('until')
        
        if not task_id or not until:
            return {'success': False, 'error': 'task_id and until date required'}
        
        self.store.update('tasks', task_id, {
            'status': 'snoozed',
            'due_date': until,
            'updated_at': datetime.now().isoformat()
        })
        
        return {'success': True, 'task_id': task_id, 'snoozed_until': until}
    
    def _sync_to_asana(self, task_id: str, data: dict):
        """Sync task to Asana via CLI."""
        # This would use the asana CLI or API
        pass
    
    def _complete_in_asana(self, asana_id: str):
        """Mark task complete in Asana."""
        # This would use the asana CLI or API
        pass
    
    def _log_action(self, action: dict, result: dict):
        """Log action to database."""
        self.store.insert('actions', {
            'id': f"action_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            'type': action.get('action_type', 'task_action'),
            'target_system': 'tasks',
            'payload': json.dumps({
                'action': action,
                'task_id': action.get('task_id'),
                'data': action.get('data', {})
            }),
            'status': 'completed' if result.get('success') else 'failed',
            'requires_approval': 0,
            'result': json.dumps(result),
            'created_at': datetime.now().isoformat()
        })
