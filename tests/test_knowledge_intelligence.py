import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.knowledge.similarity import find_similar_knowledge
from app.knowledge.statistics import build_knowledge_statistics
from app.knowledge.timeline import build_regulation_timeline
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class TestKnowledgeIntelligence(unittest.TestCase):

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

        self.primary = self.store.save_knowledge_item(
            {
                "snapshot_id": snapshot["id"],
                "source_id": "eu_ai_act",
                "title": "EU AI Act Cybersecurity Update",
                "category": "AI Regulation",
                "regulation_type": "NEW",
                "summary": "Cybersecurity obligations for connected devices.",
                "effective_date": "2026-07-01",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Network", "AI Features"],
                "requirements": ["Assess cybersecurity controls for devices"],
                "actions": ["Update compliance checklist"],
                "confidence": "HIGH",
            }
        )
        self.primary["created_at"] = "2026-01-01T10:00:00"

        self.similar = self.store.save_knowledge_item(
            {
                "snapshot_id": snapshot["id"],
                "source_id": "eu_ai_act",
                "title": "EU AI Act Cybersecurity Update Revised",
                "category": "AI Regulation",
                "regulation_type": "AMENDMENT",
                "summary": "Cybersecurity obligations for connected devices.",
                "effective_date": "2026-07-01",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Network", "AI Features"],
                "requirements": ["Assess cybersecurity controls for devices"],
                "actions": ["Update compliance checklist"],
                "confidence": "HIGH",
            }
        )
        self.similar["created_at"] = "2026-07-01T09:00:00"

        self.other = self.store.save_knowledge_item(
            {
                "snapshot_id": snapshot["id"],
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

        self.all_items = [
            self.store.get_knowledge_item(self.primary["id"]),
            self.store.get_knowledge_item(self.similar["id"]),
            self.store.get_knowledge_item(self.other["id"]),
        ]

        self.client = TestClient(
            create_dashboard_app(storage_service=self.store)
        )

    def tearDown(self):
        self.client = None
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def test_similarity_detection(self):
        matches = find_similar_knowledge(
            self.all_items[0],
            self.all_items,
            threshold=0.8,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], self.similar["id"])
        self.assertGreaterEqual(matches[0]["similarity"], 0.8)
        self.assertTrue(matches[0]["reason"])

    def test_timeline_generation(self):
        timeline = build_regulation_timeline(
            "EU AI Act Cybersecurity Update",
            knowledge_items=self.all_items,
        )

        self.assertGreaterEqual(len(timeline), 2)
        dates = [event["date"] for event in timeline]
        self.assertIn("2026-07-01", dates)
        types = {event["type"] for event in timeline}
        self.assertTrue({"NEW", "AMENDMENT", "EFFECTIVE"} & types)

    def test_statistics_api(self):
        response = self.client.get("/api/knowledge/statistics")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["by_category"]["AI Regulation"], 2)
        self.assertEqual(data["by_category"]["Product Compliance"], 1)
        self.assertEqual(data["by_module"]["Network"], 2)
        self.assertEqual(len(data["latest_updates"]), 3)

    def test_statistics_page(self):
        response = self.client.get("/knowledge/statistics")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Knowledge Statistics", content)
        self.assertIn(b"Total Knowledge Items", content)
        self.assertIn(b"Knowledge by Category", content)
        self.assertIn(b"Knowledge by Product Module", content)
        self.assertIn(b"chart.js", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_similarity_render(self, mock_load_monitors):
        mock_load_monitors.return_value = [
            {
                "id": "eu_ai_act",
                "name": "EU AI Act",
                "url": "https://example.com/ai-act",
            }
        ]

        response = self.client.get(f"/knowledge/{self.primary['id']}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Similar Regulations", content)
        self.assertIn(b"EU AI Act Cybersecurity Update Revised", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_timeline_render(self, mock_load_monitors):
        mock_load_monitors.return_value = [
            {
                "id": "eu_ai_act",
                "name": "EU AI Act",
                "url": "https://example.com/ai-act",
            }
        ]

        response = self.client.get(f"/knowledge/{self.primary['id']}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Regulation Timeline", content)
        self.assertIn(b"2026-07-01", content)
        self.assertIn(b"Cybersecurity obligations", content)


class TestKnowledgeStatisticsBuilder(unittest.TestCase):

    def test_build_knowledge_statistics_structure(self):
        items = [
            {
                "id": 1,
                "title": "Item A",
                "category": "AI Regulation",
                "modules": ["Network"],
                "created_at": "2026-07-01T10:00:00",
            },
            {
                "id": 2,
                "title": "Item B",
                "category": "Product Compliance",
                "modules": ["Network", "Display"],
                "created_at": "2026-07-02T10:00:00",
            },
        ]

        stats = build_knowledge_statistics(items)

        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["by_category"]["AI Regulation"], 1)
        self.assertEqual(stats["by_module"]["Network"], 2)
        self.assertEqual(len(stats["latest_updates"]), 2)


if __name__ == "__main__":
    unittest.main()
