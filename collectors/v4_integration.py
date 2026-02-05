#!/usr/bin/env python3
"""
V4 Integration Layer for Collectors

Bridges existing collectors to the V4 artifact system.
Call after each collection to ingest data into artifacts.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from v4.collector_hooks import get_hooks
from v4.artifact_service import get_artifact_service

OUT_DIR = Path(__file__).parent.parent / "out"


class V4Integrator:
    """Integrates collector output with V4 artifact system."""
    
    def __init__(self):
        self.hooks = get_hooks()
        self.artifact_svc = get_artifact_service()
        self.stats = {
            'gmail': {'processed': 0, 'created': 0, 'links': 0},
            'calendar': {'processed': 0, 'created': 0, 'links': 0},
            'chat': {'processed': 0, 'created': 0, 'links': 0},
            'asana': {'processed': 0, 'created': 0, 'links': 0},
        }
    
    def ingest_gmail(self, data: Dict = None) -> Dict[str, Any]:
        """
        Ingest Gmail threads into V4 artifacts.
        
        Handles two formats:
        1. Thread summary format: {id, date, from, subject, labels, messageCount}
        2. Full format with messages: {id, messages: [{id, payload, ...}]}
        
        Args:
            data: Gmail data dict, or None to load from out/gmail-full.json (or gmail-unread.json)
        """
        if data is None:
            # Prefer gmail-full.json (from gmail_direct.py)
            path = OUT_DIR / "gmail-full.json"
            if not path.exists():
                path = OUT_DIR / "gmail-unread.json"
            if not path.exists():
                return {'status': 'no_data', 'path': str(path)}
            data = json.loads(path.read_text())
        
        # Handle gmail-full.json format (messages at top level)
        if 'messages' in data and not data.get('threads'):
            for msg in data.get('messages', []):
                message_data = {
                    'id': msg.get('id'),
                    'threadId': msg.get('threadId'),
                    'subject': msg.get('subject', ''),
                    'from': msg.get('from', ''),
                    'to': self._parse_recipients(msg.get('to', '')),
                    'cc': self._parse_recipients(msg.get('cc', '')),
                    'date': msg.get('date', ''),
                    'snippet': msg.get('snippet', ''),
                    'labels': msg.get('labels', []),
                    'body': msg.get('body', '')
                }
                
                try:
                    result = self.hooks.on_gmail_message_fetched(message_data)
                    self.stats['gmail']['processed'] += 1
                    if result.get('status') == 'created':
                        self.stats['gmail']['created'] += 1
                    self.stats['gmail']['links'] += result.get('links_created', 0)
                except Exception as e:
                    print(f"  Gmail ingest error for {msg.get('id')}: {e}")
            
            return self.stats['gmail']
        
        threads = data.get('threads', [])
        
        for thread in threads:
            thread_id = thread.get('id')
            messages = thread.get('messages', [])
            
            if messages:
                # Full format with messages array
                for msg in messages:
                    msg_id = msg.get('id', thread_id)
                    headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
                    
                    message_data = {
                        'id': msg_id,
                        'threadId': thread_id,
                        'subject': headers.get('subject', ''),
                        'from': headers.get('from', ''),
                        'to': self._parse_recipients(headers.get('to', '')),
                        'cc': self._parse_recipients(headers.get('cc', '')),
                        'date': headers.get('date', ''),
                        'snippet': msg.get('snippet', ''),
                        'labels': msg.get('labelIds', []),
                        'body': self._extract_body(msg)
                    }
                    
                    try:
                        result = self.hooks.on_gmail_message_fetched(message_data)
                        self.stats['gmail']['processed'] += 1
                        if result.get('status') == 'created':
                            self.stats['gmail']['created'] += 1
                        self.stats['gmail']['links'] += result.get('links_created', 0)
                    except Exception as e:
                        print(f"  Gmail ingest error for {msg_id}: {e}")
            else:
                # Thread summary format (from gog gmail search)
                message_data = {
                    'id': thread_id,
                    'threadId': thread_id,
                    'subject': thread.get('subject', ''),
                    'from': thread.get('from', ''),
                    'to': [],
                    'cc': [],
                    'date': thread.get('date', ''),
                    'snippet': thread.get('subject', ''),  # Use subject as snippet
                    'labels': thread.get('labels', []),
                    'body': '',
                    'messageCount': thread.get('messageCount', 1)
                }
                
                try:
                    result = self.hooks.on_gmail_message_fetched(message_data)
                    self.stats['gmail']['processed'] += 1
                    if result.get('status') == 'created':
                        self.stats['gmail']['created'] += 1
                    self.stats['gmail']['links'] += result.get('links_created', 0)
                except Exception as e:
                    print(f"  Gmail ingest error for {thread_id}: {e}")
        
        return self.stats['gmail']
    
    def ingest_calendar(self, data: Dict = None) -> Dict[str, Any]:
        """
        Ingest Calendar events into V4 artifacts.
        
        Args:
            data: Calendar data dict, or None to load from out/calendar-next.json
        """
        if data is None:
            path = OUT_DIR / "calendar-next.json"
            if not path.exists():
                return {'status': 'no_data', 'path': str(path)}
            data = json.loads(path.read_text())
        
        events = data.get('events', [])
        
        for event in events:
            event_id = event.get('id')
            
            # Normalize event data
            event_data = {
                'id': event_id,
                'summary': event.get('summary', ''),
                'description': event.get('description', ''),
                'start': event.get('start', {}),
                'end': event.get('end', {}),
                'organizer': event.get('organizer', {}),
                'attendees': event.get('attendees', []),
                'location': event.get('location', ''),
                'status': event.get('status', ''),
                'htmlLink': event.get('htmlLink', '')
            }
            
            try:
                result = self.hooks.on_calendar_event_synced(event_data)
                self.stats['calendar']['processed'] += 1
                if result.get('status') == 'created':
                    self.stats['calendar']['created'] += 1
                self.stats['calendar']['links'] += result.get('links_created', 0)
            except Exception as e:
                print(f"  Calendar ingest error for {event_id}: {e}")
        
        return self.stats['calendar']
    
    def ingest_chat(self, data: Dict = None) -> Dict[str, Any]:
        """
        Ingest Chat messages into V4 artifacts.
        
        Args:
            data: Chat data dict, or None to load from out/chat-full.json
        """
        if data is None:
            # Prefer chat-full.json (from chat_direct.py)
            path = OUT_DIR / "chat-full.json"
            if not path.exists():
                path = OUT_DIR / "chat-mentions.json"
            if not path.exists():
                return {'status': 'no_data', 'path': str(path)}
            data = json.loads(path.read_text())
        
        # Process all messages from chat-full.json format
        messages = data.get('messages', [])
        
        for msg in messages:
            # Handle chat_direct.py format
            msg_name = msg.get('name', '')
            msg_id = msg_name.replace('spaces/', '').replace('/messages/', '_') if msg_name else msg.get('id', '')
            
            # Normalize message data
            message_data = {
                'id': msg_id,
                'space_id': msg.get('space_name', ''),
                'space_name': msg.get('space_display_name', ''),
                'text': msg.get('text', ''),
                'sender': {'displayName': msg.get('sender', ''), 'email': msg.get('sender_email', '')},
                'createTime': msg.get('create_time', ''),
                'thread': {'name': msg.get('thread_name', '')}
            }
            
            try:
                result = self._ingest_chat_message(message_data)
                self.stats['chat']['processed'] += 1
                if result.get('status') == 'created':
                    self.stats['chat']['created'] += 1
                self.stats['chat']['links'] += result.get('links_created', 0)
            except Exception as e:
                print(f"  Chat ingest error for {msg_id}: {e}")
        
        return self.stats['chat']
    
    def _ingest_chat_message(self, message_data: Dict) -> Dict[str, Any]:
        """Ingest a single chat message."""
        msg_id = message_data.get('id')
        
        # Resolve sender
        sender = message_data.get('sender', {})
        sender_email = sender.get('email', '')
        actor_id = None
        
        if sender_email:
            from v4.identity_service import get_identity_service
            identity_svc = get_identity_service()
            profile = identity_svc.resolve_identity(
                'email', sender_email, create_if_missing=True, source='gchat'
            )
            if profile:
                actor_id = profile['profile_id']
        
        # Create artifact
        result = self.artifact_svc.create_artifact(
            source='gchat',
            source_id=msg_id,
            artifact_type='message',
            occurred_at=message_data.get('createTime', datetime.now().isoformat()),
            payload=message_data,
            actor_person_id=actor_id
        )
        
        if result['status'] == 'unchanged':
            return result
        
        artifact_id = result['artifact_id']
        links = []
        
        # Link to thread/space
        space_id = message_data.get('space_id')
        if space_id:
            from v4.entity_link_service import get_entity_link_service
            link_svc = get_entity_link_service()
            link = link_svc.create_link(
                artifact_id, 'thread', space_id, 'headers',
                0.95, ['Chat space reference'], auto_confirm=True
            )
            links.append(link)
        
        # Match clients in text
        text = message_data.get('text', '')
        for cid, conf, reason in self.hooks._match_client_in_text(text):
            from v4.entity_link_service import get_entity_link_service
            link_svc = get_entity_link_service()
            link = link_svc.create_link(
                artifact_id, 'client', cid, 'naming', conf,
                [reason], auto_confirm=(conf >= 0.85)
            )
            links.append(link)
        
        # Create excerpt
        if text:
            self.artifact_svc.create_excerpt(
                artifact_id, text[:500],
                anchor_type='message_quote'
            )
        
        return {
            'artifact_id': artifact_id,
            'status': result['status'],
            'links_created': len(links)
        }
    
    def ingest_all(self) -> Dict[str, Any]:
        """Ingest from all available collector outputs."""
        results = {}
        
        print("📥 V4 Ingest — Processing collector outputs...")
        
        # Gmail
        print("  📧 Gmail...")
        results['gmail'] = self.ingest_gmail()
        print(f"     → {results['gmail'].get('processed', 0)} messages, {results['gmail'].get('created', 0)} new")
        
        # Calendar
        print("  📅 Calendar...")
        results['calendar'] = self.ingest_calendar()
        print(f"     → {results['calendar'].get('processed', 0)} events, {results['calendar'].get('created', 0)} new")
        
        # Chat
        print("  💬 Chat...")
        results['chat'] = self.ingest_chat()
        print(f"     → {results['chat'].get('processed', 0)} messages, {results['chat'].get('created', 0)} new")
        
        print("  ✅ V4 ingest complete")
        
        return results
    
    def _parse_recipients(self, header_value: str) -> List[str]:
        """Parse email recipient header into list of addresses."""
        if not header_value:
            return []
        # Simple parsing - split by comma and extract emails
        import re
        emails = re.findall(r'[\w\.-]+@[\w\.-]+', header_value)
        return emails
    
    def _extract_body(self, msg: Dict) -> str:
        """Extract body text from Gmail message."""
        payload = msg.get('payload', {})
        
        # Try direct body
        body_data = payload.get('body', {}).get('data', '')
        if body_data:
            import base64
            try:
                return base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
            except:
                pass
        
        # Try parts
        for part in payload.get('parts', []):
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    import base64
                    try:
                        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    except:
                        pass
        
        return msg.get('snippet', '')


def ingest_from_collectors():
    """Main entry point for V4 ingest after collection."""
    integrator = V4Integrator()
    return integrator.ingest_all()


def fetch_and_ingest_gmail_full(query: str = "is:inbox", max_threads: int = 20):
    """
    Fetch full Gmail message bodies and ingest for commitment detection.
    
    Uses direct Gmail API with gmail.readonly scope (bypasses gog).
    """
    from gmail_direct import collect_gmail_full
    
    integrator = V4Integrator()
    
    print(f"📧 Fetching full Gmail content...")
    
    # Collect using direct API
    data = collect_gmail_full(query, max_threads)
    messages = data.get('messages', [])
    
    results = {'processed': 0, 'created': 0, 'links': 0, 'errors': 0}
    
    for msg in messages:
        try:
            message_data = {
                'id': msg['id'],
                'threadId': msg['threadId'],
                'subject': msg.get('subject', ''),
                'from': msg.get('from', ''),
                'to': integrator._parse_recipients(msg.get('to', '')),
                'cc': integrator._parse_recipients(msg.get('cc', '')),
                'date': msg.get('date', ''),
                'snippet': msg.get('snippet', ''),
                'labels': msg.get('labels', []),
                'body': msg.get('body', '')
            }
            
            ingest_result = integrator.hooks.on_gmail_message_fetched(message_data)
            results['processed'] += 1
            if ingest_result.get('status') == 'created':
                results['created'] += 1
            results['links'] += ingest_result.get('links_created', 0)
            
        except Exception as e:
            print(f"  Error ingesting {msg.get('id', 'unknown')}: {e}")
            results['errors'] += 1
    
    print(f"  → {results['processed']} messages, {results['created']} new, {results['errors']} errors")
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--full-gmail':
        # Fetch full Gmail content
        max_threads = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        results = fetch_and_ingest_gmail_full(max_threads=max_threads)
    else:
        results = ingest_from_collectors()
    
    print(json.dumps(results, indent=2))
