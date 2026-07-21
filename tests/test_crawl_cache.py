import gc
import tempfile
import unittest
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from unittest.mock import MagicMock

from app.crawler.crawl_cache import FREQUENCY_TTL_DAYS, should_crawl
from app.pipeline import MonitoringPipeline
from app.analysis.diff_processor import create_diff_result
from app.storage.service import StorageService


class TestCrawlCacheStorage(unittest.TestCase):

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

    def test_get_crawl_cache_returns_none_for_new_url(self):
        self.assertIsNone(
            self.store.get_crawl_cache("https://example.com/new-page")
        )

    def test_update_and_get_crawl_cache(self):
        snapshot = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": "https://example.com/ec",
                "title": "European Commission",
                "markdown": "# Cached page",
                "timestamp": "2026-07-15T12:00:00",
            }
        )

        cache_entry = self.store.update_crawl_cache(
            "https://example.com/ec",
            snapshot["id"],
            snapshot["hash"],
        )

        loaded = self.store.get_crawl_cache("https://example.com/ec")

        self.assertEqual(cache_entry["url"], "https://example.com/ec")
        self.assertEqual(loaded["last_snapshot_id"], snapshot["id"])
        self.assertEqual(loaded["last_hash"], snapshot["hash"])
        self.assertIsNotNone(loaded["last_crawled_at"])


class TestShouldCrawl(unittest.TestCase):

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
        self.url = "https://example.com/ec"
        self.snapshot = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": self.url,
                "title": "European Commission",
                "markdown": "# Cached page",
                "timestamp": "2026-07-15T12:00:00",
            }
        )

    def tearDown(self):
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _should_crawl(self, frequency: str, now: datetime) -> bool:
        return should_crawl(
            self.url,
            frequency,
            get_cache_fn=self.store.get_crawl_cache,
            now=now,
        )

    def test_new_url_requires_crawl(self):
        self.assertTrue(
            should_crawl(
                "https://example.com/uncached",
                "daily",
                get_cache_fn=self.store.get_crawl_cache,
            )
        )

    def test_cache_hit_within_ttl(self):
        self.store.update_crawl_cache(
            self.url,
            self.snapshot["id"],
            self.snapshot["hash"],
        )
        now = datetime.now()

        self.assertFalse(self._should_crawl("daily", now))

    def test_expired_cache_requires_crawl(self):
        crawled_at = datetime.now() - timedelta(days=2)
        with self.store._connect() as connection:
            connection.execute(
                """
                INSERT INTO crawl_cache (
                    url,
                    last_snapshot_id,
                    last_hash,
                    last_crawled_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.url,
                    self.snapshot["id"],
                    self.snapshot["hash"],
                    crawled_at.isoformat(),
                    crawled_at.isoformat(),
                ),
            )

        self.assertTrue(self._should_crawl("daily", datetime.now()))

    def test_frequency_ttl_values(self):
        self.assertEqual(FREQUENCY_TTL_DAYS["daily"], 1)
        self.assertEqual(FREQUENCY_TTL_DAYS["weekly"], 7)
        self.assertEqual(FREQUENCY_TTL_DAYS["biweekly"], 14)
        self.assertEqual(FREQUENCY_TTL_DAYS["monthly"], 30)

    def test_weekly_cache_valid_before_seven_days(self):
        crawled_at = datetime.now() - timedelta(days=6)
        with self.store._connect() as connection:
            connection.execute(
                """
                INSERT INTO crawl_cache (
                    url,
                    last_snapshot_id,
                    last_hash,
                    last_crawled_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.url,
                    self.snapshot["id"],
                    self.snapshot["hash"],
                    crawled_at.isoformat(),
                    crawled_at.isoformat(),
                ),
            )

        self.assertFalse(self._should_crawl("weekly", datetime.now()))


class TestPipelineCrawlCache(unittest.TestCase):

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
            "keywords": ["EU Regulation"],
            "category": "EU Policy",
            "frequency": "daily",
            "crawl_mode": "single",
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

    def _build_pipeline(self, crawl_fn) -> MonitoringPipeline:
        return MonitoringPipeline(
            crawl_fn=crawl_fn,
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_fn=self.store.get_latest_snapshot,
            get_latest_snapshot_for_url_fn=self._get_latest_snapshot_for_url,
            create_diff_result_fn=create_diff_result,
            save_diff_fn=self.store.save_diff,
            analyze_change_impact_fn=MagicMock(),
            save_analysis_fn=self.store.save_analysis,
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            load_sources_fn=lambda: [self._monitor_config()],
            should_crawl_fn=partial(
                should_crawl,
                get_cache_fn=self.store.get_crawl_cache,
            ),
            get_crawl_cache_fn=self.store.get_crawl_cache,
            update_crawl_cache_fn=self.store.update_crawl_cache,
            get_snapshot_by_id_fn=self.store.get_snapshot_by_id,
            get_distinct_monitor_urls_fn=self.store.get_distinct_monitor_urls,
        )

    def test_pipeline_cache_hit_does_not_call_crawler(self):
        snapshot = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": "https://example.com/ec",
                "title": "European Commission",
                "markdown": "# Cached content",
                "timestamp": "2026-07-15T10:00:00",
            }
        )
        self.store.update_crawl_cache(
            "https://example.com/ec",
            snapshot["id"],
            snapshot["hash"],
        )

        crawl_mock = MagicMock()
        pipeline = self._build_pipeline(crawl_fn=crawl_mock)

        result = pipeline.process_source(self._monitor_config())

        crawl_mock.assert_not_called()
        self.assertTrue(result.get("cache_hit"))
        self.assertEqual(result["status"], "skipped")
        self.assertIn("Crawl cache hit", result["message"])

    def test_pipeline_crawls_and_updates_cache_for_new_url(self):
        crawl_mock = MagicMock(
            return_value={
                "source_id": "ec",
                "url": "https://example.com/ec",
                "title": "European Commission",
                "markdown": "# Fresh crawl",
                "timestamp": "2026-07-15T12:00:00",
            }
        )
        pipeline = self._build_pipeline(crawl_fn=crawl_mock)

        result = pipeline.process_source(self._monitor_config())

        crawl_mock.assert_called_once()
        self.assertFalse(result.get("cache_hit"))
        cache_entry = self.store.get_crawl_cache("https://example.com/ec")
        self.assertIsNotNone(cache_entry)
        self.assertEqual(cache_entry["last_snapshot_id"], result["snapshot_id"])


if __name__ == "__main__":
    unittest.main()
