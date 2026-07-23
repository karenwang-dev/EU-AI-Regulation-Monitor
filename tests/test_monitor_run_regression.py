import gc
import json
import sqlite3
import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.json_utils import dumps_json_safe, to_json_safe
from app.dev.change_test_site import LOCAL_TEST_MONITOR_ID
from app.monitors.execution import MonitorExecutionService
from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.monitors.run_store import MonitorRunStore, reset_monitor_run_store
from app.storage.service import StorageService
from app.web.app import create_dashboard_app
from app.web.monitor_api import MonitorRunResponse


class SampleStatus(str, Enum):
    CHANGED = "changed"


@dataclass
class SamplePageMeta:
    title: str
    captured_at: datetime


class MonitorRunRegressionTests(unittest.TestCase):
    def setUp(self):
        reset_monitor_repository()
        reset_monitor_run_store()
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
                            "category": "national_regulation",
                            "frequency": "daily",
                            "enabled": True,
                            "crawl_mode": "multi_page",
                            "max_depth": 1,
                            "max_pages": 3,
                            "fetch_mode": "http",
                            "skip_ai_analysis": True,
                        }
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
        self.run_store = MonitorRunStore(db_path=self.db_path)
        self.storage = StorageService(
            db_path=self.db_path,
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

    def tearDown(self):
        reset_monitor_repository()
        reset_monitor_run_store()
        gc.collect()
        self.temp_dir.cleanup()

    def _client(self, pipeline_result: dict) -> TestClient:
        execution_service = MonitorExecutionService(
            repository=self.repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(return_value=pipeline_result)
            ),
            history_file=self.history_file,
            run_store=self.run_store,
        )
        return TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
                execution_service=execution_service,
                history_file=self.history_file,
            )
        )

    def _post_run(self, client: TestClient):
        return client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")

    def test_successful_manual_run_returns_application_json(self):
        client = self._client(
            {
                "source_id": LOCAL_TEST_MONITOR_ID,
                "status": "unchanged",
                "snapshot_id": 1,
                "page_change_summary": {
                    "pages_checked": 1,
                    "pages_changed": 0,
                    "homepage_changed": False,
                    "child_pages_changed": 0,
                },
            }
        )
        response = self._post_run(client)
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers["content-type"])
        payload = response.json()
        MonitorRunResponse.model_validate(payload)
        self.assertIsInstance(payload["run_history_id"], int)

    def test_baseline_run_response(self):
        client = self._client(
            {
                "source_id": LOCAL_TEST_MONITOR_ID,
                "status": "first_snapshot",
                "snapshot_id": 1,
                "page_change_summary": {
                    "pages_checked": 1,
                    "pages_changed": 0,
                    "homepage_changed": False,
                    "child_pages_changed": 0,
                },
                "url_results": [{"status": "first_snapshot", "url": "https://example.com"}],
            }
        )
        payload = self._post_run(client).json()
        self.assertEqual(payload["change_status"], "baseline")
        self.assertEqual(payload["execution_status"], "success")

    def test_unchanged_run_response(self):
        client = self._client(
            {
                "source_id": LOCAL_TEST_MONITOR_ID,
                "status": "unchanged",
                "snapshot_id": 1,
                "page_change_summary": {
                    "pages_checked": 2,
                    "pages_changed": 0,
                    "homepage_changed": False,
                    "child_pages_changed": 0,
                },
            }
        )
        payload = self._post_run(client).json()
        self.assertEqual(payload["change_status"], "unchanged")

    def test_changed_run_response(self):
        client = self._client(
            {
                "source_id": LOCAL_TEST_MONITOR_ID,
                "status": "changed",
                "snapshot_id": 10,
                "diff_id": 5,
                "page_change_summary": {
                    "pages_checked": 3,
                    "pages_changed": 1,
                    "homepage_changed": False,
                    "child_pages_changed": 1,
                },
            }
        )
        payload = self._post_run(client).json()
        self.assertEqual(payload["change_status"], "changed")
        self.assertEqual(payload["pages_changed"], 1)

    def test_failed_pipeline_returns_structured_json(self):
        client = self._client(
            {
                "source_id": LOCAL_TEST_MONITOR_ID,
                "status": "error",
                "message": "Crawl failed",
                "page_change_summary": {
                    "pages_checked": 1,
                    "pages_changed": 0,
                    "homepage_changed": False,
                    "child_pages_changed": 0,
                },
            }
        )
        response = self._post_run(client)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["execution_status"], "failed")
        self.assertEqual(payload["change_status"], "failed")

    def test_page_results_with_datetime_enum_dataclass_serialize_safely(self):
        meta = SamplePageMeta(title="Policy", captured_at=datetime(2026, 7, 21, 10, 0, 0))
        serialized = to_json_safe(
            {
                "status": SampleStatus.CHANGED,
                "meta": meta,
                "path": Path("/tmp/example"),
            }
        )
        dumps_json_safe(serialized)
        run_id = self.run_store.save_run(
            monitor_id=LOCAL_TEST_MONITOR_ID,
            monitor_name="Local Multi-page Change Test",
            triggered_by="manual_ui",
            execution_status="success",
            change_status="changed",
            started_at="2026-07-21T10:00:00",
            finished_at="2026-07-21T10:00:01",
            duration_ms=1000,
            pages_checked=1,
            pages_changed=1,
            homepage_changed=False,
            child_pages_changed=1,
            page_results=[serialized],
        )
        saved = self.run_store.get_run(run_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["page_results"][0]["status"], "changed")

    def test_run_history_id_is_integer_in_api_response(self):
        client = self._client(
            {
                "source_id": LOCAL_TEST_MONITOR_ID,
                "status": "unchanged",
                "snapshot_id": 1,
                "page_change_summary": {
                    "pages_checked": 1,
                    "pages_changed": 0,
                    "homepage_changed": False,
                    "child_pages_changed": 0,
                },
            }
        )
        payload = self._post_run(client).json()
        self.assertIsInstance(payload["run_history_id"], int)
        self.assertGreater(payload["run_history_id"], 0)

    def test_api_response_passes_response_model_validation(self):
        client = self._client(
            {
                "source_id": LOCAL_TEST_MONITOR_ID,
                "status": "changed",
                "snapshot_id": 2,
                "diff_id": 1,
                "page_change_summary": {
                    "pages_checked": 1,
                    "pages_changed": 1,
                    "homepage_changed": True,
                    "child_pages_changed": 0,
                },
            }
        )
        payload = self._post_run(client).json()
        validated = MonitorRunResponse.model_validate(payload)
        self.assertEqual(validated.change_status, "changed")

    def test_migration_on_pre_v115_database(self):
        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(temp_dir.name)
        db_path = base_path / "legacy.db"
        history_file = base_path / "run_history.json"

        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """
                CREATE TABLE monitors (
                    id TEXT PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO monitors (
                    id, config_json, enabled, created_at, updated_at
                ) VALUES (?, ?, 1, ?, ?)
                """,
                (
                    LOCAL_TEST_MONITOR_ID,
                    json.dumps(
                        {
                            "id": LOCAL_TEST_MONITOR_ID,
                            "name": "Local Multi-page Change Test",
                            "url": "http://127.0.0.1:8080/dev/change-test-site",
                            "keywords": ["policy"],
                            "category": "national_regulation",
                            "frequency": "daily",
                            "enabled": True,
                            "crawl_mode": "multi_page",
                            "max_depth": 1,
                            "max_pages": 3,
                        }
                    ),
                    "2026-07-21T09:00:00",
                    "2026-07-21T09:00:00",
                ),
            )
            connection.execute(
                """
                CREATE TABLE monitor_execution (
                    monitor_id TEXT PRIMARY KEY,
                    execution_status TEXT NOT NULL DEFAULT 'idle',
                    last_run_at TEXT,
                    last_status TEXT,
                    last_pages_changed INTEGER DEFAULT 0,
                    last_pages_checked INTEGER DEFAULT 0,
                    last_snapshot_id INTEGER,
                    last_diff_id INTEGER,
                    last_error TEXT,
                    last_run_history_id TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )

        repository = MonitorRepository(db_path=db_path)
        run_store = MonitorRunStore(db_path=db_path)
        with repository._connect() as connection:
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(monitor_execution)"
                )
            }
        self.assertIn("last_change_status", columns)
        with repository._connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        self.assertIn("monitor_runs", tables)

        storage = StorageService(
            db_path=db_path,
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        execution_service = MonitorExecutionService(
            repository=repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(
                    return_value={
                        "source_id": LOCAL_TEST_MONITOR_ID,
                        "status": "unchanged",
                        "snapshot_id": 1,
                        "page_change_summary": {
                            "pages_checked": 1,
                            "pages_changed": 0,
                            "homepage_changed": False,
                            "child_pages_changed": 0,
                        },
                    }
                )
            ),
            history_file=history_file,
            run_store=run_store,
        )
        client = TestClient(
            create_dashboard_app(
                storage_service=storage,
                monitors_repository=repository,
                execution_service=execution_service,
                history_file=history_file,
            )
        )
        response = client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        self.assertEqual(response.status_code, 200)
        temp_dir.cleanup()

    def test_execution_lock_releases_after_persistence_failure(self):
        execution_service = MonitorExecutionService(
            repository=self.repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(
                    return_value={
                        "source_id": LOCAL_TEST_MONITOR_ID,
                        "status": "unchanged",
                        "snapshot_id": 1,
                        "page_change_summary": {
                            "pages_checked": 1,
                            "pages_changed": 0,
                            "homepage_changed": False,
                            "child_pages_changed": 0,
                        },
                    }
                )
            ),
            history_file=self.history_file,
            run_store=self.run_store,
        )
        client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
                execution_service=execution_service,
                history_file=self.history_file,
            )
        )

        with patch.object(
            self.run_store,
            "save_run",
            side_effect=RuntimeError("db write failed"),
        ):
            response = client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")

        self.assertEqual(response.status_code, 500)
        self.assertIn("application/json", response.headers["content-type"])
        detail = response.json()["detail"]
        self.assertEqual(detail["error_code"], "RUN_PERSISTENCE_FAILED")
        self.assertFalse(execution_service.is_running(LOCAL_TEST_MONITOR_ID))

        second = client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        self.assertNotEqual(second.status_code, 409)

    def test_default_execution_service_uses_history_file_when_none_passed(self):
        service = MonitorExecutionService(repository=self.repository)
        self.assertIsNotNone(service.history_file)
        self.assertTrue(service.history_file.name.endswith("run_history.json"))

    def test_frontend_does_not_unconditionally_call_response_json(self):
        response = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
            )
        ).get("/monitors")
        content = response.content
        self.assertIn(b"parseHttpResponse", content)
        self.assertIn(b"async function runMonitor", content)
        run_monitor_start = content.index(b"async function runMonitor")
        run_monitor_end = content.index(b"function setCrawlDefaults", run_monitor_start)
        run_monitor_block = content[run_monitor_start:run_monitor_end]
        self.assertNotIn(b"await response.json()", run_monitor_block)

    def test_frontend_handles_plain_text_error_fallback(self):
        response = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
            )
        ).get("/monitors")
        self.assertIn(b"formatRunError", response.content)
        self.assertIn(b"Monitor run failed (HTTP", response.content)


if __name__ == "__main__":
    unittest.main()
