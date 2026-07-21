import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.paths import get_runtime_paths
from app.dev.change_test_site import LOCAL_TEST_MONITOR_ID
from app.monitors.execution import MonitorAlreadyRunningError, MonitorExecutionService
from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.storage.service import StorageService
from app.web.app import create_dashboard_app
from app.web.monitor_api import MonitorStore, MonitorUpdateRequest


class MonitorRepositoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        reset_monitor_repository()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.db_path = base_path / "storage.db"
        self.seed_file = base_path / "monitors.json"

    def tearDown(self):
        reset_monitor_repository()
        gc.collect()
        self.temp_dir.cleanup()

    def _write_seed(self, monitors: list[dict]) -> None:
        self.seed_file.write_text(
            json.dumps({"monitors": monitors}, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_seed_config_into_empty_database(self):
        self._write_seed(
            [
                {
                    "id": LOCAL_TEST_MONITOR_ID,
                    "name": "Local Multi-page Change Test",
                    "url": "http://127.0.0.1:8080/dev/change-test-site",
                    "keywords": ["policy"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": False,
                }
            ]
        )
        repository = MonitorRepository(db_path=self.db_path, seed_file=self.seed_file)
        monitors = repository.list_all()
        self.assertEqual(len(monitors), 1)
        self.assertEqual(monitors[0]["id"], LOCAL_TEST_MONITOR_ID)

    def test_seed_twice_creates_no_duplicates(self):
        self._write_seed(
            [
                {
                    "id": LOCAL_TEST_MONITOR_ID,
                    "name": "Local Multi-page Change Test",
                    "url": "http://127.0.0.1:8080/dev/change-test-site",
                    "keywords": ["policy"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": False,
                }
            ]
        )
        repository = MonitorRepository(db_path=self.db_path, seed_file=self.seed_file)
        duplicate_repo = MonitorRepository(db_path=self.db_path, seed_file=self.seed_file)
        self.assertEqual(len(duplicate_repo.list_all()), 1)
        self.assertEqual(len(repository.list_all()), 1)

    def test_startup_does_not_overwrite_edited_enabled_state(self):
        self._write_seed(
            [
                {
                    "id": LOCAL_TEST_MONITOR_ID,
                    "name": "Local Multi-page Change Test",
                    "url": "http://127.0.0.1:8080/dev/change-test-site",
                    "keywords": ["policy"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": False,
                }
            ]
        )
        repository = MonitorRepository(db_path=self.db_path, seed_file=self.seed_file)
        repository.set_enabled(LOCAL_TEST_MONITOR_ID, True)

        self._write_seed(
            [
                {
                    "id": LOCAL_TEST_MONITOR_ID,
                    "name": "Local Multi-page Change Test",
                    "url": "http://127.0.0.1:8080/dev/change-test-site",
                    "keywords": ["policy"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": False,
                }
            ]
        )
        MonitorRepository(db_path=self.db_path, seed_file=self.seed_file)
        monitor = repository.get_by_id(LOCAL_TEST_MONITOR_ID)
        self.assertTrue(monitor["enabled"])

    def test_new_seed_monitor_is_added_safely(self):
        self._write_seed(
            [
                {
                    "id": "existing-monitor",
                    "name": "Existing Monitor",
                    "url": "https://example.com/existing",
                    "keywords": ["existing"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": True,
                }
            ]
        )
        repository = MonitorRepository(db_path=self.db_path, seed_file=self.seed_file)
        self.assertEqual(len(repository.list_all()), 1)

        self._write_seed(
            [
                {
                    "id": "existing-monitor",
                    "name": "Existing Monitor",
                    "url": "https://example.com/existing",
                    "keywords": ["existing"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": False,
                },
                {
                    "id": LOCAL_TEST_MONITOR_ID,
                    "name": "Local Multi-page Change Test",
                    "url": "http://127.0.0.1:8080/dev/change-test-site",
                    "keywords": ["policy"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": False,
                },
            ]
        )
        repository.seed_from_config(self.seed_file)
        monitors = repository.list_all()
        self.assertEqual(len(monitors), 2)
        self.assertTrue(repository.get_by_id("existing-monitor")["enabled"])

    def test_enable_through_ui_service_visible_to_cli(self):
        self._write_seed(
            [
                {
                    "id": LOCAL_TEST_MONITOR_ID,
                    "name": "Local Multi-page Change Test",
                    "url": "http://127.0.0.1:8080/dev/change-test-site",
                    "keywords": ["policy"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": False,
                }
            ]
        )
        repository = MonitorRepository(db_path=self.db_path, seed_file=self.seed_file)
        store = MonitorStore(repository=repository)
        store.update_monitor(
            LOCAL_TEST_MONITOR_ID,
            MonitorUpdateRequest(enabled=True),
        )
        enabled = repository.list_enabled()
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0]["id"], LOCAL_TEST_MONITOR_ID)

    def test_disable_through_ui_service_visible_to_cli(self):
        self._write_seed(
            [
                {
                    "id": LOCAL_TEST_MONITOR_ID,
                    "name": "Local Multi-page Change Test",
                    "url": "http://127.0.0.1:8080/dev/change-test-site",
                    "keywords": ["policy"],
                    "category": "TEST",
                    "frequency": "daily",
                    "enabled": True,
                }
            ]
        )
        repository = MonitorRepository(db_path=self.db_path, seed_file=self.seed_file)
        store = MonitorStore(repository=repository)
        store.update_monitor(
            LOCAL_TEST_MONITOR_ID,
            MonitorUpdateRequest(enabled=False),
        )
        self.assertEqual(len(repository.list_enabled()), 0)

    def test_web_and_cli_resolve_same_absolute_database_path(self):
        runtime_paths = get_runtime_paths()
        self.assertEqual(
            runtime_paths["monitors_repository"],
            runtime_paths["database"],
        )
        self.assertTrue(runtime_paths["database"].is_absolute())


class MonitorManualRunApiTests(unittest.TestCase):
    def setUp(self):
        reset_monitor_repository()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.db_path = base_path / "storage.db"
        self.history_file = base_path / "run_history.json"
        self.seed_file = base_path / "monitors.json"
        self.seed_file.write_text(
            json.dumps(
                {
                    "monitors": [
                        {
                            "id": LOCAL_TEST_MONITOR_ID,
                            "name": "Local Multi-page Change Test",
                            "url": "http://127.0.0.1:8080/dev/change-test-site",
                            "keywords": ["policy"],
                            "category": "TEST",
                            "frequency": "daily",
                            "enabled": False,
                            "crawl_mode": "multi_page",
                            "max_depth": 1,
                            "max_pages": 3,
                            "fetch_mode": "http",
                            "skip_ai_analysis": True,
                        },
                        {
                            "id": "other-monitor",
                            "name": "Other Monitor",
                            "url": "https://example.com/other",
                            "keywords": ["other"],
                            "category": "TEST",
                            "frequency": "daily",
                            "enabled": True,
                        },
                    ]
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.repository = MonitorRepository(
            db_path=self.db_path,
            seed_file=self.seed_file,
        )
        self.storage = StorageService(
            db_path=self.db_path,
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.pipeline_result = {
            "source_id": LOCAL_TEST_MONITOR_ID,
            "name": "Local Multi-page Change Test",
            "status": "changed",
            "snapshot_id": 10,
            "diff_id": 5,
            "analysis_id": None,
            "page_change_summary": {
                "pages_checked": 3,
                "pages_changed": 1,
                "homepage_changed": False,
                "child_pages_changed": 1,
            },
            "url_results": [
                {"url": "http://127.0.0.1:8080/dev/change-test-site/policy-a", "status": "changed"}
            ],
        }
        self.execution_service = MonitorExecutionService(
            repository=self.repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(return_value=self.pipeline_result)
            ),
            history_file=self.history_file,
        )
        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
                execution_service=self.execution_service,
            )
        )

    def tearDown(self):
        self.client = None
        reset_monitor_repository()
        gc.collect()
        self.temp_dir.cleanup()

    def test_run_one_selected_monitor(self):
        response = self.client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["monitor_id"], LOCAL_TEST_MONITOR_ID)
        self.assertEqual(payload["status"], "changed")
        self.assertEqual(payload["change_status"], "changed")
        self.assertEqual(payload["execution_status"], "success")
        self.assertEqual(payload["pages_checked"], 3)
        self.assertEqual(payload["pages_changed"], 1)
        self.assertFalse(payload["homepage_changed"])
        self.assertEqual(payload["child_pages_changed"], 1)

    def test_run_disabled_monitor_manually(self):
        response = self.client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "changed")

    def test_unchanged_run_returns_zero_pages_changed(self):
        unchanged = {
            **self.pipeline_result,
            "status": "skipped",
            "diff_id": None,
            "page_change_summary": {
                "pages_checked": 3,
                "pages_changed": 0,
                "homepage_changed": False,
                "child_pages_changed": 0,
            },
        }
        service = MonitorExecutionService(
            repository=self.repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(return_value=unchanged)
            ),
            history_file=self.history_file,
        )
        client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
                execution_service=service,
            )
        )
        response = client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unchanged")
        self.assertEqual(response.json()["change_status"], "unchanged")
        self.assertEqual(response.json()["pages_changed"], 0)

    def test_failed_crawl_returns_failed_status(self):
        failed = {
            "source_id": LOCAL_TEST_MONITOR_ID,
            "name": "Local Multi-page Change Test",
            "status": "error",
            "snapshot_id": None,
            "diff_id": None,
            "analysis_id": None,
            "message": "Crawl failed",
        }
        service = MonitorExecutionService(
            repository=self.repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(return_value=failed)
            ),
            history_file=self.history_file,
        )
        client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
                execution_service=service,
            )
        )
        response = client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["execution_status"], "failed")

    def test_run_history_is_saved(self):
        response = self.client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.history_file.exists())
        history = json.loads(self.history_file.read_text(encoding="utf-8"))
        self.assertEqual(len(history), 1)
        self.assertIn("run_history_id", history[0])
        self.assertIn("run_ids", history[0])

    def test_duplicate_concurrent_run_returns_409(self):
        service = MonitorExecutionService(
            repository=self.repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(return_value=self.pipeline_result)
            ),
            history_file=self.history_file,
        )
        client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
                execution_service=service,
            )
        )
        service._running.add(LOCAL_TEST_MONITOR_ID)
        response = client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        service._running.discard(LOCAL_TEST_MONITOR_ID)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Monitor is already running")

    def test_execution_service_raises_when_already_running(self):
        service = MonitorExecutionService(repository=self.repository)
        with patch.object(service, "_running", {LOCAL_TEST_MONITOR_ID}):
            with self.assertRaises(MonitorAlreadyRunningError):
                service.run_monitor(LOCAL_TEST_MONITOR_ID)


if __name__ == "__main__":
    unittest.main()
