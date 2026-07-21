import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.storage.service import StorageService
from app.version import APP_PRODUCT_TITLE, APP_VERSION, get_version_display
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

    def _client(self):
        return TestClient(create_dashboard_app(storage_service=self.store))

    @patch("app.web.app.validate_configuration")
    def test_about_page_renders(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/about")

        self.assertEqual(response.status_code, 200)
        self.assertIn("About", response.text)

    @patch("app.web.app.validate_configuration")
    def test_version_displays_v115_stable(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/about")

        self.assertIn(get_version_display(), response.text)
        self.assertIn("v1.1.5 Stable", response.text)
        self.assertIn(APP_VERSION, response.text)

    @patch("app.web.app.validate_configuration")
    def test_product_title_updated(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/about")

        self.assertIn(APP_PRODUCT_TITLE, response.text)
        self.assertIn("Smart Monitoring &amp; Compliance Analysis Platform", response.text)

    @patch("app.web.app.validate_configuration")
    def test_features_rendered(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/about")

        self.assertIn("Features", response.text)
        self.assertIn("Multi-source monitoring", response.text)
        self.assertIn("Run Details", response.text)
        self.assertIn("SQLite persistence", response.text)

    @patch("app.web.app.validate_configuration")
    def test_platform_card_rendered(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/about")

        self.assertIn("Platform", response.text)
        self.assertIn("FastAPI", response.text)
        self.assertIn("Bootstrap 5", response.text)
        self.assertIn("Firecrawl", response.text)
        self.assertIn("OpenAI Responses API", response.text)

    @patch("app.web.app.validate_configuration")
    def test_statistics_card_rendered(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/about")

        self.assertIn("Platform Statistics", response.text)
        self.assertIn("447 Passed", response.text)
        self.assertIn("Multi-page Monitoring", response.text)
        self.assertIn("Responsive Dashboard", response.text)

    @patch("app.web.app.validate_configuration")
    def test_roadmap_card_rendered(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/about")

        self.assertIn("Roadmap", response.text)
        self.assertIn("v1.2.0", response.text)
        self.assertIn("Website Explorer", response.text)
        self.assertIn("Timeline View", response.text)

    @patch("app.web.app.validate_configuration")
    def test_about_footer_rendered(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/about")

        self.assertIn("2026", response.text)
        self.assertIn("Built with", response.text)

    @patch("app.web.app.validate_configuration")
    def test_about_navigation_link_exists(self, mock_validate_configuration):
        mock_validate_configuration.return_value = {
            "status": "ok",
            "missing": [],
            "warnings": [],
        }

        response = self._client().get("/")

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

        response = self._client().get("/about")

        self.assertEqual(response.status_code, 200)
        self.assertIn("OPENAI_API_KEY", response.text)
        self.assertIn("SMTP_PASSWORD is not set (optional)", response.text)


if __name__ == "__main__":
    unittest.main()
