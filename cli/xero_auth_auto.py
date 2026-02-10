#!/usr/bin/env python3
"""Xero OAuth2 authorization flow - auto-start version."""

import http.server
import json
import secrets
import socketserver
import sys
import urllib.parse
import webbrowser

import requests

from lib import paths

CONFIG_PATH = str(paths.config_dir() / ".credentials.json")

XERO_AUTH_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"

CALLBACK_PORT = 8743
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"

SCOPES = [
    "openid",
    "profile",
    "email",
    "accounting.contacts",
    "accounting.transactions",
    "accounting.reports.read",
    "accounting.settings",
    "offline_access",
]


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
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
                self.wfile.write(
                    f"<h1>Error: {OAuthCallbackHandler.error}</h1>".encode()
                )
            elif "code" in params:
                OAuthCallbackHandler.auth_code = params["code"][0]
                OAuthCallbackHandler.state = params.get("state", [None])[0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Success! Close this window.</h1></body></html>"
                )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    print("Xero OAuth2 Authorization")
    print("=" * 50)

    with open(CONFIG_PATH) as f:
        creds = json.load(f)

    client_id = creds["xero"]["client_id"]
    client_secret = creds["xero"]["client_secret"]

    state = secrets.token_urlsafe(32)

    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
    }
    auth_url = f"{XERO_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    print(f"Starting server on port {CALLBACK_PORT}...")
    print("Opening browser...")
    print(f"\nIf browser doesn't open, visit:\n{auth_url}\n")

    with socketserver.TCPServer(("", CALLBACK_PORT), OAuthCallbackHandler) as httpd:
        httpd.timeout = 120
        webbrowser.open(auth_url)

        print("Waiting for authorization (2 min timeout)...")
        while (
            OAuthCallbackHandler.auth_code is None
            and OAuthCallbackHandler.error is None
        ):
            httpd.handle_request()

    if OAuthCallbackHandler.error:
        print(f"❌ Error: {OAuthCallbackHandler.error}")
        sys.exit(1)

    print("✓ Got auth code, exchanging for tokens...")

    resp = requests.post(
        XERO_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": OAuthCallbackHandler.auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )

    if resp.status_code != 200:
        print(f"❌ Token exchange failed: {resp.text}")
        sys.exit(1)

    tokens = resp.json()
    print("✓ Got tokens!")

    # Get tenant ID
    conn_resp = requests.get(
        XERO_CONNECTIONS_URL,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    if conn_resp.status_code != 200:
        print(f"❌ Failed to get tenant: {conn_resp.text}")
        sys.exit(1)

    connections = conn_resp.json()
    tenant_id = connections[0]["tenantId"] if connections else ""
    print(f"✓ Tenant ID: {tenant_id}")

    # Save
    creds["xero"]["refresh_token"] = tokens["refresh_token"]
    creds["xero"]["tenant_id"] = tenant_id

    with open(CONFIG_PATH, "w") as f:
        json.dump(creds, f, indent=2)

    cache_path = CONFIG_PATH.replace(".credentials.json", ".xero_token_cache.json")
    with open(cache_path, "w") as f:
        json.dump({"access_token": tokens["access_token"]}, f)

    print("\n" + "=" * 50)
    print("✅ SUCCESS! Xero connected.")
    print("=" * 50)


if __name__ == "__main__":
    main()
