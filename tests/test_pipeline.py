import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.pipeline import MonitoringPipeline, normalize_source
from app.analysis.diff_processor import create_diff_result
from app.ai.regulation_extractor import EXTRACTION_MODE_DIFF
from app.crawler.crawl_cache import should_crawl
from app.storage.service import StorageService


class TestMonitoringPipeline(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

    def tearDown(self):
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _crawl_result(
        self,
        source_id: str = "ec",
        name: str = "European Commission",
        markdown: str = "# Regulation update",
        timestamp: str = "2026-07-15T12:00:00",
    ) -> dict:
        return {
            "source_id": source_id,
            "url": "https://example.com/ec",
            "title": name,
            "markdown": markdown,
            "timestamp": timestamp,
        }

    def _monitor_config(self) -> dict:
        return {
            "id": "ec",
            "name": "European Commission",
            "enabled": True,
            "url": "https://example.com/ec",
            "keywords": ["EU Regulation", "Smart TV"],
            "category": "EU Policy",
            "frequency": "daily",
        }

    def _impact_result(self) -> dict:
        return {
            "impact_level": "HIGH",
            "affected_modules": ["Network", "AI Features"],
            "reason": "New cybersecurity requirements affect connected TVs.",
            "recommended_actions": ["Review OTA security controls"],
            "confidence": "HIGH",
        }

    def _regulation_extraction_result(self) -> dict:
        return {
            "title": "EU Cybersecurity Regulation Update",
            "publish_date": "2026-05-07",
            "summary": "New cybersecurity obligations for connected devices.",
            "category": "Cybersecurity",
            "regulation_type": "AMENDMENT",
            "effective_date": "2028-08-02",
            "affected_countries": ["EU"],
            "affected_products": ["Smart TV"],
            "affected_modules": ["Network", "Cybersecurity controls"],
            "key_requirements": ["Assess connected device security"],
            "actions_required": ["Update compliance checklist"],
            "is_regulation_content": True,
            "confidence": "HIGH",
        }

    def _get_latest_snapshot_for_url(self, source_id: str, url: str):
        with self.store._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM snapshots
                WHERE source_id = ? AND url = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
                """,
                (source_id, url),
            ).fetchone()

        if row is None:
            return None

        return self.store._row_to_snapshot(row)

    def _build_pipeline(
        self,
        crawl_fn,
        analyze_fn=None,
        extract_regulation_fn=None,
        resolve_monitor_urls_fn=None,
    ) -> MonitoringPipeline:
        analyze_fn = analyze_fn or MagicMock(
            return_value=self._impact_result()
        )
        extract_regulation_fn = extract_regulation_fn or MagicMock(
            return_value=self._regulation_extraction_result()
        )

        pipeline_kwargs = {
            "crawl_fn": crawl_fn,
            "save_snapshot_fn": self.store.save_snapshot,
            "get_latest_snapshot_fn": self.store.get_latest_snapshot,
            "get_latest_snapshot_for_url_fn": self._get_latest_snapshot_for_url,
            "create_diff_result_fn": create_diff_result,
            "save_diff_fn": self.store.save_diff,
            "analyze_change_impact_fn": analyze_fn,
            "extract_regulation_fn": extract_regulation_fn,
            "save_analysis_fn": self.store.save_analysis,
            "save_knowledge_item_fn": self.store.save_knowledge_item,
            "notify_if_needed_fn": MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            "load_sources_fn": lambda: [self._monitor_config()],
            "get_crawl_cache_fn": self.store.get_crawl_cache,
            "update_crawl_cache_fn": self.store.update_crawl_cache,
            "get_snapshot_by_id_fn": self.store.get_snapshot_by_id,
            "should_crawl_fn": lambda url, frequency: should_crawl(
                url,
                frequency,
                get_cache_fn=self.store.get_crawl_cache,
            ),
        }
        if resolve_monitor_urls_fn is not None:
            pipeline_kwargs["resolve_monitor_urls_fn"] = resolve_monitor_urls_fn

        return MonitoringPipeline(**pipeline_kwargs)

    def test_normalize_source_maps_monitor_fields(self):
        normalized = normalize_source(self._monitor_config())

        self.assertEqual(normalized["source_id"], "ec")
        self.assertEqual(normalized["keywords"], ["EU Regulation", "Smart TV"])
        self.assertEqual(normalized["category"], "EU Policy")
        self.assertEqual(normalized["frequency"], "daily")

    def test_first_snapshot_has_no_diff_or_ai(self):
        crawl_mock = MagicMock(
            return_value=self._crawl_result(markdown="# First capture")
        )
        analyze_mock = MagicMock()
        extract_mock = MagicMock()
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=analyze_mock,
            extract_regulation_fn=extract_mock,
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "first_snapshot")
        self.assertTrue(result["first_snapshot"])
        self.assertIsNone(result["diff_id"])
        self.assertIsNone(result["analysis_id"])
        analyze_mock.assert_not_called()
        extract_mock.assert_not_called()
        self.assertEqual(len(self.store.get_diff_history("ec")), 0)

    def test_unchanged_content_skips_ai(self):
        markdown = "# Stable regulation page"
        self.store.save_snapshot(
            self._crawl_result(
                markdown=markdown,
                timestamp="2026-07-15T10:00:00",
            )
        )

        crawl_mock = MagicMock(
            return_value=self._crawl_result(
                markdown=markdown,
                timestamp="2026-07-15T12:00:00",
            )
        )
        analyze_mock = MagicMock()
        extract_mock = MagicMock()
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=analyze_mock,
            extract_regulation_fn=extract_mock,
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "skipped")
        self.assertIsNone(result["diff_id"])
        self.assertIsNone(result["analysis_id"])
        analyze_mock.assert_not_called()
        extract_mock.assert_not_called()
        self.assertEqual(len(self.store.get_analysis_history("ec")), 0)

    def test_changed_diff_triggers_ai_and_saves_result(self):
        self.store.save_snapshot(
            self._crawl_result(
                markdown="# Old version",
                timestamp="2026-07-15T10:00:00",
            )
        )

        crawl_mock = MagicMock(
            return_value=self._crawl_result(
                markdown="# New version\nAdded regulation section",
                timestamp="2026-07-15T12:00:00",
            )
        )
        analyze_mock = MagicMock(return_value=self._impact_result())
        extract_mock = MagicMock(return_value=self._regulation_extraction_result())
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=analyze_mock,
            extract_regulation_fn=extract_mock,
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "analyzed")
        self.assertIsNotNone(result["diff_id"])
        self.assertIsNotNone(result["analysis_id"])
        self.assertIsNotNone(result["knowledge_id"])
        self.assertEqual(result["impact"]["impact_level"], "HIGH")
        self.assertEqual(
            result["regulation_extraction"]["regulation_type"],
            "AMENDMENT",
        )

        extract_mock.assert_called_once()
        extract_kwargs = extract_mock.call_args.kwargs
        self.assertEqual(extract_kwargs["mode"], EXTRACTION_MODE_DIFF)
        self.assertEqual(extract_kwargs["monitor"]["id"], "ec")
        self.assertIn(
            "Added regulation section",
            extract_kwargs["diff_result"]["added_content"],
        )

        analyze_mock.assert_called_once()
        diff_arg, monitor_arg = analyze_mock.call_args.args
        self.assertIn("Added regulation section", diff_arg["added_content"])
        self.assertEqual(monitor_arg["id"], "ec")

        history = self.store.get_analysis_history("ec")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["analysis"]["impact_level"], "HIGH")
        self.assertIn("Network", history[0]["analysis"]["affected_modules"])
        self.assertEqual(
            history[0]["analysis"]["regulation_extraction"]["title"],
            "EU Cybersecurity Regulation Update",
        )
        self.assertTrue(
            history[0]["analysis"]["regulation_extraction"]["is_regulation_content"]
        )

        analysis = history[0]["analysis"]
        self.assertIn("evidence", analysis)
        self.assertEqual(len(analysis["evidence"]), 1)

        evidence = analysis["evidence"][0]
        self.assertEqual(evidence["source_id"], "ec")
        self.assertEqual(evidence["name"], "European Commission")
        self.assertEqual(evidence["url"], "https://example.com/ec")
        self.assertEqual(evidence["snapshot_id"], result["snapshot_id"])
        self.assertEqual(evidence["diff_id"], result["diff_id"])
        self.assertEqual(evidence["timestamp"], "2026-07-15T12:00:00")
        self.assertEqual(result["impact"]["evidence"], analysis["evidence"])
        self.assertEqual(
            result["impact"]["regulation_extraction"],
            analysis["regulation_extraction"],
        )

    def test_regulation_extraction_runs_before_impact_analysis(self):
        self.store.save_snapshot(
            self._crawl_result(
                markdown="# Old version",
                timestamp="2026-07-15T10:00:00",
            )
        )

        crawl_mock = MagicMock(
            return_value=self._crawl_result(
                markdown="# New version\nAdded regulation section",
                timestamp="2026-07-15T12:00:00",
            )
        )
        call_order: list[str] = []

        def extract_side_effect(**kwargs):
            call_order.append("extract")
            return self._regulation_extraction_result()

        def analyze_side_effect(*args, **kwargs):
            call_order.append("impact")
            return self._impact_result()

        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=MagicMock(side_effect=analyze_side_effect),
            extract_regulation_fn=MagicMock(side_effect=extract_side_effect),
        )

        pipeline.process_source(self._monitor_config())

        self.assertEqual(call_order, ["extract", "impact"])

    def test_disabled_sources_are_not_processed(self):
        crawl_mock = MagicMock(
            return_value=self._crawl_result()
        )
        analyze_mock = MagicMock()
        extract_mock = MagicMock()
        pipeline = MonitoringPipeline(
            crawl_fn=crawl_mock,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=analyze_mock,
            extract_regulation_fn=extract_mock,
            save_analysis_fn=self.store.save_analysis,
            notify_if_needed_fn=MagicMock(),
            load_sources_fn=lambda: [
                {
                    **self._monitor_config(),
                    "enabled": False,
                }
            ],
        )

        results = pipeline.run()

        crawl_mock.assert_not_called()
        analyze_mock.assert_not_called()
        extract_mock.assert_not_called()
        self.assertEqual(results, [])

    @patch("app.crawler.url_resolver.discover_links")
    def test_single_mode_does_not_call_discovery(self, discover_mock):
        discover_mock.return_value = []

        def crawl(source):
            return {
                **self._crawl_result(markdown="# First capture"),
                "url": source["url"],
            }

        pipeline = self._build_pipeline(crawl_fn=crawl)
        monitor = {
            **self._monitor_config(),
            "crawl_mode": "single",
            "max_depth": 0,
            "max_pages": 1,
        }

        result = pipeline.process_source(monitor)

        discover_mock.assert_not_called()
        self.assertEqual(result["status"], "first_snapshot")

    def test_smart_mode_crawls_multiple_urls(self):
        urls = [
            "https://example.com/ec",
            "https://example.com/ec/ai-act",
            "https://example.com/ec/cybersecurity",
        ]

        def resolve_monitor_urls(_monitor):
            return [
                {"url": urls[0], "title": "Root", "depth": 0},
                {"url": urls[1], "title": "AI Act", "depth": 1},
                {"url": urls[2], "title": "Cybersecurity", "depth": 1},
            ]

        def crawl(source):
            return {
                "source_id": source["source_id"],
                "url": source["url"],
                "title": source.get("name", ""),
                "markdown": f"# Content for {source['url']}",
                "timestamp": "2026-07-15T12:00:00",
                "parent_monitor_id": source.get("parent_monitor_id"),
                "discovered_depth": source.get("discovered_depth"),
            }

        crawl_mock = MagicMock(side_effect=crawl)
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            resolve_monitor_urls_fn=resolve_monitor_urls,
        )
        monitor = {
            **self._monitor_config(),
            "crawl_mode": "smart",
            "max_depth": 2,
            "max_pages": 3,
        }

        result = pipeline.process_source(monitor)

        self.assertEqual(crawl_mock.call_count, 3)
        crawled_urls = [call.args[0]["url"] for call in crawl_mock.call_args_list]
        self.assertEqual(crawled_urls, urls)
        self.assertEqual(result["status"], "first_snapshot")
        self.assertEqual(result["pages_crawled"], 3)
        self.assertEqual(len(result["url_results"]), 3)

    def test_smart_mode_respects_max_pages_via_resolver(self):
        from app.crawler.url_resolver import resolve_monitor_urls

        monitor = {
            **self._monitor_config(),
            "crawl_mode": "smart",
            "max_depth": 2,
            "max_pages": 2,
        }
        discover_mock = MagicMock(
            return_value=[
                {
                    "url": "https://example.com/ec/one",
                    "title": "One",
                    "depth": 1,
                },
                {
                    "url": "https://example.com/ec/two",
                    "title": "Two",
                    "depth": 1,
                },
            ]
        )

        results = resolve_monitor_urls(monitor, discover_links_fn=discover_mock)

        self.assertEqual(len(results), 2)

    def test_one_failed_child_page_does_not_stop_others(self):
        urls = [
            "https://example.com/ec",
            "https://example.com/ec/failing",
            "https://example.com/ec/working",
        ]

        def resolve_monitor_urls(_monitor):
            return [
                {"url": url, "title": url, "depth": index}
                for index, url in enumerate(urls)
            ]

        def crawl(source):
            if source["url"] == "https://example.com/ec/failing":
                raise RuntimeError("child page failed")
            return {
                "source_id": source["source_id"],
                "url": source["url"],
                "title": source.get("name", ""),
                "markdown": f"# Content for {source['url']}",
                "timestamp": "2026-07-15T12:00:00",
            }

        crawl_mock = MagicMock(side_effect=crawl)
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            resolve_monitor_urls_fn=resolve_monitor_urls,
        )
        monitor = {
            **self._monitor_config(),
            "crawl_mode": "smart",
            "max_depth": 1,
            "max_pages": 3,
        }

        result = pipeline.process_source(monitor)

        self.assertEqual(crawl_mock.call_count, 3)
        self.assertEqual(result["pages_crawled"], 3)
        statuses = {item["url"]: item["status"] for item in result["url_results"]}
        self.assertEqual(statuses["https://example.com/ec"], "first_snapshot")
        self.assertEqual(statuses["https://example.com/ec/failing"], "error")
        self.assertEqual(statuses["https://example.com/ec/working"], "first_snapshot")
        self.assertEqual(result["status"], "partial")


if __name__ == "__main__":
    unittest.main()
