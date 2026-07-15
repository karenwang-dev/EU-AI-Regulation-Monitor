import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.web.app import create_dashboard_app
from app.web.monitor_api import MonitorStore, generate_monitor_id


class TestMonitorApi(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.monitors_file = Path(self.temp_dir.name) / "monitors.json"
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
        self.client = TestClient(
            create_dashboard_app(monitors_file=self.monitors_file)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_monitors(self):
        response = self.client.get("/api/monitors")

        self.assertEqual(response.status_code, 200)
        monitors = response.json()
        self.assertEqual(len(monitors), 1)
        self.assertEqual(monitors[0]["id"], "eu_ai_act")

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

        saved = json.loads(self.monitors_file.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["monitors"]), 2)

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

        remaining = json.loads(self.monitors_file.read_text(encoding="utf-8"))
        self.assertEqual(remaining["monitors"], [])

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

    def test_generate_monitor_id_avoids_duplicates(self):
        store = MonitorStore(monitors_file=self.monitors_file)
        first = generate_monitor_id("EU AI Act", {"eu_ai_act"})
        second = generate_monitor_id("EU AI Act", {"eu_ai_act", first})

        self.assertEqual(first, "eu_ai_act_2")
        self.assertEqual(second, "eu_ai_act_3")


if __name__ == "__main__":
    unittest.main()
