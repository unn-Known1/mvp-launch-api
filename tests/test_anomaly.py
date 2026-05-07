"""
Tests for anomaly detection system.
"""

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anomaly import (
    calculate_z_score,
    calculate_iqr_bounds,
    get_threshold_for_metric,
    update_anomaly_status,
    detect_anomalies_for_metric,
    extract_numeric_metrics,
    set_metric_threshold,
    scan_all_datasets,
    compute_anomaly_scores,
    compute_model_version,
)
from models import (
    Anomaly,
    AnomalyThreshold,
    DataRecord,
    Dataset,
    User,
    Base,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestAnomalyCalculations(unittest.TestCase):
    """Test statistical calculation functions."""

    def test_calculate_z_score_normal(self):
        z = calculate_z_score(100, 90, 10)
        self.assertAlmostEqual(z, 1.0, places=2)

    def test_calculate_z_score_zero_stddev(self):
        z = calculate_z_score(100, 90, 0)
        self.assertEqual(z, 0.0)

    def test_calculate_iqr_bounds(self):
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        lower, upper = calculate_iqr_bounds(values, multiplier=1.5)
        self.assertLess(lower, 20)
        self.assertGreater(upper, 90)

    def test_calculate_iqr_bounds_single_value(self):
        lower, upper = calculate_iqr_bounds([50], multiplier=3)
        self.assertEqual(lower, 50.0)
        self.assertEqual(upper, 50.0)

    def test_calculate_iqr_bounds_empty(self):
        lower, upper = calculate_iqr_bounds([], multiplier=3)
        self.assertEqual(lower, 0.0)
        self.assertEqual(upper, 0.0)

    def test_calculate_iqr_bounds_two_values(self):
        lower, upper = calculate_iqr_bounds([10, 20], multiplier=1.5)
        self.assertLessEqual(lower, 10)
        self.assertGreaterEqual(upper, 20)

    def test_iqr_proper_percentile(self):
        """Verify IQR uses percentile interpolation, not index-based."""
        values = list(range(1, 101))
        lower, upper = calculate_iqr_bounds(values, multiplier=1.5)
        # Q1=25.75, Q3=75.25, IQR=49.5
        # lower = 25.75 - 1.5*49.5 = -48.5
        # upper = 75.25 + 1.5*49.5 = 149.5
        self.assertAlmostEqual(lower, -48.5, delta=1.0)
        self.assertAlmostEqual(upper, 149.5, delta=1.0)


class TestAnomalyScores(unittest.TestCase):
    """Test anomaly evaluation metrics."""

    def test_compute_anomaly_scores_insufficient_data(self):
        result = compute_anomaly_scores([1.0, 2.0])
        self.assertEqual(result["anomaly_count"], 0)
        self.assertEqual(result["anomaly_rate"], 0.0)

    def test_compute_anomaly_scores_normal_data(self):
        values = [10.0] * 20
        result = compute_anomaly_scores(values)
        self.assertEqual(result["anomaly_count"], 0)
        self.assertEqual(result["std_dev"], 0.0)

    def test_compute_anomaly_scores_with_outliers(self):
        values = [10.0] * 18 + [100.0, 200.0]
        result = compute_anomaly_scores(values)
        self.assertGreater(result["anomaly_count"], 0)
        self.assertGreater(result["max_z_score"], 0)

    def test_compute_anomaly_scores_returns_all_keys(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]
        result = compute_anomaly_scores(values)
        expected_keys = [
            "num_points", "anomaly_count", "anomaly_rate", "mean",
            "std_dev", "skewness", "kurtosis", "max_z_score",
            "iqr_lower", "iqr_upper", "detection_summary",
        ]
        for key in expected_keys:
            self.assertIn(key, result)


class TestModelVersioning(unittest.TestCase):
    """Test model version generation."""

    def test_model_version_deterministic(self):
        v1 = compute_model_version(z_threshold=3.0, iqr_multiplier=3.0, data_hash="abc123")
        v2 = compute_model_version(z_threshold=3.0, iqr_multiplier=3.0, data_hash="abc123")
        self.assertEqual(v1, v2)

    def test_model_version_differs_by_params(self):
        v1 = compute_model_version(z_threshold=3.0, iqr_multiplier=3.0, data_hash="abc123")
        v2 = compute_model_version(z_threshold=2.0, iqr_multiplier=3.0, data_hash="abc123")
        self.assertNotEqual(v1, v2)

    def test_model_version_differs_by_data(self):
        v1 = compute_model_version(z_threshold=3.0, iqr_multiplier=3.0, data_hash="abc123")
        v2 = compute_model_version(z_threshold=3.0, iqr_multiplier=3.0, data_hash="def456")
        self.assertNotEqual(v1, v2)


class TestAnomalyService(unittest.TestCase):
    """Test anomaly detection service functions."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

        self.user = User(
            email="test@example.com",
            password_hash="hash",
            name="Test User",
        )
        self.db.add(self.user)
        self.db.commit()

        self.dataset = Dataset(
            name="Test Dataset",
            user_id=self.user.id,
            status="ready",
        )
        self.db.add(self.dataset)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_get_threshold_default(self):
        z, iqr, enabled = get_threshold_for_metric(
            self.db, self.dataset.id, "temperature"
        )
        self.assertEqual(z, 3)
        self.assertEqual(iqr, 3)
        self.assertTrue(enabled)

    def test_get_threshold_custom(self):
        threshold = AnomalyThreshold(
            dataset_id=self.dataset.id,
            metric_name="temperature",
            z_score_threshold=2,
            iqr_multiplier=2,
            enabled=True,
        )
        self.db.add(threshold)
        self.db.commit()

        z, iqr, enabled = get_threshold_for_metric(
            self.db, self.dataset.id, "temperature"
        )
        self.assertEqual(z, 2)
        self.assertEqual(iqr, 2)
        self.assertTrue(enabled)

    def test_update_anomaly_status(self):
        anomaly = Anomaly(
            dataset_id=self.dataset.id,
            metric_name="temperature",
            timestamp=datetime.now(timezone.utc),
            expected_value="20.0",
            actual_value="35.0",
            severity="high",
            detection_method="z_score",
            status="flagged",
        )
        self.db.add(anomaly)
        self.db.commit()

        result = update_anomaly_status(
            self.db, str(anomaly.id), "investigated", str(self.user.id), "Checked it"
        )
        self.assertEqual(result.status, "investigated")
        self.assertEqual(result.notes, "Checked it")
        self.assertIsNotNone(result.investigated_at)

    def test_update_anomaly_not_found(self):
        result = update_anomaly_status(
            self.db, "nonexistent-id", "investigated", str(self.user.id)
        )
        self.assertIsNone(result)


class TestAnomalyDetection(unittest.TestCase):
    """Test end-to-end anomaly detection."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

        self.user = User(
            email="test2@example.com",
            password_hash="hash",
            name="Test User 2",
        )
        self.db.add(self.user)
        self.db.commit()

        self.dataset = Dataset(
            name="Test Dataset 2",
            user_id=self.user.id,
            status="ready",
        )
        self.db.add(self.dataset)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch("anomaly.get_time_series_for_metric")
    def test_detect_z_score_anomaly(self, mock_get_series):
        mock_get_series.return_value = [
            (datetime(2024, 1, 1), 20.0),
            (datetime(2024, 1, 2), 21.0),
            (datetime(2024, 1, 3), 22.0),
            (datetime(2024, 1, 4), 23.0),
            (datetime(2024, 1, 5), 24.0),
            (datetime(2024, 1, 6), 100.0),
        ]

        anomalies = detect_anomalies_for_metric(
            self.db, self.dataset.id, "temperature"
        )
        self.assertGreater(len(anomalies), 0)
        self.assertTrue(
            "z_score" in anomalies[0].detection_method or
            "iqr" in anomalies[0].detection_method
        )

    @patch("anomaly.get_time_series_for_metric")
    def test_detect_anomaly_has_model_version(self, mock_get_series):
        mock_get_series.return_value = [
            (datetime(2024, 1, i), float(20 + i)) for i in range(1, 8)
        ]
        mock_get_series.return_value.append((datetime(2024, 1, 8), 200.0))

        anomalies = detect_anomalies_for_metric(
            self.db, self.dataset.id, "value"
        )
        self.assertGreater(len(anomalies), 0)
        self.assertIsNotNone(anomalies[0].model_version)
        self.assertIsInstance(anomalies[0].model_version, str)
        self.assertGreater(len(anomalies[0].model_version), 0)

    @patch("anomaly.get_time_series_for_metric")
    def test_detect_anomaly_has_confidence(self, mock_get_series):
        mock_get_series.return_value = [
            (datetime(2024, 1, i), float(20 + i)) for i in range(1, 8)
        ]
        mock_get_series.return_value.append((datetime(2024, 1, 8), 200.0))

        anomalies = detect_anomalies_for_metric(
            self.db, self.dataset.id, "value"
        )
        self.assertGreater(len(anomalies), 0)
        self.assertIsInstance(anomalies[0].confidence, float)
        self.assertGreaterEqual(anomalies[0].confidence, 0.0)
        self.assertLessEqual(anomalies[0].confidence, 1.0)

    @patch("anomaly.get_time_series_for_metric")
    def test_no_anomaly_for_normal_data(self, mock_get_series):
        mock_get_series.return_value = [
            (datetime(2024, 1, i), float(20 + i))
            for i in range(1, 10)
        ]

        anomalies = detect_anomalies_for_metric(
            self.db, self.dataset.id, "temperature"
        )
        self.assertEqual(len(anomalies), 0)

    def test_extract_numeric_metrics(self):
        for i in range(5):
            record = DataRecord(
                dataset_id=self.dataset.id,
                data={"temp": 20.0 + i, "humidity": 50.0 + i, "name": "sensor"},
            )
            self.db.add(record)
        self.db.commit()

        metrics = extract_numeric_metrics(self.db, self.dataset.id)
        self.assertIn("temp", metrics)
        self.assertIn("humidity", metrics)
        self.assertNotIn("name", metrics)


class TestThresholdManagement(unittest.TestCase):
    """Test threshold configuration."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

        self.user = User(
            email="threshold@example.com",
            password_hash="hash",
            name="Threshold User",
        )
        self.db.add(self.user)
        self.db.commit()

        self.dataset = Dataset(
            name="Threshold Test Dataset",
            user_id=self.user.id,
            status="ready",
        )
        self.db.add(self.dataset)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_set_metric_threshold_new(self):
        result = set_metric_threshold(
            self.db, self.dataset.id, "cpu_usage", z_score_threshold=2, iqr_multiplier=2
        )
        self.assertEqual(result.metric_name, "cpu_usage")
        self.assertEqual(result.z_score_threshold, 2)

    def test_set_metric_threshold_update(self):
        set_metric_threshold(
            self.db, self.dataset.id, "cpu_usage", z_score_threshold=2
        )
        result = set_metric_threshold(
            self.db, self.dataset.id, "cpu_usage", z_score_threshold=4
        )
        self.assertEqual(result.z_score_threshold, 4)

    def test_scan_all_datasets(self):
        """Test scanning all datasets for anomalies."""
        from anomaly import create_notifications

        for i in range(5):
            record = DataRecord(
                dataset_id=self.dataset.id,
                data={"metric1": 20.0 + i},
            )
            self.db.add(record)
        self.db.commit()

        with patch("anomaly.get_time_series_for_metric") as mock_get_series:
            mock_get_series.return_value = [
                (datetime(2024, 1, 1), 20.0),
                (datetime(2024, 1, 2), 21.0),
                (datetime(2024, 1, 3), 22.0),
                (datetime(2024, 1, 4), 23.0),
                (datetime(2024, 1, 5), 100.0),
            ]

            user = User(
                email="scanner@example.com",
                password_hash="hash",
                name="Scanner User",
            )
            self.db.add(user)
            self.db.commit()

            results = scan_all_datasets(self.db, str(user.id))
            self.assertIsInstance(results, dict)


if __name__ == "__main__":
    unittest.main()
