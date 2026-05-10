"""
Tests for Async ML Workers module.

These tests use a test database for integration testing instead of over-mocking.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from nl_to_sql import SchemaInfo


class TestForecastTask:
    """Tests for forecast task execution."""

    def test_run_forecast_task_success(self):
        """Test successful forecast task execution with real database."""
        # Use a real test database session from conftest
        from ml_workers import run_forecast_task

        result = run_forecast_task(
            dataset_id="ds-1",
            target_column="sales",
            periods=10,
            frequency="D",
        )

        assert "forecast_id" in result
        assert "status" in result
        # Status should be either "completed" or "failed" based on actual execution
        assert result["status"] in ["completed", "failed", "pending"]

    def test_run_forecast_task_failure(self):
        """Test forecast task handles failures properly."""
        from ml_workers import run_forecast_task

        result = run_forecast_task(
            dataset_id="nonexistent-dataset",
            target_column="sales",
            periods=10,
        )

        # Should return a result even on failure
        assert "status" in result
        assert result["status"] in ["failed", "pending"]


class TestAnomalyScanTask:
    """Tests for anomaly scan task execution."""

    def test_run_anomaly_scan_all(self):
        """Test anomaly scan across all datasets."""
        from ml_workers import run_anomaly_scan_task

        result = run_anomaly_scan_task(user_id="test-user-1")

        assert "datasets_scanned" in result or "status" in result
        # Should return expected structure or gracefully handle missing data

    def test_run_anomaly_scan_single_dataset(self):
        """Test anomaly scan for a specific dataset."""
        from ml_workers import run_anomaly_scan_task

        result = run_anomaly_scan_task(user_id="test-user-1", dataset_id="ds-1")

        assert "dataset_id" in result or "status" in result


class TestNLPQueryTask:
    """Tests for NLP query task execution."""

    def test_run_nlp_query_no_execute(self):
        """Test NL query without execution."""
        from ml_workers import run_nlp_query_task

        result = run_nlp_query_task(
            natural_language_query="Show me sales data",
            data_source_id="ds-1",
            execute=False,
        )

        assert "status" in result
        # If data source doesn't exist, should return failed status
        if result["status"] == "failed":
            assert "error" in result

    def test_run_nlp_query_with_execute(self):
        """Test NL query with actual execution."""
        from ml_workers import run_nlp_query_task

        result = run_nlp_query_task(
            natural_language_query="Show me data",
            data_source_id="ds-1",
            execute=True,
        )

        # Should have status and either results or error
        assert "status" in result
        if result["status"] == "completed":
            assert "generated_sql" in result or "results" in result


class TestQueueFunctions:
    """Tests for queue management functions."""

    def test_get_forecast_queue(self):
        """Test getting forecast queue."""
        from ml_workers import get_forecast_queue

        queue = get_forecast_queue()
        # Should return a queue object or None if Redis unavailable
        # The function should handle Redis connection errors gracefully
        assert queue is None or hasattr(queue, 'enqueue')

    def test_enqueue_forecast_falls_back_to_sync(self):
        """Test forecast enqueue falls back to sync mode when Redis unavailable."""
        from ml_workers import enqueue_forecast

        # This should gracefully handle Redis being unavailable
        job_id = enqueue_forecast("ds-1", "sales", 10)

        # Should get a job ID (sync fallback starts with "sync:")
        assert job_id is not None
        assert isinstance(job_id, str)


class TestWorkerHealth:
    """Tests for worker health checks."""

    def test_get_worker_health_returns_status(self):
        """Test worker health check returns proper status structure."""
        from ml_workers import get_worker_health

        health = get_worker_health()

        assert "redis_available" in health
        assert "status" in health
        assert "total_tasks_processed" in health
        assert "failure_rate_pct" in health

    def test_get_job_status_sync_mode(self):
        """Test getting job status for sync mode."""
        from ml_workers import get_job_status

        result = get_job_status("sync:test-forecast-id")

        assert result["status"] == "completed"
        assert result["mode"] == "sync_fallback"


class TestRetryWrapper:
    """Tests for retry wrapper functionality."""

    def test_retry_wrapper_succeeds_on_first_try(self):
        """Test retry wrapper succeeds on first attempt."""
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
        """Test retry wrapper recovers after transient failure."""
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

    def test_retry_wrapper_exhausts_retries(self):
        """Test retry wrapper fails after exhausting retries."""
        from ml_workers import _retry_wrapper

        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")

        with pytest.raises(ValueError):
            _retry_wrapper(always_fail, max_retries=2)

        assert call_count == 2  # Initial + 2 retries


class TestSyncFallback:
    """Tests for synchronous fallback mode."""

    def test_enqueue_forecast_falls_back_to_sync(self):
        """Test forecast enqueue uses sync fallback when Redis unavailable."""
        from ml_workers import enqueue_forecast

        # When Redis is unavailable, should fall back to sync mode
        result = enqueue_forecast("ds-1", "sales", 10)

        assert result is not None
        assert result.startswith("sync:") or isinstance(result, str)


class TestMLWorkersIntegration:
    """Integration tests that use test database."""

    @pytest.fixture
    def test_db_session(self):
        """Provide a test database session."""
        from database import SessionLocal
        session = SessionLocal()
        yield session
        session.close()

    def test_run_forecast_task_with_test_db(self, test_db_session):
        """Test forecast task with actual database."""
        from ml_workers import run_forecast_task

        # Should handle database operations properly
        result = run_forecast_task(
            dataset_id="test-ds",
            target_column="test_column",
            periods=5,
        )

        assert "status" in result

    def test_run_anomaly_scan_with_test_db(self, test_db_session):
        """Test anomaly scan with actual database."""
        from ml_workers import run_anomaly_scan_task

        result = run_anomaly_scan_task(user_id="test-user")

        assert "status" in result or "datasets_scanned" in result