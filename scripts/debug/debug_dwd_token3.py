"""
debug_dwd_token3.py

Purpose:
- Prove DWD token minting works for a known-working scope (gmail.readonly)
- Prove whether DWD token minting works for Directory scope (admin.directory.user.readonly)
- Print credential provenance + key JWT claims (iss/sub/aud/scope/iat/exp) without printing the raw JWT
- Optionally attempt an actual Directory users.get ONLY if token mint succeeds

Run:
  uv run python -m lib.collectors.debug_dwd_token3
  DWD_SUBJECT=someone@hrmny.co uv run python -m lib.collectors.debug_dwd_token3
  SA_KEY_PATH=".../sa-xxxx.json" uv run python -m lib.collectors.debug_dwd_token3
  DO_DIR_HTTP=1 uv run python -m lib.collectors.debug_dwd_token3
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DIRECTORY_SCOPE = "https://www.googleapis.com/auth/admin.directory.user.readonly"

DEFAULT_SUBJECT = "molham@hrmny.co"
DEFAULT_SA_KEY_PATH = (
    Path.home() / "Library" / "Application Support" / "gogcli" / "sa-bW9saGFtQGhybW55LmNv.json"
)

EXPECTED_CLIENT_ID = "105570048371531373667"


def _b64url_decode(seg: str) -> bytes:
    seg += "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg.encode("utf-8"))


def decode_jwt_header_payload(jwt_str: str) -> dict[str, Any]:
    parts = jwt_str.split(".")
    if len(parts) < 2:
        return {"error": "not_a_jwt"}
    header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
    payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    return {"header": header, "payload": payload}


def load_sa_path() -> Path:
    # Prefer explicit override for determinism.
    env = os.environ.get("SA_KEY_PATH")
    if env:
        return Path(env).expanduser()

    return DEFAULT_SA_KEY_PATH


def read_sa_client_id(sa_path: Path) -> str:
    data = json.loads(sa_path.read_text())
    # In SA keyfiles, client_id is the OAuth2 client ID used for DWD config.
    return str(data.get("client_id", ""))


def print_identity(sa_path: Path, subject: str) -> None:
    sa_client_id = read_sa_client_id(sa_path)
    sa_email = json.loads(sa_path.read_text()).get("client_email")

    print("=" * 70)
    print("[CREDENTIAL IDENTITY]")
    print("-" * 70)
    print(f"SA key path:        {sa_path}")
    print(f"SA email:           {sa_email}")
    print(f"SA client_id:       {sa_client_id}")
    print(f"EXPECTED client_id: {EXPECTED_CLIENT_ID}")
    print(f"client_id_match:    {sa_client_id == EXPECTED_CLIENT_ID}")
    print(f"Delegated subject:  {subject}")
    print(
        f"GOOGLE_APPLICATION_CREDENTIALS set: {bool(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))}"
    )
    print("=" * 70)


def try_refresh(sa_path: Path, subject: str, scope: str) -> tuple[bool, str]:
    print("=" * 70)
    print(f"[TOKEN MINT PROBE] scope={scope}")
    print("-" * 70)

    creds = service_account.Credentials.from_service_account_file(
        str(sa_path),
        scopes=[scope],
    ).with_subject(subject)

    token_uri = getattr(creds, "token_uri", getattr(creds, "_token_uri", None))
    print(f"token_uri:          {token_uri}")
    print(f"issuer (iss):       {creds.service_account_email}")
    print(f"subject (sub):      {subject}")

    # Decode JWT claims for auditing without printing raw JWT.
    try:
        jwt_bytes_or_str = creds._make_authorization_grant_assertion()
        jwt_str = (
            jwt_bytes_or_str.decode("utf-8")
            if isinstance(jwt_bytes_or_str, (bytes, bytearray))
            else str(jwt_bytes_or_str)
        )
        decoded = decode_jwt_header_payload(jwt_str)
        pld = decoded.get("payload", {})
        show = {k: pld.get(k) for k in ["iss", "sub", "aud", "scope", "iat", "exp"]}
        print("jwt_claims:         " + json.dumps(show, ensure_ascii=False))
        if isinstance(pld.get("iat"), (int, float)) and isinstance(pld.get("exp"), (int, float)):
            print(f"iat->exp seconds:   {int(pld['exp'] - pld['iat'])}")
    except Exception as e:
        print("[JWT] decode failed:", repr(e))

    try:
        creds.refresh(Request())
        print("[RESULT] SUCCESS")
        print(f"token_present:      {bool(creds.token)}")
        print(f"expiry:             {creds.expiry}")
        print("=" * 70 + "\n")
        return True, "ok"
    except Exception as e:
        print("[RESULT] FAIL")
        print(f"exc_type:           {type(e).__name__}")
        print(f"exc_repr:           {repr(e)}")
        if getattr(e, "args", None):
            print(f"exc_args:           {e.args}")
        print("=" * 70 + "\n")
        return False, type(e).__name__


def directory_users_get(sa_path: Path, subject: str) -> None:
    print("=" * 70)
    print("[DIRECTORY HTTP PROBE] users.get(userKey=<subject>)")
    print("-" * 70)

    creds = service_account.Credentials.from_service_account_file(
        str(sa_path),
        scopes=[DIRECTORY_SCOPE],
    ).with_subject(subject)

    svc = build("admin", "directory_v1", credentials=creds, cache_discovery=False)
    user = svc.users().get(userKey=subject).execute()

    # Print only a few fields.
    out = {k: user.get(k) for k in ["primaryEmail", "id", "orgUnitPath", "suspended"]}
    print("OK users.get:", json.dumps(out, indent=2, ensure_ascii=False))
    print("=" * 70 + "\n")


def main() -> None:
    subject = os.environ.get("DWD_SUBJECT", DEFAULT_SUBJECT)
    sa_path = load_sa_path()

    if not sa_path.exists():
        print(f"ERROR: SA key file not found at {sa_path}", file=sys.stderr)
        sys.exit(2)

    print_identity(sa_path, subject)

    ok_gmail, _ = try_refresh(sa_path, subject, GMAIL_SCOPE)
    ok_dir, _ = try_refresh(sa_path, subject, DIRECTORY_SCOPE)

    # Optional: prove actual Directory API call works, but ONLY if token mint succeeded.
    if os.environ.get("DO_DIR_HTTP") == "1":
        if not ok_dir:
            print(
                "SKIP Directory HTTP probe because Directory token mint failed (unauthorized_client/etc)."
            )
            sys.exit(1)
        directory_users_get(sa_path, subject)

    # Exit non-zero if Directory mint fails (so CI/scripts can detect).
    if not ok_gmail:
        sys.exit(1)
    if not ok_dir:
        sys.exit(1)


if __name__ == "__main__":
    main()
