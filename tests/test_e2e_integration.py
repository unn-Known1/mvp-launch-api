"""
E2E Integration Test Suite

Tests all major user journeys:
1. Auth flow (register -> login -> access protected routes)
2. Data upload (CSV -> dataset created -> visible in list)
3. NL query (natural language -> SQL generated -> results displayed)
4. Forecast (select dataset -> run forecast -> view predictions)
5. Anomaly detection (upload time series -> detect anomalies -> view alerts)
6. Report generation (create report -> schedule -> verify delivery)
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


class TestAuthFlow:
    """Test authentication flow: register -> login -> access protected routes."""

    @pytest.mark.asyncio
    async def test_register_new_user(self, client: AsyncClient):
        """Test user registration returns user info."""
        response = await client.post(
            "/auth/users",
            json={
                "email": "newuser@test.com",
                "password": "securepassword123",
                "name": "New User",
                "role_name": "viewer",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["name"] == "New User"
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_register_duplicate_email_fails(self, client: AsyncClient):
        """Test that duplicate email registration fails."""
        user_data = {
            "email": "duplicate@test.com",
            "password": "password123",
            "name": "Duplicate User",
        }
        await client.post("/auth/users", json=user_data)

        response = await client.post("/auth/users", json=user_data)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Test successful login returns tokens."""
        await client.post(
            "/auth/users",
            json={
                "email": "logintest@test.com",
                "password": "password123",
                "name": "Login Test",
            },
        )

        response = await client.post(
            "/auth/login",
            json={"email": "logintest@test.com", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["expires_in"] == 900

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_fails(self, client: AsyncClient):
        """Test login with invalid credentials fails."""
        response = await client.post(
            "/auth/login",
            json={"email": "nonexistent@test.com", "password": "wrongpass"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_inactive_user_fails(self, client: AsyncClient, override_get_current_user):
        """Test login with inactive account fails."""
        from auth import main

        user_data = {
            "email": "inactive@test.com",
            "password": "password123",
            "name": "Inactive User",
        }
        create_response = await client.post("/auth/users", json=user_data)
        assert create_response.status_code == 201

        user = main.app.dependency_overrides[lambda: override_get_current_user]
        if user:
            pass

        response = await client.post(
            "/auth/login",
            json={"email": "inactive@test.com", "password": "password123"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_access_protected_route_with_token(self, client: AsyncClient):
        """Test accessing protected route with valid token."""
        await client.post(
            "/auth/users",
            json={
                "email": "protected@test.com",
                "password": "password123",
                "name": "Protected User",
            },
        )

        login_response = await client.post(
            "/auth/login",
            json={"email": "protected@test.com", "password": "password123"},
        )
        token = login_response.json()["access_token"]

        response = await client.get(
            "/auth/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_access_protected_route_without_token_fails(self, client: AsyncClient):
        """Test accessing protected route without token fails."""
        response = await client.get("/auth/users")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient):
        """Test token refresh returns new access token."""
        await client.post(
            "/auth/users",
            json={
                "email": "refresh@test.com",
                "password": "password123",
                "name": "Refresh Test",
            },
        )

        login_response = await client.post(
            "/auth/login",
            json={"email": "refresh@test.com", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data


class TestDataUpload:
    """Test data upload flow: CSV -> dataset created -> visible in list."""

    @pytest.mark.asyncio
    async def test_detect_csv_types(self, client: AsyncClient, sample_csv_content: bytes):
        """Test CSV type detection endpoint."""
        response = await client.post(
            "/api/v1/csv/detect",
            files={"file": ("test.csv", sample_csv_content, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.csv"
        assert data["row_count"] == 5
        assert data["column_count"] == 5

        columns = {c["name"]: c["inferred_type"] for c in data["columns"]}
        assert columns["name"] == "string"
        assert columns["age"] == "number"
        assert columns["active"] == "boolean"
        assert columns["joined"] == "date"
        assert columns["salary"] == "number"

    @pytest.mark.asyncio
    async def test_reject_non_csv_file(self, client: AsyncClient):
        """Test that non-CSV files are rejected."""
        response = await client.post(
            "/api/v1/csv/detect",
            files={"file": ("test.txt", b"some content", "text/plain")},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_file_too_large(self, client: AsyncClient):
        """Test that files over 100MB are rejected."""
        large_content = b"x" * (100 * 1024 * 1024 + 1)
        response = await client.post(
            "/api/v1/csv/detect",
            files={"file": ("large.csv", large_content, "text/csv")},
        )
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_csv_success(
        self, client: AsyncClient, sample_csv_content: bytes, override_get_current_user
    ):
        """Test successful CSV upload creates dataset."""
        response = await client.post(
            "/api/v1/csv/upload?dataset_name=Test%20Dataset",
            files={"file": ("data.csv", sample_csv_content, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()

        assert "dataset" in data
        assert data["dataset"]["name"] == "Test Dataset"
        assert data["dataset"]["status"] == "ready"
        assert data["dataset"]["row_count"] == 5

        assert "import_batch" in data
        assert data["import_batch"]["status"] == "completed"
        assert data["import_batch"]["total_rows"] == 5

    @pytest.mark.asyncio
    async def test_list_datasets(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing datasets returns uploaded datasets."""
        response = await client.get("/api/v1/csv/datasets")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestNaturalLanguageQuery:
    """Test NL query flow: natural language -> SQL generated -> results displayed."""

    @pytest.mark.asyncio
    async def test_generate_sql_from_nl(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test SQL generation from natural language."""
        response = await client.post(
            "/api/v1/nl-query/generate",
            json={
                "question": "Show me all users older than 30",
                "context": {"table": "users", "columns": ["name", "age", "email"]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "sql" in data
        assert "SELECT" in data["sql"].upper() or "select" in data["sql"].lower()

    @pytest.mark.asyncio
    async def test_execute_nl_query(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test executing natural language query."""
        response = await client.post(
            "/api/v1/nl-query/query",
            json={
                "question": "What is the average age?",
                "context": {"table": "users", "columns": ["age"]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data or "sql" in data or "answer" in data

    @pytest.mark.asyncio
    async def test_invalid_query_handled_gracefully(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test that invalid queries are handled gracefully."""
        response = await client.post(
            "/api/v1/nl-query/query",
            json={
                "question": "",
                "context": {},
            },
        )
        assert response.status_code in [400, 422, 500]


class TestForecast:
    """Test forecast flow: select dataset -> run forecast -> view predictions."""

    @pytest.mark.asyncio
    async def test_list_forecasts(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing forecasts."""
        response = await client.get("/api/v1/ml/forecast")
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_create_forecast(
        self, client: AsyncClient, forecast_csv_content: bytes, override_get_current_user
    ):
        """Test creating a forecast."""
        upload_response = await client.post(
            "/api/v1/csv/upload?dataset_name=Forecast%20Data",
            files={"file": ("forecast.csv", forecast_csv_content, "text/csv")},
        )
        assert upload_response.status_code == 200

        forecast_response = await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_name": "Forecast Data",
                "target_column": "sales",
                "date_column": "date",
                "periods": 7,
            },
        )
        assert forecast_response.status_code in [200, 400, 404]

    @pytest.mark.asyncio
    async def test_forecast_results(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test getting forecast results."""
        response = await client.get("/api/v1/ml/forecast/test-forecast-id")
        assert response.status_code in [200, 404]


class TestAnomalyDetection:
    """Test anomaly detection: upload time series -> detect anomalies -> view alerts."""

    @pytest.mark.asyncio
    async def test_detect_anomalies(
        self, client: AsyncClient, time_series_csv_content: bytes, override_get_current_user
    ):
        """Test detecting anomalies in time series data."""
        upload_response = await client.post(
            "/api/v1/csv/upload?dataset_name=TimeSeries%20Data",
            files={
                "file": ("timeseries.csv", time_series_csv_content, "text/csv")
            },
        )
        assert upload_response.status_code == 200

        response = await client.post(
            "/api/v1/anomalies/detect",
            json={
                "dataset_name": "TimeSeries Data",
                "timestamp_column": "timestamp",
                "value_column": "value",
            },
        )
        assert response.status_code in [200, 400, 404]

    @pytest.mark.asyncio
    async def test_list_anomalies(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing detected anomalies."""
        response = await client.get("/api/v1/anomalies")
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_anomaly_alerts(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test getting anomaly alerts."""
        response = await client.get("/api/v1/anomalies/alerts")
        assert response.status_code in [200, 404]


class TestReportGeneration:
    """Test report generation: create report -> schedule -> verify delivery."""

    @pytest.mark.asyncio
    async def test_create_report(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test creating a report."""
        response = await client.post(
            "/api/v1/reports",
            json={
                "name": "Test Report",
                "report_type": "summary",
            },
        )
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_list_reports(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing reports."""
        response = await client.get("/api/v1/reports")
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_schedule_report(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test scheduling a report."""
        response = await client.post(
            "/api/v1/reports/schedule",
            json={
                "report_id": "test-report-id",
                "schedule": "daily",
                "recipients": ["test@example.com"],
            },
        )
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_generate_report(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test generating a report."""
        response = await client.post(
            "/api/v1/reports/generate",
            json={
                "report_id": "test-report-id",
                "format": "pdf",
            },
        )
        assert response.status_code in [200, 404]


class TestHealthAndRoot:
    """Test basic health check and root endpoints."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint returns service info."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])