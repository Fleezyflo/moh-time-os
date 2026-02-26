"""
Subject Access Request & Data Governance API Router.

REST endpoints for GDPR/privacy compliance:
- Subject Access Requests (article 15)
- Right to be Forgotten (article 17)
- Data export for portability (article 20)
- Audit log querying for transparency
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.response_models import DetailResponse
from lib.governance.subject_access import SubjectAccessManager
from lib.paths import data_dir
import sqlite3

logger = logging.getLogger(__name__)

# Create router
governance_router = APIRouter(
    prefix="/api/governance",
    tags=["Governance"],
)

# Get database path
db_path = data_dir() / "moh_time_os.db"

# Subject access manager instance
_manager = SubjectAccessManager(str(db_path))


@governance_router.post("/sar", response_model=DetailResponse)
def create_subject_access_request(
    subject_identifier: str = Query(..., description="Email, name, or ID of data subject"),
    request_type: str = Query(..., description="access, deletion, rectification, or portability"),
    requested_by: str | None = Query(None, description="Who is making the request"),
    reason: str | None = Query(None, description="Reason for the request"),
) -> dict:
    """
    Create a new subject access request.

    GDPR compliance: Articles 15 (access), 17 (deletion), 16 (rectification), 20 (portability).

    Returns request_id for tracking.
    """
    try:
        # Validate request type
        valid_types = ["access", "deletion", "rectification", "portability"]
        if request_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid request_type. Supported: {', '.join(valid_types)}",
            )

        # Create request
        request_id = _manager.create_request(
            subject_identifier=subject_identifier,
            request_type=request_type,
            requested_by=requested_by or "api",
            reason=reason,
        )

        return {
            "status": "ok",
            "request_id": request_id,
            "subject_identifier": subject_identifier,
            "request_type": request_type,
        }

    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error creating SAR: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@governance_router.get("/sar/{request_id}", response_model=DetailResponse)
def get_subject_access_request(request_id: str) -> dict:
    """Get status of a subject access request."""
    try:
        request = _manager.get_request_status(request_id)

        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        return {
            "status": "ok",
            "request_id": request.request_id,
            "subject_identifier": request.subject_identifier,
            "request_type": request.request_type,
            "request_status": request.status,
            "requested_at": request.requested_at,
            "fulfilled_at": request.fulfilled_at,
            "requested_by": request.requested_by,
            "reason": request.reason,
        }

    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error getting SAR status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@governance_router.get("/sar", response_model=DetailResponse)
def list_subject_access_requests(
    status: str | None = Query(None, description="Filter by status"),
) -> dict:
    """List all subject access requests with optional status filter."""
    try:
        requests = _manager.list_requests(status=status)

        return {
            "status": "ok",
            "count": len(requests),
            "requests": [
                {
                    "request_id": req.request_id,
                    "subject_identifier": req.subject_identifier,
                    "request_type": req.request_type,
                    "request_status": req.status,
                    "requested_at": req.requested_at,
                    "fulfilled_at": req.fulfilled_at,
                }
                for req in requests
            ],
        }

    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error listing SARs: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@governance_router.post("/sar/{request_id}/fulfill", response_model=DetailResponse)
def fulfill_subject_access_request(
    request_id: str,
    action: str = Query(..., description="find, export, delete, or anonymize"),
    dry_run: bool = Query(True, description="Only simulate the action"),
) -> dict:
    """
    Fulfill a subject access request.

    Supports:
    - find: Search for all subject data
    - export: Export subject data to file
    - delete: Delete subject data (dry-run by default)
    - anonymize: Anonymize subject data instead of delete

    Args:
        request_id: The SAR request ID
        action: What to do (find, export, delete, anonymize)
        dry_run: If true, only simulate (default true for destructive ops)

    Returns:
        Details of the action result
    """
    try:
        # Get the request
        sar = _manager.get_request_status(request_id)
        if not sar:
            raise HTTPException(status_code=404, detail="Request not found")

        # Perform the action
        if action == "find":
            report = _manager.find_subject_data(sar.subject_identifier)
            return {
                "status": "ok",
                "action": "find",
                "subject_identifier": report.subject_identifier,
                "tables_searched": len(report.tables_searched),
                "tables_with_data": report.tables_with_data,
                "total_records": report.total_records,
                "generated_at": report.generated_at,
            }

        elif action == "export":
            file_path = _manager.export_subject_data(sar.subject_identifier)
            return {
                "status": "ok",
                "action": "export",
                "file_path": file_path,
                "subject_identifier": sar.subject_identifier,
            }

        elif action == "delete":
            result = _manager.delete_subject_data(sar.subject_identifier, dry_run=dry_run)
            return {
                "status": "ok",
                "action": "delete",
                "dry_run": dry_run,
                "subject_identifier": result.subject_identifier,
                "tables_affected": result.tables_affected,
                "rows_deleted": result.rows_deleted,
                "tables_skipped": result.tables_skipped,
                "completed_at": result.completed_at,
            }

        elif action == "anonymize":
            result = _manager.anonymize_subject_data(sar.subject_identifier, dry_run=dry_run)
            return {
                "status": "ok",
                "action": "anonymize",
                "dry_run": dry_run,
                "subject_identifier": result.subject_identifier,
                "tables_affected": result.tables_affected,
                "rows_anonymized": result.rows_anonymized,
                "tables_skipped": result.tables_skipped,
                "completed_at": result.completed_at,
            }

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Supported: find, export, delete, anonymize",
            )

    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error fulfilling SAR: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@governance_router.get("/audit-log", response_model=DetailResponse)
def query_audit_log(
    subject: str | None = Query(None, description="Filter by data subject"),
    action: str | None = Query(None, description="Filter by action type"),
    since: str | None = Query(None, description="Filter by timestamp (ISO format)"),
) -> dict:
    """
    Query the audit log for governance operations.

    Returns all operations on a subject or of a specific action type.
    """
    try:
        # Get audit log entries
        audit_entries = _manager.audit_log.get_entries(subject=subject, action=action, since=since)

        return {
            "status": "ok",
            "count": len(audit_entries),
            "entries": [
                {
                    "id": entry.id,
                    "timestamp": entry.timestamp,
                    "action": entry.action,
                    "actor": entry.actor,
                    "subject_identifier": entry.subject_identifier,
                    "details": entry.details,
                    "ip_address": entry.ip_address,
                }
                for entry in audit_entries
            ],
        }

    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error querying audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
