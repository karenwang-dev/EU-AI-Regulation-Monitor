import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.analysis.diff_processor import create_diff_result
from app.core.paths import get_runtime_paths
from app.dev.change_test_site import LOCAL_TEST_MONITOR_ID, reset_state, update_page
from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.pipeline import MonitoringPipeline
from app.storage.service import StorageService
from app.web.app import _get_changes_for_dashboard, create_dashboard_app
from app.web.change_helper import filter_changes_by_impact
from app.web.monitor_api import MonitorStore, MonitorUpdateRequest


class ChangesCliIntegrationTests(unittest.TestCase):
    def setUp(self):
        reset_monitor_repository()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.state_file = base_path / "change_test_site.json"
        self.monitors_file = base_path / "monitors.json"
        reset_state(state_file=self.state_file, persist=True)

        self.monitors_file.write_text(
            """
{
  "monitors": [
    {
      "id": "local-multipage-change-test",
      "name": "Local Multi-page Change Test",
      "url": "http://127.0.0.1:8080/dev/change-test-site",
      "keywords": ["policy", "change", "test"],
      "category": "TEST",
      "frequency": "daily",
      "enabled": true,
      "crawl_mode": "multi_page",
      "max_depth": 1,
      "max_pages": 3,
      "fetch_mode": "http",
      "skip_ai_analysis": true
    }
  ]
}
""".strip()
            + "\n",
            encoding="utf-8",
        )

        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.monitor = {
            "id": LOCAL_TEST_MONITOR_ID,
            "name": "Local Multi-page Change Test",
            "url": "http://127.0.0.1:8080/dev/change-test-site",
            "keywords": ["policy", "change", "test"],
            "category": "TEST",
            "frequency": "daily",
            "enabled": True,
            "crawl_mode": "multi_page",
            "max_depth": 1,
            "max_pages": 3,
            "fetch_mode": "http",
            "skip_ai_analysis": True,
            "_change_test_state_file": str(self.state_file),
        }

    def tearDown(self):
        self.store = None
        reset_monitor_repository()
        gc.collect()
        self.temp_dir.cleanup()

    def _get_latest_snapshot_for_url(self, source_id: str, url: str):
        from app.crawler.url_normalizer import normalize_page_url

        normalized_target = normalize_page_url(url)
        with self.store._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM snapshots
                WHERE source_id = ?
                ORDER BY timestamp DESC, id DESC
                """,
                (source_id,),
            ).fetchall()

        for row in rows:
            snapshot = self.store._row_to_snapshot(row)
            if normalize_page_url(snapshot.get("url", "")) == normalized_target:
                return snapshot
        return None

    def _build_pipeline(self) -> MonitoringPipeline:
        from app.crawler.service import crawl

        return MonitoringPipeline(
            crawl_fn=crawl,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            get_latest_snapshot_for_url_fn=self._get_latest_snapshot_for_url,
            create_diff_result_fn=create_diff_result,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=MagicMock(),
            extract_regulation_fn=MagicMock(return_value={}),
            save_analysis_fn=self.store.save_analysis,
            save_knowledge_item_fn=self.store.save_knowledge_item,
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            load_sources_fn=lambda: [self.monitor],
            get_crawl_cache_fn=self.store.get_crawl_cache,
            update_crawl_cache_fn=self.store.update_crawl_cache,
            get_snapshot_by_id_fn=self.store.get_snapshot_by_id,
            get_distinct_monitor_urls_fn=self.store.get_distinct_monitor_urls,
            should_crawl_fn=lambda url, frequency: True,
        )

    def _run_local_monitor(self) -> dict:
        return self._build_pipeline().process_source(self.monitor)

    def test_baseline_creates_no_visible_change(self):
        result = self._run_local_monitor()
        changes = _get_changes_for_dashboard(self.store, limit=None)

        self.assertEqual(result["page_change_summary"]["pages_changed"], 0)
        self.assertEqual(len(self.store.get_diff_history(LOCAL_TEST_MONITOR_ID)), 0)
        self.assertEqual(changes, [])

    def test_policy_a_update_creates_child_page_change(self):
        self._run_local_monitor()
        update_page(
            "policy_a",
            text="Updated Policy A requirement for change detection testing.",
            state_file=self.state_file,
        )

        result = self._run_local_monitor()
        summary = result["page_change_summary"]
        diffs = self.store.get_diff_history(LOCAL_TEST_MONITOR_ID)

        self.assertEqual(summary["pages_changed"], 1)
        self.assertFalse(summary["homepage_changed"])
        self.assertEqual(summary["child_pages_changed"], 1)
        self.assertEqual(len(diffs), 1)

    def test_skip_ai_change_appears_in_unfiltered_changes(self):
        self._run_local_monitor()
        update_page("policy_a", text="Updated Policy A.", state_file=self.state_file)
        self._run_local_monitor()

        with patch("app.web.app.load_monitors", return_value=[self.monitor]):
            changes = _get_changes_for_dashboard(self.store, limit=None)

        self.assertEqual(len(changes), 1)
        self.assertTrue(changes[0]["source_url"].endswith("/policy-a"))
        self.assertEqual(changes[0]["impact_level"], "UNASSESSED")
        self.assertTrue(changes[0]["analysis_skipped"])
        self.assertEqual(changes[0]["page_type_label"], "Child page")

    def test_skip_ai_change_appears_under_unassessed_filter(self):
        self._run_local_monitor()
        update_page("policy_a", text="Updated Policy A.", state_file=self.state_file)
        self._run_local_monitor()

        with patch("app.web.app.load_monitors", return_value=[self.monitor]):
            changes = _get_changes_for_dashboard(self.store, limit=None)

        unassessed = filter_changes_by_impact(changes, "UNASSESSED")
        high = filter_changes_by_impact(changes, "HIGH")

        self.assertEqual(len(unassessed), 1)
        self.assertEqual(high, [])

    def test_unchanged_rerun_creates_no_duplicate(self):
        self._run_local_monitor()
        update_page("policy_a", text="Updated Policy A.", state_file=self.state_file)
        self._run_local_monitor()

        self._run_local_monitor()

        with patch("app.web.app.load_monitors", return_value=[self.monitor]):
            changes = _get_changes_for_dashboard(self.store, limit=None)

        self.assertEqual(len(changes), 1)
        self.assertEqual(len(self.store.get_diff_history(LOCAL_TEST_MONITOR_ID)), 1)

    def test_cli_and_web_use_same_default_storage_path(self):
        runtime_paths = get_runtime_paths()
        self.assertTrue(runtime_paths["database"].is_absolute())
        self.assertTrue(runtime_paths["change_test_site_state"].is_absolute())
        self.assertEqual(
            runtime_paths["monitors_repository"],
            runtime_paths["database"],
        )

    def test_ui_enabled_monitor_is_executed_by_run_once(self):
        with patch("app.pipeline.load_monitors", return_value=[self.monitor]):
            sources = [
                monitor
                for monitor in __import__("app.pipeline", fromlist=["load_monitors"]).load_monitors()
                if monitor.get("enabled", True)
            ]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["id"], LOCAL_TEST_MONITOR_ID)

        result = self._build_pipeline().process_source(self.monitor)
        self.assertEqual(result["source_id"], LOCAL_TEST_MONITOR_ID)

    def test_changes_page_renders_unassessed_child_page_change(self):
        self._run_local_monitor()
        update_page("policy_a", text="Updated Policy A.", state_file=self.state_file)
        self._run_local_monitor()

        app = create_dashboard_app(
            storage_service=self.store,
            monitors_repository=MonitorRepository(
                db_path=self.store.db_path,
                seed_file=self.monitors_file,
            ),
        )
        with patch("app.web.app.load_monitors", return_value=[self.monitor]):
            client = TestClient(app)
            response = client.get("/changes")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Local Multi-page Change Test", content)
        self.assertIn(b"/policy-a", content)
        self.assertIn(b"Child page", content)
        self.assertIn(b"Analysis: Skipped", content)
        self.assertIn(b"Unassessed", content)

    def test_monitor_management_persists_enabled_state(self):
        repository = MonitorRepository(
            db_path=self.store.db_path,
            seed_file=self.monitors_file,
        )
        store = MonitorStore(repository=repository)
        store.update_monitor(
            LOCAL_TEST_MONITOR_ID,
            MonitorUpdateRequest(enabled=False),
        )
        self.assertFalse(store.get_monitor(LOCAL_TEST_MONITOR_ID)["enabled"])

        store.update_monitor(
            LOCAL_TEST_MONITOR_ID,
            MonitorUpdateRequest(enabled=True),
        )
        self.assertTrue(store.get_monitor(LOCAL_TEST_MONITOR_ID)["enabled"])

    def test_crawl_cache_bypass_detects_second_run_change(self):
        pipeline = self._build_pipeline()
        pipeline.process_source(self.monitor)
        update_page("policy_a", text="Updated after cache would block.", state_file=self.state_file)

        result = pipeline.process_source(self.monitor)

        self.assertEqual(result["page_change_summary"]["pages_changed"], 1)
        self.assertEqual(len(self.store.get_diff_history(LOCAL_TEST_MONITOR_ID)), 1)


if __name__ == "__main__":
    unittest.main()
