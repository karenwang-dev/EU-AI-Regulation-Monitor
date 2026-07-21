import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.analysis.diff_processor import create_diff_result
from app.crawler.crawl_cache import should_crawl
from app.crawler.service import crawl
from app.dev.change_test_site import (
    LOCAL_TEST_MONITOR_ID,
    get_public_status,
    render_page_markdown,
    reset_state,
    update_page,
)
from app.pipeline import MonitoringPipeline
from app.run_history import _summarize_results
from app.storage.service import StorageService
from app.web.app import _get_changes_for_dashboard
from app.web.change_helper import filter_changes_by_impact


class RunOnceMultipagePolicyAFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.state_file = base_path / "change_test_site.json"
        self.monitors_file = base_path / "monitors.json"

        reset_state(state_file=self.state_file, persist=True)
        self.monitors_file.write_text(
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
            should_crawl_fn=lambda url, frequency: should_crawl(
                url,
                frequency,
                get_cache_fn=self.store.get_crawl_cache,
            ),
        )

    def _run_once_results(self) -> list[dict]:
        return [self._build_pipeline().process_source(self.monitor)]

    def test_exact_cli_flow_policy_a_change(self):
        baseline = self._run_once_results()[0]
        summary1 = baseline["page_change_summary"]

        self.assertEqual(summary1["pages_checked"], 3)
        self.assertEqual(summary1["pages_changed"], 0)
        self.assertEqual(baseline["status"], "first_snapshot")
        self.assertEqual(len(self.store.get_diff_history(LOCAL_TEST_MONITOR_ID)), 0)

        update_page(
            "policy_a",
            text="Updated Policy A requirement for run-once reproduction.",
            state_file=self.state_file,
        )
        status = get_public_status(self.state_file)
        self.assertGreater(status["policy_a_version"], 1)
        policy_md = render_page_markdown(
            "/dev/change-test-site/policy-a",
            state_file=self.state_file,
        )
        self.assertIn("Updated Policy A requirement", policy_md)

        result = self._run_once_results()[0]
        summary2 = result["page_change_summary"]

        self.assertEqual(summary2["pages_checked"], 3)
        self.assertEqual(summary2["pages_changed"], 1)
        self.assertFalse(summary2["homepage_changed"])
        self.assertEqual(summary2["child_pages_changed"], 1)
        self.assertEqual(result["status"], "changed")
        self.assertIsNotNone(result["diff_id"])

        changed_pages = [
            item for item in result["url_results"] if item.get("page_changed")
        ]
        self.assertEqual(len(changed_pages), 1)
        self.assertTrue(changed_pages[0]["url"].endswith("/policy-a"))
        self.assertFalse(changed_pages[0].get("cache_hit"))
        self.assertIsNotNone(changed_pages[0].get("previous_snapshot_id"))
        self.assertNotEqual(
            changed_pages[0]["previous_snapshot_id"],
            changed_pages[0]["snapshot_id"],
        )

        diffs = self.store.get_diff_history(LOCAL_TEST_MONITOR_ID)
        self.assertEqual(len(diffs), 1)

        history_entry = _summarize_results([result])
        self.assertEqual(history_entry["changed_count"], 1)

        with patch("app.web.app.load_monitors", return_value=[self.monitor]):
            changes = _get_changes_for_dashboard(self.store, limit=None)
        self.assertEqual(len(changes), 1)
        self.assertTrue(changes[0]["source_url"].endswith("/policy-a"))
        self.assertEqual(filter_changes_by_impact(changes, "UNASSESSED"), changes)
        self.assertEqual(filter_changes_by_impact(changes, "HIGH"), [])

        rerun = self._run_once_results()[0]
        self.assertEqual(rerun["page_change_summary"]["pages_changed"], 0)
        self.assertEqual(len(self.store.get_diff_history(LOCAL_TEST_MONITOR_ID)), 1)

    def test_aggregate_uses_child_page_diff_not_homepage_only(self):
        pipeline = self._build_pipeline()
        pipeline.process_source(self.monitor)
        update_page(
            "policy_a",
            text="Child page only aggregate check.",
            state_file=self.state_file,
        )
        result = pipeline.process_source(self.monitor)

        self.assertEqual(result["status"], "changed")
        self.assertIsNotNone(result["diff_id"])
        policy_result = next(
            item for item in result["url_results"] if item["url"].endswith("/policy-a")
        )
        self.assertEqual(result["diff_id"], policy_result["diff_id"])
        self.assertEqual(result["snapshot_id"], policy_result["snapshot_id"])


if __name__ == "__main__":
    unittest.main()
