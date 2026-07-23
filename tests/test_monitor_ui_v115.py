import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.dev.change_test_site import LOCAL_TEST_MONITOR_ID
from app.monitors.display_helpers import format_category_label
from app.monitors.execution import MonitorExecutionService
from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.monitors.run_store import MonitorRunStore, get_monitor_run_store, reset_monitor_run_store
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class MonitorUiV115Tests(unittest.TestCase):
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
        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
            )
        )

    def tearDown(self):
        self.client = None
        reset_monitor_repository()
        reset_monitor_run_store()
        gc.collect()
        self.temp_dir.cleanup()

    def test_category_display_formatting(self):
        self.assertEqual(
            format_category_label("national_regulation"),
            "National Regulation",
        )
        self.assertEqual(format_category_label("eu_regulation"), "EU Regulation")
        self.assertEqual(format_category_label("ai_act"), "AI Act")

    def test_monitor_page_has_grouped_action_controls(self):
        response = self.client.get("/monitors")
        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"monitor-actions", content)
        self.assertIn(b"run-monitor-btn", content)
        self.assertIn(b"dropdown-menu", content)
        self.assertIn(b"monitor-table-scroll", content)
        self.assertIn(b"dropdown-divider", content)
        self.assertIn(b"delete-monitor-btn", content)

    def test_bootstrap_bundle_loaded_once_on_monitors_page(self):
        response = self.client.get("/monitors")
        bundle_marker = b"bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        self.assertEqual(response.content.count(bundle_marker), 1)

    def test_more_dropdown_uses_bootstrap5_attributes(self):
        response = self.client.get("/monitors")
        content = response.content
        self.assertIn(b'data-bs-toggle="dropdown"', content)
        self.assertNotIn(b'data-toggle="dropdown"', content)
        self.assertIn(b"aria-haspopup", content)

    def test_init_monitor_dropdowns_uses_fixed_positioning(self):
        response = self.client.get("/monitors")
        content = response.content
        self.assertIn(b"initMonitorDropdowns", content)
        self.assertIn(b'strategy: "fixed"', content)

    def test_base_includes_timestamp_formatter(self):
        response = self.client.get("/")
        self.assertIn(b"/static/js/timestamp_formatter.js", response.content)
        self.assertIn(b"applyLocalTimestamps", response.content)

    def test_base_includes_bootstrap_bundle_globally(self):
        response = self.client.get("/")
        self.assertIn(
            b"bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
            response.content,
        )

    def test_toggle_enable_disable_persists(self):
        monitor = self.client.get("/api/monitors").json()[0]
        self.assertTrue(monitor["enabled"])

        disable_response = self.client.put(
            f"/api/monitors/{LOCAL_TEST_MONITOR_ID}",
            json={"enabled": False},
        )
        self.assertEqual(disable_response.status_code, 200)
        self.assertFalse(disable_response.json()["enabled"])

        enable_response = self.client.put(
            f"/api/monitors/{LOCAL_TEST_MONITOR_ID}",
            json={"enabled": True},
        )
        self.assertEqual(enable_response.status_code, 200)
        self.assertTrue(enable_response.json()["enabled"])

    def test_delete_monitor_requires_api_confirmation_flow(self):
        create_response = self.client.post(
            "/api/monitors",
            json={
                "name": "Temporary Monitor",
                "url": "https://example.com/temp",
                "keywords": ["temp"],
                "category": "Other",
                "frequency": "daily",
                "crawl_mode": "single",
                "max_depth": 0,
                "max_pages": 1,
                "enabled": True,
            },
        )
        self.assertEqual(create_response.status_code, 201)
        monitor_id = create_response.json()["id"]

        delete_response = self.client.delete(f"/api/monitors/{monitor_id}")
        self.assertEqual(delete_response.status_code, 200)
        self.assertIsNone(self.repository.get_by_id(monitor_id))

    def test_delete_requires_confirmation(self):
        response = self.client.get("/monitors")
        self.assertIn(b"confirm(", response.content)

    def test_last_run_compact_formatting_in_page(self):
        response = self.client.get("/monitors")
        self.assertIn(b"formatLastRun", response.content)
        self.assertIn(b"formatTimestamp", response.content)

    def test_view_last_run_link_when_available(self):
        self.repository.save_execution_state(
            LOCAL_TEST_MONITOR_ID,
            execution_status="success",
            last_run_at="2026-07-21T10:00:00",
            last_change_status="changed",
            last_run_history_id="99",
        )
        monitors = self.client.get("/api/monitors").json()
        monitor = next(item for item in monitors if item["id"] == LOCAL_TEST_MONITOR_ID)
        self.assertEqual(monitor["last_run_history_id"], "99")

        response = self.client.get("/monitors")
        self.assertIn(b"View Last Run", response.content)
        self.assertIn(b'/runs/${monitor.last_run_history_id}', response.content)

    def test_run_details_api_changed_child_page(self):
        run_id = self.run_store.save_run(
            monitor_id=LOCAL_TEST_MONITOR_ID,
            monitor_name="Local Multi-page Change Test",
            triggered_by="manual_ui",
            execution_status="success",
            change_status="changed",
            started_at="2026-07-21T10:00:00",
            finished_at="2026-07-21T10:00:02",
            duration_ms=2000,
            pages_checked=3,
            pages_changed=1,
            homepage_changed=False,
            child_pages_changed=1,
            page_results=[
                {
                    "url": "http://127.0.0.1:8080/dev/change-test-site/policy-a",
                    "page_title": "Policy A",
                    "page_type": "child",
                    "status": "changed",
                    "snapshot_id": 5,
                    "previous_snapshot_id": 4,
                    "diff_id": 1,
                    "content_hash": "abc",
                    "error": None,
                }
            ],
        )
        response = self.client.get(f"/api/runs/{run_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["change_status"], "changed")
        self.assertEqual(len(payload["page_results"]), 1)
        self.assertEqual(payload["page_results"][0]["status"], "changed")

    def test_run_details_api_unchanged_page(self):
        run_id = self.run_store.save_run(
            monitor_id=LOCAL_TEST_MONITOR_ID,
            monitor_name="Local Multi-page Change Test",
            triggered_by="manual_ui",
            execution_status="success",
            change_status="unchanged",
            started_at="2026-07-21T10:00:00",
            finished_at="2026-07-21T10:00:02",
            duration_ms=1500,
            pages_checked=3,
            pages_changed=0,
            homepage_changed=False,
            child_pages_changed=0,
            page_results=[
                {
                    "url": "http://127.0.0.1:8080/dev/change-test-site/policy-a",
                    "page_title": "Policy A",
                    "page_type": "child",
                    "status": "unchanged",
                    "snapshot_id": 5,
                    "previous_snapshot_id": 4,
                    "diff_id": None,
                    "content_hash": "abc",
                    "error": None,
                }
            ],
        )
        payload = self.client.get(f"/api/runs/{run_id}").json()
        self.assertEqual(payload["change_status"], "unchanged")
        self.assertEqual(payload["page_results"][0]["status"], "unchanged")

    def test_run_details_api_failed_page(self):
        run_id = self.run_store.save_run(
            monitor_id=LOCAL_TEST_MONITOR_ID,
            monitor_name="Local Multi-page Change Test",
            triggered_by="manual_ui",
            execution_status="failed",
            change_status="failed",
            started_at="2026-07-21T10:00:00",
            finished_at="2026-07-21T10:00:01",
            duration_ms=900,
            pages_checked=1,
            pages_changed=0,
            homepage_changed=False,
            child_pages_changed=0,
            pages_failed=1,
            error="Crawl failed",
            page_results=[
                {
                    "url": "http://127.0.0.1:8080/dev/change-test-site",
                    "page_title": "Homepage",
                    "page_type": "homepage",
                    "status": "failed",
                    "snapshot_id": None,
                    "previous_snapshot_id": None,
                    "diff_id": None,
                    "content_hash": None,
                    "error": "Crawl failed",
                }
            ],
        )
        payload = self.client.get(f"/api/runs/{run_id}").json()
        self.assertEqual(payload["execution_status"], "failed")
        self.assertEqual(payload["page_results"][0]["status"], "failed")

    def test_run_details_page_renders(self):
        run_id = self.run_store.save_run(
            monitor_id=LOCAL_TEST_MONITOR_ID,
            monitor_name="Local Multi-page Change Test",
            triggered_by="manual_ui",
            execution_status="success",
            change_status="changed",
            started_at="2026-07-21T10:00:00",
            finished_at="2026-07-21T10:00:02",
            duration_ms=2000,
            pages_checked=3,
            pages_changed=1,
            homepage_changed=False,
            child_pages_changed=1,
            page_results=[],
        )
        response = self.client.get(f"/runs/{run_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Run Details", response.content)
        self.assertIn(b"Page Results", response.content)

    def test_legacy_run_without_page_details(self):
        run_id = self.run_store.save_run(
            monitor_id=LOCAL_TEST_MONITOR_ID,
            monitor_name="Local Multi-page Change Test",
            triggered_by="cli",
            execution_status="success",
            change_status="unchanged",
            started_at="2026-07-21T09:00:00",
            finished_at="2026-07-21T09:00:01",
            duration_ms=500,
            pages_checked=1,
            pages_changed=0,
            homepage_changed=False,
            child_pages_changed=0,
            page_results=[],
            legacy=True,
        )
        response = self.client.get(f"/runs/{run_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Page-level details unavailable for this historical run.",
            response.content,
        )

    def test_historical_run_remains_stable(self):
        run_id = self.run_store.save_run(
            monitor_id=LOCAL_TEST_MONITOR_ID,
            monitor_name="Local Multi-page Change Test",
            triggered_by="manual_ui",
            execution_status="success",
            change_status="changed",
            started_at="2026-07-21T10:00:00",
            finished_at="2026-07-21T10:00:02",
            duration_ms=2000,
            pages_checked=3,
            pages_changed=1,
            homepage_changed=False,
            child_pages_changed=1,
            page_results=[
                {
                    "url": "http://127.0.0.1:8080/dev/change-test-site/policy-a",
                    "page_title": "Policy A",
                    "page_type": "child",
                    "status": "changed",
                    "snapshot_id": 5,
                    "previous_snapshot_id": 4,
                    "diff_id": 1,
                    "content_hash": "abc",
                    "error": None,
                }
            ],
        )
        first = self.client.get(f"/api/runs/{run_id}").json()
        self.run_store.save_run(
            monitor_id=LOCAL_TEST_MONITOR_ID,
            monitor_name="Local Multi-page Change Test",
            triggered_by="manual_ui",
            execution_status="success",
            change_status="unchanged",
            started_at="2026-07-21T11:00:00",
            finished_at="2026-07-21T11:00:02",
            duration_ms=1800,
            pages_checked=3,
            pages_changed=0,
            homepage_changed=False,
            child_pages_changed=0,
            page_results=[],
        )
        second = self.client.get(f"/api/runs/{run_id}").json()
        self.assertEqual(first, second)
        self.assertEqual(second["pages_changed"], 1)

    def test_manual_run_completion_includes_run_details_link(self):
        pipeline_result = {
            "source_id": LOCAL_TEST_MONITOR_ID,
            "name": "Local Multi-page Change Test",
            "status": "changed",
            "snapshot_id": 10,
            "diff_id": 5,
            "page_change_summary": {
                "pages_checked": 3,
                "pages_changed": 1,
                "homepage_changed": False,
                "child_pages_changed": 1,
            },
            "url_results": [
                {
                    "url": "http://127.0.0.1:8080/dev/change-test-site/policy-a",
                    "status": "changed",
                    "depth": 1,
                    "snapshot_id": 10,
                    "previous_snapshot_id": 9,
                    "diff_id": 5,
                    "content_hash": "hash",
                    "page_change": {"page_type": "Child page"},
                }
            ],
        }
        execution_service = MonitorExecutionService(
            repository=self.repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(return_value=pipeline_result)
            ),
            history_file=self.history_file,
            run_store=self.run_store,
        )
        client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
                execution_service=execution_service,
            )
        )
        response = client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["change_status"], "changed")
        self.assertIsNotNone(payload["run_history_id"])
        details = client.get(f"/api/runs/{payload['run_history_id']}")
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.json()["pages_changed"], 1)


if __name__ == "__main__":
    unittest.main()
