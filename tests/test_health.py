import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scheduler_status import record_job_success
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class TestHealthEndpoint(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.status_file = base_path / "scheduler_status.json"
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.app = create_dashboard_app(storage_service=self.store)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("app.web.app.validate_configuration")
    @patch("app.web.app.get_scheduler_health_status")
    def test_health_returns_ok_with_database(
        self,
        mock_scheduler_status,
        mock_validate_configuration,
    ):
        mock_scheduler_status.return_value = "unknown"
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"], "ok")
        self.assertEqual(payload["scheduler"], "unknown")
        self.assertEqual(payload["configuration"], "ok")
        self.assertEqual(payload["missing_config"], [])
        self.assertTrue(payload["timestamp"])

    @patch("app.web.app.validate_configuration")
    @patch("app.web.app.get_scheduler_health_status")
    def test_health_reflects_scheduler_status(
        self,
        mock_scheduler_status,
        mock_validate_configuration,
    ):
        mock_scheduler_status.return_value = "ok"
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self.client.get("/health")

        payload = response.json()
        self.assertEqual(payload["scheduler"], "ok")

    @patch("app.web.app.validate_configuration")
    @patch("app.web.app._check_database_health")
    @patch("app.web.app.get_scheduler_health_status")
    def test_health_reports_database_error(
        self,
        mock_scheduler_status,
        mock_database_health,
        mock_validate_configuration,
    ):
        mock_scheduler_status.return_value = "unknown"
        mock_database_health.return_value = "error"
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self.client.get("/health")

        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["database"], "error")

    def test_health_scheduler_status_from_file(self):
        record_job_success("daily_monitors", status_file=self.status_file)

        with patch(
            "app.scheduler_status.DEFAULT_STATUS_FILE",
            self.status_file,
        ), patch(
            "app.web.app.validate_configuration",
            return_value={
                "status": "ok",
                "missing": [],
                "warnings": [],
            },
        ):
            app = create_dashboard_app(storage_service=self.store)
            client = TestClient(app)
            response = client.get("/health")

        payload = response.json()
        self.assertEqual(payload["scheduler"], "ok")


if __name__ == "__main__":
    unittest.main()
