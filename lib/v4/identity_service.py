"""
Time OS V4 - Identity Service

Handles identity resolution: profiles, claims, and merge/split operations.
Ensures consistent identity across all artifacts and entities.
"""

import json
import os
import re
import sqlite3
import uuid
from typing import Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "moh_time_os.db")


class IdentityService:
    """Service for identity resolution and management."""

    CLAIM_TYPES = {
        "email",
        "domain",
        "chat_handle",
        "calendar_id",
        "asana_id",
        "phone",
        "alias_name",
        "xero_id",
    }

    PROFILE_TYPES = {"person", "org"}

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30)

    def _generate_id(self, prefix: str = "idp") -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    def _normalize_value(self, claim_type: str, value: str) -> str:
        """Normalize a claim value for consistent lookup."""
        value = value.strip().lower()

        if claim_type == "email":
            # Normalize email
            value = value.lower().strip()
        elif claim_type == "domain":
            # Remove www. and trailing slashes
            value = re.sub(r"^(https?://)?www\.", "", value)
            value = value.rstrip("/")
        elif claim_type == "phone":
            # Remove non-digits
            value = re.sub(r"[^\d+]", "", value)

        return value

    def _extract_domain_from_email(self, email: str) -> str | None:
        """Extract domain from email address."""
        if "@" in email:
            return email.split("@")[1].lower()
        return None

    # ===========================================
    # Profile Management
    # ===========================================

    def create_profile(
        self,
        profile_type: str,
        canonical_name: str,
        canonical_email: str | None = None,
        canonical_domain: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        Create a new identity profile.

        Args:
            profile_type: 'person' or 'org'
            canonical_name: Primary name for this identity
            canonical_email: Primary email (for persons)
            canonical_domain: Primary domain (for orgs)
            metadata: Additional attributes

        Returns:
            Created profile record
        """
        if profile_type not in self.PROFILE_TYPES:
            raise ValueError(f"Invalid profile_type: {profile_type}")

        profile_id = self._generate_id("idp")

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO identity_profiles
                (profile_id, profile_type, canonical_name, canonical_email,
                 canonical_domain, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
                (
                    profile_id,
                    profile_type,
                    canonical_name,
                    canonical_email,
                    canonical_domain,
                    json.dumps(metadata or {}),
                ),
            )

            conn.commit()
            return {
                "profile_id": profile_id,
                "profile_type": profile_type,
                "canonical_name": canonical_name,
                "status": "created",
            }
        finally:
            conn.close()

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Get a profile by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT profile_id, profile_type, canonical_name, canonical_email,
                       canonical_domain, status, metadata, created_at, updated_at
                FROM identity_profiles WHERE profile_id = ?
            """,
                (profile_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "profile_id": row[0],
                "profile_type": row[1],
                "canonical_name": row[2],
                "canonical_email": row[3],
                "canonical_domain": row[4],
                "status": row[5],
                "metadata": json.loads(row[6] or "{}"),
                "created_at": row[7],
                "updated_at": row[8],
            }
        finally:
            conn.close()

    def find_profiles(
        self,
        profile_type: str | None = None,
        name_contains: str | None = None,
        status: str = "active",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search for profiles."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            query = """
                SELECT profile_id, profile_type, canonical_name, canonical_email,
                       canonical_domain, status, created_at
                FROM identity_profiles WHERE status = ?
            """
            params = [status]

            if profile_type:
                query += " AND profile_type = ?"
                params.append(profile_type)
            if name_contains:
                query += " AND canonical_name LIKE ?"
                params.append(f"%{name_contains}%")

            query += " ORDER BY canonical_name LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [
                {
                    "profile_id": row[0],
                    "profile_type": row[1],
                    "canonical_name": row[2],
                    "canonical_email": row[3],
                    "canonical_domain": row[4],
                    "status": row[5],
                    "created_at": row[6],
                }
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    # ===========================================
    # Claim Management
    # ===========================================

    def add_claim(
        self,
        profile_id: str,
        claim_type: str,
        claim_value: str,
        source: str,
        confidence: float = 1.0,
        source_artifact_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Add a claim to a profile.

        Args:
            profile_id: Profile to add claim to
            claim_type: Type of claim (email, domain, etc.)
            claim_value: The claim value
            source: Source system
            confidence: Confidence level 0-1
            source_artifact_id: Optional artifact reference

        Returns:
            Created or existing claim
        """
        if claim_type not in self.CLAIM_TYPES:
            raise ValueError(f"Invalid claim_type: {claim_type}")

        normalized = self._normalize_value(claim_type, claim_value)
        claim_id = self._generate_id("clm")

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Check if claim already exists
            cursor.execute(
                """
                SELECT claim_id, profile_id, confidence
                FROM identity_claims
                WHERE claim_type = ? AND claim_value_normalized = ? AND status = 'active'
            """,
                (claim_type, normalized),
            )

            existing = cursor.fetchone()
            if existing:
                if existing[1] == profile_id:
                    # Same profile, maybe update confidence
                    if confidence > existing[2]:
                        cursor.execute(
                            """
                            UPDATE identity_claims SET confidence = ?
                            WHERE claim_id = ?
                        """,
                            (confidence, existing[0]),
                        )
                        conn.commit()
                    return {
                        "claim_id": existing[0],
                        "status": "existing",
                        "profile_id": profile_id,
                    }
                # Different profile - conflict!
                return {
                    "status": "conflict",
                    "existing_claim_id": existing[0],
                    "existing_profile_id": existing[1],
                    "requested_profile_id": profile_id,
                }

            # Create new claim
            cursor.execute(
                """
                INSERT INTO identity_claims
                (claim_id, profile_id, claim_type, claim_value, claim_value_normalized,
                 source, source_artifact_id, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
                (
                    claim_id,
                    profile_id,
                    claim_type,
                    claim_value,
                    normalized,
                    source,
                    source_artifact_id,
                    confidence,
                ),
            )

            conn.commit()
            return {"claim_id": claim_id, "status": "created", "profile_id": profile_id}

        finally:
            conn.close()

    def get_claims_for_profile(self, profile_id: str) -> list[dict[str, Any]]:
        """Get all claims for a profile."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT claim_id, claim_type, claim_value, source, confidence, status, created_at
                FROM identity_claims WHERE profile_id = ? AND status = 'active'
            """,
                (profile_id,),
            )

            return [
                {
                    "claim_id": row[0],
                    "claim_type": row[1],
                    "claim_value": row[2],
                    "source": row[3],
                    "confidence": row[4],
                    "status": row[5],
                    "created_at": row[6],
                }
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    # ===========================================
    # Resolution (Lookup)
    # ===========================================

    def resolve_identity(
        self,
        claim_type: str,
        claim_value: str,
        create_if_missing: bool = False,
        source: str = "system",
    ) -> dict[str, Any] | None:
        """
        Resolve a claim to an identity profile.

        Args:
            claim_type: Type of claim
            claim_value: Value to look up
            create_if_missing: Auto-create profile if not found
            source: Source for auto-creation

        Returns:
            Profile dict or None
        """
        normalized = self._normalize_value(claim_type, claim_value)

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Look up claim
            cursor.execute(
                """
                SELECT c.profile_id, c.confidence, p.canonical_name, p.profile_type, p.status
                FROM identity_claims c
                JOIN identity_profiles p ON c.profile_id = p.profile_id
                WHERE c.claim_type = ? AND c.claim_value_normalized = ?
                AND c.status = 'active' AND p.status = 'active'
                ORDER BY c.confidence DESC
                LIMIT 1
            """,
                (claim_type, normalized),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "profile_id": row[0],
                    "confidence": row[1],
                    "canonical_name": row[2],
                    "profile_type": row[3],
                    "status": row[4],
                    "matched_by": claim_type,
                }

            # Try secondary resolution for emails (domain -> org)
            if claim_type == "email" and create_if_missing:
                domain = self._extract_domain_from_email(claim_value)
                if domain:
                    cursor.execute(
                        """
                        SELECT c.profile_id, c.confidence, p.canonical_name, p.profile_type
                        FROM identity_claims c
                        JOIN identity_profiles p ON c.profile_id = p.profile_id
                        WHERE c.claim_type = 'domain' AND c.claim_value_normalized = ?
                        AND c.status = 'active' AND p.status = 'active'
                    """,
                        (domain,),
                    )

                    org_row = cursor.fetchone()
                    if org_row:
                        # Found org by domain - create person profile
                        person_name = claim_value.split("@")[0].replace(".", " ").title()
                        result = self.create_profile(
                            profile_type="person",
                            canonical_name=person_name,
                            canonical_email=claim_value.lower(),
                            metadata={
                                "auto_created": True,
                                "org_profile_id": org_row[0],
                            },
                        )
                        self.add_claim(result["profile_id"], "email", claim_value, source, 0.9)
                        return {
                            "profile_id": result["profile_id"],
                            "confidence": 0.9,
                            "canonical_name": person_name,
                            "profile_type": "person",
                            "status": "active",
                            "matched_by": "domain_inference",
                            "auto_created": True,
                        }

            if create_if_missing:
                # Create new profile
                name = claim_value
                profile_type = "person"

                if claim_type == "email":
                    name = claim_value.split("@")[0].replace(".", " ").title()
                elif claim_type == "domain":
                    name = claim_value.split(".")[0].title()
                    profile_type = "org"

                result = self.create_profile(
                    profile_type=profile_type,
                    canonical_name=name,
                    canonical_email=claim_value if claim_type == "email" else None,
                    canonical_domain=claim_value if claim_type == "domain" else None,
                    metadata={"auto_created": True},
                )
                self.add_claim(result["profile_id"], claim_type, claim_value, source, 0.7)

                return {
                    "profile_id": result["profile_id"],
                    "confidence": 0.7,
                    "canonical_name": name,
                    "profile_type": profile_type,
                    "status": "active",
                    "matched_by": "auto_create",
                    "auto_created": True,
                }

            return None

        finally:
            conn.close()

    # ===========================================
    # Merge/Split Operations
    # ===========================================

    def merge_profiles(
        self, from_profile_ids: list[str], to_profile_id: str, reason: str, actor: str
    ) -> dict[str, Any]:
        """
        Merge multiple profiles into one.

        Args:
            from_profile_ids: Profiles to merge FROM
            to_profile_id: Profile to merge INTO
            reason: Why merging
            actor: Who initiated

        Returns:
            Merge operation result
        """
        op_id = self._generate_id("iop")

        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            # Verify all profiles exist
            all_ids = from_profile_ids + [to_profile_id]
            placeholders = ",".join(["?"] * len(all_ids))
            cursor.execute(
                f"""
                SELECT profile_id FROM identity_profiles
                WHERE profile_id IN ({placeholders}) AND status = 'active'
            """,  # noqa: S608
                all_ids,
            )

            found = {row[0] for row in cursor.fetchall()}
            missing = set(all_ids) - found
            if missing:
                return {"status": "error", "error": f"Profiles not found: {missing}"}

            # Move all claims from source profiles to target
            for from_id in from_profile_ids:
                cursor.execute(
                    """
                    UPDATE identity_claims
                    SET profile_id = ?, status = 'active'
                    WHERE profile_id = ? AND status = 'active'
                """,
                    (to_profile_id, from_id),
                )

            # Mark source profiles as merged
            for from_id in from_profile_ids:
                cursor.execute(
                    """
                    UPDATE identity_profiles
                    SET status = 'merged', updated_at = datetime('now')
                    WHERE profile_id = ?
                """,
                    (from_id,),
                )

            # Log operation
            cursor.execute(
                """
                INSERT INTO identity_operations
                (op_id, op_type, from_profile_ids, to_profile_ids, reason, actor, created_at)
                VALUES (?, 'merge', ?, ?, ?, ?, datetime('now'))
            """,
                (
                    op_id,
                    json.dumps(from_profile_ids),
                    json.dumps([to_profile_id]),
                    reason,
                    actor,
                ),
            )

            conn.commit()
            return {
                "status": "success",
                "op_id": op_id,
                "merged_count": len(from_profile_ids),
                "target_profile_id": to_profile_id,
            }

        except (sqlite3.Error, ValueError, OSError):
            raise  # was silently swallowed
        finally:
            conn.close()

    def get_stats(self) -> dict[str, Any]:
        """Get identity statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        try:
            stats = {}

            cursor.execute("SELECT COUNT(*) FROM identity_profiles WHERE status = 'active'")
            stats["active_profiles"] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT profile_type, COUNT(*)
                FROM identity_profiles WHERE status = 'active'
                GROUP BY profile_type
            """)
            stats["by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM identity_claims WHERE status = 'active'")
            stats["active_claims"] = cursor.fetchone()[0]

            cursor.execute("""
                SELECT claim_type, COUNT(*)
                FROM identity_claims WHERE status = 'active'
                GROUP BY claim_type
            """)
            stats["claims_by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM identity_operations")
            stats["total_operations"] = cursor.fetchone()[0]

            return stats
        finally:
            conn.close()


# Singleton
_identity_service = None


def get_identity_service() -> IdentityService:
    global _identity_service
    if _identity_service is None:
        _identity_service = IdentityService()
    return _identity_service
