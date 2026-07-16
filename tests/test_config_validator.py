import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config.validator import validate_configuration
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class TestConfigValidator(unittest.TestCase):

    def test_all_variables_exist(self):
        result = validate_configuration(
            {
                "OPENAI_API_KEY": "sk-test",
                "FIRECRAWL_API_KEY": "fc-test",
                "SMTP_PASSWORD": "smtp-secret",
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["warnings"], [])

    def test_missing_openai_key(self):
        result = validate_configuration(
            {
                "FIRECRAWL_API_KEY": "fc-test",
                "SMTP_PASSWORD": "smtp-secret",
            }
        )

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["missing"], ["OPENAI_API_KEY"])

    def test_missing_firecrawl_key(self):
        result = validate_configuration(
            {
                "OPENAI_API_KEY": "sk-test",
                "SMTP_PASSWORD": "smtp-secret",
            }
        )

        self.assertEqual(result["status"], "warning")
        self.assertEqual(result["missing"], ["FIRECRAWL_API_KEY"])

    def test_optional_smtp_missing(self):
        result = validate_configuration(
            {
                "OPENAI_API_KEY": "sk-test",
                "FIRECRAWL_API_KEY": "fc-test",
            }
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["warnings"], ["SMTP_PASSWORD is not set (optional)"])

    @patch("app.web.app.validate_configuration")
    @patch("app.web.app.get_scheduler_health_status")
    def test_health_api_configuration_ok(
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

        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            base_path = Path(temp_dir.name)
            store = StorageService(
                db_path=base_path / "storage.db",
                raw_dir=base_path / "raw",
                meta_file=base_path / "snapshots.json",
            )
            client = TestClient(create_dashboard_app(storage_service=store))
            response = client.get("/health")
        finally:
            temp_dir.cleanup()

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["configuration"], "ok")
        self.assertEqual(payload["missing_config"], [])
        self.assertEqual(payload["status"], "ok")

    @patch("app.web.app.validate_configuration")
    @patch("app.web.app.get_scheduler_health_status")
    def test_health_api_configuration_warning(
        self,
        mock_scheduler_status,
        mock_validate_configuration,
    ):
        mock_scheduler_status.return_value = "unknown"
        mock_validate_configuration.return_value = {
            "status": "warning",
            "missing": ["OPENAI_API_KEY"],
            "warnings": ["SMTP_PASSWORD is not set (optional)"],
        }

        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            base_path = Path(temp_dir.name)
            store = StorageService(
                db_path=base_path / "storage.db",
                raw_dir=base_path / "raw",
                meta_file=base_path / "snapshots.json",
            )
            client = TestClient(create_dashboard_app(storage_service=store))
            response = client.get("/health")
        finally:
            temp_dir.cleanup()

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["configuration"], "warning")
        self.assertEqual(payload["missing_config"], ["OPENAI_API_KEY"])
        self.assertEqual(payload["status"], "warning")


if __name__ == "__main__":
    unittest.main()
