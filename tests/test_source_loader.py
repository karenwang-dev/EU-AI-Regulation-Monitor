import json
import tempfile
import unittest
from pathlib import Path

from app.source.source_loader import (
    MonitorConfigError,
    load_monitors,
    load_sources,
    normalize_legacy_source,
    validate_monitor,
)


class TestSourceLoader(unittest.TestCase):

    def _valid_monitor(self) -> dict:
        return {
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
        with tempfile.TemporaryDirectory() as temp_dir:
            monitors_file = Path(temp_dir) / "monitors.json"
            monitors_file.write_text(
                json.dumps({"monitors": [self._valid_monitor()]}),
                encoding="utf-8",
            )

            monitors = load_monitors(
                monitors_file=monitors_file,
                sources_file=Path(temp_dir) / "missing-sources.json",
            )

            self.assertEqual(len(monitors), 1)
            self.assertEqual(monitors[0]["id"], "eu_ai_act")
            self.assertEqual(monitors[0]["keywords"], ["AI Act", "cybersecurity"])

    def test_load_monitors_falls_back_to_legacy_sources_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sources_file = Path(temp_dir) / "sources.json"
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

            monitors = load_monitors(
                monitors_file=Path(temp_dir) / "missing-monitors.json",
                sources_file=sources_file,
            )

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

    def test_project_monitors_json_loads_successfully(self):
        monitors = load_monitors()

        self.assertGreaterEqual(len(monitors), 6)
        self.assertTrue(all("keywords" in monitor for monitor in monitors))
        self.assertTrue(all("category" in monitor for monitor in monitors))

    def test_load_sources_is_alias_for_load_monitors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            monitors_file = Path(temp_dir) / "monitors.json"
            monitors_file.write_text(
                json.dumps({"monitors": [self._valid_monitor()]}),
                encoding="utf-8",
            )

            self.assertEqual(
                load_sources(
                    monitors_file=monitors_file,
                    sources_file=Path(temp_dir) / "missing-sources.json",
                ),
                load_monitors(
                    monitors_file=monitors_file,
                    sources_file=Path(temp_dir) / "missing-sources.json",
                ),
            )


if __name__ == "__main__":
    unittest.main()
