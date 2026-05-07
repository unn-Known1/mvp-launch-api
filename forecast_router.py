"""
FastAPI router for Prophet forecasting endpoints.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
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

    class Config:
        from_attributes = True


class ForecastListResponse(BaseModel):
    id: str
    dataset_id: str
    model_type: str
    target_column: str
    periods: int
    frequency: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


class BacktestResponse(BaseModel):
    train_size: int
    test_size: int
    metrics: dict[str, float]


@router.post("", response_model=ForecastResponse, status_code=201)
def create_forecast(
    req: ForecastRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Generate a forecast using Prophet."""
    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == req.dataset_id, Dataset.user_id == current_user.id)
        .first()
    )
    if not dataset:
        raise HTTPException(
            status_code=404, detail="Dataset not found or access denied"
        )

    try:
        forecast_record = generate_forecast(
            db,
            dataset_id=req.dataset_id,
            target_column=req.target_column,
            periods=req.periods,
            frequency=req.frequency,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecast failed: {str(e)}")

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


@router.get("", response_model=list[ForecastListResponse])
def list_forecasts_endpoint(
    dataset_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all forecasts with optional filters, scoped to current user's datasets."""
    user_dataset_ids = (
        db.query(Dataset.id).filter(Dataset.user_id == current_user.id).subquery()
    )
    forecasts = list_forecasts(db, dataset_id=dataset_id, status=status)
    forecasts = [f for f in forecasts if f.dataset_id in user_dataset_ids]
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
    """Get a specific forecast by ID."""
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
