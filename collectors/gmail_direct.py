#!/usr/bin/env python3
"""
Direct Gmail API access using service account with gmail.readonly scope.
Bypasses gog which requires gmail.modify.
"""

import json
import base64
import socket
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Force IPv4 to avoid IPv6 timeout issues
_original_getaddrinfo = socket.getaddrinfo
def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _getaddrinfo_ipv4

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA_FILE = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
DEFAULT_USER = 'molham@hrmny.co'

OUT_DIR = Path(__file__).parent.parent / "out"


def get_gmail_service(user: str = DEFAULT_USER):
    """Get Gmail API service using service account."""
    creds = service_account.Credentials.from_service_account_file(
        str(SA_FILE), scopes=SCOPES
    )
    creds = creds.with_subject(user)
    return build('gmail', 'v1', credentials=creds)


def search_threads(query: str = "is:inbox", max_results: int = 50, user: str = DEFAULT_USER) -> List[Dict]:
    """Search Gmail threads."""
    service = get_gmail_service(user)
    results = service.users().threads().list(
        userId='me', maxResults=max_results, q=query
    ).execute()
    return results.get('threads', [])


def get_thread(thread_id: str, user: str = DEFAULT_USER) -> Dict:
    """Get full thread with messages."""
    service = get_gmail_service(user)
    return service.users().threads().get(
        userId='me', id=thread_id, format='full'
    ).execute()


def get_message(message_id: str, user: str = DEFAULT_USER) -> Dict:
    """Get full message."""
    service = get_gmail_service(user)
    return service.users().messages().get(
        userId='me', id=message_id, format='full'
    ).execute()


def extract_body(message: Dict) -> str:
    """Extract body text from message."""
    payload = message.get('payload', {})
    
    # Try direct body
    body_data = payload.get('body', {}).get('data', '')
    if body_data:
        try:
            return base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')
        except:
            pass
    
    # Try parts
    for part in payload.get('parts', []):
        if part.get('mimeType') == 'text/plain':
            data = part.get('body', {}).get('data', '')
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                except:
                    pass
        # Check nested parts
        for subpart in part.get('parts', []):
            if subpart.get('mimeType') == 'text/plain':
                data = subpart.get('body', {}).get('data', '')
                if data:
                    try:
                        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    except:
                        pass
    
    return message.get('snippet', '')


def extract_headers(message: Dict) -> Dict[str, str]:
    """Extract headers from message."""
    headers = {}
    for h in message.get('payload', {}).get('headers', []):
        headers[h['name'].lower()] = h['value']
    return headers


def collect_gmail_full(query: str = "is:unread in:inbox", max_threads: int = 20, user: str = DEFAULT_USER, timeout_per_thread: int = 10) -> Dict:
    """
    Collect Gmail threads with full message bodies.
    Uses parallel fetching with timeouts for speed.
    
    Returns dict with threads and messages ready for V4 ingestion.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
    
    print(f"📧 Fetching Gmail threads (query: {query}, max: {max_threads})...")
    
    threads = search_threads(query, max_threads, user)
    print(f"   Found {len(threads)} threads")
    
    all_messages = []
    errors = 0
    
    def fetch_thread(thread_summary):
        thread_id = thread_summary['id']
        thread = get_thread(thread_id, user)
        messages = []
        for msg in thread.get('messages', []):
            headers = extract_headers(msg)
            body = extract_body(msg)
            messages.append({
                'id': msg['id'],
                'threadId': thread_id,
                'subject': headers.get('subject', ''),
                'from': headers.get('from', ''),
                'to': headers.get('to', ''),
                'cc': headers.get('cc', ''),
                'date': headers.get('date', ''),
                'snippet': msg.get('snippet', ''),
                'body': body,
                'labels': msg.get('labelIds', []),
                'internalDate': msg.get('internalDate', '')
            })
        return messages
    
    # Parallel fetch with timeout
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_thread, t): t['id'] for t in threads}
        done = 0
        for future in as_completed(futures, timeout=120):  # 2 min total timeout
            thread_id = futures[future]
            try:
                msgs = future.result(timeout=timeout_per_thread)
                all_messages.extend(msgs)
            except Exception as e:
                errors += 1
            done += 1
            if done % 10 == 0:
                print(f"   Processed {done}/{len(threads)} threads...")
    
    print(f"   ✅ Collected {len(all_messages)} messages ({errors} errors)")
    
    return {
        'collected_at': datetime.now().isoformat(),
        'query': query,
        'user': user,
        'threads_count': len(threads),
        'messages': all_messages
    }


def save(data: Dict, filename: str = "gmail-full.json"):
    """Save to output directory."""
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"   Saved to {path}")
    return path


if __name__ == "__main__":
    import sys
    
    query = sys.argv[1] if len(sys.argv) > 1 else "is:unread in:inbox"
    max_threads = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    
    data = collect_gmail_full(query, max_threads)
    save(data)
