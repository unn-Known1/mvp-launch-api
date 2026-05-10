"""
FastAPI router for Prophet forecasting endpoints.
"""

from typing import Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from forecast import (
    backtest_forecast,
    forecasts_to_csv,
    generate_forecast,
    get_forecast_by_id,
    list_forecasts,
)
from models import Dataset

router = APIRouter(prefix="/api/v1/ml/forecast", tags=["ML"])

# B-002: Redis caching support
try:
    import redis
    import json
    _redis_client = redis.from_url("redis://localhost:6379/0", decode_responses=True)
    
    def _get_forecast_cache_key(dataset_id: str, target_column: str, periods: int, frequency: str) -> str:
        return f"forecast:{dataset_id}:{target_column}:{periods}:{frequency}"
    
    def _get_cached_forecast(cache_key: str) -> Optional[dict]:
        try:
            cached = _redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None
    
    def _cache_forecast(cache_key: str, data: dict, expire: int = 300) -> None:
        try:
            _redis_client.setex(cache_key, expire, json.dumps(data))
        except Exception:
            pass
    
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False


# B-003: In-memory task queue for long-running operations
class TaskQueue:
    """Simple in-memory task queue for async operations."""
    def __init__(self):
        self._tasks = {}
    
    def submit(self, task_type: str, params: dict) -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "params": params,
            "status": "pending",
            "result": None,
            "error": None,
        }
        return task_id
    
    def get_status(self, task_id: str) -> Optional[dict]:
        return self._tasks.get(task_id)
    
    def update_status(self, task_id: str, status: str, result=None, error=None) -> None:
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = status
            if result is not None:
                self._tasks[task_id]["result"] = result
            if error is not None:
                self._tasks[task_id]["error"] = error


_task_queue = TaskQueue()


class ForecastRequest(BaseModel):
    dataset_id: str = Field(..., description="UUID of the dataset")
    target_column: str = Field(..., min_length=1, description="Column to forecast")
    periods: int = Field(..., ge=1, le=365, description="Number of periods to forecast")
    frequency: str = Field(default="D", description="Forecast frequency: D, W, M")


class ForecastResponse(BaseModel):
    id: str
    dataset_id: str
    model_type: str
    target_column: str
    periods: int
    frequency: str
    predictions: list[dict]
    model_metrics: Optional[dict]
    status: str
    error_message: Optional[str]
    created_at: str
    completed_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ForecastListResponse(BaseModel):
    id: str
    dataset_id: str
    model_type: str
    target_column: str
    periods: int
    frequency: str
    status: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class BacktestResponse(BaseModel):
    train_size: int
    test_size: int
    metrics: dict[str, float]


@router.post("", response_model=dict, status_code=202)
def create_forecast(
    req: ForecastRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a forecast using Prophet.

    B-003 FIX: Returns 202 Accepted with task_id for long-running operations.
    Use GET /api/v1/ml/forecast/{task_id} to poll for results.
    """
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == req.dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=404, detail="Dataset not found or access denied"
        )

    # B-002: Check Redis cache first
    cache_key = None
    if HAS_REDIS:
        cache_key = _get_forecast_cache_key(req.dataset_id, req.target_column, req.periods, req.frequency)
        cached = _get_cached_forecast(cache_key)
        if cached:
            return {"status": "completed", "task_id": cached.get("id"), "data": cached}

    # Submit to task queue for background processing
    task_id = _task_queue.submit("forecast", {
        "dataset_id": str(req.dataset_id),
        "target_column": req.target_column,
        "periods": req.periods,
        "frequency": req.frequency,
        "user_id": str(current_user.id),
    })

    # Start background task
    background_tasks.add_task(_process_forecast_task, task_id, db)

    return {"status": "processing", "task_id": task_id}


def _process_forecast_task(task_id: str, db: Session):
    """Background task to process forecast generation."""
    import time
    
    task = _task_queue.get_status(task_id)
    if not task:
        return
    
    _task_queue.update_status(task_id, "processing")
    
    try:
        params = task["params"]
        
        # Check cache again before processing
        cache_key = None
        if HAS_REDIS:
            cache_key = _get_forecast_cache_key(
                params["dataset_id"], params["target_column"], 
                params["periods"], params["frequency"]
            )
            cached = _get_cached_forecast(cache_key)
            if cached:
                _task_queue.update_status(task_id, "completed", result=cached)
                return
        
        # Generate forecast
        forecast_record = generate_forecast(
            db,
            dataset_id=params["dataset_id"],
            target_column=params["target_column"],
            periods=params["periods"],
            frequency=params["frequency"],
        )
        
        result = {
            "id": str(forecast_record.id),
            "dataset_id": str(forecast_record.dataset_id),
            "model_type": forecast_record.model_type,
            "target_column": forecast_record.target_column,
            "periods": forecast_record.periods,
            "frequency": forecast_record.frequency,
            "predictions": forecast_record.predictions or [],
            "model_metrics": forecast_record.model_metrics,
            "status": forecast_record.status,
            "error_message": forecast_record.error_message,
            "created_at": forecast_record.created_at.isoformat() if forecast_record.created_at else "",
            "completed_at": forecast_record.completed_at.isoformat() if forecast_record.completed_at else None,
        }
        
        # Cache the result
        if HAS_REDIS and cache_key:
            _cache_forecast(cache_key, result, expire=300)
        
        _task_queue.update_status(task_id, "completed", result=result)
        
    except Exception as e:
        _task_queue.update_status(task_id, "failed", error=str(e))


@router.get("/tasks/{task_id}")
def get_forecast_task_status(task_id: str):
    """Get status of a forecast generation task.
    
    B-003 FIX: Endpoint to poll for task status.
    """
    task = _task_queue.get_status(task_id)
    if not task:
        return {"status": "not_found", "message": "Task not found"}
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "result": task.get("result"),
        "error": task.get("error"),
    }


@router.get("", response_model=list[ForecastListResponse])
def list_forecasts_endpoint(
    dataset_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all forecasts with optional filters, scoped to current user's datasets."""
    forecasts = list_forecasts(db, dataset_id=dataset_id, status=status, user_id=str(current_user.id))
    return [
        ForecastListResponse(
            id=str(f.id),
            dataset_id=str(f.dataset_id),
            model_type=f.model_type,
            target_column=f.target_column,
            periods=f.periods,
            frequency=f.frequency,
            status=f.status,
            created_at=f.created_at.isoformat() if f.created_at else "",
        )
        for f in forecasts
    ]


@router.get("/{forecast_id}", response_model=ForecastResponse)
def get_forecast(
    forecast_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a specific forecast by ID.
    
    NEW-009 FIX: Authorization check is now atomic with forecast fetch
    using a JOIN to prevent time-of-check-time-of-use (TOCTOU) race condition.
    """
    from uuid import UUID
    try:
        UUID(forecast_id)  # Validate UUID format first
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Invalid forecast ID format")
    
    # Atomic authorization check with forecast fetch using JOIN
    from models import Forecast
    forecast_record = (
        db.query(Forecast)
        .join(Dataset, Forecast.dataset_id == Dataset.id)
        .filter(
            Forecast.id == forecast_id,
            Dataset.user_id == current_user.id
        )
        .first()
    )
    if not forecast_record:
        raise HTTPException(status_code=404, detail="Forecast not found or access denied")

    return ForecastResponse(
        id=str(forecast_record.id),
        dataset_id=str(forecast_record.dataset_id),
        model_type=forecast_record.model_type,
        target_column=forecast_record.target_column,
        periods=forecast_record.periods,
        frequency=forecast_record.frequency,
        predictions=forecast_record.predictions or [],
        model_metrics=forecast_record.model_metrics,
        status=forecast_record.status,
        error_message=forecast_record.error_message,
        created_at=(
            forecast_record.created_at.isoformat() if forecast_record.created_at else ""
        ),
        completed_at=(
            forecast_record.completed_at.isoformat()
            if forecast_record.completed_at
            else None
        ),
    )


@router.get("/{forecast_id}/backtest", response_model=BacktestResponse)
def backtest_forecast_endpoint(
    forecast_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Backtest forecast accuracy using train/test split."""
    forecast_record = get_forecast_by_id(db, forecast_id)
    if not forecast_record:
        raise HTTPException(status_code=404, detail="Forecast not found")

    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.id == forecast_record.dataset_id, Dataset.user_id == current_user.id
        )
        .first()
    )  # noqa: E501
    if not dataset:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        result = backtest_forecast(
            db,
            dataset_id=str(forecast_record.dataset_id),
            target_column=forecast_record.target_column,
        )
        return BacktestResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")


@router.get("/{forecast_id}/download")
def download_forecast_csv(
    forecast_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Download forecast predictions as CSV."""
    forecast_record = get_forecast_by_id(db, forecast_id)
    if not forecast_record:
        raise HTTPException(status_code=404, detail="Forecast not found")

    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.id == forecast_record.dataset_id, Dataset.user_id == current_user.id
        )
        .first()
    )  # noqa: E501
    if not dataset:
        raise HTTPException(status_code=403, detail="Access denied")

    csv_data = forecasts_to_csv(forecast_record)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=forecast_{forecast_id}.csv"
        },
    )
