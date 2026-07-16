import gc
import tempfile
import unittest
from datetime import datetime
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
                "created_at": datetime.now().isoformat(),
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
            "keywords": ["EU Regulation", "cybersecurity"],
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
    def test_homepage_returns_200_with_stat_cards(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Total Monitors", content)
        self.assertIn(b"Last Run", content)
        self.assertIn(b"Today's Changes", content)
        self.assertIn(b"High Risk", content)
        self.assertIn(b"Medium", content)
        self.assertIn(b"Low", content)
        self.assertIn(b'nav-link active', content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_changes_page_renders_with_filters_and_badges(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/changes")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Keyword Search", content)
        self.assertIn(b"Impact Level", content)
        self.assertIn(b"European Commission", content)
        self.assertIn(b"text-bg-danger", content)
        self.assertIn(b"Network", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_changes_page_supports_impact_filter(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/changes?impact=HIGH")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"European Commission", response.content)

        response_none = self.client.get("/changes?impact=NONE")
        self.assertEqual(response_none.status_code, 200)
        self.assertIn(b"No regulation changes match your filters.", response_none.content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_changes_page_supports_keyword_search(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/changes?q=cybersecurity")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"European Commission", response.content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_page_renders_formatted_sections(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get(f"/detail/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Impact Analysis", content)
        self.assertIn(b"Recommended Actions", content)
        self.assertIn(b"Diff Content", content)
        self.assertIn(b"Added", content)
        self.assertIn(b"Removed", content)
        self.assertIn(b"Added regulation section", content)
        self.assertIn(b"Review OTA security controls", content)
        self.assertIn(b"New cybersecurity requirements affect connected TVs.", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_monitors_page_highlights_navigation(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/monitors")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Monitoring Targets", response.content)
        self.assertIn(b'href="/monitors"', response.content)


if __name__ == "__main__":
    unittest.main()
