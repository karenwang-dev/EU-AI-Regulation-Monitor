import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.run_history import save_run_history
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class TestDashboardWeb(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.history_file = base_path / "run_history.json"
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

        old_snapshot = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": "https://example.com/ec",
                "title": "European Commission",
                "markdown": "# Old version",
                "timestamp": "2026-07-15T10:00:00",
            }
        )
        new_snapshot = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": "https://example.com/ec",
                "title": "European Commission",
                "markdown": "# New version\nAdded regulation section",
                "timestamp": "2026-07-15T12:00:00",
            }
        )
        saved_diff = self.store.save_diff(
            {
                "source_id": "ec",
                "old_snapshot_id": old_snapshot["id"],
                "new_snapshot_id": new_snapshot["id"],
                "changed": True,
                "added_content": ["Added regulation section"],
                "removed_content": ["Old version"],
                "diff_text": "+Added regulation section",
            }
        )
        self.diff_id = saved_diff["id"]

        self.store.save_analysis(
            new_snapshot["id"],
            {
                "impact_level": "HIGH",
                "affected_modules": ["Network", "AI Features"],
                "reason": "New cybersecurity requirements affect connected TVs.",
                "recommended_actions": ["Review OTA security controls"],
                "confidence": "HIGH",
            },
        )

        save_run_history(
            [{"status": "analyzed", "diff_id": self.diff_id}],
            history_file=self.history_file,
        )

        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                history_file=self.history_file,
            )
        )

        self.monitor = {
            "id": "ec",
            "name": "European Commission",
            "url": "https://example.com/ec",
            "keywords": ["EU Regulation"],
            "category": "EU Policy",
            "frequency": "daily",
            "enabled": True,
        }

    def tearDown(self):
        self.client = None
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_homepage_returns_200(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Regulation Monitoring Dashboard", response.content)
        self.assertIn(b"High Risk", response.content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_changes_page_renders(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/changes")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Regulation Changes", response.content)
        self.assertIn(b"European Commission", response.content)
        self.assertIn(b"HIGH", response.content)
        self.assertIn(b"Network", response.content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_page_renders(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get(f"/detail/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"AI Impact Analysis", response.content)
        self.assertIn(b"Recommended Actions", response.content)
        self.assertIn(b"Added regulation section", response.content)
        self.assertIn(b"Review OTA security controls", response.content)


if __name__ == "__main__":
    unittest.main()
