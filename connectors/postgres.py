"""
PostgreSQL database connector with connection pooling.
"""

import time
from typing import Any, Optional

from sqlalchemy import text

from connectors.base import BaseConnector, ConnectionTestResult


class PostgreSQLConnector(BaseConnector):
    """PostgreSQL connector using psycopg2 driver."""

    def __init__(self, config):
        config.db_type = "postgresql"
        super().__init__(config)

    def test_connection(self) -> ConnectionTestResult:
        """Test PostgreSQL connection and return latency + server version."""
        start = time.monotonic()
        try:
            with self.get_connection() as conn:
                result = conn.execute(text("SELECT version();"))
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
        """Return PostgreSQL schema information."""
        schema_query = """
            SELECT
                table_schema,
                table_name,
                column_name,
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name, ordinal_position;
        """
        columns = self.execute_query(schema_query)

        tables = {}
        for col in columns:
            table_key = f"{col['table_schema']}.{col['table_name']}"
            if table_key not in tables:
                tables[table_key] = {
                    "schema": col["table_schema"],
                    "table": col["table_name"],
                    "columns": [],
                }
            tables[table_key]["columns"].append(
                {
                    "name": col["column_name"],
                    "type": col["data_type"],
                    "nullable": col["is_nullable"] == "YES",
                }
            )

        return {"tables": list(tables.values()), "table_count": len(tables)}
