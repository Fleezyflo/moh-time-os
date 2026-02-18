#!/usr/bin/env python3
"""
Isolated Directory API Auth Probe - Debug Script

Purpose: Diagnose exactly why Directory API users.get fails.
Outputs credential provenance, client_id verification, and full error details.
"""

import json
import os
import sys
from pathlib import Path

# Expected configuration (must match DWD setup)
EXPECTED_CLIENT_ID = "105570048371531373667"
SA_KEY_PATH = Path.home() / "Library/Application Support/gogcli/sa-bW9saGFtQGhybW55LmNv.json"
DELEGATED_SUBJECT = os.environ.get("DWD_SUBJECT", "molham@hrmny.co")
DIRECTORY_SCOPE = "https://www.googleapis.com/auth/admin.directory.user.readonly"


def main():
    print("=" * 80)
    print("DIRECTORY API AUTH PROBE - DIFFERENTIAL DIAGNOSIS")
    print("=" * 80)

    # =========================================================================
    # 1) CREDENTIAL IDENTITY
    # =========================================================================
    print("\n[1] CREDENTIAL IDENTITY")
    print("-" * 40)

    sa_key_path_abs = SA_KEY_PATH.resolve()
    print(f"  SA key path (code):     {SA_KEY_PATH}")
    print(f"  SA key path (resolved): {sa_key_path_abs}")
    print(f"  Key file exists:        {sa_key_path_abs.exists()}")

    if not sa_key_path_abs.exists():
        print(f"\n  ❌ ROOT CAUSE = key file does not exist at {sa_key_path_abs}")
        sys.exit(1)

    # Load and parse key
    try:
        with open(sa_key_path_abs) as f:
            sa_data = json.load(f)
    except Exception as e:
        print(f"\n  ❌ ROOT CAUSE = failed to parse SA key JSON: {e}")
        sys.exit(1)

    loaded_client_id = sa_data.get("client_id", "MISSING")
    loaded_client_email = sa_data.get("client_email", "MISSING")
    loaded_project_id = sa_data.get("project_id", "MISSING")
    loaded_private_key_id = (
        sa_data.get("private_key_id", "MISSING")[:16] + "..."
        if sa_data.get("private_key_id")
        else "MISSING"
    )

    print(f"  service_account_email:  {loaded_client_email}")
    print(f"  client_id (from key):   {loaded_client_id}")
    print(f"  project_id:             {loaded_project_id}")
    print(f"  private_key_id:         {loaded_private_key_id}")

    # =========================================================================
    # 2) CLIENT_ID VERIFICATION
    # =========================================================================
    print("\n[2] CLIENT_ID VERIFICATION")
    print("-" * 40)
    print(f"  Expected client_id:     {EXPECTED_CLIENT_ID}")
    print(f"  Loaded client_id:       {loaded_client_id}")

    if loaded_client_id != EXPECTED_CLIENT_ID:
        print("\n  ❌ ROOT CAUSE = wrong key/client_id")
        print(f"     Code expects client_id {EXPECTED_CLIENT_ID}")
        print(f"     But loaded key has client_id {loaded_client_id}")
        print(
            f"     FIX: Use the correct SA key file, or update DWD to authorize {loaded_client_id}"
        )
        sys.exit(1)
    else:
        print("  ✅ client_id MATCH confirmed")

    # =========================================================================
    # 3) DWD IMPERSONATION CHECK
    # =========================================================================
    print("\n[3] DWD IMPERSONATION")
    print("-" * 40)
    print(f"  Delegated subject:      {DELEGATED_SUBJECT}")

    if not DELEGATED_SUBJECT or DELEGATED_SUBJECT.strip() == "":
        print("\n  ❌ ROOT CAUSE = missing with_subject")
        print("     DWD requires .with_subject(<user_in_domain>)")
        sys.exit(1)
    else:
        print("  ✅ with_subject is set")

    # =========================================================================
    # 4) SCOPE CONFIGURATION
    # =========================================================================
    print("\n[4] SCOPE CONFIGURATION")
    print("-" * 40)
    print(f"  Directory scope:        {DIRECTORY_SCOPE}")
    print("  ✅ Scope string is correct")

    # =========================================================================
    # 5) CACHE/ENV CHECK
    # =========================================================================
    print("\n[5] CACHE/ENV CHECK")
    print("-" * 40)

    # Check for credential env vars that might override
    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"  GOOGLE_APPLICATION_CREDENTIALS: {gac or '(not set)'}")

    if gac and gac != str(sa_key_path_abs):
        print("  ⚠️  WARNING: GOOGLE_APPLICATION_CREDENTIALS is set to a different path")
        print(f"     This probe uses explicit path: {sa_key_path_abs}")

    print("  cache_discovery:        False (disabled)")
    print("  file_cache:             None (disabled)")

    # =========================================================================
    # 6) LIVE DIRECTORY API PROBE
    # =========================================================================
    print("\n[6] LIVE DIRECTORY API PROBE")
    print("-" * 40)
    print("  API:                    admin.directory_v1")
    print(f"  Method:                 users().get(userKey={DELEGATED_SUBJECT})")
    print(f"  Impersonating:          {DELEGATED_SUBJECT}")
    print()

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError

        # Build credentials explicitly from file (no env var override)
        credentials = service_account.Credentials.from_service_account_file(
            str(sa_key_path_abs),
            scopes=[DIRECTORY_SCOPE],
        )

        # Apply DWD impersonation
        credentials = credentials.with_subject(DELEGATED_SUBJECT)

        # Verify credential state
        print(f"  Credential type:        {type(credentials).__name__}")
        print(f"  Credential._subject:    {getattr(credentials, '_subject', 'N/A')}")
        print(f"  Credential.service_account_email: {credentials.service_account_email}")
        print()

        # Build service with no caching
        service = build(
            "admin",
            "directory_v1",
            credentials=credentials,
            cache_discovery=False,
        )

        print(f"  Executing: users().get(userKey={DELEGATED_SUBJECT})...")
        print()

        result = service.users().get(userKey=DELEGATED_SUBJECT).execute()

        # SUCCESS
        print("=" * 80)
        print("[DIR_AUTH_OK] status=200")
        print("=" * 80)
        print(f"  primaryEmail:           {result.get('primaryEmail')}")
        print(f"  id:                     {result.get('id')}")
        print(f"  orgUnitPath:            {result.get('orgUnitPath')}")
        print(f"  isAdmin:                {result.get('isAdmin')}")
        print()
        print("ROOT CAUSE = none (Directory API working)")

    except HttpError as e:
        print("=" * 80)
        print(f"[DIR_AUTH_FAIL] status={e.resp.status}")
        print("=" * 80)
        print(f"  HTTP status:            {e.resp.status}")
        print(f"  Reason:                 {e.reason if hasattr(e, 'reason') else 'N/A'}")

        # Parse error body
        try:
            error_body = json.loads(e.content.decode())
            print("  Error JSON:")
            print(json.dumps(error_body, indent=4))
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  Raw content:            {e.content.decode()[:500]}")

        print()
        # Differential diagnosis
        if e.resp.status == 403:
            print("DIFFERENTIAL DIAGNOSIS (403 Forbidden):")
            print("  Since client_id MATCHES and with_subject is set, possible causes:")
            print(
                "  1. DWD entry exists but scope list doesn't include admin.directory.user.readonly"
            )
            print("  2. DWD entry was recently added and hasn't propagated (wait 5-15 min)")
            print("  3. SA is disabled or deleted in GCP project")
            print("  4. Domain policy restricts this API")
            print()
            print("ROOT CAUSE = DWD scope not effective for this client_id (see above)")
        elif e.resp.status == 401:
            print("ROOT CAUSE = credential rejected (token invalid or SA disabled)")
        elif e.resp.status == 404:
            print(f"ROOT CAUSE = user {DELEGATED_SUBJECT} does not exist in domain")
        else:
            print(f"ROOT CAUSE = unexpected HTTP {e.resp.status}")

        sys.exit(1)

    except Exception as e:
        print("=" * 80)
        print("[DIR_AUTH_FAIL] status=N/A (pre-HTTP exception)")
        print("=" * 80)
        print(f"  Exception type:         {type(e).__name__}")
        print(f"  Exception message:      {str(e)[:500]}")
        print()

        error_str = str(e).lower()
        if "invalid_grant" in error_str:
            print("DIFFERENTIAL DIAGNOSIS (invalid_grant):")
            print("  This error occurs during OAuth token fetch, BEFORE the API call.")
            print("  The delegated subject is NOT a valid Workspace user principal.")
            print(f"  DWD_SUBJECT={DELEGATED_SUBJECT} is not a real user email.")
            print()
            print(
                f"ROOT CAUSE = Delegated subject is invalid (not a real Workspace user email): {DELEGATED_SUBJECT}"
            )
        elif "unauthorized_client" in error_str:
            print("DIFFERENTIAL DIAGNOSIS (unauthorized_client):")
            print("  This error occurs during OAuth token fetch, BEFORE the API call.")
            print("  Since client_id MATCHES and subject is set, the DWD scope is not authorized.")
            print()
            print("ROOT CAUSE = Directory DWD not authorized")
        elif "access_denied" in error_str:
            print("ROOT CAUSE = access_denied (SA not authorized to impersonate subject)")
        else:
            print(f"ROOT CAUSE = unexpected exception: {type(e).__name__}")

        sys.exit(1)


if __name__ == "__main__":
    main()
