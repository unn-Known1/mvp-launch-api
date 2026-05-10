"""
Database connector base classes and configuration models.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool


@dataclass
class DataSourceConfig:
    """Configuration for a database data source."""

    id: Optional[str] = None
    name: str = ""
    db_type: str = ""  # "postgresql" or "mysql"
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password_encrypted: str = ""
    connection_pool_size: int = 5
    connection_max_overflow: int = 10
    connection_timeout: int = 30
    ssl_enabled: bool = False
    extra_params: dict = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def password(self) -> str:
        """Return decrypted password."""
        from connectors.encryption import decrypt_value

        return decrypt_value(self.password_encrypted)

    @password.setter
    def password(self, plaintext: str):
        """Encrypt and store password."""
        from connectors.encryption import encrypt_value

        self.password_encrypted = encrypt_value(plaintext)

    def to_connection_url(self) -> str:
        """Build SQLAlchemy-compatible connection URL."""
        scheme = (
            "postgresql+psycopg2" if self.db_type == "postgresql" else "mysql+pymysql"
        )
        ssl_suffix = (
            "?sslmode=require"
            if self.ssl_enabled and self.db_type == "postgresql"
            else ""
        )
        return f"{scheme}://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}{ssl_suffix}"


@dataclass
class ConnectionTestResult:
    """Result of a connection test."""

    success: bool
    latency_ms: float
    message: str
    server_version: Optional[str] = None


class BaseConnector(ABC):
    """Abstract base class for database connectors."""

    def __init__(self, config: DataSourceConfig):
        self.config = config
        self._engine = None

    def _create_engine(self):
        """Create SQLAlchemy engine with connection pooling."""
        return create_engine(
            self.config.to_connection_url(),
            poolclass=QueuePool,
            pool_size=self.config.connection_pool_size,
            max_overflow=self.config.connection_max_overflow,
            pool_timeout=self.config.connection_timeout,
            pool_pre_ping=True,
        )

    @property
    def engine(self):
        """Lazy-load the engine."""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = self.engine.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close(self):
        """Dispose of the connection pool."""
        if self._engine:
            self._engine.dispose()
            self._engine = None

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """Test the database connection and return result."""
        pass

    @abstractmethod
    def execute_query(
        self, query: str, params: Optional[dict] = None
    ) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        pass

    @abstractmethod
    def get_schema_info(self) -> dict[str, Any]:
        """Return database schema information."""
        pass
