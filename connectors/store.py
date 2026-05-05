"""
CRUD service for data source configurations.
Manages persisted database connection configurations.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from connectors.base import DataSourceConfig
from connectors.encryption import encrypt_value


class DataSourceStore:
    """In-memory store for data source configurations.

    In production, this would be backed by the application database.
    For the MVP, we use an in-memory dict with the same interface.
    """

    def __init__(self):
        self._store: dict[str, dict] = {}

    def create(self, config: DataSourceConfig) -> DataSourceConfig:
        """Create a new data source configuration."""
        config_id = config.id or str(uuid4())
        config.id = config_id
        now = datetime.now(timezone.utc).isoformat()
        config.created_at = now
        config.updated_at = now

        self._store[config_id] = {
            "id": config_id,
            "name": config.name,
            "db_type": config.db_type,
            "host": config.host,
            "port": config.port,
            "database": config.database,
            "username": config.username,
            "password_encrypted": config.password_encrypted,
            "connection_pool_size": config.connection_pool_size,
            "connection_max_overflow": config.connection_max_overflow,
            "connection_timeout": config.connection_timeout,
            "ssl_enabled": config.ssl_enabled,
            "extra_params": config.extra_params,
            "created_at": now,
            "updated_at": now,
        }
        return config

    def get(self, config_id: str) -> Optional[DataSourceConfig]:
        """Get a data source configuration by ID."""
        record = self._store.get(config_id)
        if not record:
            return None
        return self._record_to_config(record)

    def list_all(self) -> list[DataSourceConfig]:
        """List all data source configurations (without decrypted passwords)."""
        return [self._record_to_config(record, include_password=False) for record in self._store.values()]

    def update(self, config_id: str, updates: dict) -> Optional[DataSourceConfig]:
        """Update a data source configuration."""
        record = self._store.get(config_id)
        if not record:
            return None

        updatable_fields = {
            "name", "host", "port", "database", "username",
            "connection_pool_size", "connection_max_overflow",
            "connection_timeout", "ssl_enabled", "extra_params",
        }

        for field, value in updates.items():
            if field == "password":
                record["password_encrypted"] = encrypt_value(value)
            elif field in updatable_fields:
                record[field] = value

        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        return self._record_to_config(record)

    def delete(self, config_id: str) -> bool:
        """Delete a data source configuration."""
        if config_id in self._store:
            del self._store[config_id]
            return True
        return False

    def _record_to_config(self, record: dict, include_password: bool = True) -> DataSourceConfig:
        """Convert a stored record to a DataSourceConfig."""
        return DataSourceConfig(
            id=record["id"],
            name=record["name"],
            db_type=record["db_type"],
            host=record["host"],
            port=record["port"],
            database=record["database"],
            username=record["username"],
            password_encrypted=record["password_encrypted"] if include_password else "",
            connection_pool_size=record["connection_pool_size"],
            connection_max_overflow=record["connection_max_overflow"],
            connection_timeout=record["connection_timeout"],
            ssl_enabled=record["ssl_enabled"],
            extra_params=record.get("extra_params", {}),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )


# Global store instance
data_source_store = DataSourceStore()
