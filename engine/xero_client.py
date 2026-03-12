"""Xero API client with OAuth2 refresh token flow.

Credentials: reads XERO_CLIENT_ID, XERO_CLIENT_SECRET, XERO_REFRESH_TOKEN,
XERO_TENANT_ID env vars first, falls back to config/.credentials.json.
Token cache still uses .xero_token_cache.json for the rotating access token.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", ".credentials.json")
TOKEN_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "config", ".xero_token_cache.json")

XERO_OAUTH_ENDPOINT = "https://identity.xero.com/connect/token"
XERO_API_BASE = "https://api.xero.com/api.xro/2.0"

logger = logging.getLogger(__name__)


@dataclass
class XeroCredentials:
    client_id: str
    client_secret: str
    refresh_token: str
    tenant_id: str
    access_token: str | None = None


def _load_from_env() -> XeroCredentials | None:
    """Try loading Xero credentials from environment variables."""
    client_id = os.environ.get("XERO_CLIENT_ID")
    client_secret = os.environ.get("XERO_CLIENT_SECRET")
    refresh_token = os.environ.get("XERO_REFRESH_TOKEN")
    tenant_id = os.environ.get("XERO_TENANT_ID")

    if all([client_id, client_secret, refresh_token, tenant_id]):
        # Still check token cache for access token
        access_token = None
        if os.path.exists(TOKEN_CACHE_PATH):
            try:
                with open(TOKEN_CACHE_PATH) as f:
                    cache = json.load(f)
                    access_token = cache.get("access_token")
            except (OSError, json.JSONDecodeError):
                logger.debug("Token cache read failed", exc_info=True)

        return XeroCredentials(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            tenant_id=tenant_id,
            access_token=access_token,
        )
    return None


def load_credentials() -> XeroCredentials:
    """Load Xero credentials from env vars, falling back to credentials file."""
    env_creds = _load_from_env()
    if env_creds:
        return env_creds

    try:
        with open(_CONFIG_PATH) as f:
            data = json.load(f)
        xero = data["xero"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(
            "Xero credentials not found. Set XERO_CLIENT_ID/XERO_CLIENT_SECRET/"
            "XERO_REFRESH_TOKEN/XERO_TENANT_ID env vars or populate config/.credentials.json"
        ) from e

    # Check for cached access token
    access_token = None
    if os.path.exists(TOKEN_CACHE_PATH):
        try:
            with open(TOKEN_CACHE_PATH) as f:
                cache = json.load(f)
                access_token = cache.get("access_token")
        except (OSError, json.JSONDecodeError):
            logger.debug("Token cache read failed", exc_info=True)

    return XeroCredentials(
        client_id=xero["client_id"],
        client_secret=xero["client_secret"],
        refresh_token=xero["refresh_token"],
        tenant_id=xero["tenant_id"],
        access_token=access_token,
    )


def save_tokens(access_token: str, refresh_token: str) -> None:
    """Save tokens to cache and update refresh token in credentials.

    Access token always cached to .xero_token_cache.json.
    Refresh token written back to .credentials.json only if using file-based creds.
    When using env vars, the rotated refresh token is logged as a warning so
    the operator can update the env var.
    """
    # Save access token to cache
    os.makedirs(os.path.dirname(TOKEN_CACHE_PATH), exist_ok=True)
    with open(TOKEN_CACHE_PATH, "w") as f:
        json.dump({"access_token": access_token}, f)

    # Update refresh token — file-based or env-var mode
    if os.environ.get("XERO_REFRESH_TOKEN"):
        # Env var mode: can't write back, warn operator
        if refresh_token != os.environ.get("XERO_REFRESH_TOKEN"):
            logger.warning(
                "Xero refresh token rotated. Update XERO_REFRESH_TOKEN env var to avoid re-auth.",
            )
    else:
        # File-based mode: update credentials file
        try:
            with open(_CONFIG_PATH) as f:
                data = json.load(f)
            data["xero"]["refresh_token"] = refresh_token
            with open(_CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("Failed to save rotated refresh token: %s", e)


def refresh_access_token(creds: XeroCredentials) -> str:
    """Use refresh token to get new access token."""
    resp = httpx.post(
        XERO_OAUTH_ENDPOINT,
        data={
            "grant_type": "refresh_token",
            "refresh_token": creds.refresh_token,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Token refresh failed: {resp.status_code} {resp.text}")

    tokens = resp.json()
    access_token = tokens["access_token"]
    new_refresh_token = tokens.get("refresh_token", creds.refresh_token)

    save_tokens(access_token, new_refresh_token)
    return access_token


def get_access_token() -> tuple[str, str]:
    """Get valid access token and tenant_id, refreshing if needed."""
    creds = load_credentials()

    # Always refresh to ensure valid token (they expire in 30 min)
    access_token = refresh_access_token(creds)
    return access_token, creds.tenant_id


def xero_get(endpoint: str) -> dict[str, Any]:
    """Make authenticated GET request to Xero API."""
    access_token, tenant_id = get_access_token()

    url = f"{XERO_API_BASE}/{endpoint}"
    resp = httpx.get(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Xero-Tenant-Id": tenant_id,
            "Accept": "application/json",
        },
        timeout=30,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Xero API error: {resp.status_code} {resp.text}")

    return resp.json()


def list_contacts(
    *, is_customer: bool | None = None, is_supplier: bool | None = None
) -> list[dict]:
    """List contacts from Xero."""
    endpoint = "Contacts"
    params = []
    if is_customer is not None:
        params.append(f"IsCustomer=={str(is_customer).lower()}")
    if is_supplier is not None:
        params.append(f"IsSupplier=={str(is_supplier).lower()}")

    if params:
        endpoint += "?where=" + " AND ".join(params)

    data = xero_get(endpoint)
    return data.get("Contacts", [])


def list_invoices(*, status: str | None = None) -> list[dict]:
    """List invoices. Status: DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED."""
    endpoint = "Invoices"
    if status:
        endpoint += f'?where=Status=="{status}"'

    data = xero_get(endpoint)
    return data.get("Invoices", [])


def list_bills(*, status: str | None = None) -> list[dict]:
    """List bills (accounts payable). Filter by status."""
    endpoint = 'Invoices?where=Type=="ACCPAY"'
    if status:
        endpoint += f' AND Status=="{status}"'

    data = xero_get(endpoint)
    return data.get("Invoices", [])


def get_aged_receivables() -> dict:
    """Get aged receivables report."""
    return xero_get("Reports/AgedReceivablesByContact")


def get_aged_payables() -> dict:
    """Get aged payables report."""
    return xero_get("Reports/AgedPayablesByContact")


def list_credit_notes(*, status: str | None = None) -> list[dict]:
    """List credit notes. Status: DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED."""
    endpoint = "CreditNotes"
    if status:
        endpoint += f'?where=Status=="{status}"'

    data = xero_get(endpoint)
    return data.get("CreditNotes", [])


def list_bank_transactions(*, status: str | None = None) -> list[dict]:
    """List bank transactions. Status: DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED."""
    endpoint = "BankTransactions"
    if status:
        endpoint += f'?where=Status=="{status}"'

    data = xero_get(endpoint)
    return data.get("BankTransactions", [])


def list_tax_rates() -> list[dict]:
    """List all tax rates."""
    data = xero_get("TaxRates")
    return data.get("TaxRates", [])


if __name__ == "__main__":
    # Test connection
    print("Testing Xero connection...")
    try:
        contacts = list_contacts(is_customer=True)
        print(f"✓ Connected! Found {len(contacts)} customers")
        for c in contacts[:5]:
            print(f"  - {c.get('Name')}")
    except Exception as e:
        print(f"✗ Error: {e}")
