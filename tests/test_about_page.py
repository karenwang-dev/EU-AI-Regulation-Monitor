import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.storage.service import StorageService
from app.version import APP_NAME, APP_VERSION
from app.web.app import create_dashboard_app


class TestAboutPage(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

    def tearDown(self):
        self.temp_dir.cleanup()
        gc.collect()

    @patch("app.web.app.validate_configuration")
    def test_about_page_renders(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        client = TestClient(create_dashboard_app(storage_service=self.store))
        response = client.get("/about")

        self.assertEqual(response.status_code, 200)
        self.assertIn("About", response.text)
        self.assertIn(APP_NAME, response.text)
        self.assertIn(APP_VERSION, response.text)
        self.assertIn("Architecture Components", response.text)
        self.assertIn("Web Dashboard", response.text)
        self.assertIn("Configuration Status", response.text)

    @patch("app.web.app.validate_configuration")
    def test_about_navigation_link_exists(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        client = TestClient(create_dashboard_app(storage_service=self.store))
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/about"', response.text)
        self.assertIn("About", response.text)

    @patch("app.web.app.validate_configuration")
    def test_about_page_shows_configuration_warning(
        self,
        mock_validate_configuration,
    ):
        mock_validate_configuration.return_value = {
            "status": "warning",
            "missing": ["OPENAI_API_KEY"],
            "warnings": ["SMTP_PASSWORD is not set (optional)"],
        }

        client = TestClient(create_dashboard_app(storage_service=self.store))
        response = client.get("/about")

        self.assertEqual(response.status_code, 200)
        self.assertIn("OPENAI_API_KEY", response.text)
        self.assertIn("SMTP_PASSWORD is not set (optional)", response.text)


if __name__ == "__main__":
    unittest.main()
