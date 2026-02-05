"""
NotificationEngine - Direct delivery to user without AI.

Processes pending notifications and delivers via channels.
CRITICAL: Does NOT go through AI. Direct API calls only.
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import List, Optional
import asyncio

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class NotificationEngine:
    """
    Processes pending notifications and delivers via channels.
    CRITICAL: Does NOT go through AI. Direct API calls only.
    """
    
    def __init__(self, store, config: dict = None):
        """
        Args:
            store: StateStore instance
            config: From config/governance.yaml notification settings
        """
        self.store = store
        self.config = config or {}
        self._load_channels()
    
    def _load_channels(self):
        """Load configured notification channels."""
        self.channels = {}
        channel_config = self.config.get('channels', {})
        
        # Load Clawdbot channel if configured
        clawdbot_cfg = channel_config.get('clawdbot', {})
        if clawdbot_cfg.get('enabled', False):
            from .channels.clawdbot import ClawdbotChannel
            self.channels['clawdbot'] = ClawdbotChannel(clawdbot_cfg)
    
    async def process_pending(self) -> List[dict]:
        """
        Process all unsent notifications.
        
        Returns:
            List of {id, channel, status, error?}
        
        Implementation:
            1. SELECT * FROM notifications WHERE sent_at IS NULL
            2. For each, check rate limits (max 3 critical/day)
            3. Route to appropriate channel based on priority
            4. Call channel handler
            5. UPDATE notifications SET sent_at = NOW()
        """
        results = []
        
        # Get pending notifications
        pending = self.store.query("""
            SELECT id, type, priority, title, body, action_url, action_data, channels, created_at
            FROM notifications
            WHERE sent_at IS NULL
            ORDER BY 
                CASE priority 
                    WHEN 'critical' THEN 1 
                    WHEN 'high' THEN 2 
                    WHEN 'normal' THEN 3 
                    ELSE 4 
                END,
                created_at ASC
        """)
        
        for row in pending:
            notif_id = row['id']
            priority = row['priority']
            title = row['title']
            body = row['body']
            channels_json = row['channels']
            
            # Check rate limit
            if not self._check_rate_limit(priority):
                results.append({
                    'id': notif_id,
                    'status': 'rate_limited',
                    'error': f'Rate limit exceeded for {priority} priority'
                })
                continue
            
            # Check quiet hours for non-critical
            if priority != 'critical' and self._is_quiet_hours():
                results.append({
                    'id': notif_id,
                    'status': 'deferred',
                    'error': 'Quiet hours - deferred'
                })
                continue
            
            # Parse channels or use default
            target_channels = json.loads(channels_json) if channels_json else ['clawdbot']
            
            # Build message
            message = f"**{title}**"
            if body:
                message += f"\n\n{body}"
            
            # Send via each channel
            for channel_name in target_channels:
                if channel_name not in self.channels:
                    results.append({
                        'id': notif_id,
                        'channel': channel_name,
                        'status': 'error',
                        'error': f'Channel {channel_name} not configured'
                    })
                    continue
                
                try:
                    channel = self.channels[channel_name]
                    result = await channel.send(message, priority=priority)
                    
                    if result.get('success'):
                        # Mark as sent
                        self.store.update('notifications', notif_id, {
                            'sent_at': datetime.now().isoformat(),
                            'delivery_channel': channel_name,
                            'delivery_id': result.get('message_id')
                        })
                        
                        results.append({
                            'id': notif_id,
                            'channel': channel_name,
                            'status': 'sent',
                            'message_id': result.get('message_id')
                        })
                    else:
                        results.append({
                            'id': notif_id,
                            'channel': channel_name,
                            'status': 'error',
                            'error': result.get('error', 'Unknown error')
                        })
                        
                except Exception as e:
                    results.append({
                        'id': notif_id,
                        'channel': channel_name,
                        'status': 'error',
                        'error': str(e)
                    })
        
        return results
    
    def process_pending_sync(self) -> List[dict]:
        """
        Synchronous version of process_pending using send_sync.
        Use this when asyncio is not available or for simpler integration.
        """
        results = []
        
        pending = self.store.query("""
            SELECT id, type, priority, title, body, action_url, action_data, channels, created_at
            FROM notifications
            WHERE sent_at IS NULL
            ORDER BY 
                CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
                created_at ASC
            LIMIT 20
        """)
        
        for row in pending:
            notif_id = row['id']
            priority = row['priority']
            title = row['title']
            body = row['body']
            channels_json = row['channels']
            
            if not self._check_rate_limit(priority):
                results.append({'id': notif_id, 'status': 'rate_limited'})
                continue
            
            if priority != 'critical' and self._is_quiet_hours():
                results.append({'id': notif_id, 'status': 'deferred'})
                continue
            
            target_channels = json.loads(channels_json) if channels_json else ['clawdbot']
            message = f"**{title}**"
            if body:
                message += f"\n\n{body}"
            
            for channel_name in target_channels:
                if channel_name not in self.channels:
                    results.append({'id': notif_id, 'channel': channel_name, 'status': 'error', 'error': f'{channel_name} not configured'})
                    continue
                
                try:
                    channel = self.channels[channel_name]
                    # Use sync method
                    result = channel.send_sync(message, priority=priority)
                    
                    if result.get('success'):
                        self.store.update('notifications', notif_id, {
                            'sent_at': datetime.now().isoformat(),
                            'delivery_channel': channel_name,
                            'delivery_id': result.get('message_id')
                        })
                        results.append({'id': notif_id, 'channel': channel_name, 'status': 'sent'})
                    else:
                        results.append({'id': notif_id, 'channel': channel_name, 'status': 'error', 'error': result.get('error')})
                except Exception as e:
                    results.append({'id': notif_id, 'channel': channel_name, 'status': 'error', 'error': str(e)})
        
        return results
    
    def create_notification(
        self,
        type: str,
        priority: str,
        title: str,
        body: str = None,
        action_url: str = None,
        action_data: dict = None,
        channels: List[str] = None
    ) -> str:
        """
        Create a new notification for delivery.
        
        Args:
            type: 'alert' | 'reminder' | 'insight' | 'decision'
            priority: 'critical' | 'high' | 'normal' | 'low'
            title: Notification title
            body: Optional body text
            action_url: Optional URL for action
            action_data: Optional action data dict
            channels: Optional list of channels ['clawdbot', 'push', 'email']
        
        Returns:
            notification_id
        """
        notif_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        self.store.insert('notifications', {
            'id': notif_id,
            'type': type,
            'priority': priority,
            'title': title,
            'body': body,
            'action_url': action_url,
            'action_data': json.dumps(action_data) if action_data else None,
            'channels': json.dumps(channels) if channels else None,
            'created_at': now
        })
        
        return notif_id
    
    def _check_rate_limit(self, priority: str) -> bool:
        """
        Check if we can send another notification of this priority.
        
        Limits (from MOH_TIME_OS_REPORTING.md):
            - critical: 3/day
            - high: 5/day  
            - normal: 10/day
            - low: unlimited (but batched)
        """
        limits = {
            'critical': 3,
            'high': 5,
            'normal': 10,
            'low': 999999  # Effectively unlimited
        }
        
        limit = limits.get(priority, 10)
        
        # Count sent today
        today_start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
        
        count = self.store.count(
            'notifications',
            where="priority = ? AND sent_at >= ?",
            params=[priority, today_start]
        )
        
        return count < limit
    
    def _is_quiet_hours(self) -> bool:
        """Check if we're in quiet hours (23:00 - 08:00 Dubai time)."""
        quiet_config = self.config.get('quiet_hours', {})
        if not quiet_config.get('enabled', True):
            return False
        
        now = datetime.now()
        hour = now.hour
        
        start_hour = int(quiet_config.get('start', '23:00').split(':')[0])
        end_hour = int(quiet_config.get('end', '08:00').split(':')[0])
        
        # Handle overnight quiet hours
        if start_hour > end_hour:
            return hour >= start_hour or hour < end_hour
        else:
            return start_hour <= hour < end_hour
    
    def get_pending_count(self) -> dict:
        """Get count of pending notifications by priority."""
        results = self.store.query("""
            SELECT priority, COUNT(*) as cnt FROM notifications
            WHERE sent_at IS NULL
            GROUP BY priority
        """)
        
        return {row['priority']: row['cnt'] for row in results}
    
    def get_sent_today(self) -> dict:
        """Get count of sent notifications today by priority."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
        
        results = self.store.query("""
            SELECT priority, COUNT(*) as cnt FROM notifications
            WHERE sent_at >= ?
            GROUP BY priority
        """, [today_start])
        
        return {row['priority']: row['cnt'] for row in results}
