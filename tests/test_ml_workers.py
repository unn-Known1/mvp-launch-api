"""
Tests for Async ML Workers module.
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from nl_to_sql import NLToSQLTranslator, SchemaInfo


class TestForecastTask:
    @patch("ml_workers.sync_generate_forecast")
    @patch("ml_workers.SessionLocal")
    def test_run_forecast_task_success(self, mock_session_local, mock_generate):
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_forecast = MagicMock()
        mock_forecast.id = "test-forecast-id"
        mock_forecast.status = "completed"
        mock_forecast.model_metrics = {"mae": 1.0}
        mock_forecast.predictions = [{"ds": "2024-01-01", "yhat": 100}]
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
        mock_scan.return_value = {"ds-1": 2}

        from ml_workers import run_anomaly_scan_task
        result = run_anomaly_scan_task(user_id="user-1", dataset_id="ds-1")

        assert result["dataset_id"] == "ds-1"
        assert "anomalies_found" in result


class TestNLPQueryTask:
    @patch("ml_workers.create_translator_from_env")
    @patch("ml_workers._get_schema_info_from_config")
    @patch("ml_workers.data_source_store")
    def test_run_nlp_query_no_execute(self, mock_store, mock_schema, mock_translator):
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

    @patch("ml_workers.create_connector")
    @patch("ml_workers.create_translator_from_env")
    @patch("ml_workers._get_schema_info_from_config")
    @patch("ml_workers.data_source_store")
    def test_run_nlp_query_with_execute(self, mock_store, mock_schema, mock_translator, mock_connector):
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
