import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.run_history import save_run_history
from app.storage.service import StorageService
from app.web.api import create_app


class TestDashboardApi(unittest.TestCase):

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

        analysis_record = self.store.save_analysis(
            new_snapshot["id"],
            {
                "impact_level": "HIGH",
                "affected_modules": ["Network"],
                "reason": "Regulation update affects connected TV security.",
                "recommended_actions": ["Review network controls"],
                "confidence": "HIGH",
            },
        )
        self.analysis_id = analysis_record["id"]

        save_run_history(
            [
                {"status": "analyzed", "diff_id": self.diff_id},
                {"status": "skipped", "diff_id": None},
            ],
            history_file=self.history_file,
        )

        self.client = TestClient(
            create_app(
                storage_service=self.store,
                history_file=self.history_file,
            )
        )

    def tearDown(self):
        self.client = None
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def test_root_status(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_api_status(self):
        with mock.patch(
            "app.web.api.load_monitors",
            return_value=[
                {
                    "id": "ec",
                    "name": "European Commission",
                    "enabled": True,
                    "frequency": "daily",
                }
            ],
        ):
            response = self.client.get("/api/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["monitor_count"], 1)
        self.assertEqual(body["changed_count"], 1)
        self.assertEqual(body["analyzed_count"], 1)
        self.assertEqual(body["failed_count"], 0)
        self.assertIsNotNone(body["last_run"])

    def test_api_monitors(self):
        with mock.patch(
            "app.web.api.load_monitors",
            return_value=[
                {
                    "id": "ec",
                    "name": "European Commission",
                    "url": "https://example.com/ec",
                    "keywords": ["EU Regulation"],
                    "category": "EU Policy",
                    "frequency": "daily",
                    "enabled": True,
                }
            ],
        ):
            response = self.client.get("/api/monitors")

        self.assertEqual(response.status_code, 200)
        monitors = response.json()["monitors"]
        self.assertEqual(len(monitors), 1)
        self.assertEqual(monitors[0]["id"], "ec")

    def test_api_analysis(self):
        response = self.client.get(f"/api/analysis/{self.analysis_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], self.analysis_id)
        self.assertEqual(body["analysis"]["impact_level"], "HIGH")

    def test_api_diff(self):
        response = self.client.get(f"/api/diff/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], self.diff_id)
        self.assertIn("Added regulation section", body["added_content"])

    def test_api_changes(self):
        with mock.patch(
            "app.web.api.load_monitors",
            return_value=[{"id": "ec", "enabled": True, "frequency": "daily"}],
        ):
            response = self.client.get("/api/changes")

        self.assertEqual(response.status_code, 200)
        changes = response.json()["changes"]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["source_id"], "ec")
        self.assertIn("Added regulation section", changes[0]["changed_content_summary"])


if __name__ == "__main__":
    unittest.main()
