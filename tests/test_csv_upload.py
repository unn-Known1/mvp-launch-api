"""
Tests for CSV upload and auto-detection pipeline.
"""

import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from csv_upload_router import detect_column_type
from models import Dataset, DataRecord, ImportBatch, Base
from database import engine


class TestColumnTypeDetection(unittest.TestCase):
    """Test auto-detection of column types."""

    def test_integer_column_detection(self):
        series = pd.Series([1, 2, 3, 4, 5])
        self.assertEqual(detect_column_type(series), "number")

    def test_float_column_detection(self):
        series = pd.Series([1.1, 2.2, 3.3])
        self.assertEqual(detect_column_type(series), "number")

    def test_string_column_detection(self):
        series = pd.Series(["a", "b", "c"])
        self.assertEqual(detect_column_type(series), "string")

    def test_boolean_column_detection(self):
        series = pd.Series([True, False, True])
        self.assertEqual(detect_column_type(series), "boolean")

    def test_date_column_detection_from_string(self):
        series = pd.Series(["2024-01-01", "2024-01-02", "2024-01-03"])
        self.assertEqual(detect_column_type(series), "date")

    def test_boolean_string_detection(self):
        series = pd.Series(["true", "false", "true"])
        self.assertEqual(detect_column_type(series), "boolean")


class TestCSVUploadEndpoints(unittest.TestCase):
    """Test CSV upload API endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.test_csv_content = b"name,age,active,joined\nAlice,30,true,2024-01-01\nBob,25,false,2024-02-01\nCharlie,35,true,2024-03-01\n"
        self.test_csv_file = io.BytesIO(self.test_csv_content)

    def test_detect_csv_types(self):
        """Test the /detect endpoint returns correct type info."""
        response = self.client.post(
            "/api/v1/csv/detect",
            files={"file": ("test.csv", self.test_csv_content, "text/csv")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["filename"], "test.csv")
        self.assertEqual(data["row_count"], 3)
        self.assertEqual(data["column_count"], 4)

        columns = {c["name"]: c["inferred_type"] for c in data["columns"]}
        self.assertEqual(columns["name"], "string")
        self.assertEqual(columns["age"], "number")
        self.assertEqual(columns["active"], "boolean")
        self.assertEqual(columns["joined"], "date")

    def test_detect_non_csv_file_rejected(self):
        """Test that non-CSV files are rejected."""
        response = self.client.post(
            "/api/v1/csv/detect",
            files={"file": ("test.txt", b"some content", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_detect_file_too_large(self):
        """Test that files over 100MB are rejected."""
        large_file = b"a,b\n" + b"1,2\n" * (50 * 1024 * 1024 // 4)
        response = self.client.post(
            "/api/v1/csv/detect",
            files={"file": ("large.csv", large_file, "text/csv")},
        )
        self.assertEqual(response.status_code, 413)

    @patch("csv_upload_router.SessionLocal")
    def test_upload_csv_success(self, mock_session):
        """Test successful CSV upload and storage."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_db

        response = self.client.post(
            "/api/v1/csv/upload",
            files={"file": ("data.csv", self.test_csv_content, "text/csv")},
            data={"dataset_name": "Test Dataset"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("dataset", data)
        self.assertIn("import_batch", data)
        self.assertIn("detection", data)

        self.assertEqual(data["dataset"]["name"], "Test Dataset")
        self.assertEqual(data["dataset"]["status"], "ready")
        self.assertEqual(data["dataset"]["row_count"], 3)

        self.assertEqual(data["import_batch"]["status"], "completed")
        self.assertEqual(data["import_batch"]["total_rows"], 3)

        columns = {c["name"]: c["inferred_type"] for c in data["detection"]["columns"]}
        self.assertEqual(columns["name"], "string")
        self.assertEqual(columns["age"], "number")

    def test_upload_non_csv_file_rejected(self):
        """Test that non-CSV files are rejected on upload."""
        response = self.client.post(
            "/api/v1/csv/upload",
            files={"file": ("test.txt", b"some content", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_list_csv_datasets(self):
        """Test listing CSV datasets."""
        response = self.client.get("/api/v1/csv/datasets")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)


if __name__ == "__main__":
    unittest.main()
