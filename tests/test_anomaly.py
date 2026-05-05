"""
Tests for anomaly detection system.
"""

import os
import sys
import unittest
from datetime import datetime
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
        self.assertEqual(lower, upper)


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
            self.db, str(self.dataset.id), "temperature"
        )
        self.assertEqual(z, 3)
        self.assertEqual(iqr, 3)
        self.assertTrue(enabled)

    def test_get_threshold_custom(self):
        threshold = AnomalyThreshold(
            dataset_id=str(self.dataset.id),
            metric_name="temperature",
            z_score_threshold=2,
            iqr_multiplier=2,
            enabled=True,
        )
        self.db.add(threshold)
        self.db.commit()

        z, iqr, enabled = get_threshold_for_metric(
            self.db, str(self.dataset.id), "temperature"
        )
        self.assertEqual(z, 2)
        self.assertEqual(iqr, 2)
        self.assertTrue(enabled)

    def test_update_anomaly_status(self):
        anomaly = Anomaly(
            dataset_id=str(self.dataset.id),
            metric_name="temperature",
            timestamp=datetime.utcnow(),
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
            (datetime(2024, 1, 5), 100.0),
        ]

        anomalies = detect_anomalies_for_metric(
            self.db, str(self.dataset.id), "temperature"
        )
        self.assertGreater(len(anomalies), 0)
        self.assertEqual(anomalies[0].detection_method, "z_score")

    @patch("anomaly.get_time_series_for_metric")
    def test_detect_iqr_anomaly(self, mock_get_series):
        mock_get_series.return_value = [
            (datetime(2024, 1, 1), 10.0),
            (datetime(2024, 1, 2), 12.0),
            (datetime(2024, 1, 3), 11.0),
            (datetime(2024, 1, 4), 13.0),
            (datetime(2024, 1, 5), 14.0),
            (datetime(2024, 1, 6), 15.0),
            (datetime(2024, 1, 7), 200.0),
        ]

        anomalies = detect_anomalies_for_metric(
            self.db, str(self.dataset.id), "value"
        )
        self.assertGreater(len(anomalies), 0)

    @patch("anomaly.get_time_series_for_metric")
    def test_no_anomaly_for_normal_data(self, mock_get_series):
        mock_get_series.return_value = [
            (datetime(2024, 1, i), float(20 + i))
            for i in range(1, 10)
        ]

        anomalies = detect_anomalies_for_metric(
            self.db, str(self.dataset.id), "temperature"
        )
        self.assertEqual(len(anomalies), 0)

    def test_extract_numeric_metrics(self):
        for i in range(5):
            record = DataRecord(
                dataset_id=str(self.dataset.id),
                data={"temp": 20.0 + i, "humidity": 50.0 + i, "name": "sensor"},
            )
            self.db.add(record)
        self.db.commit()

        metrics = extract_numeric_metrics(self.db, str(self.dataset.id))
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

        self.dataset = Dataset(
            name="Threshold Test Dataset",
            user_id=None,
            status="ready",
        )
        self.db.add(self.dataset)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_set_metric_threshold_new(self):
        result = set_metric_threshold(
            self.db, str(self.dataset.id), "cpu_usage", z_score_threshold=2, iqr_multiplier=2
        )
        self.assertEqual(result.metric_name, "cpu_usage")
        self.assertEqual(result.z_score_threshold, 2)

    def test_set_metric_threshold_update(self):
        set_metric_threshold(
            self.db, str(self.dataset.id), "cpu_usage", z_score_threshold=2
        )
        result = set_metric_threshold(
            self.db, str(self.dataset.id), "cpu_usage", z_score_threshold=4
        )
        self.assertEqual(result.z_score_threshold, 4)


if __name__ == "__main__":
    unittest.main()
