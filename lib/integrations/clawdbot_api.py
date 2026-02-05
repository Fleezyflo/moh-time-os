"""
ClawdbotAPI - Full Clawdbot Gateway integration.

For sending messages, reading channels, etc.
CRITICAL: Direct REST API, NOT through AI session.
"""

import asyncio
from typing import Dict, Optional, List

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class ClawdbotAPI:
    """
    Clawdbot Gateway REST API client.
    
    Used for:
        - Sending notifications (without AI in loop)
        - Reading channel history (if needed)
        - Managing cron jobs
    """
    
    def __init__(self, gateway_url: str = None, token: str = None):
        self.gateway_url = (gateway_url or 'http://localhost:8765').rstrip('/')
        self.token = token or ''
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    async def send_message(
        self,
        channel: str,
        to: str,
        message: str,
        reply_to: str = None
    ) -> dict:
        """
        Send a message to a channel.
        
        Endpoint: POST /api/channels/{channel}/send
        """
        if not HAS_HTTPX:
            return {'success': False, 'error': 'httpx not installed'}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    'to': to,
                    'message': message
                }
                if reply_to:
                    payload['reply_to'] = reply_to
                
                response = await client.post(
                    f"{self.gateway_url}/api/channels/{channel}/send",
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    return {'success': True, **response.json()}
                else:
                    return {
                        'success': False,
                        'error': f'HTTP {response.status_code}: {response.text}'
                    }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def get_status(self) -> dict:
        """
        Get gateway status.
        
        Endpoint: GET /api/status
        """
        if not HAS_HTTPX:
            return {'success': False, 'error': 'httpx not installed'}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.gateway_url}/api/status",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    return {'success': True, **response.json()}
                else:
                    return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def get_sessions(self) -> dict:
        """Get active sessions."""
        if not HAS_HTTPX:
            return {'success': False, 'error': 'httpx not installed'}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.gateway_url}/api/sessions",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    return {'success': True, 'sessions': response.json()}
                else:
                    return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def send_message_sync(
        self,
        channel: str,
        to: str,
        message: str,
        reply_to: str = None
    ) -> dict:
        """Synchronous wrapper for send_message."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.send_message(channel, to, message, reply_to)
        )
    
    def get_status_sync(self) -> dict:
        """Synchronous wrapper for get_status."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.get_status())


def get_clawdbot_api(config: dict = None) -> ClawdbotAPI:
    """Factory function to create ClawdbotAPI instance."""
    config = config or {}
    return ClawdbotAPI(
        gateway_url=config.get('gateway_url', 'http://localhost:8765'),
        token=config.get('token', '')
    )
