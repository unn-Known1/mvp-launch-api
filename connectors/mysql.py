"""
MySQL database connector with connection pooling.
"""

import time
from typing import Any, Optional

from sqlalchemy import text

from connectors.base import BaseConnector, ConnectionTestResult


class MySQLConnector(BaseConnector):
    """MySQL connector using pymysql driver."""

    def __init__(self, config):
        config.db_type = "mysql"
        super().__init__(config)

    def test_connection(self) -> ConnectionTestResult:
        """Test MySQL connection and return latency + server version."""
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                result = conn.execute(text("SELECT VERSION();"))
                version_row = result.fetchone()
                server_version = version_row[0] if version_row else None

                latency_ms = (time.monotonic() - start) * 1000
                return ConnectionTestResult(
                    success=True,
                    latency_ms=round(latency_ms, 2),
                    message="Connection successful",
                    server_version=server_version,
                )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return ConnectionTestResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                message=f"Connection failed: {str(e)}",
            )

    def execute_query(self, query: str, params: Optional[dict] = None) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        with self.get_connection() as conn:
            result = conn.execute(text(query), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def get_schema_info(self) -> dict[str, Any]:
        """Return MySQL schema information."""
        schema_query = """
            SELECT
                TABLE_SCHEMA,
                TABLE_NAME,
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION;
        """
        columns = self.execute_query(schema_query)

        tables = {}
        for col in columns:
            table_key = f"{col['TABLE_SCHEMA']}.{col['TABLE_NAME']}"
            if table_key not in tables:
                tables[table_key] = {
                    "schema": col["TABLE_SCHEMA"],
                    "table": col["TABLE_NAME"],
                    "columns": [],
                }
            tables[table_key]["columns"].append(
                {
                    "name": col["COLUMN_NAME"],
                    "type": col["DATA_TYPE"],
                    "nullable": col["IS_NULLABLE"] == "YES",
                }
            )

        return {"tables": list(tables.values()), "table_count": len(tables)}
