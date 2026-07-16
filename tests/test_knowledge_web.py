import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class TestKnowledgeWeb(unittest.TestCase):

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

        snapshot = self.store.save_snapshot(
            {
                "source_id": "eu_ai_act",
                "url": "https://example.com/ai-act",
                "title": "EU AI Act",
                "markdown": "# EU AI Act content",
                "timestamp": "2026-07-15T12:00:00",
            }
        )
        self.snapshot_id = snapshot["id"]

        self.store.save_diff(
            {
                "source_id": "eu_ai_act",
                "old_snapshot_id": None,
                "new_snapshot_id": self.snapshot_id,
                "changed": True,
                "added_content": ["Added AI Act section"],
                "removed_content": [],
                "diff_text": "+Added AI Act section",
            }
        )

        saved = self.store.save_knowledge_item(
            {
                "snapshot_id": self.snapshot_id,
                "source_id": "eu_ai_act",
                "title": "EU AI Act Cybersecurity Update",
                "category": "AI Regulation",
                "regulation_type": "AMENDMENT",
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
        self.knowledge_id = saved["id"]

        self.store.save_knowledge_item(
            {
                "snapshot_id": self.snapshot_id,
                "source_id": "eu_red",
                "title": "RED Directive Update",
                "category": "Product Compliance",
                "regulation_type": "NEW",
                "summary": "Radio equipment requirements.",
                "effective_date": "2027-01-01",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Radio equipment"],
                "requirements": ["Review RED documentation"],
                "actions": ["Schedule compliance review"],
                "confidence": "MEDIUM",
            }
        )

        self.client = TestClient(
            create_dashboard_app(storage_service=self.store)
        )

        self.monitor = {
            "id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/ai-act",
            "keywords": ["AI Act", "cybersecurity"],
            "category": "AI Regulation",
            "frequency": "daily",
            "enabled": True,
        }

    def tearDown(self):
        self.client = None
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_knowledge_page_returns_200(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/knowledge")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Knowledge Base", content)
        self.assertIn(b"EU AI Act Cybersecurity Update", content)
        self.assertIn(b"Search Knowledge", content)
        self.assertIn(b"AI Regulation", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_knowledge_detail_page_returns_200(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get(f"/knowledge/{self.knowledge_id}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"EU AI Act Cybersecurity Update", content)
        self.assertIn(b"Cybersecurity obligations for connected devices.", content)
        self.assertIn(b"Affected Countries", content)
        self.assertIn(b"Key Requirements", content)
        self.assertIn(b"Open Original Page", content)
        self.assertIn(b"https://example.com/ai-act", content)
        self.assertIn(str(self.snapshot_id).encode(), content)

    def test_search_knowledge_api(self):
        response = self.client.get("/api/knowledge/search?q=cybersecurity")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "EU AI Act Cybersecurity Update")
        self.assertIn("Network", data[0]["modules"])

    def test_knowledge_filter_api(self):
        category_response = self.client.get(
            "/api/knowledge?category=AI Regulation"
        )
        self.assertEqual(category_response.status_code, 200)
        category_data = category_response.json()
        self.assertEqual(len(category_data), 1)
        self.assertEqual(category_data[0]["category"], "AI Regulation")

        module_response = self.client.get("/api/knowledge?module=Network")
        self.assertEqual(module_response.status_code, 200)
        module_data = module_response.json()
        self.assertEqual(len(module_data), 1)
        self.assertIn("Network", module_data[0]["modules"])

    def test_missing_knowledge_item_returns_404(self):
        page_response = self.client.get("/knowledge/99999")
        self.assertEqual(page_response.status_code, 404)

        api_response = self.client.get("/api/knowledge/99999")
        self.assertEqual(api_response.status_code, 404)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_navigation_contains_knowledge(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/knowledge")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Knowledge Base", content)
        self.assertIn(b'href="/knowledge"', content)
        self.assertIn(b"nav-link active", content)


if __name__ == "__main__":
    unittest.main()
