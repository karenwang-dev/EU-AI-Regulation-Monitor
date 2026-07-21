import gc
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.storage.service import StorageService
from app.web.app import create_dashboard_app
from app.web.monitor_api import MonitorStore, generate_monitor_id


class TestMonitorApi(unittest.TestCase):

    def setUp(self):
        reset_monitor_repository()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.db_path = base_path / "storage.db"
        self.monitors_file = base_path / "monitors.json"
        self.monitors_file.write_text(
            json.dumps(
                {
                    "monitors": [
                        {
                            "id": "eu_ai_act",
                            "name": "EU AI Act",
                            "url": "https://example.com/ai-act",
                            "keywords": ["AI Act", "cybersecurity"],
                            "category": "AI Regulation",
                            "frequency": "daily",
                            "enabled": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.storage = StorageService(
            db_path=self.db_path,
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.repository = MonitorRepository(
            db_path=self.db_path,
            seed_file=self.monitors_file,
        )
        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
            )
        )

    def tearDown(self):
        self.client = None
        self.repository = None
        self.storage = None
        reset_monitor_repository()
        gc.collect()
        self.temp_dir.cleanup()

    def test_get_monitors(self):
        response = self.client.get("/api/monitors")

        self.assertEqual(response.status_code, 200)
        monitors = response.json()
        self.assertEqual(len(monitors), 1)
        self.assertEqual(monitors[0]["id"], "eu_ai_act")
        self.assertEqual(monitors[0]["crawl_mode"], "single")
        self.assertEqual(monitors[0]["max_depth"], 0)
        self.assertEqual(monitors[0]["max_pages"], 1)

    def test_create_monitor_with_smart_crawl_config(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "Smart Regulation",
                "url": "https://example.com/smart-regulation",
                "keywords": ["smart TV"],
                "category": "Product Compliance",
                "frequency": "weekly",
                "enabled": True,
                "crawl_mode": "smart",
                "max_depth": 2,
                "max_pages": 10,
            },
        )

        self.assertEqual(response.status_code, 201)
        created = response.json()
        self.assertEqual(created["crawl_mode"], "smart")
        self.assertEqual(created["max_depth"], 2)
        self.assertEqual(created["max_pages"], 10)

    def test_create_monitor(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "New Regulation",
                "url": "https://example.com/new-regulation",
                "keywords": ["smart TV", "cybersecurity"],
                "category": "Product Compliance",
                "frequency": "weekly",
                "enabled": True,
            },
        )

        self.assertEqual(response.status_code, 201)
        created = response.json()
        self.assertEqual(created["id"], "new_regulation")
        self.assertEqual(created["name"], "New Regulation")

        self.assertEqual(len(self.repository.list_monitors()), 2)

    def test_update_monitor(self):
        response = self.client.put(
            "/api/monitors/eu_ai_act",
            json={
                "name": "EU AI Act Updated",
                "frequency": "weekly",
                "enabled": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        updated = response.json()
        self.assertEqual(updated["name"], "EU AI Act Updated")
        self.assertEqual(updated["frequency"], "weekly")
        self.assertFalse(updated["enabled"])

    def test_delete_monitor(self):
        response = self.client.delete("/api/monitors/eu_ai_act")

        self.assertEqual(response.status_code, 200)
        self.assertIn("removed", response.json()["message"])

        self.assertEqual(self.repository.list_monitors(), [])

    def test_invalid_url_rejected(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "Bad URL Monitor",
                "url": "ftp://example.com",
                "keywords": ["smart TV"],
                "category": "Other",
                "frequency": "daily",
                "enabled": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("url must start with http:// or https://", response.json()["detail"])

    def test_invalid_frequency_rejected(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "Bad Frequency Monitor",
                "url": "https://example.com/bad-frequency",
                "keywords": ["smart TV"],
                "category": "Other",
                "frequency": "hourly",
                "enabled": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("frequency must be one of", response.json()["detail"])

    def test_invalid_crawl_mode_rejected(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "Bad Crawl Monitor",
                "url": "https://example.com/bad-crawl",
                "keywords": ["smart TV"],
                "category": "Other",
                "frequency": "daily",
                "enabled": True,
                "crawl_mode": "deep",
                "max_depth": 1,
                "max_pages": 5,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("crawl_mode must be one of", response.json()["detail"])

    def test_invalid_max_depth_rejected(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "Bad Depth Monitor",
                "url": "https://example.com/bad-depth",
                "keywords": ["smart TV"],
                "category": "Other",
                "frequency": "daily",
                "enabled": True,
                "crawl_mode": "single",
                "max_depth": -1,
                "max_pages": 5,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("max_depth must be >= 0", response.json()["detail"])

    def test_invalid_max_pages_rejected(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "Bad Pages Monitor",
                "url": "https://example.com/bad-pages",
                "keywords": ["smart TV"],
                "category": "Other",
                "frequency": "daily",
                "enabled": True,
                "crawl_mode": "single",
                "max_depth": 0,
                "max_pages": 0,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("max_pages must be > 0", response.json()["detail"])

    def test_monitors_page_renders_management_ui(self):
        response = self.client.get("/monitors")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Monitors", response.content)
        self.assertIn(b"+ Add Monitor", response.content)
        self.assertIn(b"Last Run", response.content)
        self.assertIn(b"run-monitor-btn", response.content)
        self.assertIn(b"Crawl Mode", response.content)
        self.assertIn(b"Max Depth", response.content)
        self.assertIn(b"Max Pages", response.content)
        self.assertIn(b"Smart Discovery", response.content)
        self.assertIn(b"Total Monitors", response.content)
        self.assertIn(b"Enabled", response.content)
        self.assertIn(b"Disabled", response.content)
        self.assertIn(b"Recent Updates", response.content)
        self.assertIn(b'href="/monitors"', response.content)
        self.assertNotIn(b"Manage Monitors", response.content)

    def test_manage_monitors_redirects_to_monitors(self):
        response = self.client.get("/manage-monitors", follow_redirects=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["location"], "/monitors")

    def test_generate_monitor_id_avoids_duplicates(self):
        store = MonitorStore(repository=self.repository)
        first = generate_monitor_id("EU AI Act", {"eu_ai_act"})
        second = generate_monitor_id("EU AI Act", {"eu_ai_act", first})

        self.assertEqual(first, "eu_ai_act_2")
        self.assertEqual(second, "eu_ai_act_3")


if __name__ == "__main__":
    unittest.main()
