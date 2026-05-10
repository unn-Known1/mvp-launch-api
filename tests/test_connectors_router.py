"""
Tests for connectors/router.py - Data source management endpoints.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from connectors.router import (
    CreateDataSourceRequest,
    UpdateDataSourceRequest,
    DataSourceResponse,
    ConnectionTestResponse,
    create_data_source,
    list_data_sources,
    get_data_source,
    update_data_source,
    delete_data_source,
    test_connection,
)
from connectors.base import DataSourceConfig


class TestCreateDataSource:
    """Tests for POST /api/v1/datasources"""

    def test_create_data_source_success(self):
        """Test successful data source creation."""
        mock_config = MagicMock(spec=DataSourceConfig)
        mock_config.id = "ds-123"
        mock_config.name = "Production DB"
        mock_config.db_type = "postgresql"
        mock_config.host = "db.example.com"
        mock_config.port = 5432
        mock_config.database = "mydb"
        mock_config.username = "admin"
        mock_config.password = "secret"
        mock_config.connection_pool_size = 10
        mock_config.connection_max_overflow = 20
        mock_config.connection_timeout = 30
        mock_config.ssl_enabled = True
        mock_config.extra_params = {}
        mock_config.created_at = datetime.now(timezone.utc).isoformat()
        mock_config.updated_at = None

        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.create.return_value = mock_config

        req = CreateDataSourceRequest(
            name="Production DB",
            db_type="postgresql",
            host="db.example.com",
            port=5432,
            database="mydb",
            username="admin",
            password="secret",
            connection_pool_size=10,
            connection_max_overflow=20,
            connection_timeout=30,
            ssl_enabled=True
        )

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                response = create_data_source(req, mock_current_user)

        assert response.name == "Production DB"
        assert response.db_type == "postgresql"
        assert response.host == "db.example.com"
        mock_store.create.assert_called_once()

    def test_create_data_source_invalid_db_type(self):
        """Test data source creation fails with invalid db_type."""
        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        req = CreateDataSourceRequest(
            name="Invalid DB",
            db_type="oracle",  # Not supported
            host="db.example.com",
            port=1521,
            database="mydb",
            username="admin",
            password="secret"
        )

        with pytest.raises(ValueError):
            create_data_source(req, mock_current_user)

    def test_create_data_source_invalid_port(self):
        """Test data source creation fails with invalid port."""
        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        req = CreateDataSourceRequest(
            name="Test DB",
            db_type="postgresql",
            host="db.example.com",
            port=70000,  # Invalid port
            database="mydb",
            username="admin",
            password="secret"
        )

        with pytest.raises(ValueError):
            create_data_source(req, mock_current_user)


class TestListDataSources:
    """Tests for GET /api/v1/datasources"""

    def test_list_data_sources_success(self):
        """Test successful data source listing."""
        mock_config1 = MagicMock(spec=DataSourceConfig)
        mock_config1.id = "ds-1"
        mock_config1.name = "Production"
        mock_config1.db_type = "postgresql"
        mock_config1.host = "prod.example.com"
        mock_config1.port = 5432
        mock_config1.database = "proddb"
        mock_config1.username = "prod_user"
        mock_config1.connection_pool_size = 10
        mock_config1.connection_max_overflow = 20
        mock_config1.connection_timeout = 30
        mock_config1.ssl_enabled = True
        mock_config1.created_at = datetime.now(timezone.utc).isoformat()
        mock_config1.updated_at = None

        mock_config2 = MagicMock(spec=DataSourceConfig)
        mock_config2.id = "ds-2"
        mock_config2.name = "Staging"
        mock_config2.db_type = "mysql"
        mock_config2.host = "staging.example.com"
        mock_config2.port = 3306
        mock_config2.database = "stagingdb"
        mock_config2.username = "staging_user"
        mock_config2.connection_pool_size = 5
        mock_config2.connection_max_overflow = 10
        mock_config2.connection_timeout = 20
        mock_config2.ssl_enabled = False
        mock_config2.created_at = datetime.now(timezone.utc).isoformat()
        mock_config2.updated_at = None

        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.list_all.return_value = [mock_config1, mock_config2]

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                response = list_data_sources(mock_current_user)

        assert len(response) == 2
        assert response[0].name == "Production"
        assert response[1].db_type == "mysql"

    def test_list_data_sources_empty(self):
        """Test listing when no data sources exist."""
        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.list_all.return_value = []

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                response = list_data_sources(mock_current_user)

        assert len(response) == 0


class TestGetDataSource:
    """Tests for GET /api/v1/datasources/{config_id}"""

    def test_get_data_source_success(self):
        """Test successful data source retrieval."""
        mock_config = MagicMock(spec=DataSourceConfig)
        mock_config.id = "ds-123"
        mock_config.name = "Production DB"
        mock_config.db_type = "postgresql"
        mock_config.host = "db.example.com"
        mock_config.port = 5432
        mock_config.database = "mydb"
        mock_config.username = "admin"
        mock_config.connection_pool_size = 10
        mock_config.connection_max_overflow = 20
        mock_config.connection_timeout = 30
        mock_config.ssl_enabled = True
        mock_config.created_at = datetime.now(timezone.utc).isoformat()
        mock_config.updated_at = None

        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.get.return_value = mock_config

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                response = get_data_source("ds-123", mock_current_user)

        assert response.id == "ds-123"
        assert response.name == "Production DB"

    def test_get_data_source_not_found(self):
        """Test data source retrieval for non-existent ID."""
        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.get.return_value = None

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                with pytest.raises(HTTPException) as exc_info:
                    get_data_source("non-existent-id", mock_current_user)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail


class TestUpdateDataSource:
    """Tests for PATCH /api/v1/datasources/{config_id}"""

    def test_update_data_source_success(self):
        """Test successful data source update."""
        mock_config = MagicMock(spec=DataSourceConfig)
        mock_config.id = "ds-123"
        mock_config.name = "Old Name"
        mock_config.db_type = "postgresql"
        mock_config.host = "old.example.com"
        mock_config.port = 5432
        mock_config.database = "mydb"
        mock_config.username = "admin"
        mock_config.connection_pool_size = 10
        mock_config.connection_max_overflow = 20
        mock_config.connection_timeout = 30
        mock_config.ssl_enabled = False
        mock_config.created_at = datetime.now(timezone.utc).isoformat()
        mock_config.updated_at = datetime.now(timezone.utc).isoformat()

        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.update.return_value = mock_config

        req = UpdateDataSourceRequest(
            name="New Name",
            host="new.example.com",
            ssl_enabled=True
        )

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                response = update_data_source("ds-123", req, mock_current_user)

        mock_store.update.assert_called_once()
        call_args = mock_store.update.call_args
        assert call_args[0][0] == "ds-123"
        assert "New Name" in call_args[0][1].get("name", "")

    def test_update_data_source_not_found(self):
        """Test updating non-existent data source."""
        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.update.return_value = None

        req = UpdateDataSourceRequest(name="New Name")

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                with pytest.raises(HTTPException) as exc_info:
                    update_data_source("non-existent-id", req, mock_current_user)

        assert exc_info.value.status_code == 404


class TestDeleteDataSource:
    """Tests for DELETE /api/v1/datasources/{config_id}"""

    def test_delete_data_source_success(self):
        """Test successful data source deletion."""
        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.delete.return_value = True

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                response = delete_data_source("ds-123", mock_current_user)

        assert response is None  # 204 No Content
        mock_store.delete.assert_called_once_with("ds-123", user_id="user-123")

    def test_delete_data_source_not_found(self):
        """Test deleting non-existent data source."""
        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.delete.return_value = False

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                with pytest.raises(HTTPException) as exc_info:
                    delete_data_source("non-existent-id", mock_current_user)

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail


class TestTestConnection:
    """Tests for POST /api/v1/datasources/{config_id}/test"""

    def test_test_connection_success(self):
        """Test successful connection test."""
        mock_config = MagicMock(spec=DataSourceConfig)
        mock_config.id = "ds-123"

        mock_connector = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.latency_ms = 45.2
        mock_result.message = "Connection successful"
        mock_result.server_version = "PostgreSQL 14.5"
        mock_connector.test_connection.return_value = mock_result

        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.get.return_value = mock_config

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.create_connector", return_value=mock_connector):
                with patch("connectors.router.get_current_user", return_value=mock_current_user):
                    response = test_connection("ds-123", mock_current_user)

        assert response.success is True
        assert response.latency_ms == 45.2
        assert response.server_version == "PostgreSQL 14.5"

    def test_test_connection_failure(self):
        """Test connection test failure."""
        mock_config = MagicMock(spec=DataSourceConfig)
        mock_config.id = "ds-123"

        mock_connector = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.latency_ms = 0
        mock_result.message = "Connection refused"
        mock_result.server_version = None
        mock_connector.test_connection.return_value = mock_result

        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.get.return_value = mock_config

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.create_connector", return_value=mock_connector):
                with patch("connectors.router.get_current_user", return_value=mock_current_user):
                    response = test_connection("ds-123", mock_current_user)

        assert response.success is False
        assert "refused" in response.message.lower()

    def test_test_connection_datasource_not_found(self):
        """Test connection test for non-existent data source."""
        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.get.return_value = None

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.get_current_user", return_value=mock_current_user):
                with pytest.raises(HTTPException) as exc_info:
                    test_connection("non-existent-id", mock_current_user)

        assert exc_info.value.status_code == 404

    def test_test_connection_exception_handling(self):
        """Test connection test handles connector exceptions gracefully."""
        mock_config = MagicMock(spec=DataSourceConfig)
        mock_config.id = "ds-123"

        mock_current_user = MagicMock()
        mock_current_user.id = "user-123"

        mock_store = MagicMock()
        mock_store.get.return_value = mock_config

        with patch("connectors.router.data_source_store", mock_store):
            with patch("connectors.router.create_connector", side_effect=Exception("Connector error")):
                with patch("connectors.router.get_current_user", return_value=mock_current_user):
                    response = test_connection("ds-123", mock_current_user)

        assert response.success is False
        assert "Connector error" in response.message


class TestDataSourceResponseModel:
    """Tests for DataSourceResponse model."""

    def test_data_source_response_fields(self):
        """Test DataSourceResponse contains all required fields."""
        response = DataSourceResponse(
            id="ds-123",
            name="Test DB",
            db_type="postgresql",
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser",
            connection_pool_size=5,
            connection_max_overflow=10,
            connection_timeout=30,
            ssl_enabled=True,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=None
        )

        assert response.id == "ds-123"
        assert response.name == "Test DB"
        assert response.port == 5432
        assert response.ssl_enabled is True

    def test_connection_test_response_fields(self):
        """Test ConnectionTestResponse contains all required fields."""
        response = ConnectionTestResponse(
            success=True,
            latency_ms=25.5,
            message="Connected successfully",
            server_version="PostgreSQL 15.2"
        )

        assert response.success is True
        assert response.latency_ms == 25.5
        assert response.server_version == "PostgreSQL 15.2"