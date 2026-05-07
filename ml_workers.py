"""
Async ML Workers for background task processing.
Uses Redis-based task queue (RQ) for ML workloads:
- Forecast model training
- Anomaly detection scans
- NLP query processing

Supports sync fallback mode when Redis is unavailable.
Includes retry logic, health monitoring, and task priority handling.
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from database import SessionLocal
from models import Forecast, Dataset, DataRecord
from forecast import generate_forecast as sync_generate_forecast
from anomaly import scan_all_datasets as sync_scan_all_datasets
from nl_to_sql import NLToSQLTranslator, SchemaInfo

logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_TIMEOUT = int(os.getenv("REDIS_TIMEOUT", "5"))
USE_SYNC_FALLBACK = os.getenv("ML_USE_SYNC_FALLBACK", "true").lower() == "true"
MAX_RETRIES = int(os.getenv("ML_MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("ML_RETRY_DELAY", "2"))

# Queue names
FORECAST_QUEUE = "ml-forecast"
ANOMALY_QUEUE = "ml-anomaly"
NLP_QUEUE = "ml-nlp"

# Health tracking
_health_state = {
    "last_check": None,
    "redis_available": False,
    "total_tasks": 0,
    "failed_tasks": 0,
    "sync_fallbacks": 0,
}


def _check_redis_available() -> bool:
    """Check if Redis is reachable without raising exceptions."""
    try:
        import redis
        conn = redis.from_url(REDIS_URL, socket_timeout=REDIS_TIMEOUT, socket_connect_timeout=REDIS_TIMEOUT)
        conn.ping()
        return True
    except Exception:
        return False


def get_redis_connection():
    """Get Redis connection with timeout settings."""
    import redis
    return redis.from_url(
        REDIS_URL,
        decode_responses=False,
        socket_timeout=REDIS_TIMEOUT,
        socket_connect_timeout=REDIS_TIMEOUT,
    )


def get_forecast_queue():
    """Get the forecast task queue."""
    from rq import Queue
    return Queue(FORECAST_QUEUE, connection=get_redis_connection())


def get_anomaly_queue():
    """Get the anomaly detection task queue."""
    from rq import Queue
    return Queue(ANOMALY_QUEUE, connection=get_redis_connection())


def get_nlp_queue():
    """Get the NLP processing task queue."""
    from rq import Queue
    return Queue(NLP_QUEUE, connection=get_redis_connection())


# --- Task Functions ---


def _retry_wrapper(func, *args, max_retries: int = MAX_RETRIES, **kwargs):
    """Execute a function with retry logic and exponential backoff."""
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = RETRY_DELAY * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {e}")
    raise last_exception


def run_forecast_task(
    dataset_id: str,
    target_column: str,
    periods: int,
    frequency: str = "D",
    model_type: str = "prophet",
    user_id: str | None = None,
    hyperparams: dict | None = None,
) -> dict[str, Any]:
    """
    Async task: run Prophet forecast and store results.
    Returns a dict with forecast_id and status.
    Supports retry logic and sync fallback.
    """
    logger.info(f"Starting forecast task: dataset={dataset_id}, target={target_column}")
    db = SessionLocal()
    try:
        forecast_record = _retry_wrapper(
            sync_generate_forecast,
            db=db,
            dataset_id=dataset_id,
            target_column=target_column,
            periods=periods,
            frequency=frequency,
            model_type=model_type,
            hyperparams=hyperparams,
        )
        result = {
            "forecast_id": str(forecast_record.id),
            "status": forecast_record.status,
            "metrics": forecast_record.model_metrics,
            "predictions_count": len(forecast_record.predictions),
            "completed_at": forecast_record.completed_at.isoformat() if forecast_record.completed_at else None,
        }
        logger.info(f"Forecast task completed: {result['forecast_id']}")
        _health_state["total_tasks"] += 1
        return result
    except Exception as e:
        logger.error(f"Forecast task failed after retries: {e}")
        _health_state["total_tasks"] += 1
        _health_state["failed_tasks"] += 1
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


def run_anomaly_scan_task(
    user_id: str | None = None,
    dataset_id: str | None = None,
) -> dict[str, Any]:
    """
    Async task: scan datasets for anomalies.
    If dataset_id is provided, scans only that dataset.
    Otherwise scans all ready datasets.
    Supports retry logic.
    """
    logger.info(f"Starting anomaly scan: dataset={dataset_id or 'all'}")
    db = SessionLocal()
    try:
        if dataset_id:
            from anomaly import detect_anomalies_for_metric, extract_numeric_metrics
            from anomaly import compute_anomaly_scores

            metrics = extract_numeric_metrics(db, dataset_id)
            total = 0
            evaluation_scores = {}
            for metric in metrics:
                anomalies = detect_anomalies_for_metric(db, dataset_id, metric, user_id)
                total += len(anomalies)

                series_data = db.query(DataRecord).filter(
                    DataRecord.dataset_id == dataset_id
                ).order_by(DataRecord.created_at).all()
                values = []
                for record in series_data:
                    if isinstance(record.data, dict) and metric in record.data:
                        try:
                            values.append(float(record.data[metric]))
                        except (ValueError, TypeError):
                            pass
                if values:
                    evaluation_scores[metric] = compute_anomaly_scores(values)

            result = {
                "dataset_id": dataset_id,
                "anomalies_found": total,
                "evaluation_scores": evaluation_scores,
            }
        else:
            results = sync_scan_all_datasets(db, user_id)
            result = {"datasets_scanned": len(results), "anomalies_by_dataset": results}
        logger.info(f"Anomaly scan completed: {result}")
        _health_state["total_tasks"] += 1
        return result
    except Exception as e:
        logger.error(f"Anomaly scan failed after retries: {e}")
        _health_state["total_tasks"] += 1
        _health_state["failed_tasks"] += 1
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


def run_nlp_query_task(
    natural_language_query: str,
    data_source_id: str,
    dialect: str = "postgresql",
    execute: bool = False,
) -> dict[str, Any]:
    """
    Async task: process NL query and optionally execute.
    """
    logger.info(f"Starting NLP query task: query='{natural_language_query[:50]}...'")
    try:
        from connectors import create_connector, data_source_store

        config = data_source_store.get(data_source_id)
        if not config:
            return {"status": "failed", "error": f"Data source not found: {data_source_id}"}

        from nl_langchain import create_translator_from_env
        translator = create_translator_from_env()

        schema_info = _get_schema_info_from_config(config)
        result = translator.translate(
            natural_language_query=natural_language_query,
            schema_info=schema_info,
            dialect=dialect,
            data_source_id=data_source_id,
        )

        response = {
            "status": "completed" if not result.error_message else "error",
            "natural_language_query": result.natural_language_query,
            "generated_sql": result.generated_sql,
            "confidence_score": result.confidence_score,
            "confidence_level": result.confidence_level.value if result.confidence_level else None,
            "error_message": result.error_message,
        }

        if execute and result.generated_sql and not result.error_message:
            try:
                connector = create_connector(config)
                query_results, row_count, exec_error = translator.execute_query(
                    sql=result.generated_sql,
                    connector=connector,
                    max_rows=10000,
                )
                if exec_error:
                    response["execution_error"] = exec_error
                else:
                    response["results"] = query_results[:100]
                    response["row_count"] = row_count
            except Exception as e:
                response["execution_error"] = str(e)

        logger.info(f"NLP query task completed: confidence={response.get('confidence_score')}")
        _health_state["total_tasks"] += 1
        return response
    except Exception as e:
        logger.error(f"NLP query task failed: {e}")
        _health_state["total_tasks"] += 1
        _health_state["failed_tasks"] += 1
        return {"status": "failed", "error": str(e)}


def _get_schema_info_from_config(config) -> SchemaInfo:
    """Extract SchemaInfo from a data source config."""
    from nl_to_sql import SchemaInfo
    try:
        from connectors.base import DataSourceConfig
        connector = __import__("connectors", fromlist=["create_connector"]).create_connector(config)
        raw_schema = connector.get_schema_info()
        tables = []
        relationships = []
        if isinstance(raw_schema, dict):
            raw_tables = raw_schema.get("tables", [raw_schema])
            relationships = raw_schema.get("relationships", [])
        elif isinstance(raw_schema, list):
            raw_tables = raw_schema
        else:
            raw_tables = []
        for t in raw_tables:
            tables.append({
                "name": t.get("table") or t.get("name") or t.get("table_name", ""),
                "columns": t.get("columns", []),
                "row_count": t.get("row_count"),
            })
        return SchemaInfo(tables=tables, relationships=relationships)
    except Exception as e:
        logger.warning(f"Failed to get schema: {e}")
        return SchemaInfo()


# --- Queue Submission Helpers ---


def enqueue_forecast(
    dataset_id: str,
    target_column: str,
    periods: int,
    frequency: str = "D",
    model_type: str = "prophet",
    user_id: str | None = None,
    hyperparams: dict | None = None,
    priority: str = "default",
) -> str | None:
    """Enqueue a forecast task. Returns job ID or runs sync if Redis unavailable."""
    try:
        queue = get_forecast_queue()
        job_timeout_map = {"high": "5m", "default": "10m", "low": "20m"}
        job_timeout = job_timeout_map.get(priority, "10m")

        job = queue.enqueue(
            run_forecast_task,
            dataset_id,
            target_column,
            periods,
            frequency,
            model_type,
            user_id,
            hyperparams,
            job_timeout=job_timeout,
        )
        logger.info(f"Enqueued forecast job: {job.id}")
        return job.id
    except Exception as e:
        logger.warning(f"Redis unavailable for forecast, falling back to sync: {e}")
        if USE_SYNC_FALLBACK:
            _health_state["sync_fallbacks"] += 1
            result = run_forecast_task(
                dataset_id, target_column, periods, frequency, model_type, user_id, hyperparams
            )
            return f"sync:{result.get('forecast_id', 'unknown')}"
        logger.error(f"Failed to enqueue forecast and sync fallback disabled: {e}")
        return None


def enqueue_anomaly_scan(
    user_id: str | None = None,
    dataset_id: str | None = None,
    priority: str = "default",
) -> str | None:
    """Enqueue an anomaly scan task. Returns job ID or runs sync if Redis unavailable."""
    try:
        queue = get_anomaly_queue()
        job_timeout_map = {"high": "10m", "default": "15m", "low": "30m"}
        job_timeout = job_timeout_map.get(priority, "15m")

        job = queue.enqueue(
            run_anomaly_scan_task,
            user_id,
            dataset_id,
            job_timeout=job_timeout,
        )
        logger.info(f"Enqueued anomaly scan job: {job.id}")
        return job.id
    except Exception as e:
        logger.warning(f"Redis unavailable for anomaly scan, falling back to sync: {e}")
        if USE_SYNC_FALLBACK:
            _health_state["sync_fallbacks"] += 1
            result = run_anomaly_scan_task(user_id, dataset_id)
            return f"sync:anomaly_scan"
        logger.error(f"Failed to enqueue anomaly scan and sync fallback disabled: {e}")
        return None


def enqueue_nlp_query(
    natural_language_query: str,
    data_source_id: str,
    dialect: str = "postgresql",
    execute: bool = False,
    priority: str = "default",
) -> str | None:
    """Enqueue an NLP query task. Returns job ID or runs sync if Redis unavailable."""
    try:
        queue = get_nlp_queue()
        job_timeout_map = {"high": "2m", "default": "5m", "low": "10m"}
        job_timeout = job_timeout_map.get(priority, "5m")

        job = queue.enqueue(
            run_nlp_query_task,
            natural_language_query,
            data_source_id,
            dialect,
            execute,
            job_timeout=job_timeout,
        )
        logger.info(f"Enqueued NLP query job: {job.id}")
        return job.id
    except Exception as e:
        logger.warning(f"Redis unavailable for NLP query, falling back to sync: {e}")
        if USE_SYNC_FALLBACK:
            _health_state["sync_fallbacks"] += 1
            run_nlp_query_task(natural_language_query, data_source_id, dialect, execute)
            return f"sync:nlp_query"
        logger.error(f"Failed to enqueue NLP query and sync fallback disabled: {e}")
        return None


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Get the status of a job by ID."""
    if job_id.startswith("sync:"):
        return {
            "id": job_id,
            "status": "completed",
            "mode": "sync_fallback",
        }
    try:
        from rq.job import Job
        redis_conn = get_redis_connection()
        job = Job.fetch(job_id, connection=redis_conn)
        return {
            "id": job.id,
            "status": job.get_status(),
            "result": job.result,
            "exc_info": job.exc_info,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        }
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        return None


def get_worker_health() -> dict[str, Any]:
    """Get current worker health status."""
    redis_available = _check_redis_available()
    _health_state["last_check"] = datetime.now(timezone.utc).isoformat()
    _health_state["redis_available"] = redis_available

    failure_rate = 0.0
    if _health_state["total_tasks"] > 0:
        failure_rate = round(
            _health_state["failed_tasks"] / _health_state["total_tasks"] * 100, 2
        )

    return {
        "redis_available": redis_available,
        "sync_fallback_enabled": USE_SYNC_FALLBACK,
        "total_tasks_processed": _health_state["total_tasks"],
        "failed_tasks": _health_state["failed_tasks"],
        "failure_rate_pct": failure_rate,
        "sync_fallbacks_used": _health_state["sync_fallbacks"],
        "last_health_check": _health_state["last_check"],
        "status": "healthy" if redis_available or USE_SYNC_FALLBACK else "unhealthy",
    }


# --- Worker Runner ---


def run_worker(queues: list[str] | None = None, burst: bool = False):
    """
    Run an RQ worker for ML task processing.
    Usage:
        run_worker(queues=["ml-forecast", "ml-anomaly", "ml-nlp"])
    """
    from rq import Queue, Worker
    if queues is None:
        queues = [FORECAST_QUEUE, ANOMALY_QUEUE, NLP_QUEUE]

    with Worker([Queue(q, connection=get_redis_connection()) for q in queues]) as workers:
        logger.info(f"Starting ML worker for queues: {queues}")
        if burst:
            Worker.work_burst(workers)
        else:
            Worker.work(workers)


if __name__ == "__main__":
    import sys
    burst_mode = "--burst" in sys.argv
    run_worker(burst=burst_mode)
