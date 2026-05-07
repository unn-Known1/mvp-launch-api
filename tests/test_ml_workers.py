"""Tests for Async ML Workers module."""

from unittest.mock import MagicMock, patch

from nl_to_sql import SchemaInfo


class TestForecastTask:
    @patch("ml_workers.sync_generate_forecast")
    @patch("ml_workers.SessionLocal")
    def test_run_forecast_task_success(self, mock_session_local, mock_generate):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        from datetime import datetime, timezone

        mock_forecast = MagicMock()
        mock_forecast.id = "test-forecast-id"
        mock_forecast.status = "completed"
        mock_forecast.model_metrics = {"mae": 1.0}
        mock_forecast.predictions = [{"ds": "2024-01-01", "yhat": 100}]
        mock_forecast.completed_at = datetime.now(timezone.utc)
        mock_generate.return_value = mock_forecast

        from ml_workers import run_forecast_task

        result = run_forecast_task(
            dataset_id="ds-1",
            target_column="sales",
            periods=10,
            frequency="D",
        )

        assert result["forecast_id"] == "test-forecast-id"
        assert result["status"] == "completed"
        assert "metrics" in result

    @patch("ml_workers.sync_generate_forecast")
    @patch("ml_workers.SessionLocal")
    def test_run_forecast_task_failure(self, mock_session_local, mock_generate):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_generate.side_effect = Exception("Forecast failed")

        from ml_workers import run_forecast_task

        result = run_forecast_task(
            dataset_id="ds-1",
            target_column="sales",
            periods=10,
        )

        assert result["status"] == "failed"
        assert "error" in result


class TestAnomalyScanTask:
    @patch("ml_workers.sync_scan_all_datasets")
    @patch("ml_workers.SessionLocal")
    def test_run_anomaly_scan_all(self, mock_session_local, mock_scan):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_scan.return_value = {"ds-1": 3, "ds-2": 1}

        from ml_workers import run_anomaly_scan_task

        result = run_anomaly_scan_task(user_id="user-1")

        assert "datasets_scanned" in result
        assert "anomalies_by_dataset" in result

    @patch("ml_workers.sync_scan_all_datasets")
    @patch("ml_workers.SessionLocal")
    def test_run_anomaly_scan_single_dataset(self, mock_session_local, mock_scan):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_scan.return_value = {"ds-1": 4}

        from ml_workers import run_anomaly_scan_task

        result = run_anomaly_scan_task(user_id="user-1", dataset_id="ds-1")

        assert result["dataset_id"] == "ds-1"
        assert "anomalies_found" in result


class TestNLPQueryTask:
    @patch("connectors.data_source_store")
    @patch("nl_langchain.create_translator_from_env")
    @patch("ml_workers._get_schema_info_from_config")
    def test_run_nlp_query_no_execute(self, mock_schema, mock_translator, mock_store):
        mock_config = MagicMock()
        mock_store.get.return_value = mock_config
        mock_schema.return_value = SchemaInfo(tables=[])

        mock_t = MagicMock()
        mock_result = MagicMock()
        mock_result.generated_sql = "SELECT * FROM data"
        mock_result.error_message = None
        mock_result.confidence_score = 85
        mock_result.confidence_level = MagicMock()
        mock_result.confidence_level.value = "high"
        mock_t.translate.return_value = mock_result
        mock_translator.return_value = mock_t

        from ml_workers import run_nlp_query_task

        result = run_nlp_query_task(
            natural_language_query="Show data",
            data_source_id="ds-1",
            execute=False,
        )

        assert result["status"] == "completed"
        assert result["generated_sql"] == "SELECT * FROM data"

    @patch("connectors.create_connector")
    @patch("connectors.data_source_store")
    @patch("nl_langchain.create_translator_from_env")
    @patch("ml_workers._get_schema_info_from_config")
    def test_run_nlp_query_with_execute(
        self, mock_schema, mock_translator, mock_store, mock_connector
    ):
        mock_config = MagicMock()
        mock_store.get.return_value = mock_config
        mock_schema.return_value = SchemaInfo(tables=[])

        mock_t = MagicMock()
        mock_result = MagicMock()
        mock_result.generated_sql = "SELECT * FROM data"
        mock_result.error_message = None
        mock_result.confidence_score = 85
        mock_result.confidence_level = MagicMock()
        mock_result.confidence_level.value = "high"
        mock_t.translate.return_value = mock_result
        mock_t.execute_query.return_value = ([{"id": 1}], 1, None)
        mock_translator.return_value = mock_t

        mock_connector_inst = MagicMock()
        mock_connector.return_value = mock_connector_inst

        from ml_workers import run_nlp_query_task

        result = run_nlp_query_task(
            natural_language_query="Show data",
            data_source_id="ds-1",
            execute=True,
        )

        assert "results" in result
        assert result["row_count"] == 1


class TestQueueFunctions:
    @patch("ml_workers.get_redis_connection")
    def test_get_forecast_queue(self, mock_redis):
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn

        from ml_workers import get_forecast_queue

        queue = get_forecast_queue()
        assert queue is not None

    @patch("ml_workers.get_forecast_queue")
    @patch("ml_workers.get_redis_connection")
    def test_enqueue_forecast(self, mock_redis, mock_queue):
        mock_q = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_q.enqueue.return_value = mock_job
        mock_queue.return_value = mock_q

        from ml_workers import enqueue_forecast

        job_id = enqueue_forecast("ds-1", "sales", 10)
        assert job_id == "job-123"


class TestWorkerHealth:
    @patch("ml_workers._check_redis_available")
    def test_get_worker_health_returns_status(self, mock_redis_check):
        mock_redis_check.return_value = True

        from ml_workers import get_worker_health

        health = get_worker_health()

        assert "redis_available" in health
        assert "status" in health
        assert "total_tasks_processed" in health
        assert "failure_rate_pct" in health

    def test_get_job_status_sync_mode(self):
        from ml_workers import get_job_status

        result = get_job_status("sync:test-forecast-id")

        assert result["status"] == "completed"
        assert result["mode"] == "sync_fallback"


class TestRetryWrapper:
    def test_retry_wrapper_succeeds_on_first_try(self):
        from ml_workers import _retry_wrapper

        call_count = 0

        def success_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = _retry_wrapper(success_func, max_retries=2)
        assert result == "ok"
        assert call_count == 1

    def test_retry_wrapper_succeeds_after_retry(self):
        from ml_workers import _retry_wrapper

        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "ok"

        result = _retry_wrapper(flaky_func, max_retries=2)
        assert result == "ok"
        assert call_count == 2


class TestSyncFallback:
    @patch("ml_workers.get_redis_connection")
    @patch("ml_workers.run_forecast_task")
    def test_enqueue_forecast_falls_back_to_sync(self, mock_run_task, mock_redis):
        mock_redis.side_effect = ConnectionError("Redis unavailable")

        from ml_workers import enqueue_forecast

        mock_run_task.return_value = {
            "forecast_id": "sync-123",
            "status": "completed",
        }

        job_id = enqueue_forecast("ds-1", "sales", 10)

        assert job_id is not None
        assert job_id.startswith("sync:")
