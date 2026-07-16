import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.pipeline import MonitoringPipeline, normalize_source
from app.analysis.diff_processor import create_diff_result
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

    def _build_pipeline(
        self,
        crawl_fn,
        analyze_fn=None,
    ) -> MonitoringPipeline:
        analyze_fn = analyze_fn or MagicMock(
            return_value=self._impact_result()
        )

        return MonitoringPipeline(
            crawl_fn=crawl_fn,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            create_diff_result_fn=create_diff_result,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=analyze_fn,
            save_analysis_fn=self.store.save_analysis,
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            load_sources_fn=lambda: [self._monitor_config()],
        )

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
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=analyze_mock,
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "first_snapshot")
        self.assertTrue(result["first_snapshot"])
        self.assertIsNone(result["diff_id"])
        self.assertIsNone(result["analysis_id"])
        analyze_mock.assert_not_called()
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
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=analyze_mock,
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "skipped")
        self.assertIsNone(result["diff_id"])
        self.assertIsNone(result["analysis_id"])
        analyze_mock.assert_not_called()
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
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            analyze_fn=analyze_mock,
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "analyzed")
        self.assertIsNotNone(result["diff_id"])
        self.assertIsNotNone(result["analysis_id"])
        self.assertEqual(result["impact"]["impact_level"], "HIGH")

        analyze_mock.assert_called_once()
        diff_arg, monitor_arg = analyze_mock.call_args.args
        self.assertIn("Added regulation section", diff_arg["added_content"])
        self.assertEqual(monitor_arg["id"], "ec")

        history = self.store.get_analysis_history("ec")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["analysis"]["impact_level"], "HIGH")
        self.assertIn("Network", history[0]["analysis"]["affected_modules"])

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

    def test_disabled_sources_are_not_processed(self):
        crawl_mock = MagicMock(
            return_value=self._crawl_result()
        )
        analyze_mock = MagicMock()
        pipeline = MonitoringPipeline(
            crawl_fn=crawl_mock,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=analyze_mock,
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
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
