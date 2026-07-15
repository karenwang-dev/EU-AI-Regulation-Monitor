import gc
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.storage.service import StorageService, calculate_hash


class TestStorageService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        self.base_path = Path(self.temp_dir.name)
        self.raw_dir = self.base_path / "raw"
        self.meta_file = self.base_path / "metadata" / "snapshots.json"
        self.db_path = self.base_path / "storage.db"
        self.store = StorageService(
            db_path=self.db_path,
            raw_dir=self.raw_dir,
            meta_file=self.meta_file,
        )

    def tearDown(self):
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _crawl_result(
        self,
        source_id: str = "eu_ai_act",
        markdown: str = "# EU AI Act\n\nUpdated content.",
        timestamp: str = "2026-07-15T10:30:00",
    ) -> dict:
        return {
            "source_id": source_id,
            "url": "https://example.com/ai-act",
            "title": "EU AI Act Policy Page",
            "markdown": markdown,
            "timestamp": timestamp,
        }

    def test_save_snapshot_writes_markdown_sqlite_and_legacy_metadata(self):
        snapshot = self.store.save_snapshot(self._crawl_result())

        markdown_file = Path(snapshot["file_path"])
        self.assertTrue(markdown_file.exists())
        self.assertEqual(
            markdown_file.read_text(encoding="utf-8"),
            "# EU AI Act\n\nUpdated content.",
        )
        self.assertEqual(snapshot["source_id"], "eu_ai_act")
        self.assertEqual(
            snapshot["hash"],
            calculate_hash("# EU AI Act\n\nUpdated content."),
        )

        latest = self.store.get_latest_snapshot("eu_ai_act")
        self.assertEqual(latest["id"], snapshot["id"])
        self.assertEqual(latest["title"], "EU AI Act Policy Page")

        with open(self.meta_file, "r", encoding="utf-8") as file:
            legacy_records = json.load(file)

        self.assertEqual(len(legacy_records), 1)
        self.assertEqual(legacy_records[0]["source_id"], "eu_ai_act")
        self.assertEqual(legacy_records[0]["hash"], snapshot["hash"])

    def test_get_latest_snapshot_returns_most_recent_record(self):
        self.store.save_snapshot(
            self._crawl_result(
                markdown="Version 1",
                timestamp="2026-07-15T09:00:00",
            )
        )
        self.store.save_snapshot(
            self._crawl_result(
                markdown="Version 2",
                timestamp="2026-07-15T11:00:00",
            )
        )

        latest = self.store.get_latest_snapshot("eu_ai_act")

        self.assertEqual(latest["timestamp"], "2026-07-15T11:00:00")
        self.assertEqual(
            Path(latest["file_path"]).read_text(encoding="utf-8"),
            "Version 2",
        )

    def test_save_analysis_and_get_analysis_history(self):
        snapshot = self.store.save_snapshot(self._crawl_result())
        analysis = {
            "website": "https://example.com/ai-act",
            "title": "EU AI Act Policy Page",
            "impact_level": "High",
            "affected_modules": ["AI Features", "Network"],
        }

        saved = self.store.save_analysis(snapshot["id"], analysis)
        history = self.store.get_analysis_history("eu_ai_act")

        self.assertEqual(saved["snapshot_id"], snapshot["id"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["analysis"]["impact_level"], "High")
        self.assertEqual(
            history[0]["snapshot_timestamp"],
            snapshot["timestamp"],
        )

    def test_import_legacy_snapshots_on_first_init(self):
        legacy_file = self.base_path / "legacy" / "snapshots.json"
        legacy_file.parent.mkdir(parents=True)
        legacy_file.write_text(
            json.dumps(
                [
                    {
                        "source_id": "ec",
                        "url": "https://commission.europa.eu/index_en",
                        "timestamp": "2026-07-10T17:23:15.654417",
                        "file": str(self.raw_dir / "2026-07-10" / "ec_172315.md"),
                        "hash": "abc123",
                    }
                ]
            ),
            encoding="utf-8",
        )

        imported_store = StorageService(
            db_path=self.base_path / "legacy.db",
            raw_dir=self.raw_dir,
            meta_file=legacy_file,
        )

        latest = imported_store.get_latest_snapshot("ec")

        self.assertIsNotNone(latest)
        self.assertEqual(latest["source_id"], "ec")
        self.assertEqual(latest["hash"], "abc123")
        self.assertEqual(latest["file_path"], str(self.raw_dir / "2026-07-10" / "ec_172315.md"))

    @patch("app.storage.service._default_service", None)
    def test_module_level_functions_use_default_service(self):
        temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(temp_dir.name)
        patched_store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

        try:
            with patch(
                "app.storage.service._get_service",
                return_value=patched_store,
            ):
                from app.storage.service import (
                    get_analysis_history,
                    get_latest_snapshot,
                    save_analysis,
                    save_snapshot,
                )

                snapshot = save_snapshot(self._crawl_result())
                self.assertEqual(snapshot["source_id"], "eu_ai_act")
                self.assertEqual(
                    get_latest_snapshot("eu_ai_act")["id"],
                    snapshot["id"],
                )

                save_analysis(
                    snapshot["id"],
                    {"impact_level": "Medium", "summary": "Test"},
                )
                history = get_analysis_history("eu_ai_act")
                self.assertEqual(len(history), 1)
        finally:
            patched_store = None
            gc.collect()
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
