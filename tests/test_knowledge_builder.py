import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.analysis.diff_processor import create_diff_result
from app.ai.regulation_extractor import EXTRACTION_MODE_DIFF
from app.crawler.crawl_cache import should_crawl
from app.knowledge.builder import build_knowledge_item
from app.pipeline import MonitoringPipeline
from app.storage.service import StorageService


class TestKnowledgeBuilder(unittest.TestCase):

    def _snapshot(self) -> dict:
        return {
            "id": 42,
            "source_id": "eu_ai_act",
            "url": "https://example.com/ai-act",
            "title": "EU AI Act",
            "timestamp": "2026-07-15T12:00:00",
            "file_path": "data/raw/test.md",
            "hash": "abc123",
        }

    def _monitor(self) -> dict:
        return {
            "id": "eu_ai_act",
            "name": "EU AI Act",
            "category": "AI Regulation",
            "url": "https://example.com/ai-act",
            "keywords": ["AI Act"],
            "frequency": "daily",
            "enabled": True,
        }

    def _extraction(self) -> dict:
        return {
            "title": "EU AI Act Update",
            "summary": "New obligations for embedded AI systems.",
            "category": "",
            "regulation_type": "AMENDMENT",
            "effective_date": "2028-08-02",
            "affected_countries": ["EU"],
            "affected_products": ["Smart TV"],
            "affected_modules": ["AI Features", "Network"],
            "key_requirements": ["Assess embedded high-risk AI systems"],
            "actions_required": ["Update compliance checklist"],
            "is_regulation_content": True,
            "confidence": "HIGH",
        }

    def _analysis(self) -> dict:
        return {
            "impact_level": "HIGH",
            "affected_modules": ["Network"],
            "reason": "New obligations affect connected TVs.",
            "recommended_actions": ["Review product compliance plan"],
            "confidence": "HIGH",
            "regulation_extraction": self._extraction(),
        }

    def test_build_knowledge_item_success(self):
        item = build_knowledge_item(
            self._snapshot(),
            self._monitor(),
            self._analysis(),
        )

        self.assertIsNotNone(item)
        self.assertEqual(item["snapshot_id"], 42)
        self.assertEqual(item["source_id"], "eu_ai_act")
        self.assertEqual(item["title"], "EU AI Act Update")
        self.assertEqual(item["category"], "AI Regulation")
        self.assertEqual(item["regulation_type"], "AMENDMENT")
        self.assertEqual(item["summary"], "New obligations for embedded AI systems.")
        self.assertEqual(item["effective_date"], "2028-08-02")
        self.assertEqual(item["countries"], ["EU"])
        self.assertEqual(item["products"], ["Smart TV"])
        self.assertEqual(item["modules"], ["AI Features", "Network"])
        self.assertEqual(
            item["requirements"],
            ["Assess embedded high-risk AI systems"],
        )
        self.assertEqual(item["actions"], ["Update compliance checklist"])
        self.assertEqual(item["confidence"], "HIGH")

    def test_build_without_extraction_returns_none(self):
        analysis = {
            "impact_level": "HIGH",
            "reason": "Impact without extraction.",
        }

        item = build_knowledge_item(
            self._snapshot(),
            self._monitor(),
            analysis,
        )

        self.assertIsNone(item)


class TestKnowledgePipelineIntegration(unittest.TestCase):

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

    def _crawl_result(
        self,
        markdown: str,
        timestamp: str = "2026-07-15T12:00:00",
    ) -> dict:
        return {
            "source_id": "ec",
            "url": "https://example.com/ec",
            "title": "European Commission",
            "markdown": markdown,
            "timestamp": timestamp,
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
        save_knowledge_item_fn=None,
    ) -> MonitoringPipeline:
        return MonitoringPipeline(
            crawl_fn=crawl_fn,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            get_latest_snapshot_for_url_fn=self._get_latest_snapshot_for_url,
            create_diff_result_fn=create_diff_result,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=analyze_fn or MagicMock(
                return_value=self._impact_result()
            ),
            extract_regulation_fn=extract_regulation_fn or MagicMock(
                return_value=self._regulation_extraction_result()
            ),
            save_analysis_fn=self.store.save_analysis,
            save_knowledge_item_fn=(
                save_knowledge_item_fn or self.store.save_knowledge_item
            ),
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            should_crawl_fn=lambda url, frequency: should_crawl(
                url,
                frequency,
                get_cache_fn=self.store.get_crawl_cache,
            ),
            get_crawl_cache_fn=self.store.get_crawl_cache,
            update_crawl_cache_fn=self.store.update_crawl_cache,
            get_snapshot_by_id_fn=self.store.get_snapshot_by_id,
        )

    @patch("app.pipeline.build_knowledge_item", wraps=build_knowledge_item)
    def test_pipeline_changed_creates_knowledge_item(
        self,
        mock_build_knowledge_item,
    ):
        self.store.save_snapshot(
            self._crawl_result(
                markdown="# Old version",
                timestamp="2026-07-15T10:00:00",
            )
        )

        mock_save_knowledge_item = MagicMock(
            side_effect=lambda item: {
                "id": 5,
                **item,
            }
        )

        crawl_mock = MagicMock(
            return_value=self._crawl_result(
                markdown="# New version\nAdded regulation section",
            )
        )
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            save_knowledge_item_fn=mock_save_knowledge_item,
        )
        pipeline.build_knowledge_item_fn = mock_build_knowledge_item

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "analyzed")
        self.assertEqual(result["knowledge_id"], 5)
        mock_build_knowledge_item.assert_called_once()
        mock_save_knowledge_item.assert_called_once()

        saved_payload = mock_save_knowledge_item.call_args.args[0]
        self.assertEqual(saved_payload["title"], "EU Cybersecurity Regulation Update")
        self.assertEqual(saved_payload["modules"], ["Network", "Cybersecurity controls"])
        self.assertEqual(
            saved_payload["requirements"],
            ["Assess connected device security"],
        )
        self.assertEqual(saved_payload["actions"], ["Update compliance checklist"])

    @patch("app.pipeline.build_knowledge_item", wraps=build_knowledge_item)
    def test_pipeline_changed_persists_knowledge_item(self, _mock_build):
        self.store.save_snapshot(
            self._crawl_result(
                markdown="# Old version",
                timestamp="2026-07-15T10:00:00",
            )
        )

        crawl_mock = MagicMock(
            return_value=self._crawl_result(
                markdown="# New version\nAdded regulation section",
            )
        )
        pipeline = self._build_pipeline(crawl_fn=crawl_mock)

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "analyzed")
        self.assertIsNotNone(result["knowledge_id"])

        stored = self.store.get_knowledge_item(result["knowledge_id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["title"], "EU Cybersecurity Regulation Update")
        self.assertEqual(stored["source_id"], "ec")

    def test_pipeline_without_extraction_sets_knowledge_id_none(self):
        self.store.save_snapshot(
            self._crawl_result(
                markdown="# Old version",
                timestamp="2026-07-15T10:00:00",
            )
        )

        crawl_mock = MagicMock(
            return_value=self._crawl_result(
                markdown="# New version\nAdded regulation section",
            )
        )
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            extract_regulation_fn=MagicMock(return_value={}),
        )

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "analyzed")
        self.assertIsNone(result["knowledge_id"])
        self.assertEqual(len(self.store.get_knowledge_items()), 0)

    @patch("app.pipeline.build_knowledge_item", wraps=build_knowledge_item)
    def test_knowledge_failure_does_not_break_pipeline(self, _mock_build):
        self.store.save_snapshot(
            self._crawl_result(
                markdown="# Old version",
                timestamp="2026-07-15T10:00:00",
            )
        )

        crawl_mock = MagicMock(
            return_value=self._crawl_result(
                markdown="# New version\nAdded regulation section",
            )
        )
        pipeline = self._build_pipeline(
            crawl_fn=crawl_mock,
            save_knowledge_item_fn=MagicMock(
                side_effect=RuntimeError("knowledge save failed")
            ),
        )
        pipeline.build_knowledge_item_fn = build_knowledge_item

        result = pipeline.process_source(self._monitor_config())

        self.assertEqual(result["status"], "analyzed")
        self.assertIsNone(result["knowledge_id"])
        self.assertIsNotNone(result["analysis_id"])
        self.assertEqual(result["impact"]["impact_level"], "HIGH")
        self.assertEqual(len(self.store.get_analysis_history("ec")), 1)


if __name__ == "__main__":
    unittest.main()
