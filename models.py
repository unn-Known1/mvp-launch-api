"""
Database Models - MVP Launch
SQLAlchemy models for PostgreSQL database
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


def generate_uuid():
    return uuid4()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    role = relationship("Role", back_populates="users")
    datasets = relationship("Dataset", back_populates="owner")
    api_keys = relationship("ApiKey", back_populates="user")
    nl_queries = relationship("NLQueryHistory", back_populates="user")

    __table_args__ = (Index("ix_users_role_id", "role_id"),)


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    permissions = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="role")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")

    __table_args__ = (Index("ix_api_keys_user_id", "user_id"),)


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    s3_key = Column(String(512), nullable=True)
    schema = Column(JSON, nullable=True)
    row_count = Column(Integer, default=0)
    size_bytes = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    dataset_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="datasets")
    records = relationship("DataRecord", back_populates="dataset")
    forecasts = relationship("Forecast", back_populates="dataset")

    __table_args__ = (
        Index("ix_datasets_user_id", "user_id"),
        Index("ix_datasets_status", "status"),
    )


class DataRecord(Base):
    __tablename__ = "data_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    data = Column(JSON, nullable=False)
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset", back_populates="records")
    import_batch = relationship("ImportBatch", back_populates="records")

    __table_args__ = (Index("ix_data_records_dataset_id", "dataset_id"),)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    source_type = Column(String(50), nullable=False)
    source_path = Column(String(512), nullable=True)
    status = Column(String(50), default="pending")
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    dataset = relationship("Dataset")
    records = relationship("DataRecord", back_populates="import_batch")

    __table_args__ = (Index("ix_import_batches_dataset_id", "dataset_id"),)


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    model_type = Column(String(50), nullable=False)
    target_column = Column(String(255), nullable=False)
    periods = Column(Integer, nullable=False)
    frequency = Column(String(10), default="D")
    predictions = Column(JSON, nullable=False)
    model_metrics = Column(JSON, nullable=True)
    status = Column(String(50), default="running")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    dataset = relationship("Dataset", back_populates="forecasts")

    __table_args__ = (
        Index("ix_forecasts_dataset_id", "dataset_id"),
        Index("ix_forecasts_status", "status"),
    )


class NLQueryHistory(Base):
    __tablename__ = "nl_query_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    data_source_id = Column(String(255), nullable=True)
    natural_language_query = Column(Text, nullable=False)
    generated_sql = Column(Text, nullable=True)
    executed_sql = Column(Text, nullable=True)
    query_results = Column(JSON, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    confidence_level = Column(String(20), nullable=True)
    follow_up_questions = Column(JSON, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    row_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="nl_queries")

    __table_args__ = (
        Index("ix_nl_query_history_user_id", "user_id"),
        Index("ix_nl_query_history_created_at", "created_at"),
        Index("ix_nl_query_history_status", "status"),
    )


class NLPAnalysis(Base):
    __tablename__ = "nlp_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    analysis_type = Column(String(50), nullable=False)
    results = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_nlp_analyses_user_id", "user_id"),
        Index("ix_nlp_analyses_type", "analysis_type"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_action", "action"),
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    metric_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    expected_value = Column(String(255), nullable=True)
    actual_value = Column(String(255), nullable=False)
    severity = Column(String(20), nullable=False, default="medium")
    detection_method = Column(String(50), nullable=False)
    z_score = Column(String(50), nullable=True)
    iqr_lower = Column(String(50), nullable=True)
    iqr_upper = Column(String(50), nullable=True)
    status = Column(String(20), default="flagged")
    investigated_at = Column(DateTime, nullable=True)
    investigated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("Dataset")
    investigator = relationship("User")

    __table_args__ = (
        Index("ix_anomalies_dataset_id", "dataset_id"),
        Index("ix_anomalies_timestamp", "timestamp"),
        Index("ix_anomalies_status", "status"),
        Index("ix_anomalies_severity", "severity"),
    )


class AnomalyThreshold(Base):
    __tablename__ = "anomaly_thresholds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    metric_name = Column(String(255), nullable=False)
    z_score_threshold = Column(Integer, default=3)
    iqr_multiplier = Column(Integer, default=3)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    dataset = relationship("Dataset")

    __table_args__ = (
        Index("ix_anomaly_thresholds_dataset_id", "dataset_id"),
        UniqueConstraint("dataset_id", "metric_name", name="uq_anomaly_thresholds_dataset_metric"),
    )


class AnomalyNotification(Base):
    __tablename__ = "anomaly_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    anomaly_id = Column(UUID(as_uuid=True), ForeignKey("anomalies.id"), nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    anomaly = relationship("Anomaly")

    __table_args__ = (
        Index("ix_anomaly_notifications_user_id", "user_id"),
        Index("ix_anomaly_notifications_read", "read"),
    )


# Default Roles Configuration
DEFAULT_ROLES = {
    "admin": {
        "description": "Full system access",
        "permissions": [
            "users:read",
            "users:write",
            "users:delete",
            "datasets:read",
            "datasets:write",
            "datasets:delete",
            "ml:forecast",
            "ml:nlp",
            "nl_query:read",
            "nl_query:write",
            "admin:access",
            "audit:read",
        ],
    },
    "analyst": {
        "description": "Data access and ML operations",
        "permissions": [
            "datasets:read",
            "datasets:write",
            "ml:forecast",
            "ml:nlp",
            "nl_query:read",
            "nl_query:write",
        ],
    },
    "viewer": {
        "description": "Read-only access to own data",
        "permissions": [
            "datasets:read",
            "nl_query:read",
        ],
    },
}
