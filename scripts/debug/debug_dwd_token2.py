import base64
import json
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2 import service_account

EXPECTED_CLIENT_ID = "105570048371531373667"

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DIRECTORY_SCOPE = "https://www.googleapis.com/auth/admin.directory.user.readonly"


def load_sa_path() -> Path:
    # Keep identical behavior to your existing script: default to gogcli path
    # Adjust if you already have a better canonical loader.
    p = Path.home() / "Library" / "Application Support" / "gogcli"
    # Your observed filename format: sa-bW9saGFtQGhybW55LmNv.json
    # If multiple exist, pick the first.
    matches = sorted(p.glob("sa-*.json"))
    if not matches:
        return p / "sa.json"
    return matches[0]


def b64url_decode(s: str) -> str:
    s += "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s.encode("utf-8")).decode("utf-8")


def decode_jwt_header_payload(jwt: str) -> dict:
    parts = jwt.split(".")
    if len(parts) < 2:
        return {}
    hdr = json.loads(b64url_decode(parts[0]))
    pld = json.loads(b64url_decode(parts[1]))
    return {"header": hdr, "payload": pld}


def print_identity(sa_path: Path, subject: str):
    data = json.loads(sa_path.read_text())
    sa_email = data.get("client_email")
    sa_client_id = str(data.get("client_id"))
    print("======================================================================")
    print("[CREDENTIAL IDENTITY]")
    print("----------------------------------------------------------------------")
    print(f"SA key path:       {sa_path}")
    print(f"SA email:          {sa_email}")
    print(f"SA client_id:      {sa_client_id}")
    print(f"EXPECTED client_id:{EXPECTED_CLIENT_ID}")
    print(f"client_id_match:   {sa_client_id == EXPECTED_CLIENT_ID}")
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

    token_uri = getattr(creds, "token_uri", getattr(creds, "_token_uri", None))
    print(f"token_uri:         {token_uri}")
    print(f"issuer (iss):      {creds.service_account_email}")
    print(f"subject (sub):     {subject}")

    # Signed JWT assertion (do not print raw JWT); decode key claims for auditing.
    jwt = creds._make_authorization_grant_assertion()
    jwt_str = jwt.decode("utf-8") if isinstance(jwt, (bytes, bytearray)) else jwt
    decoded = decode_jwt_header_payload(jwt_str)
    pld = decoded.get("payload", {})
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
        if getattr(e, "args", None):
            print(f"exc_args:          {e.args}")
    print("======================================================================\n")


def main():
    subject = os.environ.get("DWD_SUBJECT", "molham@hrmny.co")
    sa_path = load_sa_path()
    if not sa_path.exists():
        print(f"ERROR: SA key file not found at {sa_path}", file=sys.stderr)
        sys.exit(2)

    print_identity(sa_path, subject)
    try_refresh(sa_path, subject, GMAIL_SCOPE)
    try_refresh(sa_path, subject, DIRECTORY_SCOPE)


if __name__ == "__main__":
    main()
