import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.pipeline import MonitoringPipeline, normalize_source
from app.storage.service import StorageService, calculate_hash


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

    def _build_pipeline(
        self,
        crawl_fn,
        analyze_fn=None,
        clean_fn=None,
    ) -> MonitoringPipeline:
        analyze_fn = analyze_fn or MagicMock(
            return_value={"impact_level": "High", "summary": "Changed"}
        )
        clean_fn = clean_fn or MagicMock(side_effect=lambda text: text)

        return MonitoringPipeline(
            crawl_fn=crawl_fn,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            clean_content_fn=clean_fn,
            analyze_content_fn=analyze_fn,
            save_analysis_fn=self.store.save_analysis,
            load_sources_fn=lambda: [self._monitor_config()],
        )

    def test_normalize_source_maps_monitor_fields(self):
        normalized = normalize_source(self._monitor_config())

        self.assertEqual(normalized["source_id"], "ec")
        self.assertEqual(normalized["keywords"], ["EU Regulation", "Smart TV"])
        self.assertEqual(normalized["category"], "EU Policy")
        self.assertEqual(normalized["frequency"], "daily")

    def test_pipeline_processes_enabled_sources_with_mocked_crawler(self):
        crawl_mock = MagicMock(
            return_value=self._crawl_result(markdown="# First capture")
        )
        pipeline = self._build_pipeline(crawl_fn=crawl_mock)

        results = pipeline.run()

        crawl_mock.assert_called_once()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_id"], "ec")
        self.assertEqual(results[0]["status"], "analyzed")
        self.assertIsNotNone(results[0]["snapshot_id"])
        self.assertIsNotNone(results[0]["analysis_id"])

    def test_unchanged_content_skips_ai_analysis(self):
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
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=analyze_mock,
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "skipped")
        self.assertIsNone(result["analysis_id"])
        analyze_mock.assert_not_called()
        self.assertEqual(
            len(self.store.get_analysis_history("ec")),
            0,
        )

    def test_changed_content_triggers_ai_analysis(self):
        self.store.save_snapshot(
            self._crawl_result(
                markdown="# Old version",
                timestamp="2026-07-15T10:00:00",
            )
        )

        crawl_mock = MagicMock(
            return_value=self._crawl_result(
                markdown="# New version with updates",
                timestamp="2026-07-15T12:00:00",
            )
        )
        analyze_mock = MagicMock(
            return_value={
                "impact_level": "Medium",
                "summary": "Regulation updated",
            }
        )
        clean_mock = MagicMock(side_effect=lambda text: text.strip())
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=analyze_mock,
            clean_fn=clean_mock,
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "analyzed")
        self.assertIsNotNone(result["analysis_id"])
        crawl_mock.assert_called_once()
        clean_mock.assert_called_once_with("# New version with updates")
        analyze_mock.assert_called_once_with("# New version with updates")

        history = self.store.get_analysis_history("ec")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["analysis"]["impact_level"], "Medium")

    def test_disabled_sources_are_not_processed(self):
        crawl_mock = MagicMock(
            return_value=self._crawl_result()
        )
        pipeline = MonitoringPipeline(
            crawl_fn=crawl_mock,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            clean_content_fn=MagicMock(side_effect=lambda text: text),
            analyze_content_fn=MagicMock(),
            save_analysis_fn=self.store.save_analysis,
            load_sources_fn=lambda: [
                {
                    **self._monitor_config(),
                    "enabled": False,
                }
            ],
        )

        results = pipeline.run()

        crawl_mock.assert_not_called()
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
