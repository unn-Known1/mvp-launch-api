"""
Database connectors package.
"""

from connectors.base import BaseConnector, DataSourceConfig
from connectors.mysql import MySQLConnector
from connectors.postgres import PostgreSQLConnector


def create_connector(config: DataSourceConfig) -> BaseConnector:
    """Factory function to create the appropriate connector based on config db_type."""
    connectors = {
        "postgresql": PostgreSQLConnector,
        "mysql": MySQLConnector,
    }
    connector_class = connectors.get(config.db_type.lower())
    if not connector_class:
        raise ValueError(f"Unsupported database type: {config.db_type}. Supported: {list(connectors.keys())}")
    return connector_class(config)
