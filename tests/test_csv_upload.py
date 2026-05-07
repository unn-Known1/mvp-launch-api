"""
Tests for CSV upload and auto-detection pipeline.
"""

import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app  # noqa: E402
from csv_upload_router import detect_column_type  # noqa: E402
from auth import get_current_user  # noqa: E402


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
        from collections import namedtuple
        MockUser = namedtuple("MockUser", ["id", "email", "name", "is_active"])
        cls.mock_user = MockUser(
            id="test-user-id", email="test@test.com", name="test", is_active=True
        )
        app.dependency_overrides[get_current_user] = lambda: cls.mock_user
        cls.client = TestClient(app)

    def setUp(self):
        csv_lines = [
            "name,age,active,joined",
            "Alice,30,true,2024-01-01",
            "Bob,25,false,2024-02-01",
            "Charlie,35,true,2024-03-01",
        ]
        self.test_csv_content = "\n".join(csv_lines).encode()
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
        large_content = b"x" * (100 * 1024 * 1024 + 1)  # Just over 100MB
        response = self.client.post(
            "/api/v1/csv/detect",
            files={"file": ("large.csv", large_content, "text/csv")},
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
            "/api/v1/csv/upload?dataset_name=Test%20Dataset",
            files={"file": ("data.csv", self.test_csv_content, "text/csv")},
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

    @patch("csv_upload_router.SessionLocal")
    def test_list_csv_datasets(self, mock_session):
        """Test listing CSV datasets."""
        mock_db = MagicMock()
        mock_dataset = MagicMock()
        mock_dataset.id = "123"
        mock_dataset.name = "Test"
        mock_dataset.description = None
        mock_dataset.row_count = 10
        mock_dataset.size_bytes = 100
        mock_dataset.status = "ready"
        mock_dataset.schema = {"columns": []}
        mock_dataset.created_at = None
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_dataset]
        mock_session.return_value = mock_db

        response = self.client.get("/api/v1/csv/datasets")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)


if __name__ == "__main__":
    unittest.main()
