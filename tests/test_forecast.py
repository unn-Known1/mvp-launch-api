"""
Tests for Prophet forecasting module.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from forecast import (
    backtest_forecast,
    calculate_model_metrics,
    compute_model_version,
    cross_validate_forecast,
    generate_forecast,
    get_forecast_by_id,
    get_time_series_data,
    list_forecasts,
    tune_hyperparameters,
)
from models import DataRecord, Dataset, Forecast


def create_mock_dataset(id="ds-1", status="ready"):
    ds = MagicMock(spec=Dataset)
    ds.id = id
    ds.status = status
    return ds


def create_mock_record(dataset_id, data, created_at=None):
    rec = MagicMock(spec=DataRecord)
    rec.dataset_id = dataset_id
    rec.data = data
    rec.created_at = created_at or datetime.now(timezone.utc)
    return rec


class TestGetTimeSeriesData:
    def test_extracts_numeric_data(self):
        ds_id = "test-ds-1"
        base_time = datetime.now(timezone.utc)
        records = [
            create_mock_record(ds_id, {"sales": 100}, base_time),
            create_mock_record(ds_id, {"sales": 150}, base_time + timedelta(days=1)),
            create_mock_record(ds_id, {"sales": 200}, base_time + timedelta(days=2)),
        ]
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            records
        )

        df = get_time_series_data(mock_session, ds_id, "sales")

        assert len(df) == 3
        assert list(df.columns) == ["ds", "y"]
        assert list(df["y"]) == [100.0, 150.0, 200.0]

    def test_skips_non_numeric_values(self):
        ds_id = "test-ds-2"
        records = [
            create_mock_record(ds_id, {"sales": 100}),
            create_mock_record(ds_id, {"sales": "not_a_number"}),
            create_mock_record(ds_id, {"sales": 300}),
        ]
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            records
        )

        df = get_time_series_data(mock_session, ds_id, "sales")

        assert len(df) == 2
        assert list(df["y"]) == [100.0, 300.0]

    def test_handles_missing_column(self):
        ds_id = "test-ds-3"
        records = [
            create_mock_record(ds_id, {"other_col": 100}),
        ]
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            records
        )

        df = get_time_series_data(mock_session, ds_id, "sales")

        assert len(df) == 0


class TestCalculateModelMetrics:
    def test_calculates_metrics_correctly(self):
        actual = [100.0, 200.0, 300.0]
        predicted = [110.0, 190.0, 310.0]

        metrics = calculate_model_metrics(actual, predicted)

        assert "mae" in metrics
        assert "mse" in metrics
        assert "rmse" in metrics
        assert "mape" in metrics
        assert "r_squared" in metrics
        assert "mase" in metrics
        assert metrics["mae"] >= 0
        assert metrics["rmse"] >= 0

    def test_handles_zero_mean(self):
        actual = [0.0, 0.0, 0.0]
        predicted = [0.0, 0.0, 0.0]

        metrics = calculate_model_metrics(actual, predicted)

        assert metrics["mape"] == 0.0

    def test_handles_near_zero_actuals(self):
        """MAPE should not explode on near-zero actual values."""
        actual = [1e-11, 1e-12, 1e-11]
        predicted = [0.5, 0.5, 0.5]

        metrics = calculate_model_metrics(actual, predicted)

        assert isinstance(metrics["mape"], float)
        assert not (metrics["mape"] != metrics["mape"])

    def test_r_squared_range(self):
        actual = [1.0, 2.0, 3.0, 4.0, 5.0]
        predicted = [1.1, 2.1, 2.9, 4.2, 4.8]

        metrics = calculate_model_metrics(actual, predicted)

        assert -1.0 <= metrics["r_squared"] <= 1.0

    def test_perfect_prediction_r_squared(self):
        actual = [1.0, 2.0, 3.0, 4.0, 5.0]
        predicted = [1.0, 2.0, 3.0, 4.0, 5.0]

        metrics = calculate_model_metrics(actual, predicted)

        assert metrics["r_squared"] == 1.0
        assert metrics["mae"] == 0.0
        assert metrics["rmse"] == 0.0


class TestModelVersioning:
    def test_model_version_deterministic(self):
        v1 = compute_model_version(
            model_type="prophet",
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            data_hash="abc123",
        )
        v2 = compute_model_version(
            model_type="prophet",
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            data_hash="abc123",
        )
        assert v1 == v2

    def test_model_version_differs_by_hyperparams(self):
        v1 = compute_model_version(
            model_type="prophet",
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            data_hash="abc123",
        )
        v2 = compute_model_version(
            model_type="prophet",
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.1,
            data_hash="abc123",
        )
        assert v1 != v2


class TestGenerateForecast:
    @patch("forecast.Prophet")
    @patch("forecast.get_time_series_data")
    def test_generates_forecast_successfully(self, mock_get_data, mock_prophet):
        ds_id = "test-ds-forecast"
        mock_dataset = create_mock_dataset(ds_id)
        mock_session = MagicMock()

        def query_side_effect(model):
            if model == Dataset:
                mock_q = MagicMock()
                mock_q.filter.return_value.first.return_value = mock_dataset
                return mock_q
            return MagicMock()

        mock_session.query.side_effect = query_side_effect

        mock_get_data.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=30),
                "y": [100.0 + i for i in range(30)],
            }
        )

        mock_model = MagicMock()
        mock_prophet.return_value = mock_model
        future_df = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=40)})
        mock_model.make_future_dataframe.return_value = future_df
        mock_model.predict.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=40),
                "yhat": [150.0] * 40,
                "yhat_lower": [140.0] * 40,
                "yhat_upper": [160.0] * 40,
            }
        )

        forecast = generate_forecast(mock_session, ds_id, "sales", 10, "D")

        assert forecast.status == "completed"
        assert len(forecast.predictions) > 0
        assert forecast.model_metrics is not None
        assert "model_version" in forecast.model_metrics
        assert "hyperparameters" in forecast.model_metrics
        assert "r_squared" in forecast.model_metrics
        assert "mase" in forecast.model_metrics

    @patch("forecast.Prophet")
    @patch("forecast.get_time_series_data")
    def test_generates_forecast_with_hyperparams(self, mock_get_data, mock_prophet):
        ds_id = "test-ds-forecast-hp"
        mock_dataset = create_mock_dataset(ds_id)
        mock_session = MagicMock()

        def query_side_effect(model):
            if model == Dataset:
                mock_q = MagicMock()
                mock_q.filter.return_value.first.return_value = mock_dataset
                return mock_q
            return MagicMock()

        mock_session.query.side_effect = query_side_effect
        mock_get_data.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=30),
                "y": [100.0 + i for i in range(30)],
            }
        )

        mock_model = MagicMock()
        mock_prophet.return_value = mock_model
        future_df = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=40)})
        mock_model.make_future_dataframe.return_value = future_df
        mock_model.predict.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=40),
                "yhat": [150.0] * 40,
                "yhat_lower": [140.0] * 40,
                "yhat_upper": [160.0] * 40,
            }
        )

        hyperparams = {
            "changepoint_prior_scale": 0.1,
            "seasonality_prior_scale": 5.0,
            "daily_seasonality": True,
        }
        forecast = generate_forecast(
            mock_session, ds_id, "sales", 10, "D", hyperparams=hyperparams
        )

        assert forecast.status == "completed"
        assert (
            forecast.model_metrics["hyperparameters"]["changepoint_prior_scale"] == 0.1
        )

    def test_raises_error_for_insufficient_data(self):
        ds_id = "test-ds-small"
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            []
        )

        with pytest.raises(ValueError, match="Insufficient data"):
            generate_forecast(mock_session, ds_id, "sales", 10)


class TestBacktestForecast:
    @patch("forecast.Prophet")
    @patch("forecast.get_time_series_data")
    def test_backtest_returns_metrics(self, mock_get_data, mock_prophet):
        mock_get_data.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=50),
                "y": [100.0 + i + (i % 7) * 5 for i in range(50)],
            }
        )

        mock_model = MagicMock()
        mock_prophet.return_value = mock_model
        future_df = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=60)})
        mock_model.make_future_dataframe.return_value = future_df
        mock_model.predict.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=60),
                "yhat": [150.0] * 60,
                "yhat_lower": [140.0] * 60,
                "yhat_upper": [160.0] * 60,
            }
        )

        mock_session = MagicMock()
        result = backtest_forecast(mock_session, "ds-1", "sales", test_size=0.2)

        assert "train_size" in result
        assert "test_size" in result
        assert "metrics" in result
        assert "mae" in result["metrics"]


class TestCrossValidateForecast:
    @patch("forecast.Prophet")
    @patch("forecast.get_time_series_data")
    def test_cross_validation_returns_folds(self, mock_get_data, mock_prophet):
        mock_get_data.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=200),
                "y": [100.0 + i + (i % 7) * 5 for i in range(200)],
            }
        )

        mock_model = MagicMock()
        mock_prophet.return_value = mock_model
        future_df = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=250)})
        mock_model.make_future_dataframe.return_value = future_df
        mock_model.predict.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=250),
                "yhat": [150.0] * 250,
                "yhat_lower": [140.0] * 250,
                "yhat_upper": [160.0] * 250,
            }
        )

        mock_session = MagicMock()
        result = cross_validate_forecast(
            mock_session, "ds-1", "sales", n_folds=3, horizon_days=10
        )

        assert "n_folds_computed" in result
        assert "avg_metrics" in result
        assert "std_metrics" in result
        assert result["n_folds_computed"] > 0


class TestTuneHyperparameters:
    @patch("forecast.backtest_forecast")
    @patch("forecast.get_time_series_data")
    def test_tuning_returns_best_params(self, mock_get_data, mock_backtest):
        mock_get_data.return_value = pd.DataFrame(
            {
                "ds": pd.date_range("2024-01-01", periods=50),
                "y": [100.0 + i for i in range(50)],
            }
        )

        mock_backtest.return_value = {
            "train_size": 40,
            "test_size": 10,
            "metrics": {"mae": 5.0, "rmse": 6.0},
        }

        mock_session = MagicMock()
        result = tune_hyperparameters(
            mock_session,
            "ds-1",
            "sales",
            param_grid={
                "changepoint_prior_scale": [0.01, 0.05],
                "seasonality_prior_scale": [1.0, 10.0],
                "yearly_seasonality": [True],
                "weekly_seasonality": [True],
                "daily_seasonality": [False],
            },
        )

        assert "best_params" in result
        assert "best_score" in result
        assert "all_results" in result
        assert result["n_evaluated"] > 0


class TestGetForecastById:
    def test_returns_forecast_when_found(self):
        from uuid import uuid4

        forecast = MagicMock(spec=Forecast)
        forecast.id = uuid4()
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            forecast
        )

        result = get_forecast_by_id(mock_session, str(forecast.id))

        assert result == forecast

    def test_returns_none_when_not_found(self):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = get_forecast_by_id(mock_session, "nonexistent")

        assert result is None


class TestListForecasts:
    def test_lists_all_forecasts(self):
        mock_session = MagicMock()
        mock_session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            MagicMock(spec=Forecast),
            MagicMock(spec=Forecast),
        ]

        results = list_forecasts(mock_session)

        assert len(results) == 2

    def test_filters_by_dataset_id(self):
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.limit.return_value.all.return_value = []

        list_forecasts(mock_session, dataset_id="ds-1")

        assert mock_query.filter.call_count >= 1
