"""
Data Catalog for MOH Time OS.

Provides queryable interface to classified data and compliance reporting.
"""

import logging

from lib.governance.data_classification import DataSensitivity, TableClassification

logger = logging.getLogger(__name__)


class DataCatalog:
    """Queryable catalog of classified database tables and columns."""

    def __init__(self, tables: dict[str, TableClassification]):
        """Initialize catalog with table classifications."""
        self.tables = tables
        self.logger = logging.getLogger(__name__)

    def get_sensitive_tables(self, min_sensitivity: DataSensitivity) -> list[str]:
        """Get all tables meeting or exceeding sensitivity threshold."""
        result = []
        for table_name, table_class in self.tables.items():
            if table_class.overall_sensitivity >= min_sensitivity:
                result.append(table_name)
        return sorted(result)

    def get_tables_by_category(self, category) -> list[str]:
        """Get all tables in a specific category."""
        result = []
        for table_name, table_class in self.tables.items():
            if category in table_class.categories:
                result.append(table_name)
        return sorted(result)

    def get_pii_tables(self) -> list[str]:
        """Get all tables containing PII."""
        result = []
        for table_name, table_class in self.tables.items():
            if table_class.pii_columns:
                result.append(table_name)
        return sorted(result)

    def get_financial_tables(self) -> list[str]:
        """Get all tables containing financial data."""
        result = []
        for table_name, table_class in self.tables.items():
            if table_class.financial_columns:
                result.append(table_name)
        return sorted(result)

    def get_pii_report(self) -> dict:
        """Generate comprehensive PII report."""
        pii_tables = self.get_pii_tables()
        total_pii_columns = 0
        pii_by_table = {}

        for table_name in pii_tables:
            table_class = self.tables[table_name]
            pii_count = len(table_class.pii_columns)
            total_pii_columns += pii_count
            pii_by_table[table_name] = {
                "column_count": pii_count,
                "columns": table_class.pii_columns,
                "sensitivity": table_class.overall_sensitivity.name,
            }

        return {
            "total_tables_with_pii": len(pii_tables),
            "total_pii_columns": total_pii_columns,
            "tables": pii_by_table,
        }

    def get_compliance_summary(self) -> dict:
        """Generate compliance-ready overview."""
        # Calculate statistics
        total_tables = len(self.tables)
        total_columns = sum(t.total_columns for t in self.tables.values())
        pii_tables = self.get_pii_tables()
        financial_tables = self.get_financial_tables()
        pii_columns = sum(len(t.pii_columns) for t in self.tables.values())
        financial_columns = sum(len(t.financial_columns) for t in self.tables.values())

        # Sensitivity distribution
        sensitivity_dist = {}
        for sensitivity in DataSensitivity:
            count = len(self.get_sensitive_tables(sensitivity))
            if count > 0:
                sensitivity_dist[sensitivity.name] = count

        # High sensitivity tables
        high_sensitivity_tables = self.get_sensitive_tables(DataSensitivity.CONFIDENTIAL)

        return {
            "summary": {
                "total_tables": total_tables,
                "total_columns": total_columns,
                "tables_with_pii": len(pii_tables),
                "tables_with_financial": len(financial_tables),
                "total_pii_columns": pii_columns,
                "total_financial_columns": financial_columns,
            },
            "sensitivity_distribution": sensitivity_dist,
            "high_sensitivity_tables": high_sensitivity_tables,
            "pii_details": self.get_pii_report(),
        }

    def to_dict(self) -> dict:
        """Convert catalog to serializable dictionary."""
        return {
            "tables": {
                table_name: table_class.to_dict() for table_name, table_class in self.tables.items()
            },
            "summary": {
                "total_tables": len(self.tables),
                "total_columns": sum(t.total_columns for t in self.tables.values()),
            },
        }

    def to_markdown(self) -> str:
        """Generate human-readable markdown report."""
        lines = ["# Data Classification Report\n"]

        # Summary
        summary = self.get_compliance_summary()
        lines.append("## Executive Summary\n")
        for key, value in summary["summary"].items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

        # Sensitivity Distribution
        lines.append("## Sensitivity Distribution\n")
        for sensitivity, count in summary["sensitivity_distribution"].items():
            lines.append(f"- {sensitivity}: {count} tables")
        lines.append("")

        # High Sensitivity Tables
        lines.append("## High Sensitivity Tables\n")
        high_sensitivity = summary["high_sensitivity_tables"]
        if high_sensitivity:
            for table_name in high_sensitivity:
                table_class = self.tables[table_name]
                lines.append(f"- **{table_name}** ({table_class.overall_sensitivity.name})")
                if table_class.pii_columns:
                    lines.append(f"  - PII columns: {', '.join(table_class.pii_columns)}")
                if table_class.financial_columns:
                    lines.append(
                        f"  - Financial columns: {', '.join(table_class.financial_columns)}"
                    )
        else:
            lines.append("No high sensitivity tables found.")
        lines.append("")

        # PII Summary
        lines.append("## PII Summary\n")
        pii_report = summary["pii_details"]
        lines.append(f"Total tables with PII: {pii_report['total_tables_with_pii']}")
        lines.append(f"Total PII columns: {pii_report['total_pii_columns']}")
        lines.append("")

        if pii_report["tables"]:
            lines.append("### PII Tables\n")
            for table_name, pii_info in pii_report["tables"].items():
                lines.append(f"- **{table_name}**")
                lines.append(f"  - Sensitivity: {pii_info['sensitivity']}")
                lines.append(
                    f"  - Columns ({pii_info['column_count']}): {', '.join(pii_info['columns'])}"
                )
        lines.append("")

        # All Tables
        lines.append("## All Tables\n")
        for table_name in sorted(self.tables.keys()):
            table_class = self.tables[table_name]
            lines.append(
                f"- **{table_name}** - {table_class.overall_sensitivity.name} "
                f"({table_class.classified_columns}/{table_class.total_columns} classified)"
            )

        return "\n".join(lines)
