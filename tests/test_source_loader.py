import gc
import json
import tempfile
import unittest
from pathlib import Path

from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.source.source_loader import (
    MonitorConfigError,
    load_monitors,
    load_sources,
    normalize_legacy_source,
    validate_monitor,
)


class TestSourceLoader(unittest.TestCase):

    def tearDown(self):
        reset_monitor_repository()
        gc.collect()

    def _valid_monitor(self) -> dict:        return {
            "id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/ai-act",
            "keywords": ["AI Act", "cybersecurity"],
            "category": "AI Regulation",
            "frequency": "daily",
            "enabled": True,
        }

    def test_validate_monitor_accepts_valid_config(self):
        validate_monitor(self._valid_monitor())

    def test_validate_monitor_requires_url(self):
        monitor = self._valid_monitor()
        monitor["url"] = ""

        with self.assertRaises(MonitorConfigError) as error:
            validate_monitor(monitor)

        self.assertIn("url is required", str(error.exception))

    def test_validate_monitor_requires_keywords(self):
        monitor = self._valid_monitor()
        monitor["keywords"] = []

        with self.assertRaises(MonitorConfigError) as error:
            validate_monitor(monitor)

        self.assertIn("keywords must be a non-empty list", str(error.exception))

    def test_validate_monitor_requires_allowed_frequency(self):
        monitor = self._valid_monitor()
        monitor["frequency"] = "hourly"

        with self.assertRaises(MonitorConfigError) as error:
            validate_monitor(monitor)

        self.assertIn("frequency must be one of", str(error.exception))

    def test_load_monitors_from_monitors_json(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            monitors_file = Path(temp_dir) / "monitors.json"
            db_path = Path(temp_dir) / "storage.db"
            monitors_file.write_text(
                json.dumps({"monitors": [self._valid_monitor()]}),
                encoding="utf-8",
            )

            repository = MonitorRepository(
                db_path=db_path,
                seed_file=monitors_file,
            )
            monitors = load_monitors(repository=repository)
            reset_monitor_repository()
            gc.collect()

            self.assertEqual(len(monitors), 1)
            self.assertEqual(monitors[0]["id"], "eu_ai_act")
            self.assertEqual(monitors[0]["keywords"], ["AI Act", "cybersecurity"])

    def test_load_monitors_falls_back_to_legacy_sources_json(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            sources_file = Path(temp_dir) / "sources.json"
            db_path = Path(temp_dir) / "storage.db"
            sources_file.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "id": "ec",
                                "name": "European Commission",
                                "enabled": True,
                                "type": "regulation_policy",
                                "region": "EU",
                                "language": "en",
                                "priority": "high",
                                "crawl_interval": "daily",
                                "url": "https://example.com/ec",
                                "tags": ["EU Regulation", "Smart TV"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            repository = MonitorRepository(
                db_path=db_path,
                seed_file=Path(temp_dir) / "missing-monitors.json",
                sources_file=sources_file,
            )
            monitors = load_monitors(repository=repository)
            reset_monitor_repository()
            gc.collect()

            self.assertEqual(len(monitors), 1)
            self.assertEqual(monitors[0]["keywords"], ["EU Regulation", "Smart TV"])
            self.assertEqual(monitors[0]["category"], "regulation_policy")
            self.assertEqual(monitors[0]["frequency"], "daily")
            self.assertNotIn("region", monitors[0])
            self.assertNotIn("tags", monitors[0])

    def test_normalize_legacy_source_maps_old_fields(self):
        legacy = {
            "id": "boe",
            "name": "BOE",
            "enabled": True,
            "type": "national_regulation",
            "crawl_interval": "weekly",
            "url": "https://www.boe.es/",
            "tags": ["Spain Regulation"],
        }

        monitor = normalize_legacy_source(legacy)

        self.assertEqual(monitor["keywords"], ["Spain Regulation"])
        self.assertEqual(monitor["category"], "national_regulation")
        self.assertEqual(monitor["frequency"], "weekly")
        self.assertEqual(monitor["crawl_mode"], "single")
        self.assertEqual(monitor["max_depth"], 0)
        self.assertEqual(monitor["max_pages"], 1)

    def test_normalize_legacy_source_applies_crawl_defaults(self):
        legacy = self._valid_monitor()
        monitor = normalize_legacy_source(legacy)

        self.assertEqual(monitor["crawl_mode"], "single")
        self.assertEqual(monitor["max_depth"], 0)
        self.assertEqual(monitor["max_pages"], 1)

    def test_validate_monitor_accepts_smart_crawl_config(self):
        monitor = self._valid_monitor()
        monitor["crawl_mode"] = "smart"
        monitor["max_depth"] = 2
        monitor["max_pages"] = 10
        validate_monitor(monitor)

    def test_validate_monitor_rejects_invalid_crawl_mode(self):
        monitor = self._valid_monitor()
        monitor["crawl_mode"] = "deep"

        with self.assertRaises(MonitorConfigError) as error:
            validate_monitor(monitor)

        self.assertIn("crawl_mode must be one of", str(error.exception))

    def test_validate_monitor_rejects_negative_max_depth(self):
        monitor = self._valid_monitor()
        monitor["max_depth"] = -1

        with self.assertRaises(MonitorConfigError) as error:
            validate_monitor(monitor)

        self.assertIn("max_depth must be >= 0", str(error.exception))

    def test_validate_monitor_rejects_invalid_max_pages(self):
        monitor = self._valid_monitor()
        monitor["max_pages"] = 0

        with self.assertRaises(MonitorConfigError) as error:
            validate_monitor(monitor)

        self.assertIn("max_pages must be > 0", str(error.exception))

    def test_load_monitors_applies_defaults_for_legacy_monitor(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            monitors_file = Path(temp_dir) / "monitors.json"
            db_path = Path(temp_dir) / "storage.db"
            monitors_file.write_text(
                json.dumps({"monitors": [self._valid_monitor()]}),
                encoding="utf-8",
            )

            repository = MonitorRepository(
                db_path=db_path,
                seed_file=monitors_file,
            )
            monitors = load_monitors(repository=repository)
            reset_monitor_repository()
            gc.collect()

            self.assertEqual(monitors[0]["crawl_mode"], "single")
            self.assertEqual(monitors[0]["max_depth"], 0)
            self.assertEqual(monitors[0]["max_pages"], 1)

    def test_project_monitors_json_loads_successfully(self):
        monitors = load_monitors()

        self.assertGreaterEqual(len(monitors), 6)
        self.assertTrue(all("keywords" in monitor for monitor in monitors))
        self.assertTrue(all("category" in monitor for monitor in monitors))
        self.assertTrue(all(monitor["crawl_mode"] in {"single", "smart", "multi_page"} for monitor in monitors))
        self.assertTrue(all(isinstance(monitor["max_depth"], int) for monitor in monitors))
        self.assertTrue(all(isinstance(monitor["max_pages"], int) for monitor in monitors))

        eu_ai_act = next(monitor for monitor in monitors if monitor["id"] == "eu_ai_act")
        self.assertEqual(eu_ai_act["crawl_mode"], "smart")
        self.assertEqual(eu_ai_act["max_depth"], 3)
        self.assertEqual(eu_ai_act["max_pages"], 10)

    def test_load_sources_is_alias_for_load_monitors(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            monitors_file = Path(temp_dir) / "monitors.json"
            db_path = Path(temp_dir) / "storage.db"
            monitors_file.write_text(
                json.dumps({"monitors": [self._valid_monitor()]}),
                encoding="utf-8",
            )

            repository = MonitorRepository(
                db_path=db_path,
                seed_file=monitors_file,
            )
            self.assertEqual(
                load_sources(repository=repository),
                load_monitors(repository=repository),
            )
            reset_monitor_repository()
            gc.collect()


if __name__ == "__main__":
    unittest.main()
