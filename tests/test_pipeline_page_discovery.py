import unittest
from unittest.mock import MagicMock, patch

from app.pipeline import MonitoringPipeline


class TestPipelineMissingUrlClassification(unittest.TestCase):

    @patch("app.pipeline.classify_missing_discovered_url")
    @patch("app.pipeline.MonitoringPipeline._process_url")
    @patch("app.pipeline.MonitoringPipeline.resolve_monitor_urls_fn", create=True)
    def test_missing_url_uses_not_discovered_status(
        self,
        mock_resolve,
        mock_process_url,
        mock_classify,
    ):
        mock_classify.return_value = (
            "page_not_discovered",
            "Previously monitored page was not discovered in this crawl.",
        )
        mock_resolve.return_value = MagicMock(
            urls=[{"url": "https://example.com/", "depth": 0, "title": "Home"}]
        )
        mock_process_url.return_value = {
            "url": "https://example.com/",
            "depth": 0,
            "status": "skipped",
            "snapshot_id": 1,
            "diff_id": None,
            "analysis_id": None,
            "first_snapshot": False,
            "message": "unchanged",
        }

        pipeline = MonitoringPipeline(
            resolve_monitor_urls_fn=lambda _monitor: MagicMock(
                urls=[{"url": "https://example.com/", "depth": 0, "title": "Home"}]
            ),
            get_distinct_monitor_urls_fn=lambda _source_id: [
                "https://example.com/",
                "https://example.com/old-page",
            ],
            crawl_fn=MagicMock(),
            save_snapshot_fn=MagicMock(),
            get_latest_snapshot_fn=MagicMock(return_value=None),
            get_latest_snapshot_for_url_fn=MagicMock(return_value=None),
            create_diff_result_fn=MagicMock(),
            save_diff_fn=MagicMock(),
            analyze_change_impact_fn=MagicMock(),
            extract_regulation_fn=MagicMock(),
            save_analysis_fn=MagicMock(),
            save_knowledge_item_fn=MagicMock(),
            notify_if_needed_fn=MagicMock(return_value={"skipped": True}),
            get_crawl_cache_fn=MagicMock(return_value=None),
            update_crawl_cache_fn=MagicMock(),
            get_snapshot_by_id_fn=MagicMock(return_value=None),
            should_crawl_fn=lambda *_args, **_kwargs: True,
            load_sources_fn=lambda: [],
        )

        result = pipeline.process_source(
            {
                "id": "example",
                "name": "Example",
                "url": "https://example.com/",
                "keywords": ["example"],
                "category": "test",
                "frequency": "daily",
                "enabled": True,
                "crawl_mode": "single",
            }
        )

        statuses = {item["status"] for item in result["url_results"]}
        self.assertIn("page_not_discovered", statuses)
        summary = result["page_change_summary"]
        self.assertGreaterEqual(summary["pages_not_discovered"], 1)
        self.assertEqual(summary["pages_removed"], 0)


if __name__ == "__main__":
    unittest.main()
