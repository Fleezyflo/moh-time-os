"""
Gmail Collector - Pulls emails from Gmail via gog CLI.
Uses REAL gog commands that actually work.
Fetches FULL message body via gog gmail get <id>.
"""

import json
import re
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .base import BaseCollector


class GmailCollector(BaseCollector):
    """Collects emails from Gmail."""
    
    source_name = 'gmail'
    target_table = 'communications'
    
    def _fetch_message_body(self, thread_id: str) -> Dict[str, str]:
        """
        Fetch full message body for a thread.
        Returns: {'body': str, 'body_source': 'html_stripped'|'plain'|'snippet_fallback'}
        """
        try:
            output = self._run_command(f'gog gmail get {thread_id} --json 2>/dev/null', timeout=10)
            if not output.strip():
                return {'body': '', 'body_source': 'snippet_fallback'}
            
            data = self._parse_json_output(output)
            raw_body = data.get('body', '')
            
            if not raw_body:
                return {'body': '', 'body_source': 'snippet_fallback'}
            
            # Strip HTML tags if present
            if '<html' in raw_body.lower() or '<body' in raw_body.lower() or '<div' in raw_body.lower():
                # Remove style/script tags and their content
                text = re.sub(r'<style[^>]*>.*?</style>', '', raw_body, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                # Remove all HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                # Decode HTML entities
                text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                text = text.replace('&#39;', "'").replace('&quot;', '"')
                # Normalize whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                return {'body': text, 'body_source': 'html_stripped'}
            else:
                return {'body': raw_body.strip(), 'body_source': 'plain'}
                
        except Exception as e:
            self.logger.warning(f"Failed to fetch body for {thread_id}: {e}")
            return {'body': '', 'body_source': 'snippet_fallback'}
    
    def collect(self) -> Dict[str, Any]:
        """Fetch emails from Gmail using gog CLI."""
        try:
            all_threads = []
            lookback_days = self.config.get('lookback_days', 90)
            max_results = self.config.get('max_results', 500)
            
            # Get all emails from past 90 days (excluding promotions/updates/social)
            # Handle pagination
            page_token = None
            fetched = 0
            
            while fetched < max_results:
                page_arg = f'--page "{page_token}"' if page_token else ''
                output = self._run_command(
                    f'gog gmail search "newer_than:{lookback_days}d -category:promotions -category:updates -category:social" --max 100 {page_arg} --json 2>/dev/null',
                    timeout=60
                )
                if not output.strip():
                    break
                    
                data = self._parse_json_output(output)
                threads = data.get('threads') or []
                all_threads.extend(threads)
                fetched += len(threads)
                
                # Check for more pages
                page_token = data.get('nextPageToken')
                if not page_token or len(threads) == 0:
                    break
            
            # Deduplicate by thread id
            seen = set()
            unique = []
            for thread in all_threads:
                tid = thread.get('id')
                if tid and tid not in seen:
                    seen.add(tid)
                    unique.append(thread)
            
            # Fetch full body for each thread (limit to avoid rate limits)
            # Skip threads we already have body for (incremental fetch)
            max_bodies = self.config.get('max_body_fetch', 100)
            bodies_fetched = 0
            
            # Get existing thread IDs with body
            existing_with_body = set()
            try:
                rows = self.store.query(
                    "SELECT source_id FROM communications WHERE source = 'gmail' AND body_text IS NOT NULL AND body_text != '' AND body_text_source != 'snippet_fallback'"
                )
                existing_with_body = {r['source_id'] for r in rows}
            except Exception:
                pass  # If query fails, fetch all
            
            for thread in unique:
                if bodies_fetched >= max_bodies:
                    break
                tid = thread.get('id', '')
                if tid in existing_with_body:
                    continue  # Skip, already have body
                body_data = self._fetch_message_body(tid)
                thread['body'] = body_data['body']
                thread['body_source'] = body_data['body_source']
                # Compute content hash on full body
                if body_data['body']:
                    thread['content_hash'] = hashlib.sha256(body_data['body'].encode()).hexdigest()[:16]
                bodies_fetched += 1
            
            return {'threads': unique}
            
        except Exception as e:
            self.logger.warning(f"Gmail collection failed: {e}")
            return {'threads': []}
    
    def transform(self, raw_data: Dict) -> List[Dict]:
        """Transform Gmail threads to canonical format."""
        now = datetime.now().isoformat()
        transformed = []
        
        for thread in raw_data.get('threads', []):
            thread_id = thread.get('id')
            if not thread_id:
                continue
            
            # Skip promotional/update categories
            labels = thread.get('labels', [])
            if any(cat in labels for cat in ['CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_SOCIAL']):
                continue
            
            from_addr = self._extract_from(thread)
            subject = thread.get('subject', '(no subject)')
            
            # Get full message body (fetched in collect phase)
            body_text = thread.get('body', '') or thread.get('snippet', '') or subject
            body_source = thread.get('body_source', 'snippet_fallback')
            content_hash = thread.get('content_hash', '')
            
            # If body is too short, mark as snippet fallback
            if len(body_text) < 50:
                body_source = 'snippet_fallback'
            
            transformed.append({
                'id': f"gmail_{thread_id}",
                'source': 'gmail',
                'content_hash': content_hash,
                'body_text_source': body_source,
                'source_id': thread_id,
                'thread_id': thread_id,
                'from_email': from_addr,
                'to_emails': json.dumps([]),
                'subject': subject,
                'snippet': (body_text or subject)[:500],  # Store more text in snippet
                'body_text': body_text,  # Full body for commitment extraction
                'priority': self._compute_priority(thread),
                'requires_response': 1 if self._needs_response(thread) else 0,
                'response_deadline': self._compute_response_deadline(thread),
                'sentiment': self._analyze_sentiment(thread),
                'labels': json.dumps(labels),
                'sensitivity': '',
                'stakeholder_tier': '',
                'processed': 0,
                'created_at': self._parse_date(thread.get('date', ''))
            })
        
        return transformed
    
    def _extract_from(self, thread: Dict) -> str:
        """Extract sender from thread."""
        from_field = thread.get('from', '')
        # Parse "Name <email>" format
        if '<' in from_field and '>' in from_field:
            start = from_field.index('<') + 1
            end = from_field.index('>')
            return from_field[start:end]
        return from_field
    
    def _parse_date(self, date_str: str) -> str:
        """Parse date from gog output format."""
        if not date_str:
            return datetime.now().isoformat()
        
        # Format: "2026-02-01 08:33"
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            return dt.isoformat()
        except ValueError:
            return datetime.now().isoformat()
    
    def _compute_priority(self, thread: Dict) -> int:
        """Compute email priority 0-100."""
        score = 50
        
        from_addr = self._extract_from(thread).lower()
        labels = thread.get('labels', [])
        subject = thread.get('subject', '').lower()
        
        # Sender importance
        priority_domains = self.config.get('priority_senders', [])
        for rule in priority_domains:
            pattern = rule.get('pattern', '').lower()
            if pattern in from_addr:
                score += rule.get('boost', 0)
        
        # Important senders
        if '@hrmny' in from_addr:
            score += 25
        if 'tax.gov' in from_addr or 'government' in from_addr:
            score += 20
        
        # Label boosts
        if 'IMPORTANT' in labels:
            score += 15
        if 'STARRED' in labels:
            score += 10
        if 'UNREAD' in labels:
            score += 5
        
        # Subject keywords
        urgent_words = ['urgent', 'asap', 'immediately', 'deadline', 'overdue']
        if any(word in subject for word in urgent_words):
            score += 15
        
        return min(100, max(0, score))
    
    def _needs_response(self, thread: Dict) -> bool:
        """Determine if email likely needs a response."""
        subject = thread.get('subject', '').lower()
        from_addr = self._extract_from(thread).lower()
        snippet = thread.get('snippet', '').lower()
        
        # Skip automated emails
        no_reply_patterns = ['noreply', 'no-reply', 'donotreply', 'notification@', 
                            'alert@', 'gemini-notes', 'calendar-notification',
                            'mailer-daemon', 'automated', 'newsletter']
        if any(pattern in from_addr for pattern in no_reply_patterns):
            return False
        
        # Skip cancellation/FYI emails
        skip_patterns = ['canceled event', 'declined:', 'accepted:', 
                        'invitation:', 'updated invitation', 'notes:']
        if any(pattern in subject for pattern in skip_patterns):
            return False
        
        # Keywords indicating response needed (expanded)
        response_indicators = [
            # Explicit asks
            'please respond', 'please reply', 'awaiting', 'let me know', 
            'get back', 'your thoughts', 'action required', 'urgent', 
            'confirm', 'approval', 'approve',
            # Business patterns
            'pricing', 'proposal', 'next steps', 'request', 'discuss',
            'meeting', 'call', 'schedule', 'invoice', 'payment',
            'contract', 'agreement', 're:', 'follow up', 'follow-up',
            # Questions
            '?'
        ]
        
        # Check subject and snippet
        text = subject + ' ' + snippet
        return any(indicator in text for indicator in response_indicators)
    
    def _compute_response_deadline(self, thread: Dict) -> str:
        """Compute when a response should be sent."""
        if not self._needs_response(thread):
            return ''
        
        # 48 hours from receipt
        try:
            msg_date = datetime.fromisoformat(self._parse_date(thread.get('date', '')))
            deadline = msg_date + timedelta(hours=48)
            return deadline.isoformat()
        except Exception:
            return ''
    
    def _analyze_sentiment(self, thread: Dict) -> str:
        """Simple sentiment analysis."""
        subject = thread.get('subject', '').lower()
        
        urgent_words = ['urgent', 'asap', 'immediately', 'critical', 'emergency']
        if any(word in subject for word in urgent_words):
            return 'urgent'
        
        fyi_words = ['fyi', 'for your information', 'newsletter', 'update', 'announcement']
        if any(word in subject for word in fyi_words):
            return 'fyi'
        
        return 'normal'
