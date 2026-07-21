import gc
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from app.analysis.diff_processor import create_diff_result
from app.crawler.crawl_cache import should_crawl
from app.crawler.url_normalizer import normalize_page_url
from app.dev.change_test_site import (
    LOCAL_TEST_MONITOR_ID,
    reset_state,
    set_policy_c_enabled,
    update_page,
)
from app.pipeline import MonitoringPipeline
from app.monitors.repository import MonitorRepository
from app.source.source_loader import load_monitors
from app.storage.service import StorageService


class MultipageChangeDetectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.state_file = base_path / "change_test_site.json"
        reset_state(state_file=self.state_file, persist=True)
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.base_url = "http://127.0.0.1:8080/dev/change-test-site"
        self.analyze_fn = MagicMock(
            return_value={
                "impact_level": "HIGH",
                "affected_modules": ["Network"],
                "reason": "Should not be called for test monitor.",
                "recommended_actions": [],
                "confidence": "HIGH",
            }
        )

    def tearDown(self):
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _monitor_config(self, **overrides) -> dict:
        monitor = {
            "id": LOCAL_TEST_MONITOR_ID,
            "name": "Local Multi-page Change Test",
            "url": self.base_url,
            "keywords": ["policy", "change", "test"],
            "category": "TEST",
            "frequency": "daily",
            "enabled": True,
            "crawl_mode": "multi_page",
            "max_depth": 1,
            "max_pages": 3,
            "same_domain_only": True,
            "skip_ai_analysis": True,
            "_change_test_state_file": str(self.state_file),
        }
        monitor.update(overrides)
        return monitor

    def _crawl_fn(self, crawl_source: dict) -> dict:
        from app.dev.change_test_site import render_page_markdown, resolve_page_metadata

        url = crawl_source["url"]
        path = urlparse(url).path or "/dev/change-test-site"
        monitor = crawl_source.get("monitor", {})
        state_file = monitor.get("_change_test_state_file")
        markdown = render_page_markdown(path, state_file=state_file)
        metadata = resolve_page_metadata(path, state_file=state_file)
        parsed = urlparse(url)
        slug = (parsed.path or "root").strip("/").replace("/", "_") or "root"

        return {
            "source_id": crawl_source["source_id"],
            "url": url,
            "title": metadata["title"],
            "markdown": markdown,
            "timestamp": datetime.now().isoformat(),
            "normalized_url": normalize_page_url(url),
            "url_slug": slug,
            "crawl_depth": crawl_source.get("discovered_depth", 0),
            "parent_url": crawl_source.get("parent_url"),
        }

    def _get_latest_snapshot_for_url(self, source_id: str, url: str):
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
            crawl_fn=self._crawl_fn,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            get_latest_snapshot_for_url_fn=self._get_latest_snapshot_for_url,
            create_diff_result_fn=create_diff_result,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=self.analyze_fn,
            extract_regulation_fn=MagicMock(return_value={}),
            save_analysis_fn=self.store.save_analysis,
            save_knowledge_item_fn=self.store.save_knowledge_item,
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            load_sources_fn=lambda: [self._monitor_config()],
            get_crawl_cache_fn=self.store.get_crawl_cache,
            update_crawl_cache_fn=self.store.update_crawl_cache,
            get_snapshot_by_id_fn=self.store.get_snapshot_by_id,
            get_distinct_monitor_urls_fn=self.store.get_distinct_monitor_urls,
            should_crawl_fn=lambda url, frequency: True,
        )

    def _run_monitor(self, pipeline: MonitoringPipeline | None = None) -> dict:
        pipeline = pipeline or self._build_pipeline()
        return pipeline.process_source(self._monitor_config())

    def _changed_url_results(self, result: dict) -> list[dict]:
        return [
            item
            for item in result.get("url_results", [])
            if item.get("status") == "changed"
        ]

    def test_scenario_1_baseline(self):
        result = self._run_monitor()
        summary = result["page_change_summary"]

        self.assertEqual(summary["pages_checked"], 3)
        self.assertEqual(summary["pages_changed"], 0)
        self.assertEqual(summary["overall_status"], "no_change")
        self.assertEqual(len(self.store.get_diff_history(LOCAL_TEST_MONITOR_ID)), 0)
        self.analyze_fn.assert_not_called()

    def test_scenario_2_homepage_only_change(self):
        self._run_monitor()
        update_page(
            "homepage",
            text="Homepage-only update for change detection testing.",
            state_file=self.state_file,
        )

        result = self._run_monitor()
        summary = result["page_change_summary"]
        changed = self._changed_url_results(result)

        self.assertEqual(summary["pages_changed"], 1)
        self.assertTrue(summary["homepage_changed"])
        self.assertEqual(summary["child_pages_changed"], 0)
        self.assertEqual(len(changed), 1)
        self.assertTrue(changed[0]["url"].rstrip("/").endswith("/dev/change-test-site"))
        self.assertTrue(changed[0]["page_change"]["is_homepage"])
        self.analyze_fn.assert_not_called()

    def test_scenario_3_child_page_only_change(self):
        self._run_monitor()
        update_page(
            "policy_a",
            text="Policy A-only update for change detection testing.",
            state_file=self.state_file,
        )

        result = self._run_monitor()
        summary = result["page_change_summary"]
        changed = self._changed_url_results(result)

        self.assertEqual(summary["pages_changed"], 1)
        self.assertFalse(summary["homepage_changed"])
        self.assertEqual(summary["child_pages_changed"], 1)
        self.assertEqual(len(changed), 1)
        self.assertTrue(changed[0]["url"].endswith("/policy-a"))
        self.assertTrue(changed[0]["page_change"]["is_child_page"])
        self.assertFalse(changed[0]["page_change"]["is_homepage"])

    def test_scenario_4_two_child_pages_change(self):
        self._run_monitor()
        update_page("policy_a", text="Policy A update.", state_file=self.state_file)
        update_page("policy_b", text="Policy B update.", state_file=self.state_file)

        result = self._run_monitor()
        summary = result["page_change_summary"]
        changed = self._changed_url_results(result)

        self.assertEqual(summary["pages_changed"], 2)
        self.assertFalse(summary["homepage_changed"])
        self.assertEqual(summary["child_pages_changed"], 2)
        self.assertEqual(len(changed), 2)

    def test_scenario_5_homepage_and_child_change(self):
        self._run_monitor()
        update_page("homepage", text="Homepage update.", state_file=self.state_file)
        update_page("policy_b", text="Policy B update.", state_file=self.state_file)

        result = self._run_monitor()
        summary = result["page_change_summary"]
        changed = self._changed_url_results(result)

        self.assertEqual(summary["pages_changed"], 2)
        self.assertTrue(summary["homepage_changed"])
        self.assertEqual(summary["child_pages_changed"], 1)
        self.assertEqual(len(changed), 2)

    def test_scenario_6_new_page_discovered(self):
        monitor = self._monitor_config(max_pages=4)
        pipeline = MonitoringPipeline(
            crawl_fn=self._crawl_fn,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            get_latest_snapshot_for_url_fn=self._get_latest_snapshot_for_url,
            create_diff_result_fn=create_diff_result,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=self.analyze_fn,
            extract_regulation_fn=MagicMock(return_value={}),
            save_analysis_fn=self.store.save_analysis,
            save_knowledge_item_fn=self.store.save_knowledge_item,
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            get_crawl_cache_fn=self.store.get_crawl_cache,
            update_crawl_cache_fn=self.store.update_crawl_cache,
            get_snapshot_by_id_fn=self.store.get_snapshot_by_id,
            get_distinct_monitor_urls_fn=self.store.get_distinct_monitor_urls,
            should_crawl_fn=lambda url, frequency: True,
        )
        pipeline.process_source(monitor)
        set_policy_c_enabled(True, state_file=self.state_file)

        result = pipeline.process_source(monitor)
        summary = result["page_change_summary"]
        statuses = {item["status"] for item in result["url_results"]}

        self.assertIn("page_added", statuses)
        self.assertGreaterEqual(summary["pages_added"], 1)
        self.assertTrue(
            any(
                item.get("url", "").endswith("/policy-c")
                for item in result["url_results"]
            )
        )

    def test_scenario_7_child_page_removed(self):
        set_policy_c_enabled(True, state_file=self.state_file)
        monitor = self._monitor_config(max_pages=4)
        pipeline = MonitoringPipeline(
            crawl_fn=self._crawl_fn,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            get_latest_snapshot_for_url_fn=self._get_latest_snapshot_for_url,
            create_diff_result_fn=create_diff_result,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=self.analyze_fn,
            extract_regulation_fn=MagicMock(return_value={}),
            save_analysis_fn=self.store.save_analysis,
            save_knowledge_item_fn=self.store.save_knowledge_item,
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            get_crawl_cache_fn=self.store.get_crawl_cache,
            update_crawl_cache_fn=self.store.update_crawl_cache,
            get_snapshot_by_id_fn=self.store.get_snapshot_by_id,
            get_distinct_monitor_urls_fn=self.store.get_distinct_monitor_urls,
            should_crawl_fn=lambda url, frequency: True,
        )
        pipeline.process_source(monitor)

        set_policy_c_enabled(False, state_file=self.state_file)
        result = pipeline.process_source(self._monitor_config(max_pages=3))
        summary = result["page_change_summary"]
        statuses = {item["status"] for item in result["url_results"]}

        self.assertIn("page_removed", statuses)
        self.assertGreaterEqual(summary["pages_removed"], 1)
        with self.store._connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) AS total FROM snapshots WHERE source_id = ?",
                (LOCAL_TEST_MONITOR_ID,),
            ).fetchone()["total"]
        self.assertGreaterEqual(count, 4)

    def test_scenario_8_unchanged_rerun(self):
        self._run_monitor()
        first_diff_count = len(self.store.get_diff_history(LOCAL_TEST_MONITOR_ID))

        result = self._run_monitor()
        summary = result["page_change_summary"]
        second_diff_count = len(self.store.get_diff_history(LOCAL_TEST_MONITOR_ID))

        self.assertEqual(summary["pages_changed"], 0)
        self.assertEqual(summary["overall_status"], "no_change")
        self.assertEqual(first_diff_count, second_diff_count)

    def test_scenario_9_url_normalization(self):
        self.assertEqual(
            normalize_page_url(f"{self.base_url}/policy-a"),
            normalize_page_url(f"{self.base_url}/policy-a/"),
        )
        self.assertEqual(
            normalize_page_url(f"{self.base_url}/policy-a"),
            normalize_page_url(f"{self.base_url}/policy-a#section"),
        )
        self.assertNotEqual(
            normalize_page_url("https://news.ycombinator.com/item?id=123"),
            normalize_page_url("https://news.ycombinator.com/item?id=456"),
        )

        self._run_monitor()
        pipeline = self._build_pipeline()
        alt_monitor = self._monitor_config(
            url=f"{self.base_url}/policy-a/",
        )
        alt_result = pipeline._process_url(
            alt_monitor,
            {
                "source_id": LOCAL_TEST_MONITOR_ID,
                "name": alt_monitor["name"],
                "url": alt_monitor["url"],
                "keywords": alt_monitor["keywords"],
                "category": alt_monitor["category"],
                "frequency": alt_monitor["frequency"],
            },
            {"url": f"{self.base_url}/policy-a#section", "depth": 1, "title": "Policy A"},
        )
        self.assertEqual(alt_result["status"], "skipped")

    def test_scenario_10_test_monitors_disabled_by_default(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            seed_file = Path(temp_dir) / "monitors.json"
            db_path = Path(temp_dir) / "storage.db"
            seed_file.write_text(
                json.dumps(
                    {
                        "monitors": [
                            {
                                "id": "hacker-news-change-test",
                                "name": "Hacker News Change Detection Test",
                                "url": "https://news.ycombinator.com/",
                                "keywords": ["news"],
                                "category": "TEST",
                                "frequency": "weekly",
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
                    }
                ),
                encoding="utf-8",
            )

            repository = MonitorRepository(db_path=db_path, seed_file=seed_file)
            test_ids = {"hacker-news-change-test", LOCAL_TEST_MONITOR_ID}
            test_monitors = [
                monitor
                for monitor in repository.list_monitors()
                if monitor["id"] in test_ids
            ]

            self.assertEqual(len(test_monitors), 2)
            for monitor in test_monitors:
                self.assertFalse(monitor["enabled"])

    def test_skip_ai_analysis_does_not_call_analyzer(self):
        self._run_monitor()
        update_page("policy_a", text="Another Policy A update.", state_file=self.state_file)
        self._run_monitor()
        self.analyze_fn.assert_not_called()


class DevChangeTestApiTests(unittest.TestCase):
    def test_dev_endpoints_hidden_in_production(self):
        from fastapi.testclient import TestClient

        from app.web.app import create_dashboard_app

        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            client = TestClient(create_dashboard_app())
            response = client.get("/dev/change-test-site/status")
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
