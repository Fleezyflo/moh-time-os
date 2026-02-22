"""
Centralized configuration for MOH TIME OS.

All hardcoded values that vary by deployment belong here.
Override via environment variables where marked.
"""

import os

# ============================================================
# Identity / Email
# ============================================================

ADMIN_EMAIL: str = os.environ.get("MOH_ADMIN_EMAIL", "molham@hrmny.co")
"""Primary admin email — used for Google API delegation and GOG CLI."""

COMPANY_DOMAIN: str = os.environ.get("MOH_COMPANY_DOMAIN", "hrmny.co")
"""Primary company domain for internal vs external classification."""

INTERNAL_DOMAINS: list[str] = os.environ.get("MOH_INTERNAL_DOMAINS", "hrmny.co,hrmny.ae").split(",")
"""All internal email domains — emails from these are classified as internal."""

OUR_EMAIL_DOMAINS: list[str] = os.environ.get(
    "MOH_OUR_EMAIL_DOMAINS", "hrmny.co,hrmny.ae,harmonydigital.co"
).split(",")
"""All domains we send email from — used for direction detection."""

# ============================================================
# Asana
# ============================================================

ASANA_WORKSPACE_NAME: str = os.environ.get("MOH_ASANA_WORKSPACE", "hrmny.co")
"""Asana workspace name for project sync."""
