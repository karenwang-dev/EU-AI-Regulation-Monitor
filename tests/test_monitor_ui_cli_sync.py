import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.analysis.diff_processor import create_diff_result
from app.dev.change_test_site import LOCAL_TEST_MONITOR_ID, reset_state
from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.pipeline import MonitoringPipeline
from app.source.source_loader import load_monitors
from app.storage.service import StorageService
from app.web.monitor_api import MonitorStore, MonitorUpdateRequest


class MonitorUiCliSyncTests(unittest.TestCase):
    def setUp(self):
        reset_monitor_repository()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.db_path = base_path / "storage.db"
        self.seed_file = base_path / "monitors.json"
        reset_state(state_file=base_path / "change_test_site.json", persist=True)

        self.seed_file.write_text(
            json.dumps(
                {
                    "monitors": [
                        {
                            "id": LOCAL_TEST_MONITOR_ID,
                            "name": "Local Multi-page Change Test",
                            "url": "http://127.0.0.1:8080/dev/change-test-site",
                            "keywords": ["policy", "change", "test"],
                            "category": "TEST",
                            "frequency": "daily",
                            "enabled": False,
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
        self.store = MonitorStore(repository=self.repository)
        self.storage = StorageService(
            db_path=self.db_path,
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

    def tearDown(self):
        self.repository = None
        self.storage = None
        gc.collect()
        reset_monitor_repository()
        self.temp_dir.cleanup()

    def _enabled_monitors_from_cli(self) -> list[dict]:
        monitors = load_monitors(repository=self.repository)
        return [
            monitor for monitor in monitors if monitor.get("enabled", True)
        ]

    def test_enable_through_ui_service_is_visible_to_cli(self):
        self.assertEqual(len(self._enabled_monitors_from_cli()), 0)

        self.store.update_monitor(
            LOCAL_TEST_MONITOR_ID,
            MonitorUpdateRequest(enabled=True),
        )

        enabled = self._enabled_monitors_from_cli()
        self.assertEqual(len(enabled), 1)
        self.assertEqual(enabled[0]["id"], LOCAL_TEST_MONITOR_ID)

    def test_disable_through_ui_service_is_visible_to_cli(self):
        self.store.update_monitor(
            LOCAL_TEST_MONITOR_ID,
            MonitorUpdateRequest(enabled=True),
        )
        self.assertEqual(len(self._enabled_monitors_from_cli()), 1)

        self.store.update_monitor(
            LOCAL_TEST_MONITOR_ID,
            MonitorUpdateRequest(enabled=False),
        )
        self.assertEqual(len(self._enabled_monitors_from_cli()), 0)

    def test_enabled_monitor_is_executed_by_pipeline(self):
        self.store.update_monitor(
            LOCAL_TEST_MONITOR_ID,
            MonitorUpdateRequest(enabled=True),
        )
        monitor = self.repository.get_monitor(LOCAL_TEST_MONITOR_ID)

        pipeline = MonitoringPipeline(
            crawl_fn=MagicMock(
                return_value={
                    "source_id": monitor["id"],
                    "url": monitor["url"],
                    "title": monitor["name"],
                    "content": "baseline",
                    "timestamp": "2026-07-21T09:00:00",
                }
            ),
            save_snapshot_fn=self.storage.save_snapshot,
            get_latest_snapshot_fn=self.storage.get_latest_snapshot,
            get_latest_snapshot_for_url_fn=lambda source_id, url: None,
            create_diff_result_fn=create_diff_result,
            save_diff_fn=self.storage.save_diff,
            analyze_change_impact_fn=MagicMock(),
            extract_regulation_fn=MagicMock(return_value={}),
            save_analysis_fn=self.storage.save_analysis,
            save_knowledge_item_fn=self.storage.save_knowledge_item,
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            load_sources_fn=lambda: self._enabled_monitors_from_cli(),
            get_crawl_cache_fn=self.storage.get_crawl_cache,
            update_crawl_cache_fn=self.storage.update_crawl_cache,
            get_snapshot_by_id_fn=self.storage.get_snapshot_by_id,
            get_distinct_monitor_urls_fn=self.storage.get_distinct_monitor_urls,
            should_crawl_fn=lambda url, frequency: True,
        )

        results = pipeline.run()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_id"], LOCAL_TEST_MONITOR_ID)

    def test_seed_import_is_idempotent(self):
        first_count = len(self.repository.list_monitors())
        duplicate_repo = MonitorRepository(
            db_path=self.db_path,
            seed_file=self.seed_file,
        )
        self.assertEqual(len(duplicate_repo.list_monitors()), first_count)

    def test_seed_import_preserves_monitor_ids(self):
        monitor = self.repository.get_monitor(LOCAL_TEST_MONITOR_ID)
        self.assertIsNotNone(monitor)
        self.assertEqual(monitor["id"], LOCAL_TEST_MONITOR_ID)


if __name__ == "__main__":
    unittest.main()
