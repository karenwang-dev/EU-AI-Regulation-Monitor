import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class TestDashboardSchedulerStatus(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.status_file = base_path / "scheduler_status.json"
        now = datetime.now(timezone.utc).isoformat()
        self.status_file.write_text(
            json.dumps(
                {
                    "process": {
                        "heartbeat_at": now,
                        "timezone": "Europe/Berlin",
                    },
                    "next_runs": {"daily_monitors": now},
                    "jobs": {
                        "daily_monitors": {
                            "status": "success",
                            "completed_at": now,
                            "run_summary": {
                                "total_monitors": 16,
                                "failed_count": 0,
                                "changed_count": 1,
                                "analyzed_count": 1,
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scheduler_status_api(self):
        with patch(
            "app.scheduler_status.DEFAULT_STATUS_FILE",
            self.status_file,
        ), patch(
            "app.web.app.load_monitors",
            return_value=[
                {"id": "a", "enabled": True},
                {"id": "b", "enabled": False},
            ],
        ):
            app = create_dashboard_app(storage_service=self.store)
            client = TestClient(app)
            response = client.get("/api/scheduler/status")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["process_status"], "RUNNING")
        self.assertEqual(payload["enabled_monitor_count"], 1)
        self.assertEqual(payload["last_run_result"], "SUCCESS")

    def test_dashboard_renders_scheduler_section(self):
        with patch(
            "app.scheduler_status.DEFAULT_STATUS_FILE",
            self.status_file,
        ), patch(
            "app.web.app.load_monitors",
            return_value=[{"id": "a", "enabled": True, "frequency": "daily"}],
        ), patch(
            "app.web.app._count_changes_by_impact",
            return_value={"HIGH": 0, "MEDIUM": 0, "LOW": 0},
        ), patch(
            "app.web.app._count_todays_changes",
            return_value=0,
        ), patch(
            "app.web.app.get_latest_run",
            return_value=None,
        ), patch(
            "app.web.app.get_latest_report",
            return_value=None,
        ):
            app = create_dashboard_app(storage_service=self.store)
            client = TestClient(app)
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("data-testid=\"scheduler-process-status\"", response.text)
        self.assertIn("runs independently from your browser", response.text.lower())


if __name__ == "__main__":
    unittest.main()
