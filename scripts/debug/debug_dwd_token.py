from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account

EXPECTED_CLIENT_ID = "105570048371531373667"
DIRECTORY_SCOPE = "https://www.googleapis.com/auth/admin.directory.user.readonly"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def _b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("utf-8"))


def decode_jwt_header_payload(jwt: str) -> dict:
    parts = jwt.split(".")
    if len(parts) < 2:
        return {"error": "not a jwt"}
    hdr = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
    pld = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    # redact anything sensitive-ish (there shouldn't be)
    return {"header": hdr, "payload": pld}


def load_sa_path() -> Path:
    # Prefer an explicit env var if you have it; otherwise fall back to your known path pattern.
    env = os.environ.get("SA_KEY_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"


def print_identity(sa_path: Path, subject: str):
    info = json.loads(sa_path.read_text())
    sa_email = info.get("client_email")
    sa_client_id = info.get("client_id")
    print("======================================================================")
    print("[CREDENTIAL IDENTITY]")
    print("----------------------------------------------------------------------")
    print(f"SA key path:       {sa_path}")
    print(f"SA email:          {sa_email}")
    print(f"SA client_id:      {sa_client_id}")
    print(f"EXPECTED client_id:{EXPECTED_CLIENT_ID}")
    print(f"client_id_match:   {str(sa_client_id) == EXPECTED_CLIENT_ID}")
    print(f"Delegated subject: {subject}")
    print(
        f"GOOGLE_APPLICATION_CREDENTIALS set: {bool(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))}"
    )
    print("======================================================================")


def try_refresh(sa_path: Path, subject: str, scope: str):
    print("======================================================================")
    print(f"[TOKEN MINT PROBE] scope={scope}")
    print("----------------------------------------------------------------------")
    creds = service_account.Credentials.from_service_account_file(
        str(sa_path),
        scopes=[scope],
    ).with_subject(subject)

    print(f"token_uri:         {getattr(creds, 'token_uri', getattr(creds, '_token_uri', None))}")
    print(f"issuer (iss):      {creds.service_account_email}")
    print(f"subject (sub):     {subject}")
    # Build the signed JWT *without* printing it; decode header/payload for auditing.
    # This uses internal method; ok for debug.
    jwt = creds._make_authorization_grant_assertion()
    decoded = decode_jwt_header_payload(
        jwt.decode("utf-8") if isinstance(jwt, (bytes, bytearray)) else jwt
    )
    pld = decoded.get("payload", {})
    # Show only key claims
    show = {k: pld.get(k) for k in ["iss", "sub", "aud", "scope", "iat", "exp"]}
    print("jwt_claims:        " + json.dumps(show, ensure_ascii=False))
    if isinstance(pld.get("iat"), (int, float)) and isinstance(pld.get("exp"), (int, float)):
        print(f"iat->exp seconds:  {int(pld['exp'] - pld['iat'])}")

    try:
        creds.refresh(Request())
        print("[RESULT] SUCCESS")
        print(f"token_present:     {bool(creds.token)}")
        print(f"expiry:            {creds.expiry}")
    except Exception as e:
        print("[RESULT] FAIL")
        print(f"exc_type:          {type(e).__name__}")
        print(f"exc_repr:          {repr(e)}")
        # google-auth exceptions often have .args with embedded JSON dict
        if getattr(e, "args", None):
            print(f"exc_args:          {e.args}")
        print(
            "TIP: If gmail succeeds and directory fails with same iss/sub/aud, it's almost certainly DWD scope list mismatch."
        )
    print("======================================================================\n")


def main():
    subject = os.environ.get("DWD_SUBJECT", "molham@hrmny.co")
    sa_path = load_sa_path()
    if not sa_path.exists():
        print(f"ERROR: SA key file not found at {sa_path}", file=sys.stderr)
        sys.exit(2)

    print_identity(sa_path, subject)
    # Compare a known-working scope vs Directory scope
    try_refresh(sa_path, subject, GMAIL_SCOPE)
    try_refresh(sa_path, subject, DIRECTORY_SCOPE)


if __name__ == "__main__":
    main()
