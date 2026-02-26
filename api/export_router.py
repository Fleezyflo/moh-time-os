"""
Data Export API Router - REST endpoints for data governance and portability.

Provides endpoints for:
- Requesting bulk data exports
- Checking export status
- Listing exportable tables
- Getting table schemas
- Supporting compliance and GDPR requirements
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.response_models import DetailResponse
from lib.governance.data_export import DataExporter, ExportFormat, ExportRequest
from lib.paths import data_dir
import sqlite3

logger = logging.getLogger(__name__)

# Create router
export_router = APIRouter(
    prefix="/api/governance",
    tags=["Governance"],
)

# Get database path
db_path = data_dir() / "moh_time_os.db"

# Export instances by request ID
_exports = {}


@export_router.post("/export", response_model=DetailResponse)
def request_data_export(
    tables: list[str] = Query(..., description="Tables to export"),
    format: str = Query("json", description="Export format: json, csv, jsonl"),
    anonymize_pii: bool = Query(False, description="Anonymize PII columns"),
    requested_by: str | None = Query(None, description="Who requested the export"),
    reason: str | None = Query(None, description="Reason for export"),
) -> dict:
    """
    Request bulk data export.

    Returns request_id to check status later.
    """
    try:
        # Validate format
        try:
            fmt = ExportFormat[format.upper()]
        except KeyError as e:
            raise HTTPException(
                status_code=400, detail="Invalid format. Supported: json, csv, jsonl"
            ) from e

        # Create exporter
        exporter = DataExporter(str(db_path))

        # Create request
        request = ExportRequest(
            tables=tables,
            format=fmt,
            anonymize_pii=anonymize_pii,
            requested_by=requested_by,
            reason=reason,
        )

        # Export
        result = exporter.export_tables(request)

        # Store result
        _exports[result.request_id] = result

        return {
            "status": "ok",
            "request_id": result.request_id,
            "table_count": result.table_count,
            "row_count": result.row_count,
            "format": result.format.value,
            "anonymized": result.anonymized,
            "created_at": result.created_at,
        }
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error requesting export: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@export_router.get("/export/{request_id}", response_model=DetailResponse)
def get_export_status(request_id: str) -> dict:
    """
    Check export status and get download link.
    """
    try:
        if request_id not in _exports:
            raise HTTPException(status_code=404, detail="Export not found")

        result = _exports[request_id]

        return {
            "status": "ok",
            "request_id": result.request_id,
            "file_path": result.file_path,
            "table_count": result.table_count,
            "row_count": result.row_count,
            "size_bytes": result.size_bytes,
            "format": result.format.value,
            "anonymized": result.anonymized,
            "created_at": result.created_at,
            "checksum_sha256": result.checksum_sha256,
            "tables": result.tables_included,
        }
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error getting export status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@export_router.get("/exportable-tables", response_model=DetailResponse)
def list_exportable_tables() -> dict:
    """
    List available tables for export with metadata.
    """
    try:
        exporter = DataExporter(str(db_path))
        tables = exporter.list_exportable_tables()

        return {
            "status": "ok",
            "table_count": len(tables),
            "tables": tables,
        }
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error listing tables: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@export_router.get("/export-schema/{table}", response_model=DetailResponse)
def get_table_schema(table: str) -> dict:
    """
    Get schema for a specific table.
    """
    try:
        exporter = DataExporter(str(db_path))
        schema = exporter.get_export_schema(table)

        if "error" in schema:
            raise HTTPException(status_code=400, detail=schema["error"])

        return {
            "status": "ok",
            "schema": schema,
        }
    except HTTPException:
        raise
    except (sqlite3.Error, ValueError) as e:
        logger.error(f"Error getting schema: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
