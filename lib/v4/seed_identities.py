"""
Time OS V4 - Seed Identities from Existing Tables

Populates identity_profiles and identity_claims from:
- clients table (creates org profiles)
- people table (creates person profiles)

Run: python3 -m lib.v4.seed_identities
"""

import json
import logging
import os
import sqlite3

from .identity_service import get_identity_service

logger = logging.getLogger(__name__)


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")


def seed_identities_from_clients():
    """Create org identity profiles from clients table."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    ident = get_identity_service()

    stats = {"created": 0, "skipped": 0, "errors": 0}

    try:
        cursor.execute("""
            SELECT id, name, aliases_json, xero_contact_id
            FROM clients WHERE name IS NOT NULL
        """)

        for row in cursor.fetchall():
            client_id, name, aliases_json, xero_id = row

            try:
                # Create org profile
                result = ident.create_profile(
                    profile_type="org",
                    canonical_name=name,
                    metadata={"client_id": client_id, "source": "clients_table"},
                )
                profile_id = result["profile_id"]

                # Add domain claim if available (extract from name or xero_id)
                # Add alias claims
                aliases = json.loads(aliases_json or "[]")
                for alias in aliases:
                    ident.add_claim(profile_id, "alias_name", alias, "clients_table", 0.95)

                # Add xero claim if available
                if xero_id:
                    ident.add_claim(profile_id, "xero_id", xero_id, "xero", 0.99)

                # Update client table with identity_profile_id
                cursor.execute(
                    "UPDATE clients SET identity_profile_id = ? WHERE id = ?",
                    (profile_id, client_id),
                )

                stats["created"] += 1
                logger.info(f"  ✓ Created org profile: {name}")
            except Exception as e:
                stats["errors"] += 1
                logger.info(f"  ✗ Error for {name}: {e}")
        conn.commit()
        return stats

    finally:
        conn.close()


def seed_identities_from_people():
    """Create person identity profiles from people table."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cursor = conn.cursor()
    ident = get_identity_service()

    stats = {"created": 0, "skipped": 0, "linked": 0, "errors": 0}

    try:
        cursor.execute("""
            SELECT id, name, email, phone, client_id, asana_user_id
            FROM people WHERE name IS NOT NULL
        """)

        for row in cursor.fetchall():
            person_id, name, email, phone, client_id, asana_id = row

            try:
                # Check if profile already exists via email
                if email:
                    existing = ident.resolve_identity("email", email, create_if_missing=False)
                    if existing and not existing.get("auto_created"):
                        # Already have a profile
                        stats["skipped"] += 1
                        continue

                # Create person profile
                result = ident.create_profile(
                    profile_type="person",
                    canonical_name=name,
                    canonical_email=email,
                    metadata={
                        "people_id": person_id,
                        "client_id": client_id,
                        "source": "people_table",
                    },
                )
                profile_id = result["profile_id"]

                # Add email claim
                if email:
                    ident.add_claim(profile_id, "email", email, "people_table", 0.99)

                # Add phone claim
                if phone:
                    ident.add_claim(profile_id, "phone", phone, "people_table", 0.9)

                # Add asana claim
                if asana_id:
                    ident.add_claim(profile_id, "asana_id", asana_id, "asana", 0.99)

                # Update people table with identity_profile_id
                cursor.execute(
                    "UPDATE people SET identity_profile_id = ? WHERE id = ?",
                    (profile_id, person_id),
                )

                # Link to client profile if available
                if client_id:
                    cursor.execute(
                        "SELECT identity_profile_id FROM clients WHERE id = ?",
                        (client_id,),
                    )
                    client_row = cursor.fetchone()
                    if client_row and client_row[0]:
                        # Could create a relationship here
                        stats["linked"] += 1

                stats["created"] += 1
                logger.info(f"  ✓ Created person profile: {name}")
            except Exception as e:
                stats["errors"] += 1
                logger.info(f"  ✗ Error for {name}: {e}")
        conn.commit()
        return stats

    finally:
        conn.close()


def main():
    logger.info("=" * 60)
    logger.info("SEEDING IDENTITY PROFILES FROM EXISTING DATA")
    logger.info("=" * 60)
    logger.info("\n🏢 Seeding from clients table...")
    client_stats = seed_identities_from_clients()
    logger.info(f"   Created: {client_stats['created']}, Errors: {client_stats['errors']}")
    logger.info("\n👤 Seeding from people table...")
    people_stats = seed_identities_from_people()
    logger.info(
        f"   Created: {people_stats['created']}, Skipped: {people_stats['skipped']}, Linked: {people_stats['linked']}"
    )

    logger.info("\n" + "=" * 60)
    logger.info("SEEDING COMPLETE")
    # Show final stats
    ident = get_identity_service()
    stats = ident.get_stats()
    logger.info(f"\nTotal Profiles: {stats['active_profiles']}")
    logger.info(f"  Persons: {stats['by_type'].get('person', 0)}")
    logger.info(f"  Orgs: {stats['by_type'].get('org', 0)}")
    logger.info(f"Total Claims: {stats['active_claims']}")


if __name__ == "__main__":
    main()
