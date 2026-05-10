"""
Database connector base classes and configuration models.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# D-001: Import pybreaker for circuit breaker pattern
try:
    import pybreaker
    HAS_PYBREAKER = True
except ImportError:
    HAS_PYBREAKER = False

# D-002: Import tenacity for retry policies
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False


def _get_redis_client():
    """Get Redis client for circuit breaker state storage."""
    try:
        import redis
        redis_url = "redis://localhost:6379/0"
        return redis.from_url(redis_url)
    except Exception:
        return None


# D-001: Configure circuit breaker
if HAS_PYBREAKER:
    _redis_client = _get_redis_client()
    # Use Redis as fallback state storage; if unavailable, uses in-memory
    if _redis_client:
        circuit_breaker_storage = pybreaker.CircuitRedisStorage(
            redis_client=_redis_client,
            expire_time=60  # State expires after 60 seconds
        )
    else:
        circuit_breaker_storage = pybreaker.CircuitMemoryStorage()

    # Circuit breaker configuration
    EXTERNAL_SERVICE_CB = pybreaker.CircuitBreaker(
        fail_max=5,              # Open after 5 consecutive failures
        reset_timeout=30,        # Try to close after 30 seconds
        state_storage=circuit_breaker_storage,
        listeners=[]             # Could add listeners for logging
    )
else:
    EXTERNAL_SERVICE_CB = None


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

    def verify_password(self, plaintext: str) -> bool:
        """Verify if plaintext password matches the encrypted stored password.

        NEW-008 FIX: Never expose plaintext password through properties.
        Use this comparison method instead for verification.
        """
        from connectors.encryption import decrypt_value
        try:
            decrypted = decrypt_value(self.password_encrypted)
            return decrypted == plaintext
        except Exception:
            return False

    @property
    def password(self) -> str:
        """DEPRECATED: Never expose plaintext password.

        NEW-008 FIX: Password can no longer be retrieved in plaintext.
        Use verify_password() for comparison instead.
        """
        raise AttributeError(
            "Password cannot be retrieved in plaintext for security reasons. "
            "Use verify_password() method for password verification."
        )

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


# D-002: Default retry decorator for transient failures
def _default_retry_decorator(func):
    """Decorator to retry on transient failures with exponential backoff."""
    if HAS_TENACITY:
        return retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
            reraise=True
        )(func)
    return func


class BaseConnector(ABC):
    """Abstract base class for database connectors."""

    def __init__(self, config: DataSourceConfig):
        self.config = config
        self._engine = None

    def _create_engine(self):
        """Create SQLAlchemy engine with connection pooling and query timeout."""
        from sqlalchemy import event
        return create_engine(
            self.config.to_connection_url(),
            poolclass=QueuePool,
            pool_size=self.config.connection_pool_size,
            max_overflow=self.config.connection_max_overflow,
            pool_timeout=self.config.connection_timeout,
            pool_pre_ping=True,
            connect_args={
                "options": "-c statement_timeout=30000"  # 30 second timeout
            },
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
