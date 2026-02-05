#!/usr/bin/env python3
"""Xero OAuth2 authorization flow - run this to get fresh tokens."""

import http.server
import json
import os
import secrets
import socketserver
import sys
import urllib.parse
import webbrowser
from typing import Any

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", ".credentials.json")

# Xero OAuth endpoints
XERO_AUTH_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"

# Local callback server
CALLBACK_PORT = 8742
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"

# Scopes needed for Time OS
SCOPES = [
    "openid",
    "profile", 
    "email",
    "accounting.contacts",
    "accounting.transactions",
    "accounting.reports.read",
    "accounting.settings",
    "offline_access",  # Required for refresh tokens
]


def load_credentials() -> dict[str, Any]:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_credentials(data: dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handle OAuth callback from Xero."""
    
    auth_code = None
    state = None
    error = None
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            
            if "error" in params:
                OAuthCallbackHandler.error = params.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {OAuthCallbackHandler.error}</h1>".encode())
            elif "code" in params:
                OAuthCallbackHandler.auth_code = params["code"][0]
                OAuthCallbackHandler.state = params.get("state", [None])[0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family: system-ui; text-align: center; padding: 50px;">
                    <h1>&#10004; Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    </body></html>
                """)
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Missing authorization code</h1>")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging


def exchange_code_for_tokens(client_id: str, client_secret: str, auth_code: str) -> dict:
    """Exchange authorization code for access and refresh tokens."""
    resp = requests.post(
        XERO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    
    if resp.status_code != 200:
        raise RuntimeError(f"Token exchange failed: {resp.status_code} {resp.text}")
    
    return resp.json()


def get_tenant_id(access_token: str) -> str:
    """Get the tenant ID (organization) from Xero."""
    resp = requests.get(
        XERO_CONNECTIONS_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to get connections: {resp.status_code} {resp.text}")
    
    connections = resp.json()
    if not connections:
        raise RuntimeError("No Xero organizations connected")
    
    # Use first organization
    return connections[0]["tenantId"]


def main():
    print("=" * 60)
    print("Xero OAuth2 Authorization Flow")
    print("=" * 60)
    
    # Load existing credentials
    creds = load_credentials()
    client_id = creds["xero"]["client_id"]
    client_secret = creds["xero"]["client_secret"]
    
    print(f"\nClient ID: {client_id[:8]}...")
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Scopes: {', '.join(SCOPES)}")
    
    # IMPORTANT: Check redirect URI is registered
    print("\n" + "=" * 60)
    print("IMPORTANT: Make sure this redirect URI is registered in your")
    print("Xero app settings at https://developer.xero.com/app/manage")
    print(f"\n  {REDIRECT_URI}")
    print("=" * 60)
    
    input("\nPress Enter when ready to continue...")
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # Build authorization URL
    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
    }
    auth_url = f"{XERO_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"
    
    # Start local server
    print(f"\nStarting callback server on port {CALLBACK_PORT}...")
    
    with socketserver.TCPServer(("", CALLBACK_PORT), OAuthCallbackHandler) as httpd:
        httpd.timeout = 120  # 2 minute timeout
        
        # Open browser
        print("Opening browser for authorization...")
        print(f"\nIf browser doesn't open, visit:\n{auth_url}\n")
        webbrowser.open(auth_url)
        
        # Wait for callback
        print("Waiting for authorization...")
        while OAuthCallbackHandler.auth_code is None and OAuthCallbackHandler.error is None:
            httpd.handle_request()
    
    if OAuthCallbackHandler.error:
        print(f"\n❌ Authorization failed: {OAuthCallbackHandler.error}")
        sys.exit(1)
    
    if OAuthCallbackHandler.state != state:
        print(f"\n❌ State mismatch - possible CSRF attack")
        sys.exit(1)
    
    print("\n✓ Got authorization code!")
    
    # Exchange for tokens
    print("Exchanging code for tokens...")
    tokens = exchange_code_for_tokens(client_id, client_secret, OAuthCallbackHandler.auth_code)
    
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    
    print("✓ Got tokens!")
    
    # Get tenant ID
    print("Getting organization (tenant) ID...")
    tenant_id = get_tenant_id(access_token)
    print(f"✓ Tenant ID: {tenant_id}")
    
    # Save updated credentials
    creds["xero"]["refresh_token"] = refresh_token
    creds["xero"]["tenant_id"] = tenant_id
    save_credentials(creds)
    
    # Also save access token to cache
    cache_path = os.path.join(os.path.dirname(CONFIG_PATH), ".xero_token_cache.json")
    with open(cache_path, "w") as f:
        json.dump({"access_token": access_token}, f)
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS! Xero authorization complete.")
    print("=" * 60)
    print(f"\nCredentials saved to: {CONFIG_PATH}")
    print("\nYou can now use the Xero integration.")


if __name__ == "__main__":
    main()
