import gc
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class TestSearchApi(unittest.TestCase):

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

        self.cyber_item = self.store.save_knowledge_item(
            {
                "snapshot_id": 1,
                "source_id": "eu_ai_act",
                "title": "EU AI Act Cybersecurity Framework",
                "category": "AI Regulation",
                "regulation_type": "NEW",
                "summary": "Cybersecurity obligations for connected devices.",
                "effective_date": "2028-08-02",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Network", "AI Features"],
                "requirements": ["Assess cybersecurity controls"],
                "actions": ["Update compliance checklist"],
                "confidence": "HIGH",
            }
        )

        self.network_item = self.store.save_knowledge_item(
            {
                "snapshot_id": 2,
                "source_id": "eu_network",
                "title": "Network Compliance Guide",
                "category": "Product Compliance",
                "regulation_type": "GUIDANCE",
                "summary": "Network connectivity guidance.",
                "effective_date": "2027-06-01",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Network"],
                "requirements": ["Assess network stack"],
                "actions": ["Validate firmware"],
                "confidence": "LOW",
            }
        )

        self.client = TestClient(
            create_dashboard_app(storage_service=self.store)
        )

    def tearDown(self):
        self.client = None
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def test_search_api(self):
        response = self.client.get("/api/search?q=cybersecurity")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.cyber_item["id"])
        self.assertGreaterEqual(data[0]["score"], 100)
        self.assertIn("title", data[0]["matched_fields"])

    def test_empty_query(self):
        missing_query = self.client.get("/api/search")
        empty_query = self.client.get("/api/search?q=")

        self.assertEqual(missing_query.status_code, 200)
        self.assertEqual(empty_query.status_code, 200)
        self.assertEqual(len(missing_query.json()), 2)
        self.assertEqual(len(empty_query.json()), 2)
        self.assertEqual(missing_query.json()[0]["score"], 5)

    def test_category_filter(self):
        response = self.client.get(
            "/api/search?q=Network&category=Product Compliance"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.network_item["id"])
        self.assertEqual(data[0]["category"], "Product Compliance")

    def test_module_filter(self):
        response = self.client.get(
            "/api/search?q=Network&module=Network"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data), 1)
        ids = {item["id"] for item in data}
        self.assertIn(self.network_item["id"], ids)

    def test_limit(self):
        response = self.client.get("/api/search?limit=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_suggest(self):
        response = self.client.get("/api/search/suggest?q=cyber")

        self.assertEqual(response.status_code, 200)
        suggestions = response.json()
        self.assertLessEqual(len(suggestions), 10)
        self.assertEqual(suggestions, sorted(suggestions, key=str.lower))
        self.assertTrue(
            any("Cybersecurity" in suggestion for suggestion in suggestions)
        )

    def test_statistics(self):
        response = self.client.get("/api/search/statistics")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_items"], 2)
        self.assertEqual(
            data["searchable_fields"],
            [
                "title",
                "summary",
                "requirements",
                "actions",
                "modules",
                "category",
            ],
        )


if __name__ == "__main__":
    unittest.main()
