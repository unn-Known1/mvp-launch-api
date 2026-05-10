"""
E2E Integration Test Suite

Tests all major user journeys:
1. Auth flow (register -> login -> access protected routes -> logout -> refresh)
2. Data upload (CSV -> dataset created -> visible in list)
3. NL query (natural language -> SQL generated -> results displayed)
4. Forecast (select dataset -> run forecast -> view predictions -> download/backtest)
5. Anomaly detection (upload time series -> detect anomalies -> manage thresholds)
6. Report generation (create template -> schedule -> pause/resume -> verify delivery)
7. Role management (list roles, get role by ID)
8. Health & root endpoints
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


# =============================================================================
# Auth Flow
# =============================================================================

class TestAuthFlow:
    """Test authentication flow: register -> login -> access protected routes."""

    @pytest.mark.asyncio
    async def test_register_new_user(self, client: AsyncClient):
        """Test user registration returns user info."""
        response = await client.post(
            "/api/v1/auth/users",
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
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email_fails(self, client: AsyncClient):
        """Test that duplicate email registration fails."""
        user_data = {
            "email": "duplicate@test.com",
            "password": "password123",
            "name": "Duplicate User",
        }
        await client.post("/api/v1/auth/users", json=user_data)

        response = await client.post("/api/v1/auth/users", json=user_data)
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Test successful login returns tokens."""
        await client.post(
            "/api/v1/auth/users",
            json={
                "email": "logintest@test.com",
                "password": "password123",
                "name": "Login Test",
            },
        )

        response = await client.post(
            "/api/v1/auth/login",
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
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "wrongpass"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_empty_password_fails(self, client: AsyncClient):
        """Test login with empty password fails validation."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": ""},
        )
        assert response.status_code in (401, 422)

    @pytest.mark.asyncio
    async def test_access_protected_route_with_token(self, client: AsyncClient):
        """Test accessing protected route with valid token."""
        await client.post(
            "/api/v1/auth/users",
            json={
                "email": "protected@test.com",
                "password": "password123",
                "name": "Protected User",
            },
        )

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "protected@test.com", "password": "password123"},
        )
        token = login_response.json()["access_token"]

        response = await client.get(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_access_protected_route_without_token_fails(self, client: AsyncClient):
        """Test accessing protected route without token fails."""
        response = await client.get("/api/v1/auth/users")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient):
        """Test token refresh returns new access token."""
        await client.post(
            "/api/v1/auth/users",
            json={
                "email": "refresh@test.com",
                "password": "password123",
                "name": "Refresh Test",
            },
        )

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": "refresh@test.com", "password": "password123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["expires_in"] == 900

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_fails(self, client: AsyncClient):
        """Test token refresh with an invalid token is rejected."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-valid-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_blacklists_token(self, client: AsyncClient):
        """Test logout blacklists the access token."""
        await client.post(
            "/api/v1/auth/users",
            json={
                "email": "logout@test.com",
                "password": "password123",
                "name": "Logout Test",
            },
        )

        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "logout@test.com", "password": "password123"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        logout_resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout_resp.status_code == 200
        assert logout_resp.json()["message"] == "Logout successful"

    @pytest.mark.asyncio
    async def test_register_user_defaults_to_viewer_role(self, client: AsyncClient):
        """Test registering without role_name defaults to viewer."""
        response = await client.post(
            "/api/v1/auth/users",
            json={
                "email": "defaultviewer@test.com",
                "password": "password123",
                "name": "Default Viewer",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "viewer"


# =============================================================================
# Data Upload
# =============================================================================

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
    async def test_detect_csv_preview_contains_rows(self, client: AsyncClient, sample_csv_content: bytes):
        """Test CSV detection returns preview data."""
        response = await client.post(
            "/api/v1/csv/detect",
            files={"file": ("preview.csv", sample_csv_content, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "preview" in data
        assert len(data["preview"]) > 0
        assert data["preview"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_reject_non_csv_file(self, client: AsyncClient):
        """Test that non-CSV files are rejected."""
        response = await client.post(
            "/api/v1/csv/detect",
            files={"file": ("test.txt", b"some content", "text/plain")},
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

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
    async def test_reject_malformed_csv(self, client: AsyncClient):
        """Test that malformed CSV is rejected gracefully."""
        response = await client.post(
            "/api/v1/csv/detect",
            files={"file": ("bad.csv", b"\xff\xfe\x00\x01", "text/csv")},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_detect_empty_csv(self, client: AsyncClient):
        """Test empty CSV file is handled."""
        response = await client.post(
            "/api/v1/csv/detect",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert response.status_code in (200, 400)

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
        assert data["import_batch"]["processed_rows"] == 5

        assert "detection" in data
        assert data["detection"]["filename"] == "data.csv"

    @pytest.mark.asyncio
    async def test_upload_csv_without_name_uses_filename(
        self, client: AsyncClient, sample_csv_content: bytes, override_get_current_user
    ):
        """Test uploading without dataset_name uses the filename."""
        response = await client.post(
            "/api/v1/csv/upload",
            files={"file": ("unnamed.csv", sample_csv_content, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset"]["name"] == "unnamed.csv"

    @pytest.mark.asyncio
    async def test_upload_non_csv_rejected(self, client: AsyncClient, override_get_current_user):
        """Test upload with non-CSV file is rejected."""
        response = await client.post(
            "/api/v1/csv/upload",
            files={"file": ("data.txt", b"name,age\nAlice,30", "text/plain")},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_csv_with_description(
        self, client: AsyncClient, sample_csv_content: bytes, override_get_current_user
    ):
        """Test uploading CSV with a custom description."""
        response = await client.post(
            "/api/v1/csv/upload?dataset_name=Desc%20Test&description=My%20dataset%20description",
            files={"file": ("desc.csv", sample_csv_content, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dataset"]["description"] == "My dataset description"

    @pytest.mark.asyncio
    async def test_list_datasets(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing datasets returns uploaded datasets."""
        response = await client.get("/api/v1/csv/datasets")
        assert response.status_code == 200
        datasets = response.json()
        assert isinstance(datasets, list)


# =============================================================================
# Natural Language Query
# =============================================================================

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
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_query_history_structure(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test query history endpoint returns a list."""
        response = await client.get("/api/v1/nl-query/history")
        assert response.status_code == 200
        data = response.json()
        assert "queries" in data
        assert "total" in data
        assert isinstance(data["queries"], list)

    @pytest.mark.asyncio
    async def test_recent_queries_endpoint(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test recent queries endpoint returns a list."""
        response = await client.get("/api/v1/nl-query/recent")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# =============================================================================
# Forecast
# =============================================================================

class TestForecast:
    """Test forecast flow: upload CSV -> create forecast -> verify predictions."""

    @pytest.mark.asyncio
    async def test_upload_and_create_forecast(
        self, client: AsyncClient, forecast_csv_extended_content: bytes, override_get_current_user
    ):
        """Upload a CSV with enough data points, create a forecast, verify response structure."""
        upload_resp = await client.post(
            "/api/v1/csv/upload?dataset_name=Forecast%20E2E",
            files={"file": ("forecast.csv", forecast_csv_extended_content, "text/csv")},
        )
        assert upload_resp.status_code == 200
        upload_data = upload_resp.json()
        dataset_id = upload_data["dataset"]["id"]

        forecast_resp = await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_id": dataset_id,
                "target_column": "sales",
                "periods": 7,
                "frequency": "D",
            },
        )
        assert forecast_resp.status_code == 201
        data = forecast_resp.json()

        assert data["dataset_id"] == dataset_id
        assert data["target_column"] == "sales"
        assert data["periods"] == 7
        assert data["frequency"] == "D"
        assert data["status"] == "completed"
        assert len(data["predictions"]) > 0
        assert "ds" in data["predictions"][0]
        assert "yhat" in data["predictions"][0]
        assert data["model_metrics"] is not None
        assert "mae" in data["model_metrics"]
        assert "rmse" in data["model_metrics"]

    @pytest.mark.asyncio
    async def test_forecast_includes_model_version_in_metrics(
        self, client: AsyncClient, forecast_csv_extended_content: bytes, override_get_current_user
    ):
        """Test forecast model_metrics includes model_version."""
        upload_resp = await client.post(
            "/api/v1/csv/upload?dataset_name=Forecast%20ModelVer",
            files={"file": ("ver.csv", forecast_csv_extended_content, "text/csv")},
        )
        assert upload_resp.status_code == 200
        dataset_id = upload_resp.json()["dataset"]["id"]

        forecast_resp = await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_id": dataset_id,
                "target_column": "sales",
                "periods": 5,
                "frequency": "D",
            },
        )
        assert forecast_resp.status_code == 201
        data = forecast_resp.json()
        assert "model_version" in data["model_metrics"]
        assert isinstance(data["model_metrics"]["model_version"], str)
        assert len(data["model_metrics"]["model_version"]) > 0

    @pytest.mark.asyncio
    async def test_get_forecast_by_id(
        self, client: AsyncClient, forecast_csv_extended_content: bytes, override_get_current_user
    ):
        """Create a forecast then retrieve it by ID and verify structure."""
        upload_resp = await client.post(
            "/api/v1/csv/upload?dataset_name=Forecast%20GetByID",
            files={"file": ("forecast.csv", forecast_csv_extended_content, "text/csv")},
        )
        assert upload_resp.status_code == 200
        dataset_id = upload_resp.json()["dataset"]["id"]

        create_resp = await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_id": dataset_id,
                "target_column": "sales",
                "periods": 14,
                "frequency": "D",
            },
        )
        assert create_resp.status_code == 201
        forecast_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/ml/forecast/{forecast_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == forecast_id
        assert data["status"] == "completed"
        assert len(data["predictions"]) > 0

    @pytest.mark.asyncio
    async def test_get_forecast_not_found(self, client: AsyncClient, override_get_current_user):
        """Test getting a non-existent forecast returns 404."""
        response = await client.get("/api/v1/ml/forecast/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_forecasts(
        self, client: AsyncClient, forecast_csv_extended_content: bytes, override_get_current_user
    ):
        """Upload CSV, create forecast, verify it appears in the list."""
        upload_resp = await client.post(
            "/api/v1/csv/upload?dataset_name=Forecast%20List",
            files={"file": ("forecast.csv", forecast_csv_extended_content, "text/csv")},
        )
        assert upload_resp.status_code == 200
        dataset_id = upload_resp.json()["dataset"]["id"]

        await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_id": dataset_id,
                "target_column": "sales",
                "periods": 7,
                "frequency": "D",
            },
        )

        list_resp = await client.get("/api/v1/ml/forecast")
        assert list_resp.status_code == 200
        forecasts = list_resp.json()
        assert isinstance(forecasts, list)
        assert len(forecasts) >= 1

    @pytest.mark.asyncio
    async def test_forecast_with_insufficient_data_returns_400(
        self, client: AsyncClient, forecast_csv_content: bytes, override_get_current_user
    ):
        """Upload CSV with fewer than 30 data points; forecast should return 400."""
        upload_resp = await client.post(
            "/api/v1/csv/upload?dataset_name=Forecast%20Short",
            files={"file": ("short.csv", forecast_csv_content, "text/csv")},
        )
        assert upload_resp.status_code == 200
        dataset_id = upload_resp.json()["dataset"]["id"]

        forecast_resp = await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_id": dataset_id,
                "target_column": "sales",
                "periods": 7,
                "frequency": "D",
            },
        )
        assert forecast_resp.status_code == 400
        assert "Insufficient data" in forecast_resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_forecast_with_nonexistent_dataset_returns_404(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test forecasting with a non-existent dataset ID returns 404."""
        response = await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_id": "00000000-0000-0000-0000-000000000000",
                "target_column": "sales",
                "periods": 7,
                "frequency": "D",
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_forecast_download_csv(
        self, client: AsyncClient, forecast_csv_extended_content: bytes, override_get_current_user
    ):
        """Test downloading a forecast as CSV."""
        upload_resp = await client.post(
            "/api/v1/csv/upload?dataset_name=Forecast%20Download",
            files={"file": ("dl.csv", forecast_csv_extended_content, "text/csv")},
        )
        assert upload_resp.status_code == 200
        dataset_id = upload_resp.json()["dataset"]["id"]

        create_resp = await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_id": dataset_id,
                "target_column": "sales",
                "periods": 5,
                "frequency": "D",
            },
        )
        assert create_resp.status_code == 201
        forecast_id = create_resp.json()["id"]

        download_resp = await client.get(f"/api/v1/ml/forecast/{forecast_id}/download")
        assert download_resp.status_code == 200
        assert download_resp.headers["content-type"] == "text/csv"
        assert "forecast" in download_resp.headers.get("content-disposition", "").lower()
        assert len(download_resp.content) > 0

    @pytest.mark.asyncio
    async def test_forecast_download_nonexistent_returns_404(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test downloading a non-existent forecast CSV returns 404."""
        response = await client.get(
            "/api/v1/ml/forecast/00000000-0000-0000-0000-000000000000/download"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_forecast_backtest(
        self, client: AsyncClient, forecast_csv_extended_content: bytes, override_get_current_user
    ):
        """Test backtesting a forecast."""
        upload_resp = await client.post(
            "/api/v1/csv/upload?dataset_name=Forecast%20Backtest",
            files={"file": ("bt.csv", forecast_csv_extended_content, "text/csv")},
        )
        assert upload_resp.status_code == 200
        dataset_id = upload_resp.json()["dataset"]["id"]

        create_resp = await client.post(
            "/api/v1/ml/forecast",
            json={
                "dataset_id": dataset_id,
                "target_column": "sales",
                "periods": 5,
                "frequency": "D",
            },
        )
        assert create_resp.status_code == 201
        forecast_id = create_resp.json()["id"]

        backtest_resp = await client.get(f"/api/v1/ml/forecast/{forecast_id}/backtest")
        assert backtest_resp.status_code == 200
        data = backtest_resp.json()
        assert "train_size" in data
        assert "test_size" in data
        assert "metrics" in data
        assert data["train_size"] > 0
        assert "mae" in data["metrics"]
        assert "rmse" in data["metrics"]

    @pytest.mark.asyncio
    async def test_forecast_backtest_nonexistent_returns_404(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test backtesting a non-existent forecast returns 404."""
        response = await client.get(
            "/api/v1/ml/forecast/00000000-0000-0000-0000-000000000000/backtest"
        )
        assert response.status_code == 404


# =============================================================================
# Anomaly Detection
# =============================================================================

class TestAnomalyDetection:
    """Test anomaly detection: upload time series -> detect anomalies -> manage alerts."""

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
        assert response.status_code in (200, 400, 422)

    @pytest.mark.asyncio
    async def test_scan_anomalies_endpoint(
        self, client: AsyncClient, time_series_csv_content: bytes, override_get_current_user
    ):
        """Test the /anomalies/scan endpoint returns proper structure."""
        upload_response = await client.post(
            "/api/v1/csv/upload?dataset_name=TimeSeries%20Scan",
            files={"file": ("scan.csv", time_series_csv_content, "text/csv")},
        )
        assert upload_response.status_code == 200

        scan_resp = await client.post("/api/v1/anomalies/scan")
        assert scan_resp.status_code == 200
        data = scan_resp.json()
        assert "scanned_datasets" in data
        assert "total_anomalies_found" in data
        assert "anomalies_by_dataset" in data
        assert data["scanned_datasets"] >= 0
        assert isinstance(data["total_anomalies_found"], int)
        assert isinstance(data["anomalies_by_dataset"], dict)

    @pytest.mark.asyncio
    async def test_scan_anomalies_with_dataset_id_filter(
        self, client: AsyncClient, time_series_csv_content: bytes, override_get_current_user
    ):
        """Test the /anomalies/scan endpoint with a dataset_id filter."""
        upload_response = await client.post(
            "/api/v1/csv/upload?dataset_name=TimeSeries%20ScanFilter",
            files={"file": ("filter.csv", time_series_csv_content, "text/csv")},
        )
        assert upload_response.status_code == 200
        dataset_id = upload_response.json()["dataset"]["id"]

        scan_resp = await client.post(f"/api/v1/anomalies/scan?dataset_id={dataset_id}")
        assert scan_resp.status_code == 200
        data = scan_resp.json()
        assert data["scanned_datasets"] >= 0

    @pytest.mark.asyncio
    async def test_list_anomalies(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing detected anomalies."""
        response = await client.get("/api/v1/anomalies/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_anomaly_alerts(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test getting anomaly alerts/notifications."""
        response = await client.get("/api/v1/anomalies/notifications")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_anomaly_alerts_unread_filter(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test anomaly notifications filtered by unread."""
        response = await client.get("/api/v1/anomalies/notifications?unread_only=true")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_create_anomaly_threshold(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test creating or updating an anomaly detection threshold."""
        response = await client.post(
            "/api/v1/anomalies/thresholds",
            json={
                "metric_name": "cpu_usage",
                "z_score_threshold": 3,
                "iqr_multiplier": 3,
                "enabled": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["metric_name"] == "cpu_usage"
        assert data["z_score_threshold"] == 3
        assert data["iqr_multiplier"] == 3
        assert data["enabled"] is True
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_anomaly_threshold_custom_values(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test creating a threshold with custom z-score and IQR."""
        response = await client.post(
            "/api/v1/anomalies/thresholds",
            json={
                "metric_name": "memory_usage",
                "z_score_threshold": 2,
                "iqr_multiplier": 2,
                "enabled": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["z_score_threshold"] == 2
        assert data["iqr_multiplier"] == 2

    @pytest.mark.asyncio
    async def test_create_threshold_disabled(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test creating a disabled threshold."""
        response = await client.post(
            "/api/v1/anomalies/thresholds",
            json={
                "metric_name": "disk_io",
                "z_score_threshold": 3,
                "iqr_multiplier": 3,
                "enabled": False,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["enabled"] is False

    @pytest.mark.asyncio
    async def test_list_anomaly_thresholds(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing anomaly detection thresholds."""
        response = await client.get("/api/v1/anomalies/thresholds")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_update_anomaly_not_found(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test updating a non-existent anomaly returns 404."""
        response = await client.patch(
            "/api/v1/anomalies/00000000-0000-0000-0000-000000000000",
            json={"status": "dismissed"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_notification_read_not_found(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test marking a non-existent notification as read returns 404."""
        response = await client.post(
            "/api/v1/anomalies/notifications/00000000-0000-0000-0000-000000000000/read"
        )
        assert response.status_code == 404


# =============================================================================
# Report Generation
# =============================================================================

class TestReportGeneration:
    """Test report generation: create template -> schedule -> run -> verify delivery."""

    @pytest.mark.asyncio
    async def test_create_report_template(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test creating a report template with config."""
        response = await client.post(
            "/api/v1/reports/templates",
            json={
                "name": "Weekly Summary",
                "description": "Weekly summary of key metrics",
                "config": {
                    "queries": [],
                    "charts": [],
                    "datasets": ["users", "transactions"],
                    "include_ai_summary": True,
                    "include_csv_export": True,
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Weekly Summary"
        assert data["description"] == "Weekly summary of key metrics"
        assert "id" in data
        assert data["config"]["include_ai_summary"] is True

    @pytest.mark.asyncio
    async def test_create_report_template_without_config_defaults(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test creating a template with minimal config."""
        response = await client.post(
            "/api/v1/reports/templates",
            json={
                "name": "Minimal Template",
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Template"

    @pytest.mark.asyncio
    async def test_list_report_templates(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing report templates returns created templates."""
        await client.post(
            "/api/v1/reports/templates",
            json={
                "name": "Template A",
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        response = await client.get("/api/v1/reports/templates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "name" in data[0]
            assert "config" in data[0]
            assert "id" in data[0]

    @pytest.mark.asyncio
    async def test_get_report_template_by_id(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test getting a specific report template by ID."""
        create_resp = await client.post(
            "/api/v1/reports/templates",
            json={
                "name": "Get By ID Template",
                "config": {"queries": [], "charts": [], "datasets": ["test"]},
            },
        )
        assert create_resp.status_code == 201
        template_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/reports/templates/{template_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == template_id
        assert data["name"] == "Get By ID Template"

    @pytest.mark.asyncio
    async def test_get_report_template_not_found(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test getting a non-existent template returns 404."""
        response = await client.get(
            "/api/v1/reports/templates/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_report_template(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test updating a report template."""
        create_resp = await client.post(
            "/api/v1/reports/templates",
            json={
                "name": "Original Template",
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert create_resp.status_code == 201
        template_id = create_resp.json()["id"]

        update_resp = await client.put(
            f"/api/v1/reports/templates/{template_id}",
            json={
                "name": "Updated Template",
                "config": {"queries": [], "charts": [], "datasets": ["users"]},
            },
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["name"] == "Updated Template"
        assert data["config"]["datasets"] == ["users"]

    @pytest.mark.asyncio
    async def test_delete_report_template(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test deleting a report template."""
        create_resp = await client.post(
            "/api/v1/reports/templates",
            json={
                "name": "Delete Me Template",
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert create_resp.status_code == 201
        template_id = create_resp.json()["id"]

        delete_resp = await client.delete(
            f"/api/v1/reports/templates/{template_id}"
        )
        assert delete_resp.status_code == 200

        get_resp = await client.get(
            f"/api/v1/reports/templates/{template_id}"
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_schedule_report(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test scheduling a report with frequency and recipients."""
        response = await client.post(
            "/api/v1/reports/scheduled",
            json={
                "name": "Daily Report",
                "description": "Automated daily report",
                "frequency": "daily",
                "time_of_day": "08:00",
                "timezone": "UTC",
                "recipients": ["admin@example.com"],
                "config": {
                    "queries": [],
                    "charts": [],
                    "datasets": ["sales"],
                    "include_ai_summary": True,
                    "include_csv_export": True,
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Daily Report"
        assert data["frequency"] == "daily"
        assert data["is_active"] is True
        assert "next_run_at" in data
        assert data["recipients"] == ["admin@example.com"]

    @pytest.mark.asyncio
    async def test_schedule_weekly_report(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test scheduling a weekly report."""
        response = await client.post(
            "/api/v1/reports/scheduled",
            json={
                "name": "Weekly Report",
                "frequency": "weekly",
                "time_of_day": "09:00",
                "timezone": "America/New_York",
                "recipients": ["weekly@example.com"],
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Weekly Report"
        assert data["frequency"] == "weekly"
        assert data["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_schedule_report_invalid_email_fails(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test scheduling with invalid email is rejected."""
        response = await client.post(
            "/api/v1/reports/scheduled",
            json={
                "name": "Bad Report",
                "frequency": "daily",
                "time_of_day": "08:00",
                "recipients": ["not-an-email"],
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_list_scheduled_reports(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing scheduled reports."""
        response = await client.get("/api/v1/reports/scheduled")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "name" in data[0]
            assert "frequency" in data[0]
            assert "is_active" in data[0]

    @pytest.mark.asyncio
    async def test_list_scheduled_reports_active_filter(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test listing only active scheduled reports."""
        response = await client.get("/api/v1/reports/scheduled?is_active=true")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_scheduled_report_by_id(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test getting a specific scheduled report by ID."""
        create_resp = await client.post(
            "/api/v1/reports/scheduled",
            json={
                "name": "Get By ID Scheduled",
                "frequency": "daily",
                "time_of_day": "10:00",
                "timezone": "UTC",
                "recipients": ["test@example.com"],
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert create_resp.status_code == 201
        report_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/reports/scheduled/{report_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["id"] == report_id
        assert data["name"] == "Get By ID Scheduled"

    @pytest.mark.asyncio
    async def test_get_scheduled_report_not_found(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test getting a non-existent scheduled report returns 404."""
        response = await client.get(
            "/api/v1/reports/scheduled/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_scheduled_report(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test updating a scheduled report."""
        create_resp = await client.post(
            "/api/v1/reports/scheduled",
            json={
                "name": "Update Me Report",
                "frequency": "daily",
                "time_of_day": "08:00",
                "timezone": "UTC",
                "recipients": ["old@example.com"],
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert create_resp.status_code == 201
        report_id = create_resp.json()["id"]

        update_resp = await client.put(
            f"/api/v1/reports/scheduled/{report_id}",
            json={
                "name": "Updated Report",
                "recipients": ["new@example.com"],
                "is_active": False,
            },
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["name"] == "Updated Report"
        assert data["recipients"] == ["new@example.com"]
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_delete_scheduled_report(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test deleting a scheduled report."""
        create_resp = await client.post(
            "/api/v1/reports/scheduled",
            json={
                "name": "Delete Me Scheduled",
                "frequency": "daily",
                "time_of_day": "08:00",
                "timezone": "UTC",
                "recipients": ["delete@example.com"],
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert create_resp.status_code == 201
        report_id = create_resp.json()["id"]

        delete_resp = await client.delete(
            f"/api/v1/reports/scheduled/{report_id}"
        )
        assert delete_resp.status_code == 200

        get_resp = await client.get(
            f"/api/v1/reports/scheduled/{report_id}"
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_pause_and_resume_scheduled_report(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test pausing and resuming a scheduled report."""
        create_resp = await client.post(
            "/api/v1/reports/scheduled",
            json={
                "name": "Pause Test Report",
                "frequency": "daily",
                "time_of_day": "08:00",
                "timezone": "UTC",
                "recipients": ["test@example.com"],
                "config": {"queries": [], "charts": [], "datasets": []},
            },
        )
        assert create_resp.status_code == 201
        report_id = create_resp.json()["id"]

        pause_resp = await client.post(
            f"/api/v1/reports/scheduled/{report_id}/pause"
        )
        assert pause_resp.status_code == 200
        assert pause_resp.json()["detail"] == "Report paused"

        resume_resp = await client.post(
            f"/api/v1/reports/scheduled/{report_id}/resume"
        )
        assert resume_resp.status_code == 200
        assert resume_resp.json()["detail"] == "Report resumed"

    @pytest.mark.asyncio
    async def test_pause_nonexistent_report_returns_404(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test pausing a non-existent report returns 404."""
        response = await client.post(
            "/api/v1/reports/scheduled/00000000-0000-0000-0000-000000000000/pause"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_run_scheduled_report_and_check_delivery(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test running a scheduled report and verifying delivery."""
        create_resp = await client.post(
            "/api/v1/reports/scheduled",
            json={
                "name": "Run Test Report",
                "frequency": "daily",
                "time_of_day": "08:00",
                "timezone": "UTC",
                "recipients": ["test@example.com"],
                "config": {
                    "queries": [],
                    "charts": [],
                    "datasets": ["metrics"],
                    "include_ai_summary": True,
                    "include_csv_export": True,
                },
            },
        )
        assert create_resp.status_code == 201
        report_id = create_resp.json()["id"]

        run_resp = await client.post(
            f"/api/v1/reports/scheduled/{report_id}/run"
        )
        assert run_resp.status_code == 200
        delivery = run_resp.json()
        assert "id" in delivery
        assert delivery["status"] == "pending"

        deliveries_resp = await client.get("/api/v1/reports/deliveries")
        assert deliveries_resp.status_code == 200
        deliveries = deliveries_resp.json()
        assert isinstance(deliveries, list)
        assert len(deliveries) > 0

    @pytest.mark.asyncio
    async def test_list_deliveries_empty(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test deliveries endpoint returns a list."""
        response = await client.get("/api/v1/reports/deliveries")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_delivery_not_found(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test getting a non-existent delivery returns 404."""
        response = await client.get(
            "/api/v1/reports/deliveries/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_delivery_status_not_found(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test updating status for non-existent delivery returns 404."""
        response = await client.put(
            "/api/v1/reports/deliveries/00000000-0000-0000-0000-000000000000/status",
            json={"status": "sent"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_ai_summary_generation(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test AI summary generation from query results."""
        response = await client.post(
            "/api/v1/reports/ai-summary",
            json={
                "query_results": [
                    {"id": 1, "value": 100, "name": "Product A"},
                    {"id": 2, "value": 200, "name": "Product B"},
                ],
                "query_description": "top products by revenue",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "key_insights" in data
        assert "recommendations" in data
        assert len(data["key_insights"]) > 0
        assert "2 rows" in data["summary"]

    @pytest.mark.asyncio
    async def test_ai_summary_empty_results(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test AI summary with empty results is handled."""
        response = await client.post(
            "/api/v1/reports/ai-summary",
            json={
                "query_results": [],
                "query_description": "empty query",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "No data found" in data["summary"]

    @pytest.mark.asyncio
    async def test_report_preview_html(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test report preview returns HTML content."""
        response = await client.post(
            "/api/v1/reports/preview",
            json={
                "config": {
                    "queries": [
                        {
                            "description": "User Count",
                            "sql": "SELECT COUNT(*) as cnt FROM users",
                        }
                    ],
                    "charts": [],
                    "datasets": ["users"],
                    "include_ai_summary": False,
                    "include_csv_export": False,
                },
                "preview_type": "html",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "html" in data
        assert "<html" in data["html"].lower() or "<table" in data["html"].lower()

    @pytest.mark.asyncio
    async def test_report_preview_html_default_type(
        self, client: AsyncClient, override_get_current_user
    ):
        """Test report preview defaults to HTML type."""
        response = await client.post(
            "/api/v1/reports/preview",
            json={
                "config": {
                    "queries": [],
                    "charts": [],
                    "datasets": [],
                    "include_ai_summary": False,
                    "include_csv_export": False,
                },
                "preview_type": "pdf",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "html" in data


# =============================================================================
# Role Management
# =============================================================================

class TestRoleManagement:
    """Test role management endpoints."""

    @pytest.mark.asyncio
    async def test_list_roles(self, client: AsyncClient, override_get_current_user):
        """Test listing all roles returns default roles."""
        response = await client.get("/api/v1/roles")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        role_names = [r["name"] for r in data]
        assert "admin" in role_names
        assert "analyst" in role_names
        assert "viewer" in role_names

    @pytest.mark.asyncio
    async def test_get_role_by_name(self, client: AsyncClient, override_get_current_user):
        """Test getting a role by ID."""
        list_resp = await client.get("/api/v1/roles")
        assert list_resp.status_code == 200
        roles = list_resp.json()
        admin_role = next((r for r in roles if r["name"] == "admin"), None)
        if admin_role:
            role_id = admin_role["id"]
            get_resp = await client.get(f"/api/v1/roles/{role_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["name"] == "admin"
            assert "permissions" in data

    @pytest.mark.asyncio
    async def test_get_role_not_found(self, client: AsyncClient, override_get_current_user):
        """Test getting a non-existent role returns 404."""
        response = await client.get(
            "/api/v1/roles/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404


# =============================================================================
# Health & Root
# =============================================================================

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

    @pytest.mark.asyncio
    async def test_health_check_db_status(self, client: AsyncClient):
        """Test health check includes database status."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert data["database"] in ("connected", "disconnected")


# =============================================================================
# Route Redirects
# =============================================================================

class TestRouteRedirects:
    """Test backward-compatible route redirects."""

    @pytest.mark.asyncio
    async def test_auth_login_redirect(self, client: AsyncClient):
        """Test /auth/login redirects to /api/v1/auth/login."""
        response = await client.post(
            "/auth/login",
            json={"email": "test@test.com", "password": "password"},
        )
        assert response.status_code == 308

    @pytest.mark.asyncio
    async def test_nl_query_redirect(self, client: AsyncClient):
        """Test /nl-query/query redirects to /api/v1/nl-query/query."""
        response = await client.post(
            "/nl-query/query",
            json={"question": "test", "context": {}},
        )
        assert response.status_code == 308


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
