"""
Prophet-based time series forecasting service.
Supports model versioning, hyperparameter tuning, cross-validation,
and robust evaluation metrics.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from prophet import Prophet

from models import Dataset, DataRecord, Forecast
from sqlalchemy.orm import Session


MIN_DATA_POINTS = 30


def get_time_series_data(
    db: Session, dataset_id: str, target_column: str
) -> pd.DataFrame:
    """Extract time series data from dataset records."""
    records = (
        db.query(DataRecord)
        .filter(DataRecord.dataset_id == dataset_id)
        .order_by(DataRecord.created_at)
        .all()
    )
    data_points = []
    for record in records:
        rec_data = record.data
        if isinstance(rec_data, dict) and target_column in rec_data:
            try:
                value = float(rec_data[target_column])
                data_points.append({"ds": record.created_at, "y": value})
            except (ValueError, TypeError):
                continue
    return pd.DataFrame(data_points)


def compute_model_version(
    model_type: str,
    yearly_seasonality: bool,
    weekly_seasonality: bool,
    daily_seasonality: bool,
    changepoint_prior_scale: float,
    data_hash: str,
) -> str:
    """Compute a deterministic model version string from hyperparameters and data."""
    version_input = (
        f"type={model_type}:yr={yearly_seasonality}:wk={weekly_seasonality}:"
        f"dy={daily_seasonality}:cps={changepoint_prior_scale}:data={data_hash}"
    )
    return hashlib.sha256(version_input.encode()).hexdigest()[:12]


def generate_forecast(
    db: Session,
    dataset_id: str,
    target_column: str,
    periods: int,
    frequency: str = "D",
    model_type: str = "prophet",
    hyperparams: Optional[dict] = None,
) -> Forecast:
    """Generate forecast using Prophet and store results."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise ValueError(f"Dataset {dataset_id} not found")

    df = get_time_series_data(db, dataset_id, target_column)
    if len(df) < MIN_DATA_POINTS:
        raise ValueError(
            f"Insufficient data points for forecasting "
            f"(minimum {MIN_DATA_POINTS} required, got {len(df)})"
        )

    forecast_record = Forecast(
        dataset_id=dataset_id,
        model_type=model_type,
        target_column=target_column,
        periods=periods,
        frequency=frequency,
        predictions=[],
        model_metrics={},
        status="running",
    )
    db.add(forecast_record)
    db.commit()

    try:
        params = hyperparams or {}
        yearly_seasonality = params.get("yearly_seasonality", True)
        weekly_seasonality = params.get("weekly_seasonality", True)
        daily_seasonality = params.get("daily_seasonality", False)
        changepoint_prior_scale = params.get("changepoint_prior_scale", 0.05)
        seasonality_prior_scale = params.get("seasonality_prior_scale", 10.0)

        data_hash = hashlib.md5(
            json.dumps(df["y"].tolist(), default=str).encode()
        ).hexdigest()[:8]

        model_version = compute_model_version(
            model_type=model_type,
            yearly_seasonality=yearly_seasonality,
            weekly_seasonality=weekly_seasonality,
            daily_seasonality=daily_seasonality,
            changepoint_prior_scale=changepoint_prior_scale,
            data_hash=data_hash,
        )

        model = Prophet(
            yearly_seasonality=yearly_seasonality,
            weekly_seasonality=weekly_seasonality,
            daily_seasonality=daily_seasonality,
            interval_width=0.95,
            changepoint_prior_scale=changepoint_prior_scale,
            seasonality_prior_scale=seasonality_prior_scale,
        )
        model.fit(df)

        future = model.make_future_dataframe(periods=periods, freq=frequency)
        forecast = model.predict(future)

        predictions = []
        for _, row in forecast.iterrows():
            pred = {
                "ds": row["ds"].isoformat(),
                "yhat": float(row["yhat"]),
                "yhat_lower": float(row["yhat_lower"]),
                "yhat_upper": float(row["yhat_upper"]),
            }
            predictions.append(pred)

        forecast_record.predictions = predictions

        historical = forecast.iloc[: len(df)]
        metrics = calculate_model_metrics(df["y"].values, historical["yhat"].values)
        metrics["model_version"] = model_version
        metrics["hyperparameters"] = {
            "changepoint_prior_scale": changepoint_prior_scale,
            "seasonality_prior_scale": seasonality_prior_scale,
            "yearly_seasonality": yearly_seasonality,
            "weekly_seasonality": weekly_seasonality,
            "daily_seasonality": daily_seasonality,
        }
        forecast_record.model_metrics = metrics
        forecast_record.status = "completed"
        forecast_record.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        forecast_record.status = "failed"
        forecast_record.error_message = str(e)

    db.commit()
    return forecast_record


def calculate_model_metrics(
    actual: list[float], predicted: list[float]
) -> dict[str, float]:
    """Calculate forecast accuracy metrics with robust handling of edge cases."""
    actual_arr = np.array(actual, dtype=np.float64)
    predicted_arr = np.array(predicted, dtype=np.float64)

    mae = float(np.mean(np.abs(actual_arr - predicted_arr)))
    mse = float(np.mean((actual_arr - predicted_arr) ** 2))
    rmse = float(np.sqrt(mse))

    mask = np.abs(actual_arr) > 1e-10
    if np.any(mask):
        mape = float(np.mean(np.abs((actual_arr[mask] - predicted_arr[mask]) / actual_arr[mask])) * 100)
    else:
        mape = 0.0

    ss_res = np.sum((actual_arr - predicted_arr) ** 2)
    ss_tot = np.sum((actual_arr - np.mean(actual_arr)) ** 2)
    r_squared = float(1 - (ss_res / ss_tot)) if ss_tot > 1e-10 else 0.0

    mase_denom = np.mean(np.abs(np.diff(actual_arr)))
    if mase_denom > 1e-10 and len(actual_arr) > 1:
        mase = float(mae / mase_denom)
    else:
        mase = 0.0

    return {
        "mae": round(mae, 4),
        "mse": round(mse, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 4),
        "r_squared": round(r_squared, 4),
        "mase": round(mase, 4),
    }


def backtest_forecast(
    db: Session,
    dataset_id: str,
    target_column: str,
    test_size: float = 0.2,
    hyperparams: Optional[dict] = None,
) -> dict:
    """Backtest forecast accuracy using train/test split."""
    df = get_time_series_data(db, dataset_id, target_column)
    if len(df) < MIN_DATA_POINTS:
        raise ValueError(f"Minimum {MIN_DATA_POINTS} data points required")

    split_idx = int(len(df) * (1 - test_size))
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    params = hyperparams or {}
    model = Prophet(
        yearly_seasonality=params.get("yearly_seasonality", True),
        weekly_seasonality=params.get("weekly_seasonality", True),
        daily_seasonality=params.get("daily_seasonality", False),
        interval_width=0.95,
        changepoint_prior_scale=params.get("changepoint_prior_scale", 0.05),
        seasonality_prior_scale=params.get("seasonality_prior_scale", 10.0),
    )
    model.fit(train_df)

    future = model.make_future_dataframe(periods=len(test_df), freq="D")
    forecast = model.predict(future)

    test_forecast = forecast.iloc[-len(test_df):]

    metrics = calculate_model_metrics(
        test_df["y"].values, test_forecast["yhat"].values
    )
    return {
        "train_size": len(train_df),
        "test_size": len(test_df),
        "metrics": metrics,
    }


def cross_validate_forecast(
    db: Session,
    dataset_id: str,
    target_column: str,
    n_folds: int = 5,
    horizon_days: int = 30,
    hyperparams: Optional[dict] = None,
) -> dict:
    """Cross-validate forecast using rolling-origin evaluation."""
    df = get_time_series_data(db, dataset_id, target_column)
    if len(df) < MIN_DATA_POINTS * 2:
        raise ValueError(
            f"Need at least {MIN_DATA_POINTS * 2} data points for cross-validation, got {len(df)}"
        )

    total_len = len(df)
    fold_size = (total_len - MIN_DATA_POINTS) // n_folds
    if fold_size < horizon_days:
        fold_size = horizon_days

    params = hyperparams or {}
    fold_metrics = []

    for i in range(n_folds):
        cutoff_idx = MIN_DATA_POINTS + i * fold_size
        if cutoff_idx + horizon_days > total_len:
            break

        train_df = df.iloc[:cutoff_idx]
        test_df = df.iloc[cutoff_idx: cutoff_idx + horizon_days]

        model = Prophet(
            yearly_seasonality=params.get("yearly_seasonality", True),
            weekly_seasonality=params.get("weekly_seasonality", True),
            daily_seasonality=params.get("daily_seasonality", False),
            interval_width=0.95,
            changepoint_prior_scale=params.get("changepoint_prior_scale", 0.05),
            seasonality_prior_scale=params.get("seasonality_prior_scale", 10.0),
        )
        model.fit(train_df)

        future = model.make_future_dataframe(periods=len(test_df), freq="D")
        forecast = model.predict(future)
        test_forecast = forecast.iloc[-len(test_df):]

        metrics = calculate_model_metrics(
            test_df["y"].values, test_forecast["yhat"].values
        )
        metrics["fold"] = i + 1
        fold_metrics.append(metrics)

    if not fold_metrics:
        return {"error": "No folds could be computed"}

    avg_metrics = {}
    for key in fold_metrics[0]:
        if isinstance(fold_metrics[0][key], (int, float)):
            avg_metrics[key] = round(
                np.mean([m[key] for m in fold_metrics]), 4
            )

    std_metrics = {}
    for key in fold_metrics[0]:
        if isinstance(fold_metrics[0][key], (int, float)):
            std_metrics[f"{key}_std"] = round(
                np.std([m[key] for m in fold_metrics]), 4
            )

    return {
        "n_folds_computed": len(fold_metrics),
        "avg_metrics": avg_metrics,
        "std_metrics": std_metrics,
        "fold_results": fold_metrics,
    }


def tune_hyperparameters(
    db: Session,
    dataset_id: str,
    target_column: str,
    param_grid: Optional[dict] = None,
    metric: str = "rmse",
) -> dict:
    """Grid search for optimal Prophet hyperparameters using backtesting."""
    if param_grid is None:
        param_grid = {
            "changepoint_prior_scale": [0.001, 0.01, 0.05, 0.1],
            "seasonality_prior_scale": [0.01, 0.1, 1.0, 10.0],
            "yearly_seasonality": [True],
            "weekly_seasonality": [True],
            "daily_seasonality": [False],
        }

    from itertools import product

    keys = list(param_grid.keys())
    combinations = list(product(*[param_grid[k] for k in keys]))

    results = []
    for combo in combinations:
        params = dict(zip(keys, combo))
        try:
            backtest_result = backtest_forecast(
                db, dataset_id, target_column, test_size=0.2, hyperparams=params
            )
            score = backtest_result["metrics"].get(metric, float("inf"))
            results.append({"params": params, metric: score})
        except Exception:
            continue

    if not results:
        return {"error": "No hyperparameter combinations succeeded"}

    results.sort(key=lambda x: x[metric])
    return {
        "best_params": results[0]["params"],
        "best_score": {metric: results[0][metric]},
        "all_results": results,
        "n_evaluated": len(results),
    }


def get_forecast_by_id(db: Session, forecast_id: str) -> Optional[Forecast]:
    """Retrieve a forecast by ID."""
    from uuid import UUID

    try:
        return db.query(Forecast).filter(Forecast.id == UUID(forecast_id)).first()
    except (ValueError, AttributeError):
        return None


def list_forecasts(
    db: Session,
    dataset_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[Forecast]:
    """List forecasts with optional filters."""
    query = db.query(Forecast)
    if dataset_id:
        query = query.filter(Forecast.dataset_id == dataset_id)
    if status:
        query = query.filter(Forecast.status == status)
    return query.order_by(Forecast.created_at.desc()).limit(limit).all()


def forecasts_to_csv(forecast_record: Forecast) -> str:
    """Convert forecast predictions to CSV string."""
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ds", "yhat", "yhat_lower", "yhat_upper"])
    for pred in forecast_record.predictions:
        writer.writerow([
            pred["ds"],
            pred["yhat"],
            pred["yhat_lower"],
            pred["yhat_upper"],
        ])
    return output.getvalue()
