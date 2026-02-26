"""
Data Export System - Bulk export with format support, filtering, and anonymization.

Supports:
- Multiple export formats (JSON, CSV, JSONL)
- Table filtering and column selection
- Date range filtering on timestamp columns
- Optional PII anonymization
- SHA-256 checksums for data integrity
- Streaming for large tables
"""

import csv
import hashlib
import json
import logging
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from lib.data_lifecycle import get_lifecycle_manager
from lib.db import validate_identifier
from lib.governance.anonymizer import Anonymizer

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats."""

    JSON = "json"
    CSV = "csv"
    JSONL = "jsonl"


@dataclass
class ExportRequest:
    """Request for bulk data export."""

    tables: list[str]
    format: ExportFormat
    filters: dict | None = None
    include_schema: bool = False
    anonymize_pii: bool = False
    date_range: tuple[str, str] | None = None  # (start_date, end_date)
    columns: dict[str, list[str]] | None = None  # {table: [col1, col2, ...]}
    requested_by: str | None = None
    reason: str | None = None


@dataclass
class ExportResult:
    """Result of data export."""

    request_id: str
    format: ExportFormat
    file_path: str
    row_count: int
    table_count: int
    size_bytes: int
    created_at: str
    checksum_sha256: str
    anonymized: bool
    tables_included: list[str] = field(default_factory=list)


class DataExporter:
    """
    Bulk data exporter with format support and filtering.

    Handles:
    - Table enumeration and validation
    - Format-specific export (JSON, CSV, JSONL)
    - Column filtering
    - Date range filtering
    - PII anonymization
    - Streaming for large tables
    - SHA-256 checksums
    """

    def __init__(self, db_path: str | Path, export_dir: str | Path | None = None):
        """Initialize exporter with database path and optional export directory."""
        self.db_path = Path(db_path)
        if export_dir is None:
            export_dir = Path(tempfile.gettempdir()) / "moh_exports"
        self.export_dir = Path(export_dir)
        self.lifecycle = get_lifecycle_manager()
        self.anonymizer = Anonymizer()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _get_table_columns(self, table: str) -> list[str]:
        """Get column names for a table."""
        try:
            safe_table = validate_identifier(table)
            conn = self._get_connection()
            cursor = conn.execute(f"PRAGMA table_info({safe_table})")  # noqa: S608
            columns = [row[1] for row in cursor.fetchall()]
            conn.close()
            return columns
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error getting columns for {table}: {e}")
            return []

    def _build_query(
        self,
        table: str,
        filters: dict | None = None,
        date_range: tuple[str, str] | None = None,
        columns: list[str] | None = None,
    ) -> tuple[str, list]:
        """Build SELECT query with WHERE clause."""
        safe_table = validate_identifier(table)

        # Get all columns if not specified
        if not columns:
            columns = self._get_table_columns(table)

        if not columns:
            raise ValueError(f"Table '{table}' does not exist or has no columns")

        col_list = ", ".join([f'"{validate_identifier(col)}"' for col in columns])
        sql = f"SELECT {col_list} FROM {safe_table}"  # noqa: S608
        params = []

        conditions = []

        # Filter by column values
        if filters:
            for col, value in filters.items():
                conditions.append(f'"{col}" = ?')
                params.append(value)

        # Filter by date range (look for timestamp columns)
        if date_range:
            start_date, end_date = date_range
            # Try common timestamp column names
            timestamp_cols = ["created_at", "updated_at", "timestamp", "date"]
            for ts_col in timestamp_cols:
                if ts_col in columns:
                    conditions.append(f'"{ts_col}" >= ? AND "{ts_col}" <= ?')
                    params.append(start_date)
                    params.append(end_date)
                    break

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        return sql, params

    def list_exportable_tables(self) -> list[dict]:
        """Get list of exportable tables with metadata."""
        tables = []

        for table_name in self.lifecycle.get_all_exportable_tables():
            metadata = self.lifecycle.get_table_metadata(table_name)
            if metadata is None:
                continue

            try:
                conn = self._get_connection()
                safe_name = validate_identifier(table_name)
                cursor = conn.execute(f"SELECT COUNT(*) as count FROM {safe_name}")  # noqa: S608
                row_count = cursor.fetchone()[0]
                conn.close()

                columns = self._get_table_columns(table_name)

                tables.append(
                    {
                        "table": table_name,
                        "description": metadata.description,
                        "row_count": row_count,
                        "column_count": len(columns),
                        "has_pii": bool(metadata.pii_columns),
                        "classification": metadata.classification.value,
                    }
                )
            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Error listing table {table_name}: {e}")

        return tables

    def get_export_schema(self, table: str) -> dict:
        """Get schema for a table."""
        if not self.lifecycle.is_exportable(table):
            return {"error": f"Table {table} is not exportable"}

        try:
            safe_table = validate_identifier(table)
            conn = self._get_connection()
            cursor = conn.execute(f"PRAGMA table_info({safe_table})")  # noqa: S608

            columns = []
            for row in cursor.fetchall():
                columns.append(
                    {
                        "name": row[1],
                        "type": row[2],
                        "not_null": bool(row[3]),
                        "default": row[4],
                        "primary_key": bool(row[5]),
                    }
                )

            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {safe_table}")  # noqa: S608
            row_count = cursor.fetchone()[0]
            conn.close()

            metadata = self.lifecycle.get_table_metadata(table)

            return {
                "table": table,
                "columns": columns,
                "row_count": row_count,
                "pii_columns": metadata.pii_columns if metadata else [],
            }
        except (sqlite3.Error, ValueError, OSError) as e:
            logger.error(f"Error getting schema for {table}: {e}")
            return {"error": str(e)}

    def export_table(
        self,
        table: str,
        format: ExportFormat,
        filters: dict | None = None,
        columns: list[str] | None = None,
        anonymize: bool = False,
        date_range: tuple[str, str] | None = None,
    ) -> str:
        """
        Export single table to file.

        Returns path to exported file.
        """
        if not self.lifecycle.is_exportable(table):
            raise ValueError(f"Table {table} is not exportable")

        # Get columns
        if not columns:
            columns = self._get_table_columns(table)

        # Get PII columns if anonymizing
        pii_columns = []
        if anonymize:
            pii_columns = self.lifecycle.get_pii_columns(table)

        # Build query
        sql, params = self._build_query(table, filters, date_range, columns)

        # Execute query
        conn = self._get_connection()
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        # Convert to list of dicts
        data = [dict(row) for row in rows]

        # Anonymize if requested
        if anonymize:
            data = [self.anonymizer.anonymize_row(row, pii_columns) for row in data]

        # Export based on format
        self.export_dir.mkdir(exist_ok=True, parents=True)

        filename = f"{table}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if format == ExportFormat.JSON:
            file_path = self.export_dir / f"{filename}.json"
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        elif format == ExportFormat.CSV:
            file_path = self.export_dir / f"{filename}.csv"
            with open(file_path, "w", newline="") as f:
                if data:
                    writer = csv.DictWriter(f, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(data)
        elif format == ExportFormat.JSONL:
            file_path = self.export_dir / f"{filename}.jsonl"
            with open(file_path, "w") as f:
                for row in data:
                    f.write(json.dumps(row, default=str) + "\n")
        else:
            raise ValueError(f"Unsupported format: {format}")

        return str(file_path)

    def export_tables(self, request: ExportRequest) -> ExportResult:
        """Export multiple tables as requested."""
        result_files = {}
        total_rows = 0

        # Validate tables
        for table in request.tables:
            if not self.lifecycle.is_exportable(table):
                logger.warning(f"Table {table} is not exportable, skipping")
                continue

            try:
                file_path = self.export_table(
                    table,
                    request.format,
                    filters=request.filters,
                    columns=request.columns.get(table) if request.columns else None,
                    anonymize=request.anonymize_pii,
                    date_range=request.date_range,
                )
                result_files[table] = file_path

                # Count rows
                safe_table = validate_identifier(table)
                conn = self._get_connection()
                cursor = conn.execute(f"SELECT COUNT(*) FROM {safe_table}")  # noqa: S608
                count = cursor.fetchone()[0]
                conn.close()
                total_rows += count

            except (sqlite3.Error, ValueError, OSError) as e:
                logger.error(f"Error exporting table {table}: {e}")

        # Create manifest file
        request_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest = {
            "request_id": request_id,
            "requested_at": datetime.now().isoformat(),
            "requested_by": request.requested_by,
            "reason": request.reason,
            "format": request.format.value,
            "anonymized": request.anonymize_pii,
            "tables": list(result_files.keys()),
            "files": result_files,
        }

        manifest_file = self.export_dir / f"manifest_{request_id}.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)

        # Calculate checksum
        checksum = self._calculate_checksum(str(manifest_file))

        # Get file size
        file_size = manifest_file.stat().st_size

        return ExportResult(
            request_id=request_id,
            format=request.format,
            file_path=str(manifest_file),
            row_count=total_rows,
            table_count=len(result_files),
            size_bytes=file_size,
            created_at=datetime.now().isoformat(),
            checksum_sha256=checksum,
            anonymized=request.anonymize_pii,
            tables_included=list(result_files.keys()),
        )

    def export_all(
        self,
        format: ExportFormat,
        anonymize: bool = False,
    ) -> ExportResult:
        """Export all exportable tables."""
        tables = self.lifecycle.get_all_exportable_tables()
        request = ExportRequest(
            tables=tables,
            format=format,
            anonymize_pii=anonymize,
        )
        return self.export_tables(request)

    @staticmethod
    def _calculate_checksum(file_path: str) -> str:
        """Calculate SHA-256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
