"""
Async ML Workers for background task processing.
Uses Redis-based task queue (RQ) for ML workloads:
- Forecast model training
- Anomaly detection scans
- NLP query processing
"""

import logging
import os
import time
from datetime import datetime
from typing import Any

import redis
from rq import Queue, Worker
from rq.job import Job

from database import SessionLocal
from models import Forecast, Dataset, DataRecord
from forecast import generate_forecast as sync_generate_forecast
from anomaly import scan_all_datasets as sync_scan_all_datasets
from nl_to_sql import NLToSQLTranslator, SchemaInfo

logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Queue names
FORECAST_QUEUE = "ml-forecast"
ANOMALY_QUEUE = "ml-anomaly"
NLP_QUEUE = "ml-nlp"


def get_redis_connection() -> redis.Redis:
    """Get Redis connection."""
    return redis.from_url(REDIS_URL, decode_responses=False)


def get_forecast_queue() -> Queue:
    """Get the forecast task queue."""
    return Queue(FORECAST_QUEUE, connection=get_redis_connection())


def get_anomaly_queue() -> Queue:
    """Get the anomaly detection task queue."""
    return Queue(ANOMALY_QUEUE, connection=get_redis_connection())


def get_nlp_queue() -> Queue:
    """Get the NLP processing task queue."""
    return Queue(NLP_QUEUE, connection=get_redis_connection())


# --- Task Functions ---


def run_forecast_task(
    dataset_id: str,
    target_column: str,
    periods: int,
    frequency: str = "D",
    model_type: str = "prophet",
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Async task: run Prophet forecast and store results.
    Returns a dict with forecast_id and status.
    """
    logger.info(f"Starting forecast task: dataset={dataset_id}, target={target_column}")
    db = SessionLocal()
    try:
        forecast_record = sync_generate_forecast(
            db=db,
            dataset_id=dataset_id,
            target_column=target_column,
            periods=periods,
            frequency=frequency,
            model_type=model_type,
        )
        result = {
            "forecast_id": str(forecast_record.id),
            "status": forecast_record.status,
            "metrics": forecast_record.model_metrics,
            "predictions_count": len(forecast_record.predictions),
        }
        logger.info(f"Forecast task completed: {result['forecast_id']}")
        return result
    except Exception as e:
        logger.error(f"Forecast task failed: {e}")
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
    """
    logger.info(f"Starting anomaly scan: dataset={dataset_id or 'all'}")
    db = SessionLocal()
    try:
        if dataset_id:
            from anomaly import detect_anomalies_for_metric, extract_numeric_metrics
            metrics = extract_numeric_metrics(db, dataset_id)
            total = 0
            for metric in metrics:
                anomalies = detect_anomalies_for_metric(db, dataset_id, metric, user_id)
                total += len(anomalies)
            result = {"dataset_id": dataset_id, "anomalies_found": total}
        else:
            results = sync_scan_all_datasets(db, user_id)
            result = {"datasets_scanned": len(results), "anomalies_by_dataset": results}
        logger.info(f"Anomaly scan completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Anomaly scan failed: {e}")
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
        return response
    except Exception as e:
        logger.error(f"NLP query task failed: {e}")
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
) -> str | None:
    """Enqueue a forecast task. Returns job ID."""
    try:
        queue = get_forecast_queue()
        job = queue.enqueue(
            run_forecast_task,
            dataset_id,
            target_column,
            periods,
            frequency,
            model_type,
            user_id,
            job_timeout="10m",
        )
        logger.info(f"Enqueued forecast job: {job.id}")
        return job.id
    except Exception as e:
        logger.error(f"Failed to enqueue forecast: {e}")
        return None


def enqueue_anomaly_scan(
    user_id: str | None = None,
    dataset_id: str | None = None,
) -> str | None:
    """Enqueue an anomaly scan task. Returns job ID."""
    try:
        queue = get_anomaly_queue()
        job = queue.enqueue(
            run_anomaly_scan_task,
            user_id,
            dataset_id,
            job_timeout="15m",
        )
        logger.info(f"Enqueued anomaly scan job: {job.id}")
        return job.id
    except Exception as e:
        logger.error(f"Failed to enqueue anomaly scan: {e}")
        return None


def enqueue_nlp_query(
    natural_language_query: str,
    data_source_id: str,
    dialect: str = "postgresql",
    execute: bool = False,
) -> str | None:
    """Enqueue an NLP query task. Returns job ID."""
    try:
        queue = get_nlp_queue()
        job = queue.enqueue(
            run_nlp_query_task,
            natural_language_query,
            data_source_id,
            dialect,
            execute,
            job_timeout="5m",
        )
        logger.info(f"Enqueued NLP query job: {job.id}")
        return job.id
    except Exception as e:
        logger.error(f"Failed to enqueue NLP query: {e}")
        return None


def get_job_status(job_id: str) -> dict[str, Any] | None:
    """Get the status of a job by ID."""
    try:
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


# --- Worker Runner ---


def run_worker(queues: list[str] | None = None, burst: bool = False):
    """
    Run an RQ worker for ML task processing.
    Usage:
        run_worker(queues=["ml-forecast", "ml-anomaly", "ml-nlp"])
    """
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
