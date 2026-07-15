import gc
import tempfile
import unittest
from pathlib import Path

from app.analysis.diff_processor import compare_markdown, create_diff_result
from app.storage.service import StorageService


class TestDiffProcessor(unittest.TestCase):

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

    def _snapshot(
        self,
        markdown: str,
        timestamp: str,
        source_id: str = "ec",
    ) -> dict:
        return self.store.save_snapshot(
            {
                "source_id": source_id,
                "url": "https://example.com/ec",
                "title": "European Commission",
                "markdown": markdown,
                "timestamp": timestamp,
            }
        )

    def test_first_snapshot_returns_no_diff(self):
        new_snapshot = self._snapshot(
            markdown="# First version",
            timestamp="2026-07-15T10:00:00",
        )

        diff_result = create_diff_result("ec", None, new_snapshot)

        self.assertIsNone(diff_result)

    def test_unchanged_content_returns_no_diff(self):
        old_snapshot = self._snapshot(
            markdown="# Stable version",
            timestamp="2026-07-15T10:00:00",
        )
        new_snapshot = self._snapshot(
            markdown="# Stable version",
            timestamp="2026-07-15T12:00:00",
        )

        diff_result = create_diff_result("ec", old_snapshot, new_snapshot)

        self.assertIsNone(diff_result)

    def test_changed_content_creates_diff(self):
        old_snapshot = self._snapshot(
            markdown="# Old version",
            timestamp="2026-07-15T10:00:00",
        )
        new_snapshot = self._snapshot(
            markdown="# New version\nAdded regulation section",
            timestamp="2026-07-15T12:00:00",
        )

        diff_result = create_diff_result("ec", old_snapshot, new_snapshot)

        self.assertIsNotNone(diff_result)
        self.assertTrue(diff_result["changed"])
        self.assertEqual(diff_result["old_snapshot_id"], old_snapshot["id"])
        self.assertEqual(diff_result["new_snapshot_id"], new_snapshot["id"])
        self.assertIn("Added regulation section", diff_result["diff_text"])

    def test_diff_contains_added_content(self):
        comparison = compare_markdown(
            "# Old version",
            "# New version\nAdded regulation section",
        )

        self.assertTrue(comparison["changed"])
        self.assertIn("Added regulation section", comparison["added_content"])
        self.assertIn("# New version", comparison["added_content"])


if __name__ == "__main__":
    unittest.main()
