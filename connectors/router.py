"""
FastAPI router for data source management and connection testing.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from connectors import create_connector
from connectors.base import DataSourceConfig
from connectors.store import data_source_store
from auth import get_current_user

router = APIRouter(prefix="/api/v1/datasources", tags=["Data Sources"])


class CreateDataSourceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    db_type: str = Field(..., pattern="^(postgresql|mysql)$")
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    database: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    connection_pool_size: int = Field(default=5, ge=1, le=100)
    connection_max_overflow: int = Field(default=10, ge=0, le=50)
    connection_timeout: int = Field(default=30, ge=1, le=300)
    ssl_enabled: bool = False
    extra_params: dict = Field(default_factory=dict)


class UpdateDataSourceRequest(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    connection_pool_size: Optional[int] = Field(None, ge=1, le=100)
    connection_max_overflow: Optional[int] = Field(None, ge=0, le=50)
    connection_timeout: Optional[int] = Field(None, ge=1, le=300)
    ssl_enabled: Optional[bool] = None
    extra_params: Optional[dict] = None


class DataSourceResponse(BaseModel):
    id: str
    name: str
    db_type: str
    host: str
    port: int
    database: str
    username: str
    connection_pool_size: int
    connection_max_overflow: int
    connection_timeout: int
    ssl_enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConnectionTestResponse(BaseModel):
    success: bool
    latency_ms: float
    message: str
    server_version: Optional[str] = None


@router.post("/", response_model=DataSourceResponse, status_code=201)
def create_data_source(req: CreateDataSourceRequest, current_user=Depends(get_current_user)):
    """Create a new data source configuration."""
    config = DataSourceConfig(
        name=req.name,
        db_type=req.db_type,
        host=req.host,
        port=req.port,
        database=req.database,
        username=req.username,
    )
    config.password = req.password
    config.connection_pool_size = req.connection_pool_size
    config.connection_max_overflow = req.connection_max_overflow
    config.connection_timeout = req.connection_timeout
    config.ssl_enabled = req.ssl_enabled
    config.extra_params = req.extra_params

    created = data_source_store.create(config, user_id=str(current_user.id))
    return DataSourceResponse(
        id=created.id,
        name=created.name,
        db_type=created.db_type,
        host=created.host,
        port=created.port,
        database=created.database,
        username=created.username,
        connection_pool_size=created.connection_pool_size,
        connection_max_overflow=created.connection_max_overflow,
        connection_timeout=created.connection_timeout,
        ssl_enabled=created.ssl_enabled,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.get("/", response_model=list[DataSourceResponse])
def list_data_sources(current_user=Depends(get_current_user)):
    """List all data source configurations for the current user."""
    configs = data_source_store.list_all(user_id=str(current_user.id))
    return [
        DataSourceResponse(
            id=c.id,
            name=c.name,
            db_type=c.db_type,
            host=c.host,
            port=c.port,
            database=c.database,
            username=c.username,
            connection_pool_size=c.connection_pool_size,
            connection_max_overflow=c.connection_max_overflow,
            connection_timeout=c.connection_timeout,
            ssl_enabled=c.ssl_enabled,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in configs
    ]


@router.get("/{config_id}", response_model=DataSourceResponse)
def get_data_source(config_id: str, current_user=Depends(get_current_user)):
    """Get a data source configuration by ID."""
    config = data_source_store.get(config_id, user_id=str(current_user.id))
    if not config:
        raise HTTPException(status_code=404, detail="Data source not found")
    return DataSourceResponse(
        id=config.id,
        name=config.name,
        db_type=config.db_type,
        host=config.host,
        port=config.port,
        database=config.database,
        username=config.username,
        connection_pool_size=config.connection_pool_size,
        connection_max_overflow=config.connection_max_overflow,
        connection_timeout=config.connection_timeout,
        ssl_enabled=config.ssl_enabled,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.patch("/{config_id}", response_model=DataSourceResponse)
def update_data_source(config_id: str, req: UpdateDataSourceRequest, current_user=Depends(get_current_user)):
    """Update a data source configuration."""
    updates = req.model_dump(exclude_unset=True)
    updated = data_source_store.update(config_id, updates, user_id=str(current_user.id))
    if not updated:
        raise HTTPException(status_code=404, detail="Data source not found")
    return DataSourceResponse(
        id=updated.id,
        name=updated.name,
        db_type=updated.db_type,
        host=updated.host,
        port=updated.port,
        database=updated.database,
        username=updated.username,
        connection_pool_size=updated.connection_pool_size,
        connection_max_overflow=updated.connection_max_overflow,
        connection_timeout=updated.connection_timeout,
        ssl_enabled=updated.ssl_enabled,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/{config_id}", status_code=204)
def delete_data_source(config_id: str, current_user=Depends(get_current_user)):
    """Delete a data source configuration."""
    if not data_source_store.delete(config_id, user_id=str(current_user.id)):
        raise HTTPException(status_code=404, detail="Data source not found")


@router.post("/{config_id}/test", response_model=ConnectionTestResponse)
def test_connection(config_id: str, current_user=Depends(get_current_user)):
    """Test the connection to a data source. Returns result in < 10s."""
    config = data_source_store.get(config_id, user_id=str(current_user.id))
    if not config:
        raise HTTPException(status_code=404, detail="Data source not found")

    try:
        connector = create_connector(config)
        try:
            result = connector.test_connection()
            return ConnectionTestResponse(
                success=result.success,
                latency_ms=result.latency_ms,
                message=result.message,
                server_version=result.server_version,
            )
        finally:
            connector.close()
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            latency_ms=0,
            message=f"Connector error: {str(e)}",
        )
