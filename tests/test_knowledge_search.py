import gc
import tempfile
import unittest
from pathlib import Path

from app.knowledge.search import highlight_matches, search_knowledge_items
from app.storage.service import StorageService


class TestKnowledgeSearch(unittest.TestCase):

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

        self.title_item = self.store.save_knowledge_item(
            {
                "snapshot_id": 1,
                "source_id": "eu_ai_act",
                "title": "EU AI Act Cybersecurity Framework",
                "category": "AI Regulation",
                "regulation_type": "NEW",
                "summary": "General device obligations.",
                "effective_date": "2028-08-02",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Display"],
                "requirements": ["Maintain documentation"],
                "actions": ["Review policy"],
                "confidence": "HIGH",
            }
        )

        self.summary_item = self.store.save_knowledge_item(
            {
                "snapshot_id": 2,
                "source_id": "eu_red",
                "title": "RED Directive Update",
                "category": "Product Compliance",
                "regulation_type": "NEW",
                "summary": "Cybersecurity requirements for radio equipment.",
                "effective_date": "2027-01-01",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Radio equipment"],
                "requirements": ["Update technical file"],
                "actions": ["Schedule review"],
                "confidence": "MEDIUM",
            }
        )

        self.module_item = self.store.save_knowledge_item(
            {
                "snapshot_id": 3,
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

    def tearDown(self):
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _search(self, query: str, **kwargs):
        return search_knowledge_items(
            query,
            get_items_fn=self.store.get_knowledge_items,
            get_item_fn=self.store.get_knowledge_item,
            **kwargs,
        )

    def test_title_score(self):
        results = self._search("cybersecurity")

        top = results[0]
        self.assertEqual(top["id"], self.title_item["id"])
        self.assertGreaterEqual(top["score"], 100)
        self.assertIn("title", top["matched_fields"])

    def test_summary_score(self):
        results = self._search("Cybersecurity")

        matched = next(
            result for result in results if result["id"] == self.summary_item["id"]
        )
        self.assertGreaterEqual(matched["score"], 60)
        self.assertIn("summary", matched["matched_fields"])

    def test_module_score(self):
        results = self._search("Network")

        matched = next(
            result for result in results if result["id"] == self.module_item["id"]
        )
        self.assertGreaterEqual(matched["score"], 80)
        self.assertIn("modules", matched["matched_fields"])

    def test_category_filter(self):
        results = self._search(
            "Cybersecurity",
            category="Product Compliance",
        )

        self.assertTrue(results)
        self.assertTrue(
            all(result["category"] == "Product Compliance" for result in results)
        )
        self.assertNotIn(
            self.title_item["id"],
            {result["id"] for result in results},
        )

    def test_empty_query(self):
        results = self._search("")

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["score"], 5)
        self.assertEqual(results[0]["matched_fields"], [])

    def test_limit(self):
        results = self._search("", limit=2)

        self.assertEqual(len(results), 2)

    def test_sorting(self):
        high_match = self.store.save_knowledge_item(
            {
                "snapshot_id": 4,
                "source_id": "combo",
                "title": "Cybersecurity Network AI Act",
                "category": "AI Regulation",
                "regulation_type": "AMENDMENT",
                "summary": "Cybersecurity and network compliance update.",
                "effective_date": "2028-01-01",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Network"],
                "requirements": ["Cybersecurity assessment required"],
                "actions": ["Cybersecurity remediation plan"],
                "confidence": "HIGH",
            }
        )

        results = self._search("Cybersecurity")

        self.assertEqual(results[0]["id"], high_match["id"])
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_highlight(self):
        highlighted = highlight_matches(
            "AI cybersecurity requirement",
            ["cybersecurity"],
        )

        self.assertEqual(
            highlighted,
            "AI <mark>cybersecurity</mark> requirement",
        )


if __name__ == "__main__":
    unittest.main()
