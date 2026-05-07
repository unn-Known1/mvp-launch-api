"""
Tests for automated reporting engine with AI summaries.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from models import ReportTemplate  # noqa: E402
from models import (  # noqa: E402
    Base,
    ReportDelivery,
    ScheduledReport,
    User,
)
from report_router import calculate_next_run  # noqa: E402
from report_router import (  # noqa: E402
    generate_ai_summary_from_results,
)


class TestReportRouter(unittest.TestCase):
    """Test report router helper functions."""

    def test_calculate_next_run_daily(self):
        next_run = calculate_next_run("daily", "08:00", "UTC")
        self.assertIsInstance(next_run, datetime)
        self.assertEqual(next_run.hour, 8)
        self.assertEqual(next_run.minute, 0)

    def test_calculate_next_run_past_time(self):
        now = datetime.now(dt_timezone.utc)
        time_str = f"{now.hour:02d}:{now.minute:02d}"
        next_run = calculate_next_run("daily", time_str, "UTC")
        self.assertGreater(next_run, now)

    def test_generate_ai_summary_empty(self):
        summary, insights, recommendations = generate_ai_summary_from_results(
            [], "empty query"
        )
        self.assertIn("No data found", summary)
        self.assertTrue(len(insights) > 0)
        self.assertTrue(len(recommendations) > 0)

    def test_generate_ai_summary_with_data(self):
        results = [
            {"id": 1, "value": 100, "name": "Test"},
            {"id": 2, "value": 200, "name": "Test2"},
        ]
        summary, insights, recommendations = generate_ai_summary_from_results(
            results, "test query"
        )
        self.assertIn("2 rows", summary)
        self.assertIn("value", summary)
        self.assertTrue(len(insights) > 0)


class TestReportModels(unittest.TestCase):
    """Test report database models."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

        self.user = User(
            email="reportuser@example.com",
            password_hash="hash",
            name="Report User",
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_create_report_template(self):
        template = ReportTemplate(
            user_id=self.user.id,
            name="Test Template",
            description="A test template",
            config={"queries": [], "charts": [], "datasets": []},
        )
        self.db.add(template)
        self.db.commit()
        self.assertIsNotNone(template.id)
        self.assertEqual(template.name, "Test Template")

    def test_create_scheduled_report(self):
        template = ReportTemplate(
            user_id=self.user.id,
            name="Template",
            config={"queries": [], "charts": [], "datasets": []},
        )
        self.db.add(template)
        self.db.commit()

        next_run = datetime.now(dt_timezone.utc) + timedelta(days=1)
        report = ScheduledReport(
            user_id=self.user.id,
            template_id=template.id,
            name="Daily Report",
            frequency="daily",
            time_of_day="08:00",
            timezone="UTC",
            recipients=["test@example.com"],
            is_active=True,
            next_run_at=next_run,
            config={"queries": [], "charts": [], "datasets": []},
        )
        self.db.add(report)
        self.db.commit()
        self.assertIsNotNone(report.id)
        self.assertEqual(report.frequency, "daily")
        self.assertTrue(report.is_active)

    def test_create_report_delivery(self):
        template = ReportTemplate(
            user_id=self.user.id,
            name="Template",
            config={"queries": [], "charts": [], "datasets": []},
        )
        self.db.add(template)
        self.db.commit()

        next_run = datetime.now(dt_timezone.utc) + timedelta(days=1)
        report = ScheduledReport(
            user_id=self.user.id,
            template_id=template.id,
            name="Report",
            frequency="daily",
            time_of_day="08:00",
            timezone="UTC",
            recipients=["test@example.com"],
            next_run_at=next_run,
            config={"queries": [], "charts": [], "datasets": []},
        )
        self.db.add(report)
        self.db.commit()

        delivery = ReportDelivery(
            scheduled_report_id=report.id,
            status="pending",
        )
        self.db.add(delivery)
        self.db.commit()
        self.assertIsNotNone(delivery.id)
        self.assertEqual(delivery.status, "pending")

    def test_report_template_relationships(self):
        template = ReportTemplate(
            user_id=self.user.id,
            name="Template",
            config={"queries": [], "charts": [], "datasets": []},
        )
        self.db.add(template)
        self.db.commit()

        report = ScheduledReport(
            user_id=self.user.id,
            template_id=template.id,
            name="Report",
            frequency="weekly",
            time_of_day="09:00",
            timezone="UTC",
            recipients=["test@example.com"],
            config={"queries": [], "charts": [], "datasets": []},
        )
        self.db.add(report)
        self.db.commit()

        self.assertEqual(report.template.id, template.id)
        self.assertIn(report, template.scheduled_reports)


class TestReportAPI(unittest.TestCase):
    """Test report API endpoints."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )

        self.db = self.engine.connect()

    def tearDown(self):
        self.db.close()

    def test_ai_summary_api(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from auth import get_current_user
        from report_router import router

        app = FastAPI()
        app.include_router(router)

        def override_get_db():
            yield self.db

        from report_router import get_db

        app.dependency_overrides[get_db] = override_get_db

        # Mock the current user
        test_user = type(
            "User", (), {"id": "test-user-id", "email": "test@example.com"}
        )()
        app.dependency_overrides[get_current_user] = lambda: test_user

        client = TestClient(app)

        response = client.post(
            "/api/v1/reports/ai-summary",
            json={
                "query_results": [
                    {"id": 1, "value": 100},
                    {"id": 2, "value": 200},
                ],
                "query_description": "test summary",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("summary", data)
        self.assertIn("key_insights", data)
        self.assertIn("recommendations", data)


if __name__ == "__main__":
    unittest.main()
